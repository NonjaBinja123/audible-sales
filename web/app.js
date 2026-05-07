'use strict';

const DATA_URL   = '../data/sales.json';
const BAYESIAN_M = 100;

let regionFilter = localStorage.getItem('audible_region') || 'us';

const REGION_FLAGS = { us:'🇺🇸', ca:'🇨🇦', uk:'🇬🇧', au:'🇦🇺', de:'🇩🇪', fr:'🇫🇷', jp:'🇯🇵' };
const REGION_LABELS = { us:'US', ca:'CA', uk:'UK', au:'AU', de:'DE', fr:'FR', jp:'JP' };

function setRegion(code) {
  regionFilter = code;
  localStorage.setItem('audible_region', code);
  document.getElementById('region-select').value = code;
  _syncMobileRegion();
  applyFilters();
}

function _syncMobileRegion() {
  const btn = document.getElementById('mobile-region');
  if (btn) btn.textContent = (REGION_FLAGS[regionFilter] || '') + ' ' + (REGION_LABELS[regionFilter] || regionFilter.toUpperCase());
}

function cycleMobileRegion() {
  const regions = [...document.getElementById('region-select').options].map(o => o.value);
  const idx = regions.indexOf(regionFilter);
  setRegion(regions[(idx + 1) % regions.length]);
}

// ─── Column definitions ───────────────────────────────────────────────────────
const COLUMNS = [
  { key:'fav',           label:'★',          always:true,  def:true,  sort:false, filter:false,   dk:null },
  { key:'cover',         label:'Cover',       always:false, def:true,  sort:false, filter:false,   dk:null },
  { key:'title',         label:'Title',       always:true,  def:true,  sort:true,  filter:'text',  dk:'title' },
  { key:'region',        label:'Region',      always:false, def:true,  sort:true,  filter:'list',  dk:'region' },
  { key:'type',          label:'Type',        always:false, def:true,  sort:true,  filter:'list',  dk:'type' },
  { key:'author',        label:'Author',      always:false, def:true,  sort:true,  filter:'list',  dk:'author' },
  { key:'narrator',      label:'Narrator',    always:false, def:false, sort:true,  filter:'list',  dk:'narrator' },
  { key:'genre',         label:'Genre',       always:false, def:false, sort:true,  filter:'list',  dk:'genre' },
  { key:'categories',   label:'Categories',  always:false, def:false, sort:false, filter:'tree',  dk:'categories' },
  { key:'length_hours',  label:'Length (h)',  always:false, def:true,  sort:true,  filter:'range', dk:'length_hours' },
  { key:'rating',        label:'Rating',      always:false, def:true,  sort:true,  filter:'range', dk:'rating' },
  { key:'rating_count',  label:'# Ratings',  always:false, def:true,  sort:true,  filter:'range', dk:'rating_count' },
  { key:'bayesian',      label:'Bayesian',    always:false, def:false, sort:true,  filter:'range', dk:'bayesian' },
  { key:'weighted',      label:'Weighted',    always:false, def:false, sort:true,  filter:'range', dk:'weighted' },
  { key:'price',         label:'Sale Price',  always:false, def:true,  sort:true,  filter:'price', dk:'price' },
  { key:'regular_price', label:'List Price',  always:false, def:true,  sort:true,  filter:'range', dk:'regular_price' },
  { key:'owned',         label:'Owned',       always:false, def:false, sort:true,  filter:false,   dk:'owned' },
  { key:'asin',          label:'ASIN',        always:false, def:false, sort:false, filter:false,   dk:'asin' },
];

// ─── Card field definitions (mobile) ─────────────────────────────────────────
const CARD_FIELD_DEFS = [
  { key:'narrator',     label:'Narrator',    fmt: s => s.narrator || null },
  { key:'genre',        label:'Genre',       fmt: s => s.genre || null },
  { key:'length_hours', label:'Length',      fmt: s => s.length_hours != null ? s.length_hours.toFixed(1) + 'h' : null },
  { key:'rating',       label:'Rating',      fmt: s => s.rating != null ? '★ ' + s.rating.toFixed(1) : null },
  { key:'rating_count', label:'# Ratings',   fmt: s => s.rating_count != null ? s.rating_count.toLocaleString() + ' ratings' : null },
  { key:'bayesian',     label:'Bayesian',    fmt: s => s.bayesian != null ? 'Bayes ' + s.bayesian.toFixed(2) : null },
  { key:'weighted',     label:'Weighted',    fmt: s => s.weighted != null ? 'Score ' + s.weighted.toFixed(2) : null },
  { key:'price',        label:'Price',       fmt: s => s.type === '2for1' ? '1 credit' : (s.price != null ? '$' + s.price.toFixed(2) : null) },
];
const CARD_FIELD_MAX = 5;
let cardFields = new Set(
  JSON.parse(localStorage.getItem('audible_card_fields') || '["narrator","rating"]')
);

// ─── State ────────────────────────────────────────────────────────────────────
let allSales      = [];
let filtered      = [];
let sortKey       = 'title';
let sortAsc       = true;
let favorites     = new Set(JSON.parse(localStorage.getItem('audible_favs') || '[]'));
let ownedAsins    = new Set();
let visibleCols   = new Set(
  JSON.parse(localStorage.getItem('audible_cols') ||
    JSON.stringify(COLUMNS.filter(c => c.def).map(c => c.key)))
);
let colFilters    = {};
let openFilterKey = null;

// Quick filter state
let quickType        = '';
let searchQuery        = '';
let ownedFilter        = ''; // '' | 'owned' | 'unowned'
let excludedCategories = new Set(); // empty = show all; non-empty = exclude matching items
let authorFilter       = '';
let narratorFilter     = '';

