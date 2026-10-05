// MRPL Sovereign AI Workbench — Main App Controller & Navigation
const App = {
  init() {
    this.setupTabNavigation();
    if (window.TelemetryManager) TelemetryManager.init();
    if (window.Registry) Registry.init();
    if (window.Benchmark) Benchmark.init();
    if (window.Workbench) Workbench.init();
    if (window.ActivityHistory) ActivityHistory.init();
    if (window.TraceVisualizer) TraceVisualizer.init();
    if (window.AuditManager) AuditManager.init();
    if (window.SovereigntyManager) SovereigntyManager.init();
    if (window.RAGManager) RAGManager.init();
    if (window.FormulaManager) FormulaManager.init();
    if (window.PIDManager) PIDManager.init();
    if (window.IntegrityManager) IntegrityManager.init();
    if (window.AssetRegistryManager) AssetRegistryManager.init();
  },

  setupTabNavigation() {
    const tabButtons = document.querySelectorAll(".nav-item-btn, .nav-tab-btn, .nav-item");
    tabButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const targetTab = btn.getAttribute("data-tab");
        if (targetTab) this.switchTab(targetTab);
      });
    });
  },

  switchTab(tabId) {
    if (!tabId) return;

    // Update active nav button
    document.querySelectorAll(".nav-item-btn, .nav-tab-btn, .nav-item").forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-tab") === tabId);
    });

    // Update active section
    document.querySelectorAll(".tab-section-content, .tab-section").forEach(sec => {
      sec.classList.toggle("active", sec.id === `tab-${tabId}`);
    });

    // Lazy loads or updates on tab switch
    if (tabId === "asset-registry" && window.AssetRegistryManager) {
      AssetRegistryManager.init();
    } else if (tabId === "integrity" && window.IntegrityManager) {
      IntegrityManager.onTabActivated();
    } else if (tabId === "trace" && window.TraceVisualizer) {
      if (!TraceVisualizer.currentTraceData) {
        TraceVisualizer.runDirectTrace();
      }
    } else if (tabId === "registry" && window.Registry) {
      Registry.fetchModels();
    } else if (tabId === "rag" && window.RAGManager) {
      RAGManager.init();
    } else if (tabId === "formulas" && window.FormulaManager) {
      FormulaManager.init();
    } else if (tabId === "pid" && window.PIDManager) {
      PIDManager.init();
    } else if (tabId === "verification" && window.Workbench) {
      Workbench.openVerificationWorkspace();
    } else if (tabId === "inspection" && window.InspectionManager) {
      InspectionManager.analyzeCurrent();
    } else if (tabId === "hardware" && window.TelemetryManager) {
      TelemetryManager.fetchTelemetry();
      if (window.Benchmark) Benchmark.fetchBenchmarks();
    } else if (tabId === "audit" && window.AuditManager) {
      AuditManager.fetchTraces();
    } else if (tabId === "sovereignty" && window.SovereigntyManager) {
      SovereigntyManager.fetchStatus();
    }
  }
};

// Audit Trail Manager
const AuditManager = {
  init() {
    this.fetchTraces();
  },

  async fetchTraces() {
    try {
      const res = await fetch("/api/trace/history");
      if (!res.ok) throw new Error("Failed to load audit traces");
      const data = await res.json();
      this.renderTraces(data.traces || []);
    } catch (err) {
      console.warn("Audit load error:", err);
    }
  },

  renderTraces(traces) {
    const tbody = document.getElementById("audit-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (traces.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">No operational traces recorded yet.</td></tr>';
      return;
    }

    traces.forEach(t => {
      const tr = document.createElement("tr");
      const r = (t.risk || "medium").toLowerCase();
      const st = t.verification_status || "SUPPORTED";

      tr.innerHTML = `
        <td style="font-family: var(--font-mono); color: var(--accent-cyan); font-weight: 700;">${t.request_id}</td>
        <td>${(t.task_type || "engineering_task").replace(/_/g, " ")}</td>
        <td><span class="preset-tag ${r}">${r.toUpperCase()}</span></td>
        <td><strong>${t.primary_model}</strong>${t.is_fallback ? ' <span style="font-size:9px; color:var(--accent-ruby);">(FALLBACK)</span>' : ''}</td>
        <td>${t.verifier_model || '<span style="color: var(--text-muted);">None</span>'}</td>
        <td><span class="status-tag ${st === 'SUPPORTED' ? 'healthy' : st === 'CONTRADICTED' ? 'resource_limited' : 'degraded'}">${st}</span></td>
        <td>${t.human_approval_state || 'NOT_REQUIRED'}</td>
        <td style="font-family: var(--font-mono);">${t.total_latency_ms || 0} ms</td>
      `;
      tbody.appendChild(tr);
    });
  }
};

window.App = App;
window.AuditManager = AuditManager;

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  App.init();
});
