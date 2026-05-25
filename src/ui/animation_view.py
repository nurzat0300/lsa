"""
算法步骤动画可视化组件
使用自定义QPainter绘制，展示Dijkstra算法的逐步执行过程
"""
import math
from typing import Dict, List, Tuple, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QTextEdit, QComboBox, QSpinBox, QSplitter, QFrame,
    QSizePolicy, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, QLineF, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QPainterPath, QRadialGradient, QLinearGradient, QPolygonF,
)

from ..algorithms.stepped_dijkstra import SteppedDijkstra, DijkstraStepState


# 颜色常量
COLOR_SOURCE = QColor("#E74C3C")       # 源节点 - 红色
COLOR_CURRENT = QColor("#F39C12")      # 当前处理节点 - 橙色
COLOR_VISITED = QColor("#27AE60")      # 已访问节点 - 绿色
COLOR_FRONTIER = QColor("#3498DB")     # 边界节点 - 蓝色
COLOR_UNVISITED = QColor("#BDC3C7")    # 未访问节点 - 灰色
COLOR_EDGE_DEFAULT = QColor("#95A5A6") # 默认边 - 灰色
COLOR_EDGE_RELAXED = QColor("#E74C3C") # 松弛边 - 红色
COLOR_EDGE_PATH = QColor("#2ECC71")    # 最短路径边 - 绿色
COLOR_BG = QColor("#FAFAFA")
COLOR_TEXT = QColor("#2C3E50")
COLOR_DISTANCE_BG = QColor("#FFFFFF")
COLOR_DISTANCE_BORDER = QColor("#DDDDDD")


