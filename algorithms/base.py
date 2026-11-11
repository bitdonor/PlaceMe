import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Callable, Optional
from models.student import Student
from models.classroom import Classroom
from core.penalty import calc_penalty


# Тип рассадки: {(classroom_idx, row, col): Student}
Seating = Dict[Tuple[int, int, int], Student]


class AlgorithmResult:
    def __init__(
        self,
        seating: Seating,
        total_penalty: float,
        elapsed_seconds: float,
        history: Optional[List[float]] = None,
        algorithm_name: str = "",
    ):
        self.seating = seating
        self.total_penalty = total_penalty
        self.elapsed_seconds = elapsed_seconds
        # История штрафа по итерациям/поколениям для графика сходимости
        self.history: List[float] = history or []
        self.algorithm_name = algorithm_name


class BaseAlgorithm(ABC):
    """Базовый класс для всех алгоритмов рассадки"""

    def __init__(
        self,
        students: List[Student],
        classrooms: List[Classroom],
        progress_callback: Optional[Callable[[float, str], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.students = students
        self.classrooms = classrooms
        self.progress_callback = progress_callback
        self.stop_event = stop_event

    def _report_progress(self, fraction: float, message: str = "") -> None:
        if self.stop_event and self.stop_event.is_set():
            raise InterruptedError("Отменено пользователем")
        if self.progress_callback:
            self.progress_callback(fraction, message)

    def _get_all_seats(self) -> List[Tuple[int, int, int]]:
        """Возвращает список всех мест (ci, row, col) по всем аудиториям"""
        seats = []
        for ci, cr in enumerate(self.classrooms):
            for r, c in cr.get_all_seats():
                seats.append((ci, r, c))
        return seats

    def _seat_contribution(self, seating: Seating, key: Tuple) -> float:
        """Сумма штрафов данного места со всеми его соседями."""
        ci, row, col = key
        student = seating.get(key)
        if student is None:
            return 0.0
        total = 0.0
        for n_row, n_col, n_type in self.classrooms[ci].get_neighbors(row, col):
            neighbor = seating.get((ci, n_row, n_col))
            if neighbor is not None:
                total += calc_penalty(student, neighbor, n_type)
        return total

    @abstractmethod
    def run(self) -> AlgorithmResult:
        """Запускает алгоритм и возвращает результат"""
        ...
