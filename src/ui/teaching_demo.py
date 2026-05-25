"""
协议教学演示 - 逐步展示链路状态路由协议的工作流程
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFrame, QScrollArea, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette


STEPS = [
    {
        "title": "第1步：理解网络拓扑",
        "icon": "🌐",
        "explanation": """
<h3>什么是链路状态路由协议？</h3>

<p>链路状态路由协议（如 OSPF）是互联网中最常用的内部网关协议之一。它的核心思想是：</p>

<p><b>每个路由器都要知道整个网络的"地图"</b>（即完整的拓扑结构），然后独立计算到达每个目的地的最短路径。</p>

<p>这就像每个人都有一张完整的城市地图，可以自己规划去任何地方的最短路线。</p>

<h4>关键概念：</h4>
<ul>
<li><b>链路（Link）</b>：两个路由器之间的直接连接，每条链路有一个<b>成本（Cost）</b>值</li>
<li><b>链路状态（Link State）</b>：描述一个路由器有哪些邻居、链路成本是多少</li>
<li><b>拓扑数据库（LSDB）</b>：每个路由器存储全网拓扑信息的地方</li>
<li><b>最短路径树（SPT）</b>：以自己为根，到达所有目的地的最短路径构成的树</li>
</ul>

<p><b>提示：</b>切换到"网络拓扑"标签页查看当前网络的连接状态。</p>
"""
    },
    {
        "title": "第2步：邻居发现（Hello协议）",
        "icon": "👋",
        "explanation": """
<h3>邻居发现机制</h3>

<p>路由器启动后，首先要做的事情是<b>发现直接相连的邻居路由器</b>。</p>

<p>每个路由器会周期性地向所有邻居发送 <b>Hello 消息</b>（也叫心跳消息），告诉邻居"我还活着"。</p>

<h4>在本系统中：</h4>
<ul>
<li>每个路由器每 <b>0.8秒</b>（小拓扑）发送一次心跳</li>
<li>心跳消息包含：消息类型 + 路由器ID</li>
<li>收到心跳后，将邻居状态标记为 <b>UP</b></li>
<li>如果连续 <b>3次</b> 没有收到心跳，判定邻居 <b>DOWN</b></li>
</ul>

<h4>实验建议：</h4>
<p>在"仿真控制"标签页中，尝试<b>模拟链路故障</b>，观察邻居状态如何从 UP 变为 DOWN，
然后<b>恢复链路</b>，观察邻居如何重新建立连接。</p>
"""
    },
    {
        "title": "第3步：LSA 生成",
        "icon": "📝",
        "explanation": """
<h3>链路状态通告（LSA）</h3>

<p>发现邻居后，每个路由器需要把自己的链路状态信息告诉整个网络，这就是 <b>LSA（Link State Advertisement）</b>。</p>

<h4>LSA 包含什么？</h4>
<ul>
<li><b>路由器ID</b>：谁发出的</li>
<li><b>序列号</b>：版本号，每次更新递增</li>
<li><b>邻居列表</b>：我连接了哪些路由器，每个链路的成本是多少</li>
<li><b>链路状态</b>：每条链路是 UP 还是 DOWN</li>
</ul>

<h4>类比理解：</h4>
<p>LSA 就像路由器向全网发了一张"名片"，上面写着：<br>
<i>"我是 Router3，我的邻居有 Router2（成本=2）、Router5（成本=3）、Router8（成本=9）。"</i></p>

<p>每个路由器都会定期（每5秒）生成新的 LSA，序列号递增。</p>
"""
    },
    {
        "title": "第4步：LSA 洪泛（Flooding）",
        "icon": "🌊",
        "explanation": """
<h3>可靠洪泛机制</h3>

<p>LSA 生成后，需要通过 <b>洪泛（Flooding）</b> 传播到整个网络中的每一个路由器。</p>

<h4>洪泛过程：</h4>
<ol>
<li>路由器收到一个新的 LSA</li>
<li>检查序列号：如果比已存储的更新，就接受并更新本地 LSDB</li>
<li>如果序列号相同或更旧，丢弃（避免重复处理）</li>
<li>将 LSA <b>转发给所有其他邻居</b>（除了发送者）</li>
<li>每转发一次，<b>跳数减1</b>（防止无限循环）</li>
</ol>

<h4>为什么需要洪泛？</h4>
<p>因为每个路由器都需要完整的全网拓扑信息。LSA 就像"传话游戏"——每个人收到消息后告诉所有其他人，
最终所有人都知道了。</p>

<h4>实验建议：</h4>
<p>切换到"算法动画"标签页，执行 Dijkstra 算法逐步演示，
观察 LSA 同步后全网拓扑是如何被用于计算路由的。</p>
"""
    },
    {
        "title": "第5步：SPF 计算（Dijkstra算法）",
        "icon": "🔢",
        "explanation": """
<h3>最短路径优先（SPF）计算</h3>

