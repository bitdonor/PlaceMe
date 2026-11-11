import time
import random
from typing import List

from core.penalty import calc_total_penalty
from .base import BaseAlgorithm, AlgorithmResult, Seating


Individual = List[int]  # Список индексов мест (по одному на каждого студента)


class GeneticAlgorithm(BaseAlgorithm):
    """
    Генетический алгоритм.
    Особь = список индексов мест длиной n_students.
    individual[i] = индекс места в списке seats для студента i.
    """

    POPULATION_SIZE: int = 50
    GENERATIONS_PER_STUDENT: int = 2
    NO_IMPROVE_FRACTION: float = 0.3
    MUTATION_RATE: float = 0.02
    MUTATION_STEP: int = 15
    MUTATION_MAX: float = 1.0
    ELITE_SIZE: int = 2
    TOURNAMENT_SIZE: int = 3
    LOCAL_SEARCH_DIVISOR: int = 5  # local_search_steps = max(10, n_students // это)
    RELOCATION_PROB: float = 0.5

    def run(self) -> AlgorithmResult:
        start = time.time()
        history: List[float] = []

        seats = self._get_all_seats()
        n_students = len(self.students)

        if len(seats) < n_students:
            raise ValueError("Мест меньше, чем участников")

        relocation_prob = min(self.RELOCATION_PROB, (len(seats) - n_students) / len(seats)) if len(seats) > n_students else 0.0
        local_search_steps = max(10, n_students // self.LOCAL_SEARCH_DIVISOR)

        population = self._init_population(seats, n_students)
        penalties = [self._evaluate(ind, seats) for ind in population]

        best_idx = min(range(len(penalties)), key=lambda i: penalties[i])
        best_individual = population[best_idx][:]
        best_penalty = penalties[best_idx]
        history.append(best_penalty)

        max_generations = n_students * self.GENERATIONS_PER_STUDENT
        no_improve_limit = int(max_generations * self.NO_IMPROVE_FRACTION)
        no_improve = 0

        for gen in range(max_generations):
            if no_improve < self.MUTATION_STEP:
                mutation_rate = self.MUTATION_RATE
            else:
                mutation_rate = min(self.MUTATION_MAX, 0.10 * (no_improve // self.MUTATION_STEP))

            elite_indices = sorted(range(len(penalties)), key=lambda i: penalties[i])[:self.ELITE_SIZE]
            elites = [population[i][:] for i in elite_indices]

            new_population = elites[:]

            while len(new_population) < self.POPULATION_SIZE:
                parent1 = self._tournament_select(population, penalties)
                parent2 = self._tournament_select(population, penalties)
                child = self._ox_crossover(parent1, parent2)
                child = self._mutate(child, seats, mutation_rate, relocation_prob)
                child = self._local_search(child, seats, relocation_prob, local_search_steps)
                new_population.append(child)

            population = new_population
            penalties = [self._evaluate(ind, seats) for ind in population]

            gen_best_idx = min(range(len(penalties)), key=lambda i: penalties[i])
            gen_best_penalty = penalties[gen_best_idx]
            history.append(gen_best_penalty)

            if gen_best_penalty < best_penalty:
                best_penalty = gen_best_penalty
                best_individual = population[gen_best_idx][:]
                no_improve = 0
            else:
                no_improve += 1

            if (gen + 1) % max(1, max_generations // 10) == 0:
                fraction = (gen + 1) / max_generations
                self._report_progress(fraction, f"ГА: поколение {gen + 1}, штраф={best_penalty:.1f}")

            if best_penalty == 0:
                break

            if no_improve >= no_improve_limit:
                break

        seating = self._decode(best_individual, seats)
        self._report_progress(1.0, "Готово")

        return AlgorithmResult(
            seating=seating,
            total_penalty=best_penalty,
            elapsed_seconds=time.time() - start,
            history=history,
            algorithm_name="Генетический алгоритм",
        )

    # Инициализация

    def _init_population(self, seats, n_students: int) -> List[Individual]:
        all_indices = list(range(len(seats)))
        return [random.sample(all_indices, n_students) for _ in range(self.POPULATION_SIZE)]

    # Фитнес

    def _evaluate(self, individual: Individual, seats) -> float:
        return calc_total_penalty(self._decode(individual, seats), self.classrooms)

    def _decode(self, individual: Individual, seats) -> Seating:
        return {seats[seat_idx]: self.students[student_idx]
                for student_idx, seat_idx in enumerate(individual)}

    # Селекция

    def _tournament_select(self, population: List[Individual], penalties: List[float]) -> Individual:
        candidates = random.sample(range(len(population)), min(self.TOURNAMENT_SIZE, len(population)))
        return population[min(candidates, key=lambda i: penalties[i])]

    # Скрещивание (OX) по индексам мест

    def _ox_crossover(self, parent1: Individual, parent2: Individual) -> Individual:
        size = len(parent1)
        if size < 2:
            return parent1[:]

        a, b = sorted(random.sample(range(size), 2))
        child: List = [None] * size
        child[a:b + 1] = parent1[a:b + 1]

        used = set(child[a:b + 1])
        remaining = [x for x in parent2 if x not in used]

        ptr = 0
        for i in range(size):
            if child[i] is None:
                child[i] = remaining[ptr]
                ptr += 1

        return child

    # Локальный поиск: 50% своп, 50% перемещение на пустое место

    def _local_search(self, individual: Individual, seats, relocation_prob: float = 0.4, steps: int = 30) -> Individual:
        current = individual[:]
        if len(current) < 2:
            return current

        seating = self._decode(current, seats)
        used = set(current)
        empty = [s for s in range(len(seats)) if s not in used] if relocation_prob > 0 else []

        for _ in range(steps):
            if random.random() < relocation_prob and empty:
                # Перемещение студента на пустое место
                i = random.randrange(len(current))
                j = random.randrange(len(empty))
                key_i = seats[current[i]]
                key_j = seats[empty[j]]

                old_cost = self._seat_contribution(seating, key_i)
                seating[key_j] = seating.pop(key_i)
                new_cost = self._seat_contribution(seating, key_j)

                if new_cost <= old_cost:
                    old_seat = current[i]
                    current[i] = empty[j]
                    empty[j] = old_seat
                else:
                    seating[key_i] = seating.pop(key_j)
            else:
                # Своп двух студентов
                i, j = random.sample(range(len(current)), 2)
                key_i = seats[current[i]]
                key_j = seats[current[j]]

                old_i = self._seat_contribution(seating, key_i)
                old_j = self._seat_contribution(seating, key_j)
                seating[key_i], seating[key_j] = seating[key_j], seating[key_i]
                new_i = self._seat_contribution(seating, key_i)
                new_j = self._seat_contribution(seating, key_j)

                if (new_i + new_j) < (old_i + old_j):
                    current[i], current[j] = current[j], current[i]
                else:
                    seating[key_i], seating[key_j] = seating[key_j], seating[key_i]

        return current

    # Мутация: 50% своп, 50% перемещение на пустое место

    def _mutate(self, individual: Individual, seats, mutation_rate: float, relocation_prob: float = 0.4) -> Individual:
        if random.random() >= mutation_rate:
            return individual
        ind = individual[:]

        if random.random() < relocation_prob:
            # Перемещение на пустое место
            used = set(ind)
            empty = [s for s in range(len(seats)) if s not in used]
            if empty:
                i = random.randrange(len(ind))
                ind[i] = random.choice(empty)
        else:
            # Своп двух студентов
            if len(ind) >= 2:
                i, j = random.sample(range(len(ind)), 2)
                ind[i], ind[j] = ind[j], ind[i]

        return ind
