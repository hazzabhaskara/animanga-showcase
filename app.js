/**
 * ============================================================================
 * ANIMANGA SHOWCASE — High Performance Vanilla JS Application
 * Zero Dependencies • 100% Offline via file:// • Sub-100ms Search & Filtering
 * ============================================================================
 */

(function () {
  "use strict";

  // --- Global Application State ---
  const state = {
    allEntries: [],          // Combined 266 records (219 anime + 47 manga)
    filteredEntries: [],     // Current filtered and sorted dataset
    currentDrawerIndex: -1,  // Index in filteredEntries currently displayed in drawer
    filters: {
      searchQuery: "",
      mediaType: "all",      // 'all' | 'anime' | 'manga'
      status: "all",         // 'all' | 'Completed' | 'Watching/Reading' | 'Plan to Watch/Read' | 'On-Hold' | 'Dropped'
      scoreTier: "all",      // 'all' | 'masterpiece' | 'recommended' | 'average' | 'low' | 'unrated'
      genre: "all",          // 'all' | genre name
      sortBy: "title_asc"    // 'title_asc' | 'title_desc' | 'score_desc' | 'score_asc' | 'global_desc' | 'progress_desc'
    },
    viewMode: "gallery",     // 'gallery' | 'table'
    theme: "dark"            // 'dark' | 'light'
  };

  // --- Helper: Safe LocalStorage Wrapper (file:// sandbox resilience) ---
  const storage = {
    get(key, defaultVal) {
      try {
        const val = localStorage.getItem(key);
        return val !== null ? val : defaultVal;
      } catch (e) {
        return defaultVal;
      }
    },
    set(key, val) {
      try {
        localStorage.setItem(key, val);
      } catch (e) {
        // Storage disabled or blocked by strict file:// policy
      }
    }
  };

  // --- Helper: Generate Inline SVG Placeholder for Broken/Missing Posters ---
  function getPosterPlaceholder(title, mediaType) {
    const initials = (title || "MAL")
      .split(/\s+/)
      .slice(0, 2)
      .map(w => w.charAt(0).toUpperCase())
      .join("");
    const isAnime = mediaType === "anime";
    const bg1 = isAnime ? "%231e3a8a" : "%23831843";
    const bg2 = isAnime ? "%230f172a" : "%233b0764";
    const typeLabel = isAnime ? "ANIME" : "MANGA";

    return `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450" width="100%" height="100%"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="${bg1}"/><stop offset="100%" stop-color="${bg2}"/></linearGradient></defs><rect width="300" height="450" fill="url(%23g)"/><circle cx="150" cy="190" r="54" fill="rgba(255,255,255,0.08)"/><text x="150" y="202" font-family="sans-serif" font-size="34" font-weight="bold" fill="%23ffffff" text-anchor="middle">${initials}</text><rect x="100" y="280" width="100" height="24" rx="12" fill="rgba(255,255,255,0.15)"/><text x="150" y="296" font-family="sans-serif" font-size="12" font-weight="bold" letter-spacing="1" fill="%23ffffff" text-anchor="middle">${typeLabel}</text></svg>`;
  }

  // --- Helper: String Normalization for Ultra-Fast Search ---
  function normalizeText(text) {
    if (!text) return "";
    return text
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();
  }

  // --- Helper: Format Semantic Score Badge HTML ---
  function getScoreBadgeHtml(score, isLarge = false) {
    const s = Number(score);
    if (!s || s <= 0) {
      return `<span class="score-badge tier-unrated" title="Unrated">—</span>`;
    }

    let tierClass = "tier-low";
    if (s === 10) tierClass = "tier-10";
    else if (s >= 9) tierClass = "tier-masterpiece";
    else if (s >= 7) tierClass = "tier-recommended";
    else if (s >= 5) tierClass = "tier-average";

    const starIcon = `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>`;

    return `<span class="score-badge ${tierClass}" title="User Score: ${s}/10">${starIcon} ${s}</span>`;
  }

  // --- Helper: Format Semantic Status Pill HTML ---
  function getStatusPillHtml(status) {
    const st = (status || "").toLowerCase();
    let cls = "status-pill ";
    if (st.includes("completed")) cls += "completed";
    else if (st.includes("watching")) cls += "watching";
    else if (st.includes("reading")) cls += "reading";
    else if (st.includes("plan")) cls += "plan";
    else if (st.includes("hold")) cls += "on-hold";
    else if (st.includes("drop")) cls += "dropped";
    else cls += "plan";

    return `<span class="${cls}">${escapeHtml(status)}</span>`;
  }

  // --- Helper: HTML Escaping for Safe Rendering ---
  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // --- Initialization & Data Pre-Processing ---
  function initData() {
    if (!window.CATALOG_DATA) {
      console.error("CATALOG_DATA not found. Please verify data.js is loaded.");
      return;
    }

    const rawAnime = window.CATALOG_DATA.anime || [];
    const rawManga = window.CATALOG_DATA.manga || [];

    // Tag each record with mediaType & precompute search tokens
    const animeTagged = rawAnime.map((item) => {
      const copy = { ...item, mediaType: "anime" };
      const tokens = [
        copy.title,
        copy.title_english || "",
        copy.title_japanese || "",
        ...(copy.synonyms || []),
        copy.studio || "",
        ...(copy.genres || []),
        copy.type || "TV"
      ].join(" ");
      copy._searchIndex = normalizeText(tokens);
      copy._progressPct = typeof copy.progress_pct === "number" ? copy.progress_pct : 0.0;
      return copy;
    });

    const mangaTagged = rawManga.map((item) => {
      const copy = { ...item, mediaType: "manga" };
      const tokens = [
        copy.title,
        copy.title_english || "",
        copy.title_japanese || "",
        ...(copy.synonyms || []),
        ...(copy.authors || []),
        ...(copy.genres || []),
        copy.type || "Manga"
      ].join(" ");
      copy._searchIndex = normalizeText(tokens);
      copy._progressPct = typeof copy.chapter_progress_pct === "number" ? copy.chapter_progress_pct : 0.0;
      return copy;
    });

    state.allEntries = [...animeTagged, ...mangaTagged];
    populateGenreDropdown();
    renderKpiStats();
  }

  // --- Populate Genre Dropdown ---
  function populateGenreDropdown() {
    const genreSelect = document.getElementById("genre-select");
    if (!genreSelect) return;

    const genresSet = new Set();
    state.allEntries.forEach(item => {
      if (Array.isArray(item.genres)) {
        item.genres.forEach(g => {
          if (g && typeof g === "string") genresSet.add(g);
        });
      }
    });

    const sortedGenres = Array.from(genresSet).sort();
    sortedGenres.forEach(g => {
      const opt = document.createElement("option");
      opt.value = g;
      opt.textContent = g;
      genreSelect.appendChild(opt);
    });
  }

  // --- Render Header KPI Stats ---
  function renderKpiStats() {
    const kpiContainer = document.getElementById("header-kpi-container");
    if (!kpiContainer) return;

    const total = state.allEntries.length;
    const animeCount = state.allEntries.filter(i => i.mediaType === "anime").length;
    const mangaCount = state.allEntries.filter(i => i.mediaType === "manga").length;
    const completedCount = state.allEntries.filter(i => i.my_status === "Completed").length;

    const ratedScores = state.allEntries
      .map(i => Number(i.my_score))
      .filter(s => s > 0);
    const meanScore = ratedScores.length > 0
      ? (ratedScores.reduce((a, b) => a + b, 0) / ratedScores.length).toFixed(2)
      : "0.00";

    const watchedEp = state.allEntries
      .filter(i => i.mediaType === "anime")
      .reduce((sum, i) => sum + (Number(i.my_watched_episodes) || 0), 0);

    kpiContainer.innerHTML = `
      <div class="kpi-pill">
        <span class="dot completed"></span>
        <span>Total: <strong>${total}</strong></span>
      </div>
      <div class="kpi-pill">
        <span class="dot anime"></span>
        <span>Anime: <strong>${animeCount}</strong></span>
      </div>
      <div class="kpi-pill">
        <span class="dot manga"></span>
        <span>Manga: <strong>${mangaCount}</strong></span>
      </div>
      <div class="kpi-pill">
        <span class="dot completed"></span>
        <span>Completed: <strong>${completedCount}</strong></span>
      </div>
      <div class="kpi-pill">
        <span class="dot score"></span>
        <span>Mean Score: <strong>${meanScore}</strong></span>
      </div>
      <div class="kpi-pill">
        <span class="dot anime"></span>
        <span>Episodes: <strong>${watchedEp.toLocaleString()}</strong></span>
      </div>
    `;

    // Also update tab counts
    const tabAllCount = document.getElementById("tab-count-all");
    const tabAnimeCount = document.getElementById("tab-count-anime");
    const tabMangaCount = document.getElementById("tab-count-manga");
    if (tabAllCount) tabAllCount.textContent = total;
    if (tabAnimeCount) tabAnimeCount.textContent = animeCount;
    if (tabMangaCount) tabMangaCount.textContent = mangaCount;
  }

  // --- Core Filter & Sort Pipeline (<100ms) ---
  function applyFiltersAndSort() {
    const { searchQuery, mediaType, status, scoreTier, genre, sortBy } = state.filters;

    // 1. Search query tokenization
    const rawTokens = normalizeText(searchQuery).split(/\s+/).filter(Boolean);

    // 2. Filter records
    const results = state.allEntries.filter((item) => {
      // Media type
      if (mediaType !== "all" && item.mediaType !== mediaType) {
        return false;
      }

      // Status
      if (status !== "all") {
        const itemStatus = (item.my_status || "").toLowerCase();
        if (status === "Completed" && itemStatus !== "completed") return false;
        if (status === "Watching/Reading" && !itemStatus.includes("watching") && !itemStatus.includes("reading")) return false;
        if (status === "Plan to Watch/Read" && !itemStatus.includes("plan")) return false;
        if (status === "On-Hold" && !itemStatus.includes("hold")) return false;
        if (status === "Dropped" && !itemStatus.includes("drop")) return false;
      }

      // Score tier
      if (scoreTier !== "all") {
        const s = Number(item.my_score) || 0;
        if (scoreTier === "masterpiece" && s < 9) return false;
        if (scoreTier === "recommended" && (s < 7 || s > 8)) return false;
        if (scoreTier === "average" && (s < 5 || s > 6)) return false;
        if (scoreTier === "low" && (s < 1 || s > 4)) return false;
        if (scoreTier === "unrated" && s !== 0) return false;
      }

      // Genre
      if (genre !== "all") {
        if (!Array.isArray(item.genres) || !item.genres.includes(genre)) {
          return false;
        }
      }

      // Search tokens: ALL tokens must be in item's search index
      if (rawTokens.length > 0) {
        for (let i = 0; i < rawTokens.length; i++) {
          if (!item._searchIndex.includes(rawTokens[i])) {
            return false;
          }
        }
      }

      return true;
    });

    // 3. Sort records
    results.sort((a, b) => {
      switch (sortBy) {
        case "title_asc":
          return (a.title || "").localeCompare(b.title || "", undefined, { numeric: true, sensitivity: "base" });
        case "title_desc":
          return (b.title || "").localeCompare(a.title || "", undefined, { numeric: true, sensitivity: "base" });
        case "score_desc": {
          const sa = Number(a.my_score) || 0;
          const sb = Number(b.my_score) || 0;
          if (sa === 0 && sb > 0) return 1;
          if (sb === 0 && sa > 0) return -1;
          if (sb !== sa) return sb - sa;
          return (a.title || "").localeCompare(b.title || "");
        }
        case "score_asc": {
          const sa = Number(a.my_score) || 0;
          const sb = Number(b.my_score) || 0;
          if (sa === 0 && sb > 0) return 1;
          if (sb === 0 && sa > 0) return -1;
          if (sa !== sb) return sa - sb;
          return (a.title || "").localeCompare(b.title || "");
        }
        case "global_desc": {
          const ga = Number(a.global_score) || 0;
          const gb = Number(b.global_score) || 0;
          if (gb !== ga) return gb - ga;
          return (a.title || "").localeCompare(b.title || "");
        }
        case "progress_desc":
          return (b._progressPct || 0) - (a._progressPct || 0);
        case "type_asc": {
          const typeComp = (a.type || "").localeCompare(b.type || "");
          if (typeComp !== 0) return typeComp;
          return (a.title || "").localeCompare(b.title || "");
        }
        default:
          return 0;
      }
    });

    state.filteredEntries = results;
    renderResults();
    renderActiveFilterChips();
  }

  // --- Render Active Filter Chips ---
  function renderActiveFilterChips() {
    const container = document.getElementById("active-filters-container");
    const chipsList = document.getElementById("active-chips-list");
    const counter = document.getElementById("results-counter");

    if (counter) {
      counter.innerHTML = `Showing <strong>${state.filteredEntries.length}</strong> of <strong>${state.allEntries.length}</strong> titles`;
    }

    if (!chipsList) return;

    const chips = [];
    const { searchQuery, mediaType, status, scoreTier, genre } = state.filters;

    if (searchQuery) {
      chips.push({
        label: `Search: "${searchQuery}"`,
        onRemove: () => {
          state.filters.searchQuery = "";
          const searchInput = document.getElementById("search-input");
          if (searchInput) searchInput.value = "";
          updateSearchClearButton();
          applyFiltersAndSort();
        }
      });
    }

    if (mediaType !== "all") {
      chips.push({
        label: `Type: ${mediaType.toUpperCase()}`,
        onRemove: () => {
          setMediaType("all");
        }
      });
    }

    if (status !== "all") {
      chips.push({
        label: `Status: ${status}`,
        onRemove: () => {
          state.filters.status = "all";
          const statusSelect = document.getElementById("status-select");
          if (statusSelect) statusSelect.value = "all";
          applyFiltersAndSort();
        }
      });
    }

    if (scoreTier !== "all") {
      const tierLabels = {
        masterpiece: "★ 9-10 Masterpiece",
        recommended: "★ 7-8 Recommended",
        average: "★ 5-6 Average",
        low: "★ 1-4 Low",
        unrated: "Unrated (0)"
      };
      chips.push({
        label: `Score: ${tierLabels[scoreTier] || scoreTier}`,
        onRemove: () => {
          state.filters.scoreTier = "all";
          const scoreSelect = document.getElementById("score-select");
          if (scoreSelect) scoreSelect.value = "all";
          applyFiltersAndSort();
        }
      });
    }

    if (genre !== "all") {
      chips.push({
        label: `Genre: ${genre}`,
        onRemove: () => {
          state.filters.genre = "all";
          const genreSelect = document.getElementById("genre-select");
          if (genreSelect) genreSelect.value = "all";
          applyFiltersAndSort();
        }
      });
    }

    chipsList.innerHTML = "";
    if (chips.length > 0) {
      chips.forEach((chip) => {
        const el = document.createElement("div");
        el.className = "active-filter-chip";
        el.innerHTML = `
          <span>${escapeHtml(chip.label)}</span>
          <span class="chip-remove-btn" title="Remove filter">
            <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
          </span>
        `;
        el.querySelector(".chip-remove-btn").addEventListener("click", chip.onRemove);
        chipsList.appendChild(el);
      });

      // Show Reset All button
      const resetBtn = document.createElement("button");
      resetBtn.className = "reset-filters-btn";
      resetBtn.innerHTML = `Reset all`;
      resetBtn.addEventListener("click", resetAllFilters);
      chipsList.appendChild(resetBtn);

      if (container) container.style.display = "flex";
    } else {
      if (container) container.style.display = "none";
    }
  }

  // --- Reset All Filters ---
  function resetAllFilters() {
    state.filters.searchQuery = "";
    state.filters.mediaType = "all";
    state.filters.status = "all";
    state.filters.scoreTier = "all";
    state.filters.genre = "all";
    state.filters.sortBy = "title_asc";

    const searchInput = document.getElementById("search-input");
    if (searchInput) searchInput.value = "";
    updateSearchClearButton();

    const statusSelect = document.getElementById("status-select");
    if (statusSelect) statusSelect.value = "all";

    const scoreSelect = document.getElementById("score-select");
    if (scoreSelect) scoreSelect.value = "all";

    const genreSelect = document.getElementById("genre-select");
    if (genreSelect) genreSelect.value = "all";

    const sortSelect = document.getElementById("sort-select");
    if (sortSelect) sortSelect.value = "title_asc";

    updateTypeTabsUI();
    applyFiltersAndSort();
  }

  // --- Media Type Tab Switcher ---
  function setMediaType(type) {
    state.filters.mediaType = type;
    updateTypeTabsUI();
    applyFiltersAndSort();
  }

  function updateTypeTabsUI() {
    const tabs = document.querySelectorAll(".type-tab-btn");
    tabs.forEach(tab => {
      if (tab.getAttribute("data-type") === state.filters.mediaType) {
        tab.classList.add("active");
      } else {
        tab.classList.remove("active");
      }
    });
  }

  // --- Render Results (Gallery vs Table) ---
  function renderResults() {
    const galleryView = document.getElementById("gallery-view-container");
    const tableView = document.getElementById("table-view-container");
    const emptyState = document.getElementById("empty-state");

    if (state.filteredEntries.length === 0) {
      if (galleryView) galleryView.style.display = "none";
      if (tableView) tableView.style.display = "none";
      if (emptyState) emptyState.style.display = "block";
      return;
    }

    if (emptyState) emptyState.style.display = "none";

    if (state.viewMode === "gallery") {
      if (galleryView) galleryView.style.display = "grid";
      if (tableView) tableView.style.display = "none";
      renderGalleryView(galleryView);
    } else {
      if (galleryView) galleryView.style.display = "none";
      if (tableView) tableView.style.display = "block";
      renderTableView(tableView);
    }
  }

  // --- Render Gallery View ---
  function renderGalleryView(container) {
    if (!container) return;

    let html = "";
    state.filteredEntries.forEach((item, index) => {
      const isAnime = item.mediaType === "anime";
      const fallbackPoster = getPosterPlaceholder(item.title, item.mediaType);
      const posterUrl = item.poster_url || fallbackPoster;

      const scoreBadge = getScoreBadgeHtml(item.my_score);
      const typeLabel = escapeHtml(item.type || (isAnime ? "TV" : "Manga"));
      const typeClass = isAnime ? "anime" : "manga";

      // Status indicator dot
      const statusLower = (item.my_status || "").toLowerCase();
      let statusDotClass = "status-dot ";
      if (statusLower.includes("completed")) statusDotClass += "completed";
      else if (statusLower.includes("watching") || statusLower.includes("reading")) statusDotClass += "watching";
      else if (statusLower.includes("plan")) statusDotClass += "plan";
      else if (statusLower.includes("hold")) statusDotClass += "on-hold";
      else if (statusLower.includes("drop")) statusDotClass += "dropped";
      else statusDotClass += "plan";

      // Progress string
      let progressText = "";
      if (isAnime) {
        progressText = `${item.my_watched_episodes || 0} / ${item.episodes || "?"} ep`;
      } else {
        progressText = `${item.my_read_chapters || 0} / ${item.chapters || "?"} ch`;
      }

      // Top genres
      const genreChips = (item.genres || [])
        .slice(0, 2)
        .map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`)
        .join("");

      html += `
        <div class="anime-card" data-filtered-index="${index}" tabindex="0" role="button" aria-label="${escapeHtml(item.title)}">
          <div class="card-poster-wrap">
            <img class="card-poster-img"
                 src="${escapeHtml(posterUrl)}"
                 alt="${escapeHtml(item.title)}"
                 loading="lazy"
                 onerror="this.onerror=null;this.src='${fallbackPoster}';" />
            <div class="card-overlay-top">
              <span class="type-pill ${typeClass}">${typeLabel}</span>
              ${scoreBadge}
            </div>
          </div>
          <div class="card-body">
            <h3 class="card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h3>
            <div class="card-meta-line">
              <span class="status-indicator">
                <span class="${statusDotClass}"></span>
                <span>${escapeHtml(item.my_status)}</span>
              </span>
              <span>${progressText}</span>
            </div>
            <div class="card-genres">
              ${genreChips}
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;

    // Attach click listeners to cards
    const cards = container.querySelectorAll(".anime-card");
    cards.forEach(card => {
      card.addEventListener("click", () => {
        const idx = Number(card.getAttribute("data-filtered-index"));
        openDetailDrawer(idx);
      });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          const idx = Number(card.getAttribute("data-filtered-index"));
          openDetailDrawer(idx);
        }
      });
    });
  }

  // --- Render Table View ---
  function renderTableView(container) {
    if (!container) return;

    let rowsHtml = "";
    state.filteredEntries.forEach((item, index) => {
      const isAnime = item.mediaType === "anime";
      const fallbackPoster = getPosterPlaceholder(item.title, item.mediaType);
      const posterUrl = item.poster_url || fallbackPoster;

      const scoreBadge = getScoreBadgeHtml(item.my_score);
      const statusPill = getStatusPillHtml(item.my_status);

      // Global score
      const gScore = item.global_score ? `★ ${Number(item.global_score).toFixed(2)}` : "—";

      // Progress bar & text
      let currentVal = isAnime ? item.my_watched_episodes : item.my_read_chapters;
      let totalVal = isAnime ? item.episodes : item.chapters;
      let unit = isAnime ? "ep" : "ch";
      let pct = item._progressPct || 0;
      let isCompleted = item.my_status === "Completed";
      let fillClass = isCompleted ? "progress-fill completed" : "progress-fill";

      // Studio or Author
      let creator = isAnime ? (item.studio || "Unknown") : (item.authors && item.authors.length ? item.authors.join(", ") : "Unknown");

      // Genres
      const genresList = (item.genres || [])
        .slice(0, 2)
        .map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`)
        .join("");
      const overflowCount = (item.genres || []).length > 2 ? `<span class="genre-tag">+${item.genres.length - 2}</span>` : "";

      rowsHtml += `
        <tr data-filtered-index="${index}" tabindex="0">
          <td class="td-index">${index + 1}</td>
          <td class="td-thumb">
            <img class="thumb-img"
                 src="${escapeHtml(posterUrl)}"
                 alt=""
                 loading="lazy"
                 onerror="this.onerror=null;this.src='${fallbackPoster}';" />
          </td>
          <td class="td-title-cell">
            <span class="table-title-main" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</span>
            <span class="table-title-sub">${escapeHtml(item.title_english || item.title_japanese || "")}</span>
          </td>
          <td><span class="type-pill ${isAnime ? 'anime' : 'manga'}">${escapeHtml(item.type || (isAnime ? 'TV' : 'Manga'))}</span></td>
          <td>${scoreBadge}</td>
          <td><span style="font-weight:600;color:var(--text-secondary);">${gScore}</span></td>
          <td>${statusPill}</td>
          <td class="progress-cell">
            <div class="progress-label">
              <span>${currentVal || 0} / ${totalVal || "?"} ${unit}</span>
              <span>${pct.toFixed(0)}%</span>
            </div>
            <div class="progress-track">
              <div class="${fillClass}" style="width: ${Math.min(100, Math.max(0, pct))}%;"></div>
            </div>
          </td>
          <td>
            <div class="td-genres-list">
              ${genresList} ${overflowCount}
            </div>
          </td>
          <td><span style="color:var(--text-secondary);">${escapeHtml(creator)}</span></td>
        </tr>
      `;
    });

    container.innerHTML = `
      <div class="table-view-wrap">
        <table class="catalog-table">
          <thead>
            <tr>
              <th style="width: 45px;">#</th>
              <th style="width: 48px;">Cover</th>
              <th data-sort-key="title" class="${state.filters.sortBy.startsWith('title') ? 'active-sort' : ''}">
                <div class="th-content">Title <span class="sort-icon">${state.filters.sortBy === 'title_asc' ? '▲' : (state.filters.sortBy === 'title_desc' ? '▼' : '⇅')}</span></div>
              </th>
              <th data-sort-key="type" class="${state.filters.sortBy === 'type_asc' ? 'active-sort' : ''}">
                <div class="th-content">Format <span class="sort-icon">${state.filters.sortBy === 'type_asc' ? '▲' : '⇅'}</span></div>
              </th>
              <th data-sort-key="score" class="${state.filters.sortBy.startsWith('score') ? 'active-sort' : ''}">
                <div class="th-content">Score <span class="sort-icon">${state.filters.sortBy === 'score_desc' ? '▼' : (state.filters.sortBy === 'score_asc' ? '▲' : '⇅')}</span></div>
              </th>
              <th data-sort-key="global" class="${state.filters.sortBy === 'global_desc' ? 'active-sort' : ''}">
                <div class="th-content">Global <span class="sort-icon">${state.filters.sortBy === 'global_desc' ? '▼' : '⇅'}</span></div>
              </th>
              <th>Status</th>
              <th data-sort-key="progress" class="${state.filters.sortBy === 'progress_desc' ? 'active-sort' : ''}">
                <div class="th-content">Progress <span class="sort-icon">${state.filters.sortBy === 'progress_desc' ? '▼' : '⇅'}</span></div>
              </th>
              <th>Genres</th>
              <th>Studio / Author</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    `;

    // Attach click listeners to rows
    const rows = container.querySelectorAll("tbody tr");
    rows.forEach(row => {
      row.addEventListener("click", () => {
        const idx = Number(row.getAttribute("data-filtered-index"));
        openDetailDrawer(idx);
      });
      row.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          const idx = Number(row.getAttribute("data-filtered-index"));
          openDetailDrawer(idx);
        }
      });
    });

    // Attach sort header listeners
    const ths = container.querySelectorAll("thead th[data-sort-key]");
    ths.forEach(th => {
      th.addEventListener("click", () => {
        const sortKey = th.getAttribute("data-sort-key");
        toggleHeaderSort(sortKey);
      });
    });
  }

  // --- Toggle Table Header Sorting ---
  function toggleHeaderSort(sortKey) {
    let nextSort = "title_asc";
    if (sortKey === "title") {
      nextSort = state.filters.sortBy === "title_asc" ? "title_desc" : "title_asc";
    } else if (sortKey === "score") {
      nextSort = state.filters.sortBy === "score_desc" ? "score_asc" : "score_desc";
    } else if (sortKey === "global") {
      nextSort = "global_desc";
    } else if (sortKey === "progress") {
      nextSort = "progress_desc";
    } else if (sortKey === "type") {
      nextSort = "type_asc";
    }

    state.filters.sortBy = nextSort;
    const sortSelect = document.getElementById("sort-select");
    if (sortSelect) sortSelect.value = nextSort;
    applyFiltersAndSort();
  }

  // --- Slide-Over Detail Drawer Controller ---
  function openDetailDrawer(filteredIndex) {
    if (filteredIndex < 0 || filteredIndex >= state.filteredEntries.length) return;
    state.currentDrawerIndex = filteredIndex;
    const item = state.filteredEntries[filteredIndex];
    const isAnime = item.mediaType === "anime";

    const backdrop = document.getElementById("drawer-backdrop");
    const panel = document.getElementById("drawer-panel");
    const bannerImg = document.getElementById("drawer-banner-img");
    const posterImg = document.getElementById("drawer-poster-img");
    const titleMain = document.getElementById("drawer-title-main");
    const titleSub = document.getElementById("drawer-title-sub");
    const formatPill = document.getElementById("drawer-format-pill");

    const fallbackPoster = getPosterPlaceholder(item.title, item.mediaType);
    const posterUrl = item.poster_url || fallbackPoster;

    // Banner image
    if (bannerImg) {
      bannerImg.src = item.banner_image || posterUrl;
      bannerImg.onerror = () => { bannerImg.src = fallbackPoster; };
    }

    // Poster
    if (posterImg) {
      posterImg.src = posterUrl;
      posterImg.onerror = () => { posterImg.src = fallbackPoster; };
    }

    // Titles
    if (titleMain) titleMain.textContent = item.title;
    if (titleSub) {
      const subParts = [];
      if (item.title_english && item.title_english !== item.title) subParts.push(item.title_english);
      if (item.title_japanese) subParts.push(item.title_japanese);
      titleSub.textContent = subParts.join(" • ") || "—";
    }

    // Format & Year
    if (formatPill) {
      const yr = item.season_year ? ` • ${item.season_year}` : "";
      formatPill.textContent = `${item.type || (isAnime ? "TV" : "Manga")}${yr}`;
    }

    // Score comparison widget
    const scoreMyVal = document.getElementById("drawer-score-my");
    const scoreGlobalVal = document.getElementById("drawer-score-global");
    const scoreDiff = document.getElementById("drawer-score-diff");

    const myScoreNum = Number(item.my_score) || 0;
    const globalScoreNum = Number(item.global_score) || 0;

    if (scoreMyVal) {
      scoreMyVal.innerHTML = myScoreNum > 0 ? `★ ${myScoreNum} <span class="max">/ 10</span>` : `— <span class="max">/ 10</span>`;
    }
    if (scoreGlobalVal) {
      scoreGlobalVal.innerHTML = globalScoreNum > 0 ? `★ ${globalScoreNum.toFixed(2)} <span class="max">/ 10</span>` : `— <span class="max">/ 10</span>`;
    }
    if (scoreDiff) {
      if (myScoreNum > 0 && globalScoreNum > 0) {
        const diff = myScoreNum - globalScoreNum;
        if (Math.abs(diff) < 0.05) {
          scoreDiff.className = "score-divergence-pill equal";
          scoreDiff.textContent = "Equal to community rating";
        } else if (diff > 0) {
          scoreDiff.className = "score-divergence-pill higher";
          scoreDiff.textContent = `+${diff.toFixed(2)} higher than community`;
        } else {
          scoreDiff.className = "score-divergence-pill lower";
          scoreDiff.textContent = `${diff.toFixed(2)} lower than community`;
        }
      } else {
        scoreDiff.className = "score-divergence-pill equal";
        scoreDiff.textContent = "Rating comparison not available";
      }
    }

    // Status & Progress in Drawer
    const statusVal = document.getElementById("drawer-status-val");
    const progressText = document.getElementById("drawer-progress-text");
    const progressFill = document.getElementById("drawer-progress-fill");
    const datesVal = document.getElementById("drawer-dates-val");

    if (statusVal) {
      statusVal.innerHTML = getStatusPillHtml(item.my_status);
    }

    const cur = isAnime ? item.my_watched_episodes : item.my_read_chapters;
    const tot = isAnime ? item.episodes : item.chapters;
    const unit = isAnime ? "episodes" : "chapters";
    const pct = item._progressPct || 0;

    if (progressText) {
      progressText.textContent = `${cur || 0} of ${tot || "?"} ${unit} (${pct.toFixed(0)}%)`;
    }
    if (progressFill) {
      progressFill.style.width = `${Math.min(100, Math.max(0, pct))}%`;
      if (item.my_status === "Completed") {
        progressFill.classList.add("completed");
      } else {
        progressFill.classList.remove("completed");
      }
    }

    if (datesVal) {
      const sDate = item.my_start_date || "—";
      const fDate = item.my_finish_date || "—";
      datesVal.textContent = `${sDate} → ${fDate}`;
    }

    // Metadata Grid
    const creatorLabel = document.getElementById("drawer-creator-label");
    const creatorVal = document.getElementById("drawer-creator-val");
    const totalCountLabel = document.getElementById("drawer-total-label");
    const totalCountVal = document.getElementById("drawer-total-val");

    if (creatorLabel) creatorLabel.textContent = isAnime ? "Studio" : "Author(s)";
    if (creatorVal) {
      creatorVal.textContent = isAnime
        ? (item.studio || "Unknown")
        : (item.authors && item.authors.length ? item.authors.join(", ") : "Unknown");
    }

    if (totalCountLabel) totalCountLabel.textContent = isAnime ? "Total Episodes" : "Total Chapters / Vols";
    if (totalCountVal) {
      totalCountVal.textContent = isAnime
        ? (item.episodes || "Ongoing / Unknown")
        : `${item.chapters || "?"} ch / ${item.volumes || "?"} vol`;
    }

    // Genres Tags in Drawer (Clickable to filter!)
    const genresContainer = document.getElementById("drawer-genres-container");
    if (genresContainer) {
      genresContainer.innerHTML = "";
      (item.genres || []).forEach(g => {
        const chip = document.createElement("button");
        chip.className = "drawer-genre-chip";
        chip.textContent = g;
        chip.title = `Filter catalog by ${g}`;
        chip.addEventListener("click", () => {
          closeDetailDrawer();
          state.filters.genre = g;
          const genreSelect = document.getElementById("genre-select");
          if (genreSelect) genreSelect.value = g;
          applyFiltersAndSort();
        });
        genresContainer.appendChild(chip);
      });
      if (!item.genres || item.genres.length === 0) {
        genresContainer.innerHTML = `<span style="color:var(--text-muted);font-size:0.75rem;">None listed</span>`;
      }
    }

    // Synopsis
    const synopsisBlock = document.getElementById("drawer-synopsis-text");
    if (synopsisBlock) {
      synopsisBlock.textContent = item.synopsis || "No official synopsis available for this title.";
    }

    // Outbound link
    const malBtn = document.getElementById("drawer-mal-btn");
    if (malBtn) {
      malBtn.href = item.mal_url || (isAnime ? `https://myanimelist.net/anime/${item.id}` : `https://myanimelist.net/manga/${item.id}`);
      malBtn.target = "_blank";
      malBtn.rel = "noopener noreferrer";
    }

    // Update navigation buttons (Prev / Next)
    updateDrawerNavButtons();

    // Show drawer
    if (backdrop) backdrop.classList.add("active");
    if (panel) panel.classList.add("active");
    document.body.style.overflow = "hidden";
  }

  function closeDetailDrawer() {
    const backdrop = document.getElementById("drawer-backdrop");
    const panel = document.getElementById("drawer-panel");
    if (backdrop) backdrop.classList.remove("active");
    if (panel) panel.classList.remove("active");
    document.body.style.overflow = "";
    state.currentDrawerIndex = -1;
  }

  function updateDrawerNavButtons() {
    const prevBtn = document.getElementById("drawer-prev-btn");
    const nextBtn = document.getElementById("drawer-next-btn");
    if (prevBtn) {
      prevBtn.disabled = state.currentDrawerIndex <= 0;
    }
    if (nextBtn) {
      nextBtn.disabled = state.currentDrawerIndex >= state.filteredEntries.length - 1;
    }
  }

  function navigateDrawer(direction) {
    const newIndex = state.currentDrawerIndex + direction;
    if (newIndex >= 0 && newIndex < state.filteredEntries.length) {
      openDetailDrawer(newIndex);
    }
  }

  // --- View Mode Switcher ---
  function setViewMode(mode) {
    state.viewMode = mode;
    storage.set("animanga_view_mode", mode);

    const galleryBtn = document.getElementById("view-gallery-btn");
    const tableBtn = document.getElementById("view-table-btn");

    if (galleryBtn && tableBtn) {
      if (mode === "gallery") {
        galleryBtn.classList.add("active");
        tableBtn.classList.remove("active");
      } else {
        tableBtn.classList.add("active");
        galleryBtn.classList.remove("active");
      }
    }

    renderResults();
  }

  // --- Theme Manager (Dark / Light) ---
  function initTheme() {
    const savedTheme = storage.get("animanga_theme", null);
    if (savedTheme) {
      setTheme(savedTheme);
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      setTheme(prefersDark ? "dark" : "light");
    }

    // Listen for OS theme changes if user has no stored preference
    try {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
        if (!storage.get("animanga_theme", null)) {
          setTheme(e.matches ? "dark" : "light");
        }
      });
    } catch (e) {}
  }

  function setTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    storage.set("animanga_theme", theme);

    const themeToggleBtn = document.getElementById("theme-toggle-btn");
    if (themeToggleBtn) {
      themeToggleBtn.setAttribute("title", `Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`);
      const sunIcon = themeToggleBtn.querySelector(".icon-sun");
      const moonIcon = themeToggleBtn.querySelector(".icon-moon");
      if (sunIcon && moonIcon) {
        if (theme === "dark") {
          sunIcon.style.display = "block";
          moonIcon.style.display = "none";
        } else {
          sunIcon.style.display = "none";
          moonIcon.style.display = "block";
        }
      }
    }
  }

  function toggleTheme() {
    setTheme(state.theme === "dark" ? "light" : "dark");
  }

  // --- Search Clear Button Visibility ---
  function updateSearchClearButton() {
    const clearBtn = document.getElementById("search-clear-btn");
    if (!clearBtn) return;
    clearBtn.style.display = state.filters.searchQuery.trim() ? "flex" : "none";
  }

  // --- Attach All UI Event Listeners ---
  function attachEventListeners() {
    // 1. Search Input
    const searchInput = document.getElementById("search-input");
    const searchClearBtn = document.getElementById("search-clear-btn");

    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        state.filters.searchQuery = e.target.value;
        updateSearchClearButton();
        applyFiltersAndSort();
      });
    }

    if (searchClearBtn) {
      searchClearBtn.addEventListener("click", () => {
        state.filters.searchQuery = "";
        if (searchInput) {
          searchInput.value = "";
          searchInput.focus();
        }
        updateSearchClearButton();
        applyFiltersAndSort();
      });
    }

    // 2. Media Type Tabs
    const typeTabs = document.querySelectorAll(".type-tab-btn");
    typeTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        const type = tab.getAttribute("data-type");
        setMediaType(type);
      });
    });

    // 3. Dropdowns (Status, Score, Genre, Sort)
    const statusSelect = document.getElementById("status-select");
    if (statusSelect) {
      statusSelect.addEventListener("change", (e) => {
        state.filters.status = e.target.value;
        applyFiltersAndSort();
      });
    }

    const scoreSelect = document.getElementById("score-select");
    if (scoreSelect) {
      scoreSelect.addEventListener("change", (e) => {
        state.filters.scoreTier = e.target.value;
        applyFiltersAndSort();
      });
    }

    const genreSelect = document.getElementById("genre-select");
    if (genreSelect) {
      genreSelect.addEventListener("change", (e) => {
        state.filters.genre = e.target.value;
        applyFiltersAndSort();
      });
    }

    const sortSelect = document.getElementById("sort-select");
    if (sortSelect) {
      sortSelect.addEventListener("change", (e) => {
        state.filters.sortBy = e.target.value;
        applyFiltersAndSort();
      });
    }

    // 4. View Mode Toggles
    const galleryBtn = document.getElementById("view-gallery-btn");
    const tableBtn = document.getElementById("view-table-btn");
    if (galleryBtn) {
      galleryBtn.addEventListener("click", () => setViewMode("gallery"));
    }
    if (tableBtn) {
      tableBtn.addEventListener("click", () => setViewMode("table"));
    }

    // 5. Theme Toggle
    const themeBtn = document.getElementById("theme-toggle-btn");
    if (themeBtn) {
      themeBtn.addEventListener("click", toggleTheme);
    }

    // 6. Drawer Close & Nav
    const drawerCloseBtn = document.getElementById("drawer-close-btn");
    const drawerBackdrop = document.getElementById("drawer-backdrop");
    const drawerPrevBtn = document.getElementById("drawer-prev-btn");
    const drawerNextBtn = document.getElementById("drawer-next-btn");

    if (drawerCloseBtn) drawerCloseBtn.addEventListener("click", closeDetailDrawer);
    if (drawerBackdrop) drawerBackdrop.addEventListener("click", closeDetailDrawer);
    if (drawerPrevBtn) drawerPrevBtn.addEventListener("click", () => navigateDrawer(-1));
    if (drawerNextBtn) drawerNextBtn.addEventListener("click", () => navigateDrawer(1));

    // 7. Global Keyboard Shortcuts
    window.addEventListener("keydown", (e) => {
      // Escape: Close drawer or clear search
      if (e.key === "Escape") {
        if (state.currentDrawerIndex >= 0) {
          closeDetailDrawer();
        } else if (searchInput && document.activeElement === searchInput) {
          searchInput.value = "";
          state.filters.searchQuery = "";
          updateSearchClearButton();
          applyFiltersAndSort();
          searchInput.blur();
        }
      }

      // Drawer navigation via Left/Right arrow keys
      if (state.currentDrawerIndex >= 0) {
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          navigateDrawer(-1);
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          navigateDrawer(1);
        }
        return;
      }

      // Focus search via '/' or Ctrl+K when not typing in an input
      if (e.target.tagName !== "INPUT" && e.target.tagName !== "SELECT" && e.target.tagName !== "TEXTAREA") {
        if (e.key === "/" || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) {
          e.preventDefault();
          if (searchInput) {
            searchInput.focus();
            searchInput.select();
          }
        } else if (e.key.toLowerCase() === "g") {
          e.preventDefault();
          setViewMode("gallery");
        } else if (e.key.toLowerCase() === "t") {
          e.preventDefault();
          setViewMode("table");
        }
      }
    });
  }

  // --- Toast Notification Helper ---
  function showToast(msg) {
    let t = document.getElementById("app-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "app-toast";
      t.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1E293B;color:#F8FAFC;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;box-shadow:0 10px 25px rgba(0,0,0,0.5);border:1px solid #334155;z-index:9999;transition:opacity 0.3s;pointer-events:none;";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = "1";
    setTimeout(() => { t.style.opacity = "0"; }, 2500);
  }

  // --- Feature Modals Logic (Quiz, Matcher, Share Card) ---
  function initModalsAndFeatures() {
    // 1. Modal Triggers & Elements
    const quizBtn = document.getElementById("quiz-btn");
    const matcherBtn = document.getElementById("matcher-btn");
    const shareCardBtn = document.getElementById("share-card-btn");

    const quizModal = document.getElementById("quiz-modal");
    const matcherModal = document.getElementById("matcher-modal");
    const shareCardModal = document.getElementById("share-card-modal");

    function openModal(modal) {
      if (!modal) return;
      modal.style.display = "flex";
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    }

    function closeModal(modal) {
      if (!modal) return;
      modal.style.display = "none";
      modal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    }

    // Close buttons
    document.getElementById("quiz-modal-close")?.addEventListener("click", () => closeModal(quizModal));
    document.getElementById("matcher-modal-close")?.addEventListener("click", () => closeModal(matcherModal));
    document.getElementById("share-card-modal-close")?.addEventListener("click", () => closeModal(shareCardModal));

    // Close on backdrop click
    [quizModal, matcherModal, shareCardModal].forEach(modal => {
      if (!modal) return;
      modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal(modal);
      });
    });

    // Close on Escape key
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeModal(quizModal);
        closeModal(matcherModal);
        closeModal(shareCardModal);
      }
    });

    // --- Feature 1: Mood Quiz ---
    const moodPresets = {
      cry: {
        filterGenre: "Drama",
        titleKeywords: ["clannad", "anohana", "punpun", "solanin", "angel beats", "takopii"],
        name: "Emotional & Nangis"
      },
      mind: {
        filterGenre: "Sci-Fi",
        titleKeywords: ["steins;gate", "monster", "shingeki", "shinsekai", "aku no hana"],
        name: "Mind-Bending & Thriller"
      },
      romcom: {
        filterGenre: "Romance",
        titleKeywords: ["kaguya", "hanayome", "komi", "bocchi", "sakurai"],
        name: "Romcom & Wholesome"
      },
      dark: {
        filterGenre: "Action",
        titleKeywords: ["berserk", "shingeki", "chainsaw", "vinland", "parasyte"],
        name: "Dark Fantasy & Epik"
      },
      psych: {
        filterGenre: "Psychological",
        titleKeywords: ["punpun", "aku no hana", "solanin", "takopii", "kurosawa"],
        name: "Psikologis Mendalam"
      },
      chill: {
        filterGenre: "Slice of Life",
        titleKeywords: ["3-gatsu", "bocchi", "barakamon", "yuru", "clannad"],
        name: "Santai & Slice of Life"
      }
    };

    let currentSelectedMood = "cry";

    function renderMoodRecs(moodKey) {
      const container = document.getElementById("mood-recommendations-list");
      if (!container) return;
      const preset = moodPresets[moodKey] || moodPresets.cry;
      currentSelectedMood = moodKey;

      const matches = state.allEntries
        .filter(item => {
          const score = parseInt(item.user_score, 10) || 0;
          const titleLower = item.title.toLowerCase();
          const matchKeyword = preset.titleKeywords.some(kw => titleLower.includes(kw));
          const hasGenre = item.genres && item.genres.some(g => g.toLowerCase().includes(preset.filterGenre.toLowerCase()));
          return (matchKeyword && score >= 8) || (hasGenre && score >= 9);
        })
        .sort((a, b) => (parseInt(b.user_score, 10) || 0) - (parseInt(a.user_score, 10) || 0))
        .slice(0, 4);

      container.innerHTML = matches.map(item => `
        <div class="mood-rec-card" data-id="${item.id}">
          <img class="mood-rec-thumb" src="${item.poster_url || ''}" alt="${escapeHtml(item.title)}" onerror="this.src='${getPosterPlaceholder(item.title, item.media_type)}'" />
          <div class="mood-rec-info">
            <div class="mood-rec-title">${escapeHtml(item.title)}</div>
            <div class="mood-rec-meta">
              <span style="color: #FBBF24; font-weight: 700;">&starf; Skor Hazza: ${item.user_score}/10</span>
              <span>&bull; ${escapeHtml(item.media_type.toUpperCase())}</span>
              <span>&bull; ${escapeHtml((item.genres || []).slice(0, 2).join(', '))}</span>
            </div>
          </div>
        </div>
      `).join("");

      container.querySelectorAll(".mood-rec-card").forEach(card => {
        card.addEventListener("click", () => {
          const id = parseInt(card.dataset.id, 10);
          const idx = state.filteredEntries.findIndex(e => e.id === id);
          closeModal(quizModal);
          if (idx >= 0) {
            openDetailDrawer(idx);
          } else {
            resetAllFilters();
            const newIdx = state.filteredEntries.findIndex(e => e.id === id);
            if (newIdx >= 0) openDetailDrawer(newIdx);
          }
        });
      });
    }

    document.querySelectorAll(".mood-chip-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".mood-chip-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        renderMoodRecs(btn.dataset.mood);
      });
    });

    document.getElementById("apply-mood-to-catalog")?.addEventListener("click", () => {
      const preset = moodPresets[currentSelectedMood];
      closeModal(quizModal);
      if (preset) {
        resetAllFilters();
        const genreSelect = document.getElementById("genre-select");
        const scoreSelect = document.getElementById("score-select");
        if (genreSelect) {
          const opt = Array.from(genreSelect.options).find(o => o.value.toLowerCase() === preset.filterGenre.toLowerCase());
          if (opt) {
            genreSelect.value = opt.value;
            state.filters.genre = opt.value;
          }
        }
        if (scoreSelect) {
          scoreSelect.value = "masterpiece";
          state.filters.scoreTier = "masterpiece";
        }
        applyFiltersAndSort();
      }
    });

    quizBtn?.addEventListener("click", () => {
      openModal(quizModal);
      renderMoodRecs(currentSelectedMood);
    });

    // --- Feature 2: Friend Taste Matcher ---
    const iconicTitles = [
      "Steins;Gate",
      "Clannad: After Story",
      "Berserk",
      "Oyasumi Punpun",
      "Kaguya-sama wa Kokurasetai: Ultra Romantic",
      "Shingeki no Kyojin Season 3 Part 2",
      "Bocchi the Rock!",
      "Monster",
      "Aku no Hana",
      "3-gatsu no Lion",
      "Ano Hi Mita Hana no Namae wo Bokutachi wa Mada Shiranai.",
      "5-toubun no Hanayome",
      "Solanin",
      "Takopii no Genzai",
      "Angel Beats!",
      "Komi-san wa, Comyushou desu."
    ];

    function renderMatcher() {
      const checklist = document.getElementById("matcher-checklist");
      if (!checklist) return;
      checklist.innerHTML = iconicTitles.map((title, i) => `
        <label class="matcher-check-item">
          <input type="checkbox" data-index="${i}" class="matcher-cb" />
          <span>${escapeHtml(title)}</span>
        </label>
      `).join("");

      checklist.querySelectorAll(".matcher-cb").forEach(cb => {
        cb.addEventListener("change", calculateMatch);
      });
      calculateMatch();
    }

    function calculateMatch() {
      const checkedCount = document.querySelectorAll(".matcher-cb:checked").length;
      let pct = 0;
      let title = "Pilih judul di atas";
      let desc = "Centang beberapa judul yang pernah kamu nikmati untuk melihat tingkat kecocokan.";

      if (checkedCount > 0) {
        pct = Math.min(100, Math.round((checkedCount / 10) * 100));
        if (pct <= 30) {
          title = "Level 1: Selera Kita Berbeda Server 🍃";
          desc = "Kalian punya preferensi berbeda, tapi Hazza sangat merekomendasikan tonton Steins;Gate atau baca Punpun!";
        } else if (pct <= 60) {
          title = "Level 2: Lumayan Nyambung! 🍿";
          desc = "Kalian sama-sama menikmati beberapa anime/manga hits berkualitas.";
        } else if (pct <= 85) {
          title = "Level 3: Satu Frekuensi Selera Keren! 🔥";
          desc = "Kalian punya radar selera yang mirip, terutama di cerita emosional dan plot berbobot.";
        } else {
          title = "Level 4: SOULMATE WIBU SEJATI! 👑";
          desc = "Selera kamu dan Hazza 100% identik! Sama-sama penikmat drama psikologis dan masterpiece sejati.";
        }
      }

      const badge = document.getElementById("match-percentage-badge");
      const titleEl = document.getElementById("match-verdict-title");
      const descEl = document.getElementById("match-verdict-desc");

      if (badge) badge.textContent = `${pct}%`;
      if (titleEl) titleEl.textContent = title;
      if (descEl) descEl.textContent = desc;
    }

    matcherBtn?.addEventListener("click", () => {
      openModal(matcherModal);
      renderMatcher();
    });

    document.getElementById("copy-match-result-btn")?.addEventListener("click", () => {
      const badge = document.getElementById("match-percentage-badge")?.textContent || "0%";
      const title = document.getElementById("match-verdict-title")?.textContent || "";
      const text = `🤝 Hasil Taste Match dengan Hazza: ${badge}!\n"${title}"\nCek katalog selera Hazza di: ${window.location.href}`;
      navigator.clipboard.writeText(text).then(() => {
        showToast("Hasil match berhasil disalin ke clipboard!");
      }).catch(() => {
        alert(text);
      });
    });

    // --- Feature 3: Share Taste Card ---
    shareCardBtn?.addEventListener("click", () => {
      openModal(shareCardModal);
    });

    document.getElementById("copy-card-text-btn")?.addEventListener("click", () => {
      const text = `📇 Hazza's Animanga Vault\n` +
        `• 219 Anime & 47 Manga (227 Selesai)\n` +
        `• Rata-rata Skor: 8.1 / 10\n` +
        `• All-Time Masterpieces (10/10): Clannad: After Story, Steins;Gate, Berserk, Oyasumi Punpun, Kaguya-sama\n` +
        `• Buka katalog interaktif: ${window.location.href}`;
      navigator.clipboard.writeText(text).then(() => {
        showToast("Ringkasan profil berhasil disalin!");
      }).catch(() => {
        alert(text);
      });
    });

    document.getElementById("copy-web-link-btn")?.addEventListener("click", () => {
      navigator.clipboard.writeText(window.location.href).then(() => {
        showToast("Link website berhasil disalin!");
      }).catch(() => {
        alert(window.location.href);
      });
    });
  }

  // --- Main Bootstrapper ---
  function init() {
    initTheme();
    initData();

    // Restore saved view mode
    const savedView = storage.get("animanga_view_mode", "gallery");
    state.viewMode = savedView;
    const galleryBtn = document.getElementById("view-gallery-btn");
    const tableBtn = document.getElementById("view-table-btn");
    if (galleryBtn && tableBtn) {
      if (savedView === "table") {
        tableBtn.classList.add("active");
        galleryBtn.classList.remove("active");
      } else {
        galleryBtn.classList.add("active");
        tableBtn.classList.remove("active");
      }
    }

    attachEventListeners();
    initModalsAndFeatures();
    applyFiltersAndSort();
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
