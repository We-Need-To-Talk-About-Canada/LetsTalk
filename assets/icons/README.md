# Playbook icons

Eleven icons from [Lucide](https://lucide.dev/) v1.27.0, an open-source icon set
released under the **ISC licence** (see `LICENSE`, copied verbatim from the
`lucide-static` package). Lucide is itself a community fork of Feather Icons.

They are vendored here rather than loaded from a CDN, for the same reason the
photographs were brought into the project: no third-party requests on page
load.

The page does not fetch these `.svg` files at runtime. The inner markup of each
one is stored in `timeline-data.json` — under `playbook[].icon` and
`playbook_closing.icon` — and inlined by `buildPlaybook()`, so the icon inherits
the accent colour via `currentColor`. The files here are the unmodified
originals, kept so the source of each icon is verifiable and so any future icon
can be swapped in from the same set.

| # | Technique | Anchor | Icon |
|---|---|---|---|
| 01 | Label it before anyone can check | `#pb-instant-labelling` | `tag` |
| 02 | Recast ordinary crime as extremism | `#pb-crime-as-extremism` | `replace` |
| 03 | Fabricate the incident itself | `#pb-fabricated-incident` | `siren` |
| 04 | Impersonate the community itself | `#pb-impersonation` | `venetian-mask` |
| 05 | Launder it through a local voice | `#pb-domestic-voices` | `megaphone` |
| 06 | Get the frame into the mainstream | `#pb-mainstream-seeding` | `newspaper` |
| 07 | Run it from inside a consulate | `#pb-diplomatic-cover` | `landmark` |
| 08 | Let criminals do the work | `#pb-criminal-proxies` | `handshake` |
| 09 | Erase the reporting that contradicts it | `#pb-silence-the-record` | `eraser` |
| 10 | Have the platform do the silencing | `#pb-platform-censorship` | `ban` |
| — | What the official record says (closing panel, not a technique) | `#pb-on-the-record` | `stamp` |

Anchors are stable: `timeline.html#pb-<id>` opens the Playbook tab and scrolls
to that section on a cold load, so they are safe to share.
