# reddit-digest

A small, read-only script that lists new Reddit threads about topics I answer,
so I can find them and reply by hand.

Once a day it reads the newest posts and comments in a few subreddits through
Reddit's official API, keeps the ones that match a topic in `config.yaml`, and
writes a list of links to `digests/YYYY-MM-DD.md`.

## What it does not do

- It never posts, comments, votes, sends messages or acts on any account. It
  uses application-only (read-only) authentication: no Reddit password is used.
- It doesn't scrape pages; everything goes through the API with a descriptive
  user agent, at a few hundred requests a day.
- It keeps only the digest files and a list of ids already shown, deletes
  digests after `keep_days` (30), and doesn't share, sell or train on any data.

## Setup

1. Create a "script" app at https://www.reddit.com/prefs/apps (once your API
   access is approved) and note its client id and secret.
2. `cp .env.example .env` and fill in the values. `.env` is git-ignored.
3. Install and run:

   ```bash
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   set -a; . ./.env; set +a
   python digest.py
   ```

4. Optional, once a day at 8:00 with cron (`crontab -e`):

   ```
   0 8 * * * cd /path/to/reddit-digest && set -a && . ./.env && set +a && .venv/bin/python digest.py
   ```

## Configure

Edit `config.yaml`: `subreddits`, and `topics` (a name and a list of
case-insensitive regular expressions). If `REDDIT_USERNAME` is set, threads
you've already commented in are skipped.

## Tests

```bash
pip install pytest && python -m pytest -q
```

MIT licensed.
