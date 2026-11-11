import os
import base64
import statistics
from io import BytesIO
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from models.student import Student
from models.classroom import Classroom
from algorithms.base import AlgorithmResult
from algorithms.greedy import GreedyAlgorithm
from algorithms.annealing import AnnealingAlgorithm
from algorithms.genetic import GeneticAlgorithm
from core.penalty import get_base_penalty
from algorithms.max_annealing import find_worst_penalty


RUNS_PER_ALGO = 10

ALGO_MAP = [
    ("Жадный",       GreedyAlgorithm),
    ("Отжиг",        AnnealingAlgorithm),
    ("Генетический", GeneticAlgorithm),
]

COLORS = {
    'Жадный':       '#2196F3',
    'Отжиг':        '#FF5722',
    'Генетический': '#4CAF50',
}

PENALTY_CATEGORIES = [
    (70, 'side', '#b71c1c', 'Одноклассники, боковой (70)'),
    (70, 'diag', '#ef5350', 'Одноклассники, диагональный (35)'),
    (30, 'side', '#e65100', 'Параллельники, боковой (30)'),
    (30, 'diag', '#ff8a65', 'Параллельники, диагональный (15)'),
    (10, 'side', '#f9a825', 'Одна школа, боковой (10)'),
    (10, 'diag', '#f0c030', 'Одна школа, диагональный (5)'),
]


def run_all_and_report(
    students: List[Student],
    classrooms: List[Classroom],
    output_dir: str,
    progress_callback=None,
    stop_event=None,
) -> Dict[str, AlgorithmResult]:
    from export.excel_exporter import export_combined

    os.makedirs(output_dir, exist_ok=True)

    total = len(ALGO_MAP) * RUNS_PER_ALGO
    done = 0
    all_runs: Dict[str, List[AlgorithmResult]] = {}

    for label, AlgoClass in ALGO_MAP:
        all_runs[label] = []
        for i in range(RUNS_PER_ALGO):
            if progress_callback:
                progress_callback(done / total * 0.95, f"{label}: запуск {i + 1}/{RUNS_PER_ALGO}...")
            if stop_event and stop_event.is_set():
                raise InterruptedError("Отменено пользователем")
            r = AlgoClass(students, classrooms, stop_event=stop_event).run()
            all_runs[label].append(r)
            done += 1

    best = _find_best(all_runs)

    SUBFOLDERS = {
        'Жадный':       'Жадный алгоритм',
        'Отжиг':        'Имитация отжига',
        'Генетический': 'Генетический алгоритм',
    }
    for label, runs in all_runs.items():
        subfolder = os.path.join(output_dir, SUBFOLDERS.get(label, label))
        for i, r in enumerate(runs):
            export_combined(r, classrooms, subfolder, filename=f"{i + 1}.xlsx")

    if progress_callback:
        progress_callback(0.96, "Вычисление опорного максимума штрафа...")
    worst_penalty = find_worst_penalty(students, classrooms)

    if progress_callback:
        progress_callback(0.97, "Генерация отчёта...")

    html_path = os.path.join(output_dir, "сравнение.html")
    _generate_html(all_runs, best, classrooms, html_path, worst_penalty)

    if progress_callback:
        progress_callback(1.0, "Готово")

    return {label: r for label, (r, _) in best.items()}


def _find_best(
    all_runs: Dict[str, List[AlgorithmResult]],
) -> Dict[str, Tuple[AlgorithmResult, int]]:
    best: Dict[str, Tuple[AlgorithmResult, int]] = {}
    for label, runs in all_runs.items():
        bi = 0
        for i in range(1, len(runs)):
            a, b = runs[bi], runs[i]
            if b.total_penalty < a.total_penalty:
                bi = i
            elif b.total_penalty == a.total_penalty and b.elapsed_seconds < a.elapsed_seconds:
                bi = i
        best[label] = (runs[bi], bi + 1)
    return best


