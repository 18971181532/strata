/* Strata dashboard — vanilla JS, zero dependencies, Canvas 2D. */
"use strict";

const CATEGORY_COLORS = {
  code: "#58a6ff", web: "#bc8cff", data: "#39c5cf", config: "#79c0ff",
  docs: "#3fb950", image: "#d29922", audio: "#f0883e", video: "#db61a2",
  archive: "#e3b341", binary: "#f85149", font: "#a5d6ff", dir: "#2d333b",
  other: "#6e7d8c",
};
const PALETTE = ["#58a6ff", "#3fb950", "#bc8cff", "#d29922", "#39c5cf",
                 "#f85149", "#f0883e", "#7ee787", "#79c0ff", "#d2a8ff",
                 "#56d4dd", "#e3b341", "#ff7b72", "#a5d6ff"];

const state = {
  report: null,
  currentPath: "",
  depth: 2,
  rects: [],
};

/* ---------------- helpers ---------------- */
async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
function humanSize(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (Math.abs(bytes) >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return i === 0 ? bytes + "B" : bytes.toFixed(1) + units[i];
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width || canvas.width;
  const h = rect.height || canvas.height;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}
function catColor(category) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.other;
}
function shade(hex, amt) {
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  r = Math.max(0, Math.min(255, r + amt));
  g = Math.max(0, Math.min(255, g + amt));
  b = Math.max(0, Math.min(255, b + amt));
  return `rgb(${r},${g},${b})`;
}

/* ---------------- tabs ---------------- */
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
    renderActive();
  });
});
function activeTab() {
  return document.querySelector(".tab.active").dataset.tab;
}
function renderActive() {
  const t = activeTab();
  if (t === "treemap") { renderTreemapCards(); drawTreemap(); }
  if (t === "sunburst") drawSunburst();
  if (t === "overview") renderOverview();
  if (t === "duplicates") renderDuplicates();
  if (t === "cleanup") renderCleanup();
}

/* ---------------- breadcrumb ---------------- */
function renderBreadcrumb() {
  const parts = state.currentPath ? state.currentPath.split("/") : [];
  const rootName = state.report ? state.report.root_name : "root";
  let html = `<a data-path="">${escapeHtml(rootName)}</a>`;
  let acc = "";
  parts.forEach((p, i) => {
    acc = acc ? acc + "/" + p : p;
    html += " / ";
    if (i === parts.length - 1) html += escapeHtml(p);
    else html += `<a data-path="${escapeHtml(acc)}">${escapeHtml(p)}</a>`;
  });
  const bc = document.getElementById("breadcrumb");
  bc.innerHTML = html;
  bc.querySelectorAll("a").forEach(a =>
    a.addEventListener("click", () => navigate(a.dataset.path)));
}

/* ---------------- treemap ---------------- */
async function loadTreemap(path) {
  const data = await api(`/api/treemap?depth=${state.depth}&path=${encodeURIComponent(path)}`);
  state.rects = data.rects;
  state.currentPath = data.path;
  renderBreadcrumb();
  renderTreemapCards();
  drawTreemap();
}

function drawTreemap() {
  const canvas = document.getElementById("treemap-canvas");
  const { ctx, w, h } = setupCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  const rects = state.rects;
  if (!rects || !rects.length) return;
  const pad = 2;
  ctx.font = "12px monospace";
  rects.forEach(r => {
    const x = (r.x / 1000) * w, y = (r.y / 1000) * h;
    const rw = (r.w / 1000) * w, rh = (r.h / 1000) * h;
    const base = r.is_dir ? CATEGORY_COLORS.dir : catColor(r.category);
    const depthShift = r.is_dir ? 0 : (r.depth % 3) * 12;
    ctx.fillStyle = r.is_dir ? shade(base, 12 + depthShift) : shade(base, depthShift - 6);
    ctx.fillRect(x + pad, y + pad, Math.max(rw - pad * 2, 1), Math.max(rh - pad * 2, 1));
    ctx.strokeStyle = "rgba(13,16,23,.8)";
    ctx.lineWidth = 1;
    ctx.strokeRect(x + pad, y + pad, Math.max(rw - pad * 2, 1), Math.max(rh - pad * 2, 1));
    // Label if the tile is big enough.
    if (rw > 60 && rh > 26) {
      ctx.fillStyle = r.is_dir ? "#93a1b0" : "#e6edf3";
      const label = r.name.length > 20 ? r.name.slice(0, 19) + "…" : r.name;
      ctx.fillText(label, x + 6, y + 16);
      if (rw > 110 && rh > 46) {
        ctx.fillStyle = "rgba(230,237,243,.65)";
        ctx.fillText(humanSize(r.size), x + 6, y + 32);
      }
    }
  });
}

