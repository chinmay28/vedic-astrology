# Janma Kundali for Android

A thin client: the Janma Kundali web app (`kundali/webapp`) in a web view, in
front of a `kundali-web` server on another machine. The user guide is
[`docs/android.md`](../../docs/android.md); this page is how the app is built
and why. It is modelled file for file on SandHarbor's SAND Vault for Android,
without the full-stack mode.

```
 ┌──────────────────────── the phone ─────────────────────────┐
 │  MainActivity                                               │
 │   WebView ── the web app, from Origin only                  │
 │     ▲  kundali-bridge.js (document start, Origin only)      │
 │     │  KundaliAndroid ⇄ PageBridge: save, share, settings   │
 │     │        │                                              │
 │     │        ├─ Downloads ── MediaStore: Downloads/Janma Kundali
 │     │        ├─ Viewer ───── ACTION_VIEW: the PDF reader     │
 │     │        └─ Sharing ──── the share sheet                 │
 └─────┼───────────────────────────────────────────────────────┘
       ▼
  http(s)://server:8777   kundali-web (Swiss Ephemeris, reportlab, cairo)
```

## Why only a thin client

A chart is the Swiss Ephemeris under CPython; a report is reportlab and
cairo. Carrying that stack onto a phone would be a project of its own, and
re-implementing it in Kotlin would break the rule the whole repository is
built on — one set of modules computes every number (CLAUDE.md: "the web app
is a renderer, not a second implementation"). So the app does not compute
anything: it shows the server's page and adds only what a web view lacks.

## Native where it pays

- **Reports to Downloads, then the viewer.** `app.js` hands over every file
  by clicking an `<a download>` on a `blob:` address, which a web view
  silently drops. The bridge catches that and sends the bytes across; the
  app writes them to *Downloads/Janma Kundali* through MediaStore (no storage
  permission) and, for a PDF or HTML report, opens it in the phone's viewer
  at once — on a phone a report is downloaded to be read. `core/Reports`
  decides what counts as a report (CSVs and backups are only saved) and the
  setting turns it off.
- **The share sheet.** `navigator.share({files})`, which a web view lacks,
  is implemented by the bridge; the page shows *Share PDF report* only when
  `window.kundaliApp` exists, so a browser is unchanged. The sheet leads with
  *Save to Downloads* (`SaveToDownloadsActivity`, which copies only from the
  app's own FileProvider).
- **Launcher shortcuts.** *New chart* opens `/#/new`, the web app's own
  route for the form (`core/LaunchTarget`), so no page change was needed;
  *Settings* opens the app's settings.
- **The file picker** for restoring a JSON backup (`onShowFileChooser`,
  with `core/AcceptTypes` turning `accept=` into MIME types).
- **The developer badge** on the setup screen, with the full-screen flash
  done natively on the web page's 3-second clock (`core/DevFlash` holds the
  keyframes).

Considered and left out: **network discovery** (kundali-web announces
nothing, and a responder in the server for a once-typed address is not worth
the change) and a **home-screen widget** (nothing in the app is worth a
glance without opening it).

## The page bridge

`assets/kundali-bridge.js` is added at document start (before the page's own
scripts) and talks to an object the web view injects, `KundaliAndroid`:

| Page does | Bridge sends | App does |
|---|---|---|
| clicks `<a download href="blob:…">` (`download()` in app.js) | `begin`, `chunk`…, `end` with action `save` | writes it to *Downloads/Janma Kundali*; opens a report in the viewer |
| clicks `<a download href="/…">` on the origin | `fetch` | downloads it with the web view's cookies, same rules |
| `navigator.share({ files })` (*Share PDF report*) | each file as `stage`, then `share` | opens the share sheet, *Save to Downloads* first |
| *App settings* (Data & backup) | `settings` | opens the settings screen |

It also defines `window.kundaliApp` (`platform`, `version`, `openSettings`),
which is how the page knows it is inside the app. A file crosses in base64
chunks of 768 KB, each answered before the next is read; `core/Transfers`
holds the page to what it announced and discards a transfer that breaks it,
so a half file never lands in Downloads.

The script and the object are given to the configured origin alone
(`addDocumentStartJavaScript` and `addWebMessageListener` with that origin as
the only rule). A `fetch` is refused unless it is on the origin, and its
redirects are followed only within it.

The page side is tested in [`tests/test_android_bridge.py`](../../tests/test_android_bridge.py):
the real script under Node, with the native side played in JavaScript, plus
the checks that app.js still saves the way the bridge catches and that
everything app-only hangs off `window.kundaliApp`. Any change to
`kundali/webapp/static/` must bump `SHELL` in `sw.js` in the same commit, or
an installed app — this one included — keeps the old page.

## Navigation

`core/NavigationPolicy` decides every navigation and `window.open`: the
origin's own pages, `blob:`/`data:` and `about:blank` stay in the app; other
`http(s)` (GitHub, the source link) goes to the phone's browser; `intent:` is
launched only after dropping any component or selector, limited to apps that
take links from a browser; `javascript:`, `file:`, `content:` and the like
are refused.

## Code layout

```
apps/android/
├── core/   plain Kotlin, JVM-tested, no Android:
│           Origin, NavigationPolicy, AppConfig, Health, Bridge, Transfers,
│           FileNames, AcceptTypes, Reports, LaunchTarget, DevFlash
└── app/    the Android shell around it:
            MainActivity (web view), PageBridge + assets/kundali-bridge.js,
            Downloads, Viewer, Sharing, SaveToDownloadsActivity,
            SetupActivity, SettingsActivity, DevFlashOverlay, ConfigStore
```

```bash
export ANDROID_HOME=/path/to/android-sdk
./gradlew :core:test :app:lintDebug :app:assembleRelease
./gradlew -PcoreOnly :core:test        # no Android SDK needed
```

`-PappVersionName=v2026.11.42 -PappVersionCode=42` stamps a build (the
release workflow passes the tag and the commit count); unstamped it is `dev`,
code 1. The release build is signed with the debug key so it sideloads as it
stands.

## The icon

`kundali/webapp/static/icon.svg` is the only icon anyone draws: the PWA icons
are rasterised from it by the server, and `scripts/android_icons.py` makes
every Android one from it — the round-cornered launcher icon at 48dp per
density, the adaptive icon (the mark without its plate as the foreground,
512 SVG units across the 72dp a launcher shows; the plate's colour, read from
the SVG, as the background; a white copy as the themed-icon monochrome
layer), and `drawable-nodpi/kundali_logo.png` for the app's own screens.
`tests/test_android_icons.py` fails if a committed copy has drifted from the
SVG, and if any `@drawable/`/`@mipmap/` reference names a file that does not
exist. Change the SVG, run the script, commit both.

The developer badge PNGs in `res/drawable-nodpi/` are copies of the web
app's `dev-badge.png` and `dev-badge-full.png`.
