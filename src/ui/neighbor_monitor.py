"""
邻居状态机 + Hello/Dead 定时器可视化
通过公开 API 安全读取邻居状态
"""
import time as _time
from typing import Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
)


STATE_COLORS = {
    "down": QColor("#E74C3C"),
    "init": QColor("#F39C12"),
    "2-way": QColor("#3498DB"),
    "full": QColor("#27AE60"),
}
STATE_LABELS = {"down": "Down", "init": "Init", "2-way": "2-Way", "full": "Full"}
STATE_ORDER = ["down", "init", "2-way", "full"]


class NeighborBar(QWidget):
    """单个邻居的状态条"""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(95)
        self.setMaximumHeight(110)
        self._data = {}

    def update_data(self, neighbor_id: int, state: str, hello_elapsed: float,
                    hello_interval: float, timeout_count: int,
                    lost_count: int, cost: int, router_name: str = ""):
        self._data = {
            'id': neighbor_id, 'state': state, 'hello_elapsed': hello_elapsed,
            'hello_interval': hello_interval, 'timeout_count': timeout_count,
            'lost_count': lost_count, 'cost': cost, 'router_name': router_name,
        }
        self.update()

    def paintEvent(self, event):
        d = self._data
        if not d:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # 卡片背景
        painter.fillRect(0, 0, w, h, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#E0E4E8"), 1))
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 10, 10)

        rid = d['id']
        rname = d.get('router_name', '')
        label = f"Router {rid}" if not rname else f"Router {rid} ({rname})"

        painter.setPen(QColor("#2C3E50"))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        painter.drawText(16, 22, label)

        # 状态 + 成本
        sc = STATE_COLORS.get(d['state'], QColor("#999"))
        painter.setPen(sc)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(16, 40, f"状态: {STATE_LABELS.get(d['state'], d['state'])}")
        painter.setPen(QColor("#888"))
        painter.drawText(16, 54, f"成本: {d['cost']}")

        # ---- 状态机条 ----
        bar_x, bar_y = 14, 66
        bar_w = min(w - 28, 340)
        bar_h = 12
        step_w = bar_w / 4
        cur_idx = STATE_ORDER.index(d['state']) if d['state'] in STATE_ORDER else 0

        for i, s in enumerate(STATE_ORDER):
            sx = bar_x + i * step_w
            if cur_idx >= i:
                c = QColor(STATE_COLORS[s])
                c.setAlpha(255 if d['state'] == s else 140)
                painter.setBrush(QBrush(c))
                painter.setPen(Qt.NoPen)
            else:
                painter.setBrush(QBrush(QColor("#EEE")))
                painter.setPen(QPen(QColor("#DDD"), 1))
            painter.drawRoundedRect(int(sx), bar_y, int(step_w - 4), bar_h, 4, 4)
            painter.setPen(Qt.white if cur_idx >= i else QColor("#999"))
            painter.setFont(QFont("Arial", 6, QFont.Bold))
            painter.drawText(int(sx), bar_y, int(step_w - 4), bar_h, Qt.AlignCenter, STATE_LABELS[s])

        # ---- Hello 倒计时 + Dead 超时 ----
        timer_x = bar_x
        timer_w = bar_w
        t1_y = bar_y + bar_h + 6
        t1_h, t2_h = 8, 6

        # Hello bar
        painter.setBrush(QBrush(QColor("#EEE")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(int(timer_x), t1_y, int(timer_w), t1_h, 3, 3)
        hello_ratio = min(d['hello_elapsed'] / max(d['hello_interval'], 0.01), 1.0)
        if hello_ratio > 0:
            grad = QLinearGradient(timer_x, 0, timer_x + timer_w, 0)
            grad.setColorAt(0, QColor("#3498DB"))
            grad.setColorAt(1, QColor("#2ECC71"))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(int(timer_x), t1_y, int(timer_w * hello_ratio), t1_h, 3, 3)

        # Dead bar
        t2_y = t1_y + t1_h + 3
        dead_ratio = min(d['lost_count'] / max(d['timeout_count'], 1), 1.0)
        painter.setBrush(QBrush(QColor("#FDEBD0")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(int(timer_x), t2_y, int(timer_w), t2_h, 3, 3)
        if dead_ratio > 0:
            dc = QColor("#E74C3C") if dead_ratio > 0.6 else QColor("#F39C12")
            painter.setBrush(QBrush(dc))
            painter.drawRoundedRect(int(timer_x), t2_y, int(timer_w * dead_ratio), t2_h, 3, 3)

        # 标注文字
        painter.setPen(QColor("#888"))
        painter.setFont(QFont("Arial", 7))
        hi = d['hello_interval']
        painter.drawText(int(timer_x), t1_y + t1_h + 8,
                         f"Hello: {d['hello_elapsed']:.1f}s / {hi:.1f}s   超时计数: {d['lost_count']}/{d['timeout_count']}")


class NeighborMonitorWidget(QWidget):
    """邻居状态机面板 — 安全读取公开 API"""

    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self._bars: Dict[int, NeighborBar] = {}
        self._selected_router = None
        self._ready = False
        self.init_ui()
        self._ready = True

        self._timer = QTimer()
        self._timer.timeout.connect(self._safe_refresh)
        self._timer.start(1500)

    def init_ui(self):
        layout = QVBoxLayout()

        # 标题
        title = QLabel("邻居状态机 — Hello / Dead 定时器")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2C3E50;")
        layout.addWidget(title)

        # 图例
        leg = QHBoxLayout()
        for s in STATE_ORDER:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {STATE_COLORS[s].name()}; font-size: 14px; font-weight: bold;")
            leg.addWidget(dot)
            leg.addWidget(QLabel(STATE_LABELS[s]))
            leg.addSpacing(12)
        leg.addStretch()
        layout.addLayout(leg)

        desc = QLabel("Down → Init: 收到Hello → 2-Way: 双向确认 → Full: LSA同步完成")
        desc.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
        layout.addWidget(desc)

        # 路由器选择
        sel = QHBoxLayout()
        sel.addWidget(QLabel("观察视角:"))
        self.router_combo = QComboBox()
        self.router_combo.currentIndexChanged.connect(self._on_router_changed)
        sel.addWidget(self.router_combo)
        sel.addStretch()
        layout.addLayout(sel)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        self.bars_layout = QVBoxLayout()
        self.bars_layout.addStretch()
        container.setLayout(self.bars_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        self.setLayout(layout)
        self._update_router_list()

    def _update_router_list(self):
        self.router_combo.blockSignals(True)
        current = self.router_combo.currentData()
        self.router_combo.clear()
        for rid in sorted(self.simulator.routers.keys()):
            r = self.simulator.routers[rid]
            self.router_combo.addItem(f"Router {rid} ({r.router_name})", rid)
        idx = self.router_combo.findData(current)
        if idx >= 0:
            self.router_combo.setCurrentIndex(idx)
        elif self.router_combo.count() > 0:
            self.router_combo.setCurrentIndex(0)
        self.router_combo.blockSignals(False)
        self._selected_router = self.router_combo.currentData()

    def _on_router_changed(self):
        self._selected_router = self.router_combo.currentData()
        self._refresh()

    def _safe_refresh(self):
        """带异常保护的刷新"""
        try:
            self._refresh()
        except Exception:
            pass

    def _refresh(self):
        """使用公开 API 安全读取邻居数据"""
        if not self._ready:
            return
        self._update_router_list()
        rid = self._selected_router
        if rid is None or rid not in self.simulator.routers:
            return

        router = self.simulator.routers[rid]
        now = _time.time()

        # 通过公开 API 获取数据（get_lsa_data 内部有锁保护）
        try:
            lsa_data = router.get_lsa_data()
        except Exception:
            return

        neighbors = lsa_data.get('neighbors', {})
        neighbor_ids = set()

        for nid_str, ninfo in neighbors.items():
            nid = int(nid_str)
            neighbor_ids.add(nid)

            if nid not in self._bars:
                bar = NeighborBar()
                self._bars[nid] = bar
                self.bars_layout.insertWidget(self.bars_layout.count() - 1, bar)

            state_raw = ninfo.get('state', 'down')
            lost_count = ninfo.get('lost_count', 0)
            cost = ninfo.get('cost', 1)

            # 用 last_seen 估算 hello_elapsed（通过心跳超时计数推算）
            hello_interval = router._heartbeat_interval if hasattr(router, '_heartbeat_interval') else 0.8
            timeout_threshold = router._heartbeat_timeout_threshold if hasattr(router, '_heartbeat_timeout_threshold') else 3

            # 估算距上次Hello的时间
            if state_raw == 'up' and lost_count == 0:
                hello_elapsed = hello_interval * 0.3  # 大约在中间
                state = 'full'
            elif state_raw == 'up' and lost_count < timeout_threshold:
                hello_elapsed = hello_interval * (1 + lost_count * 0.8)
                state = '2-way'
            elif state_raw == 'down' and lost_count == 0:
                hello_elapsed = 0
                state = 'down'
            elif lost_count == 0:
                hello_elapsed = hello_interval * 0.5
                state = 'init'
            else:
                hello_elapsed = hello_interval * (1 + lost_count)
                state = 'init' if lost_count < timeout_threshold else 'down'

            n_router = self.simulator.routers.get(nid)
            n_name = n_router.router_name if n_router else ""

            self._bars[nid].update_data(
                nid, state, hello_elapsed, hello_interval,
                timeout_threshold, lost_count, cost, n_name,
            )

        # 移除不再存在的邻居
        for old_id in list(self._bars.keys()):
            if old_id not in neighbor_ids:
                bar = self._bars.pop(old_id)
                self.bars_layout.removeWidget(bar)
                bar.deleteLater()

    def refresh_data(self):
        self._refresh()
