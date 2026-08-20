# -*- coding: utf-8 -*-
"""models.py — 매물/단지 표 모델. 숫자 컬럼은 값 기준으로 정렬된다."""

from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
                            Qt)
from PySide6.QtGui import QColor

import theme

SORT_ROLE = Qt.UserRole + 1
ROW_ROLE = Qt.UserRole + 2

ARTICLE_COLUMNS = ["단지", "거래유형", "가격", "월세", "동", "공급면적", "전용면적",
                   "층", "향", "호가변동", "관리비", "확인일", "중개사", "특징", "매물번호"]
ARTICLE_WIDTHS = [160, 62, 118, 90, 66, 88, 88, 74, 52, 92, 84, 96, 150, 300, 96]
ARTICLE_NUMERIC = {"가격": "_원", "월세": "_월세원", "관리비": "_관리비원"}
ARTICLE_RIGHT = {"가격", "월세", "관리비", "호가변동"}

COMPLEX_COLUMNS = ["단지명", "주소", "준공", "세대수", "매매", "전세", "월세", "단지번호"]
COMPLEX_WIDTHS = [200, 260, 70, 80, 62, 62, 62, 90]
COMPLEX_KEYS = ["name", "sector", "year", "households", "deal", "jeonse",
                "wolse", "complexNumber"]
COMPLEX_NUMERIC = {"준공", "세대수", "매매", "전세", "월세", "단지번호"}
COMPLEX_RIGHT = COMPLEX_NUMERIC


class BaseTableModel(QAbstractTableModel):
    columns = []
    widths = []
    right_align = set()
    dedupe_key = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self._seen = set()

    # ── Qt 규약 ─────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 1)
        if orientation == Qt.Vertical and role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        col = self.columns[index.column()]

        if role == Qt.DisplayRole:
            return self.display(row, col)
        if role == SORT_ROLE:
            return self.sort_key(row, col)
        if role == ROW_ROLE:
            return row
        if role == Qt.TextAlignmentRole:
            if col in self.right_align:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            return self.tooltip(row, col)
        if role == Qt.ForegroundRole:
            return self.foreground(row, col)
        return None

    # ── 하위 클래스에서 채움 ────────────────────────────────
    def display(self, row, col):
        return ""

    def sort_key(self, row, col):
        return self.display(row, col)

    def tooltip(self, row, col):
        text = str(self.display(row, col) or "")
        return text if len(text) > 18 else None

    def foreground(self, row, col):
        return None

    # ── 데이터 조작 ─────────────────────────────────────────
    def append(self, new_rows):
        fresh = []
        for r in new_rows:
            if self.dedupe_key:
                k = r.get(self.dedupe_key)
                if k in self._seen:
                    continue
                self._seen.add(k)
            fresh.append(r)
        if not fresh:
            return 0
        first = len(self.rows)
        self.beginInsertRows(QModelIndex(), first, first + len(fresh) - 1)
        self.rows.extend(fresh)
        self.endInsertRows()
        return len(fresh)

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self._seen = set()
        self.endResetModel()

    def row_at(self, r):
        return self.rows[r]


class ArticleModel(BaseTableModel):
    columns = ARTICLE_COLUMNS
    widths = ARTICLE_WIDTHS
    right_align = ARTICLE_RIGHT
    dedupe_key = "매물번호"

    def display(self, row, col):
        return row.get(col, "")

    def sort_key(self, row, col):
        key = ARTICLE_NUMERIC.get(col)
        if key:
            return row.get(key, 0)
        if col == "호가변동":
            text = row.get(col, "")
            if not text:
                return 0
            return -1 if text.startswith("▼") else 1
        if col == "전용면적" or col == "공급면적":
            try:
                return float(str(row.get(col, "")).replace("㎡", "").split("/")[0])
            except ValueError:
                return 0.0
        return str(row.get(col, ""))

    def foreground(self, row, col):
        if col == "호가변동":
            text = row.get(col, "")
            if text.startswith("▼"):
                return QColor(theme.BLUE)
            if text.startswith("▲"):
                return QColor(theme.ACCENT)
        elif col == "가격":
            return QColor(theme.TEXT)
        elif col in ("특징", "중개사", "확인일"):
            return QColor(theme.TEXT_DIM)
        return None

    def tooltip(self, row, col):
        if col == "특징":
            return row.get("특징") or None
        if col == "단지":
            return "%s (단지번호 %s)" % (row.get("단지"), row.get("_단지번호", "-"))
        text = str(row.get(col, ""))
        return text if len(text) > 18 else None


class ComplexModel(BaseTableModel):
    columns = COMPLEX_COLUMNS
    widths = COMPLEX_WIDTHS
    right_align = COMPLEX_RIGHT
    dedupe_key = "complexNumber"

    def display(self, row, col):
        v = row.get(COMPLEX_KEYS[self.columns.index(col)], "")
        return "" if v is None else str(v)

    def sort_key(self, row, col):
        v = row.get(COMPLEX_KEYS[self.columns.index(col)], "")
        if col in COMPLEX_NUMERIC:
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0
        return str(v or "")

    def foreground(self, row, col):
        if col == "주소":
            return QColor(theme.TEXT_DIM)
        if col in ("매매", "전세", "월세"):
            key = COMPLEX_KEYS[self.columns.index(col)]
            return QColor(theme.TEXT) if row.get(key) else QColor(theme.TEXT_MUTE)
        return None


class FilterProxy(QSortFilterProxyModel):
    """모든 열을 훑는 부분 일치 필터 + 값 기준 정렬."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)
        self._needle = ""

    def set_needle(self, text):
        self._needle = (text or "").strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, parent):
        if not self._needle:
            return True
        m = self.sourceModel()
        for c in range(m.columnCount()):
            v = m.data(m.index(source_row, c), Qt.DisplayRole)
            if v and self._needle in str(v).lower():
                return True
        return False

    def visible_rows(self):
        m = self.sourceModel()
        return [m.row_at(self.mapToSource(self.index(r, 0)).row())
                for r in range(self.rowCount())]