function treemapHit(mx, my, w, h) {
  for (const r of state.rects) {
    const x = (r.x / 1000) * w, y = (r.y / 1000) * h;
    const rw = (r.w / 1000) * w, rh = (r.h / 1000) * h;
    if (mx >= x && mx <= x + rw && my >= y && my <= y + rh) return r;
  }
  return null;
}

function treemapCards() {
  const node = state.rects && state.rects.length;
  return node;
}

function renderTreemapCards() {
  if (!state.report) return;
  const r = state.report;
  const el = document.getElementById("treemap-cards");
  el.innerHTML = [
    ["Current", state.currentPath ? state.currentPath.split("/").pop() : r.root_name, "accent"],
    ["Total Size", humanSize(r.total_size), ""],
    ["Files", r.file_count.toLocaleString(), "green"],
    ["Duplicate Waste", humanSize(r.duplicate_waste),
     r.duplicate_waste > 0 ? "danger" : ""],
  ].map(c => `<div class="card"><div class="card-label">${c[0]}</div>
    <div class="card-value ${c[2]}" style="font-size:${c[0]==='Current'?'18px':''}">${escapeHtml(c[1])}</div></div>`).join("");
}

function navigate(path) {
  loadTreemap(path);
}

/* ---------------- sunburst ---------------- */
let sunburstSectors = [];
async function drawSunburst() {
  const data = await api("/api/sunburst?depth=3");
  sunburstSectors = data.sectors;
  const canvas = document.getElementById("sunburst-canvas");
  const { ctx, w, h } = setupCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  const cx = w / 2, cy = h / 2;
  const scale = Math.min(w, h) / 2.2;
  sunburstSectors.forEach(s => {
    const r0 = s.r0 * scale, r1 = s.r1 * scale;
    ctx.beginPath();
    ctx.arc(cx, cy, r1, s.a0, s.a1);
    ctx.arc(cx, cy, r0, s.a1, s.a0, true);
    ctx.closePath();
    const base = s.is_dir ? CATEGORY_COLORS.dir : catColor(s.category);
    ctx.fillStyle = shade(base, (s.depth % 3) * 10 - 6);
    ctx.fill();
    ctx.strokeStyle = "rgba(13,16,23,.85)";
    ctx.stroke();
  });
  // center label
  ctx.fillStyle = "#e6edf3";
  ctx.font = "bold 20px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(humanSize(data.size), cx, cy);
  ctx.fillStyle = "#64748b";
  ctx.font = "12px sans-serif";
  ctx.fillText(escapeHtml(data.name).slice(0, 24), cx, cy + 18);
}

/* ---------------- generic charts ---------------- */
function barChart(canvas, items, opts = {}) {
  const { ctx, w, h } = setupCanvas(canvas);
  if (!items.length) return;
  const padL = opts.padL || 150, padB = 30, padT = 10, padR = 58;
  const max = Math.max(...items.map(d => d[1])) || 1;
  const rowH = (h - padT - padB) / items.length;
  const barW = w - padL - padR;
  ctx.font = "12px monospace";
  items.forEach((d, i) => {
    const y = padT + i * rowH;
    const bw = (d[1] / max) * barW;
    ctx.fillStyle = (opts.colors && opts.colors[i]) || PALETTE[i % PALETTE.length];
    ctx.fillRect(padL, y + 4, Math.max(bw, 2), rowH - 8);
    ctx.fillStyle = "#93a1b0"; ctx.textAlign = "right";
    ctx.fillText(d[0].slice(0, 22), padL - 10, y + rowH / 2 + 4);
    ctx.fillStyle = "#e6edf3"; ctx.textAlign = "left";
    ctx.fillText(opts.fmt ? opts.fmt(d[1]) : String(d[1]), padL + bw + 6, y + rowH / 2 + 4);
  });
}

