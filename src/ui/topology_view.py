"""
网络拓扑可视化组件 — 为教学场景优化
清晰的节点状态、边权标签、视角切换
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QCheckBox, QFrame,
)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib as mpl
import networkx as nx

# 中文字体支持
mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
mpl.rcParams['axes.unicode_minus'] = False

# 教学友好的配色
COLOR_SELF = '#E74C3C'
COLOR_SYNCED = '#2ECC71'
COLOR_UNSYNCED = '#BDC3C7'
COLOR_GLOBAL = '#5DADE2'
COLOR_BG = '#FAFBFC'


class NetworkTopologyWidget(QWidget):
    """网络拓扑可视化 — 支持视角切换、同步状态着色"""

    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self._cached_pos = None
        self._cached_signature = None
        self._selected_perspective = None  # None = 全局视图
        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_topology)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- 控制栏 ----
        ctrl_bar = QHBoxLayout()

        ctrl_bar.addWidget(QLabel("视角:"))

        self.perspective_combo = QComboBox()
        self.perspective_combo.addItem("全局视图", None)
        self.perspective_combo.currentIndexChanged.connect(self._on_perspective_changed)
        ctrl_bar.addWidget(self.perspective_combo)

        ctrl_bar.addSpacing(12)

        self.auto_refresh_cb = QCheckBox("自动刷新")
        self.auto_refresh_cb.setToolTip("开启后每2秒自动刷新拓扑图")
        self.auto_refresh_cb.toggled.connect(self._toggle_auto_refresh)
        ctrl_bar.addWidget(self.auto_refresh_cb)

        refresh_btn = QPushButton("刷新拓扑")
        refresh_btn.clicked.connect(self.refresh_topology)
        ctrl_bar.addWidget(refresh_btn)

        layout_btn = QPushButton("重置布局")
        layout_btn.setToolTip("重新计算节点布局")
        layout_btn.clicked.connect(self.adjust_layout)
        ctrl_bar.addWidget(layout_btn)

        ctrl_bar.addStretch()

        # 图例面板
        legend_frame = QFrame()
        legend_frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #e0e4e8; "
            "border-radius: 6px; padding: 4px 8px; }"
        )
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(10)
        legend_layout.setContentsMargins(6, 2, 6, 2)

        for color, label in [
            (COLOR_SELF, "当前视角"),
            (COLOR_SYNCED, "已同步"),
            (COLOR_UNSYNCED, "未同步"),
            (COLOR_GLOBAL, "全局节点"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
            legend_layout.addWidget(dot)
            text = QLabel(label)
            text.setStyleSheet("color: #555; font-size: 10px;")
            legend_layout.addWidget(text)

        legend_frame.setLayout(legend_layout)
        ctrl_bar.addWidget(legend_frame)

        layout.addLayout(ctrl_bar)

        # ---- Matplotlib 画布 ----
        self.figure = Figure(figsize=(10, 7.5), dpi=100, facecolor=COLOR_BG)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("border: 1px solid #e0e4e8; border-radius: 8px;")
        layout.addWidget(self.canvas)

        # ---- 底部信息栏 ----
        self.info_label = QLabel("准备就绪 — 点击「刷新拓扑」更新视图")
        self.info_label.setStyleSheet(
            "color: #7f8c8d; font-size: 11px; padding: 4px 10px; "
            "background: white; border-radius: 4px;"
        )
        layout.addWidget(self.info_label)

        self.setLayout(layout)
        self._update_perspective_list()
        self.refresh_topology()

    # ------------------------------------------------------------------
    def _update_perspective_list(self):
        self.perspective_combo.blockSignals(True)
        current = self.perspective_combo.currentData()
        while self.perspective_combo.count() > 1:
            self.perspective_combo.removeItem(1)
        for rid in sorted(self.simulator.routers.keys()):
            r = self.simulator.routers[rid]
            self.perspective_combo.addItem(f"Router {rid}", rid)
        idx = self.perspective_combo.findData(current)
        if idx >= 0:
            self.perspective_combo.setCurrentIndex(idx)
        self.perspective_combo.blockSignals(False)

    def _on_perspective_changed(self):
        self._selected_perspective = self.perspective_combo.currentData()
        self._cached_pos = None
        self._cached_signature = None
        self.refresh_topology()

    def _toggle_auto_refresh(self, checked: bool):
        if checked:
            self.timer.start(2000)
            self.info_label.setText("自动刷新模式：每2秒更新")
        else:
            self.timer.stop()
            self.info_label.setText("手动刷新模式：点击「刷新拓扑」更新")

    # ------------------------------------------------------------------
    def refresh_topology(self):
        try:
            self._update_perspective_list()
            if self._selected_perspective is not None:
                router = self.simulator.routers.get(self._selected_perspective)
                topology = router.get_topology_data() if router else self.simulator.get_topology()
            else:
                topology = self.simulator.get_topology()
            self.draw_topology(topology)
        except Exception as e:
            self.info_label.setText(f"绘图错误: {e}")

    def draw_topology(self, topology_data):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(COLOR_BG)

        try:
            G = nx.Graph()
            nodes = topology_data.get('nodes', [])
            edges = topology_data.get('edges', [])

            for node in nodes:
                G.add_node(node['id'])
            for edge in edges:
                G.add_edge(edge['source'], edge['target'], weight=edge.get('cost', 1))

            if len(G.nodes) == 0:
                ax.text(0.5, 0.5, '暂无拓扑数据\n请等待路由器启动并同步...',
                       ha='center', va='center', fontsize=14, color='#aaa',
                       transform=ax.transAxes)
                self.canvas.draw()
                return

            node_count = len(G.nodes)
            edge_count = len(G.edges)
            is_large = node_count >= 40 or edge_count >= 120

            # ---- 布局 ----
            current_sig = (
                tuple(sorted(G.nodes)),
                tuple(sorted((min(u, v), max(u, v), d.get('weight', 1))
                            for u, v, d in G.edges(data=True)))
            )

            if self._cached_pos is None or self._cached_signature != current_sig:
                if is_large:
                    self._cached_pos = nx.kamada_kawai_layout(G)
                elif node_count <= 12:
                    self._cached_pos = nx.spring_layout(G, k=2.5, iterations=50, seed=42)
                else:
                    self._cached_pos = nx.spring_layout(G, k=1.8, iterations=30, seed=42)
                self._cached_signature = current_sig

            pos = self._cached_pos

            # ---- 确定节点颜色 ----
            perspective_id = self._selected_perspective
            node_colors = []
            node_borders = []
            node_sizes = []

            for n in G.nodes:
                if perspective_id is not None and n == perspective_id:
                    node_colors.append(COLOR_SELF)
                    node_borders.append('#C0392B')
                    node_sizes.append(1600)
                elif perspective_id is not None:
                    router = self.simulator.routers.get(perspective_id)
                    if router and n in router.topology.get_all_routers():
                        node_colors.append(COLOR_SYNCED)
                        node_borders.append('#27AE60')
                    else:
                        node_colors.append(COLOR_UNSYNCED)
                        node_borders.append('#999')
                    node_sizes.append(1200)
                else:
                    node_colors.append(COLOR_GLOBAL)
                    node_borders.append('#2E86C1')
                    node_sizes.append(1200)

            if is_large:
                node_sizes = [max(250, int(s * 0.4)) for s in node_sizes]

            # ---- 绘制边 ----
            nx.draw_networkx_edges(
                G, pos, ax=ax,
                width=1.5 if not is_large else 0.6,
                edge_color='#c0c8d0',
                alpha=0.65,
                style='solid',
            )

            # ---- 绘制节点 ----
            nx.draw_networkx_nodes(
                G, pos, ax=ax,
                node_color=node_colors,
                node_size=node_sizes,
                alpha=0.92,
                edgecolors=node_borders,
                linewidths=2,
            )

            # ---- 节点标签 ----
            labels = {n: f"R{n}" for n in G.nodes}
            nx.draw_networkx_labels(
                G, pos, ax=ax,
                labels=labels,
                font_size=7 if is_large else 10,
                font_weight='bold',
                font_color='white',
            )

            # ---- 边权标签 ----
            if not is_large:
                edge_labels = {(u, v): d['weight'] for u, v, d in G.edges(data=True)}
                nx.draw_networkx_edge_labels(
                    G, pos, ax=ax,
                    edge_labels=edge_labels,
                    font_size=7,
                    font_weight='bold',
                    font_color='#555',
                    bbox=dict(
                        boxstyle='round,pad=0.2',
                        facecolor='white',
                        edgecolor='#ddd',
                        alpha=0.85,
                    ),
                )

            # ---- 标题与信息 ----
            if perspective_id is not None:
                title = f"网络拓扑 — Router {perspective_id} 视角"
            else:
                title = "网络拓扑 — 全局视图"
            ax.set_title(title, fontsize=13, fontweight='bold', color='#2C3E50', pad=10)
            ax.axis('off')
            ax.margins(0.08)

            # ---- 底部信息 ----
            num_routers = len(self.simulator.routers)
            synced_count = 0
            if perspective_id is not None:
                router = self.simulator.routers.get(perspective_id)
                if router:
                    synced_count = len(router.topology.get_all_routers())
                self.info_label.setText(
                    f"Router {perspective_id} 视角 | "
                    f"已知节点: {synced_count}/{node_count} | "
                    f"链路: {edge_count} 条 | "
                    f"路由器总数: {num_routers}"
                )
            else:
                self.info_label.setText(
                    f"全局视图 | {num_routers} 个路由器 | "
                    f"{node_count} 个节点 | {edge_count} 条链路"
                )

            self.canvas.draw()

        except Exception as e:
            import traceback
            traceback.print_exc()
            ax.text(0.5, 0.5, f'绘制失败:\n{str(e)}',
                   ha='center', va='center', color='#E74C3C', fontsize=12,
                   transform=ax.transAxes)
            self.canvas.draw()

    def adjust_layout(self):
        self._cached_signature = None
        self._cached_pos = None
        self.refresh_topology()
