# UX Review — We Need to Talk About Canada

**Scope:** the three-page static site — `index.html` (explainer), `directory.html` (MP directory with filters/search/response-tracking), and `timeline.html` (VIRASAT, the interactive Sikh-history chronicle). **Method:** synthesis of hands-on research that drove the live site in Chromium at desktop (1440×900) and mobile (390×844), tested keyboard nav, focus/hover, filtering, dark/light rendering, and cross-page navigation, plus a code-level read of the source and a performance/load-weight pass. **Environment caveat:** the research sandbox had no outbound network, so Google Fonts, Leaflet's CDN, and every hotlinked photo fell back to error states; interactive map behavior and the intended photo-desaturation hover could not be visually confirmed. That caveat does **not** soften the two headline findings below — the dark/light rendering gap and the hotlinked-image dependency are code-level defects that exist regardless of network, and were confirmed by reading the source, not just by observing the blocked sandbox.

Issues are ordered by likely impact on the reader's experience — trust damage and blocked interaction paths first, cosmetic and consistency items last — not by how hard they are to fix.

---

## 1. [Critical · Theming] Hardcoded dark elements render as broken placeholders for the default (light) visitor

**Problem.** `timeline.html` is visually authored for dark mode, but with no OS dark preference it defaults to a beige/cream page — the common case. Numerous elements are hardcoded to near-black regardless of theme: `.figure` background `#05070A` (`timeline.html:203`), `#leaflet-map` / `.leaflet-container` `#0a0d12` (`timeline.html:284,287,291`), `.codex-card .portrait` `#05070A` (`349`), `.cd-portrait` `#05070A` (`375`), and the lightbox image wrap + thumbs `#05070A` (`411,429`). On the light page these become solid black rectangles punched into every image, portrait, and map slot — they read as broken/unstyled placeholders (`timeline-desktop-01-initial.png`, `timeline-desktop-08-codex-view.png`). Captured under `colorScheme:'dark'` the identical markup looks fully intentional (`DARKMODE-timeline-top.png`, `DARKMODE-timeline-codex.png`).

The same root cause surfaces on `directory.html` in reverse: party-tag chips are hardcoded pale pastels (`.party-tag.lib{background:#FCE9EC;color:#A2001D}`, `.cpc{background:#E7EEF6;color:#1A4782}`, `directory.html:305-306`), which glow as bright rectangles on the near-black dark-mode card (`DARKMODE-directory-cards.png`); and the "Four Questions" emphasis panel, designed to pop as a dark card on a light page, nearly vanishes in dark mode because `--color-bg:#06080C` and `--color-surface-emphasis:#12161F` are almost the same value (`DARKMODE-directory-top.png`). These are one systemic issue: colors baked as literals instead of resolved from `theme.css` tokens.

Compounding it, **there is no theme toggle anywhere** — grepping all three files for `toggle`/`theme-switch`/`data-theme` returns zero relevant hits, and `theme.css`'s own header admits "No toggle is wired up today." A light-mode visitor who sees the black-box timeline has no in-page way to switch to the theme it was designed for.

**Why it matters.** For the majority of visitors (light OS default), the flagship timeline looks broken on first paint — the single most damaging first impression on a design-conscious audience. Violates the principle that a design should look intentional in every state it ships in, not just the author's preferred one.

**Fix.** Drive these backgrounds from semantic tokens (e.g. `--color-surface-sunken` / `--color-media-frame`) defined for both schemes in `theme.css` rather than literal `#05070A`/`#0a0d12`; the media frames should be a mid neutral on light and near-black on dark. For the directory chips, define light/dark variants of the party pastels. Widen the light-vs-emphasis contrast, or give the emphasis panel a token that stays distinct in both schemes. Then either fully commit the timeline to a single dark look regardless of OS, or add a manual toggle so users can reach the intended rendering.

## 2. [Critical · Accessibility] Codex person cards cannot be opened from the keyboard

**Problem.** Codex cards are plain click-only `<div>`s: `card.className='codex-card'; ... card.addEventListener('click', () => openPerson(p.name))` (`timeline.html:1004-1012`) — no `tabindex`, no `role`, no `keydown` handler (confirmed in-browser: `tabIndex:-1`, `role:null`). Tabbing skips them entirely, so a keyboard user has no way to open any of the 46 biographical modals. The same file gets it right for the Index-view table rows — `tr.tabIndex = 0` with an Enter/Space `keydown` handler (`timeline.html:757-761`) — so the identical "click to open detail" pattern is accessible in one view and dead in the other.

