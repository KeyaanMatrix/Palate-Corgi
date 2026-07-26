"""CLI commands for the enrich package. OWNER: see docs/TRD.md section 2.

Add commands to the COMMANDS dict below. You own this file — nobody else edits
it, so it can never be a merge conflict. Keep 'check' working: `make check`
runs it before every push, and a broken check blocks the whole team's merge.
"""

from . import filestorage_exif, knowledge_base, merge_link


def check(args) -> None:
    article = {
        "title": "Lisbon restaurants",
        "content": "\n".join(
            [
                "- Prado",
                "- O Velho Eurico",
                "- Taberna Sal Grosso",
                "- Ramiro",
                "- A Cevicheria",
            ]
        ),
    }
    assert len(knowledge_base._items(article)) == 5
    assert knowledge_base._items({"title": "Todo", "content": article["content"]}) == []
    assert round(filestorage_exif._coordinate((37, 30, 0), "N"), 4) == 37.5
    assert round(filestorage_exif._coordinate((122, 15, 0), "W"), 4) == -122.25
    print("enrich.check OK (Notion precision gate, EXIF GPS conversion)")


def drive(args) -> None:
    print(f"{filestorage_exif.sync(int(args[0]) if args else 200)} visits")


def notion(args) -> None:
    print(f"{knowledge_base.sync()} intent rows")


def exchange(args) -> None:
    if not args:
        raise SystemExit("usage: python -m palate enrich.exchange <public-token>")
    print(merge_link.exchange_link_token(args[0]))


COMMANDS = {
    "drive": drive,
    "notion": notion,
    "exchange": exchange,
    "check": check,
}
