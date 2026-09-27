"""Сквозной тест сборщика на локальном макете сайта: настоящий Chromium, настоящие
перехваты ответов /api/ и HTML-данных страниц, но без обращения к TikTok."""

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytest.importorskip("playwright")

from trendbot.collector import Collector
from trendbot.config import Config
from trendbot.store import Store
from fixtures import challenge_detail, feed_page, item, music_detail, search_page


def rehydrate(data):
    return ('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            + json.dumps(data) + "</script>")


FEED_JS = """<script>
let n = 0;
document.addEventListener('keydown', e => { if (e.key === 'ArrowDown') fetch('/api/recommend/item_list/?n=' + (n++)); });
</script>"""
SCROLL_JS = """<div style="height:20000px"></div><script>
let n = 0;
window.addEventListener('scroll', () => fetch('/api/search/item/full/?n=' + (n++)), {passive: true});
</script>"""


def make_handler(video_file):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype="text/html; charset=utf-8"):
            body = body if isinstance(body, bytes) else body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            p = url.path
            if p == "/foryou":
                self.send("<html><body>" + rehydrate(feed_page([item(1, 50_000, 3)])) + FEED_JS + "</body></html>")
            elif p.startswith("/api/recommend/item_list/"):
                n = int(url.query.split("=")[1])
                self.send(json.dumps(feed_page([item(100 + n, 10_000 * (n + 1), 5, music="hot")])), "application/json")
            elif p == "/search/video":
                self.send("<html><body>" + SCROLL_JS + "</body></html>")
            elif p.startswith("/api/search/item/full/"):
                n = int(url.query.split("=")[1])
                self.send(json.dumps(search_page([item(500 + n, 777, 10, tags=("study",))])), "application/json")
            elif p.startswith("/tag/"):
                self.send("<html>" + rehydrate(challenge_detail("study", 1234, 99_000)) + SCROLL_JS + "</html>")
            elif p.startswith("/music/"):
                self.send("<html>" + rehydrate(music_detail(p.split("-")[-1], "Hot", 4321)) + "</html>")
            elif "/video/" in p:
                self.send('<html><body><video src="/clip.webm" muted preload="auto" width="360" height="640"></video></body></html>')
            elif p == "/clip.webm" and video_file:
                self.send(video_file.read_bytes(), "video/webm")
            else:
                self.send_error(404)
    return H


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    video_file = None
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        video_file = tmp_path_factory.mktemp("v") / "clip.webm"
        subprocess.run([ffmpeg, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=10:duration=8",
                        "-c:v", "libvpx", "-b:v", "300k", str(video_file)], check=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(video_file))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", video_file
    server.shutdown()


def test_collect_run_and_frames(site, tmp_path):
    base, video_file = site
    cfg = Config(keywords=["учёба"], hashtags=["study"], feed_videos=3, search_scrolls=2,
                 watch_seconds=(0.3, 0.4), pause_seconds=(0.3, 0.4), headless=True,
                 frame_timestamps=[0.5, 3.0], data_dir=tmp_path)
    store = Store(cfg.db_path)
    with Collector(cfg, store, base, log=lambda *_: None) as c:
        c.run()
        ids = {r[0] for r in store.db.execute("SELECT id FROM videos")}
        assert "1" in ids                                   # из HTML ленты
        assert {"100", "101", "102"} <= ids                 # из перехваченных /api/ ленты
        assert any(i.startswith("5") for i in ids)          # из выдачи поиска
        tags = store.db.execute("SELECT name, video_count FROM hashtag_snapshots").fetchall()
        assert ("study", 1234) in [tuple(t) for t in tags]
        sounds = store.db.execute("SELECT sound_id, video_count FROM sound_snapshots").fetchall()
        assert ("hot", 4321) in [tuple(s) for s in sounds]  # страница частого звука открыта

        if video_file:
            shots = c.frames(base + "/@alice/video/1", tmp_path / "frames")
            assert len(shots) == 2 and all(s.stat().st_size > 1000 for s in shots)
            assert shots[0].read_bytes() != shots[1].read_bytes()  # кадры действительно из разных моментов
