# -*- coding: utf-8 -*-
"""theme.py — 다크 테마 팔레트와 Qt 스타일시트."""

from PySide6.QtGui import QColor, QFontDatabase, QPalette

# ── 팔레트 ────────────────────────────────────────────────────
BG        = "#0B0C10"   # 창 바탕
SIDEBAR   = "#101218"   # 좌측 패널
SURFACE   = "#14161D"   # 카드
SURFACE_2 = "#191C24"   # 카드 안쪽 입력칸
SURFACE_3 = "#1F2330"   # hover
BORDER    = "#242835"
BORDER_2  = "#2E3444"
TEXT      = "#E7E9EF"
TEXT_DIM  = "#9AA1B4"
TEXT_MUTE = "#6B7285"

ACCENT      = "#E74339"   # BSD 심볼 레드
ACCENT_HOV  = "#F05348"
ACCENT_DOWN = "#C7362E"
ACCENT_SOFT = "#2A1614"

BLUE   = "#4E8CFF"
GREEN  = "#3FBF7F"
AMBER  = "#E2B33C"

FONT_STACK = ['Pretendard', 'Pretendard Variable', 'SUIT', 'Malgun Gothic',
              'Segoe UI', 'Noto Sans KR']
MONO_STACK = ['JetBrains Mono', 'D2Coding', 'Cascadia Mono', 'Consolas']


def pick_font(stack, fallback="Malgun Gothic"):
    families = set(QFontDatabase.families())
    for name in stack:
        if name in families:
            return name
    return fallback


def apply_palette(app):
    """QSS 가 닿지 않는 곳(툴팁, 선택 배경 등)까지 어둡게."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor(BG))
    p.setColor(QPalette.WindowText, QColor(TEXT))
    p.setColor(QPalette.Base, QColor(SURFACE))
    p.setColor(QPalette.AlternateBase, QColor(SURFACE_2))
    p.setColor(QPalette.Text, QColor(TEXT))
    p.setColor(QPalette.Button, QColor(SURFACE_2))
    p.setColor(QPalette.ButtonText, QColor(TEXT))
    p.setColor(QPalette.ToolTipBase, QColor(SURFACE_3))
    p.setColor(QPalette.ToolTipText, QColor(TEXT))
    p.setColor(QPalette.Highlight, QColor(ACCENT))
    p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.PlaceholderText, QColor(TEXT_MUTE))
    p.setColor(QPalette.Link, QColor(BLUE))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(TEXT_MUTE))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(TEXT_MUTE))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(TEXT_MUTE))
    app.setPalette(p)


def stylesheet(font, mono):
    return QSS % dict(
        font=font, mono=mono,
        bg=BG, sidebar=SIDEBAR, surface=SURFACE, surface2=SURFACE_2,
        surface3=SURFACE_3, border=BORDER, border2=BORDER_2,
        text=TEXT, dim=TEXT_DIM, mute=TEXT_MUTE,
        accent=ACCENT, accent_hov=ACCENT_HOV, accent_down=ACCENT_DOWN,
        accent_soft=ACCENT_SOFT, blue=BLUE, green=GREEN, amber=AMBER,
    )


QSS = """
* { font-family: "%(font)s"; }

QWidget { color: %(text)s; font-size: 13px; }
QMainWindow, #Root { background: %(bg)s; }

/* ── 좌측 사이드바 ──────────────────────────────────────── */
#Sidebar { background: %(sidebar)s; border-right: 1px solid %(border)s; }
#BrandSub { color: %(mute)s; font-size: 11px; letter-spacing: 0.6px; }
#NavLabel { color: %(mute)s; font-size: 10px; font-weight: 700;
            letter-spacing: 1.2px; padding: 0 4px; }

QPushButton#Nav {
    background: transparent; border: 1px solid transparent;
    border-radius: 9px; padding: 9px 12px; text-align: left;
    color: %(dim)s; font-size: 13px; font-weight: 500;
}
QPushButton#Nav:hover { background: %(surface2)s; color: %(text)s; }
QPushButton#Nav:checked {
    background: %(surface3)s; color: %(text)s;
    border: 1px solid %(border2)s; font-weight: 600;
}

/* ── 카드 ───────────────────────────────────────────────── */
#Card {
    background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px;
}
#SubCard {
    background: %(surface2)s; border: 1px solid %(border)s; border-radius: 10px;
}
#CardTitle { font-size: 14px; font-weight: 700; }
#CardHint  { color: %(mute)s; font-size: 11px; }
#PageTitle { font-size: 21px; font-weight: 800; letter-spacing: -0.3px; }
#PageSub   { color: %(dim)s; font-size: 12px; }
#FieldLabel { color: %(dim)s; font-size: 11.5px; font-weight: 600; }
#Divider { background: %(border)s; max-height: 1px; border: none; }

