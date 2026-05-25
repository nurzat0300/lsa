"""
主窗口UI
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QComboBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QStatusBar, QTextEdit
)
from PyQt5.QtCore import QTimer, QObject, pyqtSignal
import threading

from .topology_view import NetworkTopologyWidget
from .teaching_demo import TeachingDemoWidget
from .animation_view import AlgorithmAnimationWidget
from .lsa_monitor import LSAMonitorWidget
from .neighbor_monitor import NeighborMonitorWidget
from .styles import apply_stylesheet


class BenchmarkWorker(QObject):
    """后台执行算法对比，避免阻塞UI线程。"""

    finished = pyqtSignal(dict, int)
    failed = pyqtSignal(str)

    def __init__(self, path_calculator, runs: int):
        super().__init__()
        self.path_calculator = path_calculator
        self.runs = runs

    def run(self):
        try:
            results = self.path_calculator.benchmark_algorithms(runs=self.runs)
            self.finished.emit(results, self.runs)
        except Exception as e:
            self.failed.emit(str(e))


class TopologySwitchWorker(QObject):
    """后台切换拓扑配置，避免阻塞UI线程。"""

    finished = pyqtSignal(bool, str, str)

    def __init__(self, simulator, config_file: str, profile_text: str):
        super().__init__()
        self.simulator = simulator
        self.config_file = config_file
        self.profile_text = profile_text

    def run(self):
        ok = self.simulator.switch_topology_profile(self.config_file)
        self.finished.emit(ok, self.profile_text, self.config_file)


class RoutingTableWidget(QWidget):
    """路由表显示窗口"""
    
    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self.init_ui()
        
        # 定时更新
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_tables)
        self.timer.start(2000)  # 每2秒更新一次
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 路由器选择
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("选择路由器:"))
        
        self.router_combo = QComboBox()
        self.router_combo.currentTextChanged.connect(self.on_router_changed)
        select_layout.addWidget(self.router_combo)
        select_layout.addStretch()
        
        layout.addLayout(select_layout)
        
        # 路由表
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['目标', '下一跳', '成本', '完整路径', '跳数'])
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 300)
        self.table.setColumnWidth(4, 80)
        
        layout.addWidget(self.table)
        
        # 拓扑信息
        info_layout = QHBoxLayout()
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        
        layout.addWidget(QLabel("拓扑信息:"))
        layout.addWidget(self.info_text)
        
        self.setLayout(layout)
        
        # 初始化路由器列表
        self.update_router_list()
    
    def update_router_list(self):
        """更新可用的路由器列表"""
        self.router_combo.blockSignals(True)
        current = self.router_combo.currentText()
        self.router_combo.clear()
        
        for router_id in sorted(self.simulator.routers.keys()):
            router = self.simulator.routers[router_id]
            self.router_combo.addItem(f"{router.router_name} (ID: {router_id})", router_id)
        
        if current:
            index = self.router_combo.findText(current)
            if index >= 0:
                self.router_combo.setCurrentIndex(index)
        
        self.router_combo.blockSignals(False)
    
    def on_router_changed(self):
        """路由器选择改变"""
        self.refresh_tables()
    
    def refresh_tables(self):
        """刷新路由表"""
        router_id = self.router_combo.currentData()
        if not router_id:
            return
        
        router = self.simulator.routers.get(router_id)
        if not router:
            return
        
        # 更新路由表
        routes = router.routing_table.get_all_routes()
        self.table.setRowCount(len(routes))
        
        for row, (dest, (next_hop, cost, path)) in enumerate(sorted(routes.items())):
            path_str = ' → '.join(map(str, path))
            hop_count = len(path) - 1
            
            self.table.setItem(row, 0, QTableWidgetItem(str(dest)))
            self.table.setItem(row, 1, QTableWidgetItem(str(next_hop)))
            self.table.setItem(row, 2, QTableWidgetItem(str(cost)))
            self.table.setItem(row, 3, QTableWidgetItem(path_str))
            self.table.setItem(row, 4, QTableWidgetItem(str(hop_count)))
        
        # 更新拓扑信息
        neighbors = list(router._neighbors.keys())
        neighbors_str = ', '.join(map(str, neighbors)) if neighbors else '无'
        lsa_seq = router._lsa_sequence
        
        info = f"""
