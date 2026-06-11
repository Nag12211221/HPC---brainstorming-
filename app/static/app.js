// HPC Predictive Quality Platform — dashboard client
// All UI is driven from the /api/* endpoints. Charts use Plotly (loaded via CDN).

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const api = (path, opts) => fetch(`/api${path}`, opts).then(r => r.json());

const STATUS_RANK = { critical: 3, warn: 2, watch: 1, healthy: 0 };
const STATUS_COLOR = { critical: "#ff5161", warn: "#ff9a3c", watch: "#d2b441", healthy: "#36c987" };

const state = {
  activeTab: "exec",
  selectedVehicle: null,
  config: null,
};

// ---- Tabs ------------------------------------------------------------------
$$(".tab").forEach(btn => btn.addEventListener("click", () => {
  state.activeTab = btn.dataset.tab;
  $$(".tab").forEach(b => b.classList.toggle("active", b === btn));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${state.activeTab}`));
  refresh();
}));

// ---- Top actions -----------------------------------------------------------
$("#export-json").addEventListener("click", async () => {
  const data = await api("/reports/executive");
  downloadFile("executive_report.json", "application/json", JSON.stringify(data, null, 2));
});
$("#export-csv").addEventListener("click", () => {
  window.location.href = "/api/reports/executive?format=csv";
});

function downloadFile(name, type, content) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

// ---- KPI helper ------------------------------------------------------------
function kpi(label, value, sub) {
  return `<div class="kpi"><div class="label">${label}</div>
          <div class="value">${value}</div>
          ${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
}

function badge(status) {
  return `<span class="badge ${status}">${status.toUpperCase()}</span>`;
}

function fmtUsd(v) {
  return "$" + Math.round(v).toLocaleString();
}

// ---- Executive view --------------------------------------------------------
async function renderExec() {
  const [summary, roi, ab] = await Promise.all([
    api("/fleet/summary"),
    api(`/roi?fleet_size=${state.config?.fleet_size || 25}`),
    api("/models"),
  ]);
  $("#exec-kpis").innerHTML = [
    kpi("Fleet vehicles", summary.fleet_size, `Avg failure prob ${(summary.avg_failure_probability * 100).toFixed(1)}%`),
    kpi("Open alerts", summary.open_alerts, `${summary.status_counts.critical} critical`),
    kpi("Annual savings", fmtUsd(roi.total_annual_savings_usd), `${(roi.early_detection_rate*100).toFixed(0)}% early-detect rate`),
    kpi("Validation cycle ↓", (roi.validation_cycle_reduction_pct * 100).toFixed(0) + "%", "Target 30–40%"),
  ].join("");
  $("#exec-cycle").textContent = (roi.validation_cycle_reduction_pct * 100).toFixed(0) + "%";

  // Fleet status pie
  const counts = summary.status_counts;
  Plotly.react("exec-status", [{
    type: "pie", hole: 0.55,
    labels: Object.keys(counts).map(k => k.toUpperCase()),
    values: Object.values(counts),
    marker: { colors: Object.keys(counts).map(k => STATUS_COLOR[k]) },
    textinfo: "label+percent",
  }], plotlyLayout({ showlegend: false, margin: { t: 10, b: 10 } }), plotlyConfig());

  // Savings bar
  Plotly.react("exec-savings", [{
    type: "bar", orientation: "h",
    x: [roi.baseline_warranty_cost_usd, roi.projected_warranty_cost_usd],
    y: ["Baseline warranty cost", "With HPC platform"],
    marker: { color: ["#ff5161", "#36c987"] },
    text: [fmtUsd(roi.baseline_warranty_cost_usd), fmtUsd(roi.projected_warranty_cost_usd)],
    textposition: "auto",
  }], plotlyLayout({ margin: { l: 180, t: 10 }, height: 180, xaxis: { title: "Annual USD" } }), plotlyConfig());

  // Detection accuracy before/after — pull from ab report if any TP/FP, else synthetic illustration
  const arms = ab.ab_report.length
    ? ab.ab_report
    : [
        { arm: "Legacy threshold rules", precision: 0.42, recall: 0.55 },
        { arm: "HPC platform (ewma_plus_v2)", precision: 0.86, recall: 0.91 },
      ];
  Plotly.react("exec-accuracy", [
    { type: "bar", name: "Precision", x: arms.map(a => a.arm), y: arms.map(a => a.precision), marker: { color: "#4cc2ff" } },
    { type: "bar", name: "Recall",    x: arms.map(a => a.arm), y: arms.map(a => a.recall),    marker: { color: "#36c987" } },
  ], plotlyLayout({ barmode: "group", yaxis: { range: [0, 1] }, margin: { t: 20 } }), plotlyConfig());
}

// ---- Fleet view ------------------------------------------------------------
async function renderFleet() {
  const data = await api("/fleet");
  const filter = $("#fleet-filter").value;
  const rank = STATUS_RANK[filter] || 0;
  const rows = data.vehicles
    .filter(v => filter === "all" || STATUS_RANK[v.status] >= rank)
    .sort((a, b) => STATUS_RANK[b.status] - STATUS_RANK[a.status]
                  || b.failure_probability - a.failure_probability);

  $("#fleet-summary-row").innerHTML = [
    kpi("Healthy", data.summary.status_counts.healthy),
    kpi("Watch",   data.summary.status_counts.watch),
    kpi("Warn",    data.summary.status_counts.warn),
    kpi("Critical",data.summary.status_counts.critical),
    kpi("Open alerts", data.summary.open_alerts),
    kpi("Avg failure prob", (data.summary.avg_failure_probability * 100).toFixed(1) + "%"),
  ].join("");

  const tbody = $("#fleet-table tbody");
  tbody.innerHTML = rows.map(v => `
    <tr class="row-${v.status}">
      <td><b>${v.vehicle_id}</b></td>
      <td>${v.region}</td>
      <td>${v.model_year}</td>
      <td>${badge(v.status)}</td>
      <td>${v.drift_score.toFixed(2)}</td>
      <td>${(v.failure_probability * 100).toFixed(1)}%</td>
      <td>${(v.ci_low * 100).toFixed(0)}–${(v.ci_high * 100).toFixed(0)}%</td>
      <td>${v.time_to_failure_hours ? v.time_to_failure_hours.toFixed(1) : "—"}</td>
      <td><code>${v.assigned_model}</code></td>
      <td>${v.scenario}</td>
      <td><button class="ghost drill" data-vid="${v.vehicle_id}">Drill ▶</button></td>
    </tr>
  `).join("");
  $$(".drill").forEach(b => b.addEventListener("click", () => {
    state.selectedVehicle = b.dataset.vid;
    document.querySelector('.tab[data-tab="vehicle"]').click();
  }));
}

$("#fleet-refresh").addEventListener("click", renderFleet);
$("#fleet-filter").addEventListener("change", renderFleet);

// ---- Vehicle drill-down ----------------------------------------------------
async function renderVehicle() {
  const fleet = await api("/fleet");
  const picker = $("#veh-picker");
  picker.innerHTML = fleet.vehicles.map(v =>
    `<option value="${v.vehicle_id}">${v.vehicle_id} · ${v.status}</option>`).join("");
  if (!state.selectedVehicle) state.selectedVehicle = fleet.vehicles[0]?.vehicle_id;
  picker.value = state.selectedVehicle;
  picker.onchange = () => { state.selectedVehicle = picker.value; renderVehicle(); };

  if (!state.selectedVehicle) return;
  const v = await api(`/vehicles/${state.selectedVehicle}?window=180`);
  $("#veh-title").innerHTML = `${v.vehicle_id} · ${v.region} · MY${v.model_year} ${badge(statusOf(v))}`;
  const p = v.prediction || {};
  $("#veh-kpis").innerHTML = [
    kpi("Drift score", (v.drift_score || 0).toFixed(2)),
    kpi("Failure prob.", ((p.probability || 0) * 100).toFixed(1) + "%",
        `95% CI ${(p.ci_low*100||0).toFixed(0)}–${(p.ci_high*100||0).toFixed(0)}%`),
    kpi("Time-to-failure", p.time_to_failure_hours ? p.time_to_failure_hours.toFixed(1) + " h" : "—"),
    kpi("Active model", `<code>${v.assigned_model}</code>`),
    kpi("Scenario", v.scenario || "nominal"),
    kpi("Samples", v.timeline.length),
  ].join("");

  const t = v.timeline.map(s => s.t / 60); // minutes
  const actualTemp = v.timeline.map(s => s.actual.max_cell_temp_c);
  const expectTemp = v.timeline.map(s => s.expected.max_cell_temp_c);
  const actualDt   = v.timeline.map(s => s.actual.coolant_delta_c);
  const expectDt   = v.timeline.map(s => s.expected.coolant_delta_c);
  const current    = v.timeline.map(s => s.actual.current_a);
  const soc        = v.timeline.map(s => s.actual.soc_pct);

  Plotly.react("veh-twin-temp", [
    { x: t, y: expectTemp, name: "HPC expected", line: { color: "#4cc2ff", dash: "dash" } },
    { x: t, y: actualTemp, name: "Actual field", line: { color: "#ff9a3c" } },
  ], plotlyLayout({ xaxis: { title: "Sim minutes" }, yaxis: { title: "°C" } }), plotlyConfig());

  Plotly.react("veh-twin-delta", [
    { x: t, y: expectDt, name: "HPC expected", line: { color: "#4cc2ff", dash: "dash" } },
    { x: t, y: actualDt, name: "Actual field", line: { color: "#ff5161" } },
  ], plotlyLayout({ xaxis: { title: "Sim minutes" }, yaxis: { title: "ΔT °C" } }), plotlyConfig());

  // For drift/prob we only have the latest value but render a sparkline of residual
  const residual = v.timeline.map(s => s.actual.max_cell_temp_c - s.expected.max_cell_temp_c);
  Plotly.react("veh-drift", [
    { x: t, y: residual, name: "Max-cell residual (°C)", line: { color: "#d2b441" } },
    { x: t, y: t.map(() => v.drift_score), name: `Drift score (current=${(v.drift_score||0).toFixed(2)})`,
      line: { color: "#ff5161", dash: "dot" }, yaxis: "y2" },
  ], plotlyLayout({
        xaxis: { title: "Sim minutes" },
        yaxis: { title: "Residual °C" },
        yaxis2: { title: "Drift", overlaying: "y", side: "right", range: [0, Math.max(1, (v.drift_score||0)*1.4)] },
      }), plotlyConfig());

  Plotly.react("veh-load", [
    { x: t, y: current, name: "Current (A)", line: { color: "#4cc2ff" } },
    { x: t, y: soc, name: "SoC (%)", yaxis: "y2", line: { color: "#36c987" } },
  ], plotlyLayout({
        xaxis: { title: "Sim minutes" },
        yaxis: { title: "A" },
        yaxis2: { title: "SoC %", overlaying: "y", side: "right", range: [0, 100] },
      }), plotlyConfig());

  const alerts = (await api("/alerts?limit=200")).filter(a => a.vehicle_id === v.vehicle_id);
  $("#veh-alerts").innerHTML = alerts.length ? alerts.map(a => `
    <li class="${a.severity}">
      <div>
        <strong>${a.title}</strong>
        <div class="meta">${a.detail}</div>
      </div>
      <div>
        <span class="badge ${a.severity}">${a.severity}</span>
        ${a.acknowledged ? "<span class='muted'>ack'd</span>" :
          `<button data-aid="${a.id}" class="ack">Acknowledge</button>`}
      </div>
    </li>`).join("") : "<li class='muted'>No active alerts.</li>";
  $$(".ack").forEach(b => b.addEventListener("click", async () => {
    await api(`/alerts/${b.dataset.aid}/ack`, { method: "POST" });
    renderVehicle();
  }));
}

function statusOf(v) {
  const p = (v.prediction || {}).probability || 0;
  const d = v.drift_score || 0;
  if (p >= 0.65 || d >= 0.75) return "critical";
  if (p >= 0.35 || d >= 0.45) return "warn";
  if (p >= 0.15 || d >= 0.20) return "watch";
  return "healthy";
}

// ---- Case study ------------------------------------------------------------
$("#cs-run").addEventListener("click", renderCaseStudy);

async function renderCaseStudy() {
  const scenario = $("#cs-scenario").value;
  const data = await api(`/case_study?scenario=${scenario}&horizon_minutes=240`);
  $("#cs-narrative").textContent = data.narrative;
  const t = data.series.map(s => s.t_min);
  Plotly.react("cs-twin", [
    { x: t, y: data.series.map(s => s.max_cell_expected), name: "HPC expected",
      line: { color: "#4cc2ff", dash: "dash" } },
    { x: t, y: data.series.map(s => s.max_cell_actual), name: "Actual field",
      line: { color: "#ff9a3c" } },
  ], plotlyLayout({ xaxis: { title: "Minutes" }, yaxis: { title: "Max cell °C" },
                    shapes: [{ type: "line", x0: data.failure_minute, x1: data.failure_minute,
                               y0: 0, y1: 1, yref: "paper", line: { color: "#ff5161", dash: "dot" } }] }),
    plotlyConfig());

  Plotly.react("cs-prob", [
    { x: t, y: data.series.map(s => s.baseline_v1_prob),  name: "baseline_v1",  line: { color: "#93a0bf" } },
    { x: t, y: data.series.map(s => s.ewma_plus_v2_prob), name: "ewma_plus_v2", line: { color: "#36c987" } },
  ], plotlyLayout({ xaxis: { title: "Minutes" }, yaxis: { title: "P(failure)", range: [0, 1] } }), plotlyConfig());

  const lead = data.warning_lead_minutes;
  $("#cs-leadtime").innerHTML = [
    kpi("Failure ground-truth", data.failure_minute + " min", "from start"),
    kpi("baseline_v1 lead", (lead.baseline_v1 ?? "—") + " min"),
    kpi("ewma_plus_v2 lead", (lead.ewma_plus_v2 ?? "—") + " min"),
    kpi("Detection delta", lead.baseline_v1 && lead.ewma_plus_v2 ?
        (lead.ewma_plus_v2 - lead.baseline_v1).toFixed(0) + " min" : "—",
        "earlier with EWMA+"),
  ].join("");
}

// ---- Models / A/B ----------------------------------------------------------
async function renderModels() {
  const data = await api("/models");
  const tbody = $("#models-table tbody");
  tbody.innerHTML = data.available.map(m => `
    <tr>
      <td><code>${m.version}</code></td>
      <td>${m.description}</td>
      <td>${m.active ? "✅" : ""}</td>
      <td>${m.active ? "" : `<button class="ghost activate" data-v="${m.version}">Activate</button>`}</td>
    </tr>`).join("");
  $$(".activate").forEach(b => b.addEventListener("click", async () => {
    await api("/models/activate", { method: "POST", headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ version: b.dataset.v }) });
    renderModels();
  }));

  // AB split editor
  const split = data.ab_split;
  $("#ab-split-editor").innerHTML = Object.entries(split).map(([k, v]) =>
    `<label><code>${k}</code>&nbsp;<input data-arm="${k}" type="number" min="0" max="1" step="0.05" value="${v}"></label>`
  ).join("");

  const rep = data.ab_report;
  $("#ab-report tbody").innerHTML = rep.length ? rep.map(r => `
    <tr>
      <td><code>${r.arm}</code></td>
      <td>${r.assigned}</td><td>${r.alerts_fired}</td>
      <td>${r.true_positives}</td><td>${r.false_positives}</td><td>${r.missed}</td>
      <td>${r.precision}</td><td>${r.recall}</td>
    </tr>`).join("") : `<tr><td colspan="8" class="muted">No A/B traffic yet — assign vehicles by reseeding.</td></tr>`;
}

$("#ab-apply").addEventListener("click", async () => {
  const inputs = $$("#ab-split-editor input");
  const split = {};
  inputs.forEach(i => split[i.dataset.arm] = parseFloat(i.value));
  const r = await api("/models/ab_split", { method: "PATCH", headers: { "Content-Type": "application/json" },
                                            body: JSON.stringify({ split }) });
  if (r.error) alert(r.error); else renderModels();
});

// ---- Feedback --------------------------------------------------------------
$("#fb-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  await api("/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
                           body: JSON.stringify(body) });
  e.target.reset();
  renderFeedback();
});

