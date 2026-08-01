/* app.js - the whole client. No framework, no build step.
   Views are rendered from template strings into #view; navigation is
   hash-based so the PWA restores where you left off. */
'use strict';

const $ = (s) => document.querySelector(s);
const view = $('#view');
const state = { charts: [], summary: null, tab: 'snapshot', tzs: null,
                diagram: 'north', installer: null };

const esc = (s) => String(s === null || s === undefined ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

/* ------------------------------------------------------------- network */
async function api(path, opts) {
  const res = await fetch(path, Object.assign({
    headers: { 'Content-Type': 'application/json' }
  }, opts || {}));
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (!res.ok) throw new Error((data && data.error) || `HTTP ${res.status}`);
  return data;
}

function toast(msg, isError) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast' + (isError ? ' err' : '');
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.hidden = true; }, isError ? 5200 : 2600);
}

function busy(on, text) {
  $('#overlay-text').textContent = text || 'Working…';
  $('#overlay').hidden = !on;
}

async function download(url, fallbackName, label) {
  busy(true, label || 'Preparing your download…');
  try {
    const res = await fetch(url);
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try { msg = (await res.json()).error || msg; } catch (e) { /* noop */ }
      throw new Error(msg);
    }
    const disp = res.headers.get('Content-Disposition') || '';
    const m = disp.match(/filename="([^"]+)"/);
    const blob = await res.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = href;
    a.download = (m && m[1]) || fallbackName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(href), 60000);
    toast('Downloaded ' + a.download);
  } catch (err) {
    toast(err.message, true);
  } finally {
    busy(false);
  }
}

/* -------------------------------------------------------------- pieces */
const kv = (rows) => `<div class="scroll-x"><table class="kv">${rows.map(
  (r) => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join('')}
  </table></div>`;

const table = (head, rows, numCols) => `<div class="scroll-x"><table>
  <tr>${head.map((h, i) => `<th class="${(numCols || []).includes(i) ? 'num' : ''}">${esc(h)}</th>`).join('')}</tr>
  ${rows.map((r) => `<tr>${r.map((c, i) => `<td class="${(numCols || []).includes(i) ? 'num' : ''}">${esc(c)}</td>`).join('')}</tr>`).join('')}
  </table></div>`;

const hint = (text) => text ? `<p class="hint">${esc(text)}</p>` : '';

const card = (title, body, extra) => `<section class="card">
  ${title ? `<h2>${esc(title)}${extra ? `<span class="small muted">${esc(extra)}</span>` : ''}</h2>` : ''}
  ${body}</section>`;

/* `lo`/`hi` scale the bar; `weak`/`strong` are the classical reading
   thresholds that colour it. */
function bars(items, lo, hi, weak, strong) {
  return `<div class="bars">${items.map((it) => {
    const pct = Math.round(((it.value - lo) / Math.max(hi - lo, 1)) * 100);
    const cls = it.value >= strong ? 'high' : (it.value <= weak ? 'low' : '');
    return `<div class="b"><span>${esc(it.label)}</span>
      <div class="track"><i class="fill ${cls}" style="width:${Math.max(pct, 4)}%"></i></div>
      <span class="v">${esc(it.value)}</span></div>`;
  }).join('')}</div>`;
}

/* -------------------------------------------------------------- router */
const routes = [
  [/^$/, home],
  [/^new$/, () => form(null)],
  [/^data$/, dataView],
  [/^chart\/(\d+)$/, (id) => chart(id)],
  [/^chart\/(\d+)\/edit$/, (id) => editChart(id)]
];

function go(hash) { location.hash = hash; }