// ─── Help modal ───────────────────────────────────────────────────────────────
function openHelp() {
  document.getElementById('help-overlay').hidden = false;
  document.getElementById('help-modal').hidden   = false;
  const close = () => {
    document.getElementById('help-overlay').hidden = true;
    document.getElementById('help-modal').hidden   = true;
    document.removeEventListener('keydown',  close);
    document.getElementById('help-overlay').removeEventListener('click', close);
    document.getElementById('help-modal').removeEventListener('click', close);
  };
  document.getElementById('help-overlay').addEventListener('click', close);
  document.getElementById('help-modal').addEventListener('click', close);
  setTimeout(() => document.addEventListener('keydown', close), 0);
}

// ─── Theme ────────────────────────────────────────────────────────────────────
(function initTheme() {
  const stored = localStorage.getItem('audible_theme');
  const mq     = window.matchMedia('(prefers-color-scheme: dark)');
  const isDark  = stored === 'dark' || (stored !== 'light' && mq.matches);
  document.documentElement.classList.toggle('dark', isDark);
  mq.addEventListener('change', e => {
    if (!localStorage.getItem('audible_theme'))
      document.documentElement.classList.toggle('dark', e.matches);
    _syncThemeBtn();
  });
})();

function _syncThemeBtn() {
  const stored  = localStorage.getItem('audible_theme');
  const isDark  = document.documentElement.classList.contains('dark');
  const label   = stored ? (isDark ? 'Dark' : 'Light') : (isDark ? 'Dark (auto)' : 'Light (auto)');
  document.getElementById('theme-toggle')?.textContent     && (document.getElementById('theme-toggle').textContent = label);
  document.getElementById('theme-toggle-mob')?.textContent && (document.getElementById('theme-toggle-mob').textContent = label);
}

function cycleTheme() {
  const stored = localStorage.getItem('audible_theme');
  const isDark  = document.documentElement.classList.contains('dark');
  let next;
  if (!stored)           next = 'dark';
  else if (stored === 'dark')  next = 'light';
  else                   next = null;

  if (next) localStorage.setItem('audible_theme', next);
  else      localStorage.removeItem('audible_theme');

  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  document.documentElement.classList.toggle('dark',
    next === 'dark' || (!next && mq.matches));
  _syncThemeBtn();
}

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  showTosBanner();
  _syncThemeBtn();
  _syncMobileRegion();
  document.getElementById('region-select').value = regionFilter;
  buildColSelector();

  try {
    const data      = await fetch(DATA_URL).then(r => r.json());
    const rated     = data.sales.filter(s => s.rating != null);
    const globalAvg = rated.reduce((a, s) => a + s.rating, 0) / (rated.length || 1);

    allSales = data.sales.map(s => ({
      ...s,
      bayesian: computeBayesian(s.rating, s.rating_count, globalAvg),
      weighted: computeWeighted(s.rating, s.rating_count),
    }));

    const ts = data.last_updated ? 'Updated: ' + new Date(data.last_updated + 'Z').toLocaleString() : '';
    document.getElementById('last-updated').textContent  = ts;
    document.getElementById('mobile-updated').textContent = ts;

    buildTypePills();
    restoreLibation();
    updateTableHeight();
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

// ─── Quick filters ────────────────────────────────────────────────────────────
const TYPE_LABELS = {
  '2for1':   '2-for-1',
  'monthly': 'Monthly',
  'daily':   'Daily Deal',
  'cash':    'Cash Sale',
};

function buildTypePills() {
  const types = [...new Set(allSales.map(s => s.type).filter(Boolean))].sort();
  const container = document.getElementById('type-pills');
  const allBtn = `<button class="pill active" onclick="setTypeFilter('', this)">All</button>`;
  const typeBtns = types.map(t =>
    `<button class="pill" onclick="setTypeFilter('${esc(t)}', this)">${TYPE_LABELS[t] || t}</button>`
  ).join('');
  container.innerHTML = allBtn + typeBtns;
}

function setTypeFilter(type, btn) {
  if (type === '') {
    // All — always activates, clears others
    quickType = '';
  } else if (quickType === type) {
    // Clicking the active type again → go back to All
    quickType = '';
  } else {
    quickType = type;
  }
  // Sync pill highlights in whichever container the btn lives in
  const container = btn.closest('#type-pills, .sheet-pills');
  if (container) {
    container.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    const allBtn = container.querySelector('[onclick*="setTypeFilter(\'\'"]');
    const activeBtn = quickType
      ? container.querySelector(`[onclick*="setTypeFilter('${quickType}'"]`)
      : allBtn;
    if (activeBtn) activeBtn.classList.add('active');
  }
  applyFilters();
}

function setOwnedFilter(val, btn) {
  ownedFilter = ownedFilter === val ? '' : val;
  document.querySelectorAll('.owned-pill').forEach(p => p.classList.remove('active'));
  if (ownedFilter) btn.classList.add('active');
  applyFilters();
}

function clearAllFilters() {
  quickType = ''; searchQuery = ''; ownedFilter = '';
  authorFilter = ''; narratorFilter = '';
  excludedCategories.clear(); colFilters = {};
  document.getElementById('title-search').value = '';
  document.getElementById('favs-only').checked = false;
  document.querySelectorAll('#type-pills .pill').forEach(p => p.classList.remove('active'));
  document.querySelector('#type-pills .pill')?.classList.add('active');
  document.querySelectorAll('#owned-pills .pill').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.cat-tree input[type=checkbox]').forEach(i => {
    i.checked = true; i.indeterminate = false;
  });
  document.getElementById('cats-btn')?.classList.remove('active');
  renderHeader(); applyFilters(); _updateClearBtn();
}

