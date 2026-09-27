from __future__ import annotations

import argparse
import time

from . import report
from .config import Config
from .store import Store


def _collector(cfg: Config, store: Store, base_url: str | None):
    from .collector import BASE, Collector  # Playwright нужен только командам с браузером

    return Collector(cfg, store, base_url or BASE)


def cmd_login(cfg, store, args):
    with _collector(cfg, store, args.base_url) as c:
        if not c.login():
            raise SystemExit(1)


def cmd_collect(cfg, store, args):
    if args.feed is not None:
        cfg.feed_videos = args.feed
    with _collector(cfg, store, args.base_url) as c:
        c.run()


def cmd_report(cfg, store, args):
    rep = report.build(cfg, store)
    out_dir = cfg.data_dir / "reports" / time.strftime("%Y-%m-%d_%H%M")
    frames = {}
    if args.frames and rep["top_videos"]:
        with _collector(cfg, store, args.base_url) as c:
            for v in rep["top_videos"][: cfg.frame_top_videos]:
                try:
                    frames[v.id] = c.frames(v.url, out_dir / "frames" / v.id)
                except Exception as e:  # удалённый/приватный ролик не должен ронять отчёт
                    print(f"  кадры {v.url}: {e}")
    print(f"Отчёт: {report.save(rep, out_dir, frames)}")


def cmd_run(cfg, store, args):
    cmd_collect(cfg, store, args)
    args.frames = True
    cmd_report(cfg, store, args)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="trendbot", description="Поиск трендов TikTok через браузер")
    p.add_argument("--config", default="trendbot.toml")
    p.add_argument("--base-url", help=argparse.SUPPRESS)  # для тестов с локальным макетом сайта
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="открыть браузер и войти в TikTok (один раз)")
    c = sub.add_parser("collect", help="посмотреть ленту, поиск и хэштеги, сохранить данные")
    c.add_argument("--feed", type=int, help="сколько роликов ленты просмотреть")
    r = sub.add_parser("report", help="посчитать тренды и записать отчёт")
    r.add_argument("--frames", action="store_true", help="снять кадры лучших роликов")
    run = sub.add_parser("run", help="collect + report --frames")
    run.add_argument("--feed", type=int)
    args = p.parse_args(argv)

    cfg = Config.load(args.config)
    store = Store(cfg.db_path)
    {"login": cmd_login, "collect": cmd_collect, "report": cmd_report, "run": cmd_run}[args.cmd](
        cfg, store, args
    )


if __name__ == "__main__":
    main()
