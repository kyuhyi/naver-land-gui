# -*- coding: utf-8 -*-
"""
app.py — 네이버 부동산 매물 조회기 · BSD 다크 GUI (PySide6)

실행:  python app.py
필요:  pip install PySide6 playwright   (+ 구글 크롬 설치, 국내 IP)

조회 로직은 naver_land.py 를 그대로 씁니다. 이 파일은 화면과 흐름만 담당합니다.
"""

import csv
import os
import sys
from datetime import datetime

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QDesktopServices, QFont, QGuiApplication,
                           QIcon, QKeySequence, QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup,
                               QCheckBox, QDoubleSpinBox, QFileDialog, QFrame,
                               QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QSizePolicy, QSpinBox, QSplitter, QStackedWidget,
                               QTabWidget, QTableView, QVBoxLayout, QWidget)

import naver_land as nl
import theme
from models import ArticleModel, ComplexModel, FilterProxy
from worker import ChromeWarmupWorker, SearchWorker

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(APP_DIR, "assets")
LOGO = os.path.join(ASSETS, "bsd-white.png")
ICON = os.path.join(ASSETS, "bsd-symbol-color.png")

TRADES = [("매매", "A1"), ("전세", "B1"), ("월세", "B2"), ("단기", "B3")]
ESTATES = [("아파트", "A01"), ("주상복합", "A04"), ("오피스텔", "B01")]

MODES = [
    ("region",  "지역 검색",  "동 이름으로 그 동네 단지와 매물을 통째로 훑습니다."),
    ("complex", "단지 매물",  "단지번호 하나의 매물을 전량 가져옵니다."),
    ("info",    "단지 정보",  "단지의 이름·주소·세대수·매물 건수만 빠르게 봅니다."),
    ("area",    "지도 영역",  "경위도 사각형을 직접 지정해 그 안의 단지를 훑습니다."),
]


# ══════════════════════════════════════════════════════════════
# 작은 위젯들
# ══════════════════════════════════════════════════════════════
def _as_list(v):
    """QSettings 는 항목이 하나뿐인 목록을 문자열로 돌려주기도 한다."""
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def label(text, obj=None):
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    return lb


def field(text, widget, width=None):
    """라벨 + 입력칸 한 덩어리."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(label(text, "FieldLabel"))
    lay.addWidget(widget)
    if width:
        box.setFixedWidth(width)
    return box


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(14)


class ChipGroup(QWidget):
    """다중 선택 칩. values() 로 코드 목록을 준다."""

    changed = Signal()

    def __init__(self, items, checked=(), parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.buttons = []
        for name, code in items:
            b = QPushButton(name)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(code in checked)
            b.toggled.connect(lambda *_: self.changed.emit())
            b.setProperty("code", code)
            lay.addWidget(b)
            self.buttons.append(b)
        lay.addStretch(1)

    def values(self):
        return [b.property("code") for b in self.buttons if b.isChecked()]

    def set_values(self, codes):
        for b in self.buttons:
            b.setChecked(b.property("code") in codes)


class StatChip(QFrame):
    """결과 요약 한 칸."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("SubCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(13, 9, 13, 9)
        lay.setSpacing(2)
        self.t = QLabel(title)
        self.t.setObjectName("CardHint")
        self.v = QLabel("—")
        f = self.v.font()
        f.setPointSizeF(f.pointSizeF() + 2.5)
        f.setBold(True)
        self.v.setFont(f)
        lay.addWidget(self.t)
        lay.addWidget(self.v)

    def set(self, text, color=None):
        self.v.setText(text)
        self.v.setStyleSheet("color: %s;" % color if color else "")


