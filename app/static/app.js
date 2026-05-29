const state = {
  mode: "address",
};

const formatter = new Intl.NumberFormat("ja-JP");

function setText(id, value) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  element.textContent = value;
}

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
  if (!status) {
    return;
  }
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function yen(value) {
  return `¥${formatter.format(value)}`;
}

function meters(value) {
  return `${formatter.format(Math.round(value))}m`;
}

function renderResults(data) {
  const empty = document.getElementById("empty");
  const results = document.getElementById("results");
  if (empty) {
    empty.hidden = true;
  }
  if (results) {
    results.hidden = false;
  }
  setText("avgPrice", yen(data.average_price));
  setText("nearestPrice", yen(data.nearest_price));
  setText("nearestPoint", data.nearest_point);
  setText("stationLabel", data.nearest_station ?? "-");
  setText("distanceLabel", meters(data.nearest_distance_meters));
  const notice = document.getElementById("noticeBanner");
  if (data.notice) {
    if (notice) {
      notice.hidden = false;
      notice.textContent = data.notice;
    }
  } else if (notice) {
    notice.hidden = true;
    notice.textContent = "";
  }

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
  const sampleBody = document.getElementById("sampleBody");
  if (sampleBody) {
    sampleBody.innerHTML = sampleRows;
  }

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
  const trendBody = document.getElementById("trendBody");
  if (trendBody) {
    trendBody.innerHTML = trendRows;
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  renderStatus("検索中です...");

  const payload = {
    mode: state.mode,
    address: document.getElementById("address").value || null,
    latitude: document.getElementById("latitude").value
      ? Number(document.getElementById("latitude").value)
      : null,
    longitude: document.getElementById("longitude").value
      ? Number(document.getElementById("longitude").value)
      : null,
    radius_meters: Number(document.getElementById("radius").value),
    sample_limit: 12,
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
    renderResults(data);
    renderStatus("最新に取得できた年の地価情報を表示しています。");
  } catch (error) {
    const results = document.getElementById("results");
    const empty = document.getElementById("empty");
    const notice = document.getElementById("noticeBanner");
    if (results) {
      results.hidden = true;
    }
    if (empty) {
      empty.hidden = false;
    }
    if (notice) {
      notice.hidden = true;
    }
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
