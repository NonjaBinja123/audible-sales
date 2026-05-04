'use strict';

const DATA_URL   = '../data/sales.json';
const BAYESIAN_M = 100;

// ─── Column definitions ───────────────────────────────────────────────────────
// key: internal id | label: header text | always: can't hide | def: on by default
// sort: sortable | filter: false|'list'|'range' | dk: data key on sale object

const COLUMNS = [
  { key:'fav',           label:'★',          always:true,  def:true,  sort:false, filter:false,   dk:null },
  { key:'cover',         label:'Cover',       always:false, def:true,  sort:false, filter:false,   dk:null },
  { key:'title',         label:'Title',       always:true,  def:true,  sort:true,  filter:'list',  dk:'title' },
  { key:'type',          label:'Type',        always:false, def:true,  sort:true,  filter:'list',  dk:'type' },
  { key:'author',        label:'Author',      always:false, def:true,  sort:true,  filter:'list',  dk:'author' },
  { key:'narrator',      label:'Narrator',    always:false, def:false, sort:true,  filter:'list',  dk:'narrator' },
  { key:'genre',         label:'Genre',       always:false, def:false, sort:true,  filter:'list',  dk:'genre' },
  { key:'length_hours',  label:'Length (h)',  always:false, def:true,  sort:true,  filter:'range', dk:'length_hours' },
  { key:'rating',        label:'Rating',      always:false, def:true,  sort:true,  filter:'range', dk:'rating' },
  { key:'rating_count',  label:'# Ratings',  always:false, def:true,  sort:true,  filter:'range', dk:'rating_count' },
  { key:'bayesian',      label:'Bayesian',    always:false, def:false, sort:true,  filter:'range', dk:'bayesian' },
  { key:'weighted',      label:'Weighted',    always:false, def:false, sort:true,  filter:'range', dk:'weighted' },
  { key:'price',         label:'Sale Price',  always:false, def:true,  sort:true,  filter:'range', dk:'price' },
  { key:'regular_price', label:'List Price',  always:false, def:true,  sort:true,  filter:'range', dk:'regular_price' },
  { key:'asin',          label:'ASIN',        always:false, def:false, sort:false, filter:false,   dk:'asin' },
];

// ─── State ────────────────────────────────────────────────────────────────────

let allSales     = [];
let filtered     = [];
let sortKey      = 'title';
let sortAsc      = true;
let favorites    = new Set(JSON.parse(localStorage.getItem('audible_favs') || '[]'));
let ownedAsins   = new Set();
let visibleCols  = new Set(
  JSON.parse(localStorage.getItem('audible_cols') ||
    JSON.stringify(COLUMNS.filter(c => c.def).map(c => c.key)))
);
// colFilters[dk] = { type:'list', excluded:Set } | { type:'range', min, max }
let colFilters   = {};
let openFilterKey = null;

// ─── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  showTosBanner();
  buildColSelector();

  try {
    const data = await fetch(DATA_URL).then(r => r.json());
    const rated = data.sales.filter(s => s.rating != null);
    const globalAvg = rated.reduce((a, s) => a + s.rating, 0) / (rated.length || 1);

    allSales = data.sales.map(s => ({
      ...s,
      bayesian: computeBayesian(s.rating, s.rating_count, globalAvg),
      weighted: computeWeighted(s.rating, s.rating_count),
    }));

    const el = document.getElementById('last-updated');
    if (data.last_updated)
      el.textContent = 'Updated: ' + new Date(data.last_updated + 'Z').toLocaleString();

    renderHeader();
    applyFilters();
  } catch(e) {
    document.getElementById('sales-tbody').innerHTML =
      `<tr><td colspan="20" class="empty-msg">Failed to load data: ${e.message}</td></tr>`;
  }
}

// ─── Quality metrics ──────────────────────────────────────────────────────────

function computeBayesian(rating, count, globalAvg) {
  if (rating == null || count == null) return null;
  return (count / (count + BAYESIAN_M)) * rating + (BAYESIAN_M / (count + BAYESIAN_M)) * globalAvg;
}

function computeWeighted(rating, count) {
  if (rating == null || count == null) return null;
  return rating * Math.log10(count + 1);
}

// ─── ToS ──────────────────────────────────────────────────────────────────────

function showTosBanner() {
  if (!localStorage.getItem('audible_tos'))
    document.getElementById('tos-banner').hidden = false;
}
function dismissTos() {
  localStorage.setItem('audible_tos', '1');
  document.getElementById('tos-banner').hidden = true;
}

// ─── Column selector ──────────────────────────────────────────────────────────

