from __future__ import annotations
from typing import List, Tuple


COLUMN_LETTERS = 'АБВГДЕЖЗИКЛМНОПРСТУФ'
MAX_SIZE = 20


class Classroom:
    def __init__(self, name: str, rows: int = 10, cols: int = 10):
        self.name = name
        rows = min(rows, MAX_SIZE)
        cols = min(cols, MAX_SIZE)
        self.matrix: List[List[bool]] = [[False] * cols for _ in range(rows)]

    @property
    def rows(self) -> int:
        return len(self.matrix)

    @property
    def cols(self) -> int:
        return len(self.matrix[0]) if self.matrix else 0

    @property
    def total_seats(self) -> int:
        return sum(cell for row in self.matrix for cell in row)

    def resize(self, new_rows: int, new_cols: int) -> None:
        """Изменяет размер матрицы, сохраняя существующие места"""
        new_rows = min(new_rows, MAX_SIZE)
        new_cols = min(new_cols, MAX_SIZE)
        old_matrix = self.matrix
        self.matrix = [[False] * new_cols for _ in range(new_rows)]
        for r in range(min(len(old_matrix), new_rows)):
            for c in range(min(len(old_matrix[0]) if old_matrix else 0, new_cols)):
                self.matrix[r][c] = old_matrix[r][c]

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int, str]]:
        """
        Возвращает список (n_row, n_col, type) для существующих соседей.
        type = 'side' для лево/право/верх/низ, 'diag' для диагоналей.
        Контакт только если оба места существуют и они непосредственные соседи.
        """
        neighbors = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if 0 <= nr < len(self.matrix) and 0 <= nc < len(self.matrix[0]):
                    if self.matrix[nr][nc]:
                        n_type = 'diag' if (dr != 0 and dc != 0) else 'side'
                        neighbors.append((nr, nc, n_type))
        return neighbors

    def get_all_seats(self) -> List[Tuple[int, int]]:
        """Возвращает список всех существующих мест (row, col)"""
        seats = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.matrix[r][c]:
                    seats.append((r, c))
        return seats

    def get_seat_label(self, row: int, col: int) -> str:
        """
        Человеко-читаемое название места, например '2Б'.
        Буква = порядковый номер столбца среди столбцов с хотя бы одним местом.
        Цифра = порядковый номер места в столбце сверху вниз.
        """
        occupied_cols = sorted(set(
            c for r in range(self.rows)
            for c in range(self.cols)
            if self.matrix[r][c]
        ))
        if col not in occupied_cols:
            return "?"
        col_letter = COLUMN_LETTERS[occupied_cols.index(col)]
        seat_number = sum(1 for r in range(row) if self.matrix[r][col]) + 1
        return f"{seat_number}{col_letter}"

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'rows': self.rows,
            'cols': self.cols,
            'matrix': self.matrix,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Classroom':
        cr = cls(data['name'], data['rows'], data['cols'])
        cr.matrix = data['matrix']
        return cr
