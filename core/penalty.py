from typing import Dict, Tuple, List
from models.student import Student
from models.classroom import Classroom


def get_base_penalty(s1: Student, s2: Student) -> int:
    """Базовый штраф за пару участников"""
    if s1.acquaintance and s1.acquaintance == s2.acquaintance:
        return 70
    if s1.school != s2.school or s1.city != s2.city:
        return 0
    if s1.grade != s2.grade:
        return 10
    if s1.letter != s2.letter:
        return 30
    return 70


def get_neighbor_coefficient(neighbor_type: str) -> float:
    """Коэффициент: 'side' = 1.0, 'diag' = 0.5"""
    return 1.0 if neighbor_type == 'side' else 0.5


def calc_penalty(s1: Student, s2: Student, neighbor_type: str) -> float:
    """Штраф за конкретную пару соседей"""
    return get_base_penalty(s1, s2) * get_neighbor_coefficient(neighbor_type)


def calc_total_penalty(
    seating: Dict[Tuple[int, int, int], Student],
    classrooms: List[Classroom],
) -> float:
    """
    Считает суммарный штраф для всей рассадки.
    seating: {(classroom_idx, row, col): Student}
    """
    total = 0.0
    for (ci, row, col), student in seating.items():
        classroom = classrooms[ci]
        for n_row, n_col, n_type in classroom.get_neighbors(row, col):
            neighbor_key = (ci, n_row, n_col)
            if neighbor_key in seating:
                # Считаем каждую пару один раз
                if (n_row, n_col) > (row, col):
                    total += calc_penalty(student, seating[neighbor_key], n_type)
    return total


def calc_seat_penalty(
    seating: Dict[Tuple[int, int, int], Student],
    classrooms: List[Classroom],
    ci: int,
    row: int,
    col: int,
) -> float:
    """Штраф одного места — сумма штрафов со всеми его соседями"""
    student = seating.get((ci, row, col))
    if student is None:
        return 0.0
    total = 0.0
    for n_row, n_col, n_type in classrooms[ci].get_neighbors(row, col):
        neighbor = seating.get((ci, n_row, n_col))
        if neighbor is not None:
            total += calc_penalty(student, neighbor, n_type)
    return total
