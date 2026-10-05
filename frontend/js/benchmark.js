// MRPL Benchmark Service Controller
const Benchmark = {
  async init() {
    await this.fetchBenchmarks();
  },

  async fetchBenchmarks() {
    try {
      const res = await fetch("/api/benchmarks");
      if (!res.ok) throw new Error("Failed to load benchmarks");
      const data = await res.json();
      this.renderBenchmarks(data);
    } catch (err) {
      console.warn("Benchmark fetch error:", err);
    }
  },

  async runBenchmarks() {
    const tbody = document.getElementById("benchmark-tbody");
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--accent-cyan); padding: 20px;">Running synthetic benchmark suite locally across all registered models...</td></tr>';
    }

    try {
      const res = await fetch("/api/benchmarks/run", { method: "POST" });
      if (!res.ok) throw new Error("Failed to run benchmarks");
      const data = await res.json();
      this.renderBenchmarks(data);
      if (window.Registry) Registry.fetchModels();
    } catch (err) {
      alert("Benchmark execution error: " + err.message);
      this.fetchBenchmarks();
    }
  },

  renderBenchmarks(data) {
    const tbody = document.getElementById("benchmark-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const details = data.details || {};
    const keys = Object.keys(details);

    if (keys.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">No benchmark runs recorded yet. Click "Run Local Benchmark Suite" to execute empirical latency and accuracy tests.</td></tr>';
      return;
    }

    keys.forEach(modelName => {
      const item = details[modelName];
      const tr = document.createElement("tr");

      const benchPct = Math.round((item.benchmark_score || 0.8) * 100);
      const accPct = Math.round((item.accuracy || 1.0) * 100);
      const latScorePct = Math.round((item.latency_score || 0.8) * 100);

      tr.innerHTML = `
        <td>
          <strong>${item.display_name || modelName}</strong>
          <div style="font-size: 10px; color: var(--text-code); font-family: var(--font-mono);">${modelName}</div>
        </td>
        <td style="font-family: var(--font-mono);">${item.avg_latency_ms || 0} ms</td>
        <td>
          <span class="score-badge ${latScorePct >= 75 ? 'high' : 'medium'}">${latScorePct}%</span>
        </td>
        <td>
          <span class="score-badge ${accPct >= 80 ? 'high' : 'medium'}">${accPct}%</span>
        </td>
        <td>
          <span class="score-badge ${benchPct >= 80 ? 'high' : benchPct >= 60 ? 'medium' : 'low'}">
            ${benchPct}%
          </span>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }
};

window.Benchmark = Benchmark;
