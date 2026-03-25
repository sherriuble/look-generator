const weatherGridEl = document.getElementById("weatherGrid");
const occasionGridEl = document.getElementById("occasionGrid");
const preferLayersEl = document.getElementById("preferLayers");
const generateBtn = document.getElementById("generate");
const resultEl = document.getElementById("result");

const WEATHER_META = {
  hot_warm: { icon: "☀️", name: "Hot / Warm", range: "30-19°C" },
  pleasant_chilly: { icon: "🍃", name: "Pleasant / Chilly", range: "18-10°C" },
  cold: { icon: "❄️", name: "Cold", range: "Below 10°C" },
};

const OCCASION_META = {
  sport: "Sport",
  casual: "Casual",
  nice: "Nice",
  work: "Work",
};

let selectedWeather = null;
let selectedOccasion = null;
let db = null;

/** Cleared on full page reload; used to skip items for subsequent Generate clicks. */
const excludedItemIds = new Set();

function weatherSort(a, b) {
  const order = ["hot_warm", "pleasant_chilly", "cold"];
  return order.indexOf(a) - order.indexOf(b);
}

function occasionSort(a, b) {
  const order = ["sport", "casual", "nice", "work"];
  return order.indexOf(a) - order.indexOf(b);
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
      <div class="weather-icon">${meta.icon}</div>
      <div class="weather-name">${meta.name}</div>
      <div class="weather-range">${meta.range}</div>
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
  renderWeatherOptions(Object.keys(WEATHER_META));
  renderOccasionOptions(Object.keys(OCCASION_META));
}

async function loadDB() {
  const [items, clusters, topMatches, imageMap] = await Promise.all([
    fetch("/data/items.json").then((r) => r.json()),
    fetch("/data/clusters.json").then((r) => r.json()),
    fetch("/data/top_matches.json").then((r) => r.json()),
    fetch("/data/image_map.json").then((r) => r.json()),
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
    return JSON.parse(localStorage.getItem(historyKey(weather, occasion)) || "[]");
  } catch {
    return [];
  }
}

function setHistory(weather, occasion, entries) {
  localStorage.setItem(historyKey(weather, occasion), JSON.stringify(entries.slice(-200)));
}

function randomPick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
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

function chooseMatch(weather, occasion, layerMode) {
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

  const used = new Set(getHistory(weather, occasion).map((h) => h.match_key));
  const pool = viable.filter((c) => !used.has(c.match_key));
  const basePool = pool.length ? pool : viable;
  const hasLayer = (m) => (m.underlayer_ids || []).length > 0 || (m.overlayer_ids || []).length > 0;

  if (layerMode === "required") {
    const layered = basePool.filter(hasLayer);
    if (!layered.length) throw new Error("No layered looks found for this selection.");
    return randomPick(layered);
  }
  if (layerMode === "prefer") {
    const layered = basePool.filter(hasLayer);
    return randomPick(layered.length ? layered : basePool);
  }
  if (layerMode === "auto" && (weather === "pleasant_chilly" || weather === "cold")) {
    const layered = basePool.filter(hasLayer);
    if (layered.length) return randomPick(layered);
  }
  return randomPick(basePool);
}

function pickItemOrNull(ids) {
  const allowed = allowedIds(ids);
  if (!allowed.length) return null;
  return formatItem(randomPick(allowed));
}

function generateLocal(weather, occasion, layerMode) {
  const selected = chooseMatch(weather, occasion, layerMode);
  const topIds = topIdsFor(selected);
  if (!topIds.length) throw new Error("Selected look has no top.");

  const tops = allowedIds(topIds);
  if (!tops.length) throw new Error("Selected look has no top after exclusions.");

  const outfit = {
    weather,
    occasion,
    top: formatItem(randomPick(tops)),
    bottom: selected.bottom_ids?.length ? pickItemOrNull(selected.bottom_ids) : null,
    shoes: pickItemOrNull(selected.shoes_ids),
    hat: selected.hat_ids?.length ? pickItemOrNull(selected.hat_ids) : null,
    underlayer: selected.underlayer_ids?.length ? pickItemOrNull(selected.underlayer_ids) : null,
    overlayer: selected.overlayer_ids?.length ? pickItemOrNull(selected.overlayer_ids) : null,
    match_key: selected.match_key,
  };

  if (!outfit.shoes) throw new Error("Selected look has no shoes after exclusions.");
  if (!isDressMatch(selected) && selected.bottom_ids?.length && !outfit.bottom) {
    throw new Error("Selected look has no bottom after exclusions.");
  }

  const hist = getHistory(weather, occasion);
  hist.push({ match_key: selected.match_key, ts: Date.now() });
  setHistory(weather, occasion, hist);
  return outfit;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function itemCard(slot, item) {
  if (!item) return "";
  const img = item.image_thumb || item.image_full || "";
  const safeName = escapeHtml(item.name);
  const safeSlot = escapeHtml(slot);
  return `
    <article class="card">
      <img src="/${img}" alt="${safeName}" />
      <div class="meta">
        <div class="slot">${safeSlot}</div>
        <div class="name">${safeName}</div>
        <button type="button" class="skip-item-btn" data-item-id="${escapeHtml(item.item_id)}">Don't show again</button>
      </div>
    </article>
  `;
}

async function generate() {
  const weather = selectedWeather;
  const occasion = selectedOccasion;
  if (!db) {
    resultEl.classList.remove("hidden");
    resultEl.innerHTML = "<p>Loading data, try again in a second.</p>";
    return;
  }
  if (!weather || !occasion) {
    resultEl.classList.remove("hidden");
    resultEl.innerHTML = "<p>Please select weather and occasion first.</p>";
    return;
  }
  const layerMode = preferLayersEl.checked ? "prefer" : "auto";
  let data = null;
  try {
    data = generateLocal(weather, occasion, layerMode);
  } catch (err) {
    resultEl.classList.remove("hidden");
    resultEl.innerHTML = `<p>${err.message || "Could not generate look."}</p>`;
    return;
  }

  const cards = [
    ["Top", data.top],
    ["Bottom", data.bottom],
    ["Shoes", data.shoes],
    ["Hat", data.hat],
    ["Underlayer", data.underlayer],
    ["Overlayer", data.overlayer],
  ]
    .map(([slot, item]) => itemCard(slot, item))
    .join("");
  resultEl.classList.remove("hidden");
  resultEl.innerHTML = cards;
}

generateBtn.addEventListener("click", generate);

resultEl.addEventListener("click", (e) => {
  const btn = e.target.closest(".skip-item-btn[data-item-id]");
  if (!btn) return;
  const id = btn.dataset.itemId;
  if (!id) return;
  excludedItemIds.add(id);
  generate();
});

Promise.all([loadMeta(), loadDB()]).catch(() => {
  resultEl.classList.remove("hidden");
  resultEl.innerHTML = "<p>Could not load wardrobe data files.</p>";
});
