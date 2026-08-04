#!/usr/bin/env python3
"""Pull the full text of every Liv Forum digest, for citation in the chronicle.

Why this exists: livforum.org is not reachable from the environment the
chronicle is built in - the network policy answers 403 to CONNECT - so this
runs on a machine that can reach the site. It is written to be run by a human
with permission from Liv Forum, and it behaves like one: one request at a
time, a real delay between them, and it stops the moment the site says no.

    Usage
    -----
    python3 scripts/scrape-livforum.py --dry-run       # list what it would fetch
    python3 scripts/scrape-livforum.py                 # fetch everything, resumable
    python3 scripts/scrape-livforum.py --render        # for client-rendered pages
    python3 scripts/scrape-livforum.py --limit 10 --delay 3

    The file needs nothing beside it: the 106 known digest URLs are built in,
    so downloading this one script on its own and running it works. A
    livforum-urls.txt next to it, or --urls FILE, overrides the built-in list.

    On macOS, a python.org build has no CA bundle and every request fails with
    CERTIFICATE_VERIFY_FAILED. The script looks for a bundle (certifi, then the
    system ones) before giving up, and tells you how to fix it if it cannot
    find one. --insecure skips verification when nothing else is available.

    Output
    ------
    scripts/livforum-corpus.jsonl - one record per digest:

        url, title, date (ISO), category, body, paragraphs[], links[],
        word_count, extractor, quality, http_status, fetched_at

    `links` is the point of the exercise as much as `body`: each digest cites
    the reporting it summarises, and those outbound links are what the
    chronicle can actually cite.

    Why the previous scrape came back empty
    ---------------------------------------
    The earlier pass captured the same ~200 characters on all 146 records -
    the subscribe blurb and the privacy line - which is the signature of one
    of two things: a selector that matched the page shell instead of the
    article, or a body that is rendered in the browser and simply is not in
    the HTML the server sends. This script handles both:

      * it does not use a hand-written selector at all. It scores every block
        in the document by how much prose it holds against how much of that
        prose is link text, and takes the winner. JSON-LD `articleBody` and
        Next.js `__NEXT_DATA__` are checked first when present, since those
        are exact rather than heuristic.
      * boilerplate is removed statistically, not by pattern: any paragraph
        that shows up on more than 40% of the pages fetched is site furniture
        by definition, and is dropped in a second pass. That catches the
        subscribe blurb without anybody having to name it.
      * if a page still comes back thin, it is marked `needs_render`. Re-run
        with --render and it is loaded in a real browser instead.

    Anything still thin after that is reported at the end by URL, so nothing
    fails quietly.
"""
import argparse, html, json, os, re, ssl, sys, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, 'livforum-corpus.jsonl')
SEED = os.path.join(HERE, 'livforum-urls.txt')

HOST  = 'livforum.org'
ROOTS = ['https://livforum.org/', 'https://livforum.org/digest',
         'https://livforum.org/reports', 'https://livforum.org/sitemap.xml']
UA    = ('Mozilla/5.0 (compatible; VirasatChronicle/1.0; '
         'Sikh history chronicle; contact via github.com/We-Need-To-Talk-About-Canada/LetsTalk)')

# a page with less than this much prose did not give us the article
MIN_WORDS = 120
# a paragraph appearing on more than this share of pages is site furniture
BOILER_SHARE = 0.40

DROP_TAGS  = {'script', 'style', 'nav', 'header', 'footer', 'form', 'aside',
              'noscript', 'svg', 'button', 'select', 'iframe'}
VOID_TAGS  = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
              'link', 'meta', 'param', 'source', 'track', 'wbr'}
TEXT_TAGS  = {'p', 'li', 'blockquote', 'h2', 'h3', 'h4'}
MONTHS = ('january february march april may june july august september '
          'october november december').split()


