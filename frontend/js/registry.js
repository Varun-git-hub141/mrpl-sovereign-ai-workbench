// MRPL Model Registry Dashboard & Tuning Controller
const Registry = {
  models: [],
  currentOverrideModel: null,

  async init() {
    await this.fetchModels();
  },

  async fetchModels() {
    try {
      const res = await fetch("/api/registry/models");
      if (!res.ok) throw new Error("Failed to fetch models");
      const data = await res.json();
      this.models = data.models || [];
      this.renderModelGrid();
    } catch (err) {
      console.error("Registry load error:", err);
    }
  },

  async refreshModels() {
    const grid = document.getElementById("registry-model-grid");
    if (grid) grid.innerHTML = '<div style="color: var(--accent-cyan); padding: 40px; text-align: center;">Rescanning local Ollama instance (127.0.0.1:11434)...</div>';
    
    try {
      const res = await fetch("/api/registry/refresh", { method: "POST" });
      const data = await res.json();
      this.models = data.models || [];
      this.renderModelGrid();
      if (window.TelemetryManager) TelemetryManager.fetchTelemetry();
    } catch (err) {
      alert("Failed to refresh Ollama registry: " + err.message);
      this.fetchModels();
    }
  },

  renderModelGrid() {
    const grid = document.getElementById("registry-model-grid");
    if (!grid) return;
    grid.innerHTML = "";

    if (this.models.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
          No models currently registered. Ensure local Ollama is running and click "Rescan Local Ollama".
        </div>
      `;
      return;
    }

    this.models.forEach(model => {
      const card = document.createElement("div");
      card.className = "model-card";

      const caps = model.capabilities || {};
      const hw = model.hardware || {};
      const perf = model.performance || {};
      const healthStatus = (model.health || "healthy").toLowerCase();

      // Capability dimensions list with provenance sources
      const capDims = [
        { key: "reasoning", label: "Reasoning" },
        { key: "coding", label: "Coding" },
        { key: "vision", label: "Vision" },
        { key: "document_understanding", label: "Doc Understanding" },
        { key: "mathematics", label: "Math" },
        { key: "tool_use", label: "Tool Use" },
      ];

      let capRowsHtml = "";
      capDims.forEach(d => {
        let score = 0.5;
        let source = "unknown";
        if (typeof caps[d.key] === "number") {
          score = caps[d.key];
        } else if (caps[d.key] && typeof caps[d.key].score === "number") {
          score = caps[d.key].score;
          source = caps[d.key].source || "unknown";
        }

        const pct = Math.round(score * 100);
        let srcTag = `<span style="font-size: 8px; color: var(--text-muted); text-transform: uppercase;">[${source}]</span>`;
        if (source === "manual_override") {
          srcTag = `<span style="font-size: 8px; color: var(--accent-amber); font-weight: 700;">[OVERRIDE]</span>`;
        } else if (source === "probe") {
          srcTag = `<span style="font-size: 8px; color: var(--accent-cyan); font-weight: 700;">[PROBE]</span>`;
        }

        capRowsHtml += `
          <div style="display: flex; flex-direction: column; gap: 2px;">
            <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-secondary);">
              <span>${d.label} ${srcTag}</span>
              <strong style="font-family: var(--font-mono); color: var(--text-primary);">${pct}%</strong>
            </div>
            <div class="bar-track" style="height: 4px;">
              <div class="bar-fill cyan" style="width: ${pct}%;"></div>
            </div>
          </div>
        `;
      });

      card.innerHTML = `
        <div class="model-card-top">
          <div class="model-card-title">
            <h3>${model.display_name || model.ollama_name}</h3>
            <div class="model-stable-id">${model.id} • ${model.ollama_name}</div>
          </div>
          <span class="status-tag ${healthStatus}">${healthStatus.replace('_', ' ')}</span>
        </div>

        <div class="model-specs-row">
          <span class="spec-chip">Family: ${model.family || 'qwen'}</span>
          <span class="spec-chip">Params: ${model.parameter_size || '3B'}</span>
          <span class="spec-chip">Quant: ${model.quantization || 'Q4_K_M'}</span>
          <span class="spec-chip">Ctx: ${(model.context_length || 32768).toLocaleString()}</span>
        </div>

        <div style="background: var(--bg-secondary); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px; display: flex; flex-direction: column; gap: 8px;">
          <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">Capability Provenance Vector</div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            ${capRowsHtml}
          </div>
        </div>

        <div style="background: rgba(22, 163, 74, 0.08); border: 1px solid rgba(22, 163, 74, 0.25); border-radius: var(--radius-sm); padding: 8px 10px; font-size: 10.5px; font-family: var(--font-mono);">
          <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
            <span style="color: #64748b;">LOCATION:</span>
            <strong style="color: #15803d;">LOCAL (Ollama)</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
            <span style="color: #64748b;">ENDPOINT:</span>
            <strong style="color: #0284c7;">127.0.0.1:11434</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
            <span style="color: #64748b;">DOWNLOADED:</span>
            <strong style="color: #15803d;">LOCAL</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
            <span style="color: #64748b;">EXTERNAL PROVIDER:</span>
            <strong style="color: #15803d;">NONE</strong>
          </div>
          <div style="display: flex; justify-content: space-between; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 2px;">
            <span style="color: #64748b;">DIGEST:</span>
            <span style="color: #475569; font-size: 9.5px;" title="${model.digest || ''}">${model.digest ? model.digest.slice(0, 14) + '...' : 'Local runtime model'}</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; font-size: 11px; font-family: var(--font-mono); background: rgba(0,0,0,0.2); padding: 8px; border-radius: var(--radius-sm);">
          <div>
            <div style="color: var(--text-muted); font-size: 9px;">EST. VRAM</div>
            <div style="color: var(--text-primary); font-weight: 700;">${hw.estimated_vram_gb || 3.5} GB</div>
          </div>
          <div>
            <div style="color: var(--text-muted); font-size: 9px;">BENCHMARK</div>
            <div style="color: var(--accent-cyan); font-weight: 700;">${Math.round((perf.benchmark_score || 0.8) * 100)}%</div>
          </div>
          <div>
            <div style="color: var(--text-muted); font-size: 9px;">CALLS</div>
            <div style="color: var(--accent-emerald); font-weight: 700;">${perf.total_calls || 0}</div>
          </div>
        </div>

        <div style="display: flex; gap: 8px; margin-top: auto;">
          <button class="btn btn-secondary" style="flex: 1; font-size: 11px; padding: 6px;" onclick="Registry.runSingleProbe('${model.id}')">
            🔬 Run Probe
          </button>
          <button class="btn btn-secondary" style="flex: 1; font-size: 11px; padding: 6px; border-color: var(--accent-cyan);" onclick="Registry.openOverrideModal('${model.ollama_name}')">
            ⚙️ Tune Scores
          </button>
        </div>
      `;

      grid.appendChild(card);
    });
  },

  async runSingleProbe(modelId) {
    try {
      const res = await fetch(`/api/registry/probe/${modelId}`, { method: "POST" });
      if (!res.ok) throw new Error("Probe failed");
      const data = await res.json();
      alert(`Synthetic capability probe completed for ${data.probe?.ollama_name || modelId}. Capability evidence updated.`);
      this.fetchModels();
    } catch (err) {
      alert("Probe error: " + err.message);
    }
  },

  async runAllProbes() {
    for (const m of this.models) {
      await this.runSingleProbe(m.id);
    }
  },

  openOverrideModal(ollamaName) {
    const model = this.models.find(m => m.ollama_name === ollamaName);
    if (!model) return;

    this.currentOverrideModel = model;
    document.getElementById("modal-model-tag").textContent = model.ollama_name;
    const container = document.getElementById("modal-sliders-container");
    container.innerHTML = "";

    const caps = model.capabilities || {};
    const dims = [
      { key: "reasoning", label: "Reasoning & Deductive Logic" },
      { key: "coding", label: "Code Generation & Python Scripting" },
      { key: "vision", label: "Multimodal Vision & Diagrams" },
      { key: "document_understanding", label: "Technical Document Understanding" },
      { key: "mathematics", label: "Engineering Mathematics & Physics" },
      { key: "ocr", label: "OCR & Text Scanning" },
      { key: "tool_use", label: "Tool Use & Function Calling" },
      { key: "general", label: "General Knowledge & Summarization" },
    ];

    dims.forEach(d => {
      let val = 0.5;
      if (typeof caps[d.key] === "number") val = caps[d.key];
      else if (caps[d.key] && typeof caps[d.key].score === "number") val = caps[d.key].score;

      const item = document.createElement("div");
      item.className = "slider-item";
      item.innerHTML = `
        <label>${d.label}</label>
        <input type="range" min="0" max="1" step="0.01" value="${val}" id="slider-${d.key}" oninput="document.getElementById('val-${d.key}').textContent = Math.round(this.value * 100) + '%'">
        <span id="val-${d.key}">${Math.round(val * 100)}%</span>
      `;
      container.appendChild(item);
    });

    document.getElementById("override-modal").classList.add("active");
  },

  closeModal() {
    document.getElementById("override-modal").classList.remove("active");
    this.currentOverrideModel = null;
  },

  async saveCapabilityOverrides() {
    if (!this.currentOverrideModel) return;

    const dims = ["reasoning", "coding", "vision", "document_understanding", "mathematics", "ocr", "tool_use", "general"];
    const updatedCaps = {};

    dims.forEach(d => {
      const slider = document.getElementById(`slider-${d}`);
      if (slider) {
        updatedCaps[d] = parseFloat(slider.value);
      }
    });

    try {
      const res = await fetch("/api/registry/override", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ollama_name: this.currentOverrideModel.ollama_name,
          capabilities: updatedCaps,
        }),
      });

      if (!res.ok) throw new Error("Failed to save overrides");
      this.closeModal();
      await this.fetchModels();
    } catch (err) {
      alert("Error saving overrides: " + err.message);
    }
  }
};

window.Registry = Registry;
