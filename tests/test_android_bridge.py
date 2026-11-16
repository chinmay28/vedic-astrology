"""The page as the Janma Kundali Android app shows it (apps/android).

The app shows this same web interface in a web view and adds one script,
apps/android/app/src/main/assets/kundali-bridge.js, which turns the page's
downloads and navigator.share() into messages to native code over an object
the web view injects, `KundaliAndroid`. These tests run the real script
under Node with just enough of a browser around it, and play the native side
in JavaScript, so a change that the app would no longer catch fails here -
without a phone. (SandHarbor drives the same contract through a real
browser; this repo has no browser tooling and adds none.)

The native half of the contract is apps/android/core (Bridge.kt and
Transfers.kt), tested there on its own. The page's half - that app.js saves
through an <a download> on a blob: address, and that everything it shows
only inside the app hangs off window.kundaliApp - is checked at the bottom.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_JS = (ROOT / "apps" / "android" / "app" / "src" / "main" / "assets"
             / "kundali-bridge.js")
APP_JS = ROOT / "kundali" / "webapp" / "static" / "app.js"
PAGE_BRIDGE_KT = (ROOT / "apps" / "android" / "app" / "src" / "main" / "java"
                  / "io" / "github" / "chinmay28" / "kundali" / "PageBridge.kt")

# A browser reduced to what the bridge touches, a fake KundaliAndroid that
# answers as PageBridge.kt does (chunks reassembled in order, as
# Transfers.kt does), then the scenario. Prints what the native side saw.
HARNESS = r"""
const fs = require('fs')
const [bridgePath, mode, scenario] = process.argv.slice(2)

globalThis.window = globalThis
globalThis.location = { origin: 'http://pi.local:8777' }
const listeners = []
globalThis.document = { addEventListener: (t, fn) => listeners.push([t, fn]) }
class HTMLAnchorElement {
  constructor(href, download) {
    this.href = href; this.attrs = {}
    if (download !== undefined) this.attrs.download = download
  }
  hasAttribute(n) { return n in this.attrs }
  getAttribute(n) { return n in this.attrs ? this.attrs[n] : null }
  closest(sel) { return sel === 'a[download]' && this.hasAttribute('download') ? this : null }
}
let nativeClicks = 0
HTMLAnchorElement.prototype.click = function () { nativeClicks++ }
globalThis.HTMLAnchorElement = HTMLAnchorElement
class Navigator {}
globalThis.Navigator = Navigator
Object.defineProperty(globalThis, 'navigator', { value: new Navigator(), configurable: true })
class FileReader {
  readAsDataURL(blob) {
    blob.arrayBuffer().then((b) => {
      this.result = 'data:' + (blob.type || 'application/octet-stream') + ';base64,' + Buffer.from(b).toString('base64')
      this.onload()
    })
  }
}
globalThis.FileReader = FileReader
const blobs = {}
let nextBlob = 0
const blobUrl = (b) => { const u = 'blob:http://pi.local:8777/' + (++nextBlob); blobs[u] = b; return u }
globalThis.fetch = async (u) => ({ blob: async () => blobs[u] })
const warnings = []
console.warn = (...a) => warnings.push(a.join(' '))

