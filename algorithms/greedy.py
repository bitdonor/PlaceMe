import random
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from models.student import Student
from core.penalty import calc_penalty, calc_total_penalty, calc_seat_penalty
from .base import BaseAlgorithm, AlgorithmResult, Seating


class GreedyAlgorithm(BaseAlgorithm):
    """
    Жадный алгоритм рассадки — четыре фазы:
    1. Мультистарт: 10 жадных рассадок, лучшая идёт дальше
    2. Оптимизация перемещениями (нулевые места в приоритете, иначе любое улучшение)
    3. Оптимизация свапами
    4. Финальная оптимизация: цикл фаз 2 и 3
    """

    def run(self) -> AlgorithmResult:
        start = time.time()
        history: List[float] = []

        total_seats = sum(len(cr.get_all_seats()) for cr in self.classrooms)
        has_free = total_seats > len(self.students)

        self._report_progress(0.0, "Мультистарт (10 попыток)...")
        seating = self._multistart(n=10, history=history)

        if has_free:
            self._report_progress(0.2, "Оптимизация перемещениями...")
            seating, penalty = self._optimize_relocations(seating, history, max_iter=100, no_improve_limit=3)

        self._report_progress(0.4, "Оптимизация свапами...")
        seating, penalty = self._optimize_swaps(seating, history, max_iter=50, no_improve_limit=3)

        # Фаза 4: итерированный поиск — повторяем фазы 2 и 3 до первой остановки без улучшения
        cycle = 0
        while True:
            cycle += 1
            prev_penalty = penalty
            progress = 0.6 + 0.4 * (1.0 - 0.5 ** cycle)
            self._report_progress(progress, f"Итерированный поиск, цикл {cycle}...")
            if has_free:
                seating, penalty = self._optimize_relocations(seating, history, max_iter=100, no_improve_limit=3)
            seating, penalty = self._optimize_swaps(seating, history, max_iter=50, no_improve_limit=3)
            if penalty >= prev_penalty:
                break

        self._report_progress(1.0, "Готово")
        return AlgorithmResult(
            seating=seating,
            total_penalty=penalty,
            elapsed_seconds=time.time() - start,
            history=history,
            algorithm_name="Жадный алгоритм с локальным поиском",
        )

    # Мультистарт

    def _multistart(self, n: int, history: List[float]) -> Seating:
        best_seating: Optional[Seating] = None
        best_penalty = float('inf')
        for i in range(n):
            self._report_progress(i / n * 0.25, f"Мультистарт: попытка {i + 1}/{n}...")
            seating = self._initial_placement()
            penalty = calc_total_penalty(seating, self.classrooms)
            if penalty < best_penalty:
                best_penalty = penalty
                best_seating = seating
            history.append(best_penalty)
        return best_seating

    # Жадная рассадка

    def _initial_placement(self) -> Seating:
        seating: Seating = {}

        class_groups: Dict[tuple, List[Student]] = defaultdict(list)
        for s in self.students:
            class_groups[(s.city, s.school, s.grade, s.letter)].append(s)

        groups = list(class_groups.values())
        random.shuffle(groups)

        queue: List[Student] = []
        for g in sorted(groups, key=lambda g: -len(g)):
            queue.extend(g)

        for ci, classroom in enumerate(self.classrooms):
            for row, col in classroom.get_all_seats():
                if not queue:
                    break

                chosen_idx: Optional[int] = None
                fallback_idx = 0
                fallback_penalty = float('inf')

                for i, student in enumerate(queue):
                    sp = self._seat_penalty_if_placed(seating, student, ci, row, col)
                    if sp == 0:
                        chosen_idx = i
                        break
                    if sp < fallback_penalty:
                        fallback_penalty = sp
                        fallback_idx = i

                student = queue.pop(chosen_idx if chosen_idx is not None else fallback_idx)
                seating[(ci, row, col)] = student

        return seating

    def _seat_penalty_if_placed(
        self, seating: Seating, student: Student, ci: int, row: int, col: int
    ) -> float:
        total = 0.0
        for n_row, n_col, n_type in self.classrooms[ci].get_neighbors(row, col):
            neighbor = seating.get((ci, n_row, n_col))
            if neighbor is not None:
                total += calc_penalty(student, neighbor, n_type)
        return total

    # Фаза 2: перемещения

    def _optimize_relocations(
        self, seating: Seating, history: List[float], max_iter: int, no_improve_limit: int
    ) -> Tuple[Seating, float]:
        best_penalty = calc_total_penalty(seating, self.classrooms)
        no_improve = 0

        for _ in range(max_iter):
            violators = self._find_violators(seating)
            if not violators:
                break

            improved = False
            for (ci, row, col), _ in violators:
                result = self._find_best_free_seat(seating, seating[(ci, row, col)], ci, row, col)
                if result is None:
                    continue

                (new_ci, new_row, new_col), delta = result
                student = seating[(ci, row, col)]
                del seating[(ci, row, col)]
                seating[(new_ci, new_row, new_col)] = student
                best_penalty += delta
                improved = True

            history.append(best_penalty)
            if not improved:
                no_improve += 1
                if no_improve >= no_improve_limit:
                    break
            else:
                no_improve = 0

        return seating, best_penalty

    def _find_best_free_seat(
        self,
        seating: Seating,
        student: Student,
        ci: int,
        row: int,
        col: int,
    ) -> Optional[Tuple[Tuple[int, int, int], float]]:
        """Возвращает (лучшее свободное место, дельта штрафа) или None.
        Нулевой штраф — в приоритете (немедленный возврат)."""
        key_old = (ci, row, col)
        old_c = self._seat_contribution(seating, key_old)
        del seating[key_old]  # временно убираем, чтобы соседи не видели студента

        ci_order = [c for c in range(len(self.classrooms)) if c != ci] + [ci]
        best_seat = None
        best_delta = 0.0

        for c in ci_order:
            for r, sc in self.classrooms[c].get_all_seats():
                if (c, r, sc) in seating:
                    continue
                new_c = self._seat_penalty_if_placed(seating, student, c, r, sc)
                if new_c == 0:
                    seating[key_old] = student
                    return (c, r, sc), -old_c
                delta = new_c - old_c
                if delta < best_delta:
                    best_delta = delta
                    best_seat = (c, r, sc)

        seating[key_old] = student  # восстанавливаем

        if best_seat is None:
            return None
        return best_seat, best_delta

    # Фаза 3: свапы

    def _optimize_swaps(
        self, seating: Seating, history: List[float], max_iter: int, no_improve_limit: int
    ) -> Tuple[Seating, float]:
        best_penalty = calc_total_penalty(seating, self.classrooms)
        no_improve = 0

        for _ in range(max_iter):
            violators = self._find_violators(seating)
            if not violators:
                break

            improved = False
            for (ci, row, col), _ in violators:
                key1 = (ci, row, col)
                old_c1 = self._seat_contribution(seating, key1)

                for key2 in list(seating.keys()):
                    if key2 == key1:
                        continue
                    old_c2 = self._seat_contribution(seating, key2)
                    seating[key1], seating[key2] = seating[key2], seating[key1]
                    new_c1 = self._seat_contribution(seating, key1)
                    new_c2 = self._seat_contribution(seating, key2)
                    delta = (new_c1 + new_c2) - (old_c1 + old_c2)

                    if delta < 0:
                        best_penalty += delta
                        improved = True
                        break
                    else:
                        seating[key1], seating[key2] = seating[key2], seating[key1]

                if improved:
                    break

            history.append(best_penalty)
            if not improved:
                no_improve += 1
                if no_improve >= no_improve_limit:
                    break
            else:
                no_improve = 0

        return seating, best_penalty

    # Утилиты

    def _find_violators(self, seating: Seating) -> List[Tuple[Tuple, float]]:
        result = []
        for key in seating:
            ci, row, col = key
            sp = calc_seat_penalty(seating, self.classrooms, ci, row, col)
            if sp > 0:
                result.append((key, sp))
        result.sort(key=lambda x: -x[1])
        return result