function _updateClearBtn() {
  const active = quickType || searchQuery || ownedFilter || authorFilter || narratorFilter ||
    excludedCategories.size > 0 || Object.keys(colFilters).length > 0;
  document.getElementById('clear-filters-btn').hidden = !active;
}

// ─── Category tree ────────────────────────────────────────────────────────────

function _buildTree() {
  // Returns nested object: { nodeName: { children: {}, count: N } }
  const tree = {};
  for (const s of allSales) {
    for (const path of (Array.isArray(s.categories) ? s.categories : [])) {
      let node = tree;
      for (const name of path) {
        if (!node[name]) node[name] = { children: {}, count: 0 };
        node[name].count++;
        node = node[name].children;
      }
    }
  }
  return tree;
}

function _renderTree(node, depth = 0) {
  return Object.entries(node).sort(([a],[b]) => a.localeCompare(b)).map(([name, data]) => {
    const hasChildren = Object.keys(data.children).length > 0;
    const checked     = !excludedCategories.has(name) ? 'checked' : '';
    const childHtml   = hasChildren ? `<div class="cat-children">${_renderTree(data.children, depth+1)}</div>` : '';
    return `<div class="cat-node">
      <label class="cat-label">
        ${hasChildren ? `<button type="button" class="cat-toggle" onclick="toggleCatNode(this)">▶</button>` : '<span class="cat-toggle-spacer"></span>'}
        <input type="checkbox" value="${esc(name)}" ${checked} onchange="toggleCatFilter('${esc(name)}',this.checked,this)">
        <span>${esc(name)}</span>
        <small class="cat-count">${data.count}</small>
      </label>
      ${childHtml}
    </div>`;
  }).join('');
}

function buildCategoryPanel(container) {
  const tree = _buildTree();
  if (!Object.keys(tree).length) {
    container.innerHTML = '<p class="cs-empty">No categories yet — run the scraper to populate.</p>';
    return;
  }
  container.innerHTML = `
    <div class="cat-actions">
      <button onclick="selectAllCats()">Select all</button>
      <button onclick="clearCatFilter()">Uncheck all</button>
    </div>
    <div class="cat-tree-wrap"><div class="cat-tree">${_renderTree(tree)}</div></div>`;
}

function toggleCatNode(arrow) {
  const children = arrow.closest('.cat-node').querySelector('.cat-children');
  if (!children) return;
  const open = children.style.display === 'block';
  children.style.display = open ? 'none' : 'block';
  arrow.textContent = open ? '▶' : '▼';
}

function toggleCatFilter(name, checked) {
  if (!checked) {
    // Uncheck: exclude only this node — path AND logic blocks the path at this node
    excludedCategories.add(name);
  } else {
    // Check: remove this node, all its descendants, and all its ancestors so the
    // full path from root to leaf is unblocked in both directions
    excludedCategories.delete(name);
    _descendantsOf(name).forEach(n => excludedCategories.delete(n));
    _ancestorsOf(name).forEach(n  => excludedCategories.delete(n));
  }

  document.getElementById('cats-btn')?.classList.toggle('active', excludedCategories.size > 0);
  renderHeader(); applyFilters();
}

function _ancestorsOf(name) {
  const result = new Set();
  for (const s of allSales)
    for (const path of (Array.isArray(s.categories) ? s.categories : [])) {
      const idx = path.indexOf(name);
      if (idx > 0) for (let i = 0; i < idx; i++) result.add(path[i]);
    }
  return result;
}

function _descendantsOf(name) {
  const result = new Set();
  for (const s of allSales)
    for (const path of (Array.isArray(s.categories) ? s.categories : [])) {
      const idx = path.indexOf(name);
      if (idx >= 0) for (let i = idx + 1; i < path.length; i++) result.add(path[i]);
    }
  return result;
}

function _updateIndeterminate(treeEl) {
  [...treeEl.querySelectorAll('.cat-node')].reverse().forEach(node => {
    const parentCb = node.querySelector(':scope > .cat-label > input[type=checkbox]');
    const childCbs = [...node.querySelectorAll(':scope > .cat-children .cat-node > .cat-label > input[type=checkbox]')];
    if (!parentCb || !childCbs.length) return;
    // Explicitly excluded parent stays unchecked — its block is absolute
    if (excludedCategories.has(parentCb.value)) {
      parentCb.checked = false; parentCb.indeterminate = false;
      return;
    }
    // Non-excluded parent: fully checked only when all children are fully checked
    const allFullyChecked = childCbs.every(c => c.checked && !c.indeterminate);
    if (allFullyChecked) {
      parentCb.checked = true;  parentCb.indeterminate = false;
    } else {
      parentCb.checked = false; parentCb.indeterminate = true;
    }
  });
}

function _allCatNodeNames() {
  const nodes = new Set();
  for (const s of allSales) {
    for (const path of (Array.isArray(s.categories) ? s.categories : [])) {
      for (const n of path) nodes.add(n);
    }
  }
  return nodes;
}

function selectAllCats() {
  excludedCategories.clear();
  _rebuildCatPanels();
  document.getElementById('cats-btn')?.classList.remove('active');
  renderHeader(); applyFilters();
}

function clearCatFilter() {
  _allCatNodeNames().forEach(n => excludedCategories.add(n));
  _rebuildCatPanels();
  document.getElementById('cats-btn')?.classList.add('active');
  renderHeader(); applyFilters();
}

