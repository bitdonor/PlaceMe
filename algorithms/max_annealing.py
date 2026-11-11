import math
import random
from typing import List

from models.student import Student
from models.classroom import Classroom
from core.penalty import calc_total_penalty, calc_penalty


def find_worst_penalty(students: List[Student], classrooms: List[Classroom]) -> float:
    """
    Приближённый максимальный штраф для данных студентов и аудиторий.
    Использует имитацию отжига на максимизацию: принимает ходы, увеличивающие штраф.
    Результат — практическая верхняя граница, не гарантированный абсолютный максимум.
    """
    if not students:
        return 0.0

    seats = []
    for ci, cr in enumerate(classrooms):
        for row, col in cr.get_all_seats():
            seats.append((ci, row, col))

    if len(seats) < len(students):
        return 0.0

    random.shuffle(seats)
    seating = {seats[i]: students[i] for i in range(len(students))}
    occupied = list(seating.keys())
    free = [s for s in seats if s not in seating]

    def seat_contrib(key):
        student = seating.get(key)
        if student is None:
            return 0.0
        ci, row, col = key
        total = 0.0
        for nr, nc, ntype in classrooms[ci].get_neighbors(row, col):
            neighbor = seating.get((ci, nr, nc))
            if neighbor is not None:
                total += calc_penalty(student, neighbor, ntype)
        return total

    current_penalty = calc_total_penalty(seating, classrooms)
    best_penalty = current_penalty

    max_iterations = max(10_000, len(students) * 100)
    T0 = max(50.0, current_penalty * 0.2)
    T_FINAL = 0.1
    alpha = (T_FINAL / T0) ** (1.0 / max_iterations)
    no_improve_limit = int(max_iterations * 0.3)
    relocation_prob = min(0.3, len(free) / len(seats)) if free else 0.0

    T = T0
    no_improve = 0

    for iteration in range(max_iterations):
        if free and random.random() < relocation_prob:
            occ_idx = random.randrange(len(occupied))
            free_idx = random.randrange(len(free))
            key_old = occupied[occ_idx]
            key_new = free[free_idx]
            student = seating[key_old]

            old_c = seat_contrib(key_old)
            del seating[key_old]
            seating[key_new] = student
            new_c = seat_contrib(key_new)
            delta = new_c - old_c

            # Максимизация: принимаем если delta > 0, иначе с вероятностью exp(delta/T)
            if delta > 0 or random.random() < math.exp(delta / max(T, 1e-10)):
                occupied[occ_idx] = key_new
                free[free_idx] = key_old
                current_penalty += delta
            else:
                del seating[key_new]
                seating[key_old] = student
        else:
            if len(occupied) < 2:
                continue
            i, j = random.sample(range(len(occupied)), 2)
            key1, key2 = occupied[i], occupied[j]

            old_c1 = seat_contrib(key1)
            old_c2 = seat_contrib(key2)
            seating[key1], seating[key2] = seating[key2], seating[key1]
            new_c1 = seat_contrib(key1)
            new_c2 = seat_contrib(key2)
            delta = (new_c1 + new_c2) - (old_c1 + old_c2)

            if delta > 0 or random.random() < math.exp(delta / max(T, 1e-10)):
                current_penalty += delta
            else:
                seating[key1], seating[key2] = seating[key2], seating[key1]

        if current_penalty > best_penalty:
            best_penalty = current_penalty
            no_improve = 0
        else:
            no_improve += 1

        T *= alpha

        if no_improve >= no_improve_limit and iteration >= max_iterations * 0.7:
            break

    return best_penalty