def _penalty_breakdown(result: AlgorithmResult, classrooms: List[Classroom]) -> Dict[tuple, float]:
    totals: Dict[tuple, float] = {(bp, nt): 0.0 for bp, nt, _, _ in PENALTY_CATEGORIES}
    seating = result.seating
    for (ci, row, col), s1 in seating.items():
        cr = classrooms[ci]
        for n_row, n_col, n_type in cr.get_neighbors(row, col):
            if (n_row, n_col) <= (row, col):
                continue
            s2 = seating.get((ci, n_row, n_col))
            if s2 is None:
                continue
            bp = get_base_penalty(s1, s2)
            if bp == 0:
                continue
            coeff = 1.0 if n_type == 'side' else 0.5
            totals[(bp, n_type)] = totals.get((bp, n_type), 0.0) + bp * coeff
    return totals


def _fig_to_base64(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def _chart_stability(all_runs: Dict[str, List[AlgorithmResult]]) -> str:
    fig, ax = plt.subplots(figsize=(10, 4))
    labels = list(all_runs.keys())

    for i, label in enumerate(labels):
        color = COLORS.get(label, '#888')
        vals = [r.total_penalty for r in all_runs[label]]
        x_base = i + 1

        n = len(vals)
        x_pos = np.linspace(x_base - 0.22, x_base + 0.22, n) if n > 1 else np.array([x_base])
        ax.scatter(x_pos, vals, color=color, s=50, alpha=0.85, zorder=3)

        if vals:
            mean_val = statistics.mean(vals)
            ax.hlines(mean_val, x_base - 0.24, x_base + 0.24,
                      colors=color, linewidths=3, zorder=4)

    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_xlim(0.4, len(labels) + 0.6)
    ax.set_ylabel("Итоговый штраф")
    ax.grid(True, axis='y', alpha=0.3)
    plt.tight_layout()
    fig.subplots_adjust(left=0.10, right=0.90)
    return _fig_to_base64(fig)


def _chart_convergence_run(run_results: Dict[str, AlgorithmResult], worst_penalty: float) -> str:
    fig, ax = plt.subplots(figsize=(6, 3))
    for label, result in run_results.items():
        if not result.history:
            continue
        h = result.history
        n = len(h)
        xs = [i / max(n - 1, 1) * 100 for i in range(n)]
        ax.plot(xs, h, color=COLORS.get(label), linewidth=1.5)
    ax.set_xlabel("Прогресс, %", fontsize=9)
    ax.set_ylabel("Штраф", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=8)
    plt.tight_layout()

    # Вставная таблица: итоговый штраф по алгоритмам
    labels_in    = list(run_results.keys())
    penalties_in = [run_results[l].total_penalty for l in labels_in]

    ax_in = ax.inset_axes([0.65, 0.43, 0.33, 0.55])
    ax_in.set_xticks([])
    ax_in.set_yticks([])
    for sp in ax_in.spines.values():
        sp.set_linewidth(0.5)
        sp.set_color('#aaa')
    ax_in.patch.set_facecolor('white')
    ax_in.patch.set_alpha(0.88)

    T  = ax_in.transAxes
    fs = 6.5

    ax_in.text(0.50, 0.875, 'Итоговый штраф', fontsize=fs, fontweight='bold',
               ha='center', va='center', transform=T, color='#111')
    ax_in.plot([0.03, 0.97], [0.79, 0.79], color='#888', linewidth=0.8, transform=T)

    ax_in.text(0.04, 0.72, 'Алгоритм', fontsize=fs - 0.5, ha='left',  va='center', transform=T, color='#444')
    ax_in.text(0.68, 0.72, 'сумма',    fontsize=fs - 0.5, ha='right', va='center', transform=T, color='#444')
    ax_in.text(0.99, 0.72, '% от max', fontsize=fs - 0.5, ha='right', va='center', transform=T, color='#444')
    ax_in.plot([0.03, 0.97], [0.635, 0.635], color='#888', linewidth=0.8, transform=T)

    row_y     = [0.515, 0.295, 0.075]
    divider_y = [0.405, 0.185]
    for idx, (lbl, p) in enumerate(zip(labels_in, penalties_in)):
        y     = row_y[idx]
        pct_v = p / worst_penalty * 100 if worst_penalty > 0 else 0.0
        color = COLORS.get(lbl, '#888')
        ax_in.plot([0.04], [y], 'o', color=color, markersize=5, transform=T, clip_on=False)
        ax_in.text(0.10, y, lbl,             fontsize=fs, ha='left',  va='center', transform=T, color='#111')
        ax_in.text(0.68, y, f'{p:.0f}',      fontsize=fs, ha='right', va='center', transform=T, color='#111')
        ax_in.text(0.99, y, f'{pct_v:.1f}%', fontsize=fs, ha='right', va='center', transform=T, color='#111')
        if idx < len(divider_y):
            ax_in.plot([0.03, 0.97], [divider_y[idx]] * 2,
                       color='#ddd', linewidth=0.5, transform=T)

    return _fig_to_base64(fig)


def _chart_penalty_run(
    run_results: Dict[str, AlgorithmResult],
    classrooms: List[Classroom],
    worst_penalty: float,
) -> str:
    fig, ax = plt.subplots(figsize=(6, 3))
    algo_keys = list(run_results.keys())
    y_pos = np.arange(len(algo_keys))
    breakdowns = [_penalty_breakdown(run_results[k], classrooms) for k in algo_keys]

    # Предварительно считаем общий максимум для оценки ширины текста
    _pre_totals = np.zeros(len(algo_keys))
    for _bp, _nt, _c, _ in PENALTY_CATEGORIES:
        _pre_totals += np.array([bd.get((_bp, _nt), 0.0) for bd in breakdowns])
    total_max_pre = float(np.max(_pre_totals)) if np.any(_pre_totals > 0) else 1.0
    # Приблизительная полуширина текста в единицах данных (≈4 символа при данном масштабе)
    text_hw = total_max_pre * 0.045

    BAR_H = 0.55
    # Для каждой строки (алгоритма) отслеживаем правый край последнего текста
    last_right = np.zeros(len(algo_keys))

    lefts = np.zeros(len(algo_keys))
    for bp, nt, color, _ in PENALTY_CATEGORIES:
        vals = np.array([bd.get((bp, nt), 0.0) for bd in breakdowns])
        ax.barh(y_pos, vals, left=lefts, color=color, height=BAR_H)
        for i, v in enumerate(vals):
            if v > 0:
                pct_v = v / worst_penalty * 100 if worst_penalty > 0 else 0.0
                ideal_x = lefts[i] + v / 2
                # Не уходим за левый край и не налезаем на предыдущий текст
                x = max(ideal_x, last_right[i] + text_hw)
                last_right[i] = x + text_hw
                # ось Y инвертирована: -0.12 визуально сверху, +0.12 снизу
                ax.text(x, y_pos[i] - 0.12, f'{v:.0f}',
                        ha='center', va='center', fontsize=7.5, color='white', fontweight='bold')
                ax.text(x, y_pos[i] + 0.12, f'{pct_v:.1f}%',
                        ha='center', va='center', fontsize=7.5, color='white', fontweight='bold')
        lefts += vals

    total_max = float(np.max(lefts)) if np.any(lefts > 0) else 0.0
    bar_w = total_max if total_max > 0 else 1.0
    for i, total in enumerate(lefts):
        if total == 0:
            ax.barh(y_pos[i], bar_w, left=0, color=COLORS['Генетический'], height=BAR_H)
            ax.text(bar_w / 2, y_pos[i] - 0.12, '0',
                    ha='center', va='center', fontsize=7.5, color='white', fontweight='bold')
            ax.text(bar_w / 2, y_pos[i] + 0.12, '0.0%',
                    ha='center', va='center', fontsize=7.5, color='white', fontweight='bold')
    if total_max == 0:
        ax.set_xticks(np.linspace(0, 1, 6))
        ax.set_xticklabels(['0.0'] * 6, fontsize=8)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(algo_keys, fontsize=9)
    ax.set_xlabel("Суммарный штраф", fontsize=9)
    ax.grid(True, axis='x', alpha=0.3)
    ax.invert_yaxis()
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    return _fig_to_base64(fig)


def _generate_html(
    all_runs: Dict[str, List[AlgorithmResult]],
    best: Dict[str, Tuple[AlgorithmResult, int]],
    classrooms: List[Classroom],
    output_path: str,
    worst_penalty: float,
) -> None:
    labels = list(all_runs.keys())

    chart_stability = _chart_stability(all_runs)

    run_charts: List[Tuple[str, str]] = []
    for i in range(RUNS_PER_ALGO):
        run_results = {label: all_runs[label][i] for label in labels}
        run_charts.append((
            _chart_convergence_run(run_results, worst_penalty),
            _chart_penalty_run(run_results, classrooms, worst_penalty),
        ))

    html = _render_html(all_runs, best, chart_stability, run_charts, worst_penalty)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def _render_html(
    all_runs: Dict[str, List[AlgorithmResult]],
    best: Dict[str, Tuple[AlgorithmResult, int]],
    chart_stability: str,
    run_charts: List[Tuple[str, str]],
    worst_penalty: float,
) -> str:
    def img(b64: str) -> str:
        return f'<img src="data:image/png;base64,{b64}" style="max-width:100%;border-radius:6px;display:block;">'

    labels = list(all_runs.keys())

    def _pct_str(penalty: float) -> str:
        if worst_penalty > 0:
            return f"&nbsp;&nbsp;|&nbsp;&nbsp;{penalty / worst_penalty * 100:.1f}%"
        return "&nbsp;&nbsp;|&nbsp;&nbsp;—"

    # Лучшие результаты
    best_penalties = [best[label][0].total_penalty for label in labels]
    best_times     = [best[label][0].elapsed_seconds for label in labels]
    min_penalty    = min(best_penalties)
    min_time       = min(best_times)

    best_rows = ""
    for label in labels:
        r, attempt = best[label]
        badge_q = ' <span class="badge-green">Лучший штраф</span>' if r.total_penalty == min_penalty else ''
        badge_t = ' <span class="badge-blue">Быстрейший</span>'    if r.elapsed_seconds == min_time   else ''
        best_rows += f"""
        <tr>
          <td><b>{label}</b></td>
          <td>{r.total_penalty:.1f}{_pct_str(r.total_penalty)}{badge_q}</td>
          <td>{r.elapsed_seconds:.2f} с{badge_t}</td>
          <td style="text-align:center">{attempt}</td>
        </tr>"""

    # Статистика
    stats_rows = ""
    for label in labels:
        runs = all_runs[label]
        penalties = [r.total_penalty   for r in runs]
        times     = [r.elapsed_seconds for r in runs]
        avg_p = statistics.mean(penalties)
        avg_t = statistics.mean(times)
        min_p = min(penalties)
        max_p = max(penalties)
        stats_rows += f"""
        <tr>
          <td>{label}</td>
          <td>{avg_p:.1f}{_pct_str(avg_p)}</td>
          <td>{min_p:.1f}{_pct_str(min_p)}</td>
          <td>{max_p:.1f}{_pct_str(max_p)}</td>
          <td>{avg_t:.2f} с</td>
        </tr>"""

    # Легенда состава штрафов
    legend_items = ""
    for _, _, color, label in PENALTY_CATEGORIES:
        legend_items += f'<span class="leg-item"><span class="leg-color" style="background:{color}"></span>{label}</span>'
    legend_items += f'<span class="leg-item" style="grid-column: 1 / -1"><span class="leg-color" style="background:{COLORS["Генетический"]}"></span>Удалось рассадить участников без нарушений (0)</span>'

    _CONV_NAMES = {
        'Жадный':       'ЖАДНЫЙ АЛГОРИТМ С ЛОКАЛЬНЫМ ПОИСКОМ',
        'Отжиг':        'ИМИТАЦИЯ ОТЖИГА',
        'Генетический': 'ГЕНЕТИЧЕСКИЙ АЛГОРИТМ',
    }

    # Легенда сходимости (по алгоритмам)
    conv_legend = ""
    for label in labels:
        color = COLORS.get(label, '#888')
        full = _CONV_NAMES.get(label, label.upper())
        conv_legend += f'<span class="conv-item"><span class="conv-line" style="background:{color}"></span>{full}</span>'

    def run_img(b64: str) -> str:
        return f'<img src="data:image/png;base64,{b64}" style="width:100%;border-radius:6px;display:block;">'

    # Сетка запусков
    run_rows = ""
    for i, (conv_b64, penalty_b64) in enumerate(run_charts):
        run_rows += f"""
        <div class="run-label">{i + 1}</div>
        <div>{run_img(conv_b64)}</div>
        <div>{run_img(penalty_b64)}</div>"""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Сравнение алгоритмов рассадки</title>
<style>
  body         {{ font-family: 'Segoe UI', sans-serif; max-width: 1100px; margin: 0 auto;
                  padding: 32px 24px; background: #f5f7fa; color: #222; }}
  h1           {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px;
                  margin-bottom: 10px; text-align: center; }}
  h2           {{ color: #283593; text-align: center; margin-top: 44px; margin-bottom: 6px; font-size: 1.25em; }}
  .intro       {{ text-align: center; color: #555; font-size: 0.93em; margin-bottom: 28px; text-transform: uppercase; letter-spacing: 0.05em; }}
  .footnote    {{ color: #666; font-size: 0.83em; margin-top: 8px; line-height: 1.6; }}
  table        {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px;
                  overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.1); margin-bottom: 10px; }}
  caption      {{ caption-side: top; font-weight: bold; font-size: 1.05em; color: #1a237e;
                  padding: 10px 0 6px; text-align: left; }}
  th           {{ background: #3f51b5; color: white; padding: 11px 16px; text-align: left;
                  font-size: 0.92em; line-height: 1.4; }}
  th small     {{ display: block; font-weight: normal; font-size: 0.82em; opacity: 0.88; margin-top: 2px; }}
  td           {{ padding: 10px 16px; border-bottom: 1px solid #e8e8e8; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge-green {{ background: #43a047; color: white; font-size: 11px; padding: 2px 8px;
                  border-radius: 10px; margin-left: 6px; font-weight: normal; }}
  .badge-blue  {{ background: #1e88e5; color: white; font-size: 11px; padding: 2px 8px;
                  border-radius: 10px; margin-left: 6px; font-weight: normal; }}
  .card        {{ background: white; border-radius: 10px; padding: 16px 20px;
                  box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 10px; }}
  .section-hdr {{ background: #3f51b5; color: white; border-radius: 8px 8px 0 0;
                  padding: 12px 20px; font-size: 1.1em; font-weight: bold;
                  text-align: center; margin-top: 48px; }}
  .col-hdr     {{ display: grid; grid-template-columns: 36px 1fr 1fr; gap: 8px;
                  background: #e8eaf6; padding: 8px 16px; font-weight: 600;
                  color: #283593; font-size: 0.88em; text-align: center; }}
  .col-hdr-sub {{ font-weight: normal; font-size: 0.82em; color: #555; }}
  .runs-grid   {{ display: grid; grid-template-columns: 36px 1fr 1fr; gap: 8px;
                  background: white; border-radius: 0 0 10px 10px; padding: 10px 16px;
                  box-shadow: 0 2px 8px rgba(0,0,0,.08); align-items: center; }}
  .runs-grid > div {{ min-width: 0; }}
  .run-label   {{ text-align: center; color: #3f51b5; font-size: 1em;
                  font-weight: bold; padding: 2px 0; }}
  .stab-legend {{ display: flex; gap: 24px; justify-content: center; margin-bottom: 10px; flex-wrap: wrap; }}
  .sl-item     {{ display: flex; align-items: center; gap: 7px; font-size: 0.88em; color: #333; }}
  .sl-line     {{ width: 26px; height: 4px; background: #333; border-radius: 2px; flex-shrink: 0; }}
  .sl-dot      {{ width: 11px; height: 11px; background: #333; border-radius: 50%; flex-shrink: 0; }}
  .conv-legend {{ display: flex; flex-direction: column; gap: 5px; align-items: flex-start; margin: 6px 0 12px; padding-left: 8px; }}
  .conv-item   {{ display: flex; align-items: center; gap: 6px; font-size: 0.81em; color: #333; white-space: nowrap; text-transform: uppercase; letter-spacing: 0.04em; }}
  .conv-line   {{ width: 22px; height: 3px; border-radius: 2px; flex-shrink: 0; }}
  .leg-row     {{ display: grid; grid-template-columns: repeat(2, max-content); gap: 4px 20px; margin: 6px 0 12px; padding-left: 32px; }}
  .leg-item    {{ display: flex; align-items: center; gap: 6px; font-size: 0.81em; color: #333; white-space: nowrap; }}
  .leg-color   {{ width: 13px; height: 13px; border-radius: 3px; flex-shrink: 0; }}
</style>
</head>
<body>

<h1>Сравнительный анализ алгоритмов пространственной оптимизации</h1>
<p class="intro">Каждый алгоритм запущен {RUNS_PER_ALGO} раз на одних и тех же данных</p>

<table>
  <caption>Наилучшие результаты по алгоритмам</caption>
  <thead>
    <tr>
      <th>Алгоритм</th>
      <th>Итоговый штраф<small>сумма&nbsp;&nbsp;|&nbsp;&nbsp;% от max</small></th>
      <th>Время выполнения</th>
      <th style="text-align:center">№ попытки</th>
    </tr>
  </thead>
  <tbody>{best_rows}</tbody>
</table>

<h2>Стабильность результатов</h2>
<div class="card" style="display:flex;flex-direction:column;align-items:center;">
  <div class="stab-legend">
    <span class="sl-item"><span class="sl-line"></span>Среднее</span>
    <span class="sl-item"><span class="sl-dot"></span>Один запуск</span>
  </div>
  {img(chart_stability)}
</div>

<table>
  <thead>
    <tr>
      <th>Алгоритм</th>
      <th>Средний штраф<small>сумма&nbsp;&nbsp;|&nbsp;&nbsp;% от max</small></th>
      <th>Минимальный штраф<small>сумма&nbsp;&nbsp;|&nbsp;&nbsp;% от max</small></th>
      <th>Максимальный штраф<small>сумма&nbsp;&nbsp;|&nbsp;&nbsp;% от max</small></th>
      <th>Среднее время</th>
    </tr>
  </thead>
  <tbody>{stats_rows}</tbody>
</table>
<p class="footnote">
  Минимальный и максимальный штраф — лучший и худший результат среди {RUNS_PER_ALGO} запусков алгоритма
</p>
<table>
  <caption>Опорный максимум штрафа (max)</caption>
  <tbody>
    <tr>
      <td style="font-size:1.4em;font-weight:bold;color:#1a237e;white-space:nowrap;width:1%;padding-right:28px">{worst_penalty:.1f}</td>
      <td style="font-size:0.87em;color:#444;line-height:1.6">Верхняя граница суммарного штрафа
      для данного состава участников и конфигурации аудиторий, полученная методом имитации отжига на максимизацию.
      Принята за 100% при расчёте показателей в таблицах и графиках.
      Является приближённой оценкой и может незначительно отличаться от теоретического абсолютного максимума.</td>
    </tr>
  </tbody>
</table>

<div class="section-hdr">Детальный анализ по запускам</div>
<div class="col-hdr">
  <div>Запуск</div>
  <div>Динамика улучшения решения<br><span class="col-hdr-sub">Как снижается штраф по ходу работы алгоритма</span></div>
  <div>Итоговый состав штрафов по видам нарушений.<br><span class="col-hdr-sub">Цифра внутри — величина штрафа за данный тип нарушения</span></div>
</div>
<div class="runs-grid">
  <div></div>
  <div class="conv-legend">{conv_legend}</div>
  <div class="leg-row">{legend_items}</div>
  {run_rows}
</div>

</body>
</html>"""