**Why it matters.** Blocks an entire interaction path — the codex is a core feature — for keyboard and switch users, and the working Index rows prove the pattern is understood, so this reads as an oversight, not a constraint.

**Fix.** On each `.codex-card`, add `tabindex="0"`, `role="button"`, an `aria-label` with the person's name, and a `keydown` handler firing `openPerson(p.name)` on Enter/Space — mirror exactly what `timeline.html:757-761` already does for the Index rows.

## 3. [Critical · Trust] Failed-to-load images are labeled identically to images that never existed

**Problem.** The image error handler swaps in the same placeholder used for events that have no image at all: `img.addEventListener('error', () => { wrap.innerHTML = placeholder(); ... })` (`timeline.html:822`), where `placeholder()` renders "No archival image for this memory" (`timeline.html:854`). Verified directly: the Guru Amar Das event has a real `ev.media.url` (a Wikimedia painting present in the failed-request log), but when that fetch fails the UI shows "No archival image for this memory" — byte-identical to an event that genuinely has no image (`timeline-desktop-broken-image-state.png`). A reader cannot tell "no known photo exists" from "the photo exists but failed to load."

**Why it matters.** The site's stated editorial standard is that "every claim traces to something a reader can check." Telling a journalist that archival material doesn't exist when it does — and the site knows the URL — quietly undermines exactly the credibility this project is built on. This is a trust defect, not just a cosmetic one.

**Fix.** Branch the error state: when `ev.media?.url` was set but failed, render distinct copy (e.g. "Archival image could not be loaded" with a retry/source link built from the known URL); reserve "No archival image for this memory" for events where no `media.url` was ever configured.

## 4. [High · Performance] Every event/portrait/photo is hotlinked to third-party hosts with no local copy

**Problem.** All imagery is runtime-inserted via JS and points at external URLs the site doesn't control: timeline events build `img.src = ev.media.url` (`timeline.html:818-819`), codex portraits and lightbox slides inject `<img src="…">` via `innerHTML` (`timeline.html:1007,1028,1068,1079`), and MP headshots template `src="${mp.photo}"` (`directory.html:663`). The research logged ~50 unique failed image requests spanning Wikimedia Commons, a Squarespace CDN, a Substack CDN, `timesnownews.com`, `en.wikipedia.org`, and `ourcommons.ca` — roughly five unrelated hosts whose uptime, CORS, and hotlink policy the site fully depends on. No local copies, no confirmed `width`/`height`, no `srcset`.

**Why it matters.** On a real network this is the dominant contributor to perceived load time and to layout shift (missing intrinsic dimensions), and any one host de-hotlinking or rate-limiting silently breaks large parts of the page — the same single-point-of-failure that made the timeline look broken in the sandbox. For a chronicle whose entire value is the archival imagery, that's a fragile foundation.