function _rebuildCatPanels() {
  const desk = document.getElementById('cats-selector');
  if (desk && !desk.hidden) buildCategoryPanel(desk);
  const mob = document.getElementById('sheet-cat-tree');
  if (mob) buildCategoryPanel(mob);
  const fp = document.getElementById('filter-panel');
  if (fp && fp.querySelector('.cat-tree')) buildCategoryPanel(fp);
  syncFilterPanels();
}

function toggleCatsPanel() {
  const p = document.getElementById('cats-selector');
  p.hidden = !p.hidden;
  if (!p.hidden) {
    buildCategoryPanel(p);
    syncFilterPanels();
    const onOut = e => {
      if (p.contains(e.target) || e.target.closest('#cats-btn')) return;
      p.hidden = true;
      document.removeEventListener('mousedown', onOut);
    };
    setTimeout(() => document.addEventListener('mousedown', onOut), 0);
  }
}

// ─── Filter logic ─────────────────────────────────────────────────────────────
function isFilterActive(dk) {
  if (dk === 'title') return searchQuery !== '';
  const f = colFilters[dk];
  if (!f) return false;
  if (f.type === 'list')  return f.excluded.size > 0;
  if (f.type === 'range') return f.min != null || f.max != null;
  if (f.type === 'price') return !f.includeCredit || f.min != null || f.max != null;
  if (dk === 'categories') return excludedCategories.size > 0;
  return false;
}

function setSearch(val) {
  searchQuery = val.trim();
  // Sync the desktop search box if called from column panel
  const box = document.getElementById('title-search');
  if (box && box.value !== searchQuery) box.value = searchQuery;
  applyFilters();
}

function applyFilters() {
  const favsOnly = document.getElementById('favs-only').checked;

  filtered = allSales.filter(s => {
    if (favsOnly && !favorites.has(s.asin)) return false;

    // Quick type pill
    if (quickType && s.type !== quickType) return false;

    // Category filter — path AND logic: show if any complete path has no excluded nodes.
    // Checking a node also clears its ancestors/descendants so the path opens fully.
    // Items with no categories are hidden when filter is active.
    if (excludedCategories.size > 0) {
      const paths = Array.isArray(s.categories) ? s.categories : [];
      if (paths.length === 0) return false;
      const hasCleanPath = paths.some(path =>
        path.length > 0 && path.every(node => !excludedCategories.has(node))
      );
      if (!hasCleanPath) return false;
    }

    // Region filter (treat null/missing region as 'us')
    if (regionFilter && (s.region || 'us') !== regionFilter) return false;

    // Owned filter
    if (ownedFilter === 'owned'   && !ownedAsins.has(s.asin)) return false;
    if (ownedFilter === 'unowned' &&  ownedAsins.has(s.asin)) return false;

    // Title search
    if (searchQuery  && !(s.title    || '').toLowerCase().includes(searchQuery.toLowerCase()))   return false;
    if (authorFilter && !(s.author   || '').toLowerCase().includes(authorFilter.toLowerCase()))   return false;
    if (narratorFilter && !(s.narrator || '').toLowerCase().includes(narratorFilter.toLowerCase())) return false;

    // Column filters
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
      if (f.type === 'price') {
        if (!f.includeCredit && s.type === '2for1') return false;
        if (s.price != null) {
          if (f.min != null && s.price < f.min) return false;
          if (f.max != null && s.price > f.max) return false;
        }
      }
    }
    return true;
  });

  applySort();
  _updateClearBtn();
  syncFilterPanels();
}

function syncFilterPanels() {
  for (const treeEl of [
    document.querySelector('#cats-selector .cat-tree'),
    document.querySelector('#sheet-cat-tree .cat-tree'),
    document.querySelector('#filter-panel .cat-tree'),
  ].filter(Boolean)) {
    treeEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
      cb.checked = !excludedCategories.has(cb.value);
      cb.indeterminate = false;
    });
    _updateIndeterminate(treeEl);
  }
}

// ─── Sort ─────────────────────────────────────────────────────────────────────
function toggleSort(dk) {
  if (sortKey === dk) sortAsc = !sortAsc;
  else { sortKey = dk; sortAsc = true; }
  renderHeader();
  applySort();
}

function sortNorm(v) {
  // Strip leading non-alphanumeric characters so !,#,etc. don't sort before A-Z
  return typeof v === 'string' ? v.replace(/^[^a-zA-Z0-9]+/, '') : v;
}

function applySort() {
  filtered.sort((a, b) => {
    if (sortKey === 'owned') {
      const oa = ownedAsins.has(a.asin) ? 1 : 0;
      const ob = ownedAsins.has(b.asin) ? 1 : 0;
      return sortAsc ? oa - ob : ob - oa;
    }
    let va = sortNorm(a[sortKey]), vb = sortNorm(b[sortKey]);
    if (va == null && vb == null) return 0;
    if (va == null) return  sortAsc ?  1 : -1;
    if (vb == null) return  sortAsc ? -1 :  1;
    if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  });
  renderBody();
}

// ─── Render ───────────────────────────────────────────────────────────────────
function renderHeader() {
  const tr     = document.querySelector('#sales-table thead tr');
  tr.innerHTML = '';

  for (const col of COLUMNS) {
    if (!col.always && !visibleCols.has(col.key)) continue;

    const th = document.createElement('th');
    th.dataset.col = col.key;
    th.style.cssText = `position:sticky;top:0;z-index:50;background:var(--surface)`;
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
      fbtn.title = active ? 'Filter active' : 'Filter';
      fbtn.onclick = e => { e.stopPropagation(); openFilter(col.key, fbtn); };
      inner.appendChild(fbtn);
    }

    th.appendChild(inner);
    tr.appendChild(th);
  }
}

