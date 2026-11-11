import os
import re
from typing import List, Optional
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from models.classroom import Classroom
from algorithms.base import AlgorithmResult


_HEADER_FILL = PatternFill("solid", fgColor="4472C4")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_ERROR_FILL = PatternFill("solid", fgColor="FFC7CE")  # Светло-красный фон
_THIN = Side(style="thin", color="000000")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

_VAHTA_HEADERS = [
    "№", "Муниципальное образование", "Город", "Образовательная организация",
    "Ф.И.О.", "Класс участия", "Аудитория",
]
_CLASSROOM_HEADERS = [
    "№", "Муниципальное образование", "Город", "Образовательная организация",
    "Ф.И.О.", "Класс участия", "Место",
]
_COMBINED_HEADERS = [
    "Муниципальное образование",
    "Город",
    "Образовательная организация",
    "ФИО ученика",
    "Класс",
    "Буква класса",
    "Место",
    "Аудитория",
]


def export_results(
    result: AlgorithmResult,
    classrooms: List[Classroom],
    output_dir: str,
    olympiad_name: str = "",
    students_df=None,
) -> None:
    """Одиночный запуск: вахта + отдельный файл на каждую аудиторию + файл для учителя."""
    os.makedirs(output_dir, exist_ok=True)

    # Глобальная нумерация в том же порядке, что и вахта
    all_rows = []
    for (ci, row, col) in result.seating:
        all_rows.append((classrooms[ci].name, row, col, ci))
    all_rows.sort(key=lambda x: (x[0], x[1], x[2]))
    global_idx = {(ci, row, col): i + 1 for i, (_, row, col, ci) in enumerate(all_rows)}

    _export_vahta(result, classrooms, output_dir, olympiad_name)
    for ci, classroom in enumerate(classrooms):
        _export_classroom(result, ci, classroom, output_dir, olympiad_name, global_idx)
    if students_df is not None:
        _export_teacher(result, classrooms, students_df, output_dir)


def export_combined(
    result: AlgorithmResult,
    classrooms: List[Classroom],
    output_dir: str,
    suffix: str = "",
    filename: str = "",
) -> None:
    """Тест всех: один файл с полями Город|Район|ФИО|Школа|Класс|Буква|Место|Аудитория."""
    os.makedirs(output_dir, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Рассадка"
    _write_header_row(ws, _COMBINED_HEADERS, row=1)

    rows = []
    for (ci, row, col), student in result.seating.items():
        cr = classrooms[ci]
        rows.append({
            'city':         student.city,
            'municipality': student.municipality,
            'name':         student.name,
            'school':       student.school,
            'grade':        student.grade,
            'letter':       student.letter,
            'seat':         cr.get_seat_label(row, col),
            'classroom':    cr.name,
            'sort_key':     (cr.name, row, col),
        })
    rows.sort(key=lambda r: r['sort_key'])

    for i, r in enumerate(rows, start=2):
        _apply_placeholder_style(ws.cell(row=i, column=1, value=r['municipality']))
        _apply_placeholder_style(ws.cell(row=i, column=2, value=r['city']))
        _apply_placeholder_style(ws.cell(row=i, column=3, value=r['school']))
        _apply_placeholder_style(ws.cell(row=i, column=4, value=r['name']))
        _apply_placeholder_style(ws.cell(row=i, column=5, value=r['grade']))
        _apply_placeholder_style(ws.cell(row=i, column=6, value=r['letter']))
        ws.cell(row=i, column=7, value=r['seat'])
        ws.cell(row=i, column=8, value=r['classroom'])

    _autofit_columns(ws)
    if not filename:
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', result.algorithm_name)
        filename = f"{safe_name}{suffix}.xlsx" if suffix else f"{safe_name}.xlsx"
    wb.save(os.path.join(output_dir, filename))


# Вахта

def _export_vahta(result, classrooms, output_dir, olympiad_name):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Вахта"

    if olympiad_name:
        ws.cell(row=1, column=2, value=olympiad_name).font = Font(bold=True)

    _write_header_row(ws, _VAHTA_HEADERS, row=2)

    rows = []
    for (ci, row, col), student in result.seating.items():
        cr = classrooms[ci]
        rows.append({
            'city':         student.city,
            'municipality': student.municipality,
            'school':       student.school,
            'name':         student.name,
            'grade':        student.grade,
            'classroom':    cr.name,
        })

    muni_count = {}
    for r in rows:
        muni_count[r['municipality']] = muni_count.get(r['municipality'], 0) + 1
    rows.sort(key=lambda r: (-muni_count[r['municipality']], r['school'], r['name']))

    for i, r in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=i-2)
        _apply_placeholder_style(ws.cell(row=i, column=2, value=r['municipality']))
        _apply_placeholder_style(ws.cell(row=i, column=3, value=r['city']))
        _apply_placeholder_style(ws.cell(row=i, column=4, value=r['school']))
        _apply_placeholder_style(ws.cell(row=i, column=5, value=r['name']))
        _apply_placeholder_style(ws.cell(row=i, column=6, value=r['grade']))
        ws.cell(row=i, column=7, value=r['classroom'])

    _autofit_columns(ws)
    wb.save(os.path.join(output_dir, "Вахта.xlsx"))