class GraphPaintWidget(QWidget):
    """绘制算法状态图的自定义组件"""

    node_clicked = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(500, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self._graph: Dict[int, List[Tuple[int, int]]] = {}
        self._state: Optional[DijkstraStepState] = None
        self._node_positions: Dict[int, QPointF] = {}
        self._source_node: int = 0
        self._highlight_path: List[int] = []
        self._hovered_node: Optional[int] = None

        self.NODE_RADIUS = 28
        self._cached_positions = False

    def set_graph(self, graph: Dict[int, List[Tuple[int, int]]], source: int):
        self._graph = graph
        self._source_node = source
        self._cached_positions = False
        self._highlight_path = []
        self.update()

    def set_state(self, state: DijkstraStepState):
        self._state = state
        self.update()

    def set_highlight_path(self, path: List[int]):
        self._highlight_path = path
        self.update()

    def _layout_nodes(self):
        if not self._graph:
            return
        nodes = list(self._graph.keys())
        n = len(nodes)
        if n == 0:
            return

        w = max(self.width() - 100, 200)
        h = max(self.height() - 100, 200)
        cx = w / 2 + 50
        cy = h / 2 + 50
        rx = w / 2 - 60
        ry = h / 2 - 60

        if n <= 8:
            # 小图：圆形布局，保证足够的节点间距
            for i, node in enumerate(nodes):
                angle = 2 * math.pi * i / n - math.pi / 2
                self._node_positions[node] = QPointF(
                    cx + rx * math.cos(angle),
                    cy + ry * math.sin(angle),
                )
        elif n <= 20:
            # 中型图：双层圆环，内圈+外圈
            half = n // 2
            inner_rx = rx * 0.55
            inner_ry = ry * 0.55
            for i, node in enumerate(nodes):
                if i < half:
                    # 外圈
                    angle = 2 * math.pi * i / half - math.pi / 2
                    self._node_positions[node] = QPointF(
                        cx + rx * math.cos(angle),
                        cy + ry * math.sin(angle),
                    )
                else:
                    # 内圈
                    angle = 2 * math.pi * (i - half) / (n - half) - math.pi / 2 + math.pi / max(n - half, 1)
                    self._node_positions[node] = QPointF(
                        cx + inner_rx * math.cos(angle),
                        cy + inner_ry * math.sin(angle),
                    )
        else:
            # 大图：网格布局，增大间距
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            cell_w = min((w - 100) / cols, 140)
            cell_h = min((h - 100) / rows, 120)
            start_x = cx - (cols - 1) * cell_w / 2
            start_y = cy - (rows - 1) * cell_h / 2
            for i, node in enumerate(nodes):
                col = i % cols
                row = i // cols
                self._node_positions[node] = QPointF(
                    start_x + col * cell_w,
                    start_y + row * cell_h,
                )

        self._cached_positions = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), COLOR_BG)

        if not self._graph:
            painter.setPen(QColor("#999"))
            painter.setFont(QFont("Microsoft YaHei", 14))
            painter.drawText(self.rect(), Qt.AlignCenter, "请先选择源路由器并执行算法")
            return

        if not self._cached_positions:
            self._layout_nodes()

        # 绘制边
        self._draw_edges(painter)

        # 绘制节点
        self._draw_nodes(painter)

        # 绘制距离标签
        self._draw_distance_labels(painter)

    def _draw_arrow_head(self, painter, tip: QPointF, angle: float, size: int, color: QColor):
        """在边的终点绘制方向箭头"""
        arrow = QPolygonF([
            tip,
            QPointF(tip.x() - size * math.cos(angle - 0.5),
                    tip.y() - size * math.sin(angle - 0.5)),
            QPointF(tip.x() - size * math.cos(angle + 0.5),
                    tip.y() - size * math.sin(angle + 0.5)),
        ])
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(arrow)

    def _draw_edges(self, painter: QPainter):
        drawn = set()

        # === 第1层: 先画所有默认边 ===
        for u, neighbors in self._graph.items():
            for v, cost in neighbors:
                edge_key = (min(u, v), max(u, v))
                if edge_key in drawn:
                    continue
                drawn.add(edge_key)

                p1 = self._node_positions.get(u)
                p2 = self._node_positions.get(v)
                if p1 is None or p2 is None:
                    continue

                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                length = math.sqrt(dx * dx + dy * dy)
                if length < 1:
                    continue
                nx = dx / length
                ny = dy / length

                r = self.NODE_RADIUS + 2
                start = QPointF(p1.x() + nx * r, p1.y() + ny * r)
                end = QPointF(p2.x() - nx * r, p2.y() - ny * r)

                # 画默认边（灰色细线）
                painter.setPen(QPen(COLOR_EDGE_DEFAULT, 1.5, Qt.SolidLine))
                painter.drawLine(start, end)

        # === 第2层: 画松弛边（橘色虚线+箭头） ===
        if self._state and self._state.relaxed_edges:
            for r_u, r_v, _ in self._state.relaxed_edges:
                p1 = self._node_positions.get(r_u)
                p2 = self._node_positions.get(r_v)
                if p1 is None or p2 is None:
                    continue

                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                length = math.sqrt(dx * dx + dy * dy)
                if length < 1:
                    continue
                nx = dx / length
                ny = dy / length
                r = self.NODE_RADIUS + 2

                # 浅色光晕增加可读性
                glow_pen = QPen(QColor("#F5B7B1"), 7, Qt.SolidLine)
                glow_pen.setCapStyle(Qt.RoundCap)
                painter.setPen(glow_pen)
                painter.drawLine(
                    QPointF(p1.x() + nx * r, p1.y() + ny * r),
                    QPointF(p2.x() - nx * r, p2.y() - ny * r),
                )

                # 主线条
                pen = QPen(COLOR_EDGE_RELAXED, 3, Qt.DashLine)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    QPointF(p1.x() + nx * r, p1.y() + ny * r),
                    QPointF(p2.x() - nx * r, p2.y() - ny * r),
                )

                # 方向箭头（从r_u指向r_v）
                tip = QPointF(p2.x() - nx * (r + 6), p2.y() - ny * (r + 6))
                arrow_angle = math.atan2(dy, dx)
                self._draw_arrow_head(painter, tip, arrow_angle, 10, COLOR_EDGE_RELAXED)

        # === 第3层: 画高亮路径（绿色粗线+发光+箭头，画在最上面） ===
        if self._highlight_path:
            path_edges = []
            for i in range(len(self._highlight_path) - 1):
                u = self._highlight_path[i]
                v = self._highlight_path[i + 1]
                p1 = self._node_positions.get(u)
                p2 = self._node_positions.get(v)
                if p1 is None or p2 is None:
                    continue
                path_edges.append((u, v, p1, p2))

            for u, v, p1, p2 in path_edges:
                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                length = math.sqrt(dx * dx + dy * dy)
                if length < 1:
                    continue
                nx = dx / length
                ny = dy / length
                r = self.NODE_RADIUS + 2

                start = QPointF(p1.x() + nx * r, p1.y() + ny * r)
                end = QPointF(p2.x() - nx * r, p2.y() - ny * r)

                # 外层光晕
                glow = QPen(QColor("#8EF5B5"), 9, Qt.SolidLine)
                glow.setCapStyle(Qt.RoundCap)
                painter.setPen(glow)
                painter.drawLine(start, end)

                # 中层
                mid_glow = QPen(QColor("#58D68D"), 6, Qt.SolidLine)
                mid_glow.setCapStyle(Qt.RoundCap)
                painter.setPen(mid_glow)
                painter.drawLine(start, end)

                # 内核
                core = QPen(COLOR_EDGE_PATH, 3.5, Qt.SolidLine)
                core.setCapStyle(Qt.RoundCap)
                painter.setPen(core)
                painter.drawLine(start, end)

                # 方向箭头
                tip = QPointF(p2.x() - nx * (r + 8), p2.y() - ny * (r + 8))
                arrow_angle = math.atan2(dy, dx)
                self._draw_arrow_head(painter, tip, arrow_angle, 12, COLOR_EDGE_PATH)

        # === 第4层: 边权标签（白色气泡背景，去重，只画一次） ===
        drawn_labels = set()
        for u, neighbors in self._graph.items():
            for v, cost in neighbors:
                edge_key = (min(u, v), max(u, v))
                if edge_key in drawn_labels:
                    continue
                drawn_labels.add(edge_key)
                p1 = self._node_positions.get(u)
                p2 = self._node_positions.get(v)
                if p1 is None or p2 is None:
                    continue

                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                length = math.sqrt(dx * dx + dy * dy)
                if length < 1:
                    continue

                mid_x = (p1.x() + p2.x()) / 2
                mid_y = (p1.y() + p2.y()) / 2
                # 偏移到边的侧面
                offset_x = -dy / length * 14
                offset_y = dx / length * 14

                label = str(cost)
                fm = QFontMetrics(QFont("Arial", 9, QFont.Bold))
                tw = fm.horizontalAdvance(label) + 8
                th = fm.height() + 2
                lx = mid_x + offset_x - tw / 2
                ly = mid_y + offset_y - th / 2

                # 白色气泡背景
                painter.setPen(QPen(QColor("#ccc"), 1))
                painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
                painter.drawRoundedRect(QRectF(lx, ly, tw, th), 4, 4)

                # 标签文字
                painter.setPen(QColor("#333"))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(QRectF(lx, ly, tw, th), Qt.AlignCenter, label)

    def _draw_nodes(self, painter: QPainter):
        for node_id in self._graph:
            pos = self._node_positions.get(node_id)
            if pos is None:
                continue

            # 确定节点颜色
            state = self._state
            if node_id == self._source_node and (not state or state.phase == "init"):
                color = COLOR_SOURCE
            elif state:
                if node_id == state.current_node:
                    color = COLOR_CURRENT
                elif node_id in state.visited:
                    color = COLOR_VISITED
                elif node_id in state.frontier:
                    color = COLOR_FRONTIER
                else:
                    color = COLOR_UNVISITED
            else:
                color = COLOR_UNVISITED

            # 高亮路径上的节点 - 更大的光晕
            if node_id in self._highlight_path:
                for ring_size, ring_alpha in [(18, 40), (12, 70), (7, 100)]:
                    glow_color = QColor(COLOR_EDGE_PATH)
                    glow_color.setAlpha(ring_alpha)
                    glow = QRadialGradient(pos, self.NODE_RADIUS + ring_size)
                    glow.setColorAt(0, glow_color)
                    glow.setColorAt(0.5, glow_color)
                    glow.setColorAt(1, QColor(0, 0, 0, 0))
                    painter.setBrush(QBrush(glow))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(pos, self.NODE_RADIUS + ring_size, self.NODE_RADIUS + ring_size)

            # 当前处理节点加一个脉冲外环
            if state and node_id == state.current_node:
                pulse_color = QColor(COLOR_CURRENT)
                pulse_color.setAlpha(60)
                pulse = QRadialGradient(pos, self.NODE_RADIUS + 14)
                pulse.setColorAt(0, pulse_color)
                pulse.setColorAt(1, QColor(0, 0, 0, 0))
                painter.setBrush(QBrush(pulse))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(pos, self.NODE_RADIUS + 14, self.NODE_RADIUS + 14)

            # 节点主体
            border_color = QColor("#2C3E50") if node_id == self._hovered_node else color.darker(130)
            border_width = 3 if node_id == self._hovered_node else 2
            painter.setPen(QPen(border_color, border_width))

            gradient = QRadialGradient(
                pos.x() - self.NODE_RADIUS * 0.3,
                pos.y() - self.NODE_RADIUS * 0.3,
                self.NODE_RADIUS,
            )
            gradient.setColorAt(0, color.lighter(140))
            gradient.setColorAt(0.7, color)
            gradient.setColorAt(1, color.darker(110))
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(pos, self.NODE_RADIUS, self.NODE_RADIUS)

            # 节点标签
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 11 if node_id not in self._highlight_path else 12, QFont.Bold))
            painter.drawText(
                QRectF(pos.x() - self.NODE_RADIUS, pos.y() - self.NODE_RADIUS,
                       self.NODE_RADIUS * 2, self.NODE_RADIUS * 2),
                Qt.AlignCenter, str(node_id),
            )

    def _draw_distance_labels(self, painter: QPainter):
        if not self._state or not self._state.distances:
            return

        for node_id, dist in self._state.distances.items():
            if node_id == self._source_node:
                continue
            pos = self._node_positions.get(node_id)
            if pos is None:
                continue

            dist_str = str(dist) if dist < 99999 else "∞"
            label = f"d={dist_str}"

            fm = QFontMetrics(QFont("Consolas", 9, QFont.Bold))
            tw = fm.horizontalAdvance(label) + 10
            th = fm.height() + 4

            # 标签放在节点下方，避免和节点主体重叠
            label_y_offset = self.NODE_RADIUS + 8
            label_x = pos.x() - tw / 2
            label_y = pos.y() + label_y_offset

            # 颜色随节点状态
            state = self._state
            if node_id in state.visited:
                bg_color = QColor("#D5F5E3")
                text_color = QColor("#1E8449")
            elif node_id in state.frontier:
                bg_color = QColor("#D4E6F1")
                text_color = QColor("#2471A3")
            elif node_id == state.current_node:
                bg_color = QColor("#FDEBD0")
                text_color = QColor("#B9770E")
            else:
                bg_color = QColor("#F2F3F4")
                text_color = QColor("#888")

            painter.setPen(QPen(QColor("#ddd"), 1))
            painter.setBrush(QBrush(bg_color))
            painter.drawRoundedRect(QRectF(label_x, label_y, tw, th), 4, 4)

            painter.setPen(text_color)
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            painter.drawText(QRectF(label_x, label_y, tw, th), Qt.AlignCenter, label)

    def mouseMoveEvent(self, event):
        old = self._hovered_node
        self._hovered_node = self._node_at(event.pos())
        if old != self._hovered_node:
            self.update()

    def mousePressEvent(self, event):
        node = self._node_at(event.pos())
        if node is not None:
            self.node_clicked.emit(node)

    def _node_at(self, pos: QPointF) -> Optional[int]:
        for node_id, npos in self._node_positions.items():
            dx = pos.x() - npos.x()
            dy = pos.y() - npos.y()
            if math.sqrt(dx * dx + dy * dy) <= self.NODE_RADIUS:
                return node_id
        return None


