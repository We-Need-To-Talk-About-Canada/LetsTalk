#!/usr/bin/env python3
"""Mint a Perma.cc permalink for every outbound link, and record it in the data.

Why: the chronicle rests on links to Baaz, SikhRI, court filings and news
reports. Several of those outlets are small, and one of them - Baaz - has
already been the target of a documented campaign to have its consulates
investigation de-indexed and deleted (see the Playbook, technique 09). A link
that dies takes the evidence with it. Perma.cc keeps a citable copy.

    Usage
    -----
    export PERMA_API_KEY=...                 # from perma.cc → Settings → Developer
    python3 scripts/permafy.py --dry-run     # show what would be archived
    python3 scripts/permafy.py --folder 12345
    python3 scripts/permafy.py --limit 10    # stay inside a monthly allowance

    What it does
    ------------
    * collects every distinct http(s) URL in timeline-data.json - event sources,
      playbook sources, and the url/pdf on each reference record
    * skips any that already has a permalink in the ledger
    * POSTs each to the Perma API, waits for capture to finish, and records it
    * writes `perma` alongside `url` everywhere that URL appears
    * keeps scripts/perma-links.json as the ledger, so re-running is cheap,
      resumable, and never re-archives something twice

    Safety
    ------
    * nothing is written to timeline-data.json until every archive in the run
      has succeeded or been accounted for
    * a URL that fails to archive keeps its plain link; it is never dropped and
      never given a made-up permalink
    * --dry-run touches no network and no files

    Cost
    ----
    Perma.cc gives unaffiliated users a small number of links per month; an
    account through a subscribing library or a paid tier lifts that. This
    chronicle has ~112 distinct URLs, so plan for either one run on an
    unlimited account or several months of --limit runs.
"""
import argparse, json, os, re, sys, time, urllib.parse
import urllib.request, urllib.error

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(HERE)
DATA   = os.path.join(ROOT, 'timeline-data.json')
LEDGER = os.path.join(HERE, 'perma-links.json')
API    = 'https://api.perma.cc/v1'

# Links that are already archives, or that are DOIs. A DOI is a permanent
# identifier by design and the publisher is obliged to keep it resolving;
# archiving one adds nothing.
SKIP_HOSTS = {'perma.cc', 'web.archive.org', 'doi.org', 'dx.doi.org'}


# ---------------------------------------------------------------- collection
def walk(data):
    """Yield (container_dict, key) for every field holding an outbound URL."""
    for e in data.get('events', []):
        for s in e.get('sources', []):
            if s.get('url'):
                yield s, 'url'
    for t in data.get('playbook', []) + [data.get('playbook_closing') or {}]:
        for s in t.get('sources', []):
            if s.get('url'):
                yield s, 'url'
    for r in data.get('references', {}).values():
        for k in ('url', 'pdf'):
            if r.get(k):
                yield r, k


