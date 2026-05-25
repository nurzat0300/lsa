"""
LSA 生命周期视图 + 洪泛动画
实时追踪 LSA 从产生到洪泛全过程，支持自动播放和手动回溯
"""
import time as _time
import math
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QCheckBox, QSplitter,
    QFrame, QComboBox, QHeaderView, QSlider,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
)

from ..core.lsa import LSAEventType, lsa_event_log

# ========== 颜色定义 ==========
EVENT_COLORS = {
    LSAEventType.CREATED: QColor("#27AE60"),
    LSAEventType.RECEIVED_NEW: QColor("#3498DB"),
    LSAEventType.RECEIVED_OLD: QColor("#95A5A6"),
    LSAEventType.RECEIVED_DUP: QColor("#F39C12"),
    LSAEventType.FORWARDED: QColor("#9B59B6"),
    LSAEventType.DISCARDED_TTL: QColor("#E74C3C"),
}
EVENT_LABELS = {
    LSAEventType.CREATED: "生成",
    LSAEventType.RECEIVED_NEW: "接受(新)",
    LSAEventType.RECEIVED_OLD: "丢弃(旧)",
    LSAEventType.RECEIVED_DUP: "丢弃(重复)",
    LSAEventType.FORWARDED: "洪泛转发",
    LSAEventType.DISCARDED_TTL: "TTL耗尽",
}