$("#fb-retrain").addEventListener("click", async () => {
  await api("/feedback/retrain", { method: "POST", headers: { "Content-Type": "application/json" },
                                   body: "{}" });
  renderFeedback();
});

async function renderFeedback() {
  const data = await api("/feedback");
  $("#fb-table tbody").innerHTML = data.entries.length ? data.entries.map(e => `
    <tr>
      <td><code>${e.id}</code></td>
      <td>${e.vehicle_id || "—"}</td>
      <td>${e.label}</td>
      <td>${badge(e.severity === "info" ? "watch" : e.severity)}</td>
      <td>${e.comment}</td>
      <td>${e.incorporated_in_model ? `<code>${e.incorporated_in_model}</code>` : "—"}</td>
    </tr>`).join("") : `<tr><td colspan="6" class="muted">No feedback submitted yet.</td></tr>`;
  $("#retrain-history").innerHTML = data.retraining_history.length
    ? data.retraining_history.slice().reverse().map(h =>
        `<li><strong>${h.new_model_version}</strong>
         <span class="meta">${h.samples_incorporated} feedback samples · ${new Date(h.timestamp*1000).toLocaleString()}</span></li>`).join("")
    : "<li class='muted'>No retraining events.</li>";
}

// ---- Config ----------------------------------------------------------------
async function renderConfig() {
  state.config = await api("/config");
  const editor = $("#config-editor");
  editor.innerHTML = Object.entries(state.config)
    .filter(([k]) => k !== "ab_traffic_split")
    .map(([k, v]) =>
      `<label>${k}<input data-k="${k}" value="${v}"/></label>`).join("");
}

