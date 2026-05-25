"""
路由器核心实现
"""
import socket
import struct
import logging
import threading
import queue
import time
import errno
import os
import json
from typing import Dict, Optional, List, Tuple, Set
from datetime import datetime
from .constants import (
    MessageType, LinkState, RouterConfig, Link, 
    UDP_BUFFER_SIZE, LSA_SEND_INTERVAL, HEARTBEAT_INTERVAL, 
    HEARTBEAT_TIMEOUT, Constants
)
from .lsa import LSADatabase, RouterLSA, LSAPacket, LSAEventType, LSAEvent, lsa_event_log
from .topology import TopologyDB, RoutingTable
from .protocol import PathCalculator

# 配置日志
logging.basicConfig(format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')

class Router:
    """路由器类 - 代表一个路由器实例"""
    
    def __init__(self, router_id: int, router_name: str, listen_port: int, listen_ip: str = '127.0.0.1'):
        """初始化路由器"""
        self.router_id = router_id
        self.router_name = router_name
        self.listen_port = listen_port
        self.listen_ip = listen_ip
        
        # 邻接信息：{neighbor_id: {'ip': str, 'port': int, 'state': 'up'/'down', 'heartbeat_lost_count': int}}
        self._neighbors: Dict[int, Dict] = {}
        
        # 日志
        self.logger = logging.getLogger(f'Router{router_id}')
        self.logger.setLevel(logging.INFO)

        # 拓扑管理
        self.topology = TopologyDB()
        self.lsa_database = LSADatabase()
        self.routing_table = RoutingTable(router_id)

        # 路径计算
        self.path_calculator = PathCalculator(router_id, self.topology, self.routing_table, self.logger)
        
        # 线程管理
        self._running = False
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()  # 用于保护共享数据结构
        
        # 消息队列
        self._recv_queue: queue.Queue = queue.Queue()
        self._send_queue: queue.Queue = queue.Queue()
        
        # UDP套接字
        self._socket: Optional[socket.socket] = None
        
        # LSA相关
        self._lsa_sequence = 0
        self._last_lsa_sent = {}  # {neighbor_id: timestamp}
        
        # 心跳相关
        self._last_heartbeat_recv: Dict[int, float] = {}  # {neighbor_id: timestamp}

        # 运行时参数（可由仿真器按拓扑规模动态覆盖）
        self._lsa_send_interval = LSA_SEND_INTERVAL
        self._heartbeat_interval = HEARTBEAT_INTERVAL
        self._heartbeat_timeout_threshold = HEARTBEAT_TIMEOUT
        self._failure_detection_silence_until = 0.0
        self._spf_min_interval = 0.2
        self._last_spf_calc_time = 0.0
        self._spf_pending = False
        
        # 事件监听器
        self._event_listeners: List[callable] = []

    def apply_runtime_profile(
        self,
        lsa_send_interval: Optional[float] = None,
        heartbeat_interval: Optional[float] = None,
        heartbeat_timeout_threshold: Optional[int] = None,
        failure_detection_silence_seconds: float = 0.0,
        spf_min_interval: Optional[float] = None,
        log_level: Optional[int] = None,
    ):
        """应用运行时配置，用于大拓扑稳态优化。"""
        with self._lock:
            if lsa_send_interval is not None:
                self._lsa_send_interval = max(0.2, float(lsa_send_interval))

            if heartbeat_interval is not None:
                self._heartbeat_interval = max(0.2, float(heartbeat_interval))

            if heartbeat_timeout_threshold is not None:
                self._heartbeat_timeout_threshold = max(1, int(heartbeat_timeout_threshold))

            if failure_detection_silence_seconds > 0:
                self._failure_detection_silence_until = time.time() + float(failure_detection_silence_seconds)

            if spf_min_interval is not None:
                self._spf_min_interval = max(0.05, float(spf_min_interval))

            if log_level is not None:
                self.logger.setLevel(log_level)
    
    def add_neighbor(self, neighbor_id: int, neighbor_ip: str, neighbor_port: int, link_cost: int = 1):
        """添加邻接路由器"""
        with self._lock:
            self._neighbors[neighbor_id] = {
                'ip': neighbor_ip,
                'port': neighbor_port,
                'cost': link_cost,
                'state': 'down',  # 初始状态为down，直到收到第一条消息
                'heartbeat_lost_count': 0,
                'last_seen': time.time()
            }
            
            # 添加到本地拓扑
            self.topology.add_router(self.router_id)
            self.topology.add_router(neighbor_id)
            self.topology.add_link(self.router_id, neighbor_id, link_cost)
            
            self.logger.info(f"添加邻接路由器 {neighbor_id} ({neighbor_ip}:{neighbor_port}), 链路开销={link_cost}")
    
    def remove_neighbor(self, neighbor_id: int):
        """移除邻接路由器"""
        with self._lock:
            if neighbor_id in self._neighbors:
                state_was_up = self._neighbors[neighbor_id].get('state') == 'up'
                del self._neighbors[neighbor_id]
                self.topology.remove_link(self.router_id, neighbor_id)
                self.logger.info(f"移除邻接路由器 {neighbor_id}")
                
                # 链路移除后需立刻触发LSA刷新，以模拟链路中断对全网的影响
                if state_was_up:
                    self._send_lsa()
                    self._trigger_spf_calculation()
    
    def start(self):
        """启动路由器"""
        if self._running:
            self.logger.warning("路由器已经启动")
            return
        
        self._running = True
        self.logger.info(f"启动路由器 {self.router_name} (ID={self.router_id}) 在 {self.listen_ip}:{self.listen_port}")
        
        # 初始化UDP套接字
        self._init_socket()
        
        # 启动各个线程
        self._start_threads()
    
    def stop(self):
        """停止路由器"""
        if not self._running:
            return
        
        self._running = False
        self.logger.info(f"停止路由器 {self.router_name}")

        # 等待所有线程结束
        for thread_name, thread in self._threads.items():
            if thread.is_alive():
                thread.join(timeout=2)

        # 线程退出后再关闭套接字，避免发送线程在关闭后误报10038
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
    
    def _init_socket(self):
        """初始化UDP套接字"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Windows 下开启 SO_REUSEADDR 可能导致多个进程绑定同一UDP端口，
            # 造成消息被其他进程抢占，表现为邻接始终 down。
            if os.name != 'nt':
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.listen_ip, self.listen_port))
            self._socket.settimeout(1.0)  # 设置1秒超时
            self.logger.info(f"UDP套接字已绑定到 {self.listen_ip}:{self.listen_port}")
        except Exception as e:
            self.logger.error(f"初始化UDP套接字失败: {e}")
            raise
    
    def _start_threads(self):
        """启动工作线程"""
        # 接收线程
        recv_thread = threading.Thread(target=self._recv_thread, daemon=True, name='Recv')
        recv_thread.start()
        self._threads['recv'] = recv_thread
        
        # 发送线程
        send_thread = threading.Thread(target=self._send_thread, daemon=True, name='Send')
        send_thread.start()
        self._threads['send'] = send_thread
        
        # 处理线程
        process_thread = threading.Thread(target=self._process_thread, daemon=True, name='Process')
        process_thread.start()
        self._threads['process'] = process_thread
        
        # 定时LSA发送线程
        lsa_thread = threading.Thread(target=self._lsa_thread, daemon=True, name='LSA')
        lsa_thread.start()
        self._threads['lsa'] = lsa_thread
        
        # 心跳线程
        heartbeat_thread = threading.Thread(target=self._heartbeat_thread, daemon=True, name='Heartbeat')
        heartbeat_thread.start()
        self._threads['heartbeat'] = heartbeat_thread

        # SPF节流线程：合并高频触发请求，降低大拓扑计算抖动
        spf_thread = threading.Thread(target=self._spf_thread, daemon=True, name='SPF')
        spf_thread.start()
        self._threads['spf'] = spf_thread
    
    def _recv_thread(self):
        """接收UDP消息的线程"""
        while self._running:
            try:
                data, (src_ip, src_port) = self._socket.recvfrom(UDP_BUFFER_SIZE)
                self._recv_queue.put((data, src_ip, src_port))
            except socket.timeout:
                continue
            except ConnectionResetError:
                # 忽略Windows特有的UDP连接重置错误（当发往的端口未监听时会出现）
                continue
            except Exception as e:
                if self._running:
                    self.logger.error(f"接收消息异常: {e}")
    
    def _send_thread(self):
        """发送UDP消息的线程"""
        while self._running:
            try:
                item = self._send_queue.get(timeout=1.0)
                if item is None:
                    continue
                
                target_ip, target_port, message = item
                self._socket.sendto(message, (target_ip, target_port))
                self.logger.debug(f"向 {target_ip}:{target_port} 发送消息")
            except queue.Empty:
                continue
            except Exception as e:
                # 关闭流程中套接字失效属于预期，不输出噪声日志
                if not self._running:
                    continue
                if isinstance(e, OSError) and getattr(e, 'winerror', None) == 10038:
                    continue
                self.logger.error(f"发送消息异常: {e}")
    
    def _process_thread(self):
        """处理接收到的消息的线程"""
        while self._running:
            try:
                data, src_ip, src_port = self._recv_queue.get(timeout=1.0)
                self._process_message(data, src_ip, src_port)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"处理消息异常: {e}")
    
    def _lsa_thread(self):
        """定期发送LSA的线程"""
        while self._running:
            time.sleep(self._lsa_send_interval)
            try:
                self._send_lsa()
            except Exception as e:
                self.logger.error(f"LSA发送异常: {e}")
    
    def _heartbeat_thread(self):
        """定期发送心跳消息的线程"""
        while self._running:
            time.sleep(self._heartbeat_interval)
            try:
                self._send_heartbeat()
                self._check_heartbeat_timeout()
            except Exception as e:
                self.logger.error(f"心跳异常: {e}")

    def _spf_thread(self):
        """SPF计算调度线程：按节流窗口合并执行。"""
        while self._running:
            time.sleep(0.05)
            try:
                self._flush_pending_spf()
            except Exception as e:
                self.logger.error(f"SPF调度异常: {e}")
    
    def _process_message(self, data: bytes, src_ip: str, src_port: int):
        """处理接收到的消息"""
        if len(data) < 1:
            return
        
        msg_type = data[0]
        
        if msg_type == MessageType.HEARTBEAT:
            self._handle_heartbeat(data, src_ip, src_port)
        elif msg_type == MessageType.HELLO:
            self._handle_hello(data, src_ip, src_port)
        elif msg_type == MessageType.LSA:
            self._handle_lsa(data, src_ip, src_port)
        elif msg_type == MessageType.ACK:
            self._handle_ack(data, src_ip, src_port)
    
    def _handle_heartbeat(self, data: bytes, src_ip: str, src_port: int):
        """处理心跳消息"""
        try:
            # 心跳消息格式: [type:1][source_id:4]
            msg_type, source_id = struct.unpack('!BI', data[:5])
            
            with self._lock:
                if source_id not in self._neighbors:
                    self.logger.debug(f"收到来自未知路由器 {source_id} 的心跳")
                    return
                
                neighbor = self._neighbors[source_id]
                neighbor['heartbeat_lost_count'] = 0
                neighbor['last_seen'] = time.time()
                self._last_heartbeat_recv[source_id] = time.time()
                
                # 更新邻接状态
                if neighbor['state'] != 'up':
                    neighbor['state'] = 'up'
                    self.logger.info(f"邻接路由器 {source_id} 已恢复")
                    self._on_neighbor_up(source_id)
        except Exception as e:
            self.logger.error(f"处理心跳消息异常: {e}")
    
    def _handle_hello(self, data: bytes, src_ip: str, src_port: int):
        """处理HELLO消息（邻居发现）"""
        try:
            # HELLO消息格式: [type:1][source_id:4]
            msg_type, source_id = struct.unpack('!BI', data[:5])
            
            # 回复心跳
            self._send_heartbeat_to(source_id)
            
            self.logger.debug(f"收到来自路由器 {source_id} 的HELLO消息")
        except Exception as e:
            self.logger.error(f"处理HELLO消息异常: {e}")
    
    def _handle_lsa(self, data: bytes, src_ip: str, src_port: int):
        """处理LSA消息"""
        try:
            lsa_packet = LSAPacket.from_bytes(data)
            source_id = lsa_packet.source_router_id
            need_spf = False
            
            with self._lock:
                # 检查是否为新LSA
                is_new = self.lsa_database.is_new_lsa(source_id, lsa_packet.sequence_number)
                if not is_new:
                    current = self.lsa_database.get_lsa(source_id)
                    current_seq = current.sequence_number if current else -1
                    if lsa_packet.sequence_number == current_seq:
                        self.logger.debug(f"收到重复的LSA，源={source_id}, 序列号={lsa_packet.sequence_number}")
                        lsa_event_log.push(LSAEvent(
                            timestamp=time.time(),
                            event_type=LSAEventType.RECEIVED_DUP,
                            source_router_id=source_id,
                            seq_number=lsa_packet.sequence_number,
                            router_id=self.router_id,
                            detail=f"Router{self.router_id} 丢弃重复LSA from R{source_id} seq={lsa_packet.sequence_number}",
                            hop_count=lsa_packet.hop_count,
                        ))
                    else:
                        self.logger.debug(f"收到旧的LSA，源={source_id}, 序列号={lsa_packet.sequence_number}")
                        lsa_event_log.push(LSAEvent(
                            timestamp=time.time(),
                            event_type=LSAEventType.RECEIVED_OLD,
                            source_router_id=source_id,
                            seq_number=lsa_packet.sequence_number,
                            router_id=self.router_id,
                            detail=f"Router{self.router_id} 丢弃旧LSA from R{source_id} seq={lsa_packet.sequence_number}(已有seq={current_seq})",
                            hop_count=lsa_packet.hop_count,
                        ))
                    return

                # 更新LSA数据库
                self.lsa_database.update_lsa(source_id, lsa_packet.lsa_data)
                self.logger.info(f"收到新的LSA，源={source_id}, 序列号={lsa_packet.sequence_number}")

                # 发布 LSA 接收事件（新）
                lsa_event_log.push(LSAEvent(
                    timestamp=time.time(),
                    event_type=LSAEventType.RECEIVED_NEW,
                    source_router_id=source_id,
                    seq_number=lsa_packet.sequence_number,
                    router_id=self.router_id,
                    detail=f"Router{self.router_id} 接受新LSA from R{source_id} seq={lsa_packet.sequence_number}",
                    hop_count=lsa_packet.hop_count,
                ))

                # 更新拓扑
                self._update_topology_from_lsa(lsa_packet.lsa_data)

                # 转发LSA（除了来源和发送者）
                if lsa_packet.hop_count > 1:
                    self._flood_lsa(lsa_packet, source_id)
                else:
                    lsa_event_log.push(LSAEvent(
                        timestamp=time.time(),
                        event_type=LSAEventType.DISCARDED_TTL,
                        source_router_id=source_id,
                        seq_number=lsa_packet.sequence_number,
                        router_id=self.router_id,
                        detail=f"Router{self.router_id} TTL耗尽，停止转发 from R{source_id}",
                        hop_count=0,
                    ))

                # 锁外触发SPF计算，避免长时间持锁阻塞心跳处理
                need_spf = True

            if need_spf:
                self._trigger_spf_calculation()
        except Exception as e:
            self.logger.error(f"处理LSA消息异常: {e}")
    
    def _handle_ack(self, data: bytes, src_ip: str, src_port: int):
        """处理ACK消息"""
        pass  # 暂未实现ACK机制
    
    def _update_topology_from_lsa(self, lsa: RouterLSA):
        """从LSA更新拓扑"""
        with self._lock:
            # 添加源路由器
            self.topology.add_router(lsa.router_id)
            
            # 获取源路由器在当前拓扑数据库中的旧邻居集合
            old_neighbors = self.topology.get_neighbors(lsa.router_id)
            new_neighbors = set()

            # 更新链路
            for link in lsa.links:
                self.topology.add_router(link.dest_id)

                if link.state == LinkState.UP:
                    self.topology.add_link(lsa.router_id, link.dest_id, link.cost)
                    new_neighbors.add(link.dest_id)
                else:
                    self.topology.remove_link(lsa.router_id, link.dest_id)
            
            # 彻底移除 LSA 中已不包含的过时/断开的链路
            for stale_neighbor in old_neighbors - new_neighbors:
                self.topology.remove_link(lsa.router_id, stale_neighbor)

    def _flood_lsa(self, lsa_packet: LSAPacket, except_sender_id: int):
        """泛洪LSA到所有邻接路由器（除了发送者）"""
        lsa_packet.hop_count -= 1
        message = lsa_packet.to_bytes()

        with self._lock:
            forwarded_to = []
            for neighbor_id, neighbor_info in self._neighbors.items():
                if neighbor_id == except_sender_id:
                    continue

                if neighbor_info['state'] == 'up':
                    self._send_queue.put((
                        neighbor_info['ip'],
                        neighbor_info['port'],
                        message
                    ))
                    forwarded_to.append(neighbor_id)

        if forwarded_to:
            lsa_event_log.push(LSAEvent(
                timestamp=time.time(),
                event_type=LSAEventType.FORWARDED,
                source_router_id=lsa_packet.source_router_id,
                seq_number=lsa_packet.sequence_number,
                router_id=self.router_id,
                detail=f"Router{self.router_id} 洪泛LSA(from R{lsa_packet.source_router_id}) → {forwarded_to}",
                hop_count=lsa_packet.hop_count,
            ))
    
    def _send_lsa(self):
        """发送LSA"""
        with self._lock:
            # 构建当前的LSA
            lsa = RouterLSA(
                router_id=self.router_id,
                sequence_number=self._lsa_sequence,
                links=[
                    Link(
                        dest_id=neighbor_id,
                        cost=neighbor_info['cost'],
                        state=LinkState.UP if neighbor_info['state'] == 'up' else LinkState.DOWN
                    )
                    for neighbor_id, neighbor_info in self._neighbors.items()
                ]
            )
            
            self._lsa_sequence += 1
            
            # 更新自己的LSA数据库
            self.lsa_database.update_lsa(self.router_id, lsa)
            
            # 创建和发送LSA包
            lsa_packet = LSAPacket(
                packet_type=MessageType.LSA,
                source_router_id=self.router_id,
                sequence_number=lsa.sequence_number,
                lsa_data=lsa,
                hop_count=30
            )
            
            message = lsa_packet.to_bytes()
            
            # 发送到所有邻接路由器
            for neighbor_id, neighbor_info in self._neighbors.items():
                if neighbor_info['state'] == 'up':
                    self._send_queue.put((
                        neighbor_info['ip'],
                        neighbor_info['port'],
                        message
                    ))
            
            self.logger.debug(f"发送LSA，源={self.router_id}, 序列号={lsa.sequence_number}")

            # 发布 LSA 创建事件
            lsa_event_log.push(LSAEvent(
                timestamp=time.time(),
                event_type=LSAEventType.CREATED,
                source_router_id=self.router_id,
                seq_number=lsa.sequence_number,
                router_id=self.router_id,
                detail=f"Router{self.router_id} 生成新LSA seq={lsa.sequence_number}",
                hop_count=30,
            ))
    
    def _send_heartbeat(self):
        """发送心跳消息到所有邻接路由器"""
        heartbeat_msg = struct.pack('!BI', MessageType.HEARTBEAT, self.router_id)
        
        with self._lock:
            for neighbor_id, neighbor_info in self._neighbors.items():
                self._send_queue.put((
                    neighbor_info['ip'],
                    neighbor_info['port'],
                    heartbeat_msg
                ))
    
    def _send_heartbeat_to(self, neighbor_id: int):
        """发送心跳消息到指定邻接路由器"""
        if neighbor_id not in self._neighbors:
            return
        
        heartbeat_msg = struct.pack('!BI', MessageType.HEARTBEAT, self.router_id)
        neighbor_info = self._neighbors[neighbor_id]
        self._send_queue.put((
            neighbor_info['ip'],
            neighbor_info['port'],
            heartbeat_msg
        ))
    
    def _check_heartbeat_timeout(self):
        """检查心跳超时"""
        current_time = time.time()

        # 切拓扑后短暂静默，避免启动阶段误判邻居故障
        if current_time < self._failure_detection_silence_until:
            return
        
        with self._lock:
            for neighbor_id, neighbor_info in list(self._neighbors.items()):
                last_seen = neighbor_info['last_seen']
                expected_interval = self._heartbeat_interval * (self._heartbeat_timeout_threshold + 1)
                
                if current_time - last_seen > expected_interval:
                    neighbor_info['heartbeat_lost_count'] += 1
                    
                    if neighbor_info['heartbeat_lost_count'] >= self._heartbeat_timeout_threshold:
                        if neighbor_info['state'] == 'up':
                            neighbor_info['state'] = 'down'
                            self.logger.warning(f"邻接路由器 {neighbor_id} 已故障")
                            self._on_neighbor_down(neighbor_id)
    
    def _on_neighbor_up(self, neighbor_id: int):
        """邻接路由器恢复时的处理"""
        self.logger.info(f"邻接路由器 {neighbor_id} Up事件")
        # 立即发送LSA
        self._send_lsa()
        # 触发SPF重新计算
        self._trigger_spf_calculation()
    
    def _on_neighbor_down(self, neighbor_id: int):
        """邻接路由器故障时的处理"""
        self.logger.info(f"邻接路由器 {neighbor_id} Down事件")
        # 更新拓扑中的链路状态
        with self._lock:
            self.topology.remove_link(self.router_id, neighbor_id)
        
        # 立即发送LSA
        self._send_lsa()
        # 触发SPF重新计算
        self._trigger_spf_calculation()
    
    def _trigger_spf_calculation(self):
        """触发SPF计算"""
        should_compute = False
        with self._lock:
            now = time.time()
            elapsed = now - self._last_spf_calc_time

            # 尚未到节流窗口，标记待处理并返回
            if elapsed < self._spf_min_interval:
                self._spf_pending = True
                return

            self._last_spf_calc_time = now
            self._spf_pending = False
            should_compute = True

        if should_compute:
            self.logger.debug(f"触发SPF计算 on 路由器 {self.router_id}")
            self.path_calculator.calculate_routes_dijkstra()

    def _flush_pending_spf(self):
        """如果存在挂起的SPF请求且到达时间窗口，则执行一次计算。"""
        should_compute = False
        with self._lock:
            if not self._spf_pending:
                return

            now = time.time()
            if now - self._last_spf_calc_time < self._spf_min_interval:
                return

            self._last_spf_calc_time = now
            self._spf_pending = False
            should_compute = True

        if should_compute:
            self.logger.debug(f"执行合并后的SPF计算 on 路由器 {self.router_id}")
            self.path_calculator.calculate_routes_dijkstra()
    
    def get_lsa_data(self) -> Dict:
        """获取当前的LSA数据（用于UI显示）"""
        with self._lock:
            return {
                'router_id': self.router_id,
                'sequence': self._lsa_sequence,
                'neighbors': {
                    nid: {
                        'state': ninfo['state'],
                        'cost': ninfo['cost'],
                        'lost_count': ninfo['heartbeat_lost_count']
                    }
                    for nid, ninfo in self._neighbors.items()
                }
            }
    
    def get_topology_data(self) -> Dict:
        """获取拓扑数据（用于UI显示）"""
        with self._lock:
            edges = []
            nodes = []

            # 使用拓扑图的当前视图渲染
            node_ids = set(self.topology.get_all_routers())
            node_ids.add(self.router_id)

            for src, dest in self.topology.graph.edges:
                edges.append({
                    'source': src,
                    'target': dest,
                    'cost': self.topology.get_link_cost(src, dest)
                })

            for nid in sorted(node_ids):
                nodes.append({
                    'id': nid,
                    'label': f'Router{nid}',
                    'is_self': (nid == self.router_id)
                })

            return {
                'nodes': nodes,
                'edges': edges
            }
    
    def register_event_listener(self, callback: callable):
        """注册事件监听器"""
        with self._lock:
            self._event_listeners.append(callback)
    
    def _emit_event(self, event_type: str, data: Dict):
        """触发事件"""
        for listener in self._event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                self.logger.error(f"事件处理异常: {e}")