function buildColSelector() {
  const panel = document.getElementById('col-selector');
  panel.innerHTML = COLUMNS.filter(c => !c.always).map(c => `
    <label class="cs-item">
      <input type="checkbox" ${visibleCols.has(c.key) ? 'checked' : ''}
             onchange="toggleCol('${c.key}',this.checked)">
      ${c.label}
    </label>`).join('');
}

function toggleColPanel() {
  const p = document.getElementById('col-selector');
  p.hidden = !p.hidden;
  if (!p.hidden) {
    const onOut = e => {
      if (p.contains(e.target) || e.target.closest('#cols-btn')) return;
      p.hidden = true;
      document.removeEventListener('mousedown', onOut);
    };
    setTimeout(() => document.addEventListener('mousedown', onOut), 0);
  }
}

function toggleCol(key, on) {
  on ? visibleCols.add(key) : visibleCols.delete(key);
  localStorage.setItem('audible_cols', JSON.stringify([...visibleCols]));
  renderHeader();
  renderBody();
}

// ─── Filter logic ─────────────────────────────────────────────────────────────

function isFilterActive(dk) {
  const f = colFilters[dk];
  if (!f) return false;
  if (f.type === 'list')  return f.excluded.size > 0;
  if (f.type === 'range') return f.min != null || f.max != null;
  return false;
}

function applyFilters() {
  const favsOnly = document.getElementById('favs-only').checked;

  filtered = allSales.filter(s => {
    if (favsOnly && !favorites.has(s.asin)) return false;

    for (const [dk, f] of Object.entries(colFilters)) {
      if (f.type === 'list' && f.excluded.size > 0) {
        const sv = s[dk] == null ? '(blank)' : String(s[dk]);
        if (f.excluded.has(sv)) return false;
      }
      if (f.type === 'range') {
        const nv = s[dk] == null ? null : +s[dk];
        if (f.min != null && (nv == null || nv < f.min)) return false;
        if (f.max != null && (nv == null || nv > f.max)) return false;
      }
    }
    return true;
  });

  applySort();
}

// ─── Sort ─────────────────────────────────────────────────────────────────────

function toggleSort(dk) {
  if (sortKey === dk) sortAsc = !sortAsc;
  else { sortKey = dk; sortAsc = true; }
  renderHeader();
  applySort();
}

function applySort() {
  filtered.sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (va == null && vb == null) return 0;
    if (va == null) return sortAsc  ?  1 : -1;
    if (vb == null) return sortAsc  ? -1 :  1;
    if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  });
  renderBody();
}

// ─── Render ───────────────────────────────────────────────────────────────────

function renderHeader() {
  const tr = document.querySelector('#sales-table thead tr');
  tr.innerHTML = '';

  for (const col of COLUMNS) {
    if (!col.always && !visibleCols.has(col.key)) continue;

    const th  = document.createElement('th');
    const active = col.filter && isFilterActive(col.dk);
    if (active) th.classList.add('filtered');

    const inner = document.createElement('div');
    inner.className = 'th-inner';

    const lbl = document.createElement('span');
    lbl.className = 'th-label' + (col.sort ? ' sortable' : '');
    lbl.textContent = col.label;
    if (col.sort) {
      if (sortKey === col.dk) lbl.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
      lbl.onclick = () => toggleSort(col.dk);
    }
    inner.appendChild(lbl);

    if (col.filter) {
      const fbtn = document.createElement('button');
      fbtn.className = 'filter-btn' + (active ? ' active' : '');
      fbtn.textContent = '▾';
      fbtn.title = active ? 'Filter active — click to edit' : 'Filter';
      fbtn.onclick = e => { e.stopPropagation(); openFilter(col.key, fbtn); };
      inner.appendChild(fbtn);
    }

    th.appendChild(inner);
    tr.appendChild(th);
  }
}

function renderBody() {
  const tbody = document.getElementById('sales-tbody');
  const count = document.getElementById('count');
  count.textContent = filtered.length.toLocaleString() + ' title' + (filtered.length !== 1 ? 's' : '');

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="20" class="empty-msg">No results match your filters.</td></tr>';
    return;
  }

  const cols = COLUMNS.filter(c => c.always || visibleCols.has(c.key));
  const frag = document.createDocumentFragment();

  for (const sale of filtered) {
    const tr = document.createElement('tr');
    if (ownedAsins.has(sale.asin)) tr.classList.add('owned');
    cols.forEach(col => tr.appendChild(buildCell(sale, col)));
    frag.appendChild(tr);
  }

  tbody.replaceChildren(frag);
}