function renderBody() {
  if (isMobile()) { renderCards(); return; }

  const tbody = document.getElementById('sales-tbody');
  document.getElementById('count').textContent =
    filtered.length.toLocaleString() + ' title' + (filtered.length !== 1 ? 's' : '');

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
  td.dataset.col = col.key;

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
    case 'region': {
      const REGION_FLAGS = { us:'🇺🇸', ca:'🇨🇦', uk:'🇬🇧', au:'🇦🇺', de:'🇩🇪', fr:'🇫🇷', jp:'🇯🇵' };
      td.textContent = (REGION_FLAGS[sale.region] || '') + ' ' + (sale.region || '').toUpperCase();
      break;
    }
    case 'title': {
      const a = document.createElement('a');
      // Use item's native URL (already has the right regional domain)
      a.href = sale.audible_url;
      a.target = '_blank'; a.rel = 'noopener noreferrer';
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
    case 'categories': {
      const paths = Array.isArray(sale.categories) ? sale.categories : [];
      td.textContent = paths.map(p => p.join(' › ')).join('; ');
      td.className = 'tags-cell'; break;
    }
    case 'owned': {
      td.textContent = ownedAsins.has(sale.asin) ? '✓' : '';
      td.style.color = 'var(--green)';
      td.style.fontWeight = '700';
      break;
    }
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
  if (col.filter === 'list')   buildListPanel(panel, col);
  else if (col.filter === 'text')  buildTextPanel(panel, col);
  else if (col.filter === 'price') buildPricePanel(panel, col);
  else if (col.filter === 'tree')  buildCategoryPanel(panel);
  else                             buildRangePanel(panel, col);
  document.body.appendChild(panel);
  if (col.filter === 'tree') syncFilterPanels();

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

function buildTextPanel(panel, col) {
  panel.innerHTML = `
    <div class="fp-head"><strong>${col.label} search</strong></div>
    <div style="padding:10px">
      <input type="search" id="text-fp-input" value="${esc(searchQuery)}"
             placeholder="Type to search…"
             autofocus
             style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;font-size:14px;outline:none"
             oninput="setSearch(this.value)">
    </div>
    <button class="fp-clear-btn" onclick="setSearch('');document.getElementById('text-fp-input').value=''">Clear</button>`;
  setTimeout(() => panel.querySelector('input')?.focus(), 50);
}

function buildListPanel(panel, col) {
  const dk   = col.dk;
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
  const dk  = col.dk;
  const cur = colFilters[dk] || {};
  const vals = allSales.map(s => s[dk]).filter(v => v != null).map(Number);
  const lo  = vals.length ? Math.min(...vals) : 0;
  const hi  = vals.length ? Math.max(...vals) : 0;
  const step = ['rating','bayesian','weighted','length_hours','price','regular_price'].includes(dk) ? '0.1' : '1';

  panel.innerHTML = `
    <div class="fp-head"><strong>${col.label}</strong></div>
    <div class="fp-range">
      <label>Min<input type="number" id="rfmin" step="${step}" placeholder="${+lo.toFixed(2)}" value="${cur.min ?? ''}" oninput="fpRange('${dk}')"></label>
      <label>Max<input type="number" id="rfmax" step="${step}" placeholder="${+hi.toFixed(2)}" value="${cur.max ?? ''}" oninput="fpRange('${dk}')"></label>
    </div>
    <button class="fp-clear-btn" onclick="fpClearRange('${dk}')">Clear</button>`;
}

function buildPricePanel(panel, col) {
  const cur   = colFilters['price'] || { includeCredit: true };
  const vals  = allSales.map(s => s.price).filter(v => v != null).map(Number);
  const lo    = vals.length ? Math.min(...vals) : 0;
  const hi    = vals.length ? Math.max(...vals) : 0;
  const chk   = cur.includeCredit !== false ? 'checked' : '';

  panel.innerHTML = `
    <div class="fp-head"><strong>Sale Price</strong></div>
    <label class="fp-item" style="padding:8px 10px;border-bottom:1px solid var(--border)">
      <input type="checkbox" id="pf-credit" ${chk} onchange="fpPriceCredit(this.checked)">
      1-credit (2-for-1) sales
    </label>
    <div class="fp-range" style="padding-top:8px">
      <small style="color:var(--muted);padding:0 10px">Cash price range:</small>
      <label>Min<input type="number" id="rfmin" step="0.01" placeholder="${+lo.toFixed(2)}" value="${cur.min ?? ''}" oninput="fpPriceRange()"></label>
      <label>Max<input type="number" id="rfmax" step="0.01" placeholder="${+hi.toFixed(2)}" value="${cur.max ?? ''}" oninput="fpPriceRange()"></label>
    </div>
    <button class="fp-clear-btn" onclick="fpPriceClear()">Clear</button>`;
}

function fpPriceCredit(checked) {
  if (!colFilters['price']) colFilters['price'] = { type: 'price', includeCredit: true };
  colFilters['price'].includeCredit = checked;
  renderHeader(); applyFilters();
}

function fpPriceRange() {
  const min = document.getElementById('rfmin')?.value;
  const max = document.getElementById('rfmax')?.value;
  if (!colFilters['price']) colFilters['price'] = { type: 'price', includeCredit: true };
  colFilters['price'].type = 'price';
  colFilters['price'].min  = min !== '' ? +min : null;
  colFilters['price'].max  = max !== '' ? +max : null;
  renderHeader(); applyFilters();
}

function fpPriceClear() {
  delete colFilters['price'];
  closeFilter(); renderHeader(); applyFilters();
}

function fpSearch(input) {
  const q = input.value.toLowerCase();
  input.closest('.filter-panel').querySelectorAll('.fp-item').forEach(el => {
    el.style.display = (q && !el.textContent.toLowerCase().includes(q)) ? 'none' : '';
  });
}

function fpToggle(dk, cb) {
  if (!colFilters[dk]) colFilters[dk] = { type: 'list', excluded: new Set() };
  cb.checked ? colFilters[dk].excluded.delete(cb.value) : colFilters[dk].excluded.add(cb.value);
  renderHeader(); applyFilters();
}

function fpSelectAll(dk) {
  if (colFilters[dk]) colFilters[dk].excluded.clear();
  document.querySelectorAll('#filter-panel .fp-item input').forEach(i => i.checked = true);
  renderHeader(); applyFilters();
}

function fpClearList(dk) {
  if (!colFilters[dk]) colFilters[dk] = { type: 'list', excluded: new Set() };
  const vals = [...document.querySelectorAll('#filter-panel .fp-item input')].map(i => i.value);
  colFilters[dk].excluded = new Set(vals);
  document.querySelectorAll('#filter-panel .fp-item input').forEach(i => i.checked = false);
  renderHeader(); applyFilters();
}

function fpRange(dk) {
  const min = document.getElementById('rfmin')?.value;
  const max = document.getElementById('rfmax')?.value;
  colFilters[dk] = { type:'range', min: min !== '' ? +min : null, max: max !== '' ? +max : null };
  renderHeader(); applyFilters();
}

function fpClearRange(dk) {
  delete colFilters[dk];
  closeFilter(); renderHeader(); applyFilters();
}

// ─── Favourites ───────────────────────────────────────────────────────────────
function toggleFav(asin, btn) {
  favorites.has(asin) ? favorites.delete(asin) : favorites.add(asin);
  btn.classList.toggle('active', favorites.has(asin));
  localStorage.setItem('audible_favs', JSON.stringify([...favorites]));
  if (document.getElementById('favs-only').checked) applyFilters();
}

// ─── Libation ─────────────────────────────────────────────────────────────────
const LIBATION_KEY = 'audible_libation';

function restoreLibation() {
  const saved = localStorage.getItem(LIBATION_KEY);
  if (!saved) return;
  const asins = JSON.parse(saved);
  if (!asins.length) return;
  ownedAsins = new Set(asins);
  _setLibationUI(asins.length, true);
}

function loadLibation(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const lines  = e.target.result.split(/\r?\n/);
    const header = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g,'').toLowerCase());
    const idx    = header.findIndex(h => h === 'asin' || h === 'audible product id');
    if (idx === -1) { alert('No ASIN or "Audible Product ID" column found.'); return; }
    const asins = lines.slice(1)
      .map(l => (l.split(',')[idx] || '').trim().replace(/^"|"$/g,''))
      .filter(Boolean);
    ownedAsins = new Set(asins);
    localStorage.setItem(LIBATION_KEY, JSON.stringify(asins));
    _setLibationUI(asins.length, false);
    renderBody();
  };
  reader.readAsText(file);
}

