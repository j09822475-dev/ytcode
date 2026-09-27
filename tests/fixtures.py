"""Минимальные JSON в форме ответов веб-версии TikTok."""

import time

NOW = int(time.time())


def item(id, plays, hours_ago, *, author="alice", followers=1000, music="m1", music_title="sound one",
         tags=("lifehack",), likes=None, comments=10, shares=5, saves=3, v2=False):
    stats = {"playCount": plays, "diggCount": likes if likes is not None else plays // 10,
             "commentCount": comments, "shareCount": shares, "collectCount": saves}
    d = {
        "id": str(id), "desc": "текст " + " ".join("#" + t for t in tags), "createTime": NOW - hours_ago * 3600,
        "video": {"duration": 15, "cover": "https://example/cover.jpg"},
        "author": {"uniqueId": author, "nickname": author},
        "authorStats": {"followerCount": followers},
        "music": {"id": music, "title": music_title, "original": False},
        "challenges": [{"id": "1", "title": t} for t in tags],
    }
    if v2:
        d["stats"] = {k: 0 for k in stats}
        d["statsV2"] = {k: str(v) for k, v in stats.items()}
    else:
        d["stats"] = stats
    return d


def feed_page(items):
    return {"itemList": items, "hasMore": True}


def search_page(items):
    return {"data": [{"type": 1, "item": i} for i in items]}


def music_detail(music_id, title, video_count):
    return {"__DEFAULT_SCOPE__": {"webapp.music-detail": {"musicInfo": {
        "music": {"id": music_id, "title": title}, "stats": {"videoCount": video_count}}}}}


def challenge_detail(name, video_count, view_count):
    return {"__DEFAULT_SCOPE__": {"webapp.challenge-detail": {"challengeInfo": {
        "challenge": {"id": "9", "title": name}, "statsV2": {"videoCount": str(video_count), "viewCount": str(view_count)}}}}}