function buildCell(sale, col) {
  const td = document.createElement('td');

  switch (col.key) {
    case 'fav': {
      const btn = document.createElement('button');
      btn.className = 'star-btn' + (favorites.has(sale.asin) ? ' active' : '');
      btn.textContent = '★';
      btn.onclick = () => toggleFav(sale.asin, btn);
      td.appendChild(btn);
      break;
    }
    case 'cover': {
      if (sale.cover_url) {
        const img = document.createElement('img');
        img.src = sale.cover_url; img.alt = ''; img.className = 'cover-thumb'; img.loading = 'lazy';
        td.appendChild(img);
      }
      break;
    }
    case 'title': {
      const a = document.createElement('a');
      a.href = sale.audible_url; a.target = '_blank'; a.rel = 'noopener noreferrer';
      a.textContent = sale.title || '';
      td.appendChild(a);
      if (ownedAsins.has(sale.asin)) {
        const b = document.createElement('span');
        b.className = 'owned-badge'; b.textContent = 'Owned';
        td.appendChild(b);
      }
      break;
    }
    case 'type': {
      const b = document.createElement('span');
      b.className = sale.type === '2for1' ? 'badge badge-2for1' : 'badge badge-monthly';
      b.textContent = sale.type === '2for1' ? '2-for-1' : 'Monthly';
      td.appendChild(b);
      break;
    }
    case 'rating': {
      if (sale.rating != null) {
        const s = document.createElement('span');
        s.className = 'stars'; s.textContent = renderStars(sale.rating);
        td.appendChild(s);
        const n = document.createElement('small');
        n.textContent = ' ' + sale.rating.toFixed(1);
        td.appendChild(n);
      }
      break;
    }
    case 'rating_count':
      td.textContent = sale.rating_count != null ? sale.rating_count.toLocaleString() : '';
      td.className = 'num'; break;
    case 'bayesian':
      td.textContent = sale.bayesian != null ? sale.bayesian.toFixed(2) : '';
      td.className = 'num';
      td.title = 'Bayesian avg — pulls toward global mean when review count is low';
      break;
    case 'weighted':
      td.textContent = sale.weighted != null ? sale.weighted.toFixed(2) : '';
      td.className = 'num';
      td.title = 'Weighted score = rating × log₁₀(# ratings + 1)';
      break;
    case 'price':
      if (sale.type === '2for1') {
        const b = document.createElement('span');
        b.className = 'badge badge-2for1'; b.textContent = '1 credit';
        td.appendChild(b);
      } else if (sale.price != null) {
        td.textContent = '$' + sale.price.toFixed(2);
        td.className = 'price-sale num';
      }
      break;
    case 'regular_price':
      if (sale.regular_price != null) {
        td.textContent = '$' + sale.regular_price.toFixed(2);
        td.className = 'price-list num';
      }
      break;
    case 'length_hours':
      td.textContent = sale.length_hours != null ? sale.length_hours.toFixed(1) + ' h' : '';
      td.className = 'num'; break;
    default:
      td.textContent = sale[col.dk] ?? '';
  }
  return td;
}

function renderStars(r) {
  const f = Math.floor(r), h = (r - f) >= 0.5 ? 1 : 0;
  return '★'.repeat(f) + (h ? '½' : '') + '☆'.repeat(5 - f - h);
}

// ─── Column filter dropdowns ──────────────────────────────────────────────────

function openFilter(colKey, anchor) {
  if (openFilterKey === colKey) { closeFilter(); return; }
  closeFilter();
  const col = COLUMNS.find(c => c.key === colKey);
  if (!col?.filter) return;
  openFilterKey = colKey;

  const panel = document.createElement('div');
  panel.id = 'filter-panel';
  panel.className = 'filter-panel';
  col.filter === 'list' ? buildListPanel(panel, col) : buildRangePanel(panel, col);
  document.body.appendChild(panel);

  // Position below anchor
  const r = anchor.getBoundingClientRect();
  let left = r.left + window.scrollX;
  if (left + 260 > window.innerWidth) left = window.innerWidth - 264;
  panel.style.cssText = `left:${left}px;top:${r.bottom + window.scrollY + 2}px`;

  setTimeout(() => document.addEventListener('mousedown', outsideClickHandler), 0);
}

function outsideClickHandler(e) {
  const panel = document.getElementById('filter-panel');
  if (panel?.contains(e.target)) {
    document.addEventListener('mousedown', outsideClickHandler, { once: true });
  } else {
    closeFilter();
  }
}

function closeFilter() {
  document.getElementById('filter-panel')?.remove();
  document.removeEventListener('mousedown', outsideClickHandler);
  openFilterKey = null;
}

