(function () {
  const sensorSel = document.getElementById("sensor");
  const windowSel = document.getElementById("window");
  const ctx = document.getElementById("chart");
  let chart;

  async function load() {
    const sid = sensorSel.value;
    const win = windowSel.value;
    const res = await fetch(`/api/timeseries?sensor_id=${sid}&window=${win}`);
    if (!res.ok) return;
    const data = await res.json();
    const labels = data.points.map((p) => p.time.slice(5, 16).replace("T", " "));
    const values = data.points.map((p) => p.value);
    const datasets = [{ label: `${data.metric} (${data.unit})`, data: values, borderColor: "#f0883e", tension: 0.2, pointRadius: 0 }];
    for (const [key, color] of [["min", "#f85149"], ["max", "#f85149"]]) {
      const lim = data.limits[key];
      if (lim !== null) datasets.push({ label: `${key} limit`, data: values.map(() => lim), borderColor: color, borderDash: [6, 4], pointRadius: 0 });
    }
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: { responsive: true, plugins: { legend: { labels: { color: "#e6edf3" } } }, scales: { x: { ticks: { color: "#8b98a5" } }, y: { ticks: { color: "#8b98a5" } } } },
    });
  }

  sensorSel.addEventListener("change", load);
  windowSel.addEventListener("change", load);
  load();
})();
