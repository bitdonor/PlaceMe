import os
import subprocess
import sys
import threading
from typing import Optional, List

import pandas as pd
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QProgressBar,
    QFileDialog, QMessageBox, QGridLayout, QFrame, QSizePolicy,
)

from models.student import Student
from models.configuration import Configuration
from core.data_loader import df_to_students
from algorithms.greedy import GreedyAlgorithm
from algorithms.annealing import AnnealingAlgorithm
from algorithms.genetic import GeneticAlgorithm
from algorithms.base import AlgorithmResult
from export.excel_exporter import export_results
from export.report_generator import run_all_and_report
from .config_selector import ConfigSelectorDialog
from .theme import P, btn_style, ghost_btn_style, ask
from core.paths import get_results_dir, get_config_dir, get_icon_path

RESULTS_DIR = get_results_dir()
CONFIG_DIR = get_config_dir()


class _WorkerSignals(QObject):
    progress = pyqtSignal(float, str)
    done     = pyqtSignal(str, object)
    done_all = pyqtSignal(str)
    error    = pyqtSignal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Система рассадки участников олимпиады")
        self.resize(880, 580)
        self.setMinimumSize(720, 500)

        # Установка иконки окна
        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._students: Optional[List[Student]] = None
        self._students_df: Optional[pd.DataFrame] = None
        self._students_path: Optional[str] = None
        self._configuration: Optional[Configuration] = None
        self._running = False
        self._stop_event = threading.Event()

        self._signals = _WorkerSignals()
        self._signals.progress.connect(self._update_progress)
        self._signals.done.connect(self._on_done)
        self._signals.done_all.connect(self._on_done_all)
        self._signals.error.connect(self._on_error)

        self._build_ui()
        self._bind_keys()

    # построение интерфейса

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_header())
        layout.addWidget(self._make_body(), stretch=1)

    def _make_header(self) -> QWidget:
        w = QWidget()
        w.setObjectName("appHeader")
        w.setStyleSheet(f"""
            QWidget#appHeader {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #02305c, stop:1 #124e8c);
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 20, 32, 20)
        lay.setSpacing(5)

        title = QLabel("Система рассадки участников олимпиады")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #FFFFFF; font-size: 17pt; font-weight: bold; background: transparent;"
        )
        lay.addWidget(title)

        sub = QLabel("Сравнительное исследование алгоритмов пространственной оптимизации")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {P['header_sub']}; font-size: 9pt; background: transparent;")
        lay.addWidget(sub)
        return w

    def _make_body(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 24, 40, 24)
        lay.setSpacing(16)

        # Конфигурация
        cfg_group = QGroupBox("Конфигурация аудиторий")
        cfg_row = QHBoxLayout(cfg_group)
        cfg_row.setSpacing(12)

        self._cfg_btn = QPushButton("  Выбрать конфигурацию  ")
        self._cfg_btn.setStyleSheet(btn_style(P["success"]))
        self._cfg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cfg_btn.clicked.connect(self._open_config_selector)
        cfg_row.addWidget(self._cfg_btn)

        self._cfg_info = QLabel("Конфигурация не выбрана")
        self._cfg_info.setStyleSheet(f"color: {P['text_muted']}; background: transparent;")
        cfg_row.addWidget(self._cfg_info)
        cfg_row.addStretch()
        lay.addWidget(cfg_group)

        # Участники
        participants_row = QHBoxLayout()
        participants_row.setSpacing(12)

        load_group = QGroupBox("Список участников")
        load_row = QHBoxLayout(load_group)
        load_row.setSpacing(12)

        self._load_btn = QPushButton("  Загрузить список (.xlsx)  ")
        self._load_btn.setStyleSheet(btn_style(P["success"]))
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_btn.clicked.connect(self._load_students)
        load_row.addWidget(self._load_btn)

        self._students_info = QLabel("Список не загружен")
        self._students_info.setStyleSheet(f"color: {P['text_muted']}; background: transparent;")
        load_row.addWidget(self._students_info)
        load_row.addStretch()

        participants_row.addWidget(load_group, stretch=1)

        validate_group = QGroupBox("Исправление входных данных")
        validate_row = QHBoxLayout(validate_group)
        self._validate_btn = QPushButton("  Проверить список (.xlsx)  ")
        self._validate_btn.setStyleSheet(btn_style(P["orange"]))
        self._validate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._validate_btn.clicked.connect(self._validate_students)
        validate_row.addWidget(self._validate_btn)
        self._verified_info = QLabel("Список не проверен")
        self._verified_info.setStyleSheet(f"color: {P['text_muted']}; background: transparent;")
        validate_row.addWidget(self._verified_info)
        validate_row.addStretch()

        participants_row.addWidget(validate_group, stretch=1)

        lay.addLayout(participants_row)

        # Алгоритмы
        algo_group = QGroupBox("Алгоритмы рассадки")
        grid = QGridLayout(algo_group)
        grid.setSpacing(10)

        self._btn_greedy    = self._algo_btn("Жадный алгоритм",             P["primary"], lambda: self._run_single("greedy"))
        self._btn_annealing = self._algo_btn("Имитация отжига",              P["primary"], lambda: self._run_single("annealing"))
        self._btn_genetic   = self._algo_btn("Генетический алгоритм",        P["primary"], lambda: self._run_single("genetic"))
        self._btn_all       = self._algo_btn("Протестировать все алгоритмы", P["orange"],  self._run_all)

        grid.addWidget(self._btn_greedy,    0, 0)
        grid.addWidget(self._btn_annealing, 0, 1)
        grid.addWidget(self._btn_genetic,   1, 0)
        grid.addWidget(self._btn_all,       1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addWidget(algo_group)

        # Прогресс
        progress_row = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        progress_row.addWidget(self._progress_bar, stretch=1)

        self._cancel_btn = QPushButton("Отмена")
        self._cancel_btn.setStyleSheet(ghost_btn_style())
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel)
        self._cancel_btn.setVisible(False)
        progress_row.addWidget(self._cancel_btn)
        lay.addLayout(progress_row)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(f"color: {P['text_muted']}; font-size: 9pt; background: transparent;")
        lay.addWidget(self._status_label)

        lay.addStretch()
        return w

    def _algo_btn(self, text: str, color: str, cmd, bold: bool = False) -> QPushButton:
        btn = QPushButton(text)
        weight = "bold" if bold else "normal"
        btn.setStyleSheet(
            f"QPushButton {{ background:{color}; color:white; border:none; border-radius:6px;"
            f"  padding:14px 20px; font-size:11pt; font-weight:{weight}; }}"
            f"QPushButton:hover   {{ background:{self._darken(color)}; }}"
            f"QPushButton:disabled {{ background:#E2E8F0; color:#A0AEC0; }}"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        btn.clicked.connect(cmd)
        return btn

    @staticmethod
    def _darken(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{max(0,int(r*.82)):02X}{max(0,int(g*.82)):02X}{max(0,int(b*.82)):02X}"

    def _bind_keys(self):
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._load_students)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._open_config_selector)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

    # конфигурация

    def _open_config_selector(self):
        dlg = ConfigSelectorDialog(self)
        dlg.config_selected.connect(self._on_config_selected)
        dlg.exec()

    def _on_config_selected(self, cfg: Configuration):
        self._configuration = cfg
        self._cfg_btn.setText(f"  {cfg.name}  ")
        self._cfg_info.setText(f"{cfg.total_seats} мест  ·  {len(cfg.classrooms)} аудиторий")
        self._cfg_info.setStyleSheet(f"color: {P['primary']}; font-weight: bold; background: transparent;")

    # загрузка участников

    def _load_students(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить список участников",
            "", "Excel файлы (*.xlsx *.xls);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            df = pd.read_excel(path, dtype=str)
            df.columns = [str(c).strip() for c in df.columns]
            students, warnings = df_to_students(df)
            self._students = students
            self._students_df = df
            self._students_path = path
            fname = os.path.basename(path)
            short = fname if len(fname) <= 30 else fname[:27] + "..."
            self._load_btn.setText(f"  {short}  ")
            self._set_students_label(len(df))
            self._verified_info.setText("Список не проверен")
            self._verified_info.setStyleSheet(f"color: {P['text_muted']}; background: transparent;")
            if warnings:
                msg = "\n".join(warnings[:10])
                if len(warnings) > 10:
                    msg += f"\n...и ещё {len(warnings) - 10} предупреждений"
                QMessageBox.warning(self, "Предупреждения при загрузке", msg)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки", str(e))

    def _validate_students(self):
        if self._students_df is None:
            QMessageBox.information(self, "Список не загружен",
                "Сначала загрузите список участников через кнопку «Загрузить список (.xlsx)».")
            return
        from ui.validator_dialog import ValidatorDialog
        from PyQt6.QtWidgets import QDialog
        total_before = len(self._students_df)
        dlg = ValidatorDialog(self, self._students_df, self._students_path or "")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Применяем результат проверки
        try:
            students, warnings = df_to_students(dlg.result_df)
            self._students = students
            self._students_df = dlg.result_df
            if dlg.saved_path:
                self._students_path = dlg.saved_path
                fname = os.path.basename(dlg.saved_path)
                short = fname if len(fname) <= 30 else fname[:27] + "..."
                self._load_btn.setText(f"  {short}  ")
            self._set_students_label(len(students))
            self._verified_info.setText(f"Проверено: {total_before} уч.")
            self._verified_info.setStyleSheet(f"color: {P['orange']}; font-weight: bold; background: transparent;")
            if warnings:
                msg = "\n".join(warnings[:10])
                if len(warnings) > 10:
                    msg += f"\n...и ещё {len(warnings) - 10} предупреждений"
                QMessageBox.warning(self, "Предупреждения при загрузке", msg)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка обработки данных", str(e))

    def _set_students_label(self, count: int):
        self._students_info.setText(f"Загружено: {count} уч.")
        self._students_info.setStyleSheet(
            f"color: {P['success']}; font-weight: bold; background: transparent;"
        )

    # запуск алгоритмов

    def _check_ready(self) -> bool:
        if self._configuration is None:
            QMessageBox.warning(self, "Нет конфигурации", "Выберите конфигурацию аудиторий.")
            return False
        if not self._students:
            QMessageBox.warning(self, "Нет участников", "Загрузите список участников.")
            return False
        total = self._configuration.total_seats
        if len(self._students) > total:
            QMessageBox.warning(
                self, "Мест недостаточно",
                f"Участников: {len(self._students)}, мест: {total}.\n"
                "Добавьте аудитории или уменьшите список участников.",
            )
            return False
        return True

    def _cancel(self):
        self._stop_event.set()
        self._cancel_btn.setEnabled(False)
        self._status_label.setText("Отмена...")

    def _set_enabled(self, enabled: bool):
        for b in [self._btn_greedy, self._btn_annealing,
                  self._btn_genetic, self._btn_all, self._cfg_btn]:
            b.setEnabled(enabled)
        self._cancel_btn.setVisible(not enabled)
        self._cancel_btn.setEnabled(not enabled)

    def _run_single(self, name: str):
        if self._running or not self._check_ready():
            return
        map_ = {
            "greedy":    (GreedyAlgorithm,    "жадный",       "Жадный алгоритм"),
            "annealing": (AnnealingAlgorithm, "отжиг",        "Имитация отжига"),
            "genetic":   (GeneticAlgorithm,   "генетический", "Генетический алгоритм"),
        }
        Cls, folder, label = map_[name]
        self._running = True
        self._stop_event.clear()
        self._set_enabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText(f"Запуск: {label}...")

        def worker():
            try:
                algo = Cls(self._students, self._configuration.classrooms,
                           lambda f, m: self._signals.progress.emit(f, m),
                           stop_event=self._stop_event)
                result = algo.run()
                out = os.path.join(RESULTS_DIR, folder)
                export_results(result, self._configuration.classrooms, out)
                self._signals.done.emit(out, result)
            except InterruptedError:
                self._signals.error.emit("")
            except Exception as e:
                self._signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _run_all(self):
        if self._running or not self._check_ready():
            return
        self._running = True
        self._stop_event.clear()
        self._set_enabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText("Запуск всех алгоритмов...")

        def worker():
            try:
                out = os.path.join(RESULTS_DIR, "результаты тестирования")
                run_all_and_report(
                    self._students, self._configuration.classrooms, out,
                    lambda f, m: self._signals.progress.emit(f, m),
                    stop_event=self._stop_event,
                )
                self._signals.done_all.emit(out)
            except InterruptedError:
                self._signals.error.emit("")
            except Exception as e:
                self._signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, frac: float, msg: str):
        self._progress_bar.setValue(int(frac * 1000))
        self._status_label.setText(msg)

    def _on_done(self, out_dir: str, result):
        self._running = False
        self._set_enabled(True)
        self._progress_bar.setValue(1000)
        if ask(self, "Готово",
               f"Рассадка завершена!\n\n"
               f"Алгоритм: {result.algorithm_name}\n"
               f"Итоговый штраф: {result.total_penalty:.1f}\n"
               f"Время: {result.elapsed_seconds:.2f} с\n\n"
               f"Открыть папку с результатами?"):
            self._open_folder(out_dir)

    def _on_done_all(self, out_dir: str):
        self._running = False
        self._set_enabled(True)
        self._progress_bar.setValue(1000)
        if ask(self, "Готово",
               f"Тестирование завершено!\n\nОткрыть папку с результатами?"):
            self._open_folder(out_dir)

    def _on_error(self, error: str):
        self._running = False
        self._set_enabled(True)
        self._progress_bar.setValue(0)
        if not error:
            self._status_label.setText("Отменено")
            return
        self._status_label.setText("Ошибка")
        QMessageBox.critical(self, "Ошибка выполнения", error)

    @staticmethod
    def _open_folder(path: str):
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def closeEvent(self, event):
        msg = ("Алгоритм выполняется. Всё равно выйти из программы?"
               if self._running else "Выйти из программы?")
        if not ask(self, "Выход", msg):
            event.ignore()
            return
        event.accept()