const native = { messages: [], files: {}, shared: [], fetched: [], settings: 0 }
if (mode !== 'plain') {
  const replyTo = []
  let n = 0
  const reply = (o) => replyTo.forEach((fn) => fn({ data: JSON.stringify(o) }))
  const handle = (m) => {
    switch (m.t) {
      case 'begin': {
        const id = 't' + (++n)
        native.files[id] = { name: m.name, mime: m.mime, size: m.size, action: m.action, chunks: [] }
        return reply({ re: m.re, ok: true, id })
      }
      case 'chunk': {
        const f = native.files[m.id]
        if (m.seq !== f.chunks.length) return reply({ re: m.re, ok: false, error: 'out of order' })
        f.chunks.push(Buffer.from(m.data, 'base64'))
        return reply({ re: m.re, ok: true })
      }
      case 'end': {
        const f = native.files[m.id]
        const data = Buffer.concat(f.chunks)
        f.length = data.length
        f.sha = require('crypto').createHash('sha256').update(data).digest('hex')
        delete f.chunks
        return reply({ re: m.re, ok: f.length === f.size, id: m.id, name: f.name, error: 'short' })
      }
      case 'share': native.shared.push(m); return reply({ re: m.re, ok: true })
      case 'fetch': native.fetched.push(m); return reply({ re: m.re, ok: true })
      case 'settings': native.settings++; return reply({ re: m.re, ok: true })
      default: return undefined
    }
  }
  globalThis.KundaliAndroid = {
    postMessage(text) {
      const m = JSON.parse(text)
      native.messages.push({ t: m.t, seq: m.seq, action: m.action })
      setTimeout(() => handle(m), 0)
    },
    addEventListener(type, fn) { if (type === 'message') replyTo.push(fn) },
  }
}

eval(fs.readFileSync(bridgePath, 'utf8').replace('"__KUNDALI_APP_VERSION__"', '"v2026.11.30"'))

const settle = () => new Promise((r) => setTimeout(r, 50))
const pattern = (size) => { const b = Buffer.alloc(size); for (let i = 0; i < size; i++) b[i] = (i * 7 + 3) & 255; return b }
const sha = (b) => require('crypto').createHash('sha256').update(b).digest('hex')
const out = { native, warnings }

