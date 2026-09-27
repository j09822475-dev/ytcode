"""Сбор данных через обычный браузер (Playwright).

Браузер открывается с отдельным постоянным профилем (`data/browser-profile`): вы один раз
входите в свой аккаунт TikTok руками, дальше сессия сохраняется. Сборщик ведёт себя как
обычный зритель — листает ленту, открывает поиск и хэштеги с паузами — и пассивно читает
JSON, который сайт сам загружает в браузер. Капчи и проверки входа не обходятся: при их
появлении сборщик останавливается и ждёт, пока их пройдёт человек.
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path
from urllib.parse import quote, urlparse

from playwright.sync_api import BrowserContext, Page, Response, sync_playwright

from .config import Config
from .parse import Extracted, extract, extract_from_html
from .store import Store

BASE = "https://www.tiktok.com"
# Перемотка к секунде t. Если источник не поддерживает перемотку (нет Range-запросов),
# ролик проигрывается без звука до нужного момента.
SEEK_JS = """async ([el, t]) => {
    el.muted = true;
    el.pause();
    const target = Math.max(0, Math.min(t, (el.duration || t) - 0.1));
    await new Promise(done => {
        el.addEventListener('seeked', done, {once: true});
        el.currentTime = target;
        setTimeout(done, 3000);
    });
    if (Math.abs(el.currentTime - target) > 0.5) {
        await el.play().catch(() => {});
        const deadline = Date.now() + (target + 5) * 1000;
        while (el.currentTime < target && Date.now() < deadline) await new Promise(r => setTimeout(r, 50));
        el.pause();
    }
    return el.currentTime;
}"""
CAPTCHA_SELECTORS = ["#captcha-verify-container", "#captcha_container", "div[class*='captcha']"]


class Collector:
    def __init__(self, cfg: Config, store: Store, base_url: str = BASE, log=print):
        self.cfg = cfg
        self.store = store
        self.base = base_url.rstrip("/")
        self.log = log
        self.buffer = Extracted()
        self._pw = None
        self.ctx: BrowserContext | None = None
        self.page: Page | None = None

    # --- жизненный цикл -------------------------------------------------------------

    def __enter__(self) -> "Collector":
        self._pw = sync_playwright().start()
        self.cfg.profile_dir.mkdir(parents=True, exist_ok=True)
        self.ctx = self._pw.chromium.launch_persistent_context(
            str(self.cfg.profile_dir),
            headless=self.cfg.headless,
            channel=self.cfg.browser_channel or None,
            # Путь к своему Chromium, если браузеры Playwright не установлены (`playwright install chromium`).
            executable_path=os.environ.get("TRENDBOT_CHROMIUM_PATH") or None,
            viewport={"width": 1280, "height": 900},
            locale="ru-RU" if self.cfg.language == "ru" else "en-US",
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.on("response", self._on_response)
        return self

    def __exit__(self, *exc) -> None:
        if self.ctx:
            self.ctx.close()
        if self._pw:
            self._pw.stop()

    # --- перехват данных ------------------------------------------------------------

    def _on_response(self, response: Response) -> None:
        if "/api/" not in response.url or "json" not in (response.headers.get("content-type") or ""):
            return
        try:
            self.buffer.extend(extract(response.json()))
        except Exception:  # тело недоступно (редирект, обрыв) — просто пропускаем
            pass

    def _capture_html(self) -> None:
        try:
            self.buffer.extend(extract_from_html(self.page.content()))
        except Exception:
            pass

    def _flush(self, source: str) -> None:
        # Ответ на последнее действие может ещё идти: даём ему прийти и обработаться.
        self.page.wait_for_timeout(1500)
        data, self.buffer = self.buffer, Extracted()
        new = self.store.save(data, source)
        self.log(
            f"  [{source}] роликов: {len(data.videos)} (новых {new}), "
            f"звуков: {len(data.sounds)}, хэштегов: {len(data.hashtags)}"
        )

    # --- поведение «зрителя» --------------------------------------------------------

    def _pause(self, rng: tuple[float, float] | None = None) -> None:
        # Именно wait_for_timeout, а не time.sleep: во время ожидания Playwright
        # продолжает доставлять события ответов в _on_response.
        self.page.wait_for_timeout(random.uniform(*(rng or self.cfg.pause_seconds)) * 1000)

    def _goto(self, path: str) -> None:
        self.page.goto(self.base + path, wait_until="domcontentloaded")
        self._pause()
        self._wait_for_human_if_blocked()
        self._capture_html()

    def _wait_for_human_if_blocked(self) -> None:
        for sel in CAPTCHA_SELECTORS:
            if self.page.locator(sel).count():
                self.log("⚠ TikTok показал проверку (капча/вход). Пройдите её в окне браузера.")
                self.page.wait_for_selector(sel, state="detached", timeout=0)
                self._pause()
                return

    def _scroll(self, times: int) -> None:
        for _ in range(times):
            self.page.mouse.wheel(0, random.randint(1500, 2500))
            self._pause()

    # --- сценарии -------------------------------------------------------------------

    def login(self) -> None:
        self.page.goto(self.base + "/login")
        input("Войдите в TikTok в открывшемся окне, затем нажмите Enter здесь… ")

    def feed(self, videos: int) -> None:
        self.log(f"Лента «Для вас»: {videos} роликов")
        self._goto("/foryou")
        for _ in range(videos):
            self._pause(self.cfg.watch_seconds)
            self.page.keyboard.press("ArrowDown")
            self._wait_for_human_if_blocked()
        self._flush("feed")

    def search(self, keyword: str) -> None:
        self.log(f"Поиск: {keyword}")
        self._goto(f"/search/video?q={quote(keyword)}")
        self._scroll(self.cfg.search_scrolls)
        self._flush(f"search:{keyword}")

    def tag(self, name: str) -> None:
        self.log(f"Хэштег: #{name}")
        self._goto(f"/tag/{quote(name)}")
        self._scroll(self.cfg.search_scrolls)
        self._flush(f"tag:{name}")

    def sound(self, sound_id: str) -> None:
        self.log(f"Звук: {sound_id}")
        self._goto(f"/music/-{sound_id}")
        self._flush(f"sound:{sound_id}")

    def run(self) -> None:
        """Полный проход: лента → поиск по ключевым словам → хэштеги → страницы частых звуков."""
        self.feed(self.cfg.feed_videos)
        for kw in self.cfg.keywords:
            self.search(kw)
        for tag in self.cfg.hashtags:
            self.tag(tag)
        for sound_id in self._frequent_sounds(self.cfg.sound_pages):
            self.sound(sound_id)

    def _frequent_sounds(self, limit: int) -> list[str]:
        rows = self.store.db.execute(
            """SELECT music_id FROM videos WHERE music_id IS NOT NULL AND create_time > ?
               GROUP BY music_id ORDER BY COUNT(*) DESC LIMIT ?""",
            (int(time.time() - self.cfg.lookback_hours * 3600), limit),
        ).fetchall()
        return [r[0] for r in rows]

    # --- кадры для визуального анализа ----------------------------------------------

    def frames(self, video_url: str, out_dir: Path) -> list[Path]:
        """Снимает кадры ролика в заданные секунды (скриншот плеера, без скачивания видео)."""
        out_dir.mkdir(parents=True, exist_ok=True)
        self._goto(urlparse(video_url).path)
        video = self.page.locator("video").first
        video.wait_for(timeout=20_000)
        shots = []
        for t in self.cfg.frame_timestamps:
            self.page.evaluate(SEEK_JS, [video.element_handle(), t])
            shot = out_dir / f"{t:05.1f}s.png"
            video.screenshot(path=str(shot))
            shots.append(shot)
        self._flush("frames")
        return shots
