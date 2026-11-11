import time
import math
import random
from typing import List, Tuple

from core.penalty import calc_total_penalty
from .base import BaseAlgorithm, AlgorithmResult, Seating


class AnnealingAlgorithm(BaseAlgorithm):
    """
    Имитация отжига.
    Ходы: swap двух занятых мест + перемещение на пустое место.
    Инкрементальный подсчёт дельты штрафа.
    Параметры T0, ALPHA, MAX_ITERATIONS вычисляются адаптивно в run().
    """

    ITERATIONS_PER_STUDENT: int = 200  # MAX_ITERATIONS = n_students * это значение
    T0_FRACTION: float = 0.1           # T0 = initial_penalty * это значение
    T_FINAL: float = 1.0               # температура к концу работы
    NO_IMPROVE_FRACTION: float = 0.3   # no_improve_limit = max_iterations * это значение
    RELOCATION_PROB: float = 0.5

    def run(self) -> AlgorithmResult:
        start = time.time()
        history: List[float] = []

        seats = self._get_all_seats()
        if len(seats) < len(self.students):
            raise ValueError("Мест меньше, чем участников")

        # Случайное начальное размещение
        random.shuffle(seats)
        seating: Seating = {}
        for i, student in enumerate(self.students):
            seating[seats[i]] = student

        occupied = list(seating.keys())
        free = [s for s in seats if s not in seating]
        relocation_prob = min(self.RELOCATION_PROB, len(free) / len(seats)) if free else 0.0

        current_penalty = calc_total_penalty(seating, self.classrooms)
        best_seating = dict(seating)
        best_penalty = current_penalty
        history.append(current_penalty)

        # Адаптивные параметры
        max_iterations = max(20_000, len(self.students) * self.ITERATIONS_PER_STUDENT)
        T0 = max(1.0, current_penalty * self.T0_FRACTION)
        alpha = (self.T_FINAL / T0) ** (1.0 / max_iterations)
        no_improve_limit = int(max_iterations * self.NO_IMPROVE_FRACTION)

        T = T0
        no_improve = 0
        record_interval = max(1, max_iterations // 200)

        # Список нарушителей для guided selection
        violators: set = {key for key in seating if self._seat_contribution(seating, key) > 0}
        t_range = max(T0 - self.T_FINAL, 1e-10)

        for iteration in range(max_iterations):

            # Guided selection: вероятность растёт от 0 (горячо) до 1 (холодно)
            p_guided = (T0 - T) / t_range
            use_guided = bool(violators) and random.random() < p_guided

            if random.random() < relocation_prob:
                # Ход: перемещение студента на пустое место
                if use_guided:
                    key_old = random.choice(list(violators))
                    occ_idx = None
                else:
                    occ_idx = random.randrange(len(occupied))
                    key_old = occupied[occ_idx]

                free_idx = random.randrange(len(free))
                key_new = free[free_idx]
                student = seating[key_old]

                old_c = self._seat_contribution(seating, key_old)
                del seating[key_old]
                seating[key_new] = student
                new_c = self._seat_contribution(seating, key_new)
                delta = new_c - old_c

                if delta < 0 or random.random() < math.exp(-delta / max(T, 1e-10)):
                    if occ_idx is None:
                        occ_idx = occupied.index(key_old)
                    occupied[occ_idx] = key_new
                    free[free_idx] = key_old
                    current_penalty += delta
                    violators.discard(key_old)
                    affected = {key_new}
                    for src in (key_old, key_new):
                        ci_s, r_s, c_s = src
                        for nr, nc, _ in self.classrooms[ci_s].get_neighbors(r_s, c_s):
                            nk = (ci_s, nr, nc)
                            if nk in seating:
                                affected.add(nk)
                    self._refresh_violators(seating, violators, affected)
                else:
                    del seating[key_new]
                    seating[key_old] = student

            else:
                # Ход: swap двух занятых мест
                if len(occupied) < 2:
                    continue

                if use_guided:
                    key1 = random.choice(list(violators))
                    i = random.randrange(len(occupied))
                    key2 = occupied[i]
                    if key2 == key1:
                        key2 = occupied[(i + 1) % len(occupied)]
                else:
                    i, j = random.sample(range(len(occupied)), 2)
                    key1, key2 = occupied[i], occupied[j]

                old_c1 = self._seat_contribution(seating, key1)
                old_c2 = self._seat_contribution(seating, key2)
                seating[key1], seating[key2] = seating[key2], seating[key1]
                new_c1 = self._seat_contribution(seating, key1)
                new_c2 = self._seat_contribution(seating, key2)
                delta = (new_c1 + new_c2) - (old_c1 + old_c2)

                if delta < 0 or random.random() < math.exp(-delta / max(T, 1e-10)):
                    current_penalty += delta
                    affected = {key1, key2}
                    for src in (key1, key2):
                        ci_s, r_s, c_s = src
                        for nr, nc, _ in self.classrooms[ci_s].get_neighbors(r_s, c_s):
                            nk = (ci_s, nr, nc)
                            if nk in seating:
                                affected.add(nk)
                    self._refresh_violators(seating, violators, affected)
                else:
                    seating[key1], seating[key2] = seating[key2], seating[key1]

            # Обновляем лучшее решение
            if current_penalty < best_penalty:
                best_penalty = current_penalty
                best_seating = dict(seating)
                no_improve = 0
            else:
                no_improve += 1

            T *= alpha

            if iteration % record_interval == 0:
                history.append(current_penalty)

            if (iteration + 1) % max(1, max_iterations // 10) == 0:
                self._report_progress(
                    (iteration + 1) / max_iterations,
                    f"Отжиг: итерация {iteration + 1}, T={T:.2f}, штраф={best_penalty:.1f}"
                )

            # Критерии ранней остановки
            if best_penalty == 0:
                break
            if no_improve >= no_improve_limit and iteration >= max_iterations * 0.7:
                break

        history.append(best_penalty)
        self._report_progress(1.0, "Готово")

        return AlgorithmResult(
            seating=best_seating,
            total_penalty=best_penalty,
            elapsed_seconds=time.time() - start,
            history=history,
            algorithm_name="Имитация отжига",
        )

    def _refresh_violators(self, seating: Seating, violators: set, affected) -> None:
        """Обновляет множество нарушителей для затронутых мест."""
        for key in affected:
            if self._seat_contribution(seating, key) > 0:
                violators.add(key)
            else:
                violators.discard(key)

