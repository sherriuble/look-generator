const weatherGridEl = document.getElementById("weatherGrid");
const occasionGridEl = document.getElementById("occasionGrid");
const preferLayersEl = document.getElementById("preferLayers");
const generateBtn = document.getElementById("generate");
const resultEl = document.getElementById("result");
const outfitResultSection = document.getElementById("outfitResult");
const tripRowsEl = document.getElementById("tripRows");
const addTripRowBtn = document.getElementById("addTripRow");
const generateTripBtn = document.getElementById("generateTrip");
const encourageRepeatsEl = document.getElementById("encourageRepeats");
const tripResultEl = document.getElementById("tripResult");
const tripResultSectionEl = document.getElementById("tripResultSection");
const tabDailyBtn = document.getElementById("tabDaily");
const tabTripBtn = document.getElementById("tabTrip");
const dailyTabPanel = document.getElementById("dailyTabPanel");
const tripTabPanel = document.getElementById("tripTabPanel");

const WEATHER_META = {
  hot_warm: { icon: "☀️", name: "Hot / Warm", range: "(30-19°C)" },
  pleasant_chilly: { icon: "🍃", name: "Pleasant / Chilly", range: "(18-10°C)" },
  cold: { icon: "❄️", name: "Cold / Cold AF", range: "(+9-10°C)" },
};

const OCCASION_META = {
  sport: "Sport",
  casual: "Casual",
  work: "Work",
  nice: "Nice",
};

let selectedWeather = null;
let selectedOccasion = null;
let db = null;
let tripRows = [];
let nextTripRowId = 1;

/** Cleared on full page reload; used to skip items for subsequent Generate clicks. */
const excludedItemIds = new Set();
const WEATHER_ORDER = ["hot_warm", "pleasant_chilly", "cold"];
const OCCASION_ORDER = ["sport", "casual", "work", "nice"];
const REPEAT_WEIGHTS = {
  shoes: 6,
  bottom: 4,
  top: 2,
  hat: 1,
  underlayer: 1,
  overlayer: 1,
};

function weatherSort(a, b) {
  return WEATHER_ORDER.indexOf(a) - WEATHER_ORDER.indexOf(b);
}

function occasionSort(a, b) {
  return OCCASION_ORDER.indexOf(a) - OCCASION_ORDER.indexOf(b);
}

function weatherValues() {
  return [...WEATHER_ORDER];
}

function occasionValues() {
  return [...OCCASION_ORDER];
}

function selectButton(container, value) {
  for (const btn of container.querySelectorAll("button")) {
    btn.classList.toggle("active", btn.dataset.value === value);
  }
}

function renderWeatherOptions(weathers) {
  weatherGridEl.innerHTML = "";
  for (const weather of weathers.sort(weatherSort)) {
    const meta = WEATHER_META[weather] || { icon: "•", name: weather, range: "" };
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "weather-card";
    btn.dataset.value = weather;
    btn.innerHTML = `
      <div class="weather-card__inner">
        <div class="weather-icon-wrap" aria-hidden="true"><span class="weather-icon">${meta.icon}</span></div>
        <div class="weather-copy">
          <div class="weather-name">${meta.name}</div>
          <div class="weather-range">${meta.range}</div>
        </div>
      </div>
    `;
    btn.addEventListener("click", () => {
      selectedWeather = weather;
      selectButton(weatherGridEl, selectedWeather);
    });
    weatherGridEl.appendChild(btn);
  }
  selectedWeather = weathers.sort(weatherSort)[0] || null;
  selectButton(weatherGridEl, selectedWeather);
}

function renderOccasionOptions(occasions) {
  occasionGridEl.innerHTML = "";
  for (const occasion of occasions.sort(occasionSort)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "occasion-pill";
    btn.dataset.value = occasion;
    btn.textContent = OCCASION_META[occasion] || occasion;
    btn.addEventListener("click", () => {
      selectedOccasion = occasion;
      selectButton(occasionGridEl, selectedOccasion);
    });
    occasionGridEl.appendChild(btn);
  }
  selectedOccasion = occasions.sort(occasionSort)[0] || null;
  selectButton(occasionGridEl, selectedOccasion);
}

async function loadMeta() {
  renderWeatherOptions(weatherValues());
  renderOccasionOptions(occasionValues());
  initTripPicker();
}

