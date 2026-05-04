'use strict';

const DATA_URL = '../data/sales.json';

let allSales   = [];
let filtered   = [];
let sortKey    = 'title';
let sortAsc    = true;
let favorites  = new Set(JSON.parse(localStorage.getItem('audible_favs') || '[]'));
let ownedAsins = new Set();

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function init() {
  showTosBanner();

  try {
    const res  = await fetch(DATA_URL);
    const data = await res.json();
    allSales = data.sales || [];

    const updated = document.getElementById('last-updated');
    if (data.last_updated) {
      updated.textContent = 'Updated: ' + new Date(data.last_updated + 'Z').toLocaleString();
    }

    populateGenres();
    applyFilters();
  } catch (err) {
    document.getElementById('sales-tbody').innerHTML =
      '<tr><td colspan="9" id="empty">Failed to load sales data: ' + err.message + '</td></tr>';
  }
}

// ---------------------------------------------------------------------------
// ToS
// ---------------------------------------------------------------------------

function showTosBanner() {
  if (!localStorage.getItem('audible_tos')) {
    document.getElementById('tos-banner').hidden = false;
  }
}

function dismissTos() {
  localStorage.setItem('audible_tos', '1');
  document.getElementById('tos-banner').hidden = true;
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

function populateGenres() {
  const genres = [...new Set(allSales.map(s => s.genre).filter(Boolean))].sort();
  const sel = document.getElementById('genre-filter');
  genres.forEach(g => {
    const opt = document.createElement('option');
    opt.value = opt.textContent = g;
    sel.appendChild(opt);
  });
}

function applyFilters() {
  const want2for1   = document.getElementById('type-2for1').checked;
  const wantMonthly = document.getElementById('type-monthly').checked;
  const minRating   = parseFloat(document.getElementById('rating-filter').value);
  const genre       = document.getElementById('genre-filter').value;
  const favsOnly    = document.getElementById('favs-only').checked;

  filtered = allSales.filter(s => {
    if (s.type === '2for1'   && !want2for1)   return false;
    if (s.type === 'monthly' && !wantMonthly) return false;
    if (minRating > 0 && (s.rating == null || s.rating < minRating)) return false;
    if (genre && s.genre !== genre) return false;
    if (favsOnly && !favorites.has(s.asin)) return false;
    return true;
  });

  applySort(false);
}

// ---------------------------------------------------------------------------
// Sort
// ---------------------------------------------------------------------------

function toggleSort(key) {
  if (sortKey === key) {
    sortAsc = !sortAsc;
  } else {
    sortKey = key;
    sortAsc = true;
  }
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.classList.toggle('sort-asc',  th.dataset.sort === key &&  sortAsc);
    th.classList.toggle('sort-desc', th.dataset.sort === key && !sortAsc);
  });
  applySort(true);
}

