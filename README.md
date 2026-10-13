# Auto-updating EZTV RSS (no PC needed)

GitHub Actions refreshes `all_shows.xml` every 30 minutes.

## Flud URL
Use the **raw** link:
```
https://raw.githubusercontent.com/snip3gzuz/eztv-rss/refs/heads/main/all_shows.xml
```

## Edit your shows
Edit `shows.json` in this repo:
- `imdb_id` – e.g. tt27868637
- `title` – any name
- `quality` – Any / 2160p / 1080p / 720p / 480p
- `excluded_seasons` – e.g. [1, 2]

Then commit. The next Action run will rebuild the feed.
