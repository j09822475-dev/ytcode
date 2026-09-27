"""SQLite-хранилище. Каждое наблюдение ролика/звука/хэштега пишется снимком со временем,
чтобы при повторных запусках считать скорость роста."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .parse import Extracted

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    desc TEXT, create_time INTEGER, duration INTEGER,
    author TEXT, author_followers INTEGER,
    music_id TEXT, music_title TEXT, music_original INTEGER,
    hashtags TEXT,
    source TEXT, first_seen INTEGER
);
CREATE TABLE IF NOT EXISTS video_snapshots (
    video_id TEXT, ts INTEGER,
    plays INTEGER, likes INTEGER, comments INTEGER, shares INTEGER, saves INTEGER,
    PRIMARY KEY (video_id, ts)
);
CREATE TABLE IF NOT EXISTS sound_snapshots (
    sound_id TEXT, ts INTEGER, title TEXT, video_count INTEGER,
    PRIMARY KEY (sound_id, ts)
);
CREATE TABLE IF NOT EXISTS hashtag_snapshots (
    name TEXT, ts INTEGER, video_count INTEGER, view_count INTEGER,
    PRIMARY KEY (name, ts)
);
"""


class Store:
    def __init__(self, path: Path | str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def save(self, data: Extracted, source: str, ts: int | None = None) -> int:
        """Сохраняет извлечённое; возвращает число новых роликов."""
        ts = ts or int(time.time())
        new = 0
        with self.db:
            for v in data.videos:
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        v.id, v.desc, v.create_time, v.duration, v.author, v.author_followers,
                        v.music_id, v.music_title,
                        None if v.music_original is None else int(v.music_original),
                        json.dumps(v.hashtags, ensure_ascii=False), source, ts,
                    ),
                )
                new += cur.rowcount
                if v.author_followers:
                    self.db.execute(
                        "UPDATE videos SET author_followers=? WHERE id=?", (v.author_followers, v.id)
                    )
                self.db.execute(
                    "INSERT OR REPLACE INTO video_snapshots VALUES (?,?,?,?,?,?,?)",
                    (v.id, ts, v.plays, v.likes, v.comments, v.shares, v.saves),
                )
            for s in data.sounds:
                self.db.execute(
                    "INSERT OR REPLACE INTO sound_snapshots VALUES (?,?,?,?)",
                    (s.id, ts, s.title, s.video_count),
                )
            for h in data.hashtags:
                self.db.execute(
                    "INSERT OR REPLACE INTO hashtag_snapshots VALUES (?,?,?,?)",
                    (h.name, ts, h.video_count, h.view_count),
                )
        return new

    def videos_with_latest_stats(self) -> list[sqlite3.Row]:
        return self.db.execute(
            """
            SELECT v.*, s.ts AS snap_ts, s.plays, s.likes, s.comments, s.shares, s.saves
            FROM videos v
            JOIN video_snapshots s ON s.video_id = v.id
            WHERE s.ts = (SELECT MAX(ts) FROM video_snapshots WHERE video_id = v.id)
            """
        ).fetchall()

    def growth(self, table: str, key: str, value: str = "video_count") -> dict[str, tuple[float, int]]:
        """Для каждого ключа: (прирост `value` в час между первым и последним снимком, последнее значение)."""
        rows = self.db.execute(
            f"SELECT {key} AS k, ts, {value} AS v FROM {table} WHERE {value} IS NOT NULL ORDER BY ts"
        ).fetchall()
        first: dict[str, tuple[int, int]] = {}
        last: dict[str, tuple[int, int]] = {}
        for r in rows:
            first.setdefault(r["k"], (r["ts"], r["v"]))
            last[r["k"]] = (r["ts"], r["v"])
        out = {}
        for k, (t1, v1) in last.items():
            t0, v0 = first[k]
            hours = (t1 - t0) / 3600
            out[k] = ((v1 - v0) / hours if hours >= 1 else 0.0, v1)
        return out
