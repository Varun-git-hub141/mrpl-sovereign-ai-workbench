/**
 * MRPL Sovereign AI Workbench — Phase 10B Dynamic Asset Registry & Hierarchy Manager
 * Handles interactive 10-tier hierarchy navigation, asset dossier display,
 * dynamic asset creation modal, document upload & incremental indexing,
 * component/location additions, observation inspection, and audit trail rendering.
 */

const AssetRegistryManager = {
  activeAssetTag: "P-201",
  activeAssetData: null,
  activeDossierData: null,
  hierarchyTree: null,
  assetList: [],
  selectedClassFilter: "all",
  selectedUnitFilter: "all",
  searchQuery: "",

  async init() {
    console.log("Initializing MRPL Dynamic Asset Registry...");
    await this.loadHierarchy();
    await this.loadAssetList();
    this.bindEvents();
    if (this.activeAssetTag) {
      await this.selectAsset(this.activeAssetTag);
    }
  },

  bindEvents() {
    const searchInput = document.getElementById("asset-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        this.searchQuery = e.target.value.toLowerCase().trim();
        this.renderAssetCards();
      });
    }

    const classFilter = document.getElementById("asset-class-filter");
    if (classFilter) {
      classFilter.addEventListener("change", (e) => {
        this.selectedClassFilter = e.target.value;
        this.renderAssetCards();
      });
    }

    const unitFilter = document.getElementById("asset-unit-filter");
    if (unitFilter) {
      unitFilter.addEventListener("change", (e) => {
        this.selectedUnitFilter = e.target.value;
        this.renderAssetCards();
      });
    }
  },

  async loadHierarchy() {
    try {
      const res = await fetch("/api/assets/hierarchy");
      if (!res.ok) throw new Error("Failed to fetch hierarchy");
      this.hierarchyTree = await res.json();
      this.renderHierarchyTree();
    } catch (err) {
      console.error("Error loading asset hierarchy:", err);
    }
  },

  async loadAssetList() {
    try {
      const res = await fetch("/api/assets");
      if (!res.ok) throw new Error("Failed to fetch asset list");
      const data = await res.json();
      this.assetList = data.assets || [];
      this.renderAssetCards();
    } catch (err) {
      console.error("Error loading asset list:", err);
    }
  },

  renderHierarchyTree() {
    const container = document.getElementById("hierarchy-tree-container");
    if (!container || !this.hierarchyTree) return;

    let html = '<div class="hierarchy-root-node">';
    html += this.renderNodeHtml(this.hierarchyTree, 0);
    html += '</div>';
    container.innerHTML = html;
  },

  renderNodeHtml(node, depth) {
    if (!node) return "";
    const hasChildren = node.children && node.children.length > 0;
    const isAsset = node.node_type === "asset" || node.node_type === "ASSET";
    const isObs = node.node_type === "observation";
    const isMsr = node.node_type === "measurement";
    const isProv = node.node_type === "provenance";
    const isExpanded = depth < 3; // Auto-expand down to asset class

    let icon = "🏢";
    if (node.node_type === "refinery") icon = "🏭";
    else if (node.node_type === "process_unit") icon = "⚙️";
    else if (node.node_type === "asset_class") icon = "📦";
    else if (isAsset) icon = "🔧";
    else if (node.node_type === "component") icon = "🔩";
    else if (node.node_type === "location") icon = "📍";
    else if (isObs) icon = "🔍";
    else if (isMsr) icon = "📏";
    else if (isProv) icon = "📜";

    const isSelected = isAsset && node.asset_tag === this.activeAssetTag ? "selected-node" : "";

    let nodeHtml = `
      <div class="hierarchy-item depth-${depth} ${isSelected}" style="padding-left: ${depth * 14}px;">
        <div class="hierarchy-label-row" onclick="AssetRegistryManager.handleNodeClick('${node.id}', '${node.node_type}', '${node.asset_tag || ''}')">
          ${hasChildren ? `<span class="tree-caret ${isExpanded ? 'open' : ''}" onclick="event.stopPropagation(); AssetRegistryManager.toggleNode(this)">▶</span>` : '<span class="tree-bullet">•</span>'}
          <span class="tree-icon">${icon}</span>
          <span class="tree-text ${isAsset ? 'font-bold' : ''}">${node.label || node.id}</span>
          ${node.status ? `<span class="badge badge-status badge-${node.status.toLowerCase()}">${node.status}</span>` : ''}
        </div>
    `;

    if (hasChildren) {
      nodeHtml += `<div class="tree-children" style="display: ${isExpanded ? 'block' : 'none'};">`;
      for (const child of node.children) {
        nodeHtml += this.renderNodeHtml(child, depth + 1);
      }
      nodeHtml += `</div>`;
    }

    nodeHtml += `</div>`;
    return nodeHtml;
  },

  toggleNode(caretEl) {
    const parent = caretEl.closest(".hierarchy-item");
    const childrenDiv = parent.querySelector(":scope > .tree-children");
    if (childrenDiv) {
      if (childrenDiv.style.display === "none") {
        childrenDiv.style.display = "block";
        caretEl.classList.add("open");
      } else {
        childrenDiv.style.display = "none";
        caretEl.classList.remove("open");
      }
    }
  },

  handleNodeClick(nodeId, nodeType, assetTag) {
    if (assetTag) {
      this.selectAsset(assetTag);
    }
  },

  renderAssetCards() {
    const container = document.getElementById("asset-grid-container");
    if (!container) return;

    let filtered = this.assetList.filter(a => {
      const matchClass = this.selectedClassFilter === "all" || a.asset_class === this.selectedClassFilter;
      const matchUnit = this.selectedUnitFilter === "all" || a.process_unit === this.selectedUnitFilter;
      const matchSearch = !this.searchQuery || 
        a.asset_tag.toLowerCase().includes(this.searchQuery) ||
        a.asset_name.toLowerCase().includes(this.searchQuery) ||
        (a.service_description && a.service_description.toLowerCase().includes(this.searchQuery));
      return matchClass && matchUnit && matchSearch;
    });

    const countEl = document.getElementById("asset-total-count");
    if (countEl) countEl.textContent = `${filtered.length} Registered Assets`;

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state-card">
          <span style="font-size: 28px;">🔍</span>
          <p>No matching assets found in MRPL Registry.</p>
          <button class="btn btn-primary" onclick="AssetRegistryManager.openAddAssetModal()">+ Register New Asset</button>
        </div>
      `;
      return;
    }

    let html = "";
    for (const a of filtered) {
      const isSelected = a.asset_tag === this.activeAssetTag ? "active-card" : "";
      const classIcon = this.getClassIcon(a.asset_class);
      const docsCount = a.documents_manifest ? a.documents_manifest.length : 0;
      const compCount = a.components ? a.components.length : 0;

      html += `
        <div class="asset-summary-card ${isSelected}" onclick="AssetRegistryManager.selectAsset('${a.asset_tag}')">
          <div class="card-header-row">
            <div class="card-tag-wrap">
              <span class="asset-class-badge">${classIcon} ${a.asset_class}</span>
              <h3 class="asset-tag-heading">${a.asset_tag}</h3>
            </div>
            <span class="status-pill status-${(a.status || 'IN_SERVICE').toLowerCase()}">${a.status || 'IN_SERVICE'}</span>
          </div>
          <div class="asset-name-line">${a.asset_name}</div>
          <div class="asset-service-line">📌 ${a.service_description || 'General Hydrocarbon Service'}</div>
          <div class="asset-meta-footer">
            <span>🏭 ${a.process_unit}</span>
            <span>📄 ${docsCount} Docs</span>
            <span>🔩 ${compCount} Components</span>
          </div>
        </div>
      `;
    }

    container.innerHTML = html;
  },

  getClassIcon(assetClass) {
    const map = {
      "PUMP": "⚡",
      "PRESSURE_VESSEL": "🛢️",
      "STORAGE_TANK": "🏗️",
      "VALVE": "🚰",
      "HEAT_EXCHANGER": "🔄",
      "COMPRESSOR": "💨",
      "COLUMN": "🏛️",
      "REACTOR": "⚛️",
      "FIRED_HEATER": "🔥",
      "PIPING": "➰",
      "INSTRUMENT": "📟",
      "ELECTRICAL": "🔌",
      "OTHER": "⚙️"
    };
    return map[assetClass] || "⚙️";
  },

  async selectAsset(tag) {
    this.activeAssetTag = tag;
    this.renderAssetCards();

    // Highlight in tree
    const treeItems = document.querySelectorAll(".hierarchy-item");
    treeItems.forEach(el => el.classList.remove("selected-node"));

    const dossierContainer = document.getElementById("asset-dossier-container");
    if (dossierContainer) {
      dossierContainer.innerHTML = `
        <div class="loading-state-card">
          <div class="spinner"></div>
          <span>Loading Engineering Dossier for ${tag}...</span>
        </div>
      `;
    }

    try {
      const res = await fetch(`/api/assets/${encodeURIComponent(tag)}/dossier`);
      if (!res.ok) throw new Error("Failed to load dossier");
      this.activeDossierData = await res.json();
      this.activeAssetData = this.activeDossierData.asset;
      this.renderAssetDossier();
    } catch (err) {
      console.error("Error loading dossier:", err);
      if (dossierContainer) {
        dossierContainer.innerHTML = `
          <div class="error-state-card">
            <h4>Error Loading Dossier</h4>
            <p>${err.message}</p>
          </div>
        `;
      }
    }
  },

  renderAssetDossier() {
    const container = document.getElementById("asset-dossier-container");
    if (!container || !this.activeDossierData) return;

    const d = this.activeDossierData;
    const a = d.asset;
    const classIcon = this.getClassIcon(a.asset_class);

    let html = `
      <!-- DOSSIER HEADER -->
      <div class="dossier-header-banner">
        <div class="dossier-title-group">
          <div class="dossier-badge-row">
            <span class="asset-class-badge large">${classIcon} ${a.asset_class}</span>
            <span class="asset-id-badge">ID: ${a.asset_id}</span>
            <span class="status-pill status-${(a.status || 'IN_SERVICE').toLowerCase()}">${a.status || 'IN_SERVICE'}</span>
            <span class="data-status-badge">DEMO DATA</span>
          </div>
          <h1 class="dossier-main-tag">${a.asset_tag} — ${a.asset_name}</h1>
          <div class="dossier-hierarchy-path">
            <span>🌐 Hierarchy:</span> <strong>${d.hierarchy_path}</strong>
          </div>
        </div>
        <div class="dossier-actions-group">
          <button class="btn btn-primary" onclick="AssetRegistryManager.openUploadDocModal('${a.asset_tag}')">
            📤 Add Document
          </button>
          <button class="btn btn-secondary" onclick="AssetRegistryManager.openAddComponentModal('${a.asset_tag}')">
            + Component
          </button>
          <button class="btn btn-secondary" onclick="AssetRegistryManager.openAddLocationModal('${a.asset_tag}')">
            + Inspection Location
          </button>
        </div>
      </div>

      <!-- DOSSIER TABS -->
      <div class="dossier-tabs-nav">
        <button class="dossier-tab-btn active" onclick="AssetRegistryManager.switchDossierTab('specifications')">📋 Technical Specs</button>
        <button class="dossier-tab-btn" onclick="AssetRegistryManager.switchDossierTab('documents')">📄 Documents (${d.total_documents})</button>
        <button class="dossier-tab-btn" onclick="AssetRegistryManager.switchDossierTab('observations')">🔍 Observations (${d.observations.length})</button>
        <button class="dossier-tab-btn" onclick="AssetRegistryManager.switchDossierTab('components')">🔩 Components (${a.components ? a.components.length : 0})</button>
        <button class="dossier-tab-btn" onclick="AssetRegistryManager.switchDossierTab('audit')">📜 Audit Trail (${d.audit_trail ? d.audit_trail.length : 0})</button>
      </div>

      <!-- TAB CONTENTS -->
      <div class="dossier-tab-contents">

        <!-- 1. SPECIFICATIONS TAB -->
        <div id="dossier-tab-specifications" class="dossier-tab-pane active">
          <div class="specs-grid">
            <div class="spec-card">
              <div class="spec-card-title">General Information</div>
              <div class="spec-row"><span class="spec-label">Asset Tag:</span> <span class="spec-val font-mono">${a.asset_tag}</span></div>
              <div class="spec-row"><span class="spec-label">Internal Asset ID:</span> <span class="spec-val font-mono">${a.asset_id}</span></div>
              <div class="spec-row"><span class="spec-label">Refinery:</span> <span class="spec-val">${a.refinery}</span></div>
              <div class="spec-row"><span class="spec-label">Process Unit:</span> <span class="spec-val font-bold">${a.process_unit}</span></div>
              <div class="spec-row"><span class="spec-label">Operating Service:</span> <span class="spec-val">${a.service_description}</span></div>
              <div class="spec-row"><span class="spec-label">Design Code:</span> <span class="spec-val">${a.design_code || 'API / ASME'}</span></div>
              <div class="spec-row"><span class="spec-label">Commissioned:</span> <span class="spec-val">${a.commissioning_date || '2020-01-01'}</span></div>
            </div>

            <div class="spec-card">
              <div class="spec-card-title">Class-Specific Attributes (${a.asset_class})</div>
              ${this.renderClassAttributes(a.class_attributes)}
            </div>
          </div>
        </div>

        <!-- 2. DOCUMENTS TAB -->
        <div id="dossier-tab-documents" class="dossier-tab-pane">
          <div class="docs-manifest-view">
            ${this.renderDocumentsManifest(d.documents_by_category)}
          </div>
        </div>

        <!-- 3. OBSERVATIONS TAB -->
        <div id="dossier-tab-observations" class="dossier-tab-pane">
          <div class="observations-view">
            ${this.renderObservationsTable(d.observations)}
          </div>
        </div>

        <!-- 4. COMPONENTS TAB -->
        <div id="dossier-tab-components" class="dossier-tab-pane">
          <div class="components-grid">
            ${this.renderComponentsAndLocations(a)}
          </div>
        </div>

        <!-- 5. AUDIT TRAIL TAB -->
        <div id="dossier-tab-audit" class="dossier-tab-pane">
          <div class="audit-timeline">
            ${this.renderAuditTimeline(d.audit_trail)}
          </div>
        </div>

      </div>
    `;

    container.innerHTML = html;
  },

  renderClassAttributes(attrs) {
    if (!attrs || Object.keys(attrs).length === 0) {
      return '<div class="text-muted" style="padding: 10px 0;">No custom class-specific parameters configured.</div>';
    }

    let html = '<div class="class-attrs-list">';
    for (const [key, val] of Object.entries(attrs)) {
      const prettyKey = key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
      html += `
        <div class="spec-row">
          <span class="spec-label">${prettyKey}:</span>
          <span class="spec-val font-mono font-bold">${val}</span>
        </div>
      `;
    }
    html += '</div>';
    return html;
  },

  renderDocumentsManifest(docsByCat) {
    if (!docsByCat || Object.keys(docsByCat).length === 0) {
      return '<div class="empty-card-msg">No documents linked to this asset. Click "Add Document" to upload.</div>';
    }

    let html = "";
    for (const [cat, docList] of Object.entries(docsByCat)) {
      html += `
        <div class="doc-category-block">
          <h3 class="category-heading">📁 ${cat} (${docList.length})</h3>
          <div class="category-doc-cards">
      `;

      for (const doc of docList) {
        html += `
          <div class="doc-manifest-card">
            <div class="doc-card-top">
              <div class="doc-title-row">
                <span class="doc-icon">📄</span>
                <div>
                  <h4 class="doc-title-text">${doc.title}</h4>
                  <span class="doc-id-pill">${doc.document_id}</span>
                </div>
              </div>
              <span class="doc-authority-badge">${doc.authority || 'Authority Level A'}</span>
            </div>
            <div class="doc-card-meta">
              <span>📅 Date: ${doc.date}</span>
              <span>🏷️ Rev: ${doc.revision || 'R0'}</span>
              <span>🛡️ Status: <strong class="text-green">${doc.approval_status || 'APPROVED'}</strong></span>
              <span>📍 Section: ${doc.section || 'General'} (p.${doc.page || 1})</span>
            </div>
          </div>
        `;
      }

      html += `
          </div>
        </div>
      `;
    }

    return html;
  },

  renderObservationsTable(obsList) {
    if (!obsList || obsList.length === 0) {
      return '<div class="empty-card-msg">No extracted engineering observations registered.</div>';
    }

    let html = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Observation Date</th>
            <th>Location / Component</th>
            <th>Type</th>
            <th>Measurements & Values</th>
            <th>Summary / Findings</th>
            <th>Provenance Lineage</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const obs of obsList) {
      const msrsHtml = obs.measurements.map(m => `
        <div class="measurement-chip">
          <span class="msr-type">${m.measurement_type}:</span>
          <span class="msr-val font-mono font-bold">${m.value} ${m.unit}</span>
          ${m.is_within_limits ? '<span class="text-green">✓</span>' : '<span class="text-red">⚠️</span>'}
        </div>
      `).join("");

      const prov = obs.provenance;
      const provInfo = `
        <div class="provenance-cell" onclick='AssetRegistryManager.showProvenanceModal(${JSON.stringify(prov).replace(/'/g, "&apos;")})'>
          <span class="prov-doc font-bold">${prov.document_id}</span>
          <span class="prov-sub">${prov.section} (p.${prov.page})</span>
          <span class="prov-span-preview">🔍 View exact text span</span>
        </div>
      `;

      html += `
        <tr>
          <td class="font-mono">${obs.observation_date}</td>
          <td><strong>${obs.inspection_location}</strong><br><small class="text-muted">${obs.component_name}</small></td>
          <td><span class="badge badge-info">${obs.observation_type}</span></td>
          <td>${msrsHtml || '<span class="text-muted">None</span>'}</td>
          <td>${obs.findings_summary}</td>
          <td>${provInfo}</td>
        </tr>
      `;
    }

    html += `</tbody></table>`;
    return html;
  },

  renderComponentsAndLocations(asset) {
    let html = '<div class="components-layout">';

    if (asset.components && asset.components.length > 0) {
      html += '<div class="comp-col"><h3>Components</h3>';
      for (const c of asset.components) {
        html += `
          <div class="component-card">
            <div class="comp-header">
              <span class="comp-name font-bold">🔩 ${c.component_name}</span>
              <span class="badge badge-crit-${(c.criticality || 'HIGH').toLowerCase()}">${c.criticality}</span>
            </div>
            <div class="comp-id font-mono">${c.component_id}</div>
            ${c.material_of_construction ? `<div class="comp-meta">Material: ${c.material_of_construction}</div>` : ''}
          </div>
        `;
      }
      html += '</div>';
    }

    if (asset.inspection_locations && asset.inspection_locations.length > 0) {
      html += '<div class="loc-col"><h3>Condition Monitoring & Inspection Locations</h3>';
      for (const loc of asset.inspection_locations) {
        html += `
          <div class="location-card">
            <div class="loc-header">
              <span class="loc-name font-bold">📍 ${loc.location_name}</span>
              <span class="badge badge-method">${loc.inspection_method || 'UT'}</span>
            </div>
            <div class="loc-id font-mono">${loc.location_id}</div>
            <div class="loc-meta">Linked Component: ${loc.component_name || 'Main Body'}</div>
            ${loc.nominal_thickness_mm ? `<div class="loc-meta">Nominal: ${loc.nominal_thickness_mm} mm | Min Req: ${loc.minimum_required_thickness_mm || '-'} mm</div>` : ''}
          </div>
        `;
      }
      html += '</div>';
    }

    html += '</div>';
    return html;
  },

  renderAuditTimeline(auditTrail) {
    if (!auditTrail || auditTrail.length === 0) {
      return '<div class="empty-card-msg">No audit records recorded yet.</div>';
    }

    let html = '<div class="timeline-container">';
    for (const a of auditTrail) {
      const dt = new Date(a.timestamp * 1000).toLocaleString();
      let icon = "📝";
      if (a.action === "ASSET_CREATED") icon = "✨";
      else if (a.action === "DOCUMENT_ATTACHED") icon = "📤";
      else if (a.action === "COMPONENT_ADDED") icon = "🔩";
      else if (a.action === "LOCATION_ADDED") icon = "📍";

      html += `
        <div class="timeline-item">
          <div class="timeline-icon">${icon}</div>
          <div class="timeline-content">
            <div class="timeline-header">
              <strong class="action-type">${a.action}</strong>
              <span class="timeline-time">${dt}</span>
            </div>
            <div class="timeline-user">Performed by: <strong>${a.performed_by}</strong></div>
            <pre class="timeline-details">${JSON.stringify(a.details, null, 2)}</pre>
          </div>
        </div>
      `;
    }
    html += '</div>';
    return html;
  },

  switchDossierTab(tabKey) {
    const tabs = document.querySelectorAll(".dossier-tab-btn");
    const panes = document.querySelectorAll(".dossier-tab-pane");

    tabs.forEach(t => t.classList.remove("active"));
    panes.forEach(p => p.classList.remove("active"));

    const targetTab = Array.from(tabs).find(t => t.textContent.toLowerCase().includes(tabKey.toLowerCase()));
    if (targetTab) targetTab.classList.add("active");

    const targetPane = document.getElementById(`dossier-tab-${tabKey}`);
    if (targetPane) targetPane.classList.add("active");
  },

  showProvenanceModal(prov) {
    const modal = document.getElementById("asset-provenance-modal");
    if (!modal) return;

    document.getElementById("prov-modal-doc-id").textContent = prov.document_id;
    document.getElementById("prov-modal-doc-name").textContent = prov.document_name;
    document.getElementById("prov-modal-location").textContent = `${prov.section} (Page ${prov.page})`;
    document.getElementById("prov-modal-authority").textContent = prov.authority;
    document.getElementById("prov-modal-status").textContent = prov.approval_status;
    document.getElementById("prov-modal-span").textContent = prov.exact_source_span || "Exact span recorded in official knowledge base document.";

    modal.style.display = "flex";
  },

  closeProvenanceModal() {
    const modal = document.getElementById("asset-provenance-modal");
    if (modal) modal.style.display = "none";
  },

  // ─────────────────────────────────────────────────────────────
  // MODALS: ADD ASSET, ADD DOCUMENT, ADD COMPONENT
  // ─────────────────────────────────────────────────────────────

  openAddAssetModal() {
    const modal = document.getElementById("add-asset-modal");
    if (!modal) return;
    this.updateClassSpecificFormFields();
    modal.style.display = "flex";
  },

  closeAddAssetModal() {
    const modal = document.getElementById("add-asset-modal");
    if (modal) modal.style.display = "none";
  },

  updateClassSpecificFormFields() {
    const select = document.getElementById("modal-asset-class");
    const container = document.getElementById("class-specific-fields-container");
    if (!select || !container) return;

    const aclass = select.value;
    let html = "";

    if (aclass === "VALVE") {
      html = `
        <div class="form-group-row">
          <div class="form-col">
            <label>Valve Type:</label>
            <input type="text" id="attr-valve-type" class="form-input" value="Safety Relief Valve (PSV)">
          </div>
          <div class="form-col">
            <label>Set Pressure (bar):</label>
            <input type="number" step="0.1" id="attr-set-pressure" class="form-input" value="15.0">
          </div>
        </div>
        <div class="form-group-row">
          <div class="form-col">
            <label>Orifice Designation:</label>
            <input type="text" id="attr-orifice" class="form-input" value="8T10">
          </div>
          <div class="form-col">
            <label>Flange Class:</label>
            <input type="text" id="attr-flange" class="form-input" value="300# / 150#">
          </div>
        </div>
      `;
    } else if (aclass === "HEAT_EXCHANGER") {
      html = `
        <div class="form-group-row">
          <div class="form-col">
            <label>TEMA Type:</label>
            <input type="text" id="attr-tema" class="form-input" value="AES (Split-Ring Floating Head)">
          </div>
          <div class="form-col">
            <label>Tube Count:</label>
            <input type="number" id="attr-tube-count" class="form-input" value="840">
          </div>
        </div>
        <div class="form-group-row">
          <div class="form-col">
            <label>Tube OD & Thickness (mm):</label>
            <input type="text" id="attr-tube-dim" class="form-input" value="19.05 mm x 2.11 mm">
          </div>
          <div class="form-col">
            <label>Surface Area (m²):</label>
            <input type="number" id="attr-area" class="form-input" value="620.0">
          </div>
        </div>
      `;
    } else if (aclass === "STORAGE_TANK") {
      html = `
        <div class="form-group-row">
          <div class="form-col">
            <label>Tank Type:</label>
            <input type="text" id="attr-tank-type" class="form-input" value="External Floating Roof (EFR)">
          </div>
          <div class="form-col">
            <label>Nominal Capacity (m³):</label>
            <input type="number" id="attr-capacity" class="form-input" value="60000">
          </div>
        </div>
      `;
    } else if (aclass === "PRESSURE_VESSEL") {
      html = `
        <div class="form-group-row">
          <div class="form-col">
            <label>Orientation:</label>
            <input type="text" id="attr-orient" class="form-input" value="Vertical Separator">
          </div>
          <div class="form-col">
            <label>Shell Nominal Thickness (mm):</label>
            <input type="number" step="0.1" id="attr-vessel-thk" class="form-input" value="28.5">
          </div>
        </div>
      `;
    } else if (aclass === "PUMP") {
      html = `
        <div class="form-group-row">
          <div class="form-col">
            <label>Pump Type / API 610 Code:</label>
            <input type="text" id="attr-pump-type" class="form-input" value="OH2 Between Bearings">
          </div>
          <div class="form-col">
            <label>Rated Flow (m³/hr):</label>
            <input type="number" id="attr-pump-flow" class="form-input" value="450">
          </div>
        </div>
      `;
    }

    container.innerHTML = html;
  },

  async submitNewAsset() {
    const tag = document.getElementById("modal-asset-tag").value.trim().toUpperCase();
    const name = document.getElementById("modal-asset-name").value.trim();
    const aclass = document.getElementById("modal-asset-class").value;
    const unit = document.getElementById("modal-asset-unit").value;
    const service = document.getElementById("modal-asset-service").value.trim();
    const status = document.getElementById("modal-asset-status").value;

    if (!tag || !name) {
      alert("Please enter both an Asset Tag and Asset Name.");
      return;
    }

    const classAttrs = {};
    if (aclass === "VALVE") {
      if (document.getElementById("attr-valve-type")) classAttrs.valve_type = document.getElementById("attr-valve-type").value;
      if (document.getElementById("attr-set-pressure")) classAttrs.set_pressure_bar = parseFloat(document.getElementById("attr-set-pressure").value);
      if (document.getElementById("attr-orifice")) classAttrs.orifice_designation = document.getElementById("attr-orifice").value;
      if (document.getElementById("attr-flange")) classAttrs.flange_rating = document.getElementById("attr-flange").value;
    } else if (aclass === "HEAT_EXCHANGER") {
      if (document.getElementById("attr-tema")) classAttrs.tema_type = document.getElementById("attr-tema").value;
      if (document.getElementById("attr-tube-count")) classAttrs.tube_count = parseInt(document.getElementById("attr-tube-count").value);
      if (document.getElementById("attr-tube-dim")) classAttrs.tube_dimensions = document.getElementById("attr-tube-dim").value;
      if (document.getElementById("attr-area")) classAttrs.surface_area_m2 = parseFloat(document.getElementById("attr-area").value);
    }

    const payload = {
      tag: tag,
      name: name,
      asset_class: aclass,
      process_unit: unit,
      service: service || "Refinery Continuous Service",
      status: status,
      class_attributes: classAttrs,
      created_by: "MRPL Operations Engineer"
    };

    try {
      const res = await fetch("/api/assets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to create asset");

      this.closeAddAssetModal();
      await this.loadHierarchy();
      await this.loadAssetList();
      await this.selectAsset(tag);
      alert(`Asset '${tag}' created successfully! Internal Asset ID: ${data.asset.asset_id}`);
    } catch (err) {
      alert("Error creating asset: " + err.message);
    }
  },

  openUploadDocModal(tag) {
    const modal = document.getElementById("upload-doc-modal");
    if (!modal) return;
    document.getElementById("modal-doc-asset-tag").value = tag || this.activeAssetTag;
    modal.style.display = "flex";
  },

  closeUploadDocModal() {
    const modal = document.getElementById("upload-doc-modal");
    if (modal) modal.style.display = "none";
  },

  async submitUploadDocument() {
    const tag = document.getElementById("modal-doc-asset-tag").value.trim().toUpperCase();
    const title = document.getElementById("modal-doc-title").value.trim();
    const docNum = document.getElementById("modal-doc-number").value.trim();
    const docType = document.getElementById("modal-doc-type").value;
    const date = document.getElementById("modal-doc-date").value || new Date().toISOString().split("T")[0];
    const content = document.getElementById("modal-doc-content").value.trim();

    if (!title || !content) {
      alert("Please provide both Document Title and Document Text Content.");
      return;
    }

    const payload = {
      title: title,
      document_number: docNum || `MRPL-DOC-${Date.now()}`,
      document_type: docType,
      date: date,
      revision: "R0",
      content: content,
      authority: "Authority Level A",
      approval_status: "APPROVED_FOR_SERVICE"
    };

    try {
      const res = await fetch(`/api/assets/${encodeURIComponent(tag)}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to upload document");

      this.closeUploadDocModal();
      await this.selectAsset(tag);
      alert(`Document successfully indexed into Hybrid RAG and attached to '${tag}'! Extracted ${data.observations_count} observations.`);
    } catch (err) {
      alert("Error attaching document: " + err.message);
    }
  },

  openAddComponentModal(tag) {
    const compName = prompt(`Add new component to asset ${tag} (e.g. Mechanical Seal, Casing, Impeller):`);
    if (!compName) return;
    this.submitAddComponent(tag, compName);
  },

  async submitAddComponent(tag, name) {
    try {
      const res = await fetch(`/api/assets/${encodeURIComponent(tag)}/components`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_id: `COMP-${tag}-${Date.now().toString().slice(-4)}`,
          component_name: name,
          criticality: "HIGH"
        })
      });
      if (!res.ok) throw new Error("Failed to add component");
      await this.selectAsset(tag);
    } catch (err) {
      alert("Error: " + err.message);
    }
  },

  openAddLocationModal(tag) {
    const locName = prompt(`Add inspection / CML location to asset ${tag} (e.g. CML-04 Discharge Nozzle):`);
    if (!locName) return;
    this.submitAddLocation(tag, locName);
  },

  async submitAddLocation(tag, name) {
    try {
      const res = await fetch(`/api/assets/${encodeURIComponent(tag)}/locations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          location_id: `LOC-${tag}-${Date.now().toString().slice(-4)}`,
          location_name: name,
          inspection_method: "Ultrasonic Thickness (UT)"
        })
      });
      if (!res.ok) throw new Error("Failed to add inspection location");
      await this.selectAsset(tag);
    } catch (err) {
      alert("Error: " + err.message);
    }
  }
};

window.AssetRegistryManager = AssetRegistryManager;
