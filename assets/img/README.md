# Local image assets

Profile photographs that are **not** hosted on Wikimedia live here, so the page
does not depend on third-party CDNs that are slow, hotlink-protected, or liable
to disappear.

Most of this folder is populated by running, from the repo root:

```bash
bash scripts/fetch-external-images.sh
```

Until these files exist, `timeline-data.json` falls back to the original remote
URL for each image, so the page still renders correctly — just more slowly.

| File | Subject |
|---|---|
| `parmjit-singh-panjwar.jpg` | Parmjit Singh Panjwar |
| `gurdip-singh-chaggar.jpg`  | Gurdip Singh Chaggar |
| `jagtar-singh-johal.jpg`    | Jagtar Singh Johal |
| `mahmood-fighting-for-faith-and-nation.jpg` | Book cover — Mahmood, *Fighting for Faith and Nation* (shown in the cited-work hover card) |
| `moninder-singh-un-human-rights-council.jpg` | Moninder Singh at the UN Human Rights Council (Global News) — committed to the repo, not fetched |
| `gurbachan-singh-sant-nirankari.png` | Baba Gurbachan Singh, third head of the Sant Nirankari Mission — photographer unknown, published by the Sant Nirankari Mission, used under fair use. Committed to the repo, not fetched |