;(async () => {
  out.app = window.kundaliApp ? { ...window.kundaliApp, frozen: Object.isFrozen(window.kundaliApp) } : null
  if (scenario === 'save') {
    const body = pattern(2000000)
    out.sha = sha(body)
    new HTMLAnchorElement(blobUrl(new Blob([body], { type: 'application/pdf' })), 'Asha_kundali.pdf').click()
  } else if (scenario === 'anchors') {
    new HTMLAnchorElement('http://pi.local:8777/api/charts/1/dasha.csv', 'dasha.csv').click()
    new HTMLAnchorElement('https://github.com/chinmay28', '').click()
    new HTMLAnchorElement('http://pi.local:8777/#/new').click()
  } else if (scenario === 'tap') {
    const a = new HTMLAnchorElement(blobUrl(new Blob(['a,b\n'], { type: 'text/csv' })), 'positions.csv')
    const e = { target: a, defaultPrevented: false, preventDefault() { this.defaultPrevented = true } }
    listeners.filter(([t]) => t === 'click').forEach(([, fn]) => fn(e))
    out.prevented = e.defaultPrevented
  } else if (scenario === 'share') {
    const body = pattern(1000)
    out.sha = sha(body)
    out.canShare = navigator.canShare({ files: [1] })
    await navigator.share({ files: [new File([body], 'Asha_kundali.pdf', { type: 'application/pdf' })], title: 'Asha - Janma Kundali' })
  } else if (scenario === 'settings') {
    await window.kundaliApp.openSettings()
  } else if (scenario === 'plain') {
    new HTMLAnchorElement(blobUrl(new Blob(['x'])), 'x.pdf').click()
  }
  // A transfer is done when the native side has its end (or abort).
  for (let i = 0; i < 200 && scenario === 'save' && !native.messages.some((m) => m.t === 'end' || m.t === 'abort'); i++) await settle()
  await settle()
  out.nativeClicks = nativeClicks
  process.stdout.write(JSON.stringify(out))
})()
"""


@pytest.fixture(scope="module")
def node(tmp_path_factory):
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node is not installed")
    harness = tmp_path_factory.mktemp("bridge") / "harness.cjs"
    harness.write_text(HARNESS, encoding="utf-8")

    def run(scenario, mode="app"):
        done = subprocess.run([exe, str(harness), str(BRIDGE_JS), mode,
                               scenario], capture_output=True, text=True,
                              timeout=60)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)
    return run


def test_the_page_knows_it_is_in_the_app(node):
    out = node("settings")
    assert out["app"]["platform"] == "android"
    assert out["app"]["version"] == "v2026.11.30"
    assert out["app"]["frozen"]
    assert out["native"]["settings"] == 1


def test_saving_a_report_reaches_the_app_in_order(node):
    """app.js saves by clicking an <a download> on a blob: address."""
    out = node("save")
    native = out["native"]
    kinds = [m["t"] for m in native["messages"]]
    # 2,000,000 bytes in 768 KB chunks: three of them, in order.
    assert kinds == ["begin", "chunk", "chunk", "chunk", "end"]
    assert [m["seq"] for m in native["messages"] if m["t"] == "chunk"] == [0, 1, 2]
    (f,) = native["files"].values()
    assert f["name"] == "Asha_kundali.pdf"
    assert f["mime"] == "application/pdf"
    assert f["action"] == "save"
    assert f["size"] == f["length"] == 2000000
    assert f["sha"] == out["sha"]
    assert out["nativeClicks"] == 0, "the web view's own click must not run too"
    assert out["warnings"] == []


def test_a_tapped_download_link_is_taken_too(node):
    out = node("tap")
    assert out["prevented"]
    (f,) = out["native"]["files"].values()
    assert (f["name"], f["action"]) == ("positions.csv", "save")


def test_only_downloads_on_the_server_are_fetched_by_the_app(node):
    out = node("anchors")
    assert out["native"]["fetched"] == [
        {"t": "fetch", "url": "http://pi.local:8777/api/charts/1/dasha.csv",
         "name": "dasha.csv", "re": 1}]
    # GitHub, and a plain in-page link, are left to the web view (and so to
    # NavigationPolicy).
    assert out["nativeClicks"] == 2


def test_share_stages_the_file_then_opens_the_sheet(node):
    out = node("share")
    native = out["native"]
    assert out["canShare"]
    (f,) = native["files"].values()
    assert (f["action"], f["name"], f["sha"]) == ("stage", "Asha_kundali.pdf",
                                                  out["sha"])
    (shared,) = native["shared"]
    assert shared["ids"] == list(native["files"])
    assert shared["title"] == "Asha - Janma Kundali"


def test_a_plain_browser_sees_none_of_it(node):
    out = node("plain", mode="plain")
    assert out["app"] is None
    assert out["nativeClicks"] == 1
    assert out["native"]["messages"] == []


def test_the_version_placeholder_is_what_page_bridge_replaces():
    js = BRIDGE_JS.read_text(encoding="utf-8")
    kt = PAGE_BRIDGE_KT.read_text(encoding="utf-8")
    assert js.count('"__KUNDALI_APP_VERSION__"') == 1
    assert '"\\"__KUNDALI_APP_VERSION__\\""' in kt
    assert 'OBJECT_NAME = "KundaliAndroid"' in kt
    assert "window.KundaliAndroid" in js


# ------------------------------------------------- the page's half of it
def test_app_js_saves_through_a_blob_anchor():
    """What the bridge catches: an <a download> on an object URL, clicked."""
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("async function download("):]
    body = body[:body.index("\n}\n")]
    assert "URL.createObjectURL" in body
    assert "a.download =" in body
    assert "a.click()" in body


def test_app_only_ui_hangs_off_window_kundali_app():
    """Additive: a plain browser renders exactly what it did before."""
    js = APP_JS.read_text(encoding="utf-8")
    assert "const inApp = () => Boolean(window.kundaliApp);" in js
    assert re.search(r"inApp\(\) \? '<button class=\"btn\" id=\"r-share\">", js)
    assert re.search(r"\(inApp\(\) \? card\('This app'", js)
    # Every other mention of the bridge object is behind one of those.
    uses = re.findall(r"window\.kundaliApp[.)]", js)
    assert len(uses) == 3, "a new use of window.kundaliApp needs a gate"
