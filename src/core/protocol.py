"""
SPF计算和路由表管理
"""
import threading
import logging
from typing import Dict, List, Tuple, Optional
from .topology import TopologyDB, RoutingTable
from ..algorithms.dijkstra import DijkstraAlgorithm
from ..algorithms.new_algorithm import NewAlgorithm
from ..algorithms.duan_algorithm import DuanAlgorithm
from ..algorithms.extended_algorithms import (
    BellmanFordAlgorithm,
    SPFAAlgorithm,
    PrimMSTBaseline,
    FloydWarshallAlgorithm,
    AStarAllTargetsAlgorithm,
)

class PathCalculator:
    """路径计算器 - 执行SPF算法"""
    
    def __init__(self, router_id: int, topology: TopologyDB, routing_table: RoutingTable, logger=None):
        self.router_id = router_id
        self.topology = topology
        self.routing_table = routing_table
        self.logger = logger or logging.getLogger(f'PathCalc{router_id}')
        
        # 算法实例
        self.dijkstra_algo = DijkstraAlgorithm()
        self.new_algo = NewAlgorithm()
        self.bellman_ford_algo = BellmanFordAlgorithm()
        self.spfa_algo = SPFAAlgorithm()
        self.prim_mst_algo = PrimMSTBaseline()
        self.floyd_warshall_algo = FloydWarshallAlgorithm()
        self.astar_algo = AStarAllTargetsAlgorithm()
        self.duan_algo = DuanAlgorithm()

        self.algorithm_registry = {
            'dijkstra': ('Dijkstra', self.dijkstra_algo),
            'new_algo': ('NewAlgorithm', self.new_algo),
            'duan': ('Duan2025', self.duan_algo),
            'bellman_ford': ('BellmanFord', self.bellman_ford_algo),
            'spfa': ('SPFA', self.spfa_algo),
            'prim_mst': ('PrimMSTBaseline', self.prim_mst_algo),
            'floyd_warshall': ('FloydWarshall', self.floyd_warshall_algo),
            'astar': ('AStarAllTargets', self.astar_algo),
        }
        
        self._lock = threading.RLock()
        self.last_calculation_time = None
        self.algo_statistics = {}
    
    def _build_adjacency_list(self) -> Dict[int, List[Tuple[int, int]]]:
        """从拓扑构建邻接表"""
        adj_list = {}
        
        for node in self.topology.get_all_routers():
            adj_list[node] = []
            for neighbor in self.topology.get_neighbors(node):
                cost = self.topology.get_link_cost(node, neighbor)
                if cost != 65535:  # 65535为INFINITY
                    adj_list[node].append((neighbor, cost))
        
        return adj_list
    
    def calculate_routes_dijkstra(self) -> bool:
        """使用Dijkstra算法计算路由"""
        with self._lock:
            try:
                adj_list = self._build_adjacency_list()
                
                # 执行Dijkstra算法
                shortest_paths = self.dijkstra_algo.calculate_shortest_paths(
                    self.router_id, adj_list
                )
                
                # 更新路由表
                self.routing_table.clear()
                
                for dest, (cost, path) in shortest_paths.items():
                    if path and len(path) >= 2:
                        next_hop = path[1]  # 第二个节点是下一跳
                        self.routing_table.update_route(dest, next_hop, cost, path)
                
                # 记录统计信息
                self.algo_statistics['dijkstra'] = self.dijkstra_algo.get_statistics()
                
                self.logger.info(f"Dijkstra计算完成，计算时间={self.dijkstra_algo.computation_time*1000:.3f}ms")
                return True
                
            except Exception as e:
                self.logger.error(f"Dijkstra计算异常: {e}")
                return False
    
    def calculate_routes_new_algorithm(self) -> bool:
        """使用新算法计算路由"""
        with self._lock:
            try:
                adj_list = self._build_adjacency_list()
                
                # 执行新算法
                shortest_paths = self.new_algo.calculate_shortest_paths(
                    self.router_id, adj_list
                )
                
                # 更新路由表（仅用于演示，实际应该用另一个表进行对比）
                self.routing_table.clear()
                
                for dest, (cost, path) in shortest_paths.items():
                    if path and len(path) >= 2:
                        next_hop = path[1]
                        self.routing_table.update_route(dest, next_hop, cost, path)
                
                # 记录统计信息
                self.algo_statistics['new_algo'] = self.new_algo.get_statistics()
                
                self.logger.info(f"NewAlgo计算完成，计算时间={self.new_algo.computation_time*1000:.3f}ms")
                return True
                
            except Exception as e:
                self.logger.error(f"NewAlgo计算异常: {e}")
                return False
    
    def calculate_all_routes(self) -> Dict[str, Dict]:
        """计算并返回多种算法的统计对比。"""
        results = {}

        adj_list = self._build_adjacency_list()
        for key, (_, algo_obj) in self.algorithm_registry.items():
            try:
                algo_obj.calculate_shortest_paths(self.router_id, adj_list)
                stats = algo_obj.get_statistics()
                self.algo_statistics[key] = stats
                results[key] = stats
            except Exception as e:
                self.logger.error(f"{key} 计算异常: {e}")
        
        return results

    def benchmark_algorithms(self, runs: int = 30) -> Dict[str, Dict]:
        """多轮基准测试，返回平均/最小/最大耗时和平均迭代统计。"""
        with self._lock:
            adj_list = self._build_adjacency_list()
            if not adj_list:
                return {}

            runs = max(1, runs)

            def _bench_one(algo_name: str, algo_obj) -> Dict:
                times = []
                iterations = []
                visited_nodes = []
                relaxations = []

                for _ in range(runs):
                    algo_obj.calculate_shortest_paths(self.router_id, adj_list)
                    stats = algo_obj.get_statistics()
                    times.append(float(stats.get('computation_time', 0.0)))
                    iterations.append(int(stats.get('iterations', 0)))
                    visited_nodes.append(int(stats.get('visited_nodes', 0)))
                    if 'relaxation_count' in stats:
                        relaxations.append(int(stats.get('relaxation_count', 0)))

                result = {
                    'algorithm_name': algo_name,
                    'runs': runs,
                    'avg_time_ms': sum(times) / len(times),
                    'min_time_ms': min(times),
                    'max_time_ms': max(times),
                    'avg_iterations': sum(iterations) / len(iterations),
                    'avg_visited_nodes': sum(visited_nodes) / len(visited_nodes),
                }

                if relaxations:
                    result['avg_relaxation_count'] = sum(relaxations) / len(relaxations)

                return result

            benchmark_results = {}
            for key, (display_name, algo_obj) in self.algorithm_registry.items():
                benchmark_results[key] = _bench_one(display_name, algo_obj)
            return benchmark_results
    
    def get_routing_table(self) -> Dict[int, Tuple[int, int, List[int]]]:
        """获取路由表"""
        with self._lock:
            return self.routing_table.get_all_routes()
    
    def get_route_to(self, destination: int) -> Optional[Tuple[int, int, List[int]]]:
        """获取到指定目标的路由"""
        with self._lock:
            return self.routing_table.get_route(destination)