async function route() {
  const path = location.hash.replace(/^#\/?/, '');
  $('#tabbar').hidden = true;
  view.classList.remove('has-tabs');
  $('#bar-action').hidden = true;
  $('#back').hidden = path === '';
  for (const [re, fn] of routes) {
    const m = path.match(re);
    if (m) {
      try { await fn(m[1]); } catch (err) { fail(err); }
      window.scrollTo(0, 0);
      return;
    }
  }
  go('/');
}

function fail(err) {
  view.innerHTML = card('Something went wrong',
    `<p class="muted">${esc(err.message)}</p>
     <button class="btn" onclick="location.reload()">Reload</button>`);
}

function setTitle(t) { $('#title').textContent = t; }

/* ---------------------------------------------------------------- home */
async function home() {
  setTitle('Kundali');
  const action = $('#bar-action');
  action.hidden = false;
  action.textContent = '⋯';
  action.setAttribute('aria-label', 'Data and backup');
  action.onclick = () => go('/data');

  state.charts = (await api('/api/charts')).charts;
  const cards = state.charts.map((c) => `
    <button class="list-card" data-id="${c.id}">
      <div class="nm">${esc(c.name)}</div>
      <div class="meta">${esc(c.birth_date)} · ${esc(c.birth_time)} · ${esc(c.tz)}</div>
      <div class="meta">${esc(c.place || `${(+c.lat).toFixed(2)}, ${(+c.lon).toFixed(2)}`)}
        · ${esc(c.ayanamsa)}</div>
    </button>`).join('');

  view.innerHTML = (state.charts.length ? `
    <input id="filter" type="search" placeholder="Search charts"
           autocomplete="off" style="margin-bottom:12px">
    <div id="cards">${cards}</div>` : `
    <div class="empty"><span class="glyph">✳</span>
      <p>No charts saved yet.</p>
      <p class="small">Add a birth date, time and place — the server keeps
         them in one SQLite file that every device you open this on shares.</p>
    </div>`) + `<button class="fab" id="add" aria-label="New chart">+</button>`;

  $('#add').onclick = () => go('/new');
  view.querySelectorAll('.list-card').forEach((el) => {
    el.onclick = () => go('/chart/' + el.dataset.id);
  });
  const filter = $('#filter');
  if (filter) {
    filter.oninput = () => {
      const q = filter.value.toLowerCase();
      view.querySelectorAll('.list-card').forEach((el) => {
        el.hidden = !el.textContent.toLowerCase().includes(q);
      });
    };
  }
}

/* ---------------------------------------------------------------- form */
async function ensureTimezones() {
  if (!state.tzs) state.tzs = (await api('/api/timezones')).timezones;
  return state.tzs;
}

async function editChart(id) {
  const rec = (await api('/api/charts/' + id)).chart;
  form(rec);
}

async function form(rec) {
  setTitle(rec ? 'Edit chart' : 'New chart');
  const tzs = await ensureTimezones();
  const guess = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const v = rec || { name: '', birth_date: '', birth_time: '', tz: guess,
                     lat: '', lon: '', place: '', ayanamsa: 'raman',
                     varsha_years: '', notes: '' };

  view.innerHTML = card(null, `
    <label for="f-name">Name</label>
    <input id="f-name" value="${esc(v.name)}" autocomplete="name" placeholder="Whose chart is this?">
    <div class="row">
      <div><label for="f-date">Birth date</label>
        <input id="f-date" type="date" value="${esc(v.birth_date)}"></div>
      <div><label for="f-time">Local time</label>
        <input id="f-time" type="time" value="${esc(v.birth_time)}"></div>
    </div>
    <label for="f-tz">Timezone (IANA — historical DST is applied)</label>
    <input id="f-tz" list="tzlist" value="${esc(v.tz)}" autocapitalize="off"
           autocomplete="off" spellcheck="false" placeholder="Asia/Kolkata">
    <datalist id="tzlist">${tzs.map((t) => `<option value="${esc(t)}">`).join('')}</datalist>
    <div class="row">
      <div><label for="f-lat">Latitude (+N)</label>
        <input id="f-lat" type="number" step="any" inputmode="decimal" value="${esc(v.lat)}"></div>
      <div><label for="f-lon">Longitude (+E)</label>
        <input id="f-lon" type="number" step="any" inputmode="decimal" value="${esc(v.lon)}"></div>
    </div>
    <button class="btn small" id="f-here" style="margin-top:10px">
      ◎ Use this device's location</button>
    <p class="hint">Coordinates are an explicit input by design: look the
      birthplace up once in any map app. Nothing is geocoded for you.</p>
    <label for="f-place">Place label</label>
    <input id="f-place" value="${esc(v.place)}" placeholder="Sirsi, Karnataka, India">
    <label for="f-ayan">Ayanamsa</label>
    <select id="f-ayan">
      <option value="raman"${v.ayanamsa === 'raman' ? ' selected' : ''}>Raman</option>
      <option value="lahiri"${v.ayanamsa === 'lahiri' ? ' selected' : ''}>Lahiri</option>
    </select>
    <label for="f-varsha">Varshaphala years (optional)</label>
    <input id="f-varsha" value="${esc(v.varsha_years)}" inputmode="numeric"
           placeholder="2026, 2027, 2028">
    <label for="f-notes">Notes</label>
    <textarea id="f-notes" rows="2">${esc(v.notes)}</textarea>
    <div style="margin-top:18px">
      <button class="btn primary" id="f-save">${rec ? 'Save changes' : 'Save & open'}</button>
      ${rec ? '<button class="btn danger" id="f-del">Delete chart</button>' : ''}
    </div>`);

  $('#f-here').onclick = () => {
    if (!navigator.geolocation) return toast('No geolocation on this device', true);
    busy(true, 'Reading device location…');
    navigator.geolocation.getCurrentPosition((pos) => {
      busy(false);
      $('#f-lat').value = pos.coords.latitude.toFixed(4);
      $('#f-lon').value = pos.coords.longitude.toFixed(4);
      toast('Filled from device GPS — edit if the birthplace differs');
    }, (err) => { busy(false); toast(err.message, true); },
      { timeout: 10000 });
  };

  $('#f-save').onclick = async () => {
    const body = {
      name: $('#f-name').value, birth_date: $('#f-date').value,
      birth_time: $('#f-time').value, tz: $('#f-tz').value,
      lat: $('#f-lat').value, lon: $('#f-lon').value,
      place: $('#f-place').value, ayanamsa: $('#f-ayan').value,
      varsha_years: $('#f-varsha').value, notes: $('#f-notes').value
    };
    busy(true, 'Casting the chart…');
    try {
      const out = rec
        ? await api('/api/charts/' + rec.id, { method: 'PUT', body: JSON.stringify(body) })
        : await api('/api/charts', { method: 'POST', body: JSON.stringify(body) });
      toast('Saved');
      go('/chart/' + out.chart.id);
    } catch (err) {
      toast(err.message, true);
    } finally {
      busy(false);
    }
  };

  if (rec) {
    $('#f-del').onclick = async () => {
      if (!confirm(`Delete ${rec.name}? This cannot be undone.`)) return;
      await api('/api/charts/' + rec.id, { method: 'DELETE' });
      toast('Deleted');
      go('/');
    };
  }
}

/* --------------------------------------------------------------- chart */
const TABS = [
  ['snapshot', '✶', 'Snapshot'],
  ['charts', '◈', 'Charts'],
  ['dasha', '↻', 'Dasha'],
  ['strength', '▤', 'Strength'],
  ['shani', '♄', 'Shani'],
  ['report', '⤓', 'Report']
];

async function chart(id, asof) {
  setTitle('Loading…');
  busy(true, 'Computing the chart…');
  try {
    const q = asof ? '?asof=' + encodeURIComponent(asof) : '';
    state.summary = await api(`/api/charts/${id}/summary${q}`);
  } finally {
    busy(false);
  }
  const s = state.summary;
  setTitle(s.identity.name);

  const action = $('#bar-action');
  action.hidden = false;
  action.textContent = '✎';
  action.setAttribute('aria-label', 'Edit chart');
  action.onclick = () => go(`/chart/${id}/edit`);

  const tabbar = $('#tabbar');
  tabbar.hidden = false;
  view.classList.add('has-tabs');
  tabbar.innerHTML = TABS.map(([key, glyph, label]) =>
    `<button data-tab="${key}" class="${state.tab === key ? 'on' : ''}">
       <span class="g">${glyph}</span>${esc(label)}</button>`).join('');
  tabbar.querySelectorAll('button').forEach((b) => {
    b.onclick = () => {
      state.tab = b.dataset.tab;
      tabbar.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
      renderTab();
      window.scrollTo(0, 0);
    };
  });
  renderTab();
}

function renderTab() {
  const s = state.summary;
  const fn = { snapshot: tabSnapshot, charts: tabCharts, dasha: tabDasha,
               strength: tabStrength, shani: tabShani, report: tabReport };
  view.innerHTML = (fn[state.tab] || tabSnapshot)(s);
  if (state.tab === 'charts') wireDiagrams();
  if (state.tab === 'report') wireReport(s);
}

function tabSnapshot(s) {
  const i = s.identity;
  const flags = []
    .concat(s.sandhi.length ? [`<span class="chip warn">Sandhi: ${esc(s.sandhi.join(', '))}</span>`] : [])
    .concat(s.combust.length ? [`<span class="chip warn">Combust: ${esc(s.combust.join(', '))}</span>`] : [])
    .concat(s.navamsa.vargottama.length ? [`<span class="chip good">Vargottama: ${esc(s.navamsa.vargottama.join(', '))}</span>`] : []);

  return card(i.name, `
      <p class="muted mono">${esc(i.when)} · ${esc(i.tz)}</p>
      <p class="muted">${esc(i.place || '')} <span class="mono">(${i.lat.toFixed(4)}, ${i.lon.toFixed(4)})</span></p>
      <p><span class="chip gold">Lagna ${esc(i.lagna)} ${i.lagna_deg}°</span>
         <span class="chip gold">Rashi ${esc(i.rashi)}</span>
         <span class="chip">${esc(i.nakshatra)} pada ${i.pada}</span>
         <span class="chip">${esc(i.ayanamsa)} ${i.ayanamsa_deg}°</span>
         <span class="chip">Age ${i.age}</span></p>
      ${flags.length ? `<p>${flags.join(' ')}</p>` : ''}`)
    + card('Input verification', kv(s.verification) + hint(s.guidance.verification))
    + card('Panchanga at birth', kv(s.panchanga.rows) + hint(s.guidance.panchanga)
        + '<h3>Avakahada</h3>' + kv(s.panchanga.avakahada) + hint(s.guidance.avakahada))
    + card('Yogas & combinations', (s.yogas.length ? s.yogas.map((y) =>
        `<p><b style="color:var(--gold)">${esc(y.name)}.</b> ${esc(y.detail)}</p>`).join('')
        : '<p class="muted">No classical yoga from the tested set is formed.</p>')
        + hint(s.guidance.yogas));
}

function tabCharts(s) {
  const d = s.diagrams;
  const which = state.diagram;
  const svg = which === 'north' ? d.north : (which === 'south' ? d.south : d.navamsa);
  const label = { north: 'North Indian (houses fixed)',
                  south: 'South Indian (signs fixed)',
                  navamsa: 'Navamsa D-9 (South Indian)' }[which];
  return card('Chart diagrams', `
      <div class="seg" id="segd">
        <button data-d="north" class="${which === 'north' ? 'on' : ''}">North</button>
        <button data-d="south" class="${which === 'south' ? 'on' : ''}">South</button>
        <button data-d="navamsa" class="${which === 'navamsa' ? 'on' : ''}">D-9</button>
      </div>
      <div class="diagram">${svg}<p>${esc(label)}</p></div>
      ${hint(s.guidance.diagrams)}`)
    + card('Graha positions', table(
        ['Graha', 'Rashi', 'Deg', 'Nakshatra', 'Pada', 'H', 'Dignity'],
        s.positions.map((p) => [p.body + (p.retro ? ' (R)' : ''), p.sign,
          p.deg.toFixed(2), p.nakshatra, p.pada, p.house, p.dignity]),
        [2, 4, 5]) + hint(s.guidance.positions))
    + card('Houses, occupants & drishti', `
        <p class="small muted">Mutual aspects: ${s.aspects.mutual.length
          ? s.aspects.mutual.map((p) => esc(p[0] + ' ↔ ' + p[1])).join('; ')
          : 'none'}</p>`
        + table(['H', 'Sign', 'Occupants', 'Aspected by'],
            s.aspects.houses.map((h) => [h.house, h.sign,
              h.occupants.join(', ') || '—', h.aspected_by.join(', ') || '—']))
        + hint(s.guidance.aspects))
    + card('Bhav Chalit', (s.bhav.shifts.length
        ? `<p class="small">House shifts vs whole sign: ` + s.bhav.shifts.map((x) =>
            `${esc(x.planet)} ${x.whole_sign}→${x.chalit}`).join(', ') + '</p>'
        : '<p class="small muted">No planet shifts house between the two systems.</p>')
        + `<details><summary>Bhava spans</summary>${table(s.bhav.table[0], s.bhav.table.slice(1))}</details>`
        + hint(s.guidance.bhav));
}

function wireDiagrams() {
  view.querySelectorAll('#segd button').forEach((b) => {
    b.onclick = () => { state.diagram = b.dataset.d; renderTab(); };
  });
}

function periodCard(p) {
  return `<div class="period">
    <div class="lvl">${esc(p.level)}</div>
    <div class="nm">${esc(p.label)}</div>
    <div class="dt">${esc(p.from)} → ${esc(p.to)}</div>
    ${p.current ? `<div class="progress"><i style="width:${
      Math.round((p.progress || 0) * 100)}%"></i></div>` : ''}
  </div>`;
}

function tabDasha(s) {
  const dn = s.dasha_now;
  const timeline = s.mahadashas.map((m) => `
    <details${m.current ? ' open' : ''}>
      <summary>${esc(m.lord)} · ${esc(m.from)} → ${esc(m.to)}${m.current ? ' · running' : ''}</summary>
      ${m.current ? `<div class="progress"><i style="width:${Math.round(m.progress * 100)}%"></i></div>` : ''}
      ${table(['Antardasha', 'From', 'To'], m.antardashas.map((a) =>
        [`${a.lord}-${a.sub}`, a.from, a.to]))}
    </details>`).join('');

  const varsha = s.varsha.length ? card('Tajika varshaphala',
    s.varsha.map((v) => `
      <h3>${v.year} · age ${v.age}</h3>
      <p class="small muted mono">Pravesh ${esc(v.pravesh)} · Lagna ${esc(v.lagna)}</p>
      <p class="small">Muntha in ${esc(v.muntha_sign)} — house ${v.muntha_house}
         (${esc(v.grade)}), lord ${esc(v.muntha_lord)}</p>
      <div class="diagram">${v.north}</div>
      <details><summary>Mudda dasha</summary>${table(['Lord', 'From', 'To'],
        v.mudda.map((p) => [p.lord, p.from, p.to]))}</details>`).join('')
    + hint(s.guidance.varshaphal)) : '';

  return card(`Dasha as of ${esc(s.asof)}`,
      dn.running.map(periodCard).join('')
      + dn.notes.map((n) => `<p class="hint">${esc(n)}</p>`).join('')
      + '<h3>Coming up</h3>' + dn.next.map(periodCard).join('')
      + hint(s.guidance.dashanow))
    + card('Navigation guidance', dn.guidance.map((g) => `
        <h3>${esc(g.role)}: ${esc(g.planet)}</h3>
        <p class="small muted">House ${g.house} · ${esc(g.sign)} · ${esc(g.dignity)}${
          g.score ? ` · Vimshopaka ${g.score}/20` : ''}</p>
        <p>${esc(g.text)}</p>`).join(''))
    + card('Vimshottari timeline', timeline + hint(s.guidance.dasha))
    + varsha;
}

function tabStrength(s) {
  const av = s.ashtakavarga;
  const savBars = bars(av.houses.map((h) => ({
    label: `H${h.house} ${h.sign.slice(0, 3)}`, value: h.sav })), 16, 42, 24, 30);
  const vim = Object.entries(s.navamsa.vimshopaka)
    .sort((a, b) => b[1] - a[1])
    .map(([p, v]) => ({ label: p, value: v }));

  return card('Sarvashtakavarga', savBars
      + `<p class="small muted">30 bindus or more is strong ground for a
         transit; 24 or fewer is thin.</p>`
      + `<p class="small muted">Total ${av.sav.reduce((a, b) => a + b, 0)} bindus
         (the classical checksum is 337).</p>`
      + `<details><summary>Bhinnashtakavarga per planet</summary>${table(
          ['Graha'].concat(av.signs.map((x) => x.slice(0, 3))),
          Object.entries(av.bav).map(([p, vals]) => [p].concat(vals)))}</details>`
      + hint(s.guidance.ashtakavarga))
    + card('Vimshopaka Bala', bars(vim, 0, 20, 10, 15)
      + (s.navamsa.vargottama.length
        ? `<p class="small">Vargottama: ${esc(s.navamsa.vargottama.join(', '))}</p>` : '')
      + `<details><summary>Shodashavarga table</summary>${table(
          s.navamsa.shodashavarga[0], s.navamsa.shodashavarga.slice(1))}</details>`
      + hint(s.guidance.shodashavarga))
    + card('Navamsa D-9 positions', table(
        ['Graha', 'Rashi', 'Deg', 'Nakshatra', 'H'],
        s.navamsa.positions.map((p) => [p.body, p.sign, p.deg.toFixed(2),
          p.nakshatra, p.house]), [2]))
    + card('Panchadha Maitri', table(s.maitri[0], s.maitri.slice(1))
      + hint(s.guidance.maitri))
    + card('Avasthas', table(s.avastha[0], s.avastha.slice(1))
      + hint(s.guidance.avasthas));
}

function tabShani(s) {
  const sd = s.sadesati;
  const gradeChip = { mild: 'good', moderate: 'warn', demanding: 'bad' }[sd.grade] || '';
  const span = (x, title) => x ? `
    <h3>${esc(title)}</h3>
    <p class="mono muted small">${esc(x.from)} → ${esc(x.to)} · Saturn in ${esc(x.sign)}</p>
    <p><b style="color:var(--gold)">${esc(x.phase)}</b></p>
    <p class="small">${esc(x.impact)}</p>
    ${x.murti !== '-' ? `<p class="small muted">Murti at ingress: ${esc(x.murti)} (${esc(x.murti_grade)})</p>` : ''}`
    : `<h3>${esc(title)}</h3><p class="muted small">None found in the computed window.</p>`;

  return card('How Sade Sati tends to run for this chart',
      `<p><span class="chip ${gradeChip}">${esc(sd.grade)}</span></p>`
      + kv(sd.factors.map((f) => [f.factor, f.finding]))
      + hint(s.guidance.sadesati))
    + card('Current & next', span(sd.active, 'Active now') + span(sd.next, 'Next phase'))
    + card('Navigation', `<p class="small">${esc(sd.navigation)}</p>`)
    + card('Lifetime table', table(['From', 'To', 'Saturn in', 'Phase', 'Murti'],
        sd.lifetime.map((r) => [r.from, r.to, r.sign, r.phase, r.murti])));
}

function tabReport(s) {
  const id = s.chart.id;
  return card('Download reports', `
      <label for="r-asof">As-of date (drives “Dasha now” and Sade Sati)</label>
      <input id="r-asof" type="date" value="${esc(s.asof)}">
      <label for="r-varsha">Varshaphala years for the report</label>
      <input id="r-varsha" inputmode="numeric" value="${esc(s.chart.varsha_years || '')}"
             placeholder="2026, 2027">
      <button class="btn small" id="r-apply" style="margin:10px 0 16px">
        Recompute this view</button>
      <button class="btn primary" id="r-pdf">⤓ PDF report</button>
      <button class="btn" id="r-html">⤓ HTML report (single file)</button>
      <div class="row" style="margin-top:10px">
        <button class="btn small" id="r-json">JSON</button>
        <button class="btn small" id="r-csv">Positions CSV</button>
        <button class="btn small" id="r-dasha">Dasha CSV</button>
      </div>
      <p class="hint">The PDF is generated by the same code the command line
        uses, so a report downloaded here is byte-for-byte what
        kundali-report would write. Full reports with several varsha years
        take a few seconds.</p>`)
    + card('This chart', kv([
        ['Saved as', s.chart.name], ['Birth', `${s.chart.birth_date} ${s.chart.birth_time}`],
        ['Timezone', s.chart.tz], ['Place', s.chart.place || '—'],
        ['Coordinates', `${(+s.chart.lat).toFixed(4)}, ${(+s.chart.lon).toFixed(4)}`],
        ['Ayanamsa', s.chart.ayanamsa],
        ['Notes', s.chart.notes || '—']]) + `
      <button class="btn small" id="r-edit" style="margin-top:12px">Edit details</button>`)
    + card('Reading it', hint(s.guidance.closing));
}

function wireReport(s) {
  const id = s.chart.id;
  const qs = () => {
    const asof = $('#r-asof').value;
    const varsha = $('#r-varsha').value.trim();
    const p = new URLSearchParams();
    if (asof) p.set('asof', asof);
    p.set('varsha', varsha);
    return '?' + p.toString();
  };
  $('#r-apply').onclick = () => chart(id, $('#r-asof').value);
  $('#r-pdf').onclick = () => download(`/api/charts/${id}/report.pdf` + qs(),
    'kundali.pdf', 'Rendering the PDF…');
  $('#r-html').onclick = () => download(`/api/charts/${id}/report.html` + qs(),
    'kundali.html', 'Rendering the HTML report…');
  $('#r-json').onclick = () => download(`/api/charts/${id}/export.json` + qs(), 'kundali.json');
  $('#r-csv').onclick = () => download(`/api/charts/${id}/positions.csv`, 'positions.csv');
  $('#r-dasha').onclick = () => download(`/api/charts/${id}/dasha.csv`, 'dasha.csv');
  $('#r-edit').onclick = () => go(`/chart/${id}/edit`);
}

/* ---------------------------------------------------------------- data */
async function dataView() {
  setTitle('Data & backup');
  const health = await api('/api/health');
  view.innerHTML = card('Backups', `
      <p class="small muted">Open formats only: a JSON document, per-table
         CSV, or the SQLite file itself.</p>
      <button class="btn" id="d-json">⤓ All charts (JSON)</button>
      <button class="btn" id="d-csv">⤓ All charts (CSV)</button>
      <button class="btn" id="d-db">⤓ kundali.sqlite</button>
      <h3>Restore</h3>
      <p class="small muted">Importing a JSON backup merges it in; records
         matching an existing birth identity are updated, not duplicated.</p>
      <input id="d-file" type="file" accept="application/json,.json">`)
    + card('Server', kv([['Database', health.db],
        ['Saved charts', health.charts],
        ['Version', 'kundali-report v' + health.version],
        ['Authentication', 'none — keep this on a trusted network']]))
    + card('About', `
      <p class="small muted">Jyotish computation with the Swiss Ephemeris —
         sidereal, whole-sign houses, mean node. The web app, the PDF and the
         HTML report all run the same code.</p>
      <p class="small">Built by <b style="color:var(--gold)">CM Hegday</b>
         · 0x434d<br>
         <a href="https://github.com/chinmay28" target="_blank" rel="noopener">github.com/chinmay28</a>
         · <a href="https://github.com/chinmay28/vedic-astrology" target="_blank" rel="noopener">source</a></p>`)
    + card('Install on your phone', `
      <p class="small muted">Add this to your home screen and it opens
         full-screen, works offline for charts you have already viewed, and
         keeps using the same server database.</p>
      <button class="btn" id="d-install">Install app</button>
      <p class="small muted" id="d-install-note">On iOS: Share → Add to Home Screen.</p>`);

  $('#d-json').onclick = () => download('/api/export/charts.json', 'kundali-charts.json');
  $('#d-csv').onclick = () => download('/api/export/charts.csv', 'kundali-charts.csv');
  $('#d-db').onclick = () => download('/api/export/kundali.sqlite', 'kundali.sqlite');
  $('#d-file').onchange = async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    busy(true, 'Importing…');
    try {
      const out = await api('/api/import',
        { method: 'POST', body: await file.text() });
      toast(`Imported: ${out.added} added, ${out.updated} updated`);
    } catch (err) {
      toast(err.message, true);
    } finally {
      busy(false);
      ev.target.value = '';
    }
  };
  const btn = $('#d-install');
  btn.disabled = !state.installer;
  btn.onclick = async () => {
    if (!state.installer) return;
    state.installer.prompt();
    state.installer = null;
    btn.disabled = true;
  };
}

/* --------------------------------------------------- brand & dev badge */
async function showVersion() {
  try {
    const h = await api('/api/health');
    $('#version').textContent = 'v' + h.version;
  } catch (e) { /* offline: leave it blank rather than lie */ }
}

/* Tap the badge for the maker's mark; it clears itself after a beat. */
function wireDevBadge() {
  const flash = $('#dev-flash');
  let timer = null;
  const close = () => { flash.hidden = true; clearTimeout(timer); };
  $('#dev-badge').onclick = () => {
    flash.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(close, 3000);
  };
  flash.onclick = (ev) => {
    if (ev.target.tagName !== 'A') close();     // let the link through
  };
  window.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && !flash.hidden) close();
  });
}

/* ---------------------------------------------------------------- boot */
$('#back').onclick = () => history.back();
wireDevBadge();
showVersion();
window.addEventListener('hashchange', route);
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  state.installer = e;
  const btn = $('#d-install');
  if (btn) btn.disabled = false;
});
route();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* fine */ });
  });
}
