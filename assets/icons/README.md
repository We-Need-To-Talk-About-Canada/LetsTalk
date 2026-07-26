# Playbook icons

Ten icons from [Lucide](https://lucide.dev/) v1.27.0, an open-source icon set
released under the **ISC licence** (see `LICENSE`, copied verbatim from the
`lucide-static` package). Lucide is itself a community fork of Feather Icons.

They are vendored here rather than loaded from a CDN, for the same reason the
photographs were brought into the project: no third-party requests on page
load.

The page does not fetch these `.svg` files at runtime. The inner markup of each
one is stored in `timeline-data.json` under `playbook[].icon` and inlined by
`buildPlaybook()`, so the icon inherits the accent colour via `currentColor`.
The files here are the unmodified originals, kept so the source of each icon is
verifiable and so any future icon can be swapped in from the same set.

| Technique | Icon |
|---|---|
| 01 Label first, before anyone can check | `tag` |
| 02 Recast ordinary crime as political extremism | `replace` |
| 03 Use criminal proxies so the state's hand stays hidden | `venetian-mask` |
| 04 Run the operation from inside a consulate | `landmark` |
| 05 Launder the message through a local, credible voice | `megaphone` |
| 06 Get the frame into mainstream reporting | `newspaper` |
| 07 Remove the reporting that contradicts it | `eraser` |
| 08 Have the platforms do the silencing | `ban` |
| 09 Manufacture the threat you want investigated | `siren` |
| 10 What the official record now says | `stamp` |
