const state = {
  mode: "address",
};

const formatter = new Intl.NumberFormat("ja-JP");
let map;
let mapLayers = [];

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== mode;
  });
}

function renderStatus(message, isError = false) {
  const status = document.getElementById("status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function yen(value) {
  return `¥${formatter.format(value)}`;
}

function meters(value) {
  return `${formatter.format(Math.round(value))}m`;
}

function ensureMap() {
  if (map) {
    return map;
  }
  map = L.map("resultMap", {
    zoomControl: true,
    scrollWheelZoom: false,
  });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  return map;
}

function clearMapLayers() {
  mapLayers.forEach((layer) => layer.remove());
  mapLayers = [];
}

function renderMap(data) {
  const mapInstance = ensureMap();
  clearMapLayers();

  const origin = L.marker([data.latitude, data.longitude], {
    title: "検索地点",
  }).bindPopup("検索地点");

  const nearestSample = data.samples[0];
  const nearest = L.marker([nearestSample.latitude, nearestSample.longitude], {
    title: nearestSample.point_name,
  }).bindPopup(
    `${nearestSample.point_name}<br>${yen(nearestSample.price)}<br>${meters(
      nearestSample.distance_meters
    )}`
  );

  const line = L.polyline(
    [
      [data.latitude, data.longitude],
      [nearestSample.latitude, nearestSample.longitude],
    ],
    { color: "#1f2328", weight: 2 }
  );

  const sampleMarkers = data.samples.slice(1, 6).map((item) =>
    L.circleMarker([item.latitude, item.longitude], {
      radius: 5,
      color: "#4b5563",
      weight: 1,
      fillColor: "#ffffff",
      fillOpacity: 1,
    }).bindPopup(`${item.point_name}<br>${yen(item.price)}`)
  );

  mapLayers = [origin, nearest, line, ...sampleMarkers];
  mapLayers.forEach((layer) => layer.addTo(mapInstance));

  const bounds = L.latLngBounds([
    [data.latitude, data.longitude],
    [nearestSample.latitude, nearestSample.longitude],
    ...data.samples.slice(1, 6).map((item) => [item.latitude, item.longitude]),
  ]);
  mapInstance.fitBounds(bounds.pad(0.2));
  setTimeout(() => mapInstance.invalidateSize(), 0);
}

function renderTrendChart(trend) {
  const root = document.getElementById("trendChart");
  if (!trend.length) {
    root.innerHTML = '<p class="chart-empty">推移データがありません。</p>';
    return;
  }

  const width = 640;
  const height = 220;
  const padX = 40;
  const padTop = 24;
  const padBottom = 36;
  const values = trend.map((item) => item.average_price);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const stepX = trend.length === 1 ? 0 : (width - padX * 2) / (trend.length - 1);

  const points = trend.map((item, index) => {
    const x = padX + stepX * index;
    const y =
      padTop +
      ((max - item.average_price) / range) * (height - padTop - padBottom);
    return { x, y, ...item };
  });

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");

  const labels = points
    .map(
      (point) => `
        <text x="${point.x}" y="${height - 12}" text-anchor="middle" class="chart-axis-label">
          ${point.year}
        </text>
      `
    )
    .join("");

  const dots = points
    .map(
      (point) => `
        <circle cx="${point.x}" cy="${point.y}" r="4" class="chart-dot"></circle>
        <text x="${point.x}" y="${point.y - 10}" text-anchor="middle" class="chart-value-label">
          ${formatter.format(point.average_price)}
        </text>
      `
    )
    .join("");

  root.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" class="chart-svg" role="img" aria-label="価格推移グラフ">
      <line x1="${padX}" y1="${height - padBottom}" x2="${width - padX}" y2="${height - padBottom}" class="chart-axis"></line>
      <path d="${path}" class="chart-line"></path>
      ${dots}
      ${labels}
    </svg>
  `;
}

function renderResults(data) {
  document.getElementById("empty").hidden = true;
  document.getElementById("results").hidden = false;
  document.getElementById("addressLabel").textContent = data.address;
  document.getElementById("avgPrice").textContent = yen(data.average_price);
  document.getElementById("nearestPrice").textContent = yen(data.nearest_price);
  document.getElementById("nearestPoint").textContent = data.nearest_point;
  document.getElementById("stationLabel").textContent =
    data.nearest_station ?? "-";
  document.getElementById("distanceLabel").textContent = meters(
    data.nearest_distance_meters
  );

  const sampleRows = data.samples
    .map(
      (item) => `
        <tr>
          <td>${item.point_name}</td>
          <td>${yen(item.price)}</td>
          <td>${meters(item.distance_meters)}</td>
          <td>${item.nearest_station ?? "-"}</td>
          <td>${item.use_category ?? "-"}</td>
          <td>${item.address_label ?? "-"}</td>
        </tr>
      `
    )
    .join("");
  document.getElementById("sampleBody").innerHTML = sampleRows;

  const trendRows = data.trend
    .map(
      (item) => `
        <tr>
          <td>${item.year}</td>
          <td>${yen(item.average_price)}</td>
          <td>${item.count}件</td>
        </tr>
      `
    )
    .join("");
  document.getElementById("trendBody").innerHTML = trendRows;
  renderTrendChart(data.trend);
  renderMap(data);
}

async function handleSubmit(event) {
  event.preventDefault();
  renderStatus("検索中です...");
  const slowNotice = window.setTimeout(() => {
    renderStatus("検索に時間がかかっています...");
  }, 4000);

  const payload = {
    mode: state.mode,
    address: document.getElementById("address").value || null,
    latitude: document.getElementById("latitude").value
      ? Number(document.getElementById("latitude").value)
      : null,
    longitude: document.getElementById("longitude").value
      ? Number(document.getElementById("longitude").value)
      : null,
    sample_limit: 8,
  };

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "検索に失敗しました。");
    }
    window.clearTimeout(slowNotice);
    renderResults(data);
    renderStatus("最新に取得できた年の地価情報を表示しています。");
  } catch (error) {
    window.clearTimeout(slowNotice);
    document.getElementById("results").hidden = true;
    document.getElementById("empty").hidden = false;
    renderStatus(error.message, true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setMode("address");
  document
    .querySelectorAll("[data-mode]")
    .forEach((button) =>
      button.addEventListener("click", () => setMode(button.dataset.mode))
    );
  document.getElementById("searchForm").addEventListener("submit", handleSubmit);
});