function _setLibationUI(count, fromSession) {
  document.getElementById('libation-status').textContent = fromSession
    ? `${count} owned (session)`
    : `${count} owned loaded`;
  document.getElementById('libation-clear').hidden = false;

  const pills = document.getElementById('owned-pills');
  pills.hidden = false;
  pills.innerHTML =
    `<button class="pill owned-pill" onclick="setOwnedFilter('owned',this)">Owned</button>` +
    `<button class="pill owned-pill" onclick="setOwnedFilter('unowned',this)">Not Owned</button>`;
}

function clearLibation() {
  ownedAsins = new Set();
  ownedFilter = '';
  localStorage.removeItem(LIBATION_KEY);
  document.getElementById('libation-file').value = '';
  document.getElementById('libation-clear').hidden = true;
  document.getElementById('libation-status').textContent = '';
  document.getElementById('owned-pills').hidden = true;
  renderBody();
}

// ─── Utility ──────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─── Responsive helpers ───────────────────────────────────────────────────────
function isMobile() { return window.innerWidth <= 640; }

function stickyTop() {
  return document.getElementById('sticky-wrap').offsetHeight;
}

function updateTableHeight() {
  if (isMobile()) return;
  document.getElementById('table-wrap').style.height = `calc(100vh - ${stickyTop()}px)`;
}

// ─── Mobile: card rendering ───────────────────────────────────────────────────

