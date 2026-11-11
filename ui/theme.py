"""Единая тема приложения."""
from PyQt6.QtWidgets import QGroupBox

# Палитра
P = {
    "bg":            "#F0F4F8",   # фон окон
    "surface":       "#FFFFFF",   # карточки / диалоги
    "border":        "#D1D9E0",   # рамки
    "text":          "#1A202C",   # основной текст
    "text_muted":    "#718096",   # вторичный текст
    "header":        "#1A2E4A",   # хедер (тёмно-синий)
    "header_sub":    "#90B4D1",   # подзаголовок хедера
    "primary":       "#0758a8",   # синяя кнопка
    "primary_h":     "#2C5282",   # hover
    "primary_light": "#EBF4FF",   # лёгкий синий фон
    "success":       "#0c8a4b",   # Сбалансированный зеленый
    "success_h":     "#276749",
    "danger":        "#C53030",   # красная кнопка
    "danger_h":      "#9B2C2C",
    "orange":        "#C05621",
    "orange_h":      "#9C4221",
    "seat":          "#3182CE",   # цвет места в матрице
    "grid":          "#CBD5E0",   # сетка матрицы
    "empty":         "#F7FAFC",   # пустая клетка матрицы
    "preview":       "#DD6B20",   # контур выделения при drag
}

# Глобальный QSS
GLOBAL_QSS = f"""
* {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: {P['text']};
}}
QDialog, QMainWindow, QWidget {{
    background-color: {P['bg']};
}}
/* ── Поля ввода ─────────────────────────────── */
QLineEdit {{
    background: {P['surface']};
    color: {P['text']};
    border: 1.5px solid {P['border']};
    border-radius: 5px;
    padding: 5px 9px;
    selection-background-color: #BEE3F8;
    selection-color: {P['text']};
}}
QLineEdit:hover  {{ border-color: #A0AEC0; }}
QLineEdit:focus  {{ border-color: {P['primary']}; }}

/* ── GroupBox ────────────────────────────────── */
QGroupBox {{
    background: {P['surface']};
    border: 1.5px solid {P['border']};
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 10px 10px 10px;
    font-weight: bold;
    color: {P['text_muted']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 2px 8px;
    background: {P['surface']};
    border-top: 1.5px solid {P['border']};
    border-left: 1.5px solid {P['border']};
    border-right: 1.5px solid {P['border']};
    border-bottom: 1.5px solid {P['surface']};
    border-radius: 6px 6px 0 0;
    color: {P['text_muted']};
    font-weight: normal;
}}

/* ── Таблица ─────────────────────────────────── */
QTreeWidget {{
    background: {P['surface']};
    border: 1.5px solid {P['border']};
    border-radius: 6px;
    outline: none;
    alternate-background-color: {P['surface']};
}}
QTreeWidget::item {{
    padding: 5px 4px;
    border-bottom: 1px solid #E8EDF2;
}}
QTreeWidget::item:selected  {{
    background: {P['primary_light']};
    color: #1A365D;
    border-bottom: 1px solid #BEE3F8;
}}
QTreeWidget::item:hover:!selected {{ background: #EDF2F7; }}
QHeaderView::section {{
    background: #EDF2F7;
    border: none;
    border-bottom: 1.5px solid {P['border']};
    border-right: 1px solid {P['border']};
    padding: 6px 10px;
    font-weight: bold;
    color: {P['text_muted']};
    font-size: 9pt;
}}

/* ── Прогресс-бар ────────────────────────────── */
QProgressBar {{
    border: none;
    background: {P['border']};
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
}}
QProgressBar::chunk {{
    background: {P['primary']};
    border-radius: 3px;
}}

/* ── Скроллбары ──────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E0;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #A0AEC0; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #CBD5E0;
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: #A0AEC0; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Контекстное меню ────────────────────────── */
QMenu {{
    background: {P['surface']};
    border: 1px solid {P['border']};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 20px 6px 14px; border-radius: 4px; }}
QMenu::item:selected {{ background: {P['primary_light']}; color: #1A365D; }}
QMenu::separator {{ height: 1px; background: {P['border']}; margin: 4px 8px; }}

/* ── Диалоги сообщений ───────────────────────── */
QMessageBox {{ background: {P['surface']}; }}
QMessageBox QLabel {{ background: transparent; }}
QMessageBox QPushButton {{
    min-width: 80px;
    padding: 6px 14px;
    background: #EDF2F7;
    border: 1.5px solid {P['border']};
    border-radius: 5px;
    color: {P['text']};
}}
QMessageBox QPushButton:hover {{ background: #E2E8F0; }}
"""