# ========== 拓扑绘制组件 ==========
class LSAFloodPaintWidget(QWidget):
    """LSA 洪泛动画 — 拓扑 + 逐跳扩散"""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        self._nodes: List[int] = []
        self._edges: List[Tuple[int, int, int]] = []
        self._pos: Dict[int, Tuple[float, float]] = {}
        self._status: Dict[int, str] = {}   # source/received/forwarded/none
        self._anim_edges: set = set()
        self._needs_layout = True
        self._title = "等待 LSA 事件..."

    def set_topo(self, nodes: List[int], edges: List[Tuple[int, int, int]]):
        """设置拓扑数据（节点ID列表 + [(u,v,cost),...] 边列表）"""
        if nodes != self._nodes or edges != self._edges:
            self._nodes = list(nodes)
            self._edges = list(edges)
            self._needs_layout = True
            self._status = {n: "none" for n in nodes}
            self._anim_edges = set()
            self._title = "拓扑已加载 — LSA 事件追踪中..."
            self.update()

    def set_state(self, source: int, received: set, forwarded: set,
                  anim_edges: set = None, title: str = ""):
        """更新洪泛状态"""
        changed = False
        for n in self._nodes:
            old = self._status.get(n, "none")
            if n == source:
                new = "source"
            elif n in forwarded:
                new = "forwarded"
            elif n in received:
                new = "received"
            else:
                new = "none"
            if old != new:
                self._status[n] = new
                changed = True

        new_edges = anim_edges or set()
        if new_edges != self._anim_edges:
            self._anim_edges = new_edges
            changed = True

        if title:
            self._title = title

        if changed:
            self.update()

    def reset(self):
        self._status = {n: "none" for n in self._nodes}
        self._anim_edges = set()
        self._title = "动画已重置"
        self.update()

    def _do_layout(self):
        nodes = self._nodes
        if not nodes:
            return
        n = len(nodes)
        w = max(self.width() - 80, 200)
        h = max(self.height() - 80, 200)
        cx, cy = w / 2 + 40, h / 2 + 40
        rx, ry = max(w / 2 - 50, 30), max(h / 2 - 50, 30)

        for i, node in enumerate(nodes):
            if n <= 10:
                angle = 2 * math.pi * i / n - math.pi / 2
                self._pos[node] = (cx + rx * math.cos(angle), cy + ry * math.sin(angle))
            elif n <= 20:
                half = (n + 1) // 2
                outer_rx, outer_ry = rx, ry
                inner_rx, inner_ry = rx * 0.5, ry * 0.5
                if i < half:
                    angle = 2 * math.pi * i / half - math.pi / 2
                    self._pos[node] = (cx + outer_rx * math.cos(angle), cy + outer_ry * math.sin(angle))
                else:
                    angle = 2 * math.pi * (i - half) / max(n - half, 1) - math.pi / 2 + math.pi / max(n - half, 1)
                    self._pos[node] = (cx + inner_rx * math.cos(angle), cy + inner_ry * math.sin(angle))
            else:
                cols = math.ceil(math.sqrt(n))
                rows = math.ceil(n / cols)
                cell_w = min((w - 80) / cols, 110)
                cell_h = min((h - 80) / rows, 90)
                sx = cx - (cols - 1) * cell_w / 2
                sy = cy - (rows - 1) * cell_h / 2
                col = i % cols
                row = i // cols
                self._pos[node] = (sx + col * cell_w, sy + row * cell_h)
        self._needs_layout = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FAFBFC"))

        if not self._nodes:
            painter.setPen(QColor("#999"))
            painter.setFont(QFont("Microsoft YaHei", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, self._title)
            return

        if self._needs_layout:
            self._do_layout()

        r = 20  # node radius

        # === 第1层：画所有边 ===
        for u, v, cost in self._edges:
            if u not in self._pos or v not in self._pos:
                continue
            x1, y1 = self._pos[u]
            x2, y2 = self._pos[v]
            dx, dy = x2 - x1, y2 - y1
            length = math.sqrt(dx * dx + dy * dy)
            if length < 1:
                continue
            nx, ny = dx / length, dy / length

            # 洪泛边用紫色高亮
            is_anim = (u, v) in self._anim_edges or (v, u) in self._anim_edges
            if is_anim:
                pen = QPen(QColor("#9B59B6"), 3)
                pen.setStyle(Qt.DashLine)
                painter.setPen(pen)
            else:
                painter.setPen(QPen(QColor("#d5dbe3"), 1.2))

            painter.drawLine(
                int(x1 + nx * r), int(y1 + ny * r),
                int(x2 - nx * r), int(y2 - ny * r),
            )

            # 边权
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ox = -dy / length * 11
            oy = dx / length * 11
            painter.setPen(QColor("#888"))
            painter.setFont(QFont("Arial", 7, QFont.Bold))
            painter.drawText(int(mx + ox - 10), int(my + oy - 8), 20, 16,
                           Qt.AlignCenter, str(cost))

        # === 第2层：画节点 ===
        for node in self._nodes:
            if node not in self._pos:
                continue
            x, y = self._pos[node]
            status = self._status.get(node, "none")

            if status == "source":
                color = QColor("#E74C3C")
            elif status == "forwarded":
                color = QColor("#27AE60")
            elif status == "received":
                color = QColor("#3498DB")
            else:
                color = QColor("#BDC3C7")

            # 渐变球体
            grad = QRadialGradient(x - r * 0.3, y - r * 0.3, r)
            grad.setColorAt(0, color.lighter(150))
            grad.setColorAt(0.6, color)
            grad.setColorAt(1, color.darker(120))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(color.darker(140), 2))
            painter.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))

            # 标签
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(int(x - r), int(y - r), int(r * 2), int(r * 2),
                           Qt.AlignCenter, f"R{node}")

        # === 标题 ===
        painter.setPen(QColor("#2C3E50"))
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.drawText(10, self.height() - 8, self._title)


