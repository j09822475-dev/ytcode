"""Оценка трендовости по собранным данным. Чистая статистика, без внешних сервисов.

Ролик интересен, если он свежий и быстро набирает просмотры (просмотры в час),
у него высокая вовлечённость и он «выстрелил» относительно размера автора
(просмотры / подписчики). Звук или хэштег — тренд, если он встречается во многих
свежих быстрорастущих роликах и число роликов с ним растёт между запусками.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass, field

from .store import Store

# Хэштеги, которые ставят «на всякий случай» — они ничего не говорят о тренде.
GENERIC_TAGS = {
    "fyp", "foryou", "foryoupage", "fy", "fypシ", "fypage", "viral", "trending", "trend",
    "tiktok", "xyzbca", "рекомендации", "рек", "реки", "врек", "рекомендация", "хочуврек",
    "тренд", "тренды", "вирал", "capcut",
}


@dataclass
class ScoredVideo:
    id: str
    url: str
    author: str
    desc: str
    age_hours: float
    plays: int
    views_per_hour: float
    engagement: float
    breakout: float | None
    music_id: str | None
    music_title: str | None
    hashtags: list[str]
    duration: int
    score: float


@dataclass
class Group:
    key: str
    title: str
    videos: int
    median_vph: float
    growth_per_hour: float = 0.0
    total_count: int | None = None
    example_urls: list[str] = field(default_factory=list)
    score: float = 0.0


def engagement_rate(plays: int, likes: int, comments: int, shares: int, saves: int) -> float:
    # Комментарии, репосты и сохранения весят больше лайков: это более сильный сигнал.
    return (likes + 2 * comments + 3 * shares + 2 * saves) / max(plays, 1)


def score_videos(store: Store, lookback_hours: float, now: float | None = None) -> list[ScoredVideo]:
    now = now or time.time()
    out = []
    for r in store.videos_with_latest_stats():
        if not r["create_time"]:
            continue
        age = max((r["snap_ts"] - r["create_time"]) / 3600, 1.0)
        if (now - r["create_time"]) / 3600 > lookback_hours:
            continue
        vph = r["plays"] / age
        eng = engagement_rate(r["plays"], r["likes"], r["comments"], r["shares"], r["saves"])
        breakout = r["plays"] / r["author_followers"] if r["author_followers"] else None
        score = (
            math.log10(1 + vph)
            * (1 + 5 * min(eng, 0.5))
            * (1 + math.log10(1 + min(breakout, 1000)) if breakout else 1.0)
        )
        out.append(
            ScoredVideo(
                id=r["id"],
                url=f"https://www.tiktok.com/@{r['author']}/video/{r['id']}",
                author=r["author"],
                desc=r["desc"],
                age_hours=round(age, 1),
                plays=r["plays"],
                views_per_hour=round(vph),
                engagement=round(eng, 4),
                breakout=round(breakout, 2) if breakout else None,
                music_id=r["music_id"],
                music_title=r["music_title"],
                hashtags=json.loads(r["hashtags"] or "[]"),
                duration=r["duration"],
                score=round(score, 3),
            )
        )
    return sorted(out, key=lambda v: v.score, reverse=True)


def _groups(videos: list[ScoredVideo], keys_of, title_of, min_videos: int) -> dict[str, Group]:
    buckets: dict[str, list[ScoredVideo]] = {}
    for v in videos:
        for k in keys_of(v):
            buckets.setdefault(k, []).append(v)
    groups = {}
    for k, vs in buckets.items():
        if len(vs) < min_videos:
            continue
        vs.sort(key=lambda v: v.score, reverse=True)
        groups[k] = Group(
            key=k,
            title=title_of(vs[0], k),
            videos=len(vs),
            median_vph=round(statistics.median(v.views_per_hour for v in vs)),
            example_urls=[v.url for v in vs[:3]],
        )
    return groups


def _finish(groups: dict[str, Group], growth: dict[str, tuple[float, int]], top_n: int) -> list[Group]:
    for k, g in groups.items():
        if k in growth:
            g.growth_per_hour, g.total_count = round(growth[k][0], 1), growth[k][1]
        g.score = round(
            g.videos * math.log10(1 + g.median_vph) + math.log10(1 + max(g.growth_per_hour, 0)) * 3, 3
        )
    return sorted(groups.values(), key=lambda g: g.score, reverse=True)[:top_n]


def trending_sounds(store: Store, videos: list[ScoredVideo], min_videos: int, top_n: int) -> list[Group]:
    groups = _groups(
        videos,
        lambda v: [v.music_id] if v.music_id else [],
        lambda v, _: v.music_title or "",
        min_videos,
    )
    return _finish(groups, store.growth("sound_snapshots", "sound_id"), top_n)


def trending_hashtags(store: Store, videos: list[ScoredVideo], min_videos: int, top_n: int) -> list[Group]:
    groups = _groups(
        videos,
        lambda v: [t for t in v.hashtags if t not in GENERIC_TAGS],
        lambda _, k: "#" + k,
        min_videos,
    )
    return _finish(groups, store.growth("hashtag_snapshots", "name"), top_n)