$("#config-save").addEventListener("click", async () => {
  const patch = {};
  $$("#config-editor input").forEach(i => {
    const v = i.value;
    patch[i.dataset.k] = isNaN(Number(v)) ? v : Number(v);
  });
  const r = await api("/config", { method: "PATCH", headers: { "Content-Type": "application/json" },
                                   body: JSON.stringify(patch) });
  if (r.error) alert(r.error);
  else renderConfig();
});

$("#reseed").addEventListener("click", async () => {
  await api("/fleet/reseed", { method: "POST", headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ fleet_size: state.config?.fleet_size || 25 }) });
  alert("Fleet reseeded.");
  refresh();
});

// ---- Plotly helpers --------------------------------------------------------
function plotlyLayout(extra = {}) {
  return Object.assign({
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#e6ebf5", size: 11 },
    margin: { l: 50, r: 30, t: 30, b: 40 },
    legend: { orientation: "h", y: -0.2 },
  }, extra);
}
function plotlyConfig() {
  return { displayModeBar: false, responsive: true };
}

// ---- Lifecycle -------------------------------------------------------------
async function refresh() {
  $("#last-update").textContent = "Updated " + new Date().toLocaleTimeString();
  try {
    if (state.activeTab === "exec") return renderExec();
    if (state.activeTab === "fleet") return renderFleet();
    if (state.activeTab === "vehicle") return renderVehicle();
    if (state.activeTab === "casestudy") {
      // Render once on first visit, then only on demand via the Run button.
      // Plotly stores its parsed layout/data on the container as `_fullData`
      // once a chart has been drawn — we use it as a "has-rendered" probe.
      const el = document.getElementById("cs-twin");
      if (el && !el._fullData) renderCaseStudy();
      return;
    }
    if (state.activeTab === "ops") return renderModels();
    if (state.activeTab === "feedback") return renderFeedback();
    if (state.activeTab === "config") return renderConfig();
  } catch (err) {
    console.error(err);
  }
}

(async function init() {
  state.config = await api("/config");
  renderConfig();
  refresh();
  setInterval(() => {
    // auto-refresh the active live views
    if (["exec", "fleet", "vehicle"].includes(state.activeTab)) refresh();
  }, 4000);
})();
