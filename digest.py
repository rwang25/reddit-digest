"""Daily read-only digest of Reddit threads that match a list of topics.

Reads the newest posts and comments in a few subreddits through Reddit's
official API (PRAW, application-only auth), keeps the ones that match a
topic, and writes a markdown list of links to digests/YYYY-MM-DD.md.

It never posts, comments, votes or sends messages. It keeps only the
digest files and a list of ids already shown, and deletes digests older
than `keep_days`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import praw
import yaml


@dataclass(frozen=True)
class Item:
    id: str
    subreddit: str
    kind: str  # "post" or "comment"
    title: str
    text: str
    url: str
    thread_id: str
    created: float


@dataclass(frozen=True)
class Topic:
    name: str
    patterns: tuple[re.Pattern[str], ...]

    def matches(self, text: str) -> bool:
        return any(p.search(text) for p in self.patterns)


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def topics_from(config: dict) -> list[Topic]:
    return [
        Topic(name, tuple(re.compile(p, re.IGNORECASE) for p in patterns))
        for name, patterns in config["topics"].items()
    ]


def match(item: Item, topics: Iterable[Topic]) -> list[str]:
    text = f"{item.title}\n{item.text}"
    return [t.name for t in topics if t.matches(text)]


def reddit_client() -> praw.Reddit:
    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ["REDDIT_USER_AGENT"],
    )
    reddit.read_only = True
    return reddit


def fetch(reddit: praw.Reddit, sub: str, limit: int) -> list[Item]:
    sr = reddit.subreddit(sub)
    items = [
        Item(p.id, sub, "post", p.title, p.selftext or "",
             f"https://www.reddit.com{p.permalink}", p.id, p.created_utc)
        for p in sr.new(limit=limit)
    ]
    for c in sr.comments(limit=limit):
        title = c.link_title if hasattr(c, "link_title") else ""
        items.append(Item(c.id, sub, "comment", title, c.body or "",
                          f"https://www.reddit.com{c.permalink}",
                          c.link_id.removeprefix("t3_"), c.created_utc))
    return items


def my_threads(reddit: praw.Reddit, username: str | None, limit: int = 200) -> set[str]:
    """Threads I've already commented in, from my public comment history."""
    if not username:
        return set()
    return {c.link_id.removeprefix("t3_")
            for c in reddit.redditor(username).comments.new(limit=limit)}


def select(items: list[Item], topics: list[Topic], seen: set[str],
           answered: set[str], since: float) -> list[tuple[Item, list[str]]]:
    picked: dict[str, tuple[Item, list[str]]] = {}
    for item in items:
        if item.id in seen or item.thread_id in answered or item.created < since:
            continue
        names = match(item, topics)
        if names and item.thread_id not in picked:
            picked[item.thread_id] = (item, names)
    return sorted(picked.values(), key=lambda x: x[0].created, reverse=True)


def render(day: dt.date, picked: list[tuple[Item, list[str]]]) -> str:
    lines = [f"# Reddit digest {day.isoformat()}", ""]
    if not picked:
        lines.append("Nothing new matched today.")
    for item, names in picked:
        snippet = " ".join(item.text.split())[:200]
        lines.append(f"- **r/{item.subreddit}** [{item.title or '(comment)'}]({item.url})"
                     f" ({item.kind}; {', '.join(names)})")
        if snippet:
            lines.append(f"  > {snippet}")
    return "\n".join(lines) + "\n"


def prune(folder: Path, today: dt.date, keep_days: int) -> list[Path]:
    removed = []
    for f in folder.glob("*.md"):
        try:
            day = dt.date.fromisoformat(f.stem)
        except ValueError:
            continue
        if (today - day).days > keep_days:
            f.unlink()
            removed.append(f)
    return removed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="config.yaml", type=Path)
    ap.add_argument("--out", default="digests", type=Path)
    args = ap.parse_args()

    config = load_config(args.config)
    topics = topics_from(config)
    args.out.mkdir(exist_ok=True)
    seen_file = args.out / "seen.json"
    seen = set(json.loads(seen_file.read_text())) if seen_file.exists() else set()

    reddit = reddit_client()
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(hours=config.get("lookback_hours", 36))).timestamp()
    items: list[Item] = []
    for sub in config["subreddits"]:
        items += fetch(reddit, sub, config.get("per_sub_limit", 100))
    answered = my_threads(reddit, os.environ.get("REDDIT_USERNAME"))

    picked = select(items, topics, seen, answered, since)
    today = dt.date.today()
    (args.out / f"{today.isoformat()}.md").write_text(render(today, picked))
    seen |= {i.id for i, _ in picked}
    seen_file.write_text(json.dumps(sorted(seen)[-5000:]))
    prune(args.out, today, config.get("keep_days", 30))
    print(f"{len(picked)} threads -> {args.out / (today.isoformat() + '.md')}")


if __name__ == "__main__":
    main()