async function loadDB() {
  const [items, clusters, topMatches, imageMap] = await Promise.all([
    fetch("/data/items.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("/data/clusters.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("/data/top_matches.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("/data/image_map.json", { cache: "no-store" }).then((r) => r.json()),
  ]);
  db = {
    items,
    clusters,
    topMatches,
    imageMap,
    itemIndex: Object.fromEntries(items.map((i) => [i.item_id, i])),
    clusterIndex: Object.fromEntries(clusters.map((c) => [c.cluster_id, c])),
  };
}

function historyKey(weather, occasion) {
  return `outfit_history:${weather}:${occasion}`;
}

function getHistory(weather, occasion) {
  try {
    return JSON.parse(sessionStorage.getItem(historyKey(weather, occasion)) || "[]");
  } catch {
    return [];
  }
}

function setHistory(weather, occasion, entries) {
  sessionStorage.setItem(historyKey(weather, occasion), JSON.stringify(entries.slice(-200)));
}

function randomPick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function weightedPick(arr, getWeight) {
  if (!arr.length) return null;
  const weights = arr.map((item) => Math.max(0, Number(getWeight(item)) || 0));
  const total = weights.reduce((sum, w) => sum + w, 0);
  if (total <= 0) return randomPick(arr);
  let cursor = Math.random() * total;
  for (let i = 0; i < arr.length; i += 1) {
    cursor -= weights[i];
    if (cursor <= 0) return arr[i];
  }
  return arr[arr.length - 1];
}

function allowedIds(ids) {
  if (!ids?.length) return [];
  return ids.filter((id) => !excludedItemIds.has(id));
}

function isDressMatch(m) {
  const topIds =
    m.source_kind === "item" ? [m.source_id] : db.clusterIndex[m.source_id]?.member_item_ids || [];
  return topIds.some((id) => db.itemIndex[id]?.subtype === "dress");
}

function matchIsViable(m) {
  if (!allowedIds(topIdsFor(m)).length) return false;
  if (!allowedIds(m.shoes_ids || []).length) return false;
  if (!isDressMatch(m) && !allowedIds(m.bottom_ids || []).length) return false;
  return true;
}

function topIdsFor(match) {
  if (match.source_kind === "item") return [match.source_id];
  const cl = db.clusterIndex[match.source_id];
  return cl ? cl.member_item_ids : [];
}

function usageCountForAny(ids, usageCounts) {
  if (!usageCounts || !ids?.length) return 0;
  return ids.reduce((maxCount, id) => Math.max(maxCount, usageCounts.get(id) || 0), 0);
}

function formatItem(itemId) {
  const item = db.itemIndex[itemId];
  const image = db.imageMap[itemId] || {};
  if (!item) return null;
  return {
    item_id: item.item_id,
    name: item.name,
    type: item.type,
    subtype: item.subtype,
    image_thumb: image.thumb,
    image_full: image.full,
  };
}

function chooseMatch(weather, occasion, layerMode, options = {}) {
  const { bypassHistory = false, encourageRepeats = false, usageCounts = null } = options;
  const isDressCandidate = (m) => {
    const topIds = m.source_kind === "item" ? [m.source_id] : db.clusterIndex[m.source_id]?.member_item_ids || [];
    return topIds.some((id) => db.itemIndex[id]?.subtype === "dress");
  };

  const candidates = db.topMatches
    .filter((m) => m.weather_bucket === weather && m.occasion === occasion)
    .filter((m) => {
      const hasShoes = (m.shoes_ids || []).length > 0;
      const hasBottoms = (m.bottom_ids || []).length > 0;
      return hasShoes && (hasBottoms || isDressCandidate(m));
    })
    .map((m) => ({
      ...m,
      match_key: `${m.weather_bucket}|${m.occasion}|${m.source_kind}|${m.source_id}`,
    }));

  if (!candidates.length) {
    throw new Error(`No look candidates for ${weather} + ${occasion}.`);
  }

  const viable = candidates.filter(matchIsViable);
  if (!viable.length) {
    throw new Error(
      "No looks left — every option uses items you hid. Refresh the page to reset, or pick different weather/occasion."
    );
  }

  const used = bypassHistory ? new Set() : new Set(getHistory(weather, occasion).map((h) => h.match_key));
  const pool = bypassHistory ? viable : viable.filter((c) => !used.has(c.match_key));
  const basePool = pool.length ? pool : viable;
  const hasLayer = (m) => (m.underlayer_ids || []).length > 0 || (m.overlayer_ids || []).length > 0;
  const withRepeatBias = (list) => {
    if (!encourageRepeats || !usageCounts) return randomPick(list);
    return weightedPick(list, (m) => {
      const score =
        usageCountForAny(m.shoes_ids || [], usageCounts) * REPEAT_WEIGHTS.shoes +
        usageCountForAny(m.bottom_ids || [], usageCounts) * REPEAT_WEIGHTS.bottom +
        usageCountForAny(topIdsFor(m), usageCounts) * REPEAT_WEIGHTS.top +
        usageCountForAny(m.hat_ids || [], usageCounts) * REPEAT_WEIGHTS.hat +
        usageCountForAny(m.underlayer_ids || [], usageCounts) * REPEAT_WEIGHTS.underlayer +
        usageCountForAny(m.overlayer_ids || [], usageCounts) * REPEAT_WEIGHTS.overlayer;
      return 1 + score;
    });
  };

  if (layerMode === "required") {
    const layered = basePool.filter(hasLayer);
    if (!layered.length) throw new Error("No layered looks found for this selection.");
    return withRepeatBias(layered);
  }
  if (layerMode === "prefer") {
    const layered = basePool.filter(hasLayer);
    return withRepeatBias(layered.length ? layered : basePool);
  }
  if (layerMode === "auto" && (weather === "pleasant_chilly" || weather === "cold")) {
    const layered = basePool.filter(hasLayer);
    if (layered.length) return withRepeatBias(layered);
  }
  return withRepeatBias(basePool);
}

function pickItemOrNull(ids, usageCounts = null, encourageRepeats = false, slotWeight = 1) {
  const allowed = allowedIds(ids);
  if (!allowed.length) return null;
  const picked = encourageRepeats
    ? weightedPick(allowed, (id) => 1 + (usageCounts?.get(id) || 0) * slotWeight)
    : randomPick(allowed);
  return formatItem(picked);
}

function generateLocal(weather, occasion, layerMode, options = {}) {
  const { bypassHistory = false, encourageRepeats = false, usageCounts = null } = options;
  const selected = chooseMatch(weather, occasion, layerMode, {
    bypassHistory,
    encourageRepeats,
    usageCounts,
  });
  const topIds = topIdsFor(selected);
  if (!topIds.length) throw new Error("Selected look has no top.");

  const tops = allowedIds(topIds);
  if (!tops.length) throw new Error("Selected look has no top after exclusions.");

  const topPick = encourageRepeats
    ? weightedPick(tops, (id) => 1 + (usageCounts?.get(id) || 0) * REPEAT_WEIGHTS.top)
    : randomPick(tops);
  const outfit = {
    weather,
    occasion,
    top: formatItem(topPick),
    bottom: selected.bottom_ids?.length
      ? pickItemOrNull(selected.bottom_ids, usageCounts, encourageRepeats, REPEAT_WEIGHTS.bottom)
      : null,
    shoes: pickItemOrNull(selected.shoes_ids, usageCounts, encourageRepeats, REPEAT_WEIGHTS.shoes),
    hat: selected.hat_ids?.length
      ? pickItemOrNull(selected.hat_ids, usageCounts, encourageRepeats, REPEAT_WEIGHTS.hat)
      : null,
    underlayer: selected.underlayer_ids?.length
      ? pickItemOrNull(selected.underlayer_ids, usageCounts, encourageRepeats, REPEAT_WEIGHTS.underlayer)
      : null,
    overlayer: selected.overlayer_ids?.length
      ? pickItemOrNull(selected.overlayer_ids, usageCounts, encourageRepeats, REPEAT_WEIGHTS.overlayer)
      : null,
    match_key: selected.match_key,
  };

  if (!outfit.shoes) throw new Error("Selected look has no shoes after exclusions.");
  if (!isDressMatch(selected) && selected.bottom_ids?.length && !outfit.bottom) {
    throw new Error("Selected look has no bottom after exclusions.");
  }

  if (!bypassHistory) {
    const hist = getHistory(weather, occasion);
    hist.push({ match_key: selected.match_key, ts: Date.now() });
    setHistory(weather, occasion, hist);
  }
  return outfit;
}

function recordOutfitUsage(outfit, usageCounts) {
  if (!usageCounts) return;
  const ids = [outfit.top, outfit.bottom, outfit.shoes, outfit.hat, outfit.underlayer, outfit.overlayer]
    .filter(Boolean)
    .map((item) => item.item_id);
  for (const id of ids) {
    usageCounts.set(id, (usageCounts.get(id) || 0) + 1);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function slotSlug(slot) {
  return String(slot)
    .toLowerCase()
    .replace(/\s+/g, "-");
}

function photoUrlForItem(imgPath) {
  const path = imgPath.startsWith("/") ? imgPath : `/${imgPath}`;
  return encodeURI(path);
}

function itemCard(slot, item, options = {}) {
  const { showSkip = true } = options;
  if (!item) return "";
  const img = item.image_thumb || item.image_full || "";
  const safeName = escapeHtml(item.name);
  const safeSlot = escapeHtml(slot.toUpperCase());
  const slug = slotSlug(slot);
  const url = photoUrlForItem(img);
  /* One element paints the bitmap: background on .card__media only (no nested layer). */
  return `
    <article class="card" data-slot="${escapeHtml(slug)}">
      <div class="card__figure">
        <div class="card__figure-inner">
          <div
            class="card__media"
            style='background-image: url(${JSON.stringify(url)});'
            role="img"
            aria-label="${safeName}"
          >
            ${
              showSkip
                ? `<button type="button" class="skip-item-btn" data-item-id="${escapeHtml(
                    item.item_id
                  )}" aria-label="Don't show this item again" title="Don't show again">×</button>`
                : ""
            }
          </div>
        </div>
      </div>
      <div class="card__labels">
        <div class="card__category">${safeSlot}</div>
        <div class="card__name">${safeName}</div>
      </div>
    </article>
  `;
}

function rowSelect(options, selectedValue, className, dataField) {
  return `
    <select class="${className}" data-field="${dataField}">
      ${options
        .map((value) => {
          const label = dataField === "weather" ? WEATHER_META[value]?.name || value : OCCASION_META[value] || value;
          const selected = value === selectedValue ? "selected" : "";
          return `<option value="${value}" ${selected}>${escapeHtml(label)}</option>`;
        })
        .join("")}
    </select>
  `;
}

function initTripPicker() {
  if (!tripRows.length) {
    tripRows = [{ id: nextTripRowId++, weather: selectedWeather || "hot_warm", occasion: "casual", count: 1 }];
  }
  renderTripRows();
}

function renderTripRows() {
  if (!tripRowsEl) return;
  tripRowsEl.innerHTML = tripRows
    .map(
      (row) => `
      <div class="trip-row" data-row-id="${row.id}">
        ${rowSelect(weatherValues(), row.weather, "trip-select", "weather")}
        ${rowSelect(occasionValues(), row.occasion, "trip-select", "occasion")}
        <input class="trip-count" data-field="count" type="number" min="1" max="14" value="${row.count}" />
        <button type="button" class="trip-remove" data-action="remove" aria-label="Remove row">Remove</button>
      </div>
    `
    )
    .join("");
}

function setActiveTab(tab) {
  const isDaily = tab === "daily";
  tabDailyBtn?.classList.toggle("active", isDaily);
  tabTripBtn?.classList.toggle("active", !isDaily);
  dailyTabPanel?.classList.toggle("hidden", !isDaily);
  tripTabPanel?.classList.toggle("hidden", isDaily);
}

function renderOutfitCards(outfit, showSkip = true) {
  return [
    ["Top", outfit.top],
    ["Bottom", outfit.bottom],
    ["Shoes", outfit.shoes],
    ["Hat", outfit.hat],
    ["Underlayer", outfit.underlayer],
    ["Overlayer", outfit.overlayer],
  ]
    .map(([slot, item]) => itemCard(slot, item, { showSkip }))
    .join("");
}

function generateTripLooks() {
  if (!db) {
    tripResultEl.classList.remove("hidden");
    tripResultEl.innerHTML = '<p class="result-message">Loading data, try again in a second.</p>';
    return;
  }
  const layerMode = preferLayersEl.checked ? "prefer" : "auto";
  const encourageRepeats = Boolean(encourageRepeatsEl?.checked);
  const usageCounts = new Map();
  const looks = [];
  try {
    for (const row of tripRows) {
      for (let i = 0; i < row.count; i += 1) {
        const outfit = generateLocal(row.weather, row.occasion, layerMode, {
          bypassHistory: true,
          encourageRepeats,
          usageCounts,
        });
        looks.push({ row, lookNumber: i + 1, outfit });
        recordOutfitUsage(outfit, usageCounts);
      }
    }
  } catch (err) {
    tripResultEl.classList.remove("hidden");
    tripResultEl.innerHTML = `<p class="result-message">${escapeHtml(
      err.message || "Could not generate trip looks."
    )}</p>`;
    return;
  }

  tripResultSectionEl.classList.add("outfit-result--outfit");
  tripResultEl.classList.remove("hidden");
  tripResultEl.innerHTML = looks
    .map(({ row, lookNumber, outfit }) => {
      const weatherLabel = WEATHER_META[row.weather]?.name || row.weather;
      const occasionLabel = OCCASION_META[row.occasion] || row.occasion;
      return `
        <section class="trip-look">
          <h3 class="trip-look__title">${escapeHtml(weatherLabel)} - ${escapeHtml(
        occasionLabel
      )} - Look ${lookNumber}/${row.count}</h3>
          <div class="result">${renderOutfitCards(outfit, false)}</div>
        </section>
      `;
    })
    .join("");
}

async function generate() {
  const weather = selectedWeather;
  const occasion = selectedOccasion;
  if (!db) {
    resultEl.classList.remove("hidden", "result--outfit");
    outfitResultSection.classList.remove("outfit-result--outfit");
    resultEl.innerHTML = '<p class="result-message">Loading data, try again in a second.</p>';
    return;
  }
  if (!weather || !occasion) {
    resultEl.classList.remove("hidden", "result--outfit");
    outfitResultSection.classList.remove("outfit-result--outfit");
    resultEl.innerHTML = '<p class="result-message">Please select weather and occasion first.</p>';
    return;
  }
  const layerMode = preferLayersEl.checked ? "prefer" : "auto";
  let data = null;
  try {
    data = generateLocal(weather, occasion, layerMode);
  } catch (err) {
    resultEl.classList.remove("hidden", "result--outfit");
    outfitResultSection.classList.remove("outfit-result--outfit");
    const msg = escapeHtml(err.message || "Could not generate look.");
    resultEl.innerHTML = `<p class="result-message">${msg}</p>`;
    return;
  }

  const cards = renderOutfitCards(data, true);
  resultEl.classList.remove("hidden");
  resultEl.classList.add("result--outfit");
  outfitResultSection.classList.add("outfit-result--outfit");
  resultEl.innerHTML = cards;
}

generateBtn.addEventListener("click", generate);
generateTripBtn?.addEventListener("click", generateTripLooks);
tabDailyBtn?.addEventListener("click", () => setActiveTab("daily"));
tabTripBtn?.addEventListener("click", () => setActiveTab("trip"));

addTripRowBtn?.addEventListener("click", () => {
  tripRows.push({
    id: nextTripRowId++,
    weather: selectedWeather || "hot_warm",
    occasion: selectedOccasion || "casual",
    count: 1,
  });
  renderTripRows();
});

tripRowsEl?.addEventListener("change", (e) => {
  const rowEl = e.target.closest(".trip-row");
  if (!rowEl) return;
  const rowId = Number(rowEl.dataset.rowId);
  const row = tripRows.find((item) => item.id === rowId);
  if (!row) return;
  const field = e.target.dataset.field;
  if (field === "weather") row.weather = e.target.value;
  if (field === "occasion") row.occasion = e.target.value;
  if (field === "count") row.count = Math.max(1, Math.min(14, Number(e.target.value) || 1));
  renderTripRows();
});

tripRowsEl?.addEventListener("click", (e) => {
  const removeBtn = e.target.closest("button[data-action='remove']");
  if (!removeBtn) return;
  const rowEl = removeBtn.closest(".trip-row");
  const rowId = Number(rowEl?.dataset.rowId);
  tripRows = tripRows.filter((row) => row.id !== rowId);
  if (!tripRows.length) {
    tripRows.push({
      id: nextTripRowId++,
      weather: selectedWeather || "hot_warm",
      occasion: selectedOccasion || "casual",
      count: 1,
    });
  }
  renderTripRows();
});

resultEl.addEventListener("click", (e) => {
  const btn = e.target.closest(".skip-item-btn[data-item-id]");
  if (!btn) return;
  const id = btn.dataset.itemId;
  if (!id) return;
  excludedItemIds.add(id);
  generate();
});

Promise.all([loadMeta(), loadDB()]).catch(() => {
  resultEl.classList.remove("hidden", "result--outfit");
  outfitResultSection.classList.remove("outfit-result--outfit");
  resultEl.innerHTML = '<p class="result-message">Could not load wardrobe data files.</p>';
});

setActiveTab("daily");
