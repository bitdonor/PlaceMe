import copy
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QFrame,
)

from models.configuration import Configuration
from .config_editor import ConfigEditorDialog
from .theme import P, btn_style, ghost_btn_style, ask
from core.paths import get_config_dir

CONFIG_DIR = get_config_dir()


class ConfigSelectorDialog(QDialog):
    config_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор конфигурации")
        self.resize(660, 540)
        self.setModal(True)
        self._clipboard = None
        self._configs: list = Configuration.load_all(CONFIG_DIR)
        self._build_ui()
        self._bind_keys()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        # Заголовок диалога
        title = QLabel("Выберите конфигурацию аудиторий")
        title.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; color: {P['text']}; background: transparent;"
        )
        layout.addWidget(title)

        sep = _hline()
        layout.addWidget(sep)

        # Таблица
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Название", "Мест", "Аудиторий"])
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 90)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_right_click)
        self.tree.itemDoubleClicked.connect(lambda _i, _c: self._edit())
        layout.addWidget(self.tree)

        # Кнопки действий
        act_row = QHBoxLayout()
        act_row.setSpacing(8)

        self._confirm_btn = QPushButton("  Выбрать  ")
        self._confirm_btn.setStyleSheet(btn_style(P["primary"]))
        self._confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_btn.clicked.connect(self._confirm)
        act_row.addWidget(self._confirm_btn)

        for text, cmd, color in [
            ("Создать",  self._create, P["success"]),
            ("Удалить",  self._delete, P["danger"]),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(btn_style(color) if color else ghost_btn_style())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cmd)
            act_row.addWidget(b)

        act_row.addStretch()

        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet(ghost_btn_style())
        close_btn.clicked.connect(self.reject)
        act_row.addWidget(close_btn)

        layout.addLayout(act_row)

    def _bind_keys(self):
        QShortcut(QKeySequence("Return"), self).activated.connect(self._confirm)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._delete)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._copy)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self._paste)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._create)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)

    # список

    def _refresh_list(self):
        self.tree.clear()
        for cfg in self._configs:
            item = QTreeWidgetItem([cfg.name, str(cfg.total_seats), str(len(cfg.classrooms))])
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            self.tree.addTopLevelItem(item)

    def _selected_index(self) -> int:
        items = self.tree.selectedItems()
        return self.tree.indexOfTopLevelItem(items[0]) if items else -1

    # контекстное меню

    def _on_right_click(self, pos):
        item = self.tree.itemAt(pos)
        if item:
            self.tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Копировать",  self._copy)
        menu.addAction("Вставить",    self._paste)
        menu.addSeparator()
        menu.addAction("Удалить",     self._delete)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # действия

    def _confirm(self):
        idx = self._selected_index()
        if idx < 0:
            QMessageBox.warning(self, "Выбор", "Выберите конфигурацию из списка.")
            return
        self.config_selected.emit(self._configs[idx])
        self.accept()

    def _create(self):
        cfg = Configuration("Новая конфигурация")
        existing = {c.name for c in self._configs}
        dlg = ConfigEditorDialog(self, cfg, existing_names=existing)
        dlg.saved.connect(self._on_config_saved)
        dlg.exec()

    def _edit(self):
        idx = self._selected_index()
        if idx < 0:
            return
        existing = {c.name for i, c in enumerate(self._configs) if i != idx}
        dlg = ConfigEditorDialog(self, self._configs[idx], existing_names=existing)
        dlg.saved.connect(lambda _: self._reload())
        dlg.exec()

    def _delete(self):
        idx = self._selected_index()
        if idx < 0:
            return
        cfg = self._configs[idx]
        if not ask(self, "Удалить", f"Удалить конфигурацию «{cfg.name}»?"):
            return
        safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in cfg.name)
        fpath = os.path.join(CONFIG_DIR, f"{safe}.json")
        if os.path.exists(fpath):
            os.remove(fpath)
        self._configs.pop(idx)
        self._refresh_list()

    def _copy(self):
        idx = self._selected_index()
        if idx >= 0:
            self._clipboard = copy.deepcopy(self._configs[idx])

    def _paste(self):
        if self._clipboard is None:
            return
        new_cfg = copy.deepcopy(self._clipboard)
        names = {c.name for c in self._configs}
        base = f"{new_cfg.name} (копия)"
        counter = 1
        new_cfg.name = f"{base} {counter}"
        while new_cfg.name in names:
            counter += 1
            new_cfg.name = f"{base} {counter}"
        os.makedirs(CONFIG_DIR, exist_ok=True)
        new_cfg.save(CONFIG_DIR)
        self._configs.append(new_cfg)
        self._refresh_list()

    def _on_config_saved(self, cfg: Configuration):
        # Дубль уже подтверждён в редакторе — просто заменяем в списке
        self._configs = [c for c in self._configs if c.name != cfg.name]
        self._configs.append(cfg)
        self._refresh_list()

    def _reload(self):
        self._configs = Configuration.load_all(CONFIG_DIR)
        self._refresh_list()


def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background: {P['border']}; max-height: 1px;")
    return f