# ------------------------------------------------------------------ fetching
# A python.org build of Python on macOS ships with no CA bundle of its own and
# does not read the system keychain, so every https request fails with
# CERTIFICATE_VERIFY_FAILED until somebody runs Install Certificates.command.
# Rather than make that a prerequisite, look for a bundle in the usual places.
def ssl_context(insecure=False):
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:
        import certifi                                  # optional dependency
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    for path in ('/etc/ssl/cert.pem',                   # macOS system bundle
                 '/opt/homebrew/etc/ca-certificates/cert.pem',
                 '/usr/local/etc/openssl@3/cert.pem',
                 '/usr/local/etc/openssl@1.1/cert.pem',
                 '/etc/ssl/certs/ca-certificates.crt',  # debian/ubuntu
                 '/etc/pki/tls/certs/ca-bundle.crt'):   # fedora/rhel
        if os.path.exists(path):
            try:
                return ssl.create_default_context(cafile=path)
            except Exception:
                continue
    return ssl.create_default_context()                 # whatever python has


CTX = None                                              # set once in main()

CERT_HELP = """
  TLS certificate verification failed, which usually means this Python has no
  CA bundle rather than anything being wrong with the site. Pick one:

      pip3 install certifi                 # simplest; the script finds it
      "/Applications/Python 3.x/Install Certificates.command"   # macOS installer
      python3 scripts/scrape-livforum.py --insecure             # last resort

  --insecure skips verification entirely. Only reasonable here because the
  digests are public pages whose text is checked against other sources anyway.
"""


def get(url, timeout=30, tries=4):
    """One GET, with backoff. Returns (status, text). Never raises on 4xx/5xx."""
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en',
    })
    delay = 2
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                raw = r.read()
                enc = r.headers.get_content_charset() or 'utf-8'
                return r.status, raw.decode(enc, 'replace')
        except urllib.error.HTTPError as e:
            # 429 and 5xx are worth another go; 403/404 are answers, not faults
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(delay); delay *= 2; continue
            return e.code, ''
        except Exception as e:                       # DNS, TLS, timeout, reset
            # a missing CA bundle will not fix itself on the next try, and
            # retrying it four times per URL just hides the real problem
            if 'CERTIFICATE_VERIFY_FAILED' in str(e):
                raise CertError(str(e))
            if attempt < tries - 1:
                time.sleep(delay); delay *= 2; continue
            print(f'    ! {type(e).__name__}: {e}', file=sys.stderr)
            return 0, ''
    return 0, ''


class CertError(Exception):
    """Raised instead of retrying when the machine has no usable CA bundle."""


class Renderer:
    """Optional Playwright browser, opened once and reused."""
    def __init__(self):
        from playwright.sync_api import sync_playwright   # optional dependency
        self._pw = sync_playwright().start()
        # CHROME_PATH lets you point at a Chromium you already have rather than
        # letting playwright download its own
        exe = os.environ.get('CHROME_PATH') or None
        self.browser = self._pw.chromium.launch(executable_path=exe)
        self.page = self.browser.new_page(user_agent=UA)

    def get(self, url):
        try:
            resp = self.page.goto(url, wait_until='networkidle', timeout=45000)
            self.page.wait_for_timeout(600)            # late hydration
            return (resp.status if resp else 0), self.page.content()
        except Exception as e:
            print(f'    ! render failed: {e}', file=sys.stderr)
            return 0, ''

    def close(self):
        try: self.browser.close(); self._pw.stop()
        except Exception: pass


# ------------------------------------------------------------------- parsing
class Node:
    __slots__ = ('tag', 'attrs', 'kids', 'parent', 'text')

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, attrs or {}, parent
        self.kids, self.text = [], ''

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()


