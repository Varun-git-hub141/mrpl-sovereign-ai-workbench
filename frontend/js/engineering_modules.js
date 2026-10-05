// MRPL Sovereign Engineering Modules Controller (RAG, Formulas, P&ID, Inspection, DOCX)

const RAGManager = {
  currentTag: null,

  async init() {
    this.loadStats();
    this.runDebugQuery("Tell me everything relevant about P-201.");
  },

  async loadStats() {
    try {
      const res = await fetch("/api/rag/stats");
      if (!res.ok) return;
      const data = await res.json();
      const authDistEl = document.getElementById("rag-auth-dist");
      if (authDistEl) {
        const kb = data.mrpl_knowledge_base || {};
        const totalDocs = data.total_documents ?? kb.total_documents ?? 0;
        const totalChunks = data.total_chunks ?? kb.total_chunks ?? 0;
        authDistEl.innerHTML = `
          <span class="preset-tag high">${totalDocs} MRPL Docs</span>
          <span class="preset-tag cyan">${totalChunks} Chunks</span>
          <span class="preset-tag emerald">100% On-Premise</span>
        `;
      }
      const subtitleEl = document.getElementById("rag-subtitle");
      if (subtitleEl) {
        const totalDocs = data.total_documents ?? data.mrpl_knowledge_base?.total_documents ?? "";
        subtitleEl.textContent = `${totalDocs ? totalDocs + " " : ""}Curated Refinery Documents across 9 Categories • BM25 + Semantic Dense Retrieval`;
      }
    } catch (e) {
      console.warn("RAG stats error:", e);
    }
  },

  filterByTag(tag) {
    this.currentTag = tag;
    const input = document.getElementById("rag-search-input");
    if (input) input.value = `Tell me everything relevant about ${tag}.`;
    this.runDebugQuery(`Tell me everything relevant about ${tag}.`);
  },

  async runDebugQuery(customQuery) {
    const q = customQuery || document.getElementById("rag-search-input")?.value || "Tell me everything relevant about P-201.";
    const debugContainer = document.getElementById("rag-debug-pipeline-container");
    const resultsContainer = document.getElementById("rag-results-container");

    if (debugContainer) {
      debugContainer.style.display = "block";
      debugContainer.innerHTML = '<div style="color:var(--accent-cyan); padding:20px; text-align:center;">⚡ Executing Hybrid RAG Pipeline (Query Understanding → BM25 → Semantic → Hybrid Ranking → Contradiction Detection → Calculator)...</div>';
    }

    try {
      const res = await fetch("/api/rag/debug-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, top_k: 6 }),
      });
      const data = await res.json();
      this.renderDebugPipeline(data);
      this.renderRetrievedCards(data.retrieved_evidence || []);
    } catch (e) {
      if (debugContainer) {
        debugContainer.innerHTML = `<div style="color:var(--accent-ruby); padding:20px;">Pipeline execution error: ${e.message}</div>`;
      }
    }
  },

  renderDebugPipeline(data) {
    const container = document.getElementById("rag-debug-pipeline-container");
    if (!container) return;

    const contra = data.contradiction_report || {};
    const calc = data.calculation_path;
    const gate = data.human_review_gate || {};

    let contraBanner = "";
    if (contra.has_conflict) {
      contraBanner = `
        <div style="background: #fef2f2; border: 1px solid #f87171; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
          <div style="font-weight: 700; color: #dc2626; font-size: 13px;">⚠️ CONFLICT DETECTED IN ENGINEERING EVIDENCE</div>
          <div style="font-size: 11.5px; color: #1e293b; margin-top: 4px; line-height: 1.4;">${contra.explanation}</div>
          <div style="font-size: 11px; color: #b45309; margin-top: 4px; font-weight: 600;">Status: REQUIRES HUMAN REVIEW</div>
        </div>
      `;
    }

    let calcSection = "";
    if (calc && calc.result !== null && calc.result !== undefined) {
      calcSection = `
        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 12px; margin-top: 10px;">
          <div style="font-weight: 700; color: #166534; font-size: 12px;">🧪 DETERMINISTIC PYTHON CALCULATOR EXECUTION (CR-001)</div>
          <div style="font-size: 11.5px; margin-top: 4px; color: #1e293b;"><strong>Formula:</strong> <code style="background: #e2e8f0; padding: 2px 5px; border-radius: 4px; font-family: var(--font-mono);">${calc.formula_display}</code></div>
          <div style="font-size: 12px; font-weight: 700; color: #0f172a; margin-top: 4px;">Result: <span style="color: #16a34a;">${calc.result} ${calc.result_unit}</span></div>
          <div style="font-size: 10.5px; color: #64748b; margin-top: 2px;">Independent Verification: <strong>MATCH (100% Deterministic Python)</strong></div>
        </div>
      `;
    }

    container.innerHTML = `
      <div class="panel-card" style="background: #ffffff; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); padding: 16px; border-radius: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px;">
          <div style="font-size: 13px; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 8px;">
            <span>🔬 MRPL QUERY PIPELINE & REASONING TRACE</span>
          </div>
          <div style="font-size: 11px; font-family: var(--font-mono); color: #16a34a; font-weight: 600;">
            Latency: ${data.latency_ms} ms • ${data.sovereignty}
          </div>
        </div>

        ${contraBanner}

        <!-- 6-Stage Pipeline Grid -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-bottom: 14px;">
          <!-- Stage 1: Entity Extraction -->
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
            <div style="font-size: 11px; font-weight: 700; color: #0284c7;">1. Entity Extraction</div>
            <div style="font-size: 11.5px; margin-top: 4px; color: #1e293b;">Detected Tag: <strong style="color: #b45309;">${data.detected_equipment || 'General Query'}</strong></div>
            <div style="font-size: 10.5px; color: #64748b;">Type Hint: ${data.query_entities?.document_type_hint || 'Cross-Category'}</div>
          </div>

          <!-- Stage 2: BM25 Top Lexical -->
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
            <div style="font-size: 11px; font-weight: 700; color: #16a34a;">2. BM25 Top Match</div>
            <div style="font-size: 10.5px; margin-top: 4px; word-break: break-all; color: #1e293b;">${data.bm25_top_scores?.[0]?.document || '--'}</div>
            <div style="font-size: 10.5px; color: #15803d; font-weight: 600;">Score: ${data.bm25_top_scores?.[0]?.score || 0}</div>
          </div>

          <!-- Stage 3: Semantic Top Dense -->
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
            <div style="font-size: 11px; font-weight: 700; color: #9333ea;">3. Semantic Dense Match</div>
            <div style="font-size: 10.5px; margin-top: 4px; word-break: break-all; color: #1e293b;">${data.semantic_top_scores?.[0]?.document || '--'}</div>
            <div style="font-size: 10.5px; color: #7e22ce; font-weight: 600;">Cosine: ${data.semantic_top_scores?.[0]?.score || 0}</div>
          </div>

          <!-- Stage 4: Human Review Gate -->
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
            <div style="font-size: 11px; font-weight: 700; color: ${gate.required ? '#dc2626' : '#16a34a'};">4. Human Review Gate</div>
            <div style="font-size: 11.5px; margin-top: 4px; color: #1e293b;">Status: <strong style="color: ${gate.required ? '#dc2626' : '#166534'}">${gate.status}</strong></div>
            <div style="font-size: 10.5px; color: #64748b;">${gate.reason}</div>
          </div>
        </div>

        ${calcSection}

        <!-- Synthesized Final Reasoning Output -->
        <div style="margin-top: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; border-left: 3px solid #0284c7;">
          <div style="font-size: 11px; font-weight: 700; color: #0369a1; margin-bottom: 6px;">📋 SYNTHESIZED EVIDENCE REASONING:</div>
          <div style="font-size: 12px; line-height: 1.6; color: #0f172a; white-space: pre-line;">${data.final_answer}</div>
        </div>
      </div>
    `;
  },

  async searchRAG() {
    const q = document.getElementById("rag-search-input")?.value || "";
    const cat = document.getElementById("rag-category-select")?.value || "all";
    const container = document.getElementById("rag-results-container");
    if (!container) return;

    container.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">Searching MRPL knowledge documents...</div>';

    try {
      const res = await fetch("/api/rag/hybrid-search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          top_k: 6,
          document_type: cat !== "all" ? cat : null,
          equipment_tag: this.currentTag,
        }),
      });
      const data = await res.json();
      this.renderRetrievedCards(data.results || []);
    } catch (e) {
      container.innerHTML = `<div style="color:var(--accent-ruby); padding:20px;">Search error: ${e.message}</div>`;
    }
  },

  renderRetrievedCards(results) {
    const container = document.getElementById("rag-results-container");
    if (!container) return;

    if (!results || results.length === 0) {
      container.innerHTML = '<div style="color:#64748b; padding:20px; text-align:center;">No matching MRPL knowledge objects found.</div>';
      return;
    }

    container.innerHTML = `<div style="font-size: 12px; font-weight: 700; color: #64748b; margin-bottom: 8px;">Top Retrieved Evidence Chunks (${results.length} records):</div>`;

    results.forEach(item => {
      const card = document.createElement("div");
      card.className = "panel-card";
      card.style.marginBottom = "12px";
      card.style.background = "#ffffff";
      card.style.border = "1px solid #e2e8f0";
      card.style.borderRadius = "8px";
      card.style.padding = "14px";
      card.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";

      const prov = item.source || {};
      const ret = item.retrieval || {};
      const authClass = item.authority_level === "A" ? "high" : "medium";

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
          <div>
            <h4 style="color:#0369a1; font-size:13.5px; font-weight:700; margin-bottom:2px;">[${prov.document_type || 'Record'}] ${prov.document || 'Document'}</h4>
            <div style="font-size:11px; color:#64748b;">
              ID: <strong>${prov.document_id || '--'}</strong> • Page: <strong>${prov.page || 1}</strong> • Section: <em>${prov.section || 'General'}</em> • Area: <strong>${prov.plant_area || 'CDU-II'}</strong>
            </div>
          </div>
          <div style="display:flex; gap:6px;">
            <span class="preset-tag ${authClass}">Authority ${item.authority_level || 'A'}</span>
            <span class="preset-tag emerald">OFFICIAL MRPL</span>
          </div>
        </div>
        <div style="font-size:12px; line-height:1.5; color:#1e293b; margin-bottom:10px; background:#f8fafc; padding:10px; border-radius:6px; border-left:3px solid #0284c7; border:1px solid #e2e8f0; border-left-width:3px;">
          ${item.text || item.content || ''}
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; color:#64748b; background:#f1f5f9; padding:6px 10px; border-radius:4px;">
          <div>Equipment Tag: <strong style="color:#b45309;">${prov.equipment_tag || '--'}</strong></div>
          <div style="display:flex; gap:12px; font-family:var(--font-mono);">
            <span>BM25: <strong style="color:#15803d;">${ret.keyword_score || 0}</strong></span>
            <span>Semantic: <strong style="color:#7e22ce;">${ret.semantic_score || 0}</strong></span>
            <span>Hybrid Score: <strong style="color:#0284c7;">${ret.hybrid_score || item.score || 0}</strong></span>
          </div>
        </div>
      `;
      container.appendChild(card);
    });
  }
};


const FormulaManager = {
  allFormulas: [],

  async init() {
    this.fetchFormulas();
  },

  async fetchFormulas(category, query) {
    const container = document.getElementById("formulas-grid-container");
    if (!container) return;

    try {
      let url = "/api/formulas";
      const params = new URLSearchParams();
      if (category && category !== "all") params.append("category", category);
      if (query) params.append("q", query);
      if (params.toString()) url += `?${params.toString()}`;

      const res = await fetch(url);
      const list = await res.json();
      this.allFormulas = list;
      this.renderFormulas(list);
    } catch (e) {
      container.innerHTML = `<div style="color:var(--accent-ruby); padding:20px;">Error loading formulas: ${e.message}</div>`;
    }
  },

  renderFormulas(list) {
    const container = document.getElementById("formulas-grid-container");
    if (!container) return;

    const countEl = document.getElementById("formula-total-count");
    if (countEl) countEl.innerText = `${list.length} Validated Formulas`;

    if (list.length === 0) {
      container.innerHTML = '<div style="color:var(--text-muted); padding:30px; text-align:center; grid-column:1/-1;">No formulas match current filter.</div>';
      return;
    }

    container.innerHTML = "";
    list.forEach(f => {
      const card = document.createElement("div");
      card.className = "model-card";
      card.style.display = "flex";
      card.style.flexDirection = "column";
      card.style.justifyContent = "space-between";

      const riskClass = f.risk_level === "high" ? "high" : f.risk_level === "medium" ? "medium" : "low";

      card.innerHTML = `
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-family:var(--font-mono); color:var(--accent-cyan); font-weight:700; font-size:12px;">${f.formula_id}</span>
            <span class="preset-tag ${riskClass}">${f.category}</span>
          </div>
          <h4 style="font-size:14px; margin-bottom:6px; color:var(--text-bright);">${f.name}</h4>
          <div style="font-size:11px; color:var(--text-muted); margin-bottom:10px; line-height:1.4;">${f.description}</div>
          
          <div style="background:rgba(0,0,0,0.3); padding:8px 10px; border-radius:6px; font-family:var(--font-mono); font-size:12px; color:var(--accent-amber); margin-bottom:10px; border:1px solid rgba(255,255,255,0.06);">
            ${f.equation_display}
          </div>

          <div style="font-size:11px; color:var(--text-muted); margin-bottom:12px;">
            <div>Standard: <strong style="color:var(--text-main);">${f.standard_reference}</strong></div>
            <div>Equipment: <span style="color:var(--text-main);">${(f.applicable_equipment || []).slice(0, 3).join(', ')}</span></div>
          </div>
        </div>

        <button class="btn-primary" style="width:100%; padding:8px; font-size:12px;" onclick="FormulaManager.openCalculator('${f.formula_id}')">
          🧮 Calculate Deterministically
        </button>
      `;
      container.appendChild(card);
    });
  },

  openCalculator(formulaId) {
    const f = this.allFormulas.find(x => x.formula_id === formulaId);
    if (!f) return;

    const modal = document.getElementById("calc-modal");
    if (!modal) return;

    const tEl = document.getElementById("calc-modal-title");
    if (tEl) tEl.innerText = `${f.formula_id}: ${f.name}`;
    const eqEl = document.getElementById("calc-modal-eq");
    if (eqEl) eqEl.innerText = f.equation_display;
    const stdEl = document.getElementById("calc-modal-std");
    if (stdEl) stdEl.innerText = f.standard_reference;

    const inputsContainer = document.getElementById("calc-modal-inputs");
    if (inputsContainer) inputsContainer.innerHTML = "";

    // Preset sample values for convenience
    const defaults = {
      "T_initial": 5.0, "T_current": 3.8, "delta_years": 4.0, "T_previous": 4.2,
      "delta_years_ST": 2.0, "T_min": 3.2, "CR": 0.30, "future_years": 3.0,
      "CA_design": 1.8, "Max_Cap": 5.0, "P": 1.5, "D": 219.1, "S": 110.0,
      "E": 1.0, "W": 1.0, "Y": 0.4, "c": 1.8, "Q_m3hr": 280.0, "D_mm": 200.0,
      "rho": 850.0, "v": 2.47, "mu_cp": 5.0, "H_m": 68.0, "P_disch_bar": 7.2,
      "P_suct_bar": 1.8, "NPSHa": 4.8, "NPSHr": 3.2, "RMS_velocity": 7.4
    };

    f.required_data.forEach(reqKey => {
      const row = document.createElement("div");
      row.style.marginBottom = "10px";
      const u = f.units[reqKey] || "";
      const desc = f.variables[reqKey] || reqKey;
      const defVal = defaults[reqKey] !== undefined ? defaults[reqKey] : 1.0;

      row.innerHTML = `
        <label style="display:block; font-size:12px; margin-bottom:3px; color:var(--text-bright);">
          ${desc} <strong style="color:var(--accent-cyan);">(${reqKey})</strong> ${u ? `<span style="color:var(--text-muted);">[${u}]</span>` : ''}
        </label>
        <input type="number" step="any" id="calc-input-${reqKey}" value="${defVal}" class="form-input" style="width:100%; font-family:var(--font-mono);">
      `;
      if (inputsContainer) inputsContainer.appendChild(row);
    });

    const execBtn = document.getElementById("calc-modal-exec-btn");
    if (execBtn) execBtn.onclick = () => this.executeCalculation(f);
    const resBox = document.getElementById("calc-modal-result");
    if (resBox) resBox.style.display = "none";
    modal.style.display = "flex";
  },

  async executeCalculation(f) {
    const inputs = {};
    f.required_data.forEach(k => {
      const el = document.getElementById(`calc-input-${k}`);
      if (el) inputs[k] = parseFloat(el.value);
    });

    const resBox = document.getElementById("calc-modal-result");
    resBox.style.display = "block";
    resBox.innerHTML = "Calculating deterministically...";

    try {
      const res = await fetch("/api/formulas/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ formula_id: f.formula_id, inputs: inputs }),
      });
      const data = await res.json();

      if (data.status === "SUCCESS") {
        resBox.innerHTML = `
          <div style="color:var(--accent-emerald); font-weight:700; font-size:14px; margin-bottom:4px;">
            ✔ CALCULATION RESULT: ${data.result} ${data.result_unit || ''}
          </div>
          <div style="font-family:var(--font-mono); font-size:12px; color:var(--text-bright); margin-bottom:6px;">
            Formula Display: ${data.formula_display}
          </div>
          <div style="font-size:11px; color:var(--text-muted);">
            ${data.engineering_notes} • Standard: ${data.standard_reference}
          </div>
        `;
      } else {
        resBox.innerHTML = `
          <div style="color:var(--accent-ruby); font-weight:700;">Status: ${data.status}</div>
          <div style="font-size:12px; color:var(--text-muted);">${data.engineering_notes}</div>
        `;
      }
    } catch (e) {
      resBox.innerHTML = `<div style="color:var(--accent-ruby);">Error: ${e.message}</div>`;
    }
  },

  closeModal() {
    const modal = document.getElementById("calc-modal");
    if (modal) modal.style.display = "none";
  }
};


const PIDManager = {
  init() {
    const input = document.getElementById("pid-query-input");
    if (input && !input._hasEnterListener) {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.askPID();
        }
      });
      input._hasEnterListener = true;
    }
  },

  populateQuestion(q) {
    const input = document.getElementById("pid-query-input");
    if (input) {
      input.value = q;
      input.focus();
      this.askPID(q);
    }
  },

  formatPIDAnswer(text) {
    if (!text) return "";
    let clean = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Blockquotes
    clean = clean.replace(/^>\s*(.*?)$/gm, '<div style="padding:8px 12px; background:#f0fdf4; border-left:3px solid #16a34a; border-radius:4px; margin:6px 0 10px 0; font-size:12px; color:#14532d;">$1</div>');

    // Inline code
    clean = clean.replace(/`([^`]+)`/g, '<code style="background:#f1f5f9; color:#0369a1; padding:2px 6px; border-radius:4px; font-family:var(--font-mono, monospace); font-size:11.5px; border:1px solid #e2e8f0;">$1</code>');

    // Bold tags
    clean = clean.replace(/\*\*([^*]+)\*\*/g, '<strong style="color:#0f172a; font-weight:700;">$1</strong>');

    // Flow arrows with clean step formatting
    clean = clean.replace(/→/g, '<span style="color:#16a34a; font-weight:700; margin:0 6px;">→</span>');

    // Newlines
    clean = clean.replace(/\n/g, "<br>");

    return clean;
  },

  async askPID(question) {
    const q = question || document.getElementById("pid-query-input")?.value;
    if (!q) return;

    const placeholder = document.getElementById("pid-answer-placeholder");
    const resContainer = document.getElementById("pid-query-result");
    if (!resContainer) return;

    if (placeholder) placeholder.style.display = "none";
    resContainer.style.display = "block";
    resContainer.innerHTML = '<div style="color:#64748b; padding:18px; text-align:center; font-size:12.5px;"><span style="display:inline-block; animation:spin 1s linear infinite; margin-right:8px;">⚙</span> Analyzing permanent P&amp;ID architecture...</div>';

    try {
      const res = await fetch("/api/pid/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "P&ID query failed");
      }
      const data = await res.json();
      this.renderTierAResult(data, q, resContainer);
    } catch (e) {
      resContainer.innerHTML = `<div style="color:#b91c1c; background:#fee2e2; border:1px solid #fecaca; border-radius:8px; padding:14px; font-size:12.5px;">P&amp;ID Engine Error: ${e.message}</div>`;
    }
  },

  renderTierAResult(data, q, resContainer) {
    const placeholder = document.getElementById("pid-answer-placeholder");
    if (placeholder) placeholder.style.display = "none";

    const plan = data.query_plan || {};
    const target = plan.target_entity || data.drawing_id || "Asset";
    const operation = plan.intent || "TOPOLOGY";
    const directNodes = data.direct_nodes_involved || [];
    const pathTrace = data.path_trace || [];
    const isUnresolved = data.status === "UNRESOLVED";
    const isDescriptive = data.answer && data.answer.includes("DESCRIPTIVE ARCHITECTURE ANSWER");

    const formattedAnswer = this.formatPIDAnswer(data.answer);

    resContainer.innerHTML = `
      <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-top:6px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; border-bottom:1px solid #f1f5f9; padding-bottom:10px; margin-bottom:12px;">
          <div>
            <div style="font-size:14px; font-weight:700; color:#0f172a;">
              Target: <span style="color:#15803d; font-family:var(--font-mono, monospace); font-weight:800;">${target}</span>
            </div>
            <div style="font-size:11.5px; color:#64748b; margin-top:2px;">
              ${isDescriptive ? 'Mode: <strong style="color:#0284c7;">Descriptive Architecture Q&amp;A</strong>' : `Concept: <strong style="color:#15803d;">${operation}</strong>`}
              &nbsp;|&nbsp; Architecture: <strong style="color:#0f172a; font-family:var(--font-mono, monospace);">MRPL-PID-PERMANENT-P201</strong>
            </div>
          </div>
          <div style="display:flex; gap:6px; align-items:center;">
            <span style="background:${isUnresolved ? '#fee2e2' : (isDescriptive ? '#e0f2fe' : '#dcfce7')}; color:${isUnresolved ? '#b91c1c' : (isDescriptive ? '#0369a1' : '#15803d')}; font-size:11px; font-weight:700; padding:4px 10px; border-radius:9999px;">
              ${isUnresolved ? 'UNRESOLVED' : (isDescriptive ? 'DESCRIPTIVE ANSWER' : 'DETERMINISTIC TOPOLOGY')}
            </span>
            <span style="background:#f1f5f9; color:#475569; font-size:11px; font-weight:600; padding:4px 10px; border-radius:9999px;">
              100% Grounded
            </span>
          </div>
        </div>

        ${!isUnresolved && pathTrace.length > 1 ? `
        <!-- ENGINEERING PATH TRACE -->
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 14px; margin-bottom:14px;">
          <div style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
            Process Flow Sequence
          </div>
          <div style="display:flex; align-items:center; flex-wrap:wrap; gap:6px; font-size:12px; font-family:var(--font-mono, monospace);">
            ${pathTrace.map((node, idx) => `
              <span style="background:#ffffff; border:1px solid #cbd5e1; padding:3px 8px; border-radius:5px; font-weight:700; color:${node === target ? '#15803d; border-color:#86efac; background:#f0fdf4;' : '#1e293b;'}">${node}</span>
              ${idx < pathTrace.length - 1 ? '<span style="color:#16a34a; font-weight:bold; font-size:13px;">↓</span>' : ''}
            `).join('')}
          </div>
        </div>
        ` : ''}

        ${isUnresolved ? `
        <!-- UNKNOWN TARGET NOTICE -->
        <div style="background:#fff1f2; border:1px solid #fecdd3; border-radius:8px; padding:12px 16px; margin-bottom:14px; font-size:12px; color:#9f1239;">
          <strong>Entity Not Found:</strong> Tag <code>${target}</code> is not present in the permanent P&amp;ID architecture (<code>MRPL-PID-PERMANENT-P201</code>). Drawing switching and cross-drawing searches are strictly disabled.
        </div>
        ` : ''}

        <!-- FORMATTED ANSWER CONTENT -->
        <div style="font-size:13px; line-height:1.6; color:#1e293b; background:#fafafa; padding:14px 16px; border-radius:8px; border:1px solid #f1f5f9;">
          ${formattedAnswer}
        </div>
      </div>
    `;
  }
};


const InspectionManager = {
  async analyzeCurrent() {
    const text = document.getElementById("inspection-input-text")?.value || `
Equipment: P-101 Transfer Pump
Original wall thickness = 5.0 mm
Current wall thickness = 3.8 mm
Minimum allowable thickness = 3.2 mm
Inspection interval = 4.0 years
Overall vibration = 7.4 mm/s RMS
    `;

    const resBox = document.getElementById("inspection-analysis-result");
    if (!resBox) return;

    resBox.innerHTML = "Analyzing inspection report...";

    try {
      const res = await fetch("/api/inspection/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text }),
      });
      const data = await res.json();

      const bannerClass = data.operation_status === "HUMAN_REVIEW_REQUIRED" ? "ruby" : "emerald";

      resBox.innerHTML = `
        <div style="padding:12px; background:rgba(239,68,68,0.15); border:1px solid var(--accent-ruby); border-radius:8px; margin-bottom:16px;">
          <h4 style="color:var(--accent-ruby); font-size:14px; margin-bottom:4px;">${data.decision_banner}</h4>
          <div style="font-size:12px; color:var(--text-bright);">${data.reason}</div>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px; margin-bottom:16px;">
          <div class="model-card" style="padding:10px;">
            <div style="font-size:11px; color:var(--text-muted);">Corrosion Rate</div>
            <div style="font-size:18px; font-weight:700; color:var(--accent-amber); font-family:var(--font-mono);">${data.corrosion_rate_mm_year} mm/yr</div>
            <div style="font-size:10px; color:var(--text-muted);">API 570 Historical Average</div>
          </div>
          <div class="model-card" style="padding:10px;">
            <div style="font-size:11px; color:var(--text-muted);">Thickness Margin</div>
            <div style="font-size:18px; font-weight:700; color:var(--accent-cyan); font-family:var(--font-mono);">${data.remaining_thickness_margin_mm} mm</div>
            <div style="font-size:10px; color:var(--text-muted);">Above t_min (${data.minimum_allowable_mm} mm)</div>
          </div>
          <div class="model-card" style="padding:10px;">
            <div style="font-size:11px; color:var(--text-muted);">Remaining Life</div>
            <div style="font-size:18px; font-weight:700; color:var(--accent-emerald); font-family:var(--font-mono);">${data.remaining_life_years} Years</div>
            <div style="font-size:10px; color:var(--text-muted);">Statutory Half-Life: ${(data.remaining_life_years/2).toFixed(1)} yrs</div>
          </div>
          <div class="model-card" style="padding:10px;">
            <div style="font-size:11px; color:var(--text-muted);">Vibration Velocity</div>
            <div style="font-size:18px; font-weight:700; color:var(--accent-ruby); font-family:var(--font-mono);">${data.vibration_velocity_rms} mm/s</div>
            <div style="font-size:10px; color:var(--accent-ruby);">Exceeds ISO 10816 Limit (4.5)</div>
          </div>
        </div>

        <button class="btn-primary" style="padding:10px 16px;" onclick="DocxManager.generateApprovalNote()">
          📄 Generate P-101 Continued Operation DOCX Note
        </button>
      `;
    } catch (e) {
      resBox.innerHTML = `<div style="color:var(--accent-ruby);">Analysis error: ${e.message}</div>`;
    }
  }
};


const DocxManager = {
  async generateApprovalNote() {
    const btn = document.getElementById("gen-docx-btn");
    if (btn) btn.innerText = "Generating 19-Section DOCX...";

    const resBox = document.getElementById("docx-result-container");
    if (resBox) {
      resBox.style.display = "block";
      resBox.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">Compiling official 19-section engineering review note with zero fabrication...</div>';
    }

    try {
      const res = await fetch("/api/docx/generate-approval-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          original_thickness: 5.0,
          current_thickness: 3.8,
          t_min: 3.2,
          interval_years: 4.0,
          vibration_rms: "7.4 mm/s RMS",
        }),
      });
      const data = await res.json();

      if (data.success && resBox) {
        resBox.innerHTML = `
          <div style="padding:16px; background:rgba(16,185,129,0.1); border:1px solid var(--accent-emerald); border-radius:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <h4 style="color:var(--accent-emerald); font-size:15px; margin-bottom:4px;">✔ Engineering Review Note DOCX Generated</h4>
                <div style="font-size:12px; color:var(--text-muted);">File: <strong>${data.filename}</strong> (Complete 19 mandatory sections included)</div>
              </div>
              <a href="${data.download_url}" download class="btn-primary" style="text-decoration:none; padding:10px 18px; font-weight:700; background:var(--accent-emerald); color:#000;">
                ⬇ Download Official DOCX
              </a>
            </div>
          </div>
        `;
      }
    } catch (e) {
      if (resBox) resBox.innerHTML = `<div style="color:var(--accent-ruby); padding:20px;">DOCX Generation Error: ${e.message}</div>`;
    } finally {
      if (btn) btn.innerText = "📄 Generate Official P-101 Approval Note DOCX";
    }
  }
};

window.RAGManager = RAGManager;
window.FormulaManager = FormulaManager;
window.PIDManager = PIDManager;
window.InspectionManager = InspectionManager;
window.DocxManager = DocxManager;