**Fix.** Self-host the archival assets (download, optimize to WebP/AVIF, serve from the site's own origin) or proxy/cache them; add explicit `width`/`height` (or `aspect-ratio`) to every inserted `<img>` to reserve layout space and kill CLS; add `srcset`/sized variants for the large timeline and portrait images.

## 5. [High · Performance] `loading="lazy"` is applied inconsistently across the runtime-inserted images

**Problem.** Lazy-loading is present on some JS-inserted images and missing on others in the same file: the codex-grid portrait (`timeline.html:1007`) and lightbox thumbnails (`1079`) get `loading="lazy"`, but the main timeline event image (`818`, via `createElement('img')`) and the opened-person hero portrait (`1028`) do not. Static markup is similarly uneven (1/1 in directory, 2/4 in timeline's static tags). Because most images are injected at runtime, the naive static count understates the real volume that loads eagerly.

**Why it matters.** The heaviest, above-and-below-fold images (event media, hero portraits) are the ones loading eagerly, pulling forward bandwidth on the very assets described in issue 4 and slowing first interaction on a tall page.

**Fix.** Add `loading="lazy"` (and `decoding="async"`) uniformly to every JS-inserted `<img>` except the one that's truly first-paint-visible; standardize it in the shared image-building code so new insertions inherit it.

## 6. [High · Performance] The Leaflet script and Google Fonts block parsing/render for a feature that isn't shown by default

**Problem.** Leaflet is a synchronous, render-blocking dependency in `<head>`: `<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>` (`timeline.html:12`) with no `defer`/`async`, so HTML parsing waits on a third-party CDN round-trip even though the map is one of four tabs and hidden on load. Google Fonts loads as a blocking cross-origin `<link rel="stylesheet">` on all three pages; `display=swap` is set (good) but there's no self-hosting or local fallback.

**Why it matters.** Both delay first paint on the largest page (`timeline.html` is ~255 KB) for resources that either aren't visible yet (the map) or aren't essential to first render (web fonts) — and both fail hard when their CDN is unreachable, which is what stalled the sandbox.

**Fix.** Add `defer` to the Leaflet tag, or better, lazy-load Leaflet only when the Map tab is first activated. Self-host the two font families (or add `<link rel="preconnect">` plus a solid local fallback stack) so the fonts aren't a blocking cross-origin dependency.

## 7. [High · Mobile] The timeline tab bar overflows off-screen with no affordance, hiding the Index view

**Problem.** At 390px the `#tabbar` has `scrollWidth:462` vs `clientWidth:362`; `overflow-x:auto` is only set at `max-width:760px` (`timeline.html:462`), so the row scrolls, but the "04 INDEX" tab's right edge (475.8px) sits past the visible edge (376px) and is simply cut off (`timeline-mobile-01-initial.png` shows only Timeline / Map / Codex). There's no fade gradient, arrow, or peek to signal a fourth tab exists.

**Why it matters.** A mobile user has no cue that the Index view — one of the four primary navigation targets — exists at all; hidden navigation is effectively missing navigation. Violates discoverability.

**Fix.** Add a right-edge fade/scroll-shadow (a gradient overlay or `scroll-timeline`-driven mask) or shrink the tab padding/typography at mobile so all four fit; at minimum, leave the fourth tab partially visible so its cut-off edge invites a swipe.

## 8. [Medium · Navigation] Primary nav scrolls away on very tall pages and is never sticky

**Problem.** No page has a sticky header. `timeline.html`'s `.chrome` bar (`63`) and `.tabbar` (`position:relative`, `97`) scroll out of view — the Index view is 4,951px tall (~5.5 screens) and Codex is 2,252px; at the bottom of Codex the chrome's bounding box is fully above the viewport (`top:-147`). `index.html`'s `header.masthead` (`298`) is normal in-flow too. Switching timeline views or navigating home from deep in a long view requires scrolling all the way back up first.

**Why it matters.** Forces a long manual scroll to reach navigation on the site's tallest content — a friction tax that scales with how engaged the reader is. Affects everyone, worse on mobile.

**Fix.** Make `.tabbar` (and ideally `.chrome`) `position:sticky; top:0` with an appropriate `z-index` and a solid/blurred background so the four view tabs stay reachable; consider the same for the directory's "Back to Home" link and a lightweight sticky masthead on `index.html`.

## 9. [Medium · Navigation] The three pages don't form a connected nav graph — the directory can't reach the timeline

**Problem.** `directory.html` has no link to `timeline.html` anywhere (grep returns zero matches). `timeline.html` and `index.html` each link to both other pages, but from the MP directory the only route to the VIRASAT timeline is to click "Back to Home" and hunt for the timeline CTA there. Compounding it, the three pages use three unrelated nav patterns: `index.html` has no persistent header (hero + footer only), `directory.html` has a lone non-sticky "Back to Home" text link (`453`), and `timeline.html` has a distinct two-item `.chrome` bar with its own pill/uppercase styling (`472-484`) matching neither of the others.

**Why it matters.** A dead-end between two of the three main destinations makes the site feel like disconnected pages rather than one publication; inconsistent nav placement forces users to re-learn "where's the menu" on each page.

**Fix.** Add a timeline link to `directory.html` (in the same eyebrow/footer region as its existing home link). Adopt one shared, consistently placed nav treatment across all three pages — even if the timeline keeps its "chronicle" visual language, the link set and position should be predictable.

## 10. [Medium · Accessibility] Filter buttons have no explicit focus ring and are easy to confuse with unfocused state

**Problem.** The search box has a vivid explicit focus style (2px accent-red outline, 1px offset, `directory.html:204`), but `button.filter-btn` has no `:focus`/`:focus-visible` rule anywhere in the file — it falls back to the browser default (`rgb(32,28,22) auto`), a thin dark ring that sits directly against the button's own 1.5px dark border, making focused vs unfocused pills hard to distinguish at a glance (`directory-liberal-btn-focus-crop.png`).

**Why it matters.** Keyboard users can lose track of which filter has focus mid-tab-sequence; the inconsistency with the strong search-box ring means focus visibility is a coin flip depending on control type. Violates WCAG focus-visible expectations.

**Fix.** Add a `.filter-btn:focus-visible` rule matching the search box's treatment (accent-red outline, ≥2px, with offset so it clears the button's own border) — reuse the same token/values for consistency.

## 11. [Medium · Mobile] The "Cycle" diagram is illegible at phone width

**Problem.** The circular Cycle SVG uses a fixed `viewBox="-70 -40 940 830"` (`index.html:338`) with absolute font sizes baked into SVG coordinate space (14px title, 11px subtitle, 22px badges). At 390px it renders at ~342×302 CSS px (~36% scale), so the "14px" labels render ~5px effective — the seven step labels and center "THE CYCLE / SELF-SEALING" caption are hard to read (`index-mobile-cycle-diagram-zoom2.png`).

**Why it matters.** A core explanatory graphic on the landing page becomes unreadable for mobile visitors, undercutting the page's persuasive purpose.

**Fix.** Bump the SVG font sizes for small viewports (media-query-driven CSS on the `<text>` elements, since `font-size` on SVG text is stylable), reflow the diagram to a vertical/stacked layout under ~600px, or provide a tap-to-zoom/expand affordance.

## 12. [Low · Consistency/Security] `rel="noopener"` is applied inconsistently to `target="_blank"` links

**Problem.** On `directory.html` the footer Substack link and per-card "Official Profile" link (`675`) carry `rel="noopener"`, but the Instagram link (`553`) and "Verify Any MP Directly" link (`554`) do not — and the identical `@projectaananta` Instagram destination *does* get `rel="noopener"` on `index.html` (`491`). Same link, handled two different ways across pages.

**Why it matters.** Minor reverse-tabnabbing/performance exposure on the unprotected links, and the inconsistency signals under-maintained markup on a site that otherwise presents as carefully made.

**Fix.** Add `rel="noopener noreferrer"` to every `target="_blank"` link across all three files; standardize so external-link handling is uniform.

## 13. [Low · State] Directory filter state survives neither navigation, reload, nor link-sharing

**Problem.** Party/province/search state lives only in memory; back/forward reloads the page fresh (confirmed: `goForward()` triggered a real navigation, not a bfcache restore) and resets filters to "All". There's no query-string or hash encoding of the multi-dimensional filter state.

**Why it matters.** A journalist who filters to, say, Conservative MPs in Ontario can't bookmark or share that view, and loses it on any accidental back-navigation — friction on the page's primary tool. Low because nothing breaks; it's a missing convenience.

**Fix.** Reflect filter state in the URL (`?party=cpc&prov=on&q=gill`) and read it back on load; this also restores state across reload and makes filtered views shareable.

---

## What's already working

Several things the research confirmed are done well and should be preserved:

- **Reduced-motion is honored correctly.** `timeline.html:439` applies `*{animation:none !important; transition:none !important;}` under `prefers-reduced-motion: reduce`; the ambient HUD-sweep/scanline loop stops for users who ask for it (verified: `.hud-sweep`'s computed `animationName` becomes `none`).
- **The directory empty-state is genuinely good.** A nonsense search collapses the grid to a centered, helpfully worded message ("No one matches that filter. Try clearing the search or widening the province.") and the count line correctly updates to "Showing 0 of 19 MPs."
- **The map has a deliberate, well-written CDN-failure fallback.** When Leaflet can't load, the map view shows "Map library failed to load. Check your internet connection and reload the page." — a hand-authored graceful degradation, distinct from (and the right pattern for) the black-box theming problem in issue 1.
- **Filtering logic is correct**, tab order is sensible, the search-box focus ring is strong, the codex modal and gallery lightbox (open/next/Escape) all work, and the Index-view table rows are fully keyboard-accessible — the exact pattern issue 2 asks the codex cards to adopt.