function renderCards() {
  const container = document.getElementById('cards-view');
  const countEl   = document.getElementById('mobile-count');
  countEl.textContent = filtered.length.toLocaleString() + ' title' + (filtered.length !== 1 ? 's' : '');

  if (!filtered.length) {
    container.innerHTML = '<p class="empty-msg">No results match your filters.</p>';
    return;
  }

  const sortDef = CARD_FIELD_DEFS.find(d => d.key === sortKey);

  const frag = document.createDocumentFragment();
  for (const sale of filtered) {
    const card = document.createElement('a');
    card.href      = sale.audible_url;
    card.target    = '_blank';
    card.rel       = 'noopener noreferrer';
    card.className = 'book-card' + (ownedAsins.has(sale.asin) ? ' owned' : '');

    // Cover
    const coverDiv = document.createElement('div');
    coverDiv.className = 'card-cover';
    if (sale.cover_url) {
      const img = document.createElement('img');
      img.src = sale.cover_url; img.alt = ''; img.loading = 'lazy';
      coverDiv.appendChild(img);
    }

    // Details
    const det = document.createElement('div');
    det.className = 'card-details';

    const titleEl = document.createElement('div');
    titleEl.className = 'card-title';
    titleEl.textContent = sale.title || '';

    const authorEl = document.createElement('div');
    authorEl.className = 'card-meta';
    authorEl.textContent = sale.author || '';

    det.appendChild(titleEl);
    det.appendChild(authorEl);

    // Optional field chips
    const activeFields = CARD_FIELD_DEFS.filter(d => cardFields.has(d.key));
    if (activeFields.length) {
      const chipRow = document.createElement('div');
      chipRow.className = 'card-chips';
      for (const def of activeFields) {
        const val = def.fmt(sale);
        if (!val) continue;
        const chip = document.createElement('span');
        chip.className = 'card-chip';
        chip.textContent = val;
        chipRow.appendChild(chip);
      }
      if (chipRow.children.length) det.appendChild(chipRow);
    }

    // Footer
    const footer = document.createElement('div');
    footer.className = 'card-footer';

    // Sale type badge
    const badge = document.createElement('span');
    badge.className = `badge badge-${sale.type}`;
    badge.textContent = TYPE_LABELS[sale.type] || sale.type;
    footer.appendChild(badge);

    // Sort value — always shown if sorted by a displayable field not already in chips
    if (sortDef && !cardFields.has(sortKey)) {
      const val = sortDef.fmt(sale);
      if (val) {
        const sv = document.createElement('span');
        sv.className = 'card-chip card-sort-val';
        sv.textContent = val;
        sv.title = sortDef.label;
        footer.appendChild(sv);
      }
    }

    // Price — shown in footer only if not already a chip field
    if (!cardFields.has('price')) {
      if (sale.type === '2for1') {
        const cp = document.createElement('span');
        cp.className = 'card-price credit';
        cp.textContent = '1 credit';
        footer.appendChild(cp);
      } else if (sale.price != null) {
        const cp = document.createElement('span');
        cp.className = 'card-price';
        cp.textContent = '$' + sale.price.toFixed(2);
        footer.appendChild(cp);
      }
    }

    // Owned badge
    if (ownedAsins.has(sale.asin)) {
      const ob = document.createElement('span');
      ob.className = 'owned-badge'; ob.textContent = 'Owned';
      footer.appendChild(ob);
    }

    // Fav
    const favBtn = document.createElement('button');
    favBtn.className = 'star-btn' + (favorites.has(sale.asin) ? ' active' : '');
    favBtn.textContent = '★';
    favBtn.onclick = e => { e.preventDefault(); e.stopPropagation(); toggleFav(sale.asin, favBtn); };
    footer.appendChild(favBtn);

    det.appendChild(footer);
    card.appendChild(coverDiv);
    card.appendChild(det);
    frag.appendChild(card);
  }
  container.replaceChildren(frag);
}

function toggleCardField(key, cb) {
  if (cb.checked) {
    if (cardFields.size >= CARD_FIELD_MAX) { cb.checked = false; return; }
    cardFields.add(key);
  } else {
    cardFields.delete(key);
  }
  localStorage.setItem('audible_card_fields', JSON.stringify([...cardFields]));
  // Update counter and disabled states in-place (avoids sheet scroll-to-top)
  const counter = document.querySelector('.card-field-count');
  if (counter) counter.textContent = `(${cardFields.size}/${CARD_FIELD_MAX})`;
  document.querySelectorAll('.card-field-toggle').forEach(inp => {
    if (!inp.checked) inp.disabled = cardFields.size >= CARD_FIELD_MAX;
  });
  renderCards();
}

// ─── Mobile: filter sheet ─────────────────────────────────────────────────────

