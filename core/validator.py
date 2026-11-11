import re
from dataclasses import dataclass, field
from typing import List, Dict
import pandas as pd


_NAME_COL   = 'ФИО ученика'
_SCHOOL_COL = 'Образовательная организация'
_GRADE_COL  = 'Класс'
_LETTER_COL = 'Буква класса'
_CITY_COL   = 'Город'


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for c1 in s1:
        curr = [prev[0] + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Автоматическая нормализация без диалога."""
    df = df.copy()
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].apply(
            lambda x: re.sub(r'\s+', ' ', str(x).strip())
            if pd.notna(x) and str(x).strip().lower() != 'nan' else x
        )
    if _SCHOOL_COL in df.columns:
        # Убирать пробелы только ПОСЛЕ №: "Гимназия № 1" → "Гимназия №1"
        df[_SCHOOL_COL] = df[_SCHOOL_COL].apply(
            lambda x: re.sub(r'№\s+', '№', str(x)) if pd.notna(x) else x
        )
    if _GRADE_COL in df.columns:
        def _fix_grade(v):
            try:
                return str(int(float(str(v))))
            except Exception:
                return v
        df[_GRADE_COL] = df[_GRADE_COL].apply(_fix_grade)
    if _LETTER_COL in df.columns:
        def _fix_letter(v):
            s = str(v).strip().upper() if pd.notna(v) else ''
            return s[0] if s and s[0].isalpha() else v
        df[_LETTER_COL] = df[_LETTER_COL].apply(_fix_letter)
    # Колонки, полностью состоящие из NaN, pandas оставляет как float64 даже при dtype=str.
    # apply() выше может снова вернуть float64 для всё-NaN колонок.
    # Конвертируем в object в конце, чтобы гарантировать совместимость со строковыми заглушками.
    for col in df.columns:
        if df[col].dtype != object:
            df[col] = df[col].astype(object)
    return df


@dataclass
class ValidationIssue:
    kind: str        # 'full_dup' | 'dup_name' | 'similar_name' | 'similar_school' | 'missing'
    indices: List[int]   # df.index values
    meta: dict = field(default_factory=dict)


def find_issues(df: pd.DataFrame) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    
    # 1. Пропущенные значения (ТЕПЕРЬ ПЕРВЫМ)
    critical = [c for c in [_NAME_COL, _SCHOOL_COL, _GRADE_COL, _LETTER_COL, _CITY_COL] if c in df.columns]
    missing_idx: List[int] = []
    missing_fields: Dict[int, List[str]] = {}
    for idx, row in df.iterrows():
        empty = [
            c for c in critical
            if pd.isna(row.get(c)) or str(row.get(c, '')).strip().lower() in ('', 'nan')
        ]
        if empty:
            missing_idx.append(idx)
            missing_fields[idx] = empty
    if missing_idx:
        issues.append(ValidationIssue('missing', missing_idx, {'fields': missing_fields}))

    key_cols = [c for c in [_NAME_COL, _SCHOOL_COL, _GRADE_COL, _LETTER_COL] if c in df.columns]

    # 2. Полные дубликаты (ФИО + Школа + Класс + Буква)
    full_dup_idx: set = set()
    if key_cols:
        dup_mask = df.duplicated(subset=key_cols, keep=False)
        for _, grp in df[dup_mask].groupby(key_cols, sort=False):
            if len(grp) > 1:
                full_dup_idx.update(grp.index)
                issues.append(ValidationIssue('full_dup', list(grp.index)))

    # 3. Дубликаты ФИО (исключая полные дубликаты)
    if _NAME_COL in df.columns:
        sub = df[~df.index.isin(full_dup_idx)]
        for name, grp in sub.groupby(_NAME_COL, sort=False):
            if len(grp) > 1 and str(name).strip() and not str(name).upper().startswith('УЧАСТНИК'):
                issues.append(ValidationIssue('dup_name', list(grp.index), {'name': str(name)}))

    # 4. Похожие ФИО (Левенштейн ≤ 2)
    if _NAME_COL in df.columns:
        names = [str(n) for n in df[_NAME_COL].dropna().unique() if str(n).strip()]
        # Исключаем заглушки
        names = [n for n in names if not n.upper().startswith('УЧАСТНИК')]
        seen: set = set()
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                n1, n2 = names[i], names[j]
                if abs(len(n1) - len(n2)) > 2:
                    continue
                dist = levenshtein_distance(n1.lower(), n2.lower())
                if 0 < dist <= 2:
                    pair = tuple(sorted([n1, n2]))
                    if pair not in seen:
                        seen.add(pair)
                        idx1 = list(df[df[_NAME_COL] == n1].index)
                        idx2 = list(df[df[_NAME_COL] == n2].index)
                        issues.append(ValidationIssue(
                            'similar_name', idx1 + idx2,
                            {'name1': n1, 'name2': n2, 'dist': dist},
                        ))

    # 5. Похожие названия школ (Левенштейн ≤ 3)
    if _SCHOOL_COL in df.columns:
        schools = [str(s) for s in df[_SCHOOL_COL].dropna().unique() if str(s).strip()]
        seen = set()
        for i in range(len(schools)):
            for j in range(i + 1, len(schools)):
                s1, s2 = schools[i], schools[j]
                if abs(len(s1) - len(s2)) > 3:
                    continue
                dist = levenshtein_distance(s1.lower(), s2.lower())
                if 0 < dist <= 3:
                    pair = tuple(sorted([s1, s2]))
                    if pair not in seen:
                        seen.add(pair)
                        idx1 = list(df[df[_SCHOOL_COL] == s1].index)
                        idx2 = list(df[df[_SCHOOL_COL] == s2].index)
                        issues.append(ValidationIssue(
                            'similar_school', idx1 + idx2,
                            {'school1': s1, 'count1': len(idx1),
                             'school2': s2, 'count2': len(idx2), 'dist': dist},
                        ))

    return issues
