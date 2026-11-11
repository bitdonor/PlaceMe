import re
from typing import List, Tuple
import pandas as pd
from models.student import Student


def _normalize(text) -> str:
    if pd.isna(text):
        return ""
    return re.sub(r'\s+', ' ', str(text).strip())


def _normalize_grade(value) -> int:
    try:
        num = int(float(value))
        if 1 <= num <= 11:
            return num
    except (ValueError, TypeError):
        pass
    digits = re.findall(r'\d+', str(value))
    if digits:
        return int(digits[0])
    return 0


def _normalize_letter(value) -> str:
    s = _normalize(value).upper()
    if s and s[0].isalpha():
        return s[0]
    return 'А'


def load_students(filepath: str) -> Tuple[List[Student], List[str]]:
    """Загружает участников из xlsx-файла."""
    df = pd.read_excel(filepath, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    df = _normalize_columns(df)
    return df_to_students(df)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит заголовки столбцов к каноническому регистру независимо от того, как они записаны."""
    canonical = {
        'фио ученика':                  'ФИО ученика',
        'образовательная организация':  'Образовательная организация',
        'класс':                        'Класс',
        'город':                        'Город',
        'буква класса':                 'Буква класса',
        'район':                        'Район',
        'критерий знакомства':          'Критерий знакомства',
    }
    lower_to_actual = {c.lower(): c for c in df.columns}
    rename = {
        lower_to_actual[lower]: canon
        for lower, canon in canonical.items()
        if lower in lower_to_actual and lower_to_actual[lower] != canon
    }
    return df.rename(columns=rename) if rename else df


def df_to_students(df: pd.DataFrame) -> Tuple[List[Student], List[str]]:
    """
    Конвертирует DataFrame в список Student.
    Ожидаемые столбцы: 'ФИО ученика', 'Образовательная организация', 'Класс'.
    Опциональные: 'Буква класса', 'Район'.
    """
    warnings: List[str] = []

    required = ['ФИО ученика', 'Образовательная организация', 'Класс', 'Город']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"В файле отсутствуют столбцы: {', '.join(missing)}")

    has_letter        = 'Буква класса' in df.columns
    has_municipality  = 'Район' in df.columns
    has_acquaintance  = 'Критерий знакомства' in df.columns

    students: List[Student] = []
    seen_names: dict = {}

    for idx, row in df.iterrows():
        name         = _normalize(row['ФИО ученика'])
        school       = _normalize(row['Образовательная организация'])
        grade        = _normalize_grade(row['Класс'])
        letter       = _normalize_letter(row['Буква класса']) if has_letter else 'А'
        municipality = _normalize(row['Район']) if has_municipality else ''
        city         = _normalize(row['Город'])
        acquaintance = _normalize(row['Критерий знакомства']) if has_acquaintance else ''

        if not name:
            warnings.append(f"Строка {idx + 2}: пустое ФИО — строка пропущена")
            continue
        if not school:
            warnings.append(f"Строка {idx + 2}: не указана школа для '{name}' — используйте «Проверить список» для исправления")
            school = 'Неизвестно'
        if grade == 0:
            warnings.append(f"Строка {idx + 2}: некорректный класс для '{name}' — используйте «Проверить список» для исправления")
            # grade = 9  <-- УДАЛЕНО, по умолчанию оставляем 0

        if name in seen_names:
            warnings.append(f"Строка {idx + 2}: совпадение ФИО '{name}' — используйте «Проверить список» для разбора дубликатов")
        else:
            seen_names[name] = True

        students.append(Student(
            name=name,
            school=school,
            grade=grade,
            letter=letter,
            municipality=municipality,
            city=city,
            acquaintance=acquaintance,
        ))

    return students, warnings