function openFilterSheet() {
  buildFilterSheet();
  document.getElementById('filter-sheet').classList.add('open');
  document.getElementById('sheet-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeFilterSheet() {
  document.getElementById('filter-sheet').classList.remove('open');
  document.getElementById('sheet-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

function resetFilters() {
  quickType = '';
  excludedCategories.clear();
  colFilters = {};
  document.getElementById('favs-only').checked = false;
  buildFilterSheet();
  applyFilters();
}

function buildFilterSheet() {
  const types  = [...new Set(allSales.map(s => s.type).filter(Boolean))].sort();
  const ratingFilter = colFilters['rating'] || {};
  const favsOnly     = document.getElementById('favs-only').checked;

  const sortOptions = [
    ['title',        'Title A–Z'],
    ['rating',       'Rating (high–low)'],
    ['rating_count', '# Ratings (high–low)'],
    ['bayesian',     'Bayesian (high–low)'],
    ['weighted',     'Weighted (high–low)'],
    ['length_hours', 'Length (short–long)'],
    ['price',        'Price (low–high)'],
    ['owned',        'Owned first'],
  ].map(([val, label]) =>
    `<option value="${val}" ${sortKey === val ? 'selected' : ''}>${label}</option>`
  ).join('');

  const typePills = ['', ...types].map(t => {
    const active = quickType === t ? 'active' : '';
    const label  = t ? (TYPE_LABELS[t] || t) : 'All';
    return `<button class="pill ${active}" onclick="setTypeFilter('${esc(t)}',this)">${label}</button>`;
  }).join('');


  document.getElementById('sheet-body').innerHTML = `
    <div class="sheet-section">
      <div class="sheet-label">Audible region</div>
      <select class="sheet-select" onchange="setRegion(this.value)">
        ${Object.entries({us:'🇺🇸 US',ca:'🇨🇦 Canada'})
          .map(([k,v]) => `<option value="${k}" ${regionFilter===k?'selected':''}>${v}</option>`).join('')}
      </select>
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Search title</div>
      <input type="search" value="${esc(searchQuery)}" placeholder="Type to search…"
             style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;font-size:14px"
             oninput="setSearch(this.value)">
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Sort by</div>
      <select class="sheet-select" onchange="setMobileSort(this.value)">${sortOptions}</select>
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Sale type</div>
      <div class="sheet-pills">${typePills}</div>
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Author</div>
      <input type="search" class="sheet-text-filter" placeholder="Filter by author…"
             value="${esc(authorFilter)}"
             oninput="authorFilter=this.value; applyFilters()">
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Narrator</div>
      <input type="search" class="sheet-text-filter" placeholder="Filter by narrator…"
             value="${esc(narratorFilter)}"
             oninput="narratorFilter=this.value; applyFilters()">
    </div>


    <div class="sheet-section">
      <div class="sheet-label">Min rating: <span id="sheet-rating-val">${ratingFilter.min ?? 0}</span>★</div>
      <input type="range" class="sheet-range" min="0" max="5" step="0.5"
             value="${ratingFilter.min ?? 0}"
             oninput="document.getElementById('sheet-rating-val').textContent=this.value;
                      colFilters['rating']={type:'range',min:+this.value||null,max:null};
                      applyFilters()">
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Min # Ratings</div>
      <input type="number" class="sheet-text-filter" step="100" placeholder="e.g. 500"
             value="${colFilters['rating_count']?.min ?? ''}"
             oninput="setMobileRange('rating_count','min',this.value)">
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Length (hours)</div>
      <div class="sheet-range-row">
        <label>Min<input type="number" step="0.5" placeholder="0"
               value="${colFilters['length_hours']?.min ?? ''}"
               oninput="setMobileRange('length_hours','min',this.value)"></label>
        <label>Max<input type="number" step="0.5" placeholder="any"
               value="${colFilters['length_hours']?.max ?? ''}"
               oninput="setMobileRange('length_hours','max',this.value)"></label>
      </div>
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Sale Price</div>
      <label class="sheet-check" style="margin-bottom:8px">
        <input type="checkbox" ${(colFilters['price']?.includeCredit ?? true) ? 'checked' : ''}
               onchange="fpPriceCredit(this.checked)">
        Include 1-credit (2-for-1)
      </label>
      <div class="sheet-range-row">
        <label>Min<input type="number" step="0.01" placeholder="0"
               value="${colFilters['price']?.min ?? ''}"
               oninput="if(!colFilters['price'])colFilters['price']={type:'price',includeCredit:true};colFilters['price'].min=this.value?+this.value:null;applyFilters()"></label>
        <label>Max<input type="number" step="0.01" placeholder="any"
               value="${colFilters['price']?.max ?? ''}"
               oninput="if(!colFilters['price'])colFilters['price']={type:'price',includeCredit:true};colFilters['price'].max=this.value?+this.value:null;applyFilters()"></label>
      </div>
    </div>

    <label class="sheet-check">
      <input type="checkbox" ${favsOnly ? 'checked' : ''}
             onchange="document.getElementById('favs-only').checked=this.checked; applyFilters()">
      Favourites only
    </label>

    ${ownedAsins.size ? `
    <div class="sheet-pills" style="margin-bottom:16px">
      <button class="pill owned-pill ${ownedFilter==='owned'?'active':''}"
              onclick="setOwnedFilter('owned',this)">Owned</button>
      <button class="pill owned-pill ${ownedFilter==='unowned'?'active':''}"
              onclick="setOwnedFilter('unowned',this)">Not Owned</button>
    </div>` : ''}

    <div class="sheet-section">
      <div class="sheet-label">Categories</div>
      <div id="sheet-cat-tree" class="sheet-tag-list"></div>
    </div>

    <div class="sheet-section">
      <div class="sheet-label">Libation (owned books)</div>
      <input type="file" accept=".csv" onchange="loadLibation(this.files[0])">
      <div class="libation-status" style="margin-top:4px">${document.getElementById('libation-status').textContent}</div>
    </div>

    <div class="sheet-section">
      <div class="sheet-label" style="display:flex;justify-content:space-between;align-items:center">
        <span>Card fields</span>
        <span class="card-field-count" style="font-weight:400;color:var(--muted)">(${cardFields.size}/${CARD_FIELD_MAX})</span>
      </div>
      <div class="sheet-tag-list">
        ${CARD_FIELD_DEFS.map(d => `
          <label class="sheet-check">
            <input type="checkbox" class="card-field-toggle"
                   value="${d.key}"
                   ${cardFields.has(d.key) ? 'checked' : ''}
                   ${!cardFields.has(d.key) && cardFields.size >= CARD_FIELD_MAX ? 'disabled' : ''}
                   onchange="toggleCardField('${d.key}', this)">
            ${d.label}
          </label>`).join('')}
      </div>
    </div>
  `;
  // Populate category tree inside sheet (requestAnimationFrame ensures DOM is ready)
  requestAnimationFrame(() => {
    const catContainer = document.getElementById('sheet-cat-tree');
    if (catContainer) { buildCategoryPanel(catContainer); syncFilterPanels(); }
  });
}

function setMobileRange(dk, bound, val) {
  if (!colFilters[dk]) colFilters[dk] = { type: 'range', min: null, max: null };
  colFilters[dk][bound] = val !== '' ? +val : null;
  applyFilters();
}

function setMobileSort(key) {
  const descFirst = ['rating', 'bayesian', 'weighted', 'rating_count'];
  sortKey  = key;
  sortAsc  = !descFirst.includes(key);
  applySort();
}

// ─── Boot ─────────────────────────────────────────────────────────────────────
init();
window.addEventListener('resize', () => { updateTableHeight(); renderBody(); });
