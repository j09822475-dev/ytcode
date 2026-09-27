"""Отчёт о трендах: Markdown для чтения (человеком или Claude) и JSON для программ."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from .config import Config
from .store import Store
from .trends import Group, ScoredVideo, score_videos, trending_hashtags, trending_sounds


def build(cfg: Config, store: Store, now: float | None = None) -> dict:
    videos = score_videos(store, cfg.lookback_hours, now)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(now)),
        "niche": cfg.niche,
        "videos_considered": len(videos),
        "top_videos": videos[: cfg.top_n],
        "sounds": trending_sounds(store, videos, cfg.min_videos_per_sound, cfg.top_n),
        "hashtags": trending_hashtags(store, videos, cfg.min_videos_per_sound, cfg.top_n),
    }


def _fmt(n: float | None) -> str:
    if n is None:
        return "—"
    for div, suf in ((1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{n / div:.1f}{suf}"
    return f"{n:.0f}" if isinstance(n, float) else str(n)


def _groups_table(groups: list[Group]) -> list[str]:
    lines = [
        "| # | Название | Роликов у нас | Медиана просм./час | Прирост роликов/час | Всего роликов | Примеры |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, g in enumerate(groups, 1):
        examples = " ".join(f"[{j}]({u})" for j, u in enumerate(g.example_urls, 1))
        lines.append(
            f"| {i} | {g.title or g.key} | {g.videos} | {_fmt(g.median_vph)} | "
            f"{_fmt(g.growth_per_hour) if g.growth_per_hour else '—'} | {_fmt(g.total_count)} | {examples} |"
        )
    return lines


def to_markdown(rep: dict, frames: dict[str, list[Path]] | None = None, base: Path | None = None) -> str:
    frames = frames or {}
    out = [
        f"# Тренды TikTok — {rep['generated_at']}",
        "",
        f"Ниша: **{rep['niche'] or 'не задана'}** · свежих роликов в анализе: {rep['videos_considered']}",
        "",
        "## Ролики, которые сейчас «выстреливают»",
        "",
    ]
    for i, v in enumerate(rep["top_videos"], 1):
        v: ScoredVideo
        out += [
            f"### {i}. @{v.author} — score {v.score}",
            f"{v.url}",
            "",
            f"- Возраст: {v.age_hours} ч · просмотров: {_fmt(v.plays)} · в час: {_fmt(v.views_per_hour)}",
            f"- Вовлечённость: {v.engagement:.1%} · просмотры/подписчики: {v.breakout if v.breakout else '—'}",
            f"- Длина: {v.duration} c · звук: {v.music_title or '—'}",
            f"- Хэштеги: {' '.join('#' + t for t in v.hashtags) or '—'}",
            f"- Описание: {v.desc[:300]}",
        ]
        for shot in frames.get(v.id, []):
            out.append(f"- Кадр: `{shot.relative_to(base) if base else shot}`")
        out.append("")
    out += ["## Трендовые звуки", ""] + _groups_table(rep["sounds"])
    out += ["", "## Трендовые хэштеги", ""] + _groups_table(rep["hashtags"])
    out += [
        "",
        "## Как читать",
        "",
        "- **просм./час** — скорость набора просмотров с момента публикации.",
        "- **просмотры/подписчики > 1** — ролик разошёлся далеко за пределы аудитории автора: формат, а не известность.",
        "- **Прирост роликов/час** — считается между запусками; запускайте сбор регулярно, чтобы он появился.",
    ]
    return "\n".join(out) + "\n"


def save(rep: dict, out_dir: Path, frames: dict[str, list[Path]] | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "report.md"
    md.write_text(to_markdown(rep, frames, out_dir), encoding="utf-8")
    serializable = {k: [asdict(x) for x in v] if isinstance(v, list) else v for k, v in rep.items()}
    (out_dir / "trends.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return md