# ========== LSA 监视器主面板 ==========
class LSAMonitorWidget(QWidget):
    """LSA 生命周期监视器 — 事件表格 + 洪泛动画"""

    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self._events_cache: List[Dict] = []
        self._auto_scroll = True
        self._filter_source: Optional[int] = None
        self._ready = False

        # 动画播放
        self._anim_playing = False
        self._anim_step = 0
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._anim_advance)
        self._anim_speed_ms = 600

        self.init_ui()
        self._ready = True

        # 延迟启动刷新，避免初始化期间竞争
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._safe_refresh)
        self._refresh_timer.start(1500)

    def init_ui(self):
        layout = QVBoxLayout()

        # ---- 控制栏 ----
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("过滤源:"))

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部", None)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        ctrl.addWidget(self.filter_combo)

        self.auto_scroll_cb = QCheckBox("自动滚动")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(lambda v: setattr(self, '_auto_scroll', v))
        ctrl.addWidget(self.auto_scroll_cb)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_log)
        ctrl.addWidget(clear_btn)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        # ---- 分割面板 ----
        splitter = QSplitter(Qt.Vertical)

        # == 上半：事件表格 ==
        top_frame = QFrame()
        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["时间", "事件", "LSA源", "序列号", "详情"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 60)
        self.table.cellClicked.connect(self._on_row_clicked)
        top_layout.addWidget(self.table)

        top_frame.setLayout(top_layout)
        splitter.addWidget(top_frame)

        # == 下半：洪泛动画 ==
        bottom_frame = QFrame()
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(0, 4, 0, 0)

        # 标题行 + 图例 + 控制
        anim_ctrl = QHBoxLayout()
        anim_ctrl.addWidget(QLabel("LSA 洪泛传播"))
        anim_ctrl.addSpacing(20)

        for color, label in [
            ("#E74C3C", "LSA源头"), ("#3498DB", "已接收"),
            ("#27AE60", "已转发"), ("#BDC3C7", "未到达"),
            ("#9B59B6", "传播路径"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
            anim_ctrl.addWidget(dot)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 10px; color: #555;")
            anim_ctrl.addWidget(lbl)
            anim_ctrl.addSpacing(6)

        anim_ctrl.addStretch()

        # 动画播放按钮
        self.play_btn = QPushButton("▶ 自动播放")
        self.play_btn.clicked.connect(self._toggle_anim)
        anim_ctrl.addWidget(self.play_btn)

        self.reset_anim_btn = QPushButton("重置")
        self.reset_anim_btn.clicked.connect(self._reset_animation)
        anim_ctrl.addWidget(self.reset_anim_btn)

        anim_ctrl.addWidget(QLabel("速度:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.speed_slider.setMaximumWidth(80)
        anim_ctrl.addWidget(self.speed_slider)

        bottom_layout.addLayout(anim_ctrl)

        self.flood_paint = LSAFloodPaintWidget()
        bottom_layout.addWidget(self.flood_paint, 1)

        bottom_frame.setLayout(bottom_layout)
        splitter.addWidget(bottom_frame)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter, 1)

        # 底部状态
        self.status_label = QLabel("就绪 — 等待 LSA 事件...")
        self.status_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    def _on_filter_changed(self):
        self._filter_source = self.filter_combo.currentData()
        self._events_cache = []  # 强制刷新

    def _clear_log(self):
        lsa_event_log.clear()
        self._events_cache = []
        self.table.setRowCount(0)
        self.flood_paint.reset()

    def _on_speed_changed(self, v):
        self._anim_speed_ms = int(1500 / v)

    def _toggle_anim(self):
        if self._anim_playing:
            self._anim_timer.stop()
            self._anim_playing = False
            self.play_btn.setText("▶ 自动播放")
        else:
            if not self._events_cache:
                return
            self._anim_step = 0
            self._anim_playing = True
            self._anim_timer.start(self._anim_speed_ms)
            self.play_btn.setText("⏸ 暂停")

    def _anim_advance(self):
        if self._anim_step >= len(self._events_cache):
            self._anim_timer.stop()
            self._anim_playing = False
            self.play_btn.setText("▶ 自动播放")
            return
        self._apply_flood_state_at(self._anim_step)
        self._anim_step += 1

    def _apply_flood_state_at(self, ev_idx: int):
        """根据前 ev_idx 个事件，计算并绘制洪泛状态"""
        events = self._events_cache
        if ev_idx >= len(events):
            return

        source = None
        received = set()
        forwarded = set()
        anim_edges = set()

        for i in range(ev_idx + 1):
            ev = events[i]
            rid = ev['router_id']
            etype = LSAEventType(ev['event_type'])
            src = ev['source_router_id']

            if etype == LSAEventType.CREATED:
                source = src
                received.add(rid)
            elif etype == LSAEventType.RECEIVED_NEW:
                received.add(rid)
            elif etype == LSAEventType.FORWARDED:
                forwarded.add(rid)
                # 找到和该路由器相邻的已接收节点 → 标记为传播边
                for nid in received | forwarded:
                    if nid != rid:
                        anim_edges.add((min(rid, nid), max(rid, nid)))

        # 获取拓扑边用于边匹配
        topo = self.simulator.get_topology()
        valid_edges = set()
        for e in topo.get('edges', []):
            key = (min(e['source'], e['target']), max(e['source'], e['target']))
            valid_edges.add(key)

        # 只保留存在拓扑中的边
        anim_edges = anim_edges & valid_edges

        title = f"步骤 {ev_idx + 1}/{len(events)} — {events[ev_idx].get('detail', '')}"
        self.flood_paint.set_state(source or 0, received, forwarded, anim_edges, title)

    def _on_row_clicked(self, row, col):
        """点击表格行 → 显示对应时刻的洪泛状态"""
        if not self._events_cache:
            return
        # 事件在表格中倒序显示
        ev_idx = len(self._events_cache) - 1 - row
        if 0 <= ev_idx < len(self._events_cache):
            self._anim_timer.stop()
            self._anim_playing = False
            self.play_btn.setText("▶ 自动播放")
            self._anim_step = ev_idx
            self._apply_flood_state_at(ev_idx)

    def _reset_animation(self):
        self._anim_timer.stop()
        self._anim_playing = False
        self.play_btn.setText("▶ 自动播放")
        self._anim_step = 0
        self.flood_paint.reset()

    def _safe_refresh(self):
        """带异常保护的刷新"""
        try:
            self._refresh()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _refresh(self):
        """每1.5秒拉取事件并刷新UI"""
        if not self._ready:
            return
        # 更新过滤下拉
        self.filter_combo.blockSignals(True)
        current = self.filter_combo.currentData()
        existing = {self.filter_combo.itemData(i) for i in range(1, self.filter_combo.count())}
        for rid in sorted(self.simulator.routers.keys()):
            if rid not in existing:
                self.filter_combo.addItem(f"Router {rid}", rid)
        idx = self.filter_combo.findData(current)
        if idx >= 0:
            self.filter_combo.setCurrentIndex(idx)
        self.filter_combo.blockSignals(False)

        # 拉取事件
        raw = lsa_event_log.get_recent(500)
        if self._filter_source is not None:
            raw = [e for e in raw if e['source_router_id'] == self._filter_source]

        # 检查是否有新事件
        if len(raw) == len(self._events_cache):
            if raw and self._events_cache and raw[-1] == self._events_cache[-1]:
                # 没有新事件，但拓扑可能变化
                self._update_topo_only()
                return

        self._events_cache = raw

        # 更新表格
        self.table.setRowCount(len(raw))
        for row, ev in enumerate(reversed(raw)):
            ts_sec = ev['timestamp']
            ts_str = _time.strftime("%H:%M:%S", _time.localtime(ts_sec)) + f".{int(ts_sec % 1 * 1000):03d}"
            self.table.setItem(row, 0, QTableWidgetItem(ts_str))

            et = LSAEventType(ev['event_type'])
            ti = QTableWidgetItem(EVENT_LABELS.get(et, "?"))
            ti.setForeground(EVENT_COLORS.get(et, QColor("#333")))
            self.table.setItem(row, 1, ti)
            self.table.setItem(row, 2, QTableWidgetItem(f"R{ev['source_router_id']}"))
            self.table.setItem(row, 3, QTableWidgetItem(str(ev['seq_number'])))
            self.table.setItem(row, 4, QTableWidgetItem(ev['detail']))

        if self._auto_scroll and raw:
            self.table.scrollToBottom()

        # 更新拓扑数据
        self._update_topo_only()

        # 显示最新状态
        if raw and not self._anim_playing:
            self._apply_flood_state_at(len(raw) - 1)

        # 统计
        counts = defaultdict(int)
        for ev in raw:
            counts[LSAEventType(ev['event_type']).name] += 1
        parts = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        self.status_label.setText(f"事件总数: {len(raw)} | {parts}")

    def _update_topo_only(self):
        """只更新拓扑（不改变事件列表）"""
        topo = self.simulator.get_topology()
        nodes_list = [n['id'] for n in topo.get('nodes', [])]
        edges_list = [(e['source'], e['target'], e['cost']) for e in topo.get('edges', [])]
        if nodes_list:
            self.flood_paint.set_topo(nodes_list, edges_list)

    def refresh_data(self):
        """外部调用刷新"""
        self._refresh()