<p>当 LSDB 收集到全网拓扑后，每个路由器使用 <b>Dijkstra 算法</b> 计算以自己为根的最短路径树。</p>

<h4>Dijkstra 算法核心思想：</h4>
<ol>
<li>从源节点开始，距离=0</li>
<li>重复以下步骤直到所有节点都被访问：</li>
<ul>
<li>选择<b>距离最小</b>的未访问节点（贪心策略）</li>
<li>将该节点标记为<b>已访问</b></li>
<li><b>松弛</b>该节点的所有邻居：如果通过当前节点到达邻居的距离更短，就更新</li>
</ul>
</ol>

<h4>为什么要用 Dijkstra？</h4>
<ul>
<li>保证找到的是<b>全局最短路径</b></li>
<li>时间复杂度 O(V²) 或 O(E log V)（使用优先队列）</li>
<li>每个路由器独立计算，结果一致（因为 LSDB 相同）</li>
</ul>

<h4>动手实验：</h4>
<p>切换到<b>"算法动画"</b>标签页，选择任意路由器，
点击"播放"按钮，<b>一步步观察 Dijkstra 算法的执行过程</b>：
看节点如何被选中、距离如何更新、最短路径树如何构建。</p>
"""
    },
    {
        "title": "第6步：路由表生成",
        "icon": "📋",
        "explanation": """
<h3>生成路由表</h3>

<p>Dijkstra 算法计算出到每个目的地的最短路径（完整路径）后，路由器提取<b>下一跳</b>信息生成路由表。</p>

<h4>路由表结构：</h4>
<table style="width:100%; border-collapse: collapse; border: 1px solid #ddd;">
<tr style="background: #3498DB; color: white;">
<th style="padding: 6px;">目标网络/节点</th>
<th style="padding: 6px;">下一跳</th>
<th style="padding: 6px;">总成本</th>
<th style="padding: 6px;">完整路径</th>
</tr>
<tr style="background: #f8f8f8;">
<td style="padding: 5px; text-align: center;">Router5</td>
<td style="padding: 5px; text-align: center;">Router3</td>
<td style="padding: 5px; text-align: center;">8</td>
<td style="padding: 5px; text-align: center;">1→3→5</td>
</tr>
</table>

<h4>关键点：</h4>
<ul>
<li><b>下一跳</b>是路径上的第二个节点（第一个是自己）</li>
<li>路由器只关心<b>下一步发给谁</b>，不关心完整路径</li>
<li>这体现了<b>逐跳转发</b>的思想：每台路由器只做局部决策</li>
</ul>

<h4>实验建议：</h4>
<p>切换到"路由表"标签页，选择不同路由器查看各自的视角。
注意：不同路由器的路由表<b>不同</b>（因为根节点不同）。</p>
"""
    },
    {
        "title": "第7步：链路故障与收敛",
        "icon": "⚠️",
        "explanation": """
<h3>故障检测与重新收敛</h3>

<p>当链路发生故障时，协议需要<b>检测故障</b>并<b>重新计算路由</b>，这个过程叫做<b>收敛（Convergence）</b>。</p>

<h4>故障处理流程：</h4>
<ol>
<li>心跳超时 → 检测到邻居 DOWN</li>
<li>更新本地拓扑（移除故障链路）</li>
<li>立即发送新的 LSA（通告链路状态变化）</li>
<li>触发 SPF 重新计算</li>
<li>更新路由表（可能使用备用路径）</li>
</ol>

<h4>关键概念：</h4>
<ul>
<li><b>收敛时间</b>：从故障发生到所有路由器更新路由表的时间</li>
<li><b>路由环路</b>：收敛过程中可能出现的临时问题</li>
<li><b>链路恢复</b>：故障修复后，协议自动检测并恢复</li>
</ul>

<h4>动手实验：</h4>
<p>在"仿真控制"标签页中：</p>
<ol>
<li>先<b>模拟链路故障</b>（如 Router1↔Router2）</li>
<li>观察"路由表"中路由是否自动切换到备用路径</li>
<li>再<b>恢复链路</b>，观察路由是否恢复</li>
</ol>
"""
    },
    {
        "title": "第8步：算法性能对比",
        "icon": "📊",
        "explanation": """
<h3>不同最短路径算法的对比</h3>

<p>本系统实现了多种最短路径算法，用于对比分析：</p>

<h4>已实现的算法：</h4>
<table style="width:100%; border-collapse: collapse; border: 1px solid #ddd;">
<tr style="background: #3498DB; color: white;">
<th style="padding: 6px;">算法</th><th style="padding: 6px;">时间复杂度</th><th style="padding: 6px;">特点</th>
</tr>
<tr><td style="padding:5px;">Dijkstra</td><td style="padding:5px;">O(E log V)</td><td style="padding:5px;">经典算法，保证最优</td></tr>
<tr><td style="padding:5px;">Bellman-Ford</td><td style="padding:5px;">O(VE)</td><td style="padding:5px;">支持负权边</td></tr>
<tr><td style="padding:5px;">SPFA</td><td style="padding:5px;">O(kE)</td><td style="padding:5px;">Bellman-Ford的优化</td></tr>
<tr><td style="padding:5px;">Floyd-Warshall</td><td style="padding:5px;">O(V³)</td><td style="padding:5px;">全源最短路径</td></tr>
<tr><td style="padding:5px;">A*</td><td style="padding:5px;">O(E)</td><td style="padding:5px;">启发式搜索</td></tr>
</table>

