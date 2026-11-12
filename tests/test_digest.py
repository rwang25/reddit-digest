import datetime as dt

from digest import Item, prune, render, select, topics_from

TOPICS = topics_from({"topics": {
    "assignment": ["assign(ed|ment)", "called away"],
    "earnings": ["earnings"],
}})


def item(id, text, thread=None, created=100.0, title=""):
    return Item(id, "options", "post", title, text, f"https://x/{id}",
                thread or id, created)


def test_select_matches_topics_and_skips_seen_answered_and_old():
    items = [
        item("a", "got assigned early on my CC"),
        item("b", "nothing relevant here"),
        item("c", "earnings next week", created=50.0),     # too old
        item("d", "called away below cost"),               # seen
        item("e", "assignment question", thread="t1"),     # answered
        item("f", "earnings and assignment", created=200.0),
    ]
    picked = select(items, TOPICS, seen={"d"}, answered={"t1"}, since=80.0)
    assert [(i.id, names) for i, names in picked] == [
        ("f", ["assignment", "earnings"]),
        ("a", ["assignment"]),
    ]


def test_select_keeps_one_item_per_thread():
    items = [item("a", "assigned", thread="t"), item("b", "earnings", thread="t")]
    assert len(select(items, TOPICS, set(), set(), 0.0)) == 1


def test_render_lists_links_and_handles_empty():
    day = dt.date(2026, 11, 12)
    assert "Nothing new matched" in render(day, [])
    out = render(day, [(item("a", "got assigned", title="CC question"), ["assignment"])])
    assert "[CC question](https://x/a)" in out and "assignment" in out


def test_prune_deletes_only_old_digests(tmp_path):
    for name in ["2026-10-01.md", "2026-11-10.md", "notes.md"]:
        (tmp_path / name).write_text("x")
    prune(tmp_path, dt.date(2026, 11, 12), keep_days=30)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-11-10.md", "notes.md"]
