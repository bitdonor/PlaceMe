import os
from typing import List, Optional, Tuple
import pandas as pd

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QFileDialog, QMessageBox, QWidget, QScrollArea,
)

from core.validator import ValidationIssue, normalize_df, find_issues
from ui.theme import P, btn_style, ghost_btn_style


_KIND_TITLE = {
    'full_dup':       'Полные дубликаты строк',
    'dup_name':       'Совпадение ФИО',
    'similar_name':   'Похожие ФИО',
    'similar_school': 'Похожие названия школ',
    'missing':        'Пропущенные значения',
}

_COL_ORDER   = ['Город', 'ФИО ученика', 'Образовательная организация', 'Класс', 'Буква класса']
_COL_DISPLAY = {
    'Город':                        'Город',
    'ФИО ученика':                  'ФИО',
    'Образовательная организация':  'Школа',
    'Класс':                        'Класс',
    'Буква класса':                 'Буква',
}

_COLOR_STRIPE = QColor(235, 244, 255)   # голубоватый — нечётные строки / группа Б


_COLOR_ERR    = QColor(255, 228, 228)   # красный — пустые ячейки


class ValidatorDialog(QDialog):
    """
    Модальный диалог предварительной проверки списка участников.
    После exec() доступны:
      .result_df   — исправленный DataFrame
      .saved_path  — путь к сохранённому файлу или None
    """

    def __init__(self, parent, df: pd.DataFrame, filepath: str):
        super().__init__(parent)
        self.setWindowTitle("Проверка данных")
        self.setModal(True)
        self.resize(820, 600)
        self.setMinimumSize(660, 480)

        self._df = normalize_df(df)
        self._filepath = filepath
        self._issues: List[ValidationIssue] = []
        self._current = 0
        self._applied = 0
        self._skipped = 0

        # История для кнопки «Назад»: (df_snapshot, issue_idx, applied, skipped)
        self._history: List[Tuple[pd.DataFrame, int, int, int]] = []

        self.result_df: pd.DataFrame = self._df
        self.saved_path: Optional[str] = None

        self._build_ui()
        self._run_checks()

    # UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Шапка
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {P['header']};")
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(24, 14, 24, 14)
        hdr_lay.setSpacing(3)
        self._progress_lbl = QLabel()
        self._progress_lbl.setStyleSheet(
            f"color: {P['header_sub']}; font-size: 9pt; background: transparent;"
        )
        hdr_lay.addWidget(self._progress_lbl)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            "color: white; font-size: 13pt; font-weight: bold; background: transparent;"
        )
        hdr_lay.addWidget(self._title_lbl)
        root.addWidget(hdr)

        # Тело
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 16, 24, 12)
        body_lay.setSpacing(10)

        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"background: {P['primary_light']}; border: 1px solid #BEE3F8;"
            f"border-radius: 6px; padding: 10px 14px; color: #1A365D;"
        )
        body_lay.addWidget(self._desc_lbl)

        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        body_lay.addWidget(self._table, stretch=1)

        self._body_spacer = QWidget()
        self._body_spacer.setVisible(False)
        body_lay.addWidget(self._body_spacer, stretch=1)

        # Область кнопок действий (прокручиваемая)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Высота одной кнопки примерно 40px + отступы 6px. 
        # Чтобы было видно ровно "2.5 кнопки", устанавливаем высоту в 104px.
        scroll.setFixedHeight(104)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._actions_inner = QWidget()
        self._actions_inner.setStyleSheet("background: transparent;")
        self._actions_lay = QVBoxLayout(self._actions_inner)
        self._actions_lay.setContentsMargins(0, 4, 0, 0)
        self._actions_lay.setSpacing(6)
        scroll.setWidget(self._actions_inner)
        body_lay.addWidget(scroll)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {P['border']}; max-height: 1px;")
        body_lay.addWidget(sep)

        # Навигация: [← Назад]  [stretch]  [Пропустить (оставить как есть)]
        nav = QHBoxLayout()

        self._back_btn = QPushButton("← Назад")
        self._back_btn.setStyleSheet(ghost_btn_style())
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self._go_back)
        self._back_btn.setEnabled(False)
        nav.addWidget(self._back_btn)

        nav.addStretch()

        self._skip_btn = QPushButton("Пропустить (оставить как есть)")
        self._skip_btn.setStyleSheet(ghost_btn_style())
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.clicked.connect(self._skip)
        nav.addWidget(self._skip_btn)

        body_lay.addLayout(nav)
        root.addWidget(body, stretch=1)

    # Логика

    def _run_checks(self):
        self._issues = find_issues(self._df)
        if not self._issues:
            self._show_summary()
        else:
            self._show_issue(0)

    def _show_issue(self, idx: int):
        self._current = idx
        issue = self._issues[idx]

        # Отфильтровать устаревшие индексы
        issue.indices = [i for i in issue.indices if i in self._df.index]
        if not issue.indices:
            self._advance()
            return

        n = len(self._issues)
        self._progress_lbl.setText(f"Проблема {idx + 1} из {n}")
        self._title_lbl.setText(_KIND_TITLE.get(issue.kind, issue.kind))
        self._skip_btn.setVisible(True)
        self._back_btn.setVisible(True)
        self._back_btn.setEnabled(bool(self._history))
        self._table.setVisible(True)
        self._body_spacer.setVisible(False)
        self._clear_actions()

        dispatch = {
            'full_dup':       self._render_full_dup,
            'dup_name':       self._render_dup_name,
            'similar_name':   self._render_similar_name,
            'similar_school': self._render_similar_school,
            'missing':        self._render_missing,
        }
        dispatch[issue.kind](issue)

    def _show_summary(self):
        self._progress_lbl.setText("Проверка завершена")
        self._title_lbl.setText("Итог проверки")
        self._skip_btn.setVisible(False)
        self._back_btn.setVisible(True)
        self._back_btn.setEnabled(bool(self._history))
        self._clear_actions()
        self._table.setVisible(False)
        self._body_spacer.setVisible(True)
        self._table.setRowCount(0)
        self._table.setColumnCount(0)

        total = len(self._df)
        self._desc_lbl.setText(
            f"Проверка завершена.\n\n"
            f"Найдено проблем: {len(self._issues)}\n"
            f"Применено правок: {self._applied}\n"
            f"Пропущено: {self._skipped}\n\n"
            f"Итого участников после проверки: {total}"
        )

        save_btn = QPushButton("Сохранить исправленный файл (xlsx)")
        save_btn.setStyleSheet(btn_style(P['primary']))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_file)
        self._add_action(save_btn)

        close_btn = QPushButton("Применить без сохранения xlsx")
        close_btn.setStyleSheet(ghost_btn_style())
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._finish)
        self._add_action(close_btn)

    def _finish(self):
        self.result_df = self._df
        self.accept()

    def _save_file(self):
        default_dir = os.path.dirname(self._filepath) if self._filepath else ""
        base = os.path.splitext(os.path.basename(self._filepath))[0] if self._filepath else "участники"
        default_path = os.path.join(default_dir, f"{base}_проверено.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить исправленный файл",
            default_path, "Excel файлы (*.xlsx)",
        )
        if not path:
            return
        try:
            # 1. Сначала сохраняем через pandas (это надежнее для типов данных)
            self._df.to_excel(path, index=False)

            # 2. Затем открываем через openpyxl для наложения стилей
            import openpyxl
            from openpyxl.styles import PatternFill
            from openpyxl.utils import get_column_letter

            wb = openpyxl.load_workbook(path)
            ws = wb.active
            
            error_fill = PatternFill("solid", fgColor="FFC7CE")
            
            # Проходим по всем ячейкам с данными (начиная со 2-й строки)
            for r in range(2, ws.max_row + 1):
                for c in range(1, ws.max_column + 1):
                    cell = ws.cell(row=r, column=c)
                    val = str(cell.value).upper() if cell.value is not None else ""
                    
                    # Проверка на заглушки
                    if val == "НЕИЗВЕСТНО" or val == "-" or val == "0" or val.startswith("УЧАСТНИК"):
                        cell.fill = error_fill

            # Автоширина колонок
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.value:
                        val_str = str(cell.value)
                        actual_len = 0
                        for char in val_str:
                            if ord(char) > 127:
                                actual_len += 1.4
                            else:
                                actual_len += 1
                        max_len = max(max_len, actual_len)
                ws.column_dimensions[col_letter].width = max_len + 2

            wb.save(path)
            self.saved_path = path
            self.result_df = self._df
            QMessageBox.information(self, "Сохранено", f"Файл сохранён:\n{path}")
            self.accept()
        except PermissionError:
            QMessageBox.critical(
                self, "Ошибка доступа",
                f"Не удалось сохранить файл:\n{path}\n\n"
                f"Скорее всего, этот файл открыт в другой программе (например, в Excel).\n"
                f"Закройте или переименуйте файл и попробуйте снова."
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", f"Произошла ошибка:\n{str(e)}")

    # Навигация

    def _push_history(self):
        self._history.append((self._df.copy(), self._current, self._applied, self._skipped))
        self._back_btn.setEnabled(True)

    def _go_back(self):
        if not self._history:
            return
        df_snap, issue_idx, applied, skipped = self._history.pop()
        self._df = df_snap
        self._applied = applied
        self._skipped = skipped
        self._back_btn.setEnabled(bool(self._history))
        self._show_issue(issue_idx)

    def _clear_actions(self):
        while self._actions_lay.count():
            item = self._actions_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_action(self, btn: QPushButton):
        count = self._actions_lay.count()
        if count > 0:
            last = self._actions_lay.itemAt(count - 1)
            if last and last.spacerItem():
                self._actions_lay.takeAt(count - 1)
        self._actions_lay.addWidget(btn)
        self._actions_lay.addStretch()

    def _skip(self):
        """При пропуске 'missing' применяем автозаполнение автоматически"""
        issue = self._issues[self._current]
        if issue.kind == 'missing':
            # Логика автозаполнения (дублируем из _render_missing для простоты)
            from core.validator import _NAME_COL, _SCHOOL_COL, _GRADE_COL, _LETTER_COL, _CITY_COL
            for idx in issue.indices:
                if idx not in self._df.index:
                    continue
                if pd.isna(self._df.at[idx, _NAME_COL]) or not str(self._df.at[idx, _NAME_COL]).strip():
                    self._df.at[idx, _NAME_COL] = f"УЧАСТНИК (СТРОКА {idx + 2})"
                for col in [_SCHOOL_COL, _CITY_COL]:
                    if col in self._df.columns:
                        if pd.isna(self._df.at[idx, col]) or not str(self._df.at[idx, col]).strip():
                            self._df.at[idx, col] = "НЕИЗВЕСТНО"
                if _GRADE_COL in self._df.columns:
                    val = self._df.at[idx, _GRADE_COL]
                    if pd.isna(val) or not str(val).strip() or str(val) == '0':
                        self._df.at[idx, _GRADE_COL] = '0'
                if _LETTER_COL in self._df.columns:
                    val = self._df.at[idx, _LETTER_COL]
                    if pd.isna(val) or not str(val).strip():
                        self._df.at[idx, _LETTER_COL] = "-"
            self._applied += 1 # Считаем это как примененную правку, так как данные изменились
        else:
            self._skipped += 1
        
        self._push_history()
        self._advance()

    def _advance(self):
        nxt = self._current + 1
        if nxt >= len(self._issues):
            self._show_summary()
        else:
            self._show_issue(nxt)

    def _do_action(self, fn):
        self._push_history()
        fn()
        self._applied += 1
        self._advance()

    # Таблица

    def _fill_table(self, df_sub: pd.DataFrame, highlight_empty: bool = False):
        cols = [c for c in _COL_ORDER if c in df_sub.columns]
        self._table.setColumnCount(len(cols) + 1)
        self._table.setHorizontalHeaderLabels(
            ['Строка'] + [_COL_DISPLAY.get(c, c) for c in cols]
        )
        self._table.setRowCount(len(df_sub))
        for r, (idx, row) in enumerate(df_sub.iterrows()):
            row_color = None if highlight_empty else (_COLOR_STRIPE if r % 2 == 0 else None)
            cell0 = QTableWidgetItem(str(int(idx) + 2))
            cell0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if row_color:
                cell0.setBackground(row_color)
            self._table.setItem(r, 0, cell0)
            for c, col in enumerate(cols, start=1):
                val = row.get(col, '')
                text = '' if pd.isna(val) or str(val).lower() == 'nan' else str(val)
                item = QTableWidgetItem(text)
                if highlight_empty and not text:
                    item.setBackground(_COLOR_ERR)
                elif row_color:
                    item.setBackground(row_color)
                self._table.setItem(r, c, item)

    def _fill_table_two_groups(
        self,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        use_colors: bool = True,
        by_group: bool = False,
    ):
        cols = [c for c in _COL_ORDER if c in self._df.columns]
        pairs = (
            [(idx, row, 'A') for idx, row in df1.iterrows()] +
            [(idx, row, 'B') for idx, row in df2.iterrows()]
        )
        self._table.setColumnCount(len(cols) + 1)
        self._table.setHorizontalHeaderLabels(
            ['Строка'] + [_COL_DISPLAY.get(c, c) for c in cols]
        )
        self._table.setRowCount(len(pairs))
        for r, (idx, row, group) in enumerate(pairs):
            if not use_colors:
                clr = None
            elif by_group:
                clr = _COLOR_STRIPE if group == 'A' else None
            else:
                clr = _COLOR_STRIPE if r % 2 == 0 else None
            cell0 = QTableWidgetItem(str(int(idx) + 2))
            cell0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if clr:
                cell0.setBackground(clr)
            self._table.setItem(r, 0, cell0)
            for c, col in enumerate(cols, start=1):
                val = row.get(col, '')
                text = '' if pd.isna(val) or str(val).lower() == 'nan' else str(val)
                item = QTableWidgetItem(text)
                if clr:
                    item.setBackground(clr)
                self._table.setItem(r, c, item)

    # Рендеры по типу проблемы

    def _render_full_dup(self, issue: ValidationIssue):
        rows = self._df.loc[issue.indices]
        n = len(issue.indices)
        self._desc_lbl.setText(
            f"Найдено {n} строк(и) с полностью одинаковыми данными (ФИО + Школа + Класс + Буква).\n\n"
            f"Один человек добавлен несколько раз."
        )
        self._fill_table(rows)

        for idx in issue.indices:
            btn = QPushButton(f"Удалить все дубликаты — оставить строку (строка {idx + 2})")
            btn.setStyleSheet(ghost_btn_style())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            def make_keep(keep_idx=idx, all_indices=list(issue.indices)):
                def fn():
                    to_drop = [i for i in all_indices if i != keep_idx and i in self._df.index]
                    self._df = self._df.drop(index=to_drop)
                return fn
            btn.clicked.connect(lambda checked=False, fn=make_keep(): self._do_action(fn))
            self._add_action(btn)

    def _render_dup_name(self, issue: ValidationIssue):
        name = issue.meta.get('name', '')
        rows = self._df.loc[issue.indices]
        self._desc_lbl.setText(
            f"Найдено {len(issue.indices)} строк(и) с одинаковым ФИО: \"{name}\".\n\n"
            f"Это могут быть однофамильцы или один человек, добавленный дважды."
        )
        df1 = rows.iloc[:1]
        df2 = rows.iloc[1:]
        self._fill_table_two_groups(df1, df2)

        for idx in issue.indices:
            parts = []
            for col in ['Образовательная организация', 'Класс', 'Буква класса']:
                if col in self._df.columns and idx in self._df.index:
                    v = str(self._df.at[idx, col])
                    if v and v.lower() != 'nan':
                        parts.append(v)
            label = ', '.join(parts) if parts else '—'
            btn = QPushButton(f"Удалить строку {idx + 2}  ({label})")
            btn.setStyleSheet(ghost_btn_style())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            def make_del(i=idx):
                def fn():
                    if i in self._df.index:
                        self._df = self._df.drop(index=i)
                return fn
            btn.clicked.connect(lambda checked=False, fn=make_del(): self._do_action(fn))
            self._add_action(btn)

    def _render_similar_name(self, issue: ValidationIssue):
        meta = issue.meta
        n1, n2, dist = meta['name1'], meta['name2'], meta['dist']
        self._desc_lbl.setText(
            f"Похожие ФИО (расстояние Левенштейна: {dist}):\n"
            f"  \"{n1}\"\n"
            f"  \"{n2}\"\n\n"
            f"Возможно, это один человек с опечаткой в имени."
        )
        if 'ФИО ученика' in self._df.columns:
            df1 = self._df[self._df['ФИО ученика'] == n1]
            df2 = self._df[self._df['ФИО ученика'] == n2]
        else:
            df1 = self._df.iloc[:0]
            df2 = self._df.iloc[:0]
        self._fill_table_two_groups(df1, df2)

        for idx in list(df1.index) + list(df2.index):
            if idx not in self._df.index:
                continue
            name = str(self._df.at[idx, 'ФИО ученика']) if 'ФИО ученика' in self._df.columns else ''
            btn = QPushButton(f"Удалить строку {idx + 2} ({name})")
            btn.setStyleSheet(ghost_btn_style())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            def make_del(i=idx):
                def fn():
                    if i in self._df.index:
                        self._df = self._df.drop(index=i)
                return fn
            btn.clicked.connect(lambda checked=False, fn=make_del(): self._do_action(fn))
            self._add_action(btn)

    def _render_similar_school(self, issue: ValidationIssue):
        meta = issue.meta
        s1, s2 = meta['school1'], meta['school2']
        c1, c2 = meta['count1'], meta['count2']
        dist = meta['dist']
        sc = 'Образовательная организация'

        self._desc_lbl.setText(
            f"Похожие названия школ (расстояние Левенштейна: {dist}):\n"
            f"Вариант А: \"{s1}\" — {c1} уч.\n"
            f"Вариант Б: \"{s2}\" — {c2} уч.\n\n"
            f"Возможно, это одна школа с опечаткой в названии."
        )

        if sc in self._df.columns:
            df1 = self._df[self._df[sc] == s1].head(5)
            df2 = self._df[self._df[sc] == s2].head(5)
        else:
            df1 = df2 = self._df.iloc[:0]
        self._fill_table_two_groups(df1, df2, use_colors=True, by_group=True)

        btn1 = QPushButton(f"Заменить \"{s2}\" → \"{s1}\"  (изменить {c2} строк)")
        btn1.setStyleSheet(ghost_btn_style())
        btn1.setCursor(Qt.CursorShape.PointingHandCursor)
        def replace_b_to_a(col=sc, frm=s2, to=s1):
            if col in self._df.columns:
                self._df.loc[self._df[col] == frm, col] = to
        btn1.clicked.connect(lambda: self._do_action(replace_b_to_a))
        self._add_action(btn1)

        btn2 = QPushButton(f"Заменить \"{s1}\" → \"{s2}\"  (изменить {c1} строк)")
        btn2.setStyleSheet(ghost_btn_style())
        btn2.setCursor(Qt.CursorShape.PointingHandCursor)
        def replace_a_to_b(col=sc, frm=s1, to=s2):
            if col in self._df.columns:
                self._df.loc[self._df[col] == frm, col] = to
        btn2.clicked.connect(lambda: self._do_action(replace_a_to_b))
        self._add_action(btn2)

    def _render_missing(self, issue: ValidationIssue):
        rows = self._df.loc[issue.indices]
        self._desc_lbl.setText(
            f"Найдено {len(issue.indices)} строк(и) с пустыми значениями в важных столбцах.\n\n"
            f"Пустые ячейки выделены красным. При нажатии «Пропустить» они будут заполнены заглушками автоматически."
        )
        self._fill_table(rows, highlight_empty=True)

        del_btn = QPushButton(
            f"Удалить все строки с пустыми полями ({len(issue.indices)} строк(и))"
        )
        del_btn.setStyleSheet(btn_style(P['danger']))
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        def delete_missing(indices=list(issue.indices)):
            to_drop = [i for i in indices if i in self._df.index]
            self._df = self._df.drop(index=to_drop)
        del_btn.clicked.connect(lambda: self._do_action(delete_missing))
        self._add_action(del_btn)