def archivable(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    host = host[4:] if host.startswith('www.') else host
    return url.startswith(('http://', 'https://')) and host not in SKIP_HOSTS


# -------------------------------------------------------------------- ledger
def load_ledger():
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_ledger(led):
    with open(LEDGER, 'w', encoding='utf-8') as f:
        json.dump(led, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')


# ----------------------------------------------------------------------- API
def api(path, key, payload=None, method=None):
    url = f'{API}{path}'
    sep = '&' if '?' in url else '?'
    url = f'{url}{sep}api_key={urllib.parse.quote(key)}'
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=body, method=method or ('POST' if body else 'GET'),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode() or '{}')


def archive(url, key, folder=None, tries=3):
    """Create one Perma link and wait for the capture to settle."""
    payload = {'url': url}
    path = f'/archives/?folder={folder}' if folder else '/archives/'
    last = None
    for attempt in range(1, tries + 1):
        try:
            rec = api(path, key, payload)
            guid = rec.get('guid')
            if not guid:
                raise RuntimeError(f'no guid in response: {rec}')
            # poll until the capture stops being "pending"
            for _ in range(20):
                status = rec.get('status') or ''
                if status and status != 'pending':
                    break
                time.sleep(3)
                rec = api(f'/archives/{guid}/', key)
            return f'https://perma.cc/{guid}', rec.get('status', 'unknown')
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors='replace')[:300]
            last = f'HTTP {e.code}: {detail}'
            if e.code in (401, 403):
                raise SystemExit(f'Perma rejected the API key ({last})')
            if e.code == 429:                      # over the allowance
                raise SystemExit(f'Perma rate limit / quota reached: {last}')
        except Exception as e:                      # noqa: BLE001 - report and retry
            last = str(e)
        if attempt < tries:
            time.sleep(2 ** attempt)
    return None, last


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true',
                    help='list what would be archived; no network, no writes')
    ap.add_argument('--limit', type=int, default=0,
                    help='archive at most N new URLs this run (0 = no cap)')
    ap.add_argument('--folder', type=int, default=None,
                    help='Perma folder id to file the links under')
    ap.add_argument('--relink-only', action='store_true',
                    help='write permalinks already in the ledger into the data; no new archiving')
    args = ap.parse_args()

    data = json.load(open(DATA, encoding='utf-8'))
    ledger = load_ledger()

    fields = list(walk(data))
    urls = sorted({o[k] for o, k in fields if archivable(o[k])})
    skipped = sorted({o[k] for o, k in fields if not archivable(o[k])})
    todo = [u for u in urls if u not in ledger]

    print(f'link fields in the data : {len(fields)}')
    print(f'distinct URLs           : {len(urls)}')
    print(f'already in the ledger   : {len(urls) - len(todo)}')
    print(f'to archive              : {len(todo)}')
    if skipped:
        print(f'skipped (already permanent): {len(skipped)}')
        for u in skipped:
            print(f'    {u}')

    if args.dry_run:
        print('\n--dry-run: nothing was archived or written\n')
        for u in todo:
            print(f'    {u}')
        return

    if not args.relink_only and todo:
        key = os.environ.get('PERMA_API_KEY')
        if not key:
            raise SystemExit(
                'PERMA_API_KEY is not set.\n'
                'Get one at perma.cc → Settings → Developer, then:\n'
                '    export PERMA_API_KEY=...\n'
                'Or run with --relink-only to apply permalinks already in the ledger.')
        batch = todo[:args.limit] if args.limit else todo
        print(f'\narchiving {len(batch)} URL(s)...\n')
        failed = []
        for i, u in enumerate(batch, 1):
            link, status = archive(u, key, args.folder)
            if link:
                ledger[u] = {'perma': link, 'status': status,
                             'archived': time.strftime('%Y-%m-%d')}
                save_ledger(ledger)            # checkpoint every time
                print(f'  [{i}/{len(batch)}] {link}  {status:<10} {u[:70]}')
            else:
                failed.append((u, status))
                print(f'  [{i}/{len(batch)}] FAILED  {u[:70]}\n        {status}')
        if failed:
            print(f'\n{len(failed)} URL(s) could not be archived and keep their plain link.')

    # ---- write the permalinks into the data ----
    applied = 0
    for obj, k in fields:
        rec = ledger.get(obj[k])
        if rec and obj.get('perma') != rec['perma']:
            obj['perma'] = rec['perma']
            applied += 1
    json.dump(data, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # ---- validate ----
    d2 = json.load(open(DATA, encoding='utf-8'))
    n_perma = 0
    for obj, k in walk(d2):
        if obj.get('perma'):
            assert obj['perma'].startswith('https://perma.cc/'), obj
            n_perma += 1
    covered = len({o[k] for o, k in walk(d2) if o.get('perma')})
    print(f'\nwrote {applied} permalink field(s)')
    print(f'link fields now carrying a permalink: {n_perma}/{len(list(walk(d2)))}')
    print(f'distinct URLs covered               : {covered}/{len(urls)}')
    if covered < len(urls):
        print('\nremaining, in ledger order - rerun to pick them up:')
        for u in urls:
            if u not in ledger:
                print(f'    {u}')


if __name__ == '__main__':
    main()
