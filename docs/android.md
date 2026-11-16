# Janma Kundali on Android

The Janma Kundali app puts the web app on your Android phone's home screen as
a real app. It is a **thin client**: your charts are computed, stored and
rendered into reports by your Janma Kundali server — the same `kundali-web`
the [quick start](../README.md#quick-start) installs on a Raspberry Pi or any
other machine — and the phone opens it.

Everything the browser app does, the phone app does, because it shows the
same pages: saved charts and places, the chart views, the week ahead, the
reports, backups and restore. This page covers what is different on a phone.
How it is built is in [`apps/android/README.md`](../apps/android/README.md).

**There is no offline, on-phone mode, on purpose.** A chart here is the Swiss
Ephemeris under CPython, with reportlab and cairo drawing the PDF — a whole
scientific Python stack that does not belong on a phone, and that a second
implementation in Kotlin would only drift from (this project's rule is that
every number comes from one set of modules). The phone needs to reach the
server: on your Wi-Fi, over a VPN or tailnet, or through a reverse proxy.

## Install the app

Every [release](https://github.com/chinmay28/vedic-astrology/releases)
attaches it as `janma-kundali.apk`, and the latest is always at:

```
https://github.com/chinmay28/vedic-astrology/releases/latest/download/janma-kundali.apk
```

Open that address on the phone, download the APK, and open it. Android asks
once to let your browser install apps; allow it. A newer release installs
over the old one, keeping your settings. It needs Android 10 or newer.

## The first screen

The app asks for your server's address: `192.168.1.20`, `pi.local`, or
`https://charts.example.com`. An address with no `http://` or `https://`
means `http://` on kundali-web's own port, **8777**; give a port if yours is
different (`192.168.1.20:9090`). An `https://` or `http://` address with no
port means the standard one, as for a server behind a reverse proxy.

**Continue** checks that a Janma Kundali server answers there (its
`/api/health`) before keeping the address. If nothing answers — a typo, or a
server that is off right now — it says so, and **Continue anyway** keeps the
address regardless.

The server has to accept connections from the phone. The quick start
publishes on `0.0.0.0:8777` for exactly this; a server started by hand needs
`kundali-web --host 0.0.0.0`. Like the web app, the app has no
authentication of its own: keep the server on a network you trust.

The version of the app is in small print under **Continue**, and the
developer badge at the bottom of the screen shows the maker's mark when
tapped, as the badge in the web app's header does.

## Reports and backups

Every download — the PDF and HTML reports, JSON and CSV exports, the
`kundali.sqlite` backup — is saved to **Downloads/Janma Kundali** on the
phone, where the Files app, a PDF reader or any other app can find it.

- A **PDF or HTML report opens straight away** in the phone's own viewer (a
  PDF reader, or the browser for the HTML report). Turn this off in the app's
  settings (*Open reports after saving*) to have reports only saved.
- **Share PDF report**, on a chart's Report tab, renders the PDF and opens
  the phone's share sheet with it attached — to send it on WhatsApp, mail or
  Drive. The sheet's first entry, *Save to Downloads*, keeps a copy as well.
  The button only appears inside the app.
- **Restore** (Data & backup) opens the phone's file picker for the JSON
  backup: from Downloads, a USB stick, or a cloud's own app such as Drive.

## Shortcuts and settings

Long-press the app's icon:

- **New chart** opens the new-chart form directly.
- **Settings** opens the app's settings.

The settings are also on the **Data & backup** screen (*This app → App
settings*), and on the screen the app shows when it cannot reach the
server. They hold the server's address and *Open reports after saving*.

## When the server cannot be reached

The app shows what went wrong, with **Retry** and **App settings**. Pages
you have already opened may still show from the web app's offline cache, as
they do in an installed browser app, but nothing new is computed until the
server is back.

Links that leave your server — the developer's GitHub page, the source code —
open in the phone's browser, not inside the app.

## Not in the app

- Running the server on the phone (see above).
- Finding the server on the network by itself: kundali-web does not announce
  itself, and the address is typed once.
