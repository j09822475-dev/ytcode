import json

from trendbot.parse import extract, extract_from_html
from fixtures import challenge_detail, feed_page, item, music_detail, search_page


def test_extracts_videos_from_feed_and_search_shapes():
    data = extract(feed_page([item(1, 5000, 2)]))
    data.extend(extract(search_page([item(2, 100, 5, tags=("a", "B"))])))
    assert [v.id for v in data.videos] == ["1", "2"]
    v = data.videos[1]
    assert v.hashtags == ["a", "b"]
    assert v.plays == 100 and v.author == "alice" and v.author_followers == 1000 and v.music_id == "m1"


def test_stats_v2_string_counters():
    v = extract(feed_page([item(1, 12345, 1, v2=True)])).videos[0]
    assert v.plays == 12345 and v.shares == 5


def test_duplicate_items_counted_once():
    assert len(extract({"a": [item(1, 1, 1)], "b": {"x": item(1, 1, 1)}}).videos) == 1


def test_sound_and_hashtag_pages_from_html():
    html = (
        '<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        + json.dumps({**music_detail("m1", "sound one", 4200)["__DEFAULT_SCOPE__"],
                      **challenge_detail("Лайфхак", 900, 10**6)["__DEFAULT_SCOPE__"]})
        + "</script></html>"
    )
    data = extract_from_html(html)
    assert [(s.id, s.video_count) for s in data.sounds] == [("m1", 4200)]
    assert [(h.name, h.video_count, h.view_count) for h in data.hashtags] == [("лайфхак", 900, 10**6)]


def test_ignores_garbage():
    assert extract({"id": 1, "desc": "no author"}).videos == []
    assert extract_from_html('<script id="SIGI_STATE">{broken</script>').videos == []
