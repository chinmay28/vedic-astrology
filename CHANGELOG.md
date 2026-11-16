# Changelog

Releases are `vYEAR.MONTH.PATCH` — a calendar version, where YEAR.MONTH is the
month of the release's commit and the patch number is the repository's commit
count, so `v2026.11.42` is the 42nd commit, made in November 2026. See
[`kundali/version.py`](./kundali/version.py). The package itself reports the
same number without the `v` (`kundali-report 2026.11.42`, PEP 440).

Each section below is the body of the corresponding GitHub release. A heading
must name the tag exactly — a tag whose commit builds a different version is a
tag that shouldn't be published — and the release workflow publishes only a
commit whose own version has a section here. To cut a release, rename
`## Unreleased` to the version that commit builds (`python3
scripts/version.py`, with a `v`) in the commit itself.

## Unreleased

**Downloads:** **`janma-kundali.apk`** (new: Janma Kundali for Android — on
the phone, open
`https://github.com/chinmay28/vedic-astrology/releases/latest/download/janma-kundali.apk`
and install it; see [`docs/android.md`](./docs/android.md)), and the package
as `kundali_report-<version>.tar.gz` and `kundali_report-<version>-py3-none-any.whl`
for `pip install`. All are in `SHA256SUMS`. The installers
(`scripts/quickstart.sh`, `scripts/install-systemd.sh`) build from git as
before and need none of these.

### Janma Kundali for Android

A phone app for your Janma Kundali server. It shows the server's own web app,
so everything the browser app does, the phone app does — saved charts and
places, the chart views, the week ahead, reports, backups — and adds what a
phone needs:

- **Reports land in Downloads/Janma Kundali** and a PDF or HTML report opens
  straight away in the phone's own viewer (switch that off in the app's
  settings if you would rather only save them). JSON, CSV and `kundali.sqlite`
  backups are saved the same way.
- **Share PDF report**, on a chart's Report tab, renders the PDF and opens the
  phone's share sheet with it attached.
- **New chart** from a long-press on the app's icon opens the new-chart form
  directly; **Settings** opens the app's settings.
- **Restore** from a JSON backup through the phone's file picker.
- Links that leave your server open in the phone's browser.

The first screen asks for the server's address (`pi.local` means
`http://pi.local:8777`) and checks that Janma Kundali answers there. The app
is a thin client only: the charts are computed and stored by the server, and
nothing runs on the phone without it. Android 10 or newer.

### The version follows the commit

The version's year and month are now the month of the commit being built,
rather than constants bumped by hand; the patch is still the commit count.
Nothing changes for an existing install: the installers pass both halves into
the build (`KUNDALI_VERSION_DATE` joins `KUNDALI_VERSION_PATCH` in the `.env`
quickstart writes), and an installed package keeps reporting what it was built
as.

### Smaller things

- The developer badge in the app bar is the size it is in the other apps
  (36px in a 44px target), and its full-screen mark now fades out as well as
  in.