def btn_style(bg: str, fg: str = "white", hover: str = None) -> str:
    h = hover or _darken(bg)
    return (
        f"QPushButton {{"
        f"  background: {bg}; color: {fg}; border: none;"
        f"  border-radius: 6px; padding: 7px 16px; font-size: 10pt;"
        f"}}"
        f"QPushButton:hover   {{ background: {h}; }}"
        f"QPushButton:pressed {{ background: {h}; }}"
        f"QPushButton:disabled {{ background: #E2E8F0; color: #A0AEC0; }}"
    )


def ghost_btn_style() -> str:
    return (
        f"QPushButton {{"
        f"  background: {P['surface']}; color: {P['text']};"
        f"  border: 1.5px solid {P['border']}; border-radius: 6px; padding: 6px 14px;"
        f"}}"
        f"QPushButton:hover {{ background: #EDF2F7; border-color: #A0AEC0; }}"
        f"QPushButton:disabled {{ color: #A0AEC0; }}"
    )


def _darken(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = max(0, int(r * 0.82)), max(0, int(g * 0.82)), max(0, int(b * 0.82))
    return f"#{r:02X}{g:02X}{b:02X}"


def apply(app) -> None:
    app.setStyleSheet(GLOBAL_QSS)


class FadingGroupBox(QGroupBox):
    """QGroupBox у которого нижняя половина боковых рамок заголовка белая."""

    def paintEvent(self, event):
        super().paintEvent(event)

        if not self.title():
            return

        from PyQt6.QtGui import QPainter, QColor
        from PyQt6.QtCore import QRect
        from PyQt6.QtWidgets import QStyleOptionGroupBox, QStyle

        opt = QStyleOptionGroupBox()
        self.initStyleOption(opt)

        # Реальный rect текста с учётом QSS и DPI
        lbl = self.style().subControlRect(
            QStyle.ComplexControl.CC_GroupBox, opt,
            QStyle.SubControl.SC_GroupBoxLabel, self
        )
        if lbl.isEmpty():
            return

        ph = 8; pv = 2; bw = 1.5; r = 6.0

        x_left  = float(lbl.x()) - ph - bw / 2
        x_right = float(lbl.right()) + ph + bw / 2
        tab_top = float(lbl.y()) - pv - bw
        tab_bot = float(lbl.bottom()) + pv + bw

        side_start = tab_top + r
        side_end   = tab_bot
        side_len   = side_end - side_start

        if side_len <= 0:
            return

        mid_y = side_start + side_len * 0.5

        patch_y = round(mid_y - 3)
        patch_h = round(side_end) - patch_y
        patch_w = round(bw + 4.0)

        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        c = QColor(P["surface"])
        p.fillRect(QRect(round(x_left  - patch_w / 2),     patch_y, patch_w, patch_h), c)
        p.fillRect(QRect(round(x_right - patch_w / 2 + 5), patch_y, patch_w, patch_h), c)

        p.end()


def ask(parent, title: str, text: str) -> bool:
    """QMessageBox.question с кнопками «Да» / «Нет» вместо Yes / No."""
    from PyQt6.QtWidgets import QMessageBox
    mb = QMessageBox(parent)
    mb.setWindowTitle(title)
    mb.setText(text)
    mb.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    mb.setDefaultButton(QMessageBox.StandardButton.Yes)
    mb.button(QMessageBox.StandardButton.Yes).setText("Да")
    mb.button(QMessageBox.StandardButton.No).setText("Нет")
    return mb.exec() == QMessageBox.StandardButton.Yes
