from trendbot.config import Config
from trendbot.parse import extract
from trendbot.report import build, save
from trendbot.store import Store
from fixtures import NOW, feed_page, item, music_detail


def make_store(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    items = [
        item(1, 200_000, 4, author="small", followers=500, music="hot", music_title="Hot sound", tags=("fyp", "study")),
        item(2, 90_000, 6, author="b", music="hot", music_title="Hot sound", tags=("study",)),
        item(3, 1_000, 48, author="c", music="cold", tags=("study",)),
        item(4, 50_000_000, 24 * 30, author="old", music="cold"),  # старый — вне окна
    ]
    store.save(extract(feed_page(items)), "feed", ts=NOW)
    return store


def test_scoring_prefers_fast_breakout_and_skips_old(tmp_path):
    rep = build(Config(lookback_hours=72, min_videos_per_sound=2), make_store(tmp_path), now=NOW)
    ids = [v.id for v in rep["top_videos"]]
    assert ids[0] == "1" and "4" not in ids
    assert rep["top_videos"][0].breakout == 400


def test_trending_sounds_and_generic_tags_filtered(tmp_path):
    rep = build(Config(min_videos_per_sound=2), make_store(tmp_path), now=NOW)
    assert rep["sounds"][0].key == "hot"
    tags = [g.key for g in rep["hashtags"]]
    assert "study" in tags and "fyp" not in tags


def test_growth_between_snapshots(tmp_path):
    store = make_store(tmp_path)
    store.save(extract(music_detail("hot", "Hot sound", 1000)), "sound", ts=NOW - 10 * 3600)
    store.save(extract(music_detail("hot", "Hot sound", 3000)), "sound", ts=NOW)
    rep = build(Config(min_videos_per_sound=2), store, now=NOW)
    hot = next(g for g in rep["sounds"] if g.key == "hot")
    assert hot.growth_per_hour == 200 and hot.total_count == 3000


def test_report_files(tmp_path):
    rep = build(Config(niche="учёба"), make_store(tmp_path), now=NOW)
    md = save(rep, tmp_path / "out")
    text = md.read_text(encoding="utf-8")
    assert "Трендовые звуки" in text and "Hot sound" in text
    assert (tmp_path / "out" / "trends.json").exists()