class Tree(HTMLParser):
    """A tolerant DOM-lite. Enough to score blocks; not a browser."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self.cur = self.root
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TAGS:
            self.skip += 1
            return
        if self.skip or tag in VOID_TAGS:
            return
        n = Node(tag, dict(attrs), self.cur)
        self.cur.kids.append(n)
        self.cur = n

    def handle_endtag(self, tag):
        if tag in DROP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag in VOID_TAGS:
            return
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root and n.parent:
            self.cur = n.parent

    def handle_data(self, data):
        if not self.skip and data.strip():
            n = Node('#text', parent=self.cur)
            n.text = data
            self.cur.kids.append(n)


def text_of(node):
    parts = []
    for n in node.walk():
        if n.tag == '#text':
            parts.append(n.text)
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


def blocks_of(node):
    """The prose paragraphs inside a node, in document order."""
    out = []
    for n in node.walk():
        if n.tag in TEXT_TAGS:
            t = text_of(n)
            if len(t) > 1:
                out.append(t)
    # a <li> inside a <p> would be counted twice; de-dupe conservatively
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t); uniq.append(t)
    return uniq


def link_text_len(node):
    return sum(len(text_of(n)) for n in node.walk() if n.tag == 'a')


def score(node):
    """Prose wins; navigation, which is mostly link text, does not."""
    paras = blocks_of(node)
    body = sum(len(p) for p in paras)
    if body < 200 or len(paras) < 2:
        return 0
    density = link_text_len(node) / max(body, 1)
    hint = 0
    ident = ' '.join([node.attrs.get('class', ''), node.attrs.get('id', '')]).lower()
    if node.tag in ('article', 'main'):
        hint = 0.35
    elif re.search(r'\b(content|article|post|entry|body|prose|rich[-_]?text)', ident):
        hint = 0.2
    elif re.search(r'\b(nav|menu|sidebar|footer|header|subscribe|banner|cookie)', ident):
        hint = -0.6
    return body * (1 + hint) * max(0.05, 1 - density * 1.6)


def structured_body(doc):
    """Exact extraction, when the page hands it to us. Beats any heuristic."""
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
                         doc, re.S | re.I):
        try:
            data = json.loads(html.unescape(m.group(1)).strip())
        except Exception:
            continue
        for obj in (data if isinstance(data, list) else
                    data.get('@graph', [data]) if isinstance(data, dict) else []):
            if isinstance(obj, dict) and obj.get('articleBody'):
                return 'ld+json', str(obj['articleBody'])
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', doc, re.S)
    if m:
        try:
            blob = json.dumps(json.loads(m.group(1)))
            hit = re.search(r'"(?:body|content|articleBody)":"((?:[^"\\]|\\.){400,})"', blob)
            if hit:
                return '__NEXT_DATA__', json.loads('"' + hit.group(1) + '"')
        except Exception:
            pass
    return None, ''


def extract(doc, url):
    """Return (paragraphs, links, extractor_name)."""
    tree = Tree()
    try:
        tree.feed(doc)
    except Exception:
        pass

    best, best_score = None, 0
    for n in tree.root.walk():
        if n.tag in ('#text', '#root') or n.tag in VOID_TAGS:
            continue
        s = score(n)
        if s > best_score:
            best, best_score = n, s

    how, exact = structured_body(doc)
    if exact and len(exact.split()) >= MIN_WORDS:
        paras = [p.strip() for p in re.split(r'\n{1,}|(?<=\.)\s{2,}', exact) if p.strip()]
        links = links_in(best, url) if best is not None else []
        return paras, links, how

    if best is None:
        return [], [], 'none'
    return blocks_of(best), links_in(best, url), 'scored-block'


def links_in(node, base):
    out, seen = [], set()
    for n in node.walk():
        if n.tag != 'a':
            continue
        href = (n.attrs.get('href') or '').strip()
        if not href or href.startswith(('#', 'mailto:', 'javascript:')):
            continue
        u = urllib.parse.urljoin(base, href)
        if urllib.parse.urlparse(u).hostname in (HOST, 'www.' + HOST):
            continue                                   # internal, not a source
        if u in seen:
            continue
        seen.add(u)
        out.append({'url': u, 'text': text_of(n)[:200]})
    return out


def page_title(doc):
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', doc, re.I)
    if m:
        return clean_title(html.unescape(m.group(1)))
    m = re.search(r'<title[^>]*>(.*?)</title>', doc, re.S | re.I)
    return clean_title(html.unescape(m.group(1))) if m else ''


def clean_title(t):
    """Drop the site name a <title> usually carries: 'Headline | Liv Forum'."""
    t = re.sub(r'\s+', ' ', t).strip()
    return re.sub(r'\s*[|–—·-]\s*Liv\s*Forum\s*$', '', t, flags=re.I).strip()


def page_date(doc):
    for pat in (r'"datePublished"\s*:\s*"([^"]+)"',
                r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"',
                r'<time[^>]+datetime="([^"]+)"'):
        m = re.search(pat, doc, re.I)
        if m:
            return m.group(1)[:10]
    m = re.search(r'\b(\d{1,2})\s*([A-Za-z]{3,9})\s*(\d{4})\b', doc)
    if m and m.group(2).lower() in [x[:len(m.group(2))] for x in MONTHS]:
        mo = next(i for i, x in enumerate(MONTHS) if x.startswith(m.group(2).lower())) + 1
        return f'{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}'
    return ''


# ----------------------------------------------------------------- discovery
# The 106 digests known as of July 2026, as "date slug". Embedded so the
# script works on its own when downloaded without livforum-urls.txt beside
# it; the file, if present, wins, and the crawler finds anything newer.
EMBEDDED_SEEDS = """\
2024-09-04 digest/akal-takht-declares-sukhbir-singh-badal-guilty-of-religious-misconduct
2024-09-11 digest/panjabs-fiscal-health-deteriorates-in-22-23-law-passed-against-illegal-colonies
2024-09-18 digest/rahul-gandhi-visits-us-remark-on-sikhs-kicks-up-furore
2024-09-25 digest/cm-mann-reshuffles-cabinet-amid-protests-haryana-election-campaign
2024-10-02 digest/panjab-cm-recovers-panchayat-elections-announced
2024-10-09 digest/paddy-procurement-woes
2024-10-16 digest/diplomatic-fracas-as-canada-names-verma-person-of-interest-in-nijjar-killing
2024-10-23 digest/india-claims-arrest-of-ex-raw-officer-hindu-group-lobbying-in-us
2024-10-30 digest/india-china-opt-for-border-conflict-resolution-us-raises-concern-on-pannun-plot
2024-11-06 digest/canada-accuses-indias-home-minister-of-targeting-sikhs
2024-11-13 digest/trudeau-condemns-brampton-hindu-sikh-clashes-arrests-made
2024-11-20 digest/panjab-leaders-unite-against-chandigarh-land-allocation-to-haryana
2024-11-27 digest/panjab-by-polls-aap-wins-3-inc-wins-1
2024-12-04 digest/badal-publicly-confesses-mistakes-late-cm-badals-faqr-e-qaum-revoked
2024-12-11 digest/dallewals-health-worsens-haryana-police-thwart-2-attempts-to-march-to-delhi
2024-12-18 digest/police-thwarts-3rd-attempt-by-farmers-to-delhi-dallewal-critical
2024-12-25 digest/sad-misses-akal-takht-deadline-sgpc-suspends-giani-harpreet-singh
2025-01-01 digest/former-indian-pm-manmohan-singh-dies-leaves-behind-a-mixed-legacy
2025-01-08 digest/two-massive-mahapanchayats-signs-of-solidarity-between-farmers-unions
2025-01-14 reports/panjab-agrarian-crisis-2025
2025-01-15 digest/uapa-on-amritpal-his-father-launches-political-party
2025-01-22 digest/independents-are-key-winners-in-haryana-gurdwara-elections
2025-01-29 digest/panjab-ranks-18th-among-indian-states-on-fiscal-health-index
2025-02-05 digest/indian-media-misreads-canadian-report-absolves-india-in-nijjar-killing-case
2025-02-12 digest/sgpc-removes-takht-damdama-sahib-jathedar-giani-harpreet-singh
2025-02-19 digest/delhi-court-convicts-sajjan-kumar-for-1984-sikh-killings
2025-02-26 digest/delhi-court-sentences-sajjan-kumar-to-double-life-imprisonment
2025-03-04 digest/panjab-govt-rejects-draft-npfam-skm-lauds-move
2025-03-12 digest/sgpc-removes-takht-jathedars-sikh-community-outraged
2025-03-18 digest/dhami-withdraws-resignation-damdami-taksal-opposes-jathedar-removal
2025-03-25 digest/cm-mann-betrays-farmers-leaders-police-evicts-protesters
2025-03-26 reports/panjab-cordon-search-operations-in-last-3-years
2025-04-01 digest/panjabs-budget-presented-total-liabilities-estimated-at-usd-44-2b
2025-04-08 digest/trump-imposes-reciprocal-tariff-panjab-basmati-farmers-hit
2025-04-15 digest/badal-returns-as-sad-president
2025-04-22 digest/panjab-extends-mp-amritpal-singhs-nsa-detention-by-1-year
2025-04-29 digest/kashmir-pahalgam-attack-reminds-sikhs-of-chittisinghpora-massacre
2025-05-06 digest/panjab-assembly-guards-waters-but-resolutions-leave-much-desired
2025-05-13 digest/trump-announces-indo-pak-ceasefire-pre-empts-modis-address
2025-05-20 digest/india-to-send-multi-nation-delegations-us-to-tax-nri-remittances
2025-05-27 digest/akal-takht-pardons-dhadrianwale-takhts-challenge-each-others-authority
2025-06-03 digest/bjp-offers-tribute-to-operation-blue-star-martyrs-later-deletes-post
2025-06-10 digest/blue-star-anniversary-peaceful-giani-gargajj-refrains-from-making-speech
2025-06-17 digest/canada-modi-attends-g7-summit-jagmeet-faced-threats
2025-06-24 digest/arora-wins-panjabs-ludhiana-west-sad-does-not-gain-voter-confidence
2025-07-01 digest/sad-leader-majithia-arrested-opposition-cries-foul
2025-07-03 reports/panjab-river-waters-2025
2025-07-08 digest/akal-takht-reverses-patna-takht-decision-badal-detained
2025-07-15 digest/cm-mann-proposes-chenab-water-for-panjab
2025-07-23 digest/sad-announces-tarn-taran-by-poll-candidate
2025-07-30 digest/direct-affront-to-sikhi-says-dhami-on-guru-teghbahadars-anniversary-event
2025-08-06 digest/trump-says-india-will-face-25-tariff-plus-penalty-for-trading-with-russia
2025-08-12 digest/farmers-win-panjab-withdraws-land-pooling-policy
2025-08-20 digest/sisodias-remarks-trigger-political-storm-in-panjab
2025-08-26 digest/flood-situation-grim-in-panjab-red-alert-sounded
2025-09-02 digest/panjab-flood-toll-29-lives-lost-16k-people-evacuated-300k-acres-crops-destroyed
2025-09-09 digest/panjab-flood-toll-51-lives-lost-387k-people-displaced-528k-acres-crops-destroyed
2025-09-16 digest/india-bars-sikhs-from-visiting-nanakana-sahib-akal-takht-website-for-flood-relief
2025-09-22 reports/2025-panjab-floods-relief-rebuilding
2025-09-23 digest/indian-supreme-court-asks-states-to-frame-rules-for-anand-marriage-act
2025-09-30 digest/panjab-passes-resolution-blasting-india-over-floods
2025-10-07 digest/india-allows-sikhs-to-visit-nankana-sahib-with-caveats
2025-10-14 digest/veteran-inc-leader-chidambaram-says-operation-blue-star-was-wrong
2025-10-21 digest/dig-bhullar-arrest-shatters-aaps-anti-corruption-image
2025-10-28 digest/sikh-groups-ratify-jathedar-gargajj-dsgmc-sacks-former-presidents
2025-11-04 digest/bjp-celebrates-patels-birthday-as-unity-day-on-sikh-genocide-anniversary
2025-11-11 digest/pu-senate-election-demand-spirals-into-panjab-staking-claim-on-chandigarh
2025-11-18 digest/aap-wins-tarn-taran-sad-gets-another-chance
2025-11-25 digest/on-guru-teghbahadars-350th-martyrdom-day-panjab-declares-holy-cities
2025-12-02 digest/panjab-university-students-win-senate-elections-notified
2025-12-09 digest/panjab-district-block-polls-on-14-dec
2025-12-16 digest/ngt-issues-notice-on-panjab-floods-ed-attaches-malbros-properties
2025-12-23 digest/vb-g-ram-g-act-replaces-mgnrega-opposition-cries-foul
2025-12-30 digest/sikhs-observe-sahibzade-shahidi-sabha-guru-gobind-singh-parkash-purab
2026-01-06 digest/akal-takht-summons-panjab-cm-mann
2026-01-13 digest/sad-aap-bjp-to-flex-muscle-on-maghi-mela
2026-01-20 digest/panjab-cm-appears-at-akal-takht
2026-01-27 digest/delhi-court-acquits-sajjan-kumar-in-4th-1984-sikh-genocide-case
2026-02-03 digest/pm-modi-visits-dera-sachkhand-ballan-bjp-wins-chandigarh-mayoral-elections
2026-02-10 digest/trump-dictates-us-india-trade-deal-panjab-will-be-hugely-impacted
2026-02-17 digest/gupta-pleads-guilty-punctures-indias-foreign-home-ministrys-long-denial
2026-02-24 digest/34-encounters-in-3-months-in-panjab-policemen-found-dead
2026-03-03 digest/israel-us-launch-operation-epic-fury-khamenei-dead-iran-bombs-us-bases
2026-03-10 digest/iran-effectively-closes-strait-of-hormuz-panjab-affected
2026-03-17 digest/india-walks-a-tight-rope-with-iran-panjab-stops-urea-production
2026-03-24 digest/irans-leader-visits-delhi-gurdwara-war-impacts-students-farmers
2026-03-27 reports/indias-federal-agency-courts-judgements-1992-1995-extrajudicial-killings-in-panjab
2026-03-31 digest/iran-allows-india-crude-supply-gas-scarcity-pauses-industry-in-panjab
2026-04-07 digest/war-causes-migrant-labor-exodus-siropa-shortage
2026-04-14 digest/panjab-assembly-passes-anti-sacrilege-bill-governor-nod-awaited
2026-04-21 digest/opposition-defeats-bjps-plan-to-amend-womens-bill-bring-in-delimitation
2026-04-28 digest/seven-aap-mps-including-pathak-and-chadha-defect-to-bjp
2026-05-05 digest/panjab-opposition-targets-cm-for-appearing-drunk-in-assembly
2026-05-12 digest/twin-blasts-rock-panjab-cm-mann-blames-bjp
2026-05-19 digest/sir-begins-in-panjab-civic-polls-announced
2026-05-26 digest/panjab-civic-polls-through-ballot-paper-amid-sporadic-violence
2026-06-02 digest/aap-wins-48-wards-in-civic-polls
2026-06-09 digest/operation-blue-star-marked-peacefully-at-akal-takht-bjp-leader-at-taksal-hq
2026-06-16 digest/akal-takht-declares-cm-mann-gurus-betrayer-anti-khalsa-panth
2026-06-23 digest/opposition-presents-evidence-against-cm-mann-demands-resignation
2026-06-25 reports/india-eu-free-trade-agreement-how-can-panjab-leverage-it
2026-06-30 digest/akal-takht-lays-bare-gaps-in-how-anti-sacrilege-law-was-passed
2026-07-07 digest/satluj-earlier-punjab-95-abruptly-withdrawn-from-ott-after-2-day-run
2026-07-14 digest/movie-satluj-floods-panjabs-villages-indian-cities-diaspora
2026-07-21 digest/modi-visits-panjab-criticizes-opposition-farmers-to-protest-indo-us-fta
2026-07-28 digest/gen-z-protest-education-minister-pradhan-resigns-sikhs-earn-praise
"""


def seeds(path=None):
    """The URL list, from --urls, from the file beside the script, or built in.

    Returns ({url: iso_date}, where_it_came_from).
    """
    src = path or SEED
    if os.path.exists(src):
        out = {}
        for line in open(src):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # the file is "url<TAB>date"; a bare list of URLs works too
            url, _, date = line.partition('\t')
            if url.startswith(('http://', 'https://')):
                out[url.rstrip('/')] = date.strip()
        if out:
            return out, os.path.basename(src)
        print(f'{src} held no URLs; using the built-in list instead')
    elif path:
        sys.exit(f'no such file: {path}')

    out = {}
    for line in EMBEDDED_SEEDS.strip().splitlines():
        date, _, rel = line.partition(' ')
        out[f'https://{HOST}/{rel}'] = date
    return out, 'the built-in list'


def looks_like_article(u):
    p = urllib.parse.urlparse(u)
    if p.hostname not in (HOST, 'www.' + HOST) or p.query:
        return False
    parts = [x for x in p.path.split('/') if x]
    if not parts:
        return False
    if parts[0] in ('digest', 'digests', 'report', 'reports', 'article', 'articles', 'post'):
        return len(parts) > 1
    return len(parts) == 1 and parts[0].count('-') >= 2


def crawl(known, max_pages, delay, fetch):
    """Widen the seed list: sitemap first, then a shallow walk of the site."""
    found, queue, seen = set(known), list(ROOTS), set()
    while queue and len(seen) < max_pages:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        status, doc = fetch(u)
        if status != 200 or not doc:
            continue
        for m in re.finditer(r'<loc>\s*([^<\s]+)\s*</loc>', doc, re.I):
            v = m.group(1)
            if v.endswith('.xml') and len(seen) + len(queue) < max_pages:
                queue.append(v)
            elif looks_like_article(v):
                found.add(v.rstrip('/'))
        for m in re.finditer(r'href="([^"#]+)"', doc):
            v = urllib.parse.urljoin(u, m.group(1))
            if looks_like_article(v):
                found.add(v.rstrip('/'))
            elif (urllib.parse.urlparse(v).hostname in (HOST, 'www.' + HOST)
                  and v not in seen and len(queue) < 60
                  and re.search(r'/(digest|reports?|articles?|page)\b', v)):
                queue.append(v)
        time.sleep(delay)
    return sorted(found)


# ---------------------------------------------------------------------- main
def load_done():
    done = {}
    if os.path.exists(OUT):
        for line in open(OUT):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            done[r['url'].rstrip('/')] = r
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='list targets, fetch nothing')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--delay', type=float, default=1.5, help='seconds between requests')
    ap.add_argument('--render', action='store_true', help='use a browser (needs playwright)')
    ap.add_argument('--refetch', action='store_true', help='ignore anything already saved')
    ap.add_argument('--thin-only', action='store_true', help='retry only the thin ones')
    ap.add_argument('--no-crawl', action='store_true', help='use the seed list alone')
    ap.add_argument('--max-crawl', type=int, default=40, help='listing pages to walk')
    ap.add_argument('--urls', help='a file of URLs to use instead of the built-in list')
    ap.add_argument('--out', help='where to write the corpus (default: beside this script)')
    ap.add_argument('--insecure', action='store_true',
                    help='skip TLS verification (only if certs cannot be fixed)')
    args = ap.parse_args()

    global CTX, OUT
    CTX = ssl_context(args.insecure)
    if args.insecure:
        print('! TLS verification is OFF for this run')
    if args.out:
        OUT = os.path.abspath(args.out)

    seed, where = seeds(args.urls)
    print(f'{len(seed)} seed URLs from {where}')

    renderer = Renderer() if args.render else None
    fetch = (lambda u: renderer.get(u)) if renderer else (lambda u: get(u))

    if args.no_crawl or args.dry_run:
        urls = sorted(seed)
        if not args.no_crawl:
            print('(--dry-run skips the crawl; run without it to discover more)')
    else:
        print('crawling for digests not in the seed list ...')
        try:
            urls = crawl(seed.keys(), args.max_crawl, args.delay, fetch)
        except CertError as e:
            sys.exit(f'\n  {e}\n{CERT_HELP}')
        new = [u for u in urls if u not in seed]
        print(f'  {len(urls)} total, {len(new)} newly discovered')

    done = {} if args.refetch else load_done()
    KEEP = ('ok', 'short')                    # already have the article; leave it alone
    if args.thin_only:
        todo = [u for u in urls if u in done and done[u].get('quality') not in KEEP]
    else:
        todo = [u for u in urls if u not in done or done[u].get('quality') not in KEEP]
    if args.limit:
        todo = todo[:args.limit]

    print(f'{len(todo)} to fetch, {len(done)} already saved')
    if args.dry_run:
        for u in todo[:40]:
            print('  ', u)
        if len(todo) > 40:
            print(f'   ... and {len(todo) - 40} more')
        return

    fresh = []
    for i, u in enumerate(todo, 1):
        print(f'[{i}/{len(todo)}] {u}')
        try:
            status, doc = fetch(u)
        except CertError as e:
            if renderer:
                renderer.close()
            sys.exit(f'\n  {e}\n{CERT_HELP}')
        if status != 200 or not doc:
            print(f'    ! HTTP {status}')
            if status in (401, 403, 429):
                print('    stopping: the site is refusing requests. Slow down '
                      '(--delay) or check with Liv Forum before continuing.')
                break
            fresh.append({'url': u, 'http_status': status, 'quality': 'failed',
                          'body': '', 'paragraphs': [], 'links': [],
                          'word_count': 0, 'extractor': 'none',
                          'title': '', 'date': seed.get(u, ''), 'category': '',
                          'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
            time.sleep(args.delay)
            continue

        paras, links, how = extract(doc, u)
        rec = {
            'url': u,
            'title': page_title(doc),
            'date': page_date(doc) or seed.get(u, ''),
            'category': '',
            'paragraphs': paras,
            'links': links,
            'extractor': how,
            'http_status': status,
            'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        fresh.append(rec)
        print(f'    {how}: {sum(len(p.split()) for p in paras)} words, {len(links)} outbound links')
        time.sleep(args.delay)

    if renderer:
        renderer.close()

    # --- boilerplate, removed by frequency rather than by pattern -----------
    all_recs = list(done.values()) + fresh
    if not all_recs:
        # nothing was fetched and nothing was saved before: write no file at
        # all rather than leaving an empty one that looks like a finished run
        sys.exit('\nnothing was fetched, so no corpus was written.\n'
                 'Check the errors above; --dry-run lists the targets without '
                 'touching the network.')
    counts = {}
    for r in all_recs:
        for p in set(r.get('paragraphs') or []):
            counts[p] = counts.get(p, 0) + 1
    n = max(len(all_recs), 1)
    furniture = {p for p, c in counts.items() if c > max(2, n * BOILER_SHARE)}
    if furniture:
        print(f'\ndropping {len(furniture)} boilerplate paragraph(s) seen on >'
              f'{int(BOILER_SHARE*100)}% of pages')

    by_url = {}
    for r in all_recs:
        paras = [p for p in (r.get('paragraphs') or []) if p not in furniture]
        body = '\n\n'.join(paras)
        words = len(body.split())
        r['paragraphs'] = paras
        r['body'] = body
        r['word_count'] = words
        if r.get('quality') == 'failed':
            pass
        elif words >= MIN_WORDS:
            r['quality'] = 'ok'
        elif len(paras) >= 2 and words > 0:
            # a real body was found, it is just a brief digest. Complete enough
            # to keep, so a normal re-run will not fetch this page again.
            r['quality'] = 'short'
        elif words > 0:
            r['quality'] = 'thin'
        else:
            r['quality'] = 'needs_render'
        by_url[r['url'].rstrip('/')] = r

    tmp = OUT + '.tmp'
    with open(tmp, 'w') as f:
        for u in sorted(by_url):
            f.write(json.dumps(by_url[u], ensure_ascii=False) + '\n')
    os.replace(tmp, OUT)

    tally = {}
    for r in by_url.values():
        tally[r['quality']] = tally.get(r['quality'], 0) + 1
    print(f'\nwrote {len(by_url)} records to {OUT}')
    print('  ' + ', '.join(f'{k}: {v}' for k, v in sorted(tally.items())))
    words = sum(r['word_count'] for r in by_url.values())
    links = sum(len(r.get('links') or []) for r in by_url.values())
    print(f'  {words:,} words, {links:,} outbound links')

    bad = [r for r in by_url.values() if r['quality'] not in ('ok', 'short')]
    if bad:
        print(f'\n{len(bad)} page(s) did not give up an article body:')
        for r in bad[:25]:
            print(f'  {r["quality"]:<13} {r["url"]}')
        if len(bad) > 25:
            print(f'  ... and {len(bad) - 25} more')
        if any(r['quality'] == 'needs_render' for r in bad):
            print('\n  Pages marked needs_render have no article text in the HTML the\n'
                  '  server sends - the body is drawn by JavaScript. Re-run with:\n'
                  '      pip install playwright && playwright install chromium\n'
                  '      python3 scripts/scrape-livforum.py --render --thin-only')


if __name__ == '__main__':
    main()