function buildListPanel(panel, col) {
  const dk = col.dk;
  const excl = colFilters[dk]?.excluded;

  const vals = [...new Set(allSales.map(s => {
    const v = s[dk]; return v == null ? '(blank)' : String(v);
  }))].sort((a, b) => a === '(blank)' ? 1 : b === '(blank)' ? -1 : a.localeCompare(b));

  panel.innerHTML = `
    <div class="fp-head">
      <strong>${col.label}</strong>
      <div class="fp-actions">
        <button onclick="fpSelectAll('${dk}')">Select all</button>
        <button onclick="fpClearList('${dk}')">Clear</button>
      </div>
    </div>
    <input class="fp-search" type="text" placeholder="Search…" oninput="fpSearch(this)">
    <div class="fp-list">
      ${vals.map(v => {
        const checked = !excl || !excl.has(v) ? 'checked' : '';
        return `<label class="fp-item"><input type="checkbox" value="${esc(v)}" ${checked} onchange="fpToggle('${dk}',this)"> ${esc(v)}</label>`;
      }).join('')}
    </div>`;
}

function buildRangePanel(panel, col) {
  const dk = col.dk;
  const cur = colFilters[dk] || {};
  const vals = allSales.map(s => s[dk]).filter(v => v != null).map(Number);
  const lo = vals.length ? Math.min(...vals) : 0;
  const hi = vals.length ? Math.max(...vals) : 0;
  const step = ['rating','bayesian','weighted','length_hours','price','regular_price'].includes(dk) ? '0.1' : '1';

  panel.innerHTML = `
    <div class="fp-head"><strong>${col.label}</strong></div>
    <div class="fp-range">
      <label>Min<input type="number" id="rfmin" step="${step}" placeholder="${+lo.toFixed(2)}" value="${cur.min ?? ''}" oninput="fpRange('${dk}')"></label>
      <label>Max<input type="number" id="rfmax" step="${step}" placeholder="${+hi.toFixed(2)}" value="${cur.max ?? ''}" oninput="fpRange('${dk}')"></label>
    </div>
    <button class="fp-clear-btn" onclick="fpClearRange('${dk}')">Clear</button>`;
}

function fpSearch(input) {
  const q = input.value.toLowerCase();
  input.closest('.filter-panel').querySelectorAll('.fp-item').forEach(el => {
    el.hidden = !!q && !el.textContent.toLowerCase().includes(q);
  });
}

function fpToggle(dk, cb) {
  if (!colFilters[dk]) colFilters[dk] = { type: 'list', excluded: new Set() };
  const excl = colFilters[dk].excluded;
  cb.checked ? excl.delete(cb.value) : excl.add(cb.value);
  renderHeader();
  applyFilters();
}

function fpSelectAll(dk) {
  if (colFilters[dk]) colFilters[dk].excluded.clear();
  document.querySelectorAll('#filter-panel .fp-item input').forEach(i => i.checked = true);
  renderHeader();
  applyFilters();
}

function fpClearList(dk) {
  if (!colFilters[dk]) colFilters[dk] = { type: 'list', excluded: new Set() };
  const vals = [...document.querySelectorAll('#filter-panel .fp-item input')].map(i => i.value);
  colFilters[dk].excluded = new Set(vals);
  document.querySelectorAll('#filter-panel .fp-item input').forEach(i => i.checked = false);
  renderHeader();
  applyFilters();
}

function fpRange(dk) {
  const min = document.getElementById('rfmin')?.value;
  const max = document.getElementById('rfmax')?.value;
  colFilters[dk] = {
    type: 'range',
    min: min !== '' ? +min : null,
    max: max !== '' ? +max : null,
  };
  renderHeader();
  applyFilters();
}

function fpClearRange(dk) {
  delete colFilters[dk];
  closeFilter();
  renderHeader();
  applyFilters();
}

// ─── Favourites ───────────────────────────────────────────────────────────────

function toggleFav(asin, btn) {
  favorites.has(asin) ? favorites.delete(asin) : favorites.add(asin);
  btn.classList.toggle('active', favorites.has(asin));
  localStorage.setItem('audible_favs', JSON.stringify([...favorites]));
  if (document.getElementById('favs-only').checked) applyFilters();
}

// ─── Libation ─────────────────────────────────────────────────────────────────

function loadLibation(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const lines  = e.target.result.split(/\r?\n/);
    const header = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g,'').toLowerCase());
    const idx    = header.findIndex(h => h === 'asin' || h === 'audible product id');
    if (idx === -1) { alert('No ASIN or "Audible Product ID" column found.'); return; }
    ownedAsins = new Set(
      lines.slice(1)
        .map(l => (l.split(',')[idx] || '').trim().replace(/^"|"$/g,''))
        .filter(Boolean)
    );
    document.getElementById('libation-clear').hidden = false;
    renderBody();
  };
  reader.readAsText(file);
}

function clearLibation() {
  ownedAsins = new Set();
  document.getElementById('libation-file').value = '';
  document.getElementById('libation-clear').hidden = true;
  renderBody();
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

init();
