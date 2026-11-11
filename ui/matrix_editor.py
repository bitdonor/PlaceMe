import copy
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QFont, QPen, QKeySequence, QShortcut,
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QWidget, QFrame,
)

from models.classroom import Classroom
from .theme import P, btn_style, ghost_btn_style, ask


# Цвета матрицы
C_SEAT    = QColor(P["seat"])
C_EMPTY   = QColor(P["empty"])
C_GRID    = QColor(P["grid"])
C_LABEL   = QColor(P["text_muted"])
C_PREVIEW = QColor(P["preview"])
C_WHITE   = QColor("#FFFFFF")
C_AXIS_BG = QColor("#EDF2F7")

CELL_SIZE = 46
MIN_CELL  = 20
MAX_CELL  = 80


class MatrixCanvas(QWidget):
    changed = pyqtSignal()

    AXIS_W = 44
    AXIS_H = 32

    def __init__(self, classroom: Classroom, parent=None):
        super().__init__(parent)
        self.classroom = classroom
        self.cell_size = CELL_SIZE
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._centered = False

        self._drag_mode: Optional[str] = None
        self._rect_start: Optional[Tuple[int, int]] = None
        self._rect_end: Optional[Tuple[float, float]] = None

        self._pan_start: Optional[Tuple[float, float]] = None
        self._space_held = False

        self._history: List = []
        self._hist_idx: int = -1
        self._save_snapshot()

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background: #FFFFFF; border: none;")

    # координаты

    def _origin(self) -> Tuple[float, float]:
        return self.AXIS_W + self._offset_x, self.AXIS_H + self._offset_y

    def _px_to_cell(self, x: float, y: float) -> Tuple[int, int]:
        ox, oy = self._origin()
        return int((y - oy) / self.cell_size), int((x - ox) / self.cell_size)

    def _valid(self, r: int, c: int) -> bool:
        return 0 <= r < self.classroom.rows and 0 <= c < self.classroom.cols

    # история (undo / redo)

    def _save_snapshot(self):
        """Сохраняет текущее состояние после действия. Обрезает историю redo."""
        state = ([row[:] for row in self.classroom.matrix], self.classroom.rows, self.classroom.cols)
        del self._history[self._hist_idx + 1:]
        self._history.append(state)
        self._hist_idx = len(self._history) - 1
        if len(self._history) > 50:
            self._history.pop(0)
            self._hist_idx -= 1

    # Обратная совместимость — вызывается из MatrixEditorDialog перед resize
    def push_undo(self):
        self._save_snapshot()

    def _apply_history(self):
        state, rows, cols = self._history[self._hist_idx]
        self.classroom.resize(rows, cols)
        self.classroom.matrix = [row[:] for row in state]
        self.changed.emit()
        self.update()

    def undo(self):
        if self._hist_idx > 0:
            self._hist_idx -= 1
            self._apply_history()

    def redo(self):
        if self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
            self._apply_history()

    def clear_all(self):
        for r in range(self.classroom.rows):
            for c in range(self.classroom.cols):
                self.classroom.matrix[r][c] = False
        self._save_snapshot()
        self.changed.emit()
        self.update()

    def select_all(self):
        for r in range(self.classroom.rows):
            for c in range(self.classroom.cols):
                self.classroom.matrix[r][c] = True
        self._save_snapshot()
        self.changed.emit()
        self.update()

    # центрирование

    def showEvent(self, event):
        super().showEvent(event)
        if not self._centered:
            self._centered = True
            grid_w = self.classroom.cols * self.cell_size
            grid_h = self.classroom.rows * self.cell_size
            avail_w = self.width() - self.AXIS_W
            avail_h = self.height() - self.AXIS_H
            self._offset_x = max(0.0, (avail_w - grid_w) / 2)
            self._offset_y = max(0.0, (avail_h - grid_h) / 2)
            self.update()

    # отрисовка

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rows, cols, cs = self.classroom.rows, self.classroom.cols, self.cell_size
        ox, oy = self._origin()

        occupied_cols = sorted({
            c for r in range(rows) for c in range(cols) if self.classroom.matrix[r][c]
        })

        # Фон оси X
        p.fillRect(0, 0, int(ox + cols * cs + 10), self.AXIS_H, C_AXIS_BG)
        # Фон оси Y
        p.fillRect(0, 0, self.AXIS_W, int(oy + rows * cs + 10), C_AXIS_BG)

        grid_pen = QPen(C_GRID, 1)

        for r in range(rows):
            for c in range(cols):
                x0 = int(ox + c * cs)
                y0 = int(oy + r * cs)
                exists = self.classroom.matrix[r][c]

                p.fillRect(x0, y0, cs, cs, C_SEAT if exists else C_EMPTY)
                p.setPen(grid_pen)
                p.drawRect(x0, y0, cs, cs)

                if exists:
                    label = self.classroom.get_seat_label(r, c)
                    fs = max(7, int(cs * 0.27))
                    p.setFont(QFont("Segoe UI", fs, QFont.Weight.Bold))
                    p.setPen(QPen(C_WHITE))
                    p.drawText(x0, y0, cs, cs, Qt.AlignmentFlag.AlignCenter, label)

        # Метки оси X (числа)
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QPen(C_LABEL))
        for c in range(cols):
            x = int(ox + c * cs + cs / 2)
            p.drawText(x - 12, 0, 24, self.AXIS_H, Qt.AlignmentFlag.AlignCenter, str(c + 1))

        # Метки оси Y (номера рядов)
        p.setFont(QFont("Segoe UI", 8))
        for r in range(rows):
            y = int(oy + r * cs + cs / 2)
            p.drawText(0, y - 10, self.AXIS_W - 4, 20, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(r + 1))

        # Превью прямоугольника при drag
        if self._rect_start and self._rect_end:
            r0, c0 = self._rect_start
            ex, ey = self._rect_end
            r2, c2 = self._px_to_cell(ex, ey)
            rx0 = int(ox + min(c0, c2) * cs)
            ry0 = int(oy + min(r0, r2) * cs)
            w_px = (abs(c2 - c0) + 1) * cs
            h_px = (abs(r2 - r0) + 1) * cs

            pen = QPen(C_PREVIEW, 2, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(rx0, ry0, w_px, h_px)

            # Подсказка размера
            w_cells = abs(c2 - c0) + 1
            h_cells = abs(r2 - r0) + 1
            tip = f"Ш: {w_cells}\nВ: {h_cells}"
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.setPen(QPen(C_PREVIEW))
            # Белый фон под текстом
            tip_x = int(ex) + 12
            tip_y = int(ey) - 38
            p.fillRect(tip_x - 2, tip_y - 2, 60, 38, QColor(255, 255, 255, 210))
            p.drawText(tip_x, tip_y, 58, 36, Qt.AlignmentFlag.AlignLeft, tip)

        p.end()

    # мышь

    def mousePressEvent(self, event):
        self.setFocus()  # тачпад может уводить фокус — возвращаем для Space
        x, y = event.position().x(), event.position().y()

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = (x, y)
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self._space_held:
                self._pan_start = (x, y)
                return
            r, c = self._px_to_cell(x, y)
            if not self._valid(r, c):
                return
            self._drag_mode = 'draw'
            self._rect_start = (r, c)
            self._rect_end = (x, y)
            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            r, c = self._px_to_cell(x, y)
            if not self._valid(r, c):
                return
            self._drag_mode = 'erase'
            self._rect_start = (r, c)
            self._rect_end = (x, y)
            self.update()

    def mouseMoveEvent(self, event):
        x, y = event.position().x(), event.position().y()
        btns = event.buttons()

        if self._pan_start is not None and (
            btns & Qt.MouseButton.MiddleButton or
            (self._space_held and btns & Qt.MouseButton.LeftButton)
        ):
            self._offset_x += x - self._pan_start[0]
            self._offset_y += y - self._pan_start[1]
            self._pan_start = (x, y)
            self.update()
            return

        if self._rect_start and (
            btns & Qt.MouseButton.LeftButton or btns & Qt.MouseButton.RightButton
        ):
            self._rect_end = (x, y)
            self.update()

    def mouseReleaseEvent(self, event):
        x, y = event.position().x(), event.position().y()

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = None
            self.setCursor(Qt.CursorShape.SizeAllCursor if self._space_held else Qt.CursorShape.CrossCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self._pan_start is not None and self._space_held:
                self._pan_start = None
                return
            if self._rect_start and self._drag_mode == 'draw':
                r0, c0 = self._rect_start
                r2, c2 = self._px_to_cell(x, y)
                for r in range(min(r0, r2), max(r0, r2) + 1):
                    for c in range(min(c0, c2), max(c0, c2) + 1):
                        if self._valid(r, c):
                            self.classroom.matrix[r][c] = True
                self._save_snapshot()
                self.changed.emit()
            self._rect_start = self._rect_end = self._drag_mode = None
            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            if self._rect_start and self._drag_mode == 'erase':
                r0, c0 = self._rect_start
                r2, c2 = self._px_to_cell(x, y)
                for r in range(min(r0, r2), max(r0, r2) + 1):
                    for c in range(min(c0, c2), max(c0, c2) + 1):
                        if self._valid(r, c):
                            self.classroom.matrix[r][c] = False
                self._save_snapshot()
                self.changed.emit()
            self._rect_start = self._rect_end = self._drag_mode = None
            self.update()

    def wheelEvent(self, event):
        d = event.angleDelta().y()
        if d == 0:
            d = event.pixelDelta().y()  # фоллбэк для тачпадов без angleDelta
        if d > 0:
            self.cell_size = min(MAX_CELL, int(self.cell_size * 1.15))
        elif d < 0:
            self.cell_size = max(MIN_CELL, int(self.cell_size / 1.15))
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            super().keyReleaseEvent(event)


# Диалог редактора

class MatrixEditorDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, parent, classroom: Classroom, on_save=None, other_names=None):
        super().__init__(parent)
        self.classroom = copy.deepcopy(classroom)
        self._original = classroom
        self._other_names = other_names or set()
        if on_save:
            self.saved.connect(on_save)

        self.setWindowTitle(f"Редактор: {classroom.name}")
        self.resize(880, 740)
        self.setModal(True)
        self._build_ui()
        self._bind_keys()
        self._update_seat_count()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Верхняя панель: имя + счётчик
        top = QWidget()
        top.setStyleSheet(f"background: {P['surface']}; border-bottom: 1px solid {P['border']};")
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(14, 10, 14, 10)
        top_lay.setSpacing(10)

        lbl = QLabel("Аудитория:")
        lbl.setStyleSheet(f"color: {P['text_muted']}; background: transparent;")
        top_lay.addWidget(lbl)

        self._name_edit = QLineEdit(self.classroom.name)
        self._name_edit.setFixedWidth(200)
        self._name_edit.textChanged.connect(lambda _: self._update_seat_count())
        top_lay.addWidget(self._name_edit)

        self._seat_label = QLabel()
        self._seat_label.setStyleSheet(
            f"color: {P['primary']}; font-weight: bold; font-size: 10pt; background: transparent;"
        )
        top_lay.addWidget(self._seat_label)
        top_lay.addStretch()
        layout.addWidget(top)

        # Панель инструментов
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: #EDF2F7; border-bottom: 1px solid {P['border']};")
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(10, 6, 10, 6)
        tb_lay.setSpacing(6)

        def tb_btn(text, cmd, color=None):
            b = QPushButton(text)
            if color:
                b.setStyleSheet(btn_style(color))
            else:
                b.setStyleSheet(ghost_btn_style())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cmd)
            return b

        tb_lay.addWidget(tb_btn("+ Строка",    self._add_row))
        tb_lay.addWidget(tb_btn("– Строка",    self._remove_row))
        tb_lay.addWidget(tb_btn("+ Столбец",   self._add_col))
        tb_lay.addWidget(tb_btn("– Столбец",   self._remove_col))

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {P['border']}; max-width: 1px;")
        tb_lay.addWidget(sep)

        tb_lay.addWidget(tb_btn("Очистить всё", self._clear_all,  P["danger"]))
        tb_lay.addWidget(tb_btn("↩ Отменить",   self._undo,       P["primary"]))
        tb_lay.addWidget(tb_btn("↪ Вернуть",    self._redo,       P["primary"]))

        tb_lay.addStretch()

        hint = QLabel("ЛКМ — добавить  ·  ПКМ — удалить  ·  Drag — область  ·  Колесо — масштаб  ·  Пробел+ЛКМ — перемещение")
        hint.setStyleSheet(f"color: {P['text_muted']}; font-size: 8pt; background: transparent;")
        tb_lay.addWidget(hint)
        layout.addWidget(toolbar)

        # Холст
        self.canvas = MatrixCanvas(self.classroom)
        self.canvas.changed.connect(self._update_seat_count)
        layout.addWidget(self.canvas, stretch=1)

        # Нижняя панель
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {P['surface']}; border-top: 1px solid {P['border']};")
        bot_lay = QHBoxLayout(bottom)
        bot_lay.setContentsMargins(14, 10, 14, 10)
        bot_lay.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet(ghost_btn_style())
        cancel_btn.clicked.connect(self.reject)
        bot_lay.addWidget(cancel_btn)

        save_btn = QPushButton("  Готово  ")
        save_btn.setStyleSheet(btn_style(P["success"]))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        bot_lay.addWidget(save_btn)

        layout.addWidget(bottom)

    def _bind_keys(self):
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self._redo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._redo)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save)
        QShortcut(QKeySequence("Ctrl+A"), self).activated.connect(self._select_all)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._clear_all)
        QShortcut(QKeySequence("Backspace"), self).activated.connect(self._clear_all)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)
        self.canvas.setFocus()

    def _update_seat_count(self):
        self.classroom.name = self._name_edit.text()
        count = self.classroom.total_seats
        self._seat_label.setText(f"Мест: {count}")
        self.setWindowTitle(f"Редактор: {self.classroom.name}  [{count} мест]")

    def _add_row(self):
        if self.classroom.rows < 20:
            self.classroom.resize(self.classroom.rows + 1, self.classroom.cols)
            self.canvas._save_snapshot()
            self._update_seat_count()
            self.canvas.update()

    def _remove_row(self):
        if self.classroom.rows > 1:
            self.classroom.resize(self.classroom.rows - 1, self.classroom.cols)
            self.canvas._save_snapshot()
            self._update_seat_count()
            self.canvas.update()

    def _add_col(self):
        if self.classroom.cols < 20:
            self.classroom.resize(self.classroom.rows, self.classroom.cols + 1)
            self.canvas._save_snapshot()
            self._update_seat_count()
            self.canvas.update()

    def _remove_col(self):
        if self.classroom.cols > 1:
            self.classroom.resize(self.classroom.rows, self.classroom.cols - 1)
            self.canvas._save_snapshot()
            self._update_seat_count()
            self.canvas.update()

    def _clear_all(self):
        self.canvas.clear_all()

    def _select_all(self):
        self.canvas.select_all()

    def _undo(self):
        self.canvas.undo()

    def _redo(self):
        self.canvas.redo()

    def _save(self):
        self.classroom.name = self._name_edit.text().strip() or self._original.name
        if self.classroom.name in self._other_names:
            if not ask(self, "Аудитория уже существует",
                       f'Аудитория с именем «{self.classroom.name}» уже существует в этой конфигурации.\n'
                       f'Вы уверены, что хотите перезаписать её?'):
                return
        self._original.name = self.classroom.name
        self._original.matrix = [row[:] for row in self.classroom.matrix]
        if (self._original.rows != self.classroom.rows
                or self._original.cols != self.classroom.cols):
            self._original.resize(self.classroom.rows, self.classroom.cols)
            self._original.matrix = [row[:] for row in self.classroom.matrix]
        self.saved.emit()
        self.accept()
