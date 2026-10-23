const COLORS = {"Min variance": "#10B981", "Equal weight": "#60A5FA", "SPY": "#F59E0B"};
const ASSET_COLORS = ["#F59E0B", "#A78BFA", "#10B981", "#60A5FA", "#FBBF24", "#F472B6"];
const LAYOUT = {
  paper_bgcolor: "#111827", plot_bgcolor: "#111827", font: {color: "#E5E7EB"},
  margin: {l: 50, r: 10, t: 10, b: 40}, legend: {orientation: "h", y: -0.15},
  xaxis: {gridcolor: "#1F2937"}, yaxis: {gridcolor: "#1F2937"},
};
const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";
const num = (v) => v.toFixed(2);

function lines(id, s, yfmt) {
  const traces = Object.keys(s).filter((k) => k !== "dates").map((k) => ({
    x: s.dates, y: s[k], name: k, type: "scatter", mode: "lines", line: {color: COLORS[k], width: 1.6},
  }));
  Plotly.newPlot(id, traces, {...LAYOUT, yaxis: {...LAYOUT.yaxis, tickformat: yfmt}},
    {responsive: true, displayModeBar: false});
}

function table(id, head, rows) {
  const el = document.getElementById(id);
  el.innerHTML = "<thead><tr>" + head.map((h) => `<th scope="col">${h}</th>`).join("") +
    "</tr></thead><tbody>" + rows.map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") +
    "</tr>").join("") + "</tbody>";
}

fetch("data.json").then((r) => r.json()).then((d) => {
  document.getElementById("period").textContent = `${d.period.first} to ${d.period.last}`;
  const m = d.metrics, names = Object.keys(m);
  const rows = [
    ["Total return", "total_return", pct], ["Annualised return", "annualized_return", (v) => pct(v, 2)],
    ["Annualised volatility", "annualized_vol", (v) => pct(v, 2)], ["Sharpe", "sharpe", num],
    ["Sortino", "sortino", num], ["Max drawdown", "max_drawdown", pct], ["Calmar", "calmar", num],
  ];
  table("metrics", ["Metric", ...names], rows.map(([lab, k, f]) => [lab, ...names.map((n) => f(m[n][k]))]));
  lines("growth", d.growth, "$.2f");
  lines("drawdown", d.drawdown, ".0%");
  lines("sharpe", d.rolling_sharpe, ".1f");
  const w = d.mv_weights, assets = Object.keys(w).filter((k) => k !== "dates");
  Plotly.newPlot("weights", assets.map((a, i) => ({
    x: w.dates, y: w[a], name: a, stackgroup: "one", type: "scatter", mode: "lines",
    line: {width: 0.5, color: ASSET_COLORS[i]},
  })), {...LAYOUT, yaxis: {...LAYOUT.yaxis, tickformat: ".0%", range: [0, 1]}},
  {responsive: true, displayModeBar: false});
  const sk = Object.keys(d.stress[0]).filter((k) => !["name", "start_date", "end_date"].includes(k));
  table("stress", ["Episode", "Peak", "Trough", ...sk],
    d.stress.map((r) => [r.name, r.start_date, r.end_date, ...sk.map((k) => r[k].toFixed(1))]));
  table("regime", ["Regime", "Asset", "Days", "Correlation with SPY"],
    d.regime_corr.map((r) => [r.regime, r.other, r.n_days, r.corr.toFixed(4)]));
});
