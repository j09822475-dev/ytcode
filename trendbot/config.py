from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    niche: str = ""
    language: str = "ru"
    keywords: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    feed_videos: int = 40
    search_scrolls: int = 4
    watch_seconds: tuple[float, float] = (3, 8)
    pause_seconds: tuple[float, float] = (2, 5)
    headless: bool = False
    browser_channel: str = ""
    sound_pages: int = 5
    lookback_hours: float = 72
    min_videos_per_sound: int = 2
    top_n: int = 15
    frame_top_videos: int = 8
    frame_timestamps: list[float] = field(default_factory=lambda: [0.5, 2.5, 6.0])
    data_dir: Path = Path("data")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "trendbot.sqlite"

    @property
    def profile_dir(self) -> Path:
        return self.data_dir / "browser-profile"

    @classmethod
    def load(cls, path: Path | str = "trendbot.toml") -> "Config":
        path = Path(path)
        if not path.exists():
            return cls()
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        ch, co, tr, fr = (raw.get(k, {}) for k in ("channel", "collect", "trends", "frames"))
        cfg = cls()
        cfg.niche = ch.get("niche", cfg.niche)
        cfg.language = ch.get("language", cfg.language)
        cfg.keywords = co.get("keywords", cfg.keywords)
        cfg.hashtags = [h.lstrip("#") for h in co.get("hashtags", cfg.hashtags)]
        cfg.feed_videos = co.get("feed_videos", cfg.feed_videos)
        cfg.search_scrolls = co.get("search_scrolls", cfg.search_scrolls)
        cfg.watch_seconds = tuple(co.get("watch_seconds", cfg.watch_seconds))
        cfg.pause_seconds = tuple(co.get("pause_seconds", cfg.pause_seconds))
        cfg.headless = co.get("headless", cfg.headless)
        cfg.browser_channel = co.get("browser_channel", cfg.browser_channel)
        cfg.sound_pages = co.get("sound_pages", cfg.sound_pages)
        cfg.lookback_hours = tr.get("lookback_hours", cfg.lookback_hours)
        cfg.min_videos_per_sound = tr.get("min_videos_per_sound", cfg.min_videos_per_sound)
        cfg.top_n = tr.get("top_n", cfg.top_n)
        cfg.frame_top_videos = fr.get("top_videos", cfg.frame_top_videos)
        cfg.frame_timestamps = fr.get("timestamps", cfg.frame_timestamps)
        if "data_dir" in raw:
            cfg.data_dir = Path(raw["data_dir"])
        return cfg