<h4>实验建议：</h4>
<p>切换到"算法对比"标签页，选择不同规模的拓扑（8/20/50节点），
运行算法对比，观察各种算法在不同规模下的<b>计算时间</b>和<b>访问节点数</b>差异。</p>
"""
    },
]


class TeachingDemoWidget(QWidget):
    """协议教学演示窗口"""

    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator
        self._current_step = 0
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        # ---- 左侧：步骤导航 ----
        nav_frame = QFrame()
        nav_frame.setFrameStyle(QFrame.StyledPanel)
        nav_frame.setMaximumWidth(220)
        nav_layout = QVBoxLayout()

        nav_title = QLabel("学习步骤导航")
        nav_title.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        nav_title.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(nav_title)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #ddd;")
        nav_layout.addWidget(sep)

        self.step_buttons = []
        for i, step in enumerate(STEPS):
            btn = QPushButton(f"{step['icon']} {step['title']}")
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 10px 12px; "
                "border: none; border-radius: 4px; font-size: 11px; "
                "background: #f0f0f0; color: #333; }"
                "QPushButton:checked { background: #3498DB; color: white; "
                "font-weight: bold; }"
                "QPushButton:hover { background: #d5e8f7; }"
            )
            btn.clicked.connect(lambda checked, idx=i: self._go_to_step(idx))
            nav_layout.addWidget(btn)

            if i == 0:
                btn.setChecked(True)
            self.step_buttons.append(btn)

        nav_layout.addStretch()

        # 底部提示
        tip = QLabel("💡 按顺序学习效果最佳\n\n也可在标签页中\n动手操作验证")
        tip.setStyleSheet("color: #888; font-size: 10px; padding: 10px;")
        tip.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(tip)

        nav_frame.setLayout(nav_layout)
        layout.addWidget(nav_frame)

        # ---- 右侧：内容展示 ----
        content_frame = QFrame()
        content_frame.setFrameStyle(QFrame.StyledPanel)
        content_layout = QVBoxLayout()

        # 步骤标题
        self.step_title = QLabel()
        self.step_title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        self.step_title.setStyleSheet("padding: 15px; color: #2C3E50;")
        self.step_title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.step_title)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #ddd;")
        content_layout.addWidget(sep2)

        # 内容区域（可滚动）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none;")

        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setStyleSheet(
            "QTextEdit { border: none; padding: 15px; font-size: 13px; "
            "line-height: 1.8; background: transparent; }"
        )

        scroll_area.setWidget(self.content_text)
        content_layout.addWidget(scroll_area, 1)

        # 底部导航按钮
        nav_btn_layout = QHBoxLayout()

        self.prev_btn = QPushButton("◀ 上一步")
        self.prev_btn.clicked.connect(self._prev_step)
        nav_btn_layout.addWidget(self.prev_btn)

        nav_btn_layout.addStretch()

        step_indicator = QLabel("")
        step_indicator.setAlignment(Qt.AlignCenter)
        nav_btn_layout.addWidget(step_indicator)
        self.step_indicator = step_indicator

        nav_btn_layout.addStretch()

        self.next_btn = QPushButton("下一步 ▶")
        self.next_btn.clicked.connect(self._next_step)
        nav_btn_layout.addWidget(self.next_btn)

        btn_frame = QFrame()
        btn_frame.setLayout(nav_btn_layout)
        btn_frame.setStyleSheet(
            "QPushButton { padding: 8px 20px; border-radius: 4px; "
            "font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { opacity: 0.8; }"
        )
        content_layout.addWidget(btn_frame)

        content_frame.setLayout(content_layout)
        layout.addWidget(content_frame, 1)

        self.setLayout(layout)
        self._display_step(0)

    def _go_to_step(self, idx):
        self._current_step = idx
        self._display_step(idx)
        for i, btn in enumerate(self.step_buttons):
            btn.setChecked(i == idx)

    def _next_step(self):
        if self._current_step < len(STEPS) - 1:
            self._go_to_step(self._current_step + 1)

    def _prev_step(self):
        if self._current_step > 0:
            self._go_to_step(self._current_step - 1)

    def _display_step(self, idx):
        step = STEPS[idx]
        self.step_title.setText(f"{step['icon']} {step['title']}")
        self.content_text.setHtml(step['explanation'])

        self.prev_btn.setEnabled(idx > 0)
        self.next_btn.setEnabled(idx < len(STEPS) - 1)

        self.step_indicator.setText(f"{idx + 1} / {len(STEPS)}")