function applySort(render = true) {
  filtered.sort((a, b) => {
    let va = a[sortKey];
    let vb = b[sortKey];
    if (va == null && vb == null) return 0;
    if (va == null) return sortAsc ? 1 : -1;
    if (vb == null) return sortAsc ? -1 : 1;
    if (typeof va === 'string') {
      return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    return sortAsc ? va - vb : vb - va;
  });
  if (render) renderTable();
  else renderTable();
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function renderTable() {
  const tbody = document.getElementById('sales-tbody');
  document.getElementById('count').textContent =
    filtered.length.toLocaleString() + ' title' + (filtered.length === 1 ? '' : 's');

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" id="empty">No titles match your filters.</td></tr>';
    return;
  }

  const frag = document.createDocumentFragment();

  for (const s of filtered) {
    const tr = document.createElement('tr');
    if (ownedAsins.has(s.asin)) tr.classList.add('owned');

    // Favourite
    const starTd = document.createElement('td');
    const star = document.createElement('button');
    star.className = 'star-btn' + (favorites.has(s.asin) ? ' active' : '');
    star.setAttribute('aria-label', 'Favourite');
    star.textContent = '★';
    star.onclick = () => toggleFav(s.asin, star);
    starTd.appendChild(star);
    tr.appendChild(starTd);

    // Cover
    const coverTd = document.createElement('td');
    if (s.cover_url) {
      const img = document.createElement('img');
      img.src = s.cover_url;
      img.alt = '';
      img.className = 'cover-thumb';
      img.loading = 'lazy';
      coverTd.appendChild(img);
    }
    tr.appendChild(coverTd);

    // Title
    const titleTd = document.createElement('td');
    const a = document.createElement('a');
    a.href = s.audible_url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = s.title || '';
    titleTd.appendChild(a);
    if (ownedAsins.has(s.asin)) {
      const badge = document.createElement('span');
      badge.className = 'owned-badge';
      badge.textContent = 'Owned';
      titleTd.appendChild(badge);
    }
    tr.appendChild(titleTd);

    // Author / Narrator
    tr.appendChild(textCell(s.author));
    tr.appendChild(textCell(s.narrator));

    // Length
    tr.appendChild(textCell(s.length_hours != null ? s.length_hours.toFixed(1) + ' h' : ''));

    // Rating
    const ratingTd = document.createElement('td');
    if (s.rating != null) {
      const starsSpan = document.createElement('span');
      starsSpan.className = 'stars';
      starsSpan.textContent = renderStars(s.rating);
      ratingTd.appendChild(starsSpan);
      const info = document.createElement('span');
      info.className = 'rating-info';
      info.textContent = s.rating.toFixed(1) + ' · ' + (s.rating_count || 0).toLocaleString();
      ratingTd.appendChild(info);
    }
    tr.appendChild(ratingTd);

    // Sale price
    const priceTd = document.createElement('td');
    if (s.type === '2for1') {
      const b = document.createElement('span');
      b.className = 'badge badge-2for1';
      b.textContent = '2-for-1';
      priceTd.appendChild(b);
    } else if (s.price != null) {
      const span = document.createElement('span');
      span.className = 'price-sale';
      span.textContent = '$' + s.price.toFixed(2);
      priceTd.appendChild(span);
    }
    tr.appendChild(priceTd);

    // List price
    const listTd = document.createElement('td');
    if (s.regular_price != null) {
      listTd.className = 'price-list';
      listTd.textContent = '$' + s.regular_price.toFixed(2);
    }
    tr.appendChild(listTd);

    frag.appendChild(tr);
  }

  tbody.replaceChildren(frag);
}

function textCell(text) {
  const td = document.createElement('td');
  td.textContent = text ?? '';
  return td;
}

function renderStars(rating) {
  const full = Math.floor(rating);
  const half = (rating - full) >= 0.5 ? 1 : 0;
  const empty = 5 - full - half;
  return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty);
}

// ---------------------------------------------------------------------------
// Favourites
// ---------------------------------------------------------------------------

function toggleFav(asin, btn) {
  if (favorites.has(asin)) {
    favorites.delete(asin);
    btn.classList.remove('active');
  } else {
    favorites.add(asin);
    btn.classList.add('active');
  }
  localStorage.setItem('audible_favs', JSON.stringify([...favorites]));

  // If "favourites only" is active, re-filter (item may disappear)
  if (document.getElementById('favs-only').checked) applyFilters();
}

// ---------------------------------------------------------------------------
// Libation CSV
// ---------------------------------------------------------------------------

function loadLibation(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const lines  = e.target.result.split(/\r?\n/);
    const header = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, '').toLowerCase());
    const asinIdx = header.findIndex(h => h === 'asin' || h === 'audible product id');
    if (asinIdx === -1) {
      alert('Could not find an ASIN or "Audible Product ID" column in this CSV.');
      return;
    }
    ownedAsins = new Set(
      lines.slice(1)
        .map(l => {
          const parts = l.split(',');
          return (parts[asinIdx] || '').trim().replace(/^"|"$/g, '');
        })
        .filter(Boolean)
    );
    document.getElementById('libation-clear').hidden = false;
    renderTable();
  };
  reader.readAsText(file);
}

function clearLibation() {
  ownedAsins = new Set();
  document.getElementById('libation-file').value = '';
  document.getElementById('libation-clear').hidden = true;
  renderTable();
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

init();