class StatusDot(QWidget):
    """사이드바 하단 상태 표시."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: %s; font-size: 11px;" % theme.TEXT_MUTE)
        self.text = QLabel("대기 중")
        self.text.setStyleSheet("color: %s; font-size: 11.5px;" % theme.TEXT_DIM)
        lay.addWidget(self.dot)
        lay.addWidget(self.text, 1)

    def set(self, text, color):
        self.dot.setStyleSheet("color: %s; font-size: 11px;" % color)
        self.text.setText(text)


class ResultTable(QTableView):
    """공통 설정을 먹인 표."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.src = model
        self.proxy = FilterProxy(self)
        self.proxy.setSourceModel(model)
        self.setModel(self.proxy)

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        h = self.horizontalHeader()
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setMinimumSectionSize(44)
        for i, w in enumerate(model.widths):
            self.setColumnWidth(i, w)

        v = self.verticalHeader()
        v.setDefaultSectionSize(31)
        v.setSectionResizeMode(QHeaderView.Fixed)
        v.setFixedWidth(44)
        v.setHighlightSections(False)

    def selected_rows(self):
        out, seen = [], set()
        for idx in self.selectionModel().selectedRows():
            r = self.proxy.mapToSource(idx).row()
            if r not in seen:
                seen.add(r)
                out.append(self.src.row_at(r))
        return out

    def row_under(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return None
        return self.src.row_at(self.proxy.mapToSource(idx).row())


# ══════════════════════════════════════════════════════════════
# 메인 창
# ══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.settings = QSettings("BSD", "NaverLandGUI")
        self.worker = None
        self.warmup = None
        self._t0 = None
        self._last_dir = self.settings.value("last_dir", os.path.expanduser("~"))

        self.setWindowTitle("BSD · 네이버 부동산 매물 조회기")
        if os.path.exists(ICON):
            self.setWindowIcon(QIcon(ICON))
        self.resize(1320, 860)
        self.setMinimumSize(1080, 700)

        self._build()
        self._restore()
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._update_elapsed)

        QTimer.singleShot(80, self._check_chrome_state)

    # ── 화면 구성 ───────────────────────────────────────────
    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._sidebar())
        outer.addWidget(self._content(), 1)

        self._statusbar()
        self._shortcuts()

    # ── 사이드바 ────────────────────────────────────────────
    def _sidebar(self):
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(238)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(0)

        # 로고
        logo = QLabel()
        if os.path.exists(LOGO):
            pm = QPixmap(LOGO)
            ratio = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
            pm = pm.scaledToHeight(int(30 * max(ratio, 1.0)),
                                   Qt.SmoothTransformation)
            pm.setDevicePixelRatio(max(ratio, 1.0))
            logo.setPixmap(pm)
        else:
            logo.setText("BSD")
        logo.setContentsMargins(2, 0, 0, 0)
        lay.addWidget(logo)
        lay.addSpacing(8)
        sub = label("네이버 부동산 매물 조회기", "BrandSub")
        sub.setContentsMargins(3, 0, 0, 0)
        lay.addWidget(sub)
        lay.addSpacing(22)

        lay.addWidget(label("검색 방식", "NavLabel"))
        lay.addSpacing(8)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for i, (key, name, hint) in enumerate(MODES):
            b = QPushButton("  " + name)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(hint)
            b.setChecked(i == 0)
            self.nav_group.addButton(b, i)
            lay.addWidget(b)
            lay.addSpacing(3)
        self.nav_group.idClicked.connect(self._switch_mode)

        lay.addStretch(1)

        # 설정
        lay.addWidget(label("설정", "NavLabel"))
        lay.addSpacing(9)
        opt = QFrame()
        opt.setObjectName("SubCard")
        ol = QVBoxLayout(opt)
        ol.setContentsMargins(12, 11, 12, 11)
        ol.setSpacing(9)

        self.chk_headless = QCheckBox("크롬 창 숨김")
        self.chk_headless.setToolTip("차단될 수 있어 권장하지 않습니다.")
        ol.addWidget(self.chk_headless)

        drow = QHBoxLayout()
        drow.setSpacing(8)
        dl = label("요청 간격", "FieldLabel")
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.5, 5.0)
        self.spin_delay.setSingleStep(0.1)
        self.spin_delay.setValue(0.8)
        self.spin_delay.setSuffix(" 초")
        self.spin_delay.setFixedWidth(88)
        self.spin_delay.setToolTip("줄이면 429(요청 과다)로 막힐 수 있습니다.")
        drow.addWidget(dl)
        drow.addStretch(1)
        drow.addWidget(self.spin_delay)
        ol.addLayout(drow)
        lay.addWidget(opt)

        lay.addSpacing(12)
        lay.addWidget(label("브라우저", "NavLabel"))
        lay.addSpacing(9)
        self.dot = StatusDot()
        lay.addWidget(self.dot)
        lay.addSpacing(8)
        self.btn_warm = QPushButton("크롬 미리 띄우기")
        self.btn_warm.setObjectName("Ghost")
        self.btn_warm.setCursor(Qt.PointingHandCursor)
        self.btn_warm.clicked.connect(self._warm_chrome)
        lay.addWidget(self.btn_warm)

        return bar

    # ── 본문 ────────────────────────────────────────────────
    def _content(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(22, 20, 22, 14)
        lay.setSpacing(14)

        # 헤더
        head = QHBoxLayout()
        head.setSpacing(12)
        tbox = QVBoxLayout()
        tbox.setSpacing(3)
        self.lb_title = label(MODES[0][1], "PageTitle")
        self.lb_sub = label(MODES[0][2], "PageSub")
        tbox.addWidget(self.lb_title)
        tbox.addWidget(self.lb_sub)
        head.addLayout(tbox)
        head.addStretch(1)

        self.btn_stop = QPushButton("중지")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        head.addWidget(self.btn_stop)

        self.btn_run = QPushButton("검색 시작")
        self.btn_run.setObjectName("Primary")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setMinimumWidth(120)
        self.btn_run.setToolTip("Ctrl+Enter")
        self.btn_run.clicked.connect(self._start)
        head.addWidget(self.btn_run)
        lay.addLayout(head)

        # 조건 카드
        lay.addWidget(self._params_card())

        # 통계
        lay.addLayout(self._stats_row())

        # 결과
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.addWidget(self._results())
        splitter.addWidget(self._log_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([600, 150])
        self.splitter = splitter
        lay.addWidget(splitter, 1)

        return page

    def _params_card(self):
        card = Card()
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(label("검색 조건", "CardTitle"))
        top.addStretch(1)
        self.lb_hint = label("", "CardHint")
        top.addWidget(self.lb_hint)
        card.lay.addLayout(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._form_region())
        self.stack.addWidget(self._form_complex())
        self.stack.addWidget(self._form_info())
        self.stack.addWidget(self._form_area())
        card.lay.addWidget(self.stack)
        return card

    # 지역 검색
    def _form_region(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(13)

        r1 = QHBoxLayout()
        r1.setSpacing(12)
        self.ed_region = QLineEdit()
        self.ed_region.setPlaceholderText("서울시 양천구 신정동")
        self.ed_region.returnPressed.connect(self._start)
        r1.addWidget(field("지역", self.ed_region), 1)

        self.spin_span = QDoubleSpinBox()
        self.spin_span.setRange(0.002, 0.060)
        self.spin_span.setDecimals(3)
        self.spin_span.setSingleStep(0.002)
        self.spin_span.setValue(0.013)
        self.spin_span.setToolTip("중심에서 좌우로 잡을 경도 폭. 0.013 ≈ 1.2km")
        self.spin_span.valueChanged.connect(self._update_span_hint)
        r1.addWidget(field("검색 반경 (경도 폭)", self.spin_span, 156))

        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 1000)
        self.spin_limit.setValue(200)
        self.spin_limit.setToolTip("확인할 단지 수 상한")
        r1.addWidget(field("단지 상한", self.spin_limit, 110))
        lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(18)
        self.chips_trade = ChipGroup(TRADES, {"A1"})
        r2.addWidget(field("거래유형", self.chips_trade))
        self.chips_estate = ChipGroup(ESTATES, {"A01"})
        r2.addWidget(field("매물종류", self.chips_estate))
        r2.addStretch(1)
        self.chk_articles = QCheckBox("매물까지 수집")
        self.chk_articles.setChecked(True)
        self.chk_articles.setToolTip("끄면 단지 목록만 빠르게 확인합니다.")
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addSpacing(19)
        wl.addWidget(self.chk_articles)
        r2.addWidget(wrap)
        lay.addLayout(r2)
        return w

    # 단지 매물
    def _form_complex(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(13)
        r1 = QHBoxLayout()
        r1.setSpacing(18)
        self.ed_complex = QLineEdit()
        self.ed_complex.setPlaceholderText("8742")
        self.ed_complex.returnPressed.connect(self._start)
        r1.addWidget(field("단지번호", self.ed_complex, 200))
        self.chips_trade2 = ChipGroup(TRADES, {"A1"})
        r1.addWidget(field("거래유형", self.chips_trade2))
        r1.addStretch(1)
        lay.addLayout(r1)
        lay.addWidget(label(
            "네이버 부동산에서 단지를 열면 주소 끝에 붙는 숫자입니다.  "
            "…/complexes/8742?tab=article → 8742", "CardHint"))
        return w

    # 단지 정보
    def _form_info(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(13)
        r1 = QHBoxLayout()
        self.ed_info = QLineEdit()
        self.ed_info.setPlaceholderText("8742")
        self.ed_info.returnPressed.connect(self._start)
        r1.addWidget(field("단지번호", self.ed_info, 200))
        r1.addStretch(1)
        lay.addLayout(r1)
        lay.addWidget(label(
            "이름·주소·세대수·준공연도와 매매/전세/월세 매물 건수를 한 번에 확인합니다.",
            "CardHint"))
        return w

    # 지도 영역
    def _form_area(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(13)

        def coord(val, lon):
            s = QDoubleSpinBox()
            s.setRange(120.0, 140.0) if lon else s.setRange(30.0, 45.0)
            s.setDecimals(5)
            s.setSingleStep(0.005)
            s.setValue(val)
            return s

        r1 = QHBoxLayout()
        r1.setSpacing(12)
        self.sp_left = coord(126.84300, True)
        self.sp_right = coord(126.87900, True)
        self.sp_bottom = coord(37.50300, False)
        self.sp_top = coord(37.53300, False)
        r1.addWidget(field("좌 (경도)", self.sp_left, 132))
        r1.addWidget(field("우 (경도)", self.sp_right, 132))
        r1.addWidget(field("하 (위도)", self.sp_bottom, 132))
        r1.addWidget(field("상 (위도)", self.sp_top, 132))
        self.ed_filter_word = QLineEdit()
        self.ed_filter_word.setPlaceholderText("신정동")
        r1.addWidget(field("주소 필터 (선택)", self.ed_filter_word), 1)
        self.spin_limit2 = QSpinBox()
        self.spin_limit2.setRange(1, 1000)
        self.spin_limit2.setValue(200)
        r1.addWidget(field("단지 상한", self.spin_limit2, 110))
        lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(18)
        self.chips_trade3 = ChipGroup(TRADES, {"A1"})
        r2.addWidget(field("거래유형", self.chips_trade3))
        self.chips_estate3 = ChipGroup(ESTATES, {"A01"})
        r2.addWidget(field("매물종류", self.chips_estate3))
        r2.addStretch(1)
        self.chk_articles3 = QCheckBox("매물까지 수집")
        self.chk_articles3.setChecked(True)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addSpacing(19)
        wl.addWidget(self.chk_articles3)
        r2.addWidget(wrap)
        lay.addLayout(r2)
        return w

    # ── 통계 ────────────────────────────────────────────────
    def _stats_row(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        self.stat_count = StatChip("매물 건수")
        self.stat_low = StatChip("최저가")
        self.stat_mid = StatChip("중위가")
        self.stat_high = StatChip("최고가")
        self.stat_move = StatChip("호가 변동")
        for s in (self.stat_count, self.stat_low, self.stat_mid,
                  self.stat_high, self.stat_move):
            s.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(s)
        return row

    # ── 결과 표 ─────────────────────────────────────────────
    def _results(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.ed_search = QLineEdit()
        self.ed_search.setObjectName("SearchBox")
        self.ed_search.setPlaceholderText("표에서 찾기  (Ctrl+F)")
        self.ed_search.setToolTip("단지명·층·향·중개사·특징 등 모든 칸을 훑습니다.")
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.setMinimumWidth(250)
        self.ed_search.setMaximumWidth(320)
        self.ed_search.textChanged.connect(self._filter_changed)
        bar.addWidget(self.ed_search)

        self.lb_count = label("결과 없음", "CardHint")
        bar.addWidget(self.lb_count)
        bar.addStretch(1)

        self.btn_copy = QPushButton("선택 복사")
        self.btn_copy.setObjectName("Ghost")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setToolTip("Ctrl+C")
        self.btn_copy.clicked.connect(self._copy_selection)
        bar.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("결과 비우기")
        self.btn_clear.setObjectName("Ghost")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_results)
        bar.addWidget(self.btn_clear)

        self.btn_csv = QPushButton("CSV 저장")
        self.btn_csv.setCursor(Qt.PointingHandCursor)
        self.btn_csv.setToolTip("Ctrl+S — 지금 보이는 행을 저장합니다.")
        self.btn_csv.clicked.connect(self._save_csv)
        bar.addWidget(self.btn_csv)
        lay.addLayout(bar)

        self.tabs = QTabWidget()
        self.m_articles = ArticleModel(self)
        self.m_complexes = ComplexModel(self)
        self.t_articles = ResultTable(self.m_articles)
        self.t_complexes = ResultTable(self.m_complexes)

        self.t_articles.customContextMenuRequested.connect(self._menu_articles)
        self.t_complexes.customContextMenuRequested.connect(self._menu_complexes)
        self.t_complexes.doubleClicked.connect(self._open_complex_from_row)

        self.tabs.addTab(self.t_articles, "매물")
        self.tabs.addTab(self.t_complexes, "단지")
        self.tabs.currentChanged.connect(self._tab_changed)
        lay.addWidget(self.tabs, 1)
        return box

    # ── 로그 ────────────────────────────────────────────────
    def _log_panel(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        bar = QHBoxLayout()
        bar.addWidget(label("진행 기록", "CardHint"))
        bar.addStretch(1)
        b = QPushButton("지우기")
        b.setObjectName("LinkBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.log.clear())
        bar.addWidget(b)
        lay.addLayout(bar)

        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setMinimumHeight(80)
        lay.addWidget(self.log, 1)
        return box

    # ── 상태 표시줄 ─────────────────────────────────────────
    def _statusbar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)   # 창 테두리로 크기를 조절합니다
        self.pbar = QProgressBar()
        self.pbar.setFixedWidth(170)
        self.pbar.setTextVisible(False)
        self.pbar.setVisible(False)
        self.lb_status = QLabel("준비됨")
        self.lb_elapsed = QLabel("")
        self.lb_elapsed.setStyleSheet("color: %s;" % theme.TEXT_MUTE)
        sb.setContentsMargins(10, 0, 12, 4)
        sb.addWidget(self.lb_status, 1)
        sb.addPermanentWidget(self.lb_elapsed)
        sb.addPermanentWidget(self.pbar)

    def _shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Return"), self, self._start)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._start)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_csv)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.ed_search.setFocus())
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy_selection)
        QShortcut(QKeySequence("Escape"), self, self._stop)

    # ══════════════════════════════════════════════════════
    # 동작
    # ══════════════════════════════════════════════════════
    def _switch_mode(self, idx):
        self.stack.setCurrentIndex(idx)
        self.lb_title.setText(MODES[idx][1])
        self.lb_sub.setText(MODES[idx][2])
        self._update_span_hint()

    def _update_span_hint(self):
        if self.stack.currentIndex() == 0:
            km = self.spin_span.value() * 88
            self.lb_hint.setText("가로 약 %.1fkm × 세로 약 %.1fkm 범위를 훑습니다" %
                                 (km * 2, km * 1.6))
        else:
            self.lb_hint.setText("")

    def mode(self):
        return MODES[self.nav_group.checkedId()][0]

    def _params(self):
        m = self.mode()
        p = {"mode": m,
             "headless": self.chk_headless.isChecked(),
             "delay": self.spin_delay.value()}

        if m == "region":
            q = self.ed_region.text().strip()
            if not q:
                raise ValueError("지역을 입력해 주세요. 예) 서울시 양천구 신정동")
            p.update(query=q, span=self.spin_span.value(),
                     limit=self.spin_limit.value(),
                     trades=self.chips_trade.values(),
                     estates=self.chips_estate.values(),
                     articles=self.chk_articles.isChecked())
        elif m == "complex":
            no = self.ed_complex.text().strip()
            if not no.isdigit():
                raise ValueError("단지번호는 숫자입니다. 예) 8742")
            p.update(complex_number=no, trades=self.chips_trade2.values())
        elif m == "info":
            no = self.ed_info.text().strip()
            if not no.isdigit():
                raise ValueError("단지번호는 숫자입니다. 예) 8742")
            p.update(complex_number=no)
        else:
            left, right = self.sp_left.value(), self.sp_right.value()
            bottom, top = self.sp_bottom.value(), self.sp_top.value()
            if left >= right or bottom >= top:
                raise ValueError("좌 < 우, 하 < 상 이 되도록 좌표를 넣어 주세요.")
            p.update(left=left, right=right, bottom=bottom, top=top,
                     filter=self.ed_filter_word.text().strip(),
                     limit=self.spin_limit2.value(),
                     trades=self.chips_trade3.values(),
                     estates=self.chips_estate3.values(),
                     articles=self.chk_articles3.isChecked())

        if m in ("region", "complex", "area") and not p.get("trades"):
            raise ValueError("거래유형을 하나 이상 골라 주세요.")
        if m in ("region", "area") and not p.get("estates"):
            raise ValueError("매물종류를 하나 이상 골라 주세요.")
        return p

    def _start(self):
        if self.worker and self.worker.isRunning():
            return
        try:
            params = self._params()
        except ValueError as e:
            self._warn(str(e))
            return

        self.m_articles.clear()
        self.m_complexes.clear()
        self._refresh_stats()
        self._append_log("── %s · %s 검색 시작" % (
            datetime.now().strftime("%H:%M:%S"), MODES[self.nav_group.checkedId()][1]))

        self.worker = SearchWorker(params, self)
        self.worker.log.connect(self._append_log)
        self.worker.status.connect(self._set_status)
        self.worker.progress.connect(self._set_progress)
        self.worker.complexesReady.connect(self._on_complexes)
        self.worker.articlesBatch.connect(self._on_articles)
        self.worker.infoReady.connect(self._on_info)
        self.worker.done.connect(self._on_done)
        self.worker.start()

        self._set_busy(True)
        self._t0 = datetime.now()
        self._tick.start(500)

    def _stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.requestInterruption()
            self.btn_stop.setEnabled(False)
            self._set_status("중지하는 중…")

    def _set_busy(self, busy):
        self.btn_run.setEnabled(not busy)
        self.btn_run.setText("수집 중…" if busy else "검색 시작")
        self.btn_stop.setEnabled(busy)
        self.stack.setEnabled(not busy)
        self.btn_warm.setEnabled(not busy)
        self.pbar.setVisible(busy)
        self.dot.set("수집 중" if busy else "대기 중",
                     theme.ACCENT if busy else theme.TEXT_MUTE)
        if not busy:
            self._tick.stop()
            self.lb_elapsed.setText("")

    def _update_elapsed(self):
        if self._t0:
            s = int((datetime.now() - self._t0).total_seconds())
            self.lb_elapsed.setText("%d:%02d 경과" % (s // 60, s % 60))

    # ── 워커 신호 ───────────────────────────────────────────
    def _append_log(self, text):
        self.log.appendPlainText(text)

    def _set_status(self, text):
        self.lb_status.setText(text)

    def _set_progress(self, cur, total):
        if total <= 0:
            self.pbar.setRange(0, 0)          # 불확정
        else:
            self.pbar.setRange(0, total)
            self.pbar.setValue(cur)

    def _on_complexes(self, rows):
        self.m_complexes.append(rows)
        self._refresh_counts()
        if not self.m_articles.rows:
            self.tabs.setCurrentIndex(1)

    def _on_articles(self, rows):
        added = self.m_articles.append(rows)
        if added and self.tabs.currentIndex() != 0 and self.m_articles.rowCount() == added:
            self.tabs.setCurrentIndex(0)
        self._refresh_stats()

    def _on_info(self, info):
        self._append_log(
            "· %s\n  주소   %s %s\n  도로명 %s\n  세대수 %s · 준공 %s\n"
            "  매물   매매 %s · 전세 %s · 월세 %s" % (
                info["name"], info["sector"], info["jibun"], info["road"],
                info["households"], info["year"],
                info["deal"], info["jeonse"], info["wolse"]))

    def _on_done(self, ok, message):
        self._set_busy(False)
        self.dot.set("연결됨" if nl.cdp_alive() else "대기 중",
                     theme.GREEN if nl.cdp_alive() else theme.TEXT_MUTE)
        n_a, n_c = len(self.m_articles.rows), len(self.m_complexes.rows)
        if ok:
            msg = "완료 — 단지 %d개 · 매물 %d건" % (n_c, n_a)
            self._set_status(msg)
            self._append_log("✔ " + msg)
        else:
            self._set_status(message.splitlines()[0])
            self._append_log("✖ " + message.replace("\n", " "))
            if "중지" not in message:
                self._warn(message, title="검색을 마치지 못했습니다")
        self._refresh_stats()

    # ── 결과 표 갱신 ────────────────────────────────────────
    def _refresh_counts(self):
        t = self._table()
        shown, total = t.proxy.rowCount(), t.src.rowCount()
        name = "매물" if self.tabs.currentIndex() == 0 else "단지"
        if total == 0:
            self.lb_count.setText("결과 없음")
        elif shown == total:
            self.lb_count.setText("%s %s건" % (name, format(total, ",")))
        else:
            self.lb_count.setText("%s %s / %s건" % (
                name, format(shown, ","), format(total, ",")))

    def _refresh_stats(self):
        rows = self.m_articles.rows
        prices = sorted(r["_원"] for r in rows if r["_원"])
        self.stat_count.set(format(len(rows), ",") + "건" if rows else "—")
        if prices:
            self.stat_low.set(nl.money(prices[0]))
            self.stat_mid.set(nl.money(prices[len(prices) // 2]))
            self.stat_high.set(nl.money(prices[-1]))
        else:
            for s in (self.stat_low, self.stat_mid, self.stat_high):
                s.set("—")
        down = sum(1 for r in rows if r["호가변동"].startswith("▼"))
        up = sum(1 for r in rows if r["호가변동"].startswith("▲"))
        if down or up:
            self.stat_move.set("▼%d  ▲%d" % (down, up),
                               theme.BLUE if down >= up else theme.ACCENT)
        else:
            self.stat_move.set("—")
        self._refresh_counts()

    def _table(self):
        return self.t_articles if self.tabs.currentIndex() == 0 else self.t_complexes

    def _tab_changed(self, *_):
        self._filter_changed(self.ed_search.text())

    def _filter_changed(self, text):
        self.t_articles.proxy.set_needle(text)
        self.t_complexes.proxy.set_needle(text)
        self._refresh_counts()

    def _clear_results(self):
        self.m_articles.clear()
        self.m_complexes.clear()
        self._refresh_stats()
        self._set_status("결과를 비웠습니다.")

    # ── 내보내기 / 복사 ─────────────────────────────────────
    def _rows_as_text(self, table, rows):
        cols = table.src.columns
        out = ["\t".join(cols)]
        for r in rows:
            out.append("\t".join(str(table.src.display(r, c) or "") for c in cols))
        return "\n".join(out)

    def _copy_selection(self):
        t = self._table()
        rows = t.selected_rows() or t.proxy.visible_rows()
        if not rows:
            self._set_status("복사할 행이 없습니다.")
            return
        QGuiApplication.clipboard().setText(self._rows_as_text(t, rows))
        self._set_status("%d행을 클립보드에 복사했습니다." % len(rows))

    def _save_csv(self):
        t = self._table()
        rows = t.proxy.visible_rows()
        if not rows:
            self._warn("저장할 결과가 없습니다.")
            return
        kind = "매물" if self.tabs.currentIndex() == 0 else "단지"
        base = "%s_%s.csv" % (kind, datetime.now().strftime("%Y%m%d_%H%M"))
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV 저장", os.path.join(self._last_dir, base),
            "CSV 파일 (*.csv)")
        if not path:
            return
        cols = t.src.columns
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow([t.src.display(r, c) for c in cols])
        except OSError as e:
            self._warn("저장하지 못했습니다.\n%s" % e)
            return
        self._last_dir = os.path.dirname(path)
        self.settings.setValue("last_dir", self._last_dir)
        self._set_status("CSV 저장 완료 — %s (%d건)" % (path, len(rows)))
        self._append_log("CSV 저장: %s (%d건)" % (path, len(rows)))

    # ── 표 맥락 메뉴 ────────────────────────────────────────
    def _menu_articles(self, pos):
        row = self.t_articles.row_under(pos)
        if not row:
            return
        m = QMenu(self)
        no = row.get("_단지번호")
        if no:
            a = QAction("네이버에서 '%s' 열기" % row.get("단지", ""), m)
            a.triggered.connect(lambda: self._open_naver(no))
            m.addAction(a)
            b = QAction("이 단지 매물만 다시 조회", m)
            b.triggered.connect(lambda: self._goto_complex(no))
            m.addAction(b)
            m.addSeparator()
        c = QAction("행 복사", m)
        c.triggered.connect(self._copy_selection)
        m.addAction(c)
        d = QAction("매물번호 복사", m)
        d.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(str(row.get("매물번호", ""))))
        m.addAction(d)
        m.exec(self.t_articles.viewport().mapToGlobal(pos))

    def _menu_complexes(self, pos):
        row = self.t_complexes.row_under(pos)
        if not row:
            return
        m = QMenu(self)
        no = row.get("complexNumber")
        a = QAction("네이버에서 열기", m)
        a.triggered.connect(lambda: self._open_naver(no, row.get("url")))
        m.addAction(a)
        b = QAction("이 단지 매물 조회", m)
        b.triggered.connect(lambda: self._goto_complex(no))
        m.addAction(b)
        m.addSeparator()
        c = QAction("행 복사", m)
        c.triggered.connect(self._copy_selection)
        m.addAction(c)
        d = QAction("단지번호 복사", m)
        d.triggered.connect(lambda: QGuiApplication.clipboard().setText(str(no)))
        m.addAction(d)
        m.exec(self.t_complexes.viewport().mapToGlobal(pos))

    def _open_complex_from_row(self, index):
        row = self.m_complexes.row_at(
            self.t_complexes.proxy.mapToSource(index).row())
        self._goto_complex(row.get("complexNumber"))

    def _goto_complex(self, no):
        if not no:
            return
        self.nav_group.button(1).setChecked(True)
        self._switch_mode(1)
        self.ed_complex.setText(str(no))
        self.ed_complex.setFocus()
        self._set_status("단지 %s — 검색 시작을 누르면 매물을 가져옵니다." % no)

    def _open_naver(self, no, url=None):
        target = url or ("https://fin.land.naver.com/complexes/%s?tab=article" % no)
        if not str(target).startswith("http"):
            target = "https://fin.land.naver.com/complexes/%s?tab=article" % no
        QDesktopServices.openUrl(QUrl(target))

    # ── 크롬 상태 ───────────────────────────────────────────
    def _check_chrome_state(self):
        alive = nl.cdp_alive()
        self.dot.set("연결됨" if alive else "대기 중",
                     theme.GREEN if alive else theme.TEXT_MUTE)

    def _warm_chrome(self):
        if self.warmup and self.warmup.isRunning():
            return
        self.btn_warm.setEnabled(False)
        self.dot.set("크롬 여는 중…", theme.AMBER)
        self.warmup = ChromeWarmupWorker(self.chk_headless.isChecked(), self)
        self.warmup.done.connect(self._warm_done)
        self.warmup.start()

    def _warm_done(self, ok, msg):
        self.btn_warm.setEnabled(True)
        self._append_log(("· " if ok else "✖ ") + msg)
        self._set_status(msg.splitlines()[0])
        self.dot.set("연결됨" if ok else "대기 중",
                     theme.GREEN if ok else theme.TEXT_MUTE)
        if not ok:
            self._warn(msg, title="크롬을 띄우지 못했습니다")

    # ── 기타 ────────────────────────────────────────────────
    def _warn(self, text, title="확인해 주세요"):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(text)
        box.exec()

    def _restore(self):
        s = self.settings
        g = s.value("geometry")
        if g:
            self.restoreGeometry(g)
        idx = int(s.value("mode", 0))
        if 0 <= idx < len(MODES):
            self.nav_group.button(idx).setChecked(True)
            self._switch_mode(idx)
        self.ed_region.setText(s.value("region", ""))
        self.ed_complex.setText(s.value("complex", ""))
        self.ed_info.setText(s.value("info", ""))
        self.spin_span.setValue(float(s.value("span", 0.013)))
        self.spin_delay.setValue(float(s.value("delay", 0.8)))
        self.spin_limit.setValue(int(s.value("limit", 200)))
        self.chk_headless.setChecked(s.value("headless", "false") == "true")
        tr = _as_list(s.value("trades"))
        if tr:
            self.chips_trade.set_values(tr)
            self.chips_trade2.set_values(tr)
            self.chips_trade3.set_values(tr)
        es = _as_list(s.value("estates"))
        if es:
            self.chips_estate.set_values(es)
            self.chips_estate3.set_values(es)
        self._update_span_hint()

    def _save_settings(self):
        s = self.settings
        s.setValue("geometry", self.saveGeometry())
        s.setValue("mode", self.nav_group.checkedId())
        s.setValue("region", self.ed_region.text())
        s.setValue("complex", self.ed_complex.text())
        s.setValue("info", self.ed_info.text())
        s.setValue("span", self.spin_span.value())
        s.setValue("delay", self.spin_delay.value())
        s.setValue("limit", self.spin_limit.value())
        s.setValue("headless", "true" if self.chk_headless.isChecked() else "false")
        s.setValue("trades", self.chips_trade.values())
        s.setValue("estates", self.chips_estate.values())

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            ask = QMessageBox(self)
            ask.setIcon(QMessageBox.Question)
            ask.setWindowTitle("수집 중입니다")
            ask.setText("아직 매물을 가져오는 중입니다. 중지하고 종료할까요?")
            ask.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            ask.setDefaultButton(QMessageBox.No)
            if ask.exec() != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.requestInterruption()
            self.worker.wait(8000)
        self._save_settings()
        event.accept()


# ══════════════════════════════════════════════════════════════
def apply_dark_titlebar(win):
    """윈도우 11/10 제목표시줄까지 어둡게."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(win.winId())
        for attr in (20, 19):        # DWMWA_USE_IMMERSIVE_DARK_MODE
            val = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd), ctypes.c_int(attr),
                ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def _log_dir():
    """실행파일(.exe) 옆, 개발 중이면 소스 폴더."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return APP_DIR


def _install_crash_log():
    """--windowed 로 묶은 exe 는 오류가 화면에 안 뜨므로 파일로 남긴다."""
    import traceback

    # windowed 모드에서는 stdout/stderr 가 None 이라 print 한 줄에도 죽는다
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    path = os.path.join(_log_dir(), "error.log")

    def hook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n===== %s =====\n%s" %
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text))
        except OSError:
            pass
        try:
            from PySide6.QtWidgets import QMessageBox
            box = QMessageBox()
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("오류가 났습니다")
            box.setText("프로그램에 문제가 생겼습니다.\n"
                        "자세한 내용은 error.log 파일을 봐 주세요.")
            box.setDetailedText(text)
            box.exec()
        except Exception:
            pass

    sys.excepthook = hook


def main():
    _install_crash_log()

    if "--selftest" in sys.argv:
        import selftest
        sys.exit(selftest.run(_log_dir(), ASSETS))

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "bsd.naverland.gui")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("네이버 부동산 매물 조회기")
    app.setOrganizationName("BSD")
    if os.path.exists(ICON):
        app.setWindowIcon(QIcon(ICON))

    ui_font = theme.pick_font(theme.FONT_STACK)
    mono_font = theme.pick_font(theme.MONO_STACK, "Consolas")
    app.setFont(QFont(ui_font, 10))
    theme.apply_palette(app)
    app.setStyleSheet(theme.stylesheet(ui_font, mono_font))

    win = MainWindow()
    win.show()
    apply_dark_titlebar(win)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