路由器 {router_id} ({router.router_name}) 拓扑信息:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
邻接路由器: {neighbors_str}
已知拓扑节点: {', '.join(map(str, sorted(router.topology.get_all_routers())))}
LSA序列号: {lsa_seq}
已缓存LSA数目: {len(router.lsa_database.get_all_lsas())}
        """.strip()
        
        self.info_text.setText(info)


class AlgorithmComparisonWidget(QWidget):
    """算法对比窗口"""
    
    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self._worker = None
        self._worker_thread = None
        self.algorithm_display_map = {
            'dijkstra': 'Dijkstra算法',
            'new_algo': '新型算法(分层桶)',
            'duan': 'Duan2025(STOC最佳)',
            'bellman_ford': 'Bellman-Ford算法',
            'spfa': 'SPFA算法',
            'prim_mst': 'Prim(MST基线)',
            'floyd_warshall': 'Floyd-Warshall算法',
            'astar': 'A*算法(多目标)',
        }
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 选择路由器
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("选择源路由器:"))
        
        self.router_combo = QComboBox()
        select_layout.addWidget(self.router_combo)

        select_layout.addWidget(QLabel("测试轮数:"))
        self.runs_spin = QSpinBox()
        self.runs_spin.setMinimum(1)
        self.runs_spin.setMaximum(500)
        self.runs_spin.setValue(10)
        select_layout.addWidget(self.runs_spin)
        
        compute_btn = QPushButton("执行对比计算")
        compute_btn.clicked.connect(self.run_comparison)
        self.compute_btn = compute_btn
        select_layout.addWidget(compute_btn)
        
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        # 对比结果表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['算法', '平均时间(ms)', '最小(ms)', '最大(ms)', '平均访问节点', '平均迭代'])
        layout.addWidget(self.table)
        
        # 统计信息
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        layout.addWidget(QLabel("详细统计:"))
        layout.addWidget(self.stats_text)
        
        self.setLayout(layout)
        
        # 初始化路由器列表
        self.update_router_list()
    
    def update_router_list(self):
        """更新路由器列表"""
        self.router_combo.clear()
        for router_id in sorted(self.simulator.routers.keys()):
            router = self.simulator.routers[router_id]
            self.router_combo.addItem(f"{router.router_name}", router_id)
    
    def run_comparison(self):
        """执行算法对比"""
        router_id = self.router_combo.currentData()
        if not router_id:
            return
        
        router = self.simulator.routers.get(router_id)
        if not router:
            return

        if self._worker_thread and self._worker_thread.is_alive():
            QMessageBox.information(self, "提示", "已有对比任务在运行，请稍候。")
            return

        runs = self.runs_spin.value()
        self.compute_btn.setEnabled(False)
        self.compute_btn.setText("计算中...")
        self.stats_text.setText("正在后台执行算法对比，请稍候...")

        self._worker = BenchmarkWorker(router.path_calculator, runs)
        self._worker.finished.connect(self._on_benchmark_finished)
        self._worker.failed.connect(self._on_benchmark_failed)

        self._worker_thread = threading.Thread(target=self._worker.run, daemon=True)
        self._worker_thread.start()

    def _on_benchmark_finished(self, results: dict, runs: int):
        """后台计算完成后更新界面。"""
        self.compute_btn.setEnabled(True)
        self.compute_btn.setText("执行对比计算")

        ordered_keys = [
            'dijkstra',
            'new_algo',
            'duan',
            'bellman_ford',
            'spfa',
            'prim_mst',
            'floyd_warshall',
            'astar',
        ]
        algo_keys = [k for k in ordered_keys if k in results] + [
            k for k in results.keys() if k not in ordered_keys
        ]

        self.table.setRowCount(len(algo_keys))

        def format_time_ms(value: float) -> str:
            if value < 0.001:
                return "<0.001"
            return f"{value:.6f}"

        row = 0
        for algo_name in algo_keys:
            stats = results.get(algo_name, {})
            algo_display = self.algorithm_display_map.get(
                algo_name,
                stats.get('algorithm_name', algo_name)
            )
            avg_time = stats.get('avg_time_ms', 0)
            min_time = stats.get('min_time_ms', 0)
            max_time = stats.get('max_time_ms', 0)
            nodes = stats.get('avg_visited_nodes', 0)
            iters = stats.get('avg_iterations', 0)

            self.table.setItem(row, 0, QTableWidgetItem(algo_display))
            self.table.setItem(row, 1, QTableWidgetItem(format_time_ms(avg_time)))
            self.table.setItem(row, 2, QTableWidgetItem(format_time_ms(min_time)))
            self.table.setItem(row, 3, QTableWidgetItem(format_time_ms(max_time)))
            self.table.setItem(row, 4, QTableWidgetItem(f"{nodes:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{iters:.2f}"))
            row += 1

        stats_text = f"算法对比统计（每种算法运行 {runs} 轮）:\n"
        stats_text += "━" * 50 + "\n"

        for algo_name in algo_keys:
            stats = results.get(algo_name, {})
            algo_display = self.algorithm_display_map.get(
                algo_name,
                stats.get('algorithm_name', algo_name)
            )
            algo_display = f"【{algo_display}】"
            stats_text += f"\n{algo_display}\n"
            stats_text += f"  平均耗时: {format_time_ms(stats.get('avg_time_ms', 0))}ms\n"
            stats_text += f"  最小耗时: {format_time_ms(stats.get('min_time_ms', 0))}ms\n"
            stats_text += f"  最大耗时: {format_time_ms(stats.get('max_time_ms', 0))}ms\n"
            stats_text += f"  平均访问节点: {stats.get('avg_visited_nodes', 0):.2f}\n"
            stats_text += f"  平均迭代次数: {stats.get('avg_iterations', 0):.2f}\n"
            if 'avg_relaxation_count' in stats:
                stats_text += f"  平均松弛操作: {stats.get('avg_relaxation_count', 0):.2f}\n"

        self.stats_text.setText(stats_text)
        QMessageBox.information(self, "成功", "算法对比计算完成！")

    def _on_benchmark_failed(self, error_message: str):
        """后台计算失败。"""
        self.compute_btn.setEnabled(True)
        self.compute_btn.setText("执行对比计算")
        QMessageBox.critical(self, "错误", f"计算过程中出现错误: {error_message}")


class SimulationControlWidget(QWidget):
    """仿真控制窗口"""
    
    def __init__(self, simulator, main_window=None):
        super().__init__()
        self.simulator = simulator
        self.main_window = main_window
        self._switch_worker = None
        self._switch_thread = None
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 演示拓扑选择
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("演示拓扑:"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("小型拓扑（8节点）", "config/topology_small_demo.json")
        self.profile_combo.addItem("中型拓扑（20节点）", "config/topology_medium_demo.json")
        self.profile_combo.addItem("大型拓扑（50节点）", "config/benchmark_topology_50.json")
        profile_layout.addWidget(self.profile_combo)

        load_profile_btn = QPushButton("加载并演示")
        load_profile_btn.clicked.connect(self.load_topology_profile)
        self.load_profile_btn = load_profile_btn
        profile_layout.addWidget(load_profile_btn)
        profile_layout.addStretch()
        layout.addLayout(profile_layout)
        
        # 链路故障模拟
        failure_layout = QHBoxLayout()
        failure_layout.addWidget(QLabel("模拟链路故障:"))
        
        failure_layout.addWidget(QLabel("路由器1:"))
        self.fail_router1 = QSpinBox()
        self.fail_router1.setMinimum(1)
        self.fail_router1.setMaximum(255)
        failure_layout.addWidget(self.fail_router1)
        
        failure_layout.addWidget(QLabel("路由器2:"))
        self.fail_router2 = QSpinBox()
        self.fail_router2.setMinimum(1)
        self.fail_router2.setMaximum(255)
        failure_layout.addWidget(self.fail_router2)
        
        fail_btn = QPushButton("创建故障")
        fail_btn.clicked.connect(self.create_link_failure)
        failure_layout.addWidget(fail_btn)
        
        failure_layout.addStretch()
        layout.addLayout(failure_layout)
        
        # 链路恢复模拟
        recovery_layout = QHBoxLayout()
        recovery_layout.addWidget(QLabel("模拟链路恢复:"))
        
        recovery_layout.addWidget(QLabel("路由器1:"))
        self.recover_router1 = QSpinBox()
        self.recover_router1.setMinimum(1)
        self.recover_router1.setMaximum(255)
        recovery_layout.addWidget(self.recover_router1)
        
        recovery_layout.addWidget(QLabel("路由器2:"))
        self.recover_router2 = QSpinBox()
        self.recover_router2.setMinimum(1)
        self.recover_router2.setMaximum(255)
        recovery_layout.addWidget(self.recover_router2)
        
        recovery_layout.addWidget(QLabel("成本:"))
        self.cost_spinbox = QSpinBox()
        self.cost_spinbox.setValue(1)
        self.cost_spinbox.setMinimum(1)
        recovery_layout.addWidget(self.cost_spinbox)
        
        recover_btn = QPushButton("恢复链路")
        recover_btn.clicked.connect(self.create_link_recovery)
        recovery_layout.addWidget(recover_btn)
        
        recovery_layout.addStretch()
        layout.addLayout(recovery_layout)

        # 动态新增路由器
        add_router_layout = QHBoxLayout()
        add_router_layout.addWidget(QLabel("新增路由器:"))
        add_router_layout.addWidget(QLabel("ID:"))
        self.new_router_id = QSpinBox()
        self.new_router_id.setMinimum(1)
        self.new_router_id.setMaximum(255)
        add_router_layout.addWidget(self.new_router_id)

        add_router_layout.addWidget(QLabel("端口:"))
        self.new_router_port = QSpinBox()
        self.new_router_port.setMinimum(10000)
        self.new_router_port.setMaximum(65535)
        self.new_router_port.setValue(22000)
        add_router_layout.addWidget(self.new_router_port)

        add_router_btn = QPushButton("添加路由器")
        add_router_btn.clicked.connect(self.create_router)
        add_router_layout.addWidget(add_router_btn)
        add_router_layout.addStretch()
        layout.addLayout(add_router_layout)

        # 动态新增链路
        add_link_layout = QHBoxLayout()
        add_link_layout.addWidget(QLabel("新增链路:"))
        add_link_layout.addWidget(QLabel("路由器1:"))
        self.add_link_r1 = QSpinBox()
        self.add_link_r1.setMinimum(1)
        self.add_link_r1.setMaximum(255)
        add_link_layout.addWidget(self.add_link_r1)

        add_link_layout.addWidget(QLabel("路由器2:"))
        self.add_link_r2 = QSpinBox()
        self.add_link_r2.setMinimum(1)
        self.add_link_r2.setMaximum(255)
        add_link_layout.addWidget(self.add_link_r2)

        add_link_layout.addWidget(QLabel("成本:"))
        self.add_link_cost = QSpinBox()
        self.add_link_cost.setMinimum(1)
        self.add_link_cost.setMaximum(999)
        self.add_link_cost.setValue(5)
        add_link_layout.addWidget(self.add_link_cost)

        add_link_btn = QPushButton("添加链路")
        add_link_btn.clicked.connect(self.create_link)
        add_link_layout.addWidget(add_link_btn)
        add_link_layout.addStretch()
        layout.addLayout(add_link_layout)
        
        # 统计信息
        layout.addWidget(QLabel("仿真统计:"))
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        layout.addWidget(self.stats_text)
        
        # 定时更新统计
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_statistics)
        self.timer.start(2000)
        
        self.setLayout(layout)
        
        # 初始化显示
        self.update_statistics()
    
    def create_link_failure(self):
        """创建链路故障"""
        r1 = self.fail_router1.value()
        r2 = self.fail_router2.value()
        
        if r1 == r2:
            QMessageBox.warning(self, "警告", "两个路由器不能相同！")
            return
        
        self.simulator.simulate_link_failure(r1, r2)
        QMessageBox.information(self, "成功", f"已模拟链路 {r1}<->{r2} 故障")
    
    def create_link_recovery(self):
        """创建链路恢复"""
        r1 = self.recover_router1.value()
        r2 = self.recover_router2.value()
        cost = self.cost_spinbox.value()
        
        if r1 == r2:
            QMessageBox.warning(self, "警告", "两个路由器不能相同！")
            return
        
        self.simulator.simulate_link_recovery(r1, r2, cost)
        QMessageBox.information(self, "成功", f"已恢复链路 {r1}<->{r2}，成本={cost}")

    def create_router(self):
        """动态新增路由器"""
        router_id = self.new_router_id.value()
        port = self.new_router_port.value()
        ok = self.simulator.add_router_dynamic(router_id, port, f"Router{router_id}")
        if ok:
            QMessageBox.information(self, "成功", f"已添加路由器 Router{router_id}，端口={port}")
        else:
            QMessageBox.warning(self, "失败", "添加路由器失败，请检查ID/端口是否冲突")

    def create_link(self):
        """动态新增链路"""
        r1 = self.add_link_r1.value()
        r2 = self.add_link_r2.value()
        cost = self.add_link_cost.value()
        if r1 == r2:
            QMessageBox.warning(self, "警告", "两个路由器不能相同！")
            return
        ok = self.simulator.add_link_dynamic(r1, r2, cost)
        if ok:
            QMessageBox.information(self, "成功", f"已添加链路 {r1}<->{r2}，成本={cost}")
            if self.main_window:
                self.main_window.refresh_all_views()
        else:
            QMessageBox.warning(self, "失败", "添加链路失败，请先确认两个路由器已存在")

    def load_topology_profile(self):
        """加载小/中/大演示拓扑。"""
        if self._switch_thread and self._switch_thread.is_alive():
            QMessageBox.information(self, "提示", "拓扑切换正在进行，请稍候。")
            return

        config_file = self.profile_combo.currentData()
        profile_text = self.profile_combo.currentText()
        self.load_profile_btn.setEnabled(False)
        self.load_profile_btn.setText("切换中...")

        self._switch_worker = TopologySwitchWorker(self.simulator, config_file, profile_text)
        self._switch_worker.finished.connect(self._on_topology_switch_finished)

        self._switch_thread = threading.Thread(target=self._switch_worker.run, daemon=True)
        self._switch_thread.start()

    def _on_topology_switch_finished(self, ok: bool, profile_text: str, config_file: str):
        """拓扑切换完成回调。"""
        self.load_profile_btn.setEnabled(True)
        self.load_profile_btn.setText("加载并演示")

        if ok:
            if self.main_window:
                self.main_window.refresh_all_views()
            QMessageBox.information(self, "成功", f"已加载演示拓扑: {profile_text}")
        else:
            QMessageBox.warning(self, "失败", f"加载拓扑失败: {config_file}\n请检查端口占用或配置文件")
    
    def update_statistics(self):
        """更新统计信息"""
        stats = "系统统计信息:\n"
        stats += "━" * 60 + "\n\n"
        
        total_routers = len(self.simulator.routers)
        stats += f"总路由器数: {total_routers}\n\n"

        # 大拓扑下优先显示汇总，避免频繁渲染过长文本导致UI卡顿
        if total_routers >= 40:
            total_neighbors = 0
            total_active_neighbors = 0
            total_known_nodes = 0
            total_routes = 0

            for _, router in sorted(self.simulator.routers.items()):
                neigh_count = len(router._neighbors)
                active_count = sum(1 for n in router._neighbors.values() if n['state'] == 'up')
                total_neighbors += neigh_count
                total_active_neighbors += active_count
                total_known_nodes += len(router.topology.get_all_routers())
                total_routes += len(router.routing_table.get_all_routes())

            avg_known = (total_known_nodes / total_routers) if total_routers else 0
            avg_routes = (total_routes / total_routers) if total_routers else 0

            stats += "【大规模拓扑汇总】\n"
            stats += f"  邻接总数: {total_neighbors}\n"
            stats += f"  活跃邻接总数: {total_active_neighbors}\n"
            stats += f"  平均已知节点数: {avg_known:.1f}\n"
            stats += f"  平均路由表条目: {avg_routes:.1f}\n\n"

            stats += "【前10个路由器明细】\n"
            for router_id, router in sorted(self.simulator.routers.items())[:10]:
                active_neighbors = sum(1 for n in router._neighbors.values() if n['state'] == 'up')
                stats += f"  Router{router_id}: 邻接={len(router._neighbors)}, 活跃={active_neighbors}, "
                stats += f"已知节点={len(router.topology.get_all_routers())}, 路由={len(router.routing_table.get_all_routes())}\n"

            stats += "\n提示: 当前为大规模模式，已自动简化统计显示以提升流畅度。\n"
            self.stats_text.setText(stats)
            return
        
        for router_id, router in sorted(self.simulator.routers.items()):
            stats += f"【路由器 {router_id}】\n"
            stats += f"  名称: {router.router_name}\n"
            stats += f"  邻接路由器数: {len(router._neighbors)}\n"
            
            active_neighbors = sum(1 for n in router._neighbors.values() if n['state'] == 'up')
            stats += f"  活跃邻接: {active_neighbors}/{len(router._neighbors)}\n"
            stats += f"  已知节点数: {len(router.topology.get_all_routers())}\n"
            stats += f"  路由表条目: {len(router.routing_table.get_all_routes())}\n\n"
        
        self.stats_text.setText(stats)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self.setWindowTitle("链路状态路由协议分布式仿真系统")
        self.setGeometry(100, 100, 1400, 900)
        
        # 应用样式表
        apply_stylesheet(self)
        
        # 初始化UI
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 创建标签页
        tabs = QTabWidget()

        # 教学演示标签页（默认第一个）
        self.teaching_widget = TeachingDemoWidget(self.simulator)
        tabs.addTab(self.teaching_widget, "📖 教学演示")

        # 拓扑显示标签页
        self.topology_widget = NetworkTopologyWidget(self.simulator)
        tabs.addTab(self.topology_widget, "🔍 网络拓扑")

        # 算法动画标签页
        self.animation_widget = AlgorithmAnimationWidget(self.simulator)
        tabs.addTab(self.animation_widget, "🎬 算法动画")

        # 路由表标签页
        self.routing_table_widget = RoutingTableWidget(self.simulator)
        tabs.addTab(self.routing_table_widget, "📋 路由表")

        # 算法对比标签页
        self.algorithm_widget = AlgorithmComparisonWidget(self.simulator)
        tabs.addTab(self.algorithm_widget, "📊 算法对比")

        # 仿真控制标签页
        self.control_widget = SimulationControlWidget(self.simulator, self)
        tabs.addTab(self.control_widget, "⚙️ 仿真控制")

        # LSA 洪泛监控标签页
        self.lsa_monitor_widget = LSAMonitorWidget(self.simulator)
        tabs.addTab(self.lsa_monitor_widget, "📡 LSA洪泛")

        # 邻居状态机标签页
        self.neighbor_monitor_widget = NeighborMonitorWidget(self.simulator)
        tabs.addTab(self.neighbor_monitor_widget, "💓 邻居状态")

        # 设置中心窗口
        self.setCentralWidget(tabs)
        
        # 创建状态栏
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("系统就绪，仿真运行中...")
        
        # 定时更新
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)
    
    def update_status(self):
        """更新状态栏"""
        running_routers = sum(1 for r in self.simulator.routers.values() if r._running)
        node_count = len(self.simulator.routers)
        active_links = sum(
            sum(1 for n in r._neighbors.values() if n['state'] == 'up')
            for r in self.simulator.routers.values()
        )

        if node_count == 8:
            topology_label = "8节点"
        elif node_count == 20:
            topology_label = "20节点"
        elif node_count == 50:
            topology_label = "50节点"
        else:
            topology_label = f"自定义({node_count}节点)"
        
        self.status.showMessage(
            f"当前已加载拓扑: {topology_label} | "
            f"已启动路由器: {running_routers}/{len(self.simulator.routers)} | "
            f"活跃链路: {active_links} | "
            f"系统运行中..."
        )
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        reply = QMessageBox.question(
            self, '确认关闭',
            '是否确认关闭仿真系统？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.simulator.stop_simulation()
            event.accept()
        else:
            event.ignore()

    def refresh_all_views(self):
        """切换拓扑后刷新全部视图。"""
        try:
            self.routing_table_widget.update_router_list()
            self.routing_table_widget.refresh_tables()
        except Exception:
            pass

        try:
            self.algorithm_widget.update_router_list()
        except Exception:
            pass

        try:
            self.topology_widget.refresh_topology()
        except Exception:
            pass

        try:
            self.control_widget.update_statistics()
        except Exception:
            pass

        try:
            self.animation_widget.refresh_data()
        except Exception:
            pass

        try:
            self.lsa_monitor_widget.refresh_data()
        except Exception:
            pass

        try:
            self.neighbor_monitor_widget.refresh_data()
        except Exception:
            pass