/* ---------------- overview ---------------- */
function renderOverview() {
  if (!state.report) return;
  const r = state.report;
  const cards = [
    ["Total Size", humanSize(r.total_size), "accent"],
    ["Files", r.file_count.toLocaleString(), "green"],
    ["Directories", r.dir_count.toLocaleString(), "purple"],
    ["Categories", Object.keys(r.category_sizes).length, ""],
    ["Duplicates", r.duplicates.length, r.duplicate_waste ? "danger" : ""],
    ["Scan Time", r.scan_time.toFixed(2) + "s", ""],
  ];
  document.getElementById("stats-cards").innerHTML = cards.map(c =>
    `<div class="card"><div class="card-label">${c[0]}</div>
     <div class="card-value ${c[2]}">${escapeHtml(c[1])}</div></div>`).join("");

  const catItems = Object.entries(r.category_sizes).sort((a, b) => b[1] - a[1]);
  const catColors = catItems.map(([c]) => catColor(c));
  barChart(document.getElementById("category-canvas"), catItems,
    { colors: catColors, fmt: humanSize });

  const ageItems = ["last_7_days", "last_30_days", "last_90_days",
    "last_180_days", "last_year", "over_a_year"]
    .map(k => [k.replace(/_/g, " "), r.age_buckets[k] || 0]);
  barChart(document.getElementById("age-canvas"), ageItems,
    { padL: 130, colors: ["#3fb950", "#58a6ff", "#39c5cf", "#d29922", "#f0883e", "#f85149"] });

  const sizeOrder = ["<1KB", "1-10KB", "10-100KB", "100KB-1MB", "1-10MB",
    "10-100MB", "100MB-1GB", ">1GB"];
  const sizeItems = sizeOrder.map(k => [k, r.size_buckets[k] || 0]);
  barChart(document.getElementById("size-canvas"), sizeItems, { padL: 110 });

  const tbody = document.querySelector("#big-table tbody");
  tbody.innerHTML = r.largest_files.slice(0, 20).map((f, i) =>
    `<tr><td>${i + 1}</td><td class="size">${humanSize(f.size)}</td>
     <td>${f.extension || "—"}</td><td>${escapeHtml(f.category)}</td>
     <td>${escapeHtml(f.path)}</td></tr>`).join("");
}

/* ---------------- duplicates ---------------- */
function renderDuplicates() {
  if (!state.report) return;
  const groups = state.report.duplicates || [];
  const cards = document.getElementById("dupe-cards");
  cards.innerHTML = [
    ["Duplicate Groups", groups.length, groups.length ? "danger" : "green"],
    ["Wasted Space", humanSize(state.report.duplicate_waste),
     state.report.duplicate_waste ? "danger" : ""],
    ["Extra Copies", groups.reduce((s, g) => s + g.count - 1, 0), "warn"],
  ].map(c => `<div class="card"><div class="card-label">${c[0]}</div>
    <div class="card-value ${c[2]}">${c[1]}</div></div>`).join("");

  const list = document.getElementById("dupe-list");
  if (!groups.length) {
    list.innerHTML = '<div class="empty-note">No duplicate files found. 🎉</div>';
    return;
  }
  list.innerHTML = groups.map(g => `
    <div class="dupe-group">
      <div class="dupe-head">
        <span><strong>${g.count} × ${humanSize(g.size)}</strong> copies</span>
        <span class="dupe-waste">wastes ${humanSize(g.wasted_bytes)}</span>
      </div>
      <ul class="dupe-paths">${g.paths.map(p => `<li>${escapeHtml(p)}</li>`).join("")}</ul>
    </div>`).join("");
}

/* ---------------- cleanup ---------------- */
async function renderCleanup() {
  const data = await api("/api/recommendations?threshold_mb=50");
  const recs = data.recommendations;
  const byKind = {};
  recs.forEach(r => { byKind[r.kind] = (byKind[r.kind] || 0) + 1; });
  document.getElementById("clean-cards").innerHTML = [
    ["Recommendations", recs.length, "accent"],
    ["Est. Reclaimable", humanSize(data.estimated_reclaimable),
     data.estimated_reclaimable ? "green" : ""],
    ["Duplicates", byKind.duplicate || 0, "danger"],
    ["Caches / Deps", (byKind.cache || 0) + (byKind.dev_dir || 0), "warn"],
  ].map(c => `<div class="card"><div class="card-label">${c[0]}</div>
    <div class="card-value ${c[2]}">${c[1]}</div></div>`).join("");

  const tbody = document.querySelector("#clean-table tbody");
  if (!recs.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-note">Nothing to clean.</td></tr>';
    return;
  }
  tbody.innerHTML = recs.slice(0, 60).map(r => `
    <tr>
      <td class="nowrap"><span class="kind-badge kind-${r.kind}">${escapeHtml(r.kind)}</span></td>
      <td class="size">${r.reclaimable ? humanSize(r.reclaimable) : "—"}</td>
      <td class="nowrap"><span class="conf-wrap"><span class="conf-bar"><span class="conf-fill" style="width:${Math.round(r.confidence * 100)}%"></span></span>${Math.round(r.confidence * 100)}%</span></td>
      <td><strong>${escapeHtml(r.path)}</strong><br>${escapeHtml(r.reason)}</td>
    </tr>`).join("");
}

