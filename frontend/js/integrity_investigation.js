// frontend/js/integrity_investigation.js
/**
 * MRPL Sovereign AI Workbench — Phase 9: Industrial Integrity Investigation Workflow
 * Orchestrates real user-facing investigation workflow from Source Evidence -> Decisions -> Trace.
 */

const IntegrityManager = {
  currentCaseId: null,
  currentCase: null,
  activeStageTab: 'evidence',
  auditTraceTree: null,
  isInitialized: false,

  async init() {
    if (!this.isInitialized) {
      this.bindEvents();
      this.isInitialized = true;
    }
    await this.fetchCases();
    if (!this.currentCaseId) {
      await this.loadDemonstration('E-801');
    } else {
      this.renderCaseOverview();
      this.renderCurrentStageContent();
    }
  },

  onTabActivated() {
    this.renderCaseOverview();
    this.renderCurrentStageContent();
    this.fetchCases();
  },

  bindEvents() {
    // Stepper button clicks
    document.querySelectorAll('.integrity-step-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const stage = btn.getAttribute('data-stage');
        if (stage) this.switchStage(stage);
      });
    });

    const caseSelect = document.getElementById('integrity-case-select');
    if (caseSelect) {
      caseSelect.addEventListener('change', (e) => {
        if (e.target.value) {
          this.loadCase(e.target.value);
        }
      });
    }
  },

  async fetchCases() {
    try {
      const res = await fetch('/api/integrity/cases');
      if (!res.ok) return;
      const data = await res.json();
      const select = document.getElementById('integrity-case-select');
      if (!select) return;

      select.innerHTML = '<option value="">-- Select Integrity Case --</option>';
      (data.cases || []).forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.case_id;
        opt.textContent = `[${c.entity_tag}] ${c.case_title} (${c.workflow_stage})`;
        if (this.currentCaseId === c.case_id) opt.selected = true;
        select.appendChild(opt);
      });
    } catch (err) {
      console.warn('Failed to fetch cases:', err);
    }
  },

  async loadCase(caseId) {
    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${caseId}`);
      if (!res.ok) throw new Error('Failed to load case');
      this.currentCase = await res.json();
      this.currentCaseId = this.currentCase.case_id;
      this.renderCaseOverview();
      this.renderCurrentStageContent();
      await this.fetchCases();
    } catch (err) {
      console.error('Error loading case:', err);
      this.showToast('Error loading case: ' + err.message, 'error');
    } finally {
      this.setLoading(false);
    }
  },

  async createNewCaseModal() {
    const tag = prompt('Enter Equipment/Entity Tag (e.g., E-801, PSV-201, C-101):', 'E-801');
    if (!tag) return;
    const title = prompt('Enter Case Title:', `Integrity Evaluation for ${tag}`);
    if (!title) return;
    const desc = prompt('Enter Case Description:', 'Wall thinning and statutory compliance audit.');

    try {
      this.setLoading(true);
      const res = await fetch('/api/integrity/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_tag: tag.trim().toUpperCase(),
          case_title: title.trim(),
          description: desc || '',
          risk_level: tag.includes('PSV') ? 'STATUTORY' : 'LOW',
        }),
      });
      if (!res.ok) throw new Error('Failed to create case');
      const created = await res.json();
      this.showToast(`Case ${created.case_id} created successfully!`, 'success');
      await this.loadCase(created.case_id);
    } catch (err) {
      alert('Error creating case: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  async loadDemonstration(scenario = 'E-801') {
    try {
      this.setLoading(true);
      const res = await fetch('/api/integrity/demonstration', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario }),
      });
      if (!res.ok) throw new Error('Failed to load demonstration case');
      const data = await res.json();
      this.currentCase = data.case;
      this.currentCaseId = this.currentCase.case_id;
      this.renderCaseOverview();
      this.renderCurrentStageContent();
      await this.fetchCases();
      this.showToast(`Loaded Demonstration: ${scenario} (${this.currentCase.entity_tag})`, 'success');
    } catch (err) {
      console.error('Demo load error:', err);
      this.showToast('Failed to load demo: ' + err.message, 'error');
    } finally {
      this.setLoading(false);
    }
  },

  switchStage(stageName) {
    this.activeStageTab = stageName;
    document.querySelectorAll('.integrity-step-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-stage') === stageName);
    });
    document.querySelectorAll('.integrity-stage-panel').forEach(p => {
      p.classList.toggle('active', p.id === `stage-panel-${stageName}`);
    });
    this.renderCurrentStageContent();
  },

  renderCaseOverview() {
    if (!this.currentCase) return;
    const c = this.currentCase;

    const elId = document.getElementById('case-badge-id');
    const elTag = document.getElementById('case-badge-tag');
    const elRisk = document.getElementById('case-badge-risk');
    const elStage = document.getElementById('case-badge-stage');
    const elTitle = document.getElementById('case-header-title');
    const elDesc = document.getElementById('case-header-desc');
    const elHash = document.getElementById('case-header-hash');

    if (elId) elId.textContent = c.case_id || '--';
    if (elTag) elTag.textContent = c.entity_tag || '--';
    if (elRisk) {
      const r = c.risk_level || 'LOW';
      elRisk.textContent = r;
      elRisk.className = `preset-tag ${String(r).toLowerCase()}`;
    }
    if (elStage) {
      const s = c.workflow_stage || 'EVIDENCE_RECEIVED';
      elStage.textContent = s;
      elStage.className = `preset-tag emerald stage-${String(s).toLowerCase()}`;
    }
    if (elTitle) elTitle.textContent = c.case_title || 'Integrity Investigation';
    if (elDesc) elDesc.textContent = c.description || 'No description provided.';
    if (elHash) elHash.textContent = c.audit_trail_hash ? `SHA-256: ${c.audit_trail_hash.substring(0, 16)}...` : 'Hash: Pending Evaluation';

    this.updateStepperProgress();
  },

  updateStepperProgress() {
    if (!this.currentCase) return;
    const stage = this.currentCase.workflow_stage || 'EVIDENCE_RECEIVED';
    const stagesOrdered = [
      'EVIDENCE_RECEIVED',
      'OBSERVATIONS_EXTRACTED',
      'EVIDENCE_ASSESSED',
      'RECONCILED',
      'DECISION_EVALUATED',
      'HUMAN_REVIEW_REQUIRED',
      'COMPLETED'
    ];
    const currentIndex = stagesOrdered.indexOf(stage);

    document.querySelectorAll('.integrity-step-btn').forEach((btn) => {
      const stepStage = btn.getAttribute('data-stage-code');
      const stepIndex = stagesOrdered.indexOf(stepStage);
      if (stepIndex <= currentIndex && currentIndex !== -1) {
        btn.classList.add('completed');
      } else {
        btn.classList.remove('completed');
      }
    });
  },

  renderCurrentStageContent() {
    if (!this.currentCase) return;

    switch (this.activeStageTab) {
      case 'evidence':
        this.renderEvidenceDocs();
        break;
      case 'observations':
        this.renderObservations();
        break;
      case 'sufficiency':
        this.renderSufficiency();
        break;
      case 'reconciliation':
        this.renderReconciliation();
        break;
      case 'decision':
        this.renderDecision();
        break;
      case 'human-review':
        this.renderHumanReview();
        break;
      case 'audit-trace':
        this.renderAuditTrace();
        break;
      default:
        this.renderEvidenceDocs();
    }
  },

  // ─────────────────────────────────────────────────────────────
  // 1. EVIDENCE INGESTION (Phase 9B)
  // ─────────────────────────────────────────────────────────────
  renderEvidenceDocs() {
    const tbody = document.getElementById('evidence-docs-tbody');
    if (!tbody) return;
    const docs = this.currentCase.evidence_documents || [];

    if (docs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty-hint" style="text-align:center; padding: 20px; color: #64748b;">No evidence documents attached. Click "+ Add Document" or select a demo scenario.</td></tr>`;
      return;
    }

    tbody.innerHTML = docs.map((d) => `
      <tr>
        <td><strong class="font-mono" style="color: #15803d;">${d.document_id}</strong></td>
        <td><span style="font-weight: 600;">${d.filename}</span></td>
        <td><span class="badge-subtle" style="background:#f1f5f9; padding:2px 6px; border-radius:4px;">${d.document_type}</span></td>
        <td><span class="font-mono">${d.revision || 'Rev 0'}</span></td>
        <td><span class="status-tag healthy">${d.approval_status || 'APPROVED'}</span></td>
        <td><span class="preset-tag emerald">${d.authority_tier || 'APPROVED_AUTHORITATIVE'}</span></td>
        <td>
          <span class="status-tag ${d.extraction_status === 'EXTRACTED' ? 'healthy' : 'degraded'}">${d.extraction_status || 'PENDING'}</span>
        </td>
      </tr>
    `).join('');
  },

  async handleAddEvidenceForm() {
    if (!this.currentCaseId) return alert('Select or create a case first.');
    const fname = prompt('Enter document filename (e.g. E801_UT_Scan_2025.json or PSV201_Test.json):');
    if (!fname) return;
    const docType = prompt('Document Type (INSPECTION_REPORT, CALIBRATION_CERT, DATASHEET, MOC_RECORD):', 'INSPECTION_REPORT');
    const prop = prompt('Measured Property Name (e.g. shell_thickness_mm, set_pressure_barg):', 'shell_thickness_mm');
    const valStr = prompt('Measurement Value (numerical):', '10.9');
    const unit = prompt('Measurement Unit (mm, barg, degC):', 'mm');
    const date = prompt('Observation Date (YYYY-MM-DD):', '2025-04-20');
    const span = prompt('Verbatim Raw Statement / Source Span:', `Turnaround UT inspection at CML-01 recorded at ${valStr} ${unit}.`);

    const payload = {
      filename: fname,
      document_type: docType || 'INSPECTION_REPORT',
      revision: 'Rev 0',
      approval_status: 'APPROVED',
      authority_tier: 'APPROVED_AUTHORITATIVE',
      raw_content: {
        equipment_tag: this.currentCase.entity_tag,
        property_name: prop,
        value: parseFloat(valStr) || valStr,
        unit: unit,
        observation_date: date,
        measurement_location: 'CML-01',
        measurement_method: 'Ultrasonic Thickness Gauge',
        source_statement: span,
      }
    };

    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to register evidence');
      this.currentCase = await res.json();
      this.renderEvidenceDocs();
      this.showToast('Evidence document registered successfully.', 'success');
    } catch (err) {
      alert('Error adding evidence: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  async runObservationExtraction() {
    if (!this.currentCaseId) return;
    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/extract`, { method: 'POST' });
      if (!res.ok) throw new Error('Extraction failed');
      const data = await res.json();
      this.currentCase = data.case;
      this.showToast(`Extracted ${data.extracted_count} discrete observations!`, 'success');
      this.renderCaseOverview();
      this.switchStage('observations');
    } catch (err) {
      alert('Error during extraction: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  // ─────────────────────────────────────────────────────────────
  // 2. OBSERVATION & PROVENANCE INSPECTOR (Phase 9C)
  // ─────────────────────────────────────────────────────────────
  renderObservations() {
    const tbody = document.getElementById('observations-tbody');
    const counter = document.getElementById('obs-total-count');
    if (!tbody) return;

    const obsList = this.currentCase.extracted_observations || [];
    if (counter) counter.textContent = `${obsList.length} Discrete Records`;

    if (obsList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-hint" style="text-align:center; padding: 20px; color: #64748b;">No observations extracted yet. Click "Extract Observations →" from Stage 1.</td></tr>`;
      return;
    }

    tbody.innerHTML = obsList.map((obs, idx) => `
      <tr class="obs-row" style="cursor: pointer;" onclick="IntegrityManager.inspectProvenance(${idx})">
        <td><strong class="font-mono" style="color: #15803d;">${obs.observation_id}</strong></td>
        <td><strong>${obs.entity_tag}</strong></td>
        <td><span class="preset-tag cyan">${obs.property_name}</span></td>
        <td><strong style="color: #0f172a; font-size: 13px;">${obs.value} ${obs.unit || ''}</strong></td>
        <td><span class="font-mono text-muted">${obs.observation_date || 'N/A'}</span></td>
        <td><span style="font-size: 11px;">${obs.measurement_location || 'General'}</span></td>
        <td><span class="status-tag healthy">${obs.approval_status || 'APPROVED'}</span></td>
        <td>
          <button class="btn btn-secondary" style="font-size: 11px; padding: 3px 8px;" onclick="event.stopPropagation(); IntegrityManager.inspectProvenance(${idx})">
            Inspect Provenance →
          </button>
        </td>
      </tr>
    `).join('');
  },

  inspectProvenance(obsIndex) {
    const obsList = this.currentCase.extracted_observations || [];
    const obs = obsList[obsIndex];
    if (!obs) return;

    const drawer = document.getElementById('provenance-drawer');
    const content = document.getElementById('provenance-drawer-content');
    if (!drawer || !content) return;

    content.innerHTML = `
      <div class="provenance-detail-card" style="display: flex; flex-direction: column; gap: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px;">
          <div>
            <span class="preset-tag emerald">${obs.observation_id}</span>
            <h3 style="margin: 4px 0 0 0; font-size: 15px; color: #0f172a;">${obs.property_name}: <span style="color: #15803d;">${obs.value} ${obs.unit || ''}</span></h3>
          </div>
          <span class="preset-tag emerald">${obs.authority_tier || 'APPROVED_AUTHORITATIVE'}</span>
        </div>

        <div class="prov-grid-2">
          <div><strong>Entity Tag:</strong> ${obs.entity_tag}</div>
          <div><strong>Observation Date:</strong> ${obs.observation_date || 'Unknown (Not Fabricated)'}</div>
          <div><strong>Location:</strong> ${obs.measurement_location || 'Unspecified'}</div>
          <div><strong>Method:</strong> ${obs.measurement_method || 'Standard NDT'}</div>
          <div><strong>Source Document:</strong> <span class="font-mono">${obs.source_document}</span></div>
          <div><strong>Document ID:</strong> <span class="font-mono">${obs.document_id || 'N/A'}</span></div>
          <div><strong>Document Revision:</strong> ${obs.revision_number || 'Rev 0'}</div>
          <div><strong>Approval Status:</strong> ${obs.approval_status}</div>
          <div><strong>Extraction Method:</strong> ${obs.extraction_method}</div>
          <div><strong>Page / Section:</strong> Page ${obs.page_number || 1}, Sec: ${obs.section || 'General'}</div>
        </div>

        <div class="prov-quote-box">
          <div style="font-size: 11px; font-weight: 700; color: #15803d; margin-bottom: 4px;">Exact Verbatim Source Text Span:</div>
          <blockquote class="prov-quote">${obs.source_span || obs.raw_statement || 'N/A'}</blockquote>
        </div>

        <div class="prov-invariants-box">
          <span style="font-size: 16px;">🛡️</span>
          <span><strong>Safety Invariant:</strong> This measurement is stored non-destructively. It is NEVER averaged, smoothed, or overwritten by adjacent scans.</span>
        </div>
      </div>
    `;

    drawer.classList.add('open');
  },

  closeProvenanceDrawer() {
    const drawer = document.getElementById('provenance-drawer');
    if (drawer) drawer.classList.remove('open');
  },

  // ─────────────────────────────────────────────────────────────
  // 3. EVIDENCE SUFFICIENCY (Phase 9D)
  // ─────────────────────────────────────────────────────────────
  async runSufficiencyAssessment() {
    if (!this.currentCaseId) return;
    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/assess`, { method: 'POST' });
      if (!res.ok) throw new Error('Sufficiency assessment failed');
      this.currentCase = await res.json();
      this.renderCaseOverview();
      this.renderSufficiency();
      this.showToast('Evidence sufficiency assessed deterministically.', 'success');
    } catch (err) {
      alert('Error during assessment: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  renderSufficiency() {
    const container = document.getElementById('sufficiency-content');
    if (!container) return;
    const asmt = this.currentCase.evidence_assessment;

    if (!asmt) {
      container.innerHTML = `
        <div class="panel-card" style="text-align: center; padding: 30px;">
          <p style="color: #64748b; margin-bottom: 12px;">Evidence sufficiency has not yet been evaluated for this case.</p>
          <button class="btn btn-primary" onclick="IntegrityManager.runSufficiencyAssessment()">
            Run Phase 2 Sufficiency Assessment
          </button>
        </div>
      `;
      return;
    }

    const isSufficient = asmt.overall_status === 'SUFFICIENT';

    container.innerHTML = `
      <div class="panel-card" style="border-left: 4px solid ${isSufficient ? '#16a34a' : '#ef4444'}; margin-bottom: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Sufficiency Status</div>
            <h2 style="font-size: 18px; font-weight: 800; color: ${isSufficient ? '#15803d' : '#dc2626'}; margin: 2px 0 0 0;">${asmt.overall_status}</h2>
          </div>
          <div style="text-align: right;">
            <span style="font-size: 22px; font-weight: 800; color: #15803d;">${Math.round(asmt.coverage_score * 100)}%</span>
            <div style="font-size: 10.5px; color: #64748b;">Coverage Ratio</div>
          </div>
        </div>
        <p style="font-size: 12px; color: #334155; margin: 0;"><strong>System Guidance:</strong> ${asmt.system_recommendation || 'Evidence meets mandatory engineering requirements.'}</p>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
        <!-- Checklist & Requirements -->
        <div class="panel-card">
          <div class="section-title-txt" style="margin-bottom: 10px;">Mandatory Engineering Checklist</div>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${(asmt.evidence_checklist || []).map(item => `
              <div style="display: flex; align-items: center; justify-content: space-between; background: #f8fafc; padding: 8px 10px; border-radius: 6px; border: 1px solid #e2e8f0;">
                <div>
                  <strong style="font-size: 12px; color: #0f172a;">${item.name || item.evidence_type}</strong>
                  <div style="font-size: 11px; color: #64748b;">${item.description || item.matched_source || 'Required parameter'}</div>
                </div>
                <span class="preset-tag ${item.satisfied ? 'emerald' : 'ruby'}">
                  ${item.satisfied ? 'SATISFIED' : 'MISSING'}
                </span>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Evidence Debt & Blockers -->
        <div class="panel-card">
          <div class="section-title-txt" style="margin-bottom: 10px;">Evidence Debt & Contradictions</div>
          <div style="font-size: 12px; display: flex; gap: 14px; margin-bottom: 12px;">
            <div>Missing Mandatory: <strong>${asmt.evidence_debt ? asmt.evidence_debt.missing_mandatory_count : 0}</strong></div>
            <div>Contradictions: <strong>${(asmt.contradictions || []).length}</strong></div>
          </div>

          ${(asmt.blocking_reasons || []).length > 0 ? `
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 10px; margin-bottom: 8px;">
              <strong style="color: #dc2626; font-size: 11.5px;">Blocking Execution Reasons:</strong>
              <ul style="margin: 4px 0 0 16px; font-size: 11.5px; color: #991b1b;">
                ${asmt.blocking_reasons.map(r => `<li>${r}</li>`).join('')}
              </ul>
            </div>
          ` : `
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px; font-size: 11.5px; color: #166534;">
              <span>✓ Zero blocking evidence debt. Deterministic gate clear to proceed.</span>
            </div>
          `}

          ${(asmt.contradictions || []).length > 0 ? `
            <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 10px; margin-top: 8px;">
              <strong style="color: #b45309; font-size: 11.5px;">Contradictions Detected:</strong>
              <ul style="margin: 4px 0 0 16px; font-size: 11.5px; color: #92400e;">
                ${asmt.contradictions.map(c => `<li>${c}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  },

  // ─────────────────────────────────────────────────────────────
  // 4. MULTI-OBSERVATION RECONCILIATION (Phase 9E)
  // ─────────────────────────────────────────────────────────────
  async runReconciliation() {
    if (!this.currentCaseId) return;
    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/reconcile`, { method: 'POST' });
      if (!res.ok) throw new Error('Reconciliation failed');
      this.currentCase = await res.json();
      this.renderCaseOverview();
      this.renderReconciliation();
      this.showToast('Reconciliation completed.', 'success');
    } catch (err) {
      alert('Error during reconciliation: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  renderReconciliation() {
    const container = document.getElementById('reconciliation-content');
    if (!container) return;
    const rec = this.currentCase.reconciliation_result;

    if (!rec) {
      container.innerHTML = `
        <div class="panel-card" style="text-align: center; padding: 30px;">
          <p style="color: #64748b; margin-bottom: 12px;">Reconciliation engine has not been executed for this case.</p>
          <button class="btn btn-primary" onclick="IntegrityManager.runReconciliation()">
            Run Phase 3 Reconciliation Engine
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="panel-card" style="margin-bottom: 14px; background: linear-gradient(135deg, #ffffff, #f0fdf4); border: 1.5px solid #16a34a;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div>
            <h3 style="margin: 0; font-size: 16px; color: #0f172a;">Multi-Observation Reconciliation</h3>
            <div style="font-size: 11.5px; color: #64748b; margin-top: 2px;">
              Status: <strong style="color: #15803d;">${rec.reconciliation_status}</strong> &nbsp;•&nbsp; Consistency: <strong>${rec.consistency_state}</strong>
            </div>
          </div>
          <div style="display: flex; gap: 8px;">
            <span class="preset-tag emerald">Obs: ${rec.all_observations ? rec.all_observations.length : 0}</span>
            <span class="preset-tag emerald">Relationships: ${rec.relationships ? rec.relationships.length : 0}</span>
            <span class="preset-tag ${rec.active_conflicts && rec.active_conflicts.length > 0 ? 'ruby' : 'emerald'}">
              Conflicts: ${rec.active_conflicts ? rec.active_conflicts.length : 0}
            </span>
          </div>
        </div>
        <p style="font-size: 12px; color: #334155; margin: 0;">${rec.reconciliation_summary || 'Multi-observation timeline analyzed.'}</p>
      </div>

      <!-- Relationships List -->
      <div class="panel-card">
        <div class="section-title-txt" style="margin-bottom: 10px;">Identified Evidence Relationships & Temporal Progressions</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 10px;">
          ${(rec.relationships || []).map(rel => `
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span class="preset-tag ${rel.is_anomaly ? 'ruby' : 'emerald'}">${rel.relationship_type}</span>
                <span class="font-mono text-muted" style="font-size: 11px;">${rel.property_name}</span>
              </div>
              <p style="font-size: 11.5px; color: #1e293b; margin: 0 0 8px 0;">${rel.explanation}</p>
              <div style="display: flex; justify-content: space-between; font-size: 10.5px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 4px;">
                <span>Search: ${rel.evidence_search_status}</span>
                <span class="font-mono">Obs: ${(rel.observation_ids || []).join(', ')}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  },

  // ─────────────────────────────────────────────────────────────
  // 5. DECISION EVALUATION (Phase 9F)
  // ─────────────────────────────────────────────────────────────
  async runDecisionEvaluation() {
    if (!this.currentCaseId) return;
    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/evaluate`, { method: 'POST' });
      if (!res.ok) throw new Error('Decision evaluation failed');
      this.currentCase = await res.json();
      this.renderCaseOverview();
      this.renderDecision();
      this.showToast('Decision evaluated through Phase 4 Decision Engine.', 'success');
    } catch (err) {
      alert('Error evaluating decision: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  renderDecision() {
    const container = document.getElementById('decision-content');
    if (!container) return;
    const pkg = this.currentCase.decision_package;

    if (!pkg) {
      container.innerHTML = `
        <div class="panel-card" style="text-align: center; padding: 30px;">
          <p style="color: #64748b; margin-bottom: 12px;">Phase 4 DecisionEngine has not evaluated this case yet.</p>
          <button class="btn btn-primary" onclick="IntegrityManager.runDecisionEvaluation()">
            Run Phase 4 Decision Engine
          </button>
        </div>
      `;
      return;
    }

    const isBlocked = pkg.governance_outcome === 'GOVERNANCE_GATE_BLOCKED';

    container.innerHTML = `
      <div class="panel-card" style="border-left: 4px solid ${isBlocked ? '#ef4444' : '#16a34a'}; margin-bottom: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Governance Outcome</div>
            <h2 style="font-size: 18px; font-weight: 800; color: ${isBlocked ? '#dc2626' : '#15803d'}; margin: 2px 0 0 0;">${pkg.governance_outcome}</h2>
          </div>
          <div style="display: flex; gap: 8px;">
            <span class="preset-tag cyan">Policy: ${pkg.policy_evaluation_status}</span>
            <span class="preset-tag ${String(pkg.risk_level).toLowerCase()}">Risk: ${pkg.risk_level}</span>
          </div>
        </div>

        <div style="background: #f8fafc; border-radius: 6px; padding: 10px 12px; margin: 8px 0; border: 1px solid #e2e8f0;">
          <strong style="font-size: 11.5px; color: #0f172a;">Recommended Action / Governance Notice:</strong>
          <p style="font-size: 12px; color: #334155; margin: 4px 0 0 0;">${pkg.recommended_action || 'Advisory assessment completed.'}</p>
        </div>

        <div class="prov-invariants-box" style="margin-top: 8px;">
          <span style="font-size: 16px;">🛡️</span>
          <span><strong>Safety Boundary:</strong> This decision is advisory and read-only. Zero automated actuation or live plant DCS write capability exists.</span>
        </div>
      </div>

      <!-- Rule Evaluations Matrix -->
      <div class="panel-card">
        <div class="section-title-txt" style="margin-bottom: 10px;">Statutory Governance Rules Evaluated</div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Rule ID</th>
              <th>Rule Description</th>
              <th>Result</th>
              <th>Gate Type</th>
              <th>Details / Remarks</th>
            </tr>
          </thead>
          <tbody>
            ${(pkg.rule_evaluations || []).map(r => `
              <tr>
                <td><strong class="font-mono">${r.rule_id}</strong></td>
                <td>${r.rule_name || r.description || 'Statutory Criterion'}</td>
                <td><span class="preset-tag ${r.passed ? 'emerald' : 'ruby'}">${r.passed ? 'PASSED' : 'BLOCKED'}</span></td>
                <td><span class="preset-tag ${r.is_blocking_gate ? 'ruby' : 'cyan'}">${r.is_blocking_gate ? 'BLOCKING' : 'ADVISORY'}</span></td>
                <td class="text-xs text-muted">${r.details || r.rationale || 'Evaluated deterministically'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  },

  // ─────────────────────────────────────────────────────────────
  // 6. HUMAN-IN-THE-LOOP REVIEW (Phase 9G)
  // ─────────────────────────────────────────────────────────────
  async generateApprovalPackage() {
    if (!this.currentCaseId) return;
    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/approval-package`, { method: 'POST' });
      if (!res.ok) throw new Error('Package generation failed');
      this.currentCase = await res.json();
      this.renderCaseOverview();
      this.renderHumanReview();
      this.showToast('Decision Approval Package generated for review.', 'success');
    } catch (err) {
      alert('Error generating package: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  renderHumanReview() {
    const container = document.getElementById('human-review-content');
    if (!container) return;
    const deliv = this.currentCase.approval_deliverable;

    if (!deliv) {
      container.innerHTML = `
        <div class="panel-card" style="text-align: center; padding: 30px;">
          <p style="color: #64748b; margin-bottom: 12px;">Approval Deliverable has not been generated for this case.</p>
          <button class="btn btn-primary" onclick="IntegrityManager.generateApprovalPackage()">
            Generate HITL Approval Package
          </button>
        </div>
      `;
      return;
    }

    const state = this.currentCase.human_approval_state || 'PENDING';
    const isApproved = state === 'APPROVED';

    container.innerHTML = `
      <div class="panel-card" style="margin-bottom: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; margin-bottom: 12px;">
          <div>
            <span class="preset-tag emerald font-mono">${deliv.deliverable_id}</span>
            <h3 style="margin: 4px 0 0 0; font-size: 16px; color: #0f172a;">Engineering Review & Workflow Sign-Off</h3>
          </div>
          <span class="preset-tag ${isApproved ? 'emerald' : 'ruby'}">${state}</span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px; margin-bottom: 12px;">
          <div><strong>Entity Tag:</strong> ${deliv.entity_tag}</div>
          <div><strong>Required Reviewer Roles:</strong> <span class="font-mono text-emerald">${(deliv.required_human_roles || []).join(', ') || 'Chief Inspection Engineer'}</span></div>
          <div><strong>Governance Outcome:</strong> ${deliv.governance_outcome}</div>
          <div><strong>Audit Trail Hash:</strong> <span class="font-mono text-xs">${(deliv.audit_trail_hash || '').substring(0, 24)}...</span></div>
        </div>

        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; margin-bottom: 14px;">
          <strong style="font-size: 11.5px; color: #15803d;">Deliverable Executive Summary:</strong>
          <pre style="margin-top: 6px; font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap; color: #334155;">${deliv.deliverable_summary || 'Review package prepared for engineering inspection.'}</pre>
        </div>

        <!-- Human Disposition Form -->
        <div style="border-top: 1px solid #e2e8f0; padding-top: 12px;">
          <div class="section-title-txt" style="margin-bottom: 8px;">Reviewer Disposition & Sign-Off</div>
          ${isApproved ? `
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px;">
              <strong style="color: #15803d; font-size: 12.5px;">✓ Signed Off by ${this.currentCase.reviewed_by || 'Engineer'}:</strong>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #166534;">${this.currentCase.reviewer_notes || 'Approved according to standard operating criteria.'}</p>
            </div>
          ` : `
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <input type="text" id="disp-reviewer-name" class="form-input" placeholder="Your Name & Designation (e.g. Chief Inspection Engineer)" value="Chief Inspection Engineer">
              <textarea id="disp-notes" class="form-input" rows="2" placeholder="Mandatory engineering remarks and verification justification..."></textarea>
              <div style="display: flex; gap: 8px; margin-top: 4px;">
                <button class="btn btn-primary" onclick="IntegrityManager.submitDisposition('APPROVE')">
                  ✓ Approve (Workflow Sign-off)
                </button>
                <button class="btn btn-secondary" onclick="IntegrityManager.submitDisposition('REQUEST_REVISION')">
                  ↺ Request Revision
                </button>
                <button class="btn btn-secondary" style="color: #dc2626;" onclick="IntegrityManager.submitDisposition('REJECT')">
                  ✕ Reject / Block
                </button>
              </div>
            </div>
            <p class="text-xs text-muted" style="margin-top: 8px;">
              * Note: Human approval records administrative engineering workflow sign-off. It never automatically executes physical plant control or grants unverified statutory clearances.
            </p>
          `}
        </div>
      </div>
    `;
  },

  async submitDisposition(action) {
    if (!this.currentCaseId) return;
    const nameEl = document.getElementById('disp-reviewer-name');
    const notesEl = document.getElementById('disp-notes');
    const name = nameEl ? nameEl.value.trim() : 'Chief Inspection Engineer';
    const notes = notesEl ? notesEl.value.trim() : '';

    if (!name) return alert('Please enter reviewer name.');

    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/disposition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          reviewer_name: name,
          notes: notes,
        }),
      });
      if (!res.ok) throw new Error('Failed to record disposition');
      this.currentCase = await res.json();
      this.renderCaseOverview();
      this.renderHumanReview();
      this.showToast(`Workflow disposition '${action}' recorded.`, 'success');
    } catch (err) {
      alert('Error submitting disposition: ' + err.message);
    } finally {
      this.setLoading(false);
    }
  },

  // ─────────────────────────────────────────────────────────────
  // 7. COMPLETE AUDIT TRACE (Phase 9H)
  // ─────────────────────────────────────────────────────────────
  async renderAuditTrace() {
    const container = document.getElementById('audit-trace-content');
    if (!container || !this.currentCaseId) return;

    try {
      this.setLoading(true);
      const res = await fetch(`/api/integrity/cases/${this.currentCaseId}/audit-trace`);
      if (!res.ok) throw new Error('Failed to fetch audit trace');
      const rootNode = await res.json();
      this.auditTraceTree = rootNode;

      container.innerHTML = `
        <div class="trace-tree-wrapper">
          <div class="trace-tree-header">
            <div>
              <h3 style="margin:0; font-size: 15px;">7-Tier Hierarchical Audit Lineage</h3>
              <p class="text-xs text-muted" style="margin: 2px 0 0 0;">Complete provenance linking the final decision down to verbatim source document text spans.</p>
            </div>
            <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 10px;" onclick="IntegrityManager.expandAllTraceNodes()">Expand All</button>
          </div>
          <div class="trace-nodes-container" id="trace-nodes-tree" style="margin-top: 12px;">
            ${this.renderTraceNodeHtml(rootNode, 0)}
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `<div class="empty-hint" style="padding: 20px; color: #64748b;">Audit trace not yet available: ${err.message}</div>`;
    } finally {
      this.setLoading(false);
    }
  },

  renderTraceNodeHtml(node, depth = 0) {
    const hasChildren = node.children && node.children.length > 0;
    const nodeTypeClass = (node.node_type || '').toLowerCase().replace(/_/g, '-');

    const detailsStr = Object.entries(node.details || {})
      .map(([k, v]) => `<div><span class="detail-k">${k}:</span> <span class="detail-v">${typeof v === 'object' ? JSON.stringify(v) : v}</span></div>`)
      .join('');

    return `
      <div class="trace-node-item depth-${depth}">
        <div class="trace-node-header" onclick="this.parentElement.classList.toggle('expanded')">
          <span class="tree-caret" style="font-size: 10px; color: #64748b; width: 12px;">${hasChildren ? '▼' : '•'}</span>
          <span class="node-type-badge type-${nodeTypeClass}">${node.node_type}</span>
          <span class="node-title" style="font-weight: 600; font-size: 12px; margin-left: 6px;">${node.title}</span>
          ${node.status ? `<span class="preset-tag emerald" style="font-size: 10px; margin-left: 8px;">${node.status}</span>` : ''}
          <span class="font-mono text-muted" style="font-size: 10.5px; margin-left: auto;">${node.node_id}</span>
        </div>
        <div class="trace-node-body">
          ${detailsStr ? `<div class="trace-details-grid">${detailsStr}</div>` : ''}
          ${hasChildren ? `
            <div class="trace-children">
              ${node.children.map(ch => this.renderTraceNodeHtml(ch, depth + 1)).join('')}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  },

  expandAllTraceNodes() {
    document.querySelectorAll('.trace-node-item').forEach(el => el.classList.add('expanded'));
  },

  setLoading(isLoading) {
    const loader = document.getElementById('integrity-loader');
    if (loader) loader.style.display = isLoading ? 'flex' : 'none';
  },

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `integrity-toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
};

window.IntegrityManager = IntegrityManager;
