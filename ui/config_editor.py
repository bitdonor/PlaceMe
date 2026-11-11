import copy
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QFrame, QWidget,
)

from models.classroom import Classroom
from models.configuration import Configuration
from .matrix_editor import MatrixEditorDialog
from .theme import P, btn_style, ghost_btn_style, ask
from core.paths import get_config_dir

CONFIG_DIR = get_config_dir()


class ConfigEditorDialog(QDialog):
    saved = pyqtSignal(object)

    def __init__(self, parent=None, configuration: Configuration = None, existing_names: set = None):
        super().__init__(parent)
        self.config = configuration
        self._original_name = configuration.name
        self._existing_names = existing_names or set()
        self._classroom_clipboard = None
        self._editing_idx = -1
        self._dirty = False
        self.setWindowTitle("Редактор конфигурации")
        self.resize(740, 560)
        self.setModal(True)
        self._build_ui()
        self._bind_keys()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        # Заголовок
        title = QLabel("Редактор конфигурации")
        title.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; color: {P['text']}; background: transparent;"
        )
        layout.addWidget(title)
        layout.addWidget(_hline())

        # Название
        name_row = QHBoxLayout()
        lbl = QLabel("Название:")
        lbl.setStyleSheet(f"color: {P['text_muted']}; background: transparent;")
        name_row.addWidget(lbl)
        self._name_edit = QLineEdit(self.config.name)
        self._name_edit.setFixedWidth(280)
        name_row.addWidget(self._name_edit)
        name_row.addStretch()
        layout.addLayout(name_row)

        # Таблица аудиторий
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Аудитория", "Мест"])
        self.tree.setColumnWidth(0, 500)
        self.tree.setColumnWidth(1, 80)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.itemDoubleClicked.connect(lambda _i, _c: self._open_matrix_editor())
        layout.addWidget(self.tree)

        # Кнопки действий
        act_row = QHBoxLayout()
        act_row.setSpacing(8)

        for text, cmd, color in [
            ("Создать аудиторию", self._create_classroom, P["primary"]),
            ("Копировать",        self._copy_classroom, None),
            ("Вставить",          self._paste_classroom, None),
            ("Удалить",           self._delete_classroom, P["danger"]),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(btn_style(color) if color else ghost_btn_style())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cmd)
            act_row.addWidget(b)

        act_row.addStretch()
        layout.addLayout(act_row)

        # Нижняя панель
        layout.addWidget(_hline())
        bottom = QHBoxLayout()
        bottom.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet(ghost_btn_style())
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        save_btn = QPushButton("  Сохранить  ")
        save_btn.setStyleSheet(btn_style(P["success"]))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        bottom.addWidget(save_btn)

        layout.addLayout(bottom)

    def reject(self):
        if self._dirty:
            if not ask(self, "Закрыть без сохранения?",
                       "Конфигурация была изменена, но не сохранена.\nЗакрыть без сохранения?"):
                return
        super().reject()

    def _bind_keys(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._create_classroom)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._copy_classroom)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self._paste_classroom)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._delete_classroom)
        QShortcut(QKeySequence("Return"), self).activated.connect(self._open_matrix_editor)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)

    # список

    def _refresh_list(self):
        self.tree.clear()
        for cr in self.config.classrooms:
            item = QTreeWidgetItem([cr.name, str(cr.total_seats)])
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            self.tree.addTopLevelItem(item)

    def _selected_index(self) -> int:
        items = self.tree.selectedItems()
        return self.tree.indexOfTopLevelItem(items[0]) if items else -1

    # действия

    def _create_classroom(self):
        existing = {cr.name for cr in self.config.classrooms}
        i = len(self.config.classrooms) + 1
        name = f"Аудитория {i}"
        while name in existing:
            i += 1
            name = f"Аудитория {i}"
        cr = Classroom(name, rows=6, cols=6)
        other_names = {c.name for c in self.config.classrooms}
        dlg = MatrixEditorDialog(self, cr, other_names=other_names)
        dlg.saved.connect(lambda: self._finish_create_classroom(cr))
        dlg.exec()

    def _finish_create_classroom(self, cr: Classroom):
        self.config.add_classroom(cr)
        self._dirty = True
        self._refresh_list()
        last = self.tree.topLevelItem(self.tree.topLevelItemCount() - 1)
        self.tree.setCurrentItem(last)
        self.tree.scrollToItem(last)

    def _open_matrix_editor(self):
        idx = self._selected_index()
        if idx < 0:
            return
        self._editing_idx = idx
        other_names = {cr.name for i, cr in enumerate(self.config.classrooms) if i != idx}
        dlg = MatrixEditorDialog(self, self.config.classrooms[idx], other_names=other_names)
        dlg.saved.connect(self._on_classroom_saved)
        dlg.exec()

    def _on_classroom_saved(self):
        self._dirty = True
        # Если аудитория была переименована в уже существующее имя (пользователь подтвердил),
        # удаляем старую аудиторию с тем же именем
        if 0 <= self._editing_idx < len(self.config.classrooms):
            saved_name = self.config.classrooms[self._editing_idx].name
            dupes = [i for i, cr in enumerate(self.config.classrooms)
                     if cr.name == saved_name and i != self._editing_idx]
            for i in reversed(dupes):
                self.config.classrooms.pop(i)
                if i < self._editing_idx:
                    self._editing_idx -= 1
        self._refresh_list()

    def _copy_classroom(self):
        idx = self._selected_index()
        if idx >= 0:
            self._classroom_clipboard = copy.deepcopy(self.config.classrooms[idx])

    def _paste_classroom(self):
        if self._classroom_clipboard is None:
            return
        new_cr = copy.deepcopy(self._classroom_clipboard)
        existing = {cr.name for cr in self.config.classrooms}
        base = f"{new_cr.name} (копия)"
        counter = 1
        name = f"{base} {counter}"
        while name in existing:
            counter += 1
            name = f"{base} {counter}"
        new_cr.name = name
        self.config.add_classroom(new_cr)
        self._dirty = True
        self._refresh_list()
        last = self.tree.topLevelItem(self.tree.topLevelItemCount() - 1)
        self.tree.setCurrentItem(last)
        self.tree.scrollToItem(last)

    def _delete_classroom(self):
        idx = self._selected_index()
        if idx < 0:
            return
        name = self.config.classrooms[idx].name
        if ask(self, "Удалить", f"Удалить аудиторию «{name}»?"):
            self.config.remove_classroom(idx)
            self._dirty = True
            self._refresh_list()

    def _save(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Имя", "Введите название конфигурации.")
            return
        if name in self._existing_names:
            if not ask(self, "Конфигурация уже существует",
                       f'Конфигурация с именем «{name}» уже существует.\n'
                       f'Если вы продолжите, она будет перезаписана.\n\nВы уверены?'):
                return
        old_name = self._original_name
        self.config.name = name
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            self.config.save(CONFIG_DIR)
            if old_name != name:
                safe_old = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in old_name)
                old_path = os.path.join(CONFIG_DIR, f"{safe_old}.json")
                if os.path.exists(old_path):
                    os.remove(old_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", str(e))
            return
        self._original_name = name
        self.saved.emit(self.config)
        self.accept()


def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background: {P['border']}; max-height: 1px;")
    return f