/* ---------------- canvas interaction ---------------- */
function bindTreemapCanvas() {
  const canvas = document.getElementById("treemap-canvas");
  const popover = document.getElementById("info-popover");
  canvas.addEventListener("mousemove", e => {
    const rect = canvas.getBoundingClientRect();
    const hit = treemapHit(e.clientX - rect.left, e.clientY - rect.top,
                           rect.width, rect.height);
    if (!hit) { popover.classList.add("hidden"); canvas.style.cursor = "default"; return; }
    canvas.style.cursor = "pointer";
    popover.innerHTML = `<div class="pv-name">${escapeHtml(hit.path)}</div>
      <div class="pv-size">${humanSize(hit.size)} · ${escapeHtml(hit.category)}</div>
      <div>${hit.is_dir ? "click to drill in" : "file"}</div>`;
    popover.style.left = Math.min(e.clientX + 14, window.innerWidth - 380) + "px";
    popover.style.top = (e.clientY + 14) + "px";
    popover.classList.remove("hidden");
    document.getElementById("treemap-hover").textContent =
      hit.path + " — " + humanSize(hit.size);
  });
  canvas.addEventListener("mouseleave", () => popover.classList.add("hidden"));
  canvas.addEventListener("click", e => {
    const rect = canvas.getBoundingClientRect();
    const hit = treemapHit(e.clientX - rect.left, e.clientY - rect.top,
                           rect.width, rect.height);
    if (hit && hit.is_dir) navigate(hit.path);
  });
}

const sunCanvas = document.getElementById("sunburst-canvas");
sunCanvas.addEventListener("mousemove", e => {
  const popover = document.getElementById("info-popover");
  const rect = sunCanvas.getBoundingClientRect();
  const cx = rect.width / 2, cy = rect.height / 2;
  const dx = e.clientX - rect.left - cx, dy = e.clientY - rect.top - cy;
  const radius = Math.sqrt(dx * dx + dy * dy);
  const scale = Math.min(rect.width, rect.height) / 2.2;
  let angle = Math.atan2(dy, dx);
  if (angle < 0) angle += Math.PI * 2;
  const hit = sunburstSectors.find(s =>
    radius >= s.r0 * scale && radius <= s.r1 * scale &&
    angle >= s.a0 && angle <= s.a1);
  if (!hit) { popover.classList.add("hidden"); return; }
  popover.innerHTML = `<div class="pv-name">${escapeHtml(hit.path)}</div>
    <div class="pv-size">${humanSize(hit.size)}</div>`;
  popover.style.left = Math.min(e.clientX + 14, window.innerWidth - 380) + "px";
  popover.style.top = (e.clientY + 14) + "px";
  popover.classList.remove("hidden");
  document.getElementById("sunburst-hover").textContent =
    hit.path + " — " + humanSize(hit.size);
});
sunCanvas.addEventListener("mouseleave", () =>
  document.getElementById("info-popover").classList.add("hidden"));

document.getElementById("depth-select").addEventListener("change", e => {
  state.depth = parseInt(e.target.value, 10);
  loadTreemap(state.currentPath);
});
document.getElementById("refresh-btn").addEventListener("click", async () => {
  const btn = document.getElementById("refresh-btn");
  btn.textContent = "…";
  state.report = await api("/api/refresh");
  btn.textContent = "↻ Rescan";
  await loadTreemap("");
  renderActive();
});
window.addEventListener("resize", () => { if (activeTab() === "treemap") drawTreemap(); });

/* ---------------- init ---------------- */
(async function init() {
  state.report = await api("/api/report");
  bindTreemapCanvas();
  await loadTreemap("");
  renderTreemapCards();
})();