class AlgorithmAnimationWidget(QWidget):
    """算法动画控制面板 - 整合绘图、控制和信息展示"""

    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self._stepper = SteppedDijkstra()
        self._states: List[DijkstraStepState] = []
        self._current_step = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._next_step)
        self._speed_ms = 800
        self._graph: Dict[int, List[Tuple[int, int]]] = {}
        self._source_node: int = 0

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        # ---- 左侧: 图可视化 ----
        left_panel = QVBoxLayout()

        # 顶部选择栏
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("源路由器:"))

        self.source_combo = QComboBox()
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        top_bar.addWidget(self.source_combo)

        top_bar.addSpacing(20)
        top_bar.addWidget(QLabel("目标路由器(可选):"))

        self.target_combo = QComboBox()
        self.target_combo.addItem("(不选择)", -1)
        top_bar.addWidget(self.target_combo)

        self.show_path_btn = QPushButton("高亮最短路径")
        self.show_path_btn.clicked.connect(self._highlight_shortest_path)
        top_bar.addWidget(self.show_path_btn)

        top_bar.addStretch()
        left_panel.addLayout(top_bar)

        # 图绘制区域
        self.graph_widget = GraphPaintWidget()
        self.graph_widget.node_clicked.connect(self._on_node_clicked)
        left_panel.addWidget(self.graph_widget, 1)

        # ---- 右侧: 控制面板 ----
        right_panel = QVBoxLayout()

        # 图例
        legend_frame = QFrame()
        legend_frame.setFrameStyle(QFrame.StyledPanel)
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(4)

        title = QLabel("图例说明")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        legend_layout.addWidget(title)

        legend_items = [
            ("● 源节点", COLOR_SOURCE),
            ("● 当前节点", COLOR_CURRENT),
            ("● 已访问", COLOR_VISITED),
            ("● 边界节点", COLOR_FRONTIER),
            ("● 未访问", COLOR_UNVISITED),
            ("— 松弛边", COLOR_EDGE_RELAXED),
            ("— 最短路径", COLOR_EDGE_PATH),
        ]
        for text, color in legend_items:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color.name()}; font-weight: bold; font-size: 11px;")
            legend_layout.addWidget(lbl)

        legend_frame.setLayout(legend_layout)
        right_panel.addWidget(legend_frame)

        # 步骤控制
        ctrl_frame = QFrame()
        ctrl_frame.setFrameStyle(QFrame.StyledPanel)
        ctrl_layout = QVBoxLayout()

        ctrl_title = QLabel("步骤控制")
        ctrl_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        ctrl_title.setAlignment(Qt.AlignCenter)
        ctrl_layout.addWidget(ctrl_title)

        # 进度
        self.progress_label = QLabel("未开始")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setFont(QFont("Microsoft YaHei", 10))
        ctrl_layout.addWidget(self.progress_label)

        # 按钮行
        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton("⏮ 重置")
        self.reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self.reset_btn)

        self.prev_btn = QPushButton("◀ 上一步")
        self.prev_btn.clicked.connect(self._prev_step)
        btn_row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.clicked.connect(self._toggle_play)
        btn_row.addWidget(self.play_btn)

        self.next_btn = QPushButton("下一步 ▶")
        self.next_btn.clicked.connect(self._next_step)
        btn_row.addWidget(self.next_btn)
        ctrl_layout.addLayout(btn_row)

        # 速度控制
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("速度:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self.speed_slider)
        self.speed_label = QLabel("中速")
        speed_row.addWidget(self.speed_label)
        ctrl_layout.addLayout(speed_row)

        # 步进跳转
        jump_row = QHBoxLayout()
        jump_row.addWidget(QLabel("跳转到步骤:"))
        self.jump_spin = QSpinBox()
        self.jump_spin.setMinimum(0)
        self.jump_spin.setEnabled(False)
        jump_row.addWidget(self.jump_spin)
        self.jump_btn = QPushButton("跳转")
        self.jump_btn.clicked.connect(self._jump_to_step)
        self.jump_btn.setEnabled(False)
        jump_row.addWidget(self.jump_btn)
        ctrl_layout.addLayout(jump_row)

        ctrl_frame.setLayout(ctrl_layout)
        right_panel.addWidget(ctrl_frame)

        # 步骤描述
        desc_frame = QFrame()
        desc_frame.setFrameStyle(QFrame.StyledPanel)
        desc_layout = QVBoxLayout()

        desc_title = QLabel("步骤详情")
        desc_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        desc_title.setAlignment(Qt.AlignCenter)
        desc_layout.addWidget(desc_title)

        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMinimumHeight(120)
        self.desc_text.setFont(QFont("Microsoft YaHei", 10))
        desc_layout.addWidget(self.desc_text)

        # 状态信息
        self.state_table = QTextEdit()
        self.state_table.setReadOnly(True)
        self.state_table.setMaximumHeight(150)
        self.state_table.setFont(QFont("Consolas", 9))
        desc_layout.addWidget(QLabel("节点距离表:"))
        desc_layout.addWidget(self.state_table)

        desc_frame.setLayout(desc_layout)
        right_panel.addWidget(desc_frame, 1)

        # 组装
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.setLayout(layout)
        self._update_source_list()

    def _update_source_list(self):
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        current = self.source_combo.currentData()
        for rid in sorted(self.simulator.routers.keys()):
            router = self.simulator.routers[rid]
            self.source_combo.addItem(f"Router {rid} ({router.router_name})", rid)
        if current and current in self.simulator.routers:
            idx = self.source_combo.findData(current)
            if idx >= 0:
                self.source_combo.setCurrentIndex(idx)
        self.source_combo.blockSignals(False)

    def _update_target_list(self):
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("(不选择)", -1)
        if self._graph:
            for node in sorted(self._graph.keys()):
                if node != self._source_node:
                    self.target_combo.addItem(f"Router {node}", node)
        self.target_combo.blockSignals(False)

    def _on_source_changed(self):
        rid = self.source_combo.currentData()
        if rid is None:
            return
        self._source_node = rid
        self._build_graph()
        self._reset()
        self._update_target_list()

    def _build_graph(self):
        rid = self._source_node
        if rid not in self.simulator.routers:
            return
        router = self.simulator.routers[rid]
        adj_list = {}
        for node in router.topology.get_all_routers():
            adj_list[node] = []
            for neighbor in router.topology.get_neighbors(node):
                cost = router.topology.get_link_cost(node, neighbor)
                if cost != 65535:
                    adj_list[node].append((neighbor, cost))
        if rid not in adj_list:
            adj_list[rid] = []
        self._graph = adj_list
        self._update_target_list()

    def _reset(self):
        self._timer.stop()
        self.play_btn.setText("▶ 播放")
        self._current_step = 0
        self._states = []

        if self._graph and self._source_node in self._graph:
            self._states = self._stepper.calculate_with_steps(
                self._source_node, self._graph
            )
            self.jump_spin.setMaximum(max(0, len(self._states) - 1))
            self.jump_spin.setEnabled(True)
            self.jump_btn.setEnabled(True)
            self.graph_widget.set_graph(self._graph, self._source_node)
            if self._states:
                self.graph_widget.set_state(self._states[0])
                self._display_state(self._states[0])
        else:
            self.graph_widget.set_graph(
                {self._source_node: []}, self._source_node
            )
            self.progress_label.setText("当前拓扑无数据，请先加载拓扑")
            self.desc_text.clear()
            self.state_table.clear()

    def _next_step(self):
        if not self._states:
            return
        if self._current_step < len(self._states) - 1:
            self._current_step += 1
            self.graph_widget.set_state(self._states[self._current_step])
            self._display_state(self._states[self._current_step])

            if self._states[self._current_step].is_complete:
                self._timer.stop()
                self.play_btn.setText("▶ 播放")
                self._show_final_result()

    def _prev_step(self):
        if not self._states or self._current_step <= 0:
            return
        self._timer.stop()
        self.play_btn.setText("▶ 播放")
        self._current_step -= 1
        self.graph_widget.set_state(self._states[self._current_step])
        self._display_state(self._states[self._current_step])

    def _toggle_play(self):
        if not self._states:
            self._on_source_changed()
            if not self._states:
                return

        if self._timer.isActive():
            self._timer.stop()
            self.play_btn.setText("▶ 播放")
        else:
            if self._current_step >= len(self._states) - 1:
                self._current_step = -1  # 从头开始
            self._timer.start(self._speed_ms)
            self.play_btn.setText("⏸ 暂停")

    def _on_speed_changed(self, value):
        speed_names = {1: "非常慢", 3: "慢速", 5: "中速", 7: "快速", 10: "极速"}
        self._speed_ms = int(1500 / value)
        self.speed_label.setText(speed_names.get(value, f"{value}"))
        if self._timer.isActive():
            self._timer.start(self._speed_ms)

    def _jump_to_step(self):
        step = self.jump_spin.value()
        if 0 <= step < len(self._states):
            self._timer.stop()
            self.play_btn.setText("▶ 播放")
            self._current_step = step
            self.graph_widget.set_state(self._states[step])
            self._display_state(self._states[step])

    def _display_state(self, state: DijkstraStepState):
        self.progress_label.setText(
            f"步骤 {state.step_number} / {len(self._states) - 1}"
        )
        self.jump_spin.setValue(state.step_number)

        # 阶段标签
        phase_names = {
            "init": "【初始化】",
            "select": "【选择节点】",
            "relax": "【松弛邻边】",
            "complete": "【完成】",
        }
        phase_label = phase_names.get(state.phase, "")

        self.desc_text.setHtml(
            f"<b style='color:#2C3E50;font-size:13px;'>{phase_label}</b><br><br>"
            f"<span style='font-size:11px;line-height:1.6;'>{state.description}</span>"
        )

        # 距离表
        if state.distances:
            table_html = "<table style='width:100%;border-collapse:collapse;'>"
            table_html += "<tr style='background:#3498DB;color:white;'>"
            table_html += "<th style='padding:4px;'>节点</th>"
            table_html += "<th style='padding:4px;'>距离</th>"
            table_html += "<th style='padding:4px;'>状态</th></tr>"

            for node in sorted(state.distances.keys()):
                dist = state.distances[node]
                dist_str = str(dist) if dist < 99999 else "∞"

                if node in state.visited:
                    row_color = "#D5F5E3"
                    status = "已访问 ✓"
                elif node in state.frontier:
                    row_color = "#D4E6F1"
                    status = "边界"
                else:
                    row_color = "#F2F3F4"
                    status = "未访问"

                if node == state.current_node:
                    row_color = "#FDEBD0"

                table_html += (
                    f"<tr style='background:{row_color};'>"
                    f"<td style='padding:3px;text-align:center;'>{node}</td>"
                    f"<td style='padding:3px;text-align:center;'>{dist_str}</td>"
                    f"<td style='padding:3px;text-align:center;font-size:10px;'>{status}</td>"
                    f"</tr>"
                )
            table_html += "</table>"
            self.state_table.setHtml(table_html)

    def _show_final_result(self):
        if not self._stepper.final_result:
            return
        result_html = "<b>最终结果 - 最短路径树:</b><br><br>"
        result_html += "<table style='width:100%;border-collapse:collapse;'>"
        result_html += "<tr style='background:#27AE60;color:white;'>"
        result_html += "<th style='padding:4px;'>目标</th>"
        result_html += "<th style='padding:4px;'>距离</th>"
        result_html += "<th style='padding:4px;'>路径</th></tr>"

        for dest, (cost, path) in sorted(self._stepper.final_result.items()):
            path_str = " → ".join(map(str, path))
            result_html += (
                f"<tr><td style='padding:3px;text-align:center;'>{dest}</td>"
                f"<td style='padding:3px;text-align:center;'>{cost}</td>"
                f"<td style='padding:3px;text-align:center;font-size:9px;'>{path_str}</td></tr>"
            )
        result_html += "</table>"
        self.state_table.setHtml(result_html)

    def _highlight_shortest_path(self):
        target = self.target_combo.currentData()
        if target is None or target < 0:
            QMessageBox.information(self, "提示", "请先选择目标路由器")
            return
        if not self._stepper.final_result or target not in self._stepper.final_result:
            QMessageBox.information(self, "提示", "请先执行算法到完成状态")
            return

        _, path = self._stepper.final_result[target]
        self.graph_widget.set_highlight_path(path)
        self.desc_text.setHtml(
            f"<b style='color:#2ECC71;font-size:13px;'>最短路径高亮</b><br><br>"
            f"<span style='font-size:11px;'>"
            f"从 Router {self._source_node} 到 Router {target} 的最短路径：<br>"
            f"<b>{' → '.join(map(str, path))}</b><br>"
            f"总成本: {self._stepper.final_result[target][0]}"
            f"</span>"
        )

    def _on_node_clicked(self, node_id: int):
        """点击图中的节点时，更新目标选择"""
        idx = self.target_combo.findData(node_id)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
        if self._stepper.final_result and node_id in self._stepper.final_result:
            self._highlight_path_for(node_id)

    def _highlight_path_for(self, target: int):
        if target not in self._stepper.final_result:
            return
        _, path = self._stepper.final_result[target]
        self.graph_widget.set_highlight_path(path)

    def refresh_data(self):
        """外部调用 - 刷新路由器列表和拓扑"""
        self._update_source_list()
        self._on_source_changed()