# Аудитория

def _export_classroom(result, ci, classroom, output_dir, olympiad_name, global_idx):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = classroom.name[:31]

    if olympiad_name:
        ws.cell(row=1, column=2, value=olympiad_name).font = Font(bold=True)
    ws.cell(row=1, column=4, value=f"АУДИТОРИЯ {classroom.name.upper()}").font = Font(bold=True)

    _write_header_row(ws, _CLASSROOM_HEADERS, row=2)

    rows = []
    for (key_ci, row, col), student in result.seating.items():
        if key_ci != ci:
            continue
        rows.append({
            'num':          global_idx[(key_ci, row, col)],
            'seat':         classroom.get_seat_label(row, col),
            'city':         student.city,
            'municipality': student.municipality,
            'school':       student.school,
            'name':         student.name,
            'grade':        student.grade,
        })
    rows.sort(key=lambda r: r['name'])

    for i, r in enumerate(rows, start=1):
        ws.cell(row=i + 2, column=1, value=r['num'])
        _apply_placeholder_style(ws.cell(row=i + 2, column=2, value=r['municipality']))
        _apply_placeholder_style(ws.cell(row=i + 2, column=3, value=r['city']))
        _apply_placeholder_style(ws.cell(row=i + 2, column=4, value=r['school']))
        _apply_placeholder_style(ws.cell(row=i + 2, column=5, value=r['name']))
        _apply_placeholder_style(ws.cell(row=i + 2, column=6, value=r['grade']))
        ws.cell(row=i + 2, column=7, value=r['seat'])

    _autofit_columns(ws)
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', classroom.name)
    wb.save(os.path.join(output_dir, f"Аудитория_{safe_name}.xlsx"))


# Для учителя

def _export_teacher(result, classrooms, students_df, output_dir: str) -> None:
    from collections import defaultdict
    from core.data_loader import _normalize as _norm

    # Для каждого имени храним список мест — чтобы корректно обрабатывать дубликаты ФИО
    name_to_seats: dict = defaultdict(list)
    for (ci, row, col), student in result.seating.items():
        name_to_seats[student.name].append((
            classrooms[ci].get_seat_label(row, col),
            classrooms[ci].name,
        ))

    name_col = 'ФИО ученика'
    name_counters: dict = defaultdict(int)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Для учителя"

    all_cols = list(students_df.columns) + ['Место', 'Аудитория']
    _write_header_row(ws, all_cols, row=1)

    n_orig = len(students_df.columns)
    for r_idx, (_, df_row) in enumerate(students_df.iterrows(), start=2):
        for c_idx, col_name in enumerate(students_df.columns, start=1):
            val = df_row[col_name]
            ws.cell(row=r_idx, column=c_idx, value=None if str(val) == 'nan' else val)

        raw_name = df_row[name_col] if name_col in students_df.columns else ''
        norm_name = _norm(raw_name)
        seats_list = name_to_seats.get(norm_name, [])
        i = name_counters[norm_name]
        seat_label, classroom_name = seats_list[i] if i < len(seats_list) else ('', '')
        name_counters[norm_name] += 1

        ws.cell(row=r_idx, column=n_orig + 1, value=seat_label)
        ws.cell(row=r_idx, column=n_orig + 2, value=classroom_name)

    _autofit_columns(ws)
    wb.save(os.path.join(output_dir, "Для учителя.xlsx"))


# Вспомогательные

def _write_header_row(ws, headers: list, row: int = 1) -> None:
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = _BORDER


def _autofit_columns(ws) -> None:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                # Учитываем, что кириллица шире латиницы в Excel
                val_str = str(cell.value)
                actual_len = 0
                for char in val_str:
                    if ord(char) > 127:
                        actual_len += 1.4  # Коэффициент для русских букв
                    else:
                        actual_len += 1
                max_len = max(max_len, actual_len)
        ws.column_dimensions[col_letter].width = max_len + 2


def _apply_placeholder_style(cell) -> None:
    """Применяет красный стиль, если в ячейке заглушка"""
    val = str(cell.value).upper() if cell.value is not None else ""
    if val == "НЕИЗВЕСТНО" or val == "-" or val == "0" or val.startswith("УЧАСТНИК"):
        cell.fill = _ERROR_FILL
