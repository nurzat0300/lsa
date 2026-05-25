"""
现代化样式表 — 链路状态路由协议分布式仿真系统
为教学场景设计：清晰、现代、护眼
"""

STYLESHEET = """
/* ========== 全局 ========== */
QMainWindow {
    background-color: #f0f2f5;
}

QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}

/* ========== 标签页容器 ========== */
QTabWidget::pane {
    border: none;
    background-color: #f0f2f5;
    border-radius: 10px;
}

QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e8ecf1, stop:1 #d5dbe3);
    color: #5a6a7e;
    padding: 10px 24px;
    margin-right: 3px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid #d0d7de;
    border-bottom: none;
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #f8f9fb);
    color: #1a73e8;
    border-bottom: 3px solid #1a73e8;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background: #e3eaf2;
    color: #2c3e50;
}

/* ========== 按钮 ========== */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a73e8, stop:1 #1557b0);
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 12px;
    min-height: 20px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1e82f0, stop:1 #1864c7);
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1557b0, stop:1 #0f4390);
}

QPushButton:disabled {
    background: #b0c4de;
    color: #e0e0e0;
}

/* ========== 标签 ========== */
QLabel {
    color: #2c3e50;
    font-size: 12px;
}

/* ========== 输入框 ========== */
QLineEdit, QSpinBox, QComboBox {
    padding: 7px 10px;
    border: 1.5px solid #d0d7de;
    border-radius: 6px;
    background-color: #ffffff;
    color: #2c3e50;
    font-size: 12px;
    selection-background-color: #1a73e8;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 2px solid #1a73e8;
    background-color: #f8faff;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    border: 1px solid #d0d7de;
    border-radius: 4px;
    padding: 4px;
    selection-background-color: #e8f0fe;
    selection-color: #1a73e8;
}

/* ========== 表格 ========== */
QTableWidget {
    gridline-color: #e8ecf1;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    background-color: #ffffff;
    alternate-background-color: #fafbfc;
    font-size: 12px;
}

QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #f0f2f5;
}

QTableWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a73e8, stop:1 #1557b0);
    color: white;
    padding: 8px 10px;
    border: none;
    font-weight: 700;
    font-size: 12px;
}

/* ========== 文本编辑框 ========== */
QTextEdit {
    border: 1.5px solid #d0d7de;
    border-radius: 8px;
    background-color: #ffffff;
    padding: 10px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    color: #2c3e50;
}

/* ========== 状态栏 ========== */
QStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a1f36, stop:1 #2c3e50);
    color: #e0e6ed;
    border-top: 2px solid #1a73e8;
    font-size: 12px;
    padding: 4px 12px;
}

/* ========== 滑块 ========== */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #d0d7de;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #1a73e8;
    border: 2px solid white;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 9px;
}

QSlider::sub-page:horizontal {
    background: #1a73e8;
    border-radius: 3px;
}

/* ========== 框架面板 ========== */
QFrame#panel {
    background-color: #ffffff;
    border: 1px solid #e0e4e8;
    border-radius: 10px;
    padding: 12px;
}

/* ========== 滚动条 ========== */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #c0c8d0;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #a0a8b0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
}

QScrollBar::handle:horizontal {
    background: #c0c8d0;
    border-radius: 4px;
    min-width: 30px;
}

/* ========== 提示框 ========== */
QMessageBox {
    background-color: #f0f2f5;
}

QMessageBox QLabel {
    color: #2c3e50;
    font-size: 13px;
}

QMessageBox QPushButton {
    min-width: 80px;
    min-height: 28px;
}

/* ========== 分割线 ========== */
QSplitter::handle {
    background: #d0d7de;
    width: 2px;
}
"""


def apply_stylesheet(app_or_widget):
    """应用现代化样式表"""
    app_or_widget.setStyleSheet(STYLESHEET)
