"""Извлечение роликов, звуков и хэштегов из JSON, который веб-версия TikTok получает в браузер.

Схема ответов TikTok меняется без предупреждения, поэтому парсер не привязан к конкретным
эндпоинтам: он рекурсивно обходит любой JSON и забирает всё, что похоже на ролик
(`id` + `desc` + `author` + `stats`/`statsV2`), страницу звука (`musicInfo`) или
страницу хэштега (`challengeInfo`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

REHYDRATION_RE = re.compile(
    r'<script[^>]+id="(?:__UNIVERSAL_DATA_FOR_REHYDRATION__|SIGI_STATE|__NEXT_DATA__)"[^>]*>(.*?)</script>',
    re.S,
)


@dataclass
class Video:
    id: str
    desc: str
    create_time: int
    duration: int
    author: str
    author_followers: int | None
    music_id: str | None
    music_title: str | None
    music_original: bool | None
    hashtags: list[str]
    plays: int
    likes: int
    comments: int
    shares: int
    saves: int

    @property
    def url(self) -> str:
        return f"https://www.tiktok.com/@{self.author}/video/{self.id}"


@dataclass
class Sound:
    id: str
    title: str
    video_count: int


@dataclass
class Hashtag:
    name: str
    video_count: int | None
    view_count: int | None


@dataclass
class Extracted:
    videos: list[Video] = field(default_factory=list)
    sounds: list[Sound] = field(default_factory=list)
    hashtags: list[Hashtag] = field(default_factory=list)

    def extend(self, other: "Extracted") -> None:
        self.videos.extend(other.videos)
        self.sounds.extend(other.sounds)
        self.hashtags.extend(other.hashtags)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _stat(item: dict, *names: str) -> int:
    """Счётчик из `stats`, а если там 0 — из `statsV2` (где числа приходят строками)."""
    stats = item.get("stats") or {}
    stats_v2 = item.get("statsV2") or {}
    for name in names:
        value = _int(stats.get(name)) or _int(stats_v2.get(name))
        if value:
            return value
    return 0


def _walk(node: Any) -> Iterator[dict]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _looks_like_video(d: dict) -> bool:
    return (
        "id" in d
        and "desc" in d
        and isinstance(d.get("author"), (dict, str))
        and ("stats" in d or "statsV2" in d)
    )


def _video(d: dict) -> Video:
    author = d.get("author")
    author_name = author.get("uniqueId", "") if isinstance(author, dict) else str(author)
    author_stats = d.get("authorStats") or d.get("authorStatsV2") or {}
    followers = _int(author_stats.get("followerCount")) or None
    music = d.get("music") or {}
    tags = {c.get("title", "") for c in d.get("challenges") or []}
    tags |= {t.get("hashtagName", "") for t in d.get("textExtra") or []}
    tags |= set(re.findall(r"#(\w+)", d.get("desc") or ""))
    return Video(
        id=str(d["id"]),
        desc=d.get("desc") or "",
        create_time=_int(d.get("createTime")),
        duration=_int((d.get("video") or {}).get("duration")),
        author=author_name,
        author_followers=followers,
        music_id=str(music["id"]) if music.get("id") else None,
        music_title=music.get("title"),
        music_original=music.get("original"),
        hashtags=sorted(t.lower() for t in tags if t),
        plays=_stat(d, "playCount"),
        likes=_stat(d, "diggCount"),
        comments=_stat(d, "commentCount"),
        shares=_stat(d, "shareCount"),
        saves=_stat(d, "collectCount"),
    )


def extract(payload: Any) -> Extracted:
    out = Extracted()
    seen: set[str] = set()
    for d in _walk(payload):
        if _looks_like_video(d) and str(d["id"]) not in seen:
            seen.add(str(d["id"]))
            out.videos.append(_video(d))
        music_info = d.get("musicInfo")
        if isinstance(music_info, dict) and isinstance(music_info.get("music"), dict):
            m = music_info["music"]
            stats = music_info.get("stats") or {}
            if m.get("id"):
                out.sounds.append(Sound(str(m["id"]), m.get("title", ""), _int(stats.get("videoCount"))))
        challenge_info = d.get("challengeInfo")
        if isinstance(challenge_info, dict) and isinstance(challenge_info.get("challenge"), dict):
            c = challenge_info["challenge"]
            stats = challenge_info.get("statsV2") or challenge_info.get("stats") or {}
            if c.get("title"):
                out.hashtags.append(
                    Hashtag(
                        c["title"].lower(),
                        _int(stats.get("videoCount")) or None,
                        _int(stats.get("viewCount")) or None,
                    )
                )
    return out


def extract_from_html(html: str) -> Extracted:
    """Данные, встроенные в HTML страницы при первой загрузке (ролик, звук, хэштег)."""
    out = Extracted()
    for match in REHYDRATION_RE.finditer(html):
        try:
            out.extend(extract(json.loads(match.group(1))))
        except json.JSONDecodeError:
            continue
    return out