/* ── 입력 ───────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: %(surface2)s; border: 1px solid %(border2)s;
    border-radius: 8px; padding: 7px 10px; color: %(text)s;
    selection-background-color: %(accent)s; selection-color: #fff;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border-color: #3A4256;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: %(accent)s; background: #1C1F29;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: %(mute)s; background: #15171E;
}
#SearchBox { padding-left: 30px; }

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    width: 16px; border: none; background: transparent;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-bottom: 5px solid %(dim)s;
    width: 0; height: 0; margin-bottom: 2px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid %(dim)s;
    width: 0; height: 0; margin-top: 2px;
}

QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid %(dim)s;
    width: 0; height: 0; margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: %(surface2)s; border: 1px solid %(border2)s; border-radius: 8px;
    selection-background-color: %(surface3)s; outline: none; padding: 4px;
}

/* ── 버튼 ───────────────────────────────────────────────── */
QPushButton {
    background: %(surface2)s; border: 1px solid %(border2)s; border-radius: 8px;
    padding: 8px 14px; color: %(text)s; font-weight: 600;
}
QPushButton:hover  { background: %(surface3)s; border-color: #3A4256; }
QPushButton:pressed { background: #171A22; }
QPushButton:disabled { color: %(mute)s; background: #15171E;
                       border-color: %(border)s; }

QPushButton#Primary {
    background: %(accent)s; border: 1px solid %(accent)s; color: #fff;
    padding: 9px 20px;
}
QPushButton#Primary:hover   { background: %(accent_hov)s; border-color: %(accent_hov)s; }
QPushButton#Primary:pressed { background: %(accent_down)s; }
QPushButton#Primary:disabled { background: #3A2320; border-color: #3A2320;
                               color: #8B6560; }

QPushButton#Ghost {
    background: transparent; border: 1px solid %(border2)s; color: %(dim)s;
}
QPushButton#Ghost:hover { color: %(text)s; background: %(surface2)s; }

QPushButton#Danger { border-color: #4A2A27; color: #F0857C; background: %(accent_soft)s; }
QPushButton#Danger:hover { background: #351916; color: #FF9C93; }

QPushButton#Chip {
    background: %(surface2)s; border: 1px solid %(border2)s; border-radius: 999px;
    padding: 5px 13px; font-size: 12px; font-weight: 600; color: %(dim)s;
}
QPushButton#Chip:hover { color: %(text)s; border-color: #3A4256; }
QPushButton#Chip:checked {
    background: %(accent_soft)s; border-color: %(accent)s; color: #FF8B82;
}

QPushButton#LinkBtn {
    background: transparent; border: none; color: %(mute)s; font-weight: 600;
    padding: 4px 6px; font-size: 11.5px;
}
QPushButton#LinkBtn:hover { color: %(text)s; }

/* ── 체크박스 ───────────────────────────────────────────── */
QCheckBox { color: %(dim)s; spacing: 8px; }
QCheckBox:hover { color: %(text)s; }
QCheckBox::indicator {
    width: 15px; height: 15px; border-radius: 4px;
    border: 1px solid %(border2)s; background: %(surface2)s;
}
QCheckBox::indicator:hover { border-color: #46506A; }
QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; }

/* ── 탭 ─────────────────────────────────────────────────── */
QTabWidget::pane { border: none; background: transparent; }
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    background: transparent; color: %(mute)s; padding: 7px 15px;
    margin-right: 4px; border-radius: 8px; font-weight: 600; font-size: 12.5px;
}
QTabBar::tab:hover { color: %(text)s; background: %(surface2)s; }
QTabBar::tab:selected {
    background: %(surface3)s; color: %(text)s;
}

/* ── 표 ─────────────────────────────────────────────────── */
QTableView {
    background: %(surface)s; alternate-background-color: #16181F;
    border: 1px solid %(border)s; border-radius: 12px;
    gridline-color: #1E212B; outline: none;
    selection-background-color: %(surface3)s; selection-color: %(text)s;
}
QTableView::item { padding: 5px 8px; border: none; }
QTableView::item:selected { background: #23283A; color: %(text)s; }
QHeaderView { background: transparent; }
QHeaderView::section {
    background: %(surface2)s; color: %(dim)s; border: none;
    border-right: 1px solid %(border)s; border-bottom: 1px solid %(border)s;
    padding: 8px 8px; font-weight: 700; font-size: 11.5px;
}
QHeaderView::section:hover { color: %(text)s; background: %(surface3)s; }
QHeaderView::down-arrow, QHeaderView::up-arrow { width: 0; height: 0; }
QTableCornerButton::section { background: %(surface2)s; border: none; }

/* ── 로그 ───────────────────────────────────────────────── */
QPlainTextEdit#Log {
    background: #0E1015; border: 1px solid %(border)s; border-radius: 10px;
    color: %(dim)s; font-family: "%(mono)s"; font-size: 11.5px;
    padding: 8px 10px; selection-background-color: %(accent)s;
}

/* ── 진행바 ─────────────────────────────────────────────── */
QProgressBar {
    background: %(surface2)s; border: none; border-radius: 3px;
    height: 6px; text-align: center; color: transparent;
}
QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }

/* ── 스크롤바 ───────────────────────────────────────────── */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: #2B3040; border-radius: 5px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #3A4256; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: #2B3040; border-radius: 5px; min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #3A4256; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ── 기타 ───────────────────────────────────────────────── */
QToolTip {
    background: #21252F; color: %(text)s; border: 1px solid %(border2)s;
    border-radius: 6px; padding: 5px 8px;
}
QMenu {
    background: %(surface2)s; border: 1px solid %(border2)s;
    border-radius: 9px; padding: 5px;
}
QMenu::item { padding: 7px 24px 7px 12px; border-radius: 6px; }
QMenu::item:selected { background: %(surface3)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 4px 8px; }
QSplitter::handle { background: transparent; height: 8px; }
QMessageBox { background: %(surface)s; }
QStatusBar { background: transparent; color: %(mute)s; }
QStatusBar::item { border: none; }
"""
