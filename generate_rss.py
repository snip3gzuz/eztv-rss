#!/usr/bin/env python3
"""
Generate all_shows.xml from shows.json using the EZTV API.
Designed to run on GitHub Actions (no GUI).
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

SHOWS_FILE = Path("shows.json")
OUT_FILE = Path("all_shows.xml")
EZTV_API = "https://eztvx.to/api/get-torrents"
MAX_PAGES = 10


def rfc2822(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def xml_esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def magnet_id(link: str) -> str:
    m = re.search(r"btih:([a-fA-F0-9]{40})", link or "")
    return m.group(1).lower() if m else (link or "")[:64]


def http_get_json(url: str) -> dict:
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_eztv(imdb_id: str) -> List[dict]:
    numeric = re.sub(r"^tt", "", imdb_id, flags=re.I)
    all_torrents = []
    page = 1
    while page <= MAX_PAGES:
        url = f"{EZTV_API}?imdb_id={numeric}&limit=100&page={page}"
        try:
            data = http_get_json(url)
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError):
            break
        torrents = data.get("torrents") or []
        if not torrents:
            break
        all_torrents.extend(torrents)
        if page * 100 >= int(data.get("torrents_count") or 0):
            break
        page += 1
        time.sleep(0.3)
    return all_torrents


def filter_items(torrents: List[dict], quality: str, excluded: Set[int]) -> List[dict]:
    best: Dict[str, dict] = {}
    for t in torrents:
        filename = t.get("filename") or t.get("title") or ""
        if quality != "Any" and not re.search(rf"\b{re.escape(quality)}\b", filename, re.I):
            continue
        season = int(t.get("season") or 0)
        episode = int(t.get("episode") or 0)
        if season < 1 or episode < 1 or season in excluded:
            continue
        magnet = t.get("magnet_url") or ""
        torrent_url = t.get("torrent_url") or t.get("torrent") or ""
        if not magnet.startswith("magnet:") and not str(torrent_url).startswith("http"):
            continue
        key = f"S{season:02d}E{episode:02d}"
        seeds = int(t.get("seeds") or 0)
        if key not in best or seeds > best[key]["seeds"]:
            best[key] = {
                "title": t.get("title") or filename,
                "magnet": magnet if magnet.startswith("magnet:") else "",
                "torrent_url": torrent_url if str(torrent_url).startswith("http") else "",
                "seeds": seeds,
                "date": int(t.get("date_released_unix") or 0),
            }
    return sorted(best.values(), key=lambda x: x["date"], reverse=True)


def build_rss(shows: List[dict], all_items: Dict[str, List[dict]]) -> str:
    now = rfc2822(int(time.time()))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        "    <title>My EZTV Shows</title>",
        "    <link>https://eztvx.to/</link>",
        "    <description>Auto-updated EZTV feed - highest seeders</description>",
        f"    <lastBuildDate>{now}</lastBuildDate>",
    ]
    flat = []
    for show in shows:
        for item in all_items.get(show["imdb_id"], []):
            flat.append((item, show.get("title") or show["imdb_id"]))
    flat.sort(key=lambda x: x[0]["date"], reverse=True)

    for item, show_title in flat:
        download = item.get("torrent_url") or item.get("magnet") or ""
        link = item.get("magnet") or item.get("torrent_url") or download
        mid = magnet_id(link)
        lines += [
            "    <item>",
            f"      <title>{xml_esc(item['title'])}</title>",
            f"      <link>{xml_esc(link)}</link>",
            f'      <guid isPermaLink="false">{mid}</guid>',
            f"      <pubDate>{rfc2822(item['date'])}</pubDate>",
            f"      <description>{xml_esc(show_title)} | Seeds: {item['seeds']}</description>",
        ]
        if download:
            lines.append(
                f'      <enclosure url="{xml_esc(download)}" type="application/x-bittorrent" length="0" />'
            )
        lines.append("    </item>")
    lines += ["  </channel>", "</rss>"]
    return "\n".join(lines)


def main():
    if not SHOWS_FILE.exists():
        raise SystemExit("shows.json not found")
    shows = json.loads(SHOWS_FILE.read_text(encoding="utf-8"))
    if not shows:
        raise SystemExit("shows.json is empty")

    all_items: Dict[str, List[dict]] = {}
    for show in shows:
        imdb = show["imdb_id"]
        quality = show.get("quality") or "1080p"
        excluded = set(show.get("excluded_seasons") or [])
        print(f"Fetching {show.get('title', imdb)} ({imdb}) [{quality}] ...")
        torrents = fetch_eztv(imdb)
        items = filter_items(torrents, quality, excluded)
        all_items[imdb] = items
        print(f"  -> {len(items)} episodes")

    xml = build_rss(shows, all_items)
    OUT_FILE.write_text(xml, encoding="utf-8")
    total = sum(len(v) for v in all_items.values())
    print(f"Wrote {OUT_FILE} ({total} items)")


if __name__ == "__main__":
    main()
