# scripts

Maintenance tools for the chronicle. All of them are safe to run repeatedly:
each keeps its own ledger or output file and picks up where it left off.

Nothing here runs automatically, and nothing here is needed to view the site —
`timeline.html`, `fake-news.html` and `timeline-data.json` stand on their own.

## `scrape-livforum.py`

Pulls the full text of the Liv Forum digests so their reporting can be cited in
the chronicle, and — just as usefully — collects the outbound links inside each
digest, which are the primary sources it summarises.

Run it from a machine that can reach livforum.org. It cannot be run from the
build environment, whose network policy refuses the host.

```sh
python3 scripts/scrape-livforum.py --dry-run     # show the targets
python3 scripts/scrape-livforum.py --delay 2     # fetch; resumable
python3 scripts/scrape-livforum.py --render --thin-only   # for JS-rendered pages
```

The script is self-contained: the 106 known digest URLs (Sept 2024 – July 2026)
are built into it, so downloading the single `.py` and running it from anywhere
works. `livforum-urls.txt` beside it, or `--urls FILE`, overrides that list, and
the crawler walks the sitemap and listing pages for anything newer.

On macOS a python.org build ships no CA bundle and every https request dies
with `CERTIFICATE_VERIFY_FAILED`. The script looks for one — `certifi` first,
then the system bundles — and if it finds none it stops with the fix rather
than retrying: `pip3 install certifi`, or the `Install Certificates.command`
that came with the Python installer, or `--insecure` as a last resort.

Output is `livforum-corpus.jsonl` (`--out` to move it), one record per digest,
with a `quality` field so
that a page which failed to give up its body is reported rather than silently
saved empty. The site's subscribe blurb is removed by frequency — any paragraph
appearing on more than 40% of pages is furniture — so no hand-written selector
has to be maintained.

Be a good guest: keep `--delay` at 1.5s or higher. The script stops on its own
if the site answers 401, 403 or 429.

## `permafy.py`

Mints a Perma.cc permalink for every outbound link in `timeline-data.json` and
writes it back alongside the original URL, so a dead link never takes the
evidence with it. Needs `PERMA_API_KEY`. Start with `--dry-run`; use `--limit`
to stay inside a monthly allowance.

## `fetch-external-images.sh`

Downloads the handful of images that are not served from Wikimedia into
`assets/`, so the page does not depend on a third-party host staying up.
