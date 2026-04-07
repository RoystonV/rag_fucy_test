/* ===================================================================
   app.js — TARA RAG Visualizer · Extended for full TARA schema
   Handles: assets, item_definition, damage_scenarios,
            attacks, threat_scenarios, cybersecurity
   =================================================================== */

const API = "http://localhost:5000";

let _reports     = [];
let _currentDoc  = null;
let _allDamage   = [];
let _allDetails  = [];
let _allItemDef  = [];
let _allAttacks  = [];
let _allThreats  = [];
let _allCSReqs   = [];
let _filterNode  = null;
let _activeTab   = "damage";

/* ── DOM refs ────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);

const DOM = {
  reportList:       $("report-list"),
  searchInput:      $("search-input"),
  statusPill:       $("status-pill"),
  statusText:       $("status-text"),
  headerCount:      $("header-report-count"),
  loadingOverlay:   $("loading-overlay"),
  graphPlaceholder: $("graph-placeholder"),
  statNodes:        $("stat-nodes"),
  statEdges:        $("stat-edges"),
  statDerivs:       $("stat-derivs"),
  statAttacks:      $("stat-attacks"),
  statCS:           $("stat-cs"),
  nodeInfo:         $("node-info"),
  damageList:       $("damage-list"),
  panelCount:       $("panel-count"),
  attackList:       $("attack-list"),
  attackCount:      $("attack-panel-count"),
  threatList:       $("threat-list"),
  threatCount:      $("threat-panel-count"),
  csList:           $("cs-list"),
  csCount:          $("cs-panel-count"),
  itemList:         $("item-list"),
  itemCount:        $("item-panel-count"),
  tabBar:           $("tab-bar"),
  btnZoomIn:        $("btn-zoom-in"),
  btnZoomOut:       $("btn-zoom-out"),
  btnFit:           $("btn-fit"),
};

/* ── Boot ────────────────────────────────────────────────────────── */
async function boot() {
  await checkStatus();
  await loadReports();
  Graph.init("graph-canvas", onNodeClick);
  bindUI();
}

/* ── Status check ────────────────────────────────────────────────── */
async function checkStatus() {
  try {
    const r = await fetch(`${API}/api/status`);
    const d = await r.json();
    if (d.mongo_connected) {
      DOM.statusPill.className = "status-pill connected";
      DOM.statusText.textContent = "MongoDB Connected";
    } else {
      DOM.statusPill.className = "status-pill disconnected";
      DOM.statusText.textContent = "MongoDB Offline";
    }
  } catch {
    DOM.statusPill.className = "status-pill disconnected";
    DOM.statusText.textContent = "Server Offline";
  }
}

/* ── Load report list ────────────────────────────────────────────── */
async function loadReports() {
  try {
    const r = await fetch(`${API}/api/reports`);
    _reports = await r.json();
  } catch {
    _reports = [];
  }
  DOM.headerCount.textContent = _reports.length;
  renderReportList(_reports);
}

function renderReportList(list) {
  if (!list.length) {
    DOM.reportList.innerHTML = `
      <div class="sidebar-empty">
        <div class="empty-icon">🗄️</div>
        <div>No reports in MongoDB</div>
        <div style="margin-top:6px;color:var(--text-label);font-size:11px;">
          Run: <code style="font-family:var(--mono)">python seed_mongo.py</code>
        </div>
      </div>`;
    return;
  }

  DOM.reportList.innerHTML = list.map(r => {
    const date = r.saved_at
      ? new Date(r.saved_at).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
      : "";
    return `
      <div class="report-item fade-in" data-id="${r._id}" onclick="selectReport('${r._id}')">
        <div class="report-name">${r.ecu_name || r.query}</div>
        <div class="report-meta">
          <span class="badge">${r.node_count} nodes</span>
          <span class="badge green">${r.edge_count} edges</span>
          <span class="badge amber">${r.deriv_count} DS</span>
          ${r.attack_count ? `<span class="badge purple">${r.attack_count} atk</span>` : ""}
          ${r.cs_req_count ? `<span class="badge cyan">${r.cs_req_count} req</span>` : ""}
        </div>
        <div class="report-time">${date}</div>
        <button class="report-delete" onclick="deleteReport(event,'${r._id}')">✕</button>
      </div>`;
  }).join("");
}

/* ── Select report ───────────────────────────────────────────────── */
async function selectReport(id) {
  document.querySelectorAll(".report-item").forEach(el => {
    el.classList.toggle("active", el.dataset.id === id);
  });

  showLoading(true);
  DOM.graphPlaceholder.style.display = "none";

  try {
    const r = await fetch(`${API}/api/report/${id}`);
    if (!r.ok) throw new Error("fetch failed");
    _currentDoc = await r.json();
    renderReport(_currentDoc);
  } catch (e) {
    console.error(e);
    alert("Could not load report.");
  } finally {
    showLoading(false);
  }
}

/* ── Render report into graph + all panels ───────────────────────── */
function renderReport(doc) {
  const template = doc?.assets?.template || { nodes: [], edges: [] };
  const nodes    = template.nodes || [];
  const edges    = template.edges || [];

  _allDamage  = doc?.damage_scenarios?.Derivations || [];
  _allDetails = doc?.damage_scenarios?.Details     || [];
  _allItemDef = doc?.item_definition               || [];
  _allAttacks = doc?.attacks?.scenes               || [];
  _allThreats = doc?.threat_scenarios?.Details     || [];
  _allCSReqs  = doc?.cybersecurity?.scenes         || [];
  _filterNode = null;

  // Stats
  DOM.statNodes.textContent   = nodes.length;
  DOM.statEdges.textContent   = edges.length;
  DOM.statDerivs.textContent  = _allDamage.length;
  DOM.statAttacks.textContent = _allAttacks.length;
  DOM.statCS.textContent      = _allCSReqs.length;

  // Graph
  Graph.render(template);
  Graph.clearSelection();

  // Reset node info
  DOM.nodeInfo.innerHTML = `<div class="node-info-empty">Click a node to inspect it</div>`;

  // Render all panels
  renderDamagePanel(_allDamage, _allDetails, null);
  renderAttacksPanel(_allAttacks);
  renderThreatsPanel(_allThreats, null);
  renderCSPanel(_allCSReqs);
  renderItemDefPanel(_allItemDef);
}

/* ── Node click handler ──────────────────────────────────────────── */
function onNodeClick(nodeId, nodeData) {
  if (!nodeId) {
    DOM.nodeInfo.innerHTML = `<div class="node-info-empty">Click a node to inspect it</div>`;
    _filterNode = null;
    renderDamagePanel(_allDamage, _allDetails, null);
    renderThreatsPanel(_allThreats, null);
    return;
  }

  _filterNode = nodeId;
  const data  = nodeData?.data || {};
  const style = data.style || {};
  const props = nodeData?.properties || [];

  DOM.nodeInfo.innerHTML = `
    <div class="node-info-card">
      <div class="node-color-swatch" style="background:${style.backgroundColor || '#aaa'}"></div>
      <div>
        <div class="node-info-label">${data.label || nodeId}</div>
        <div class="node-info-type">${nodeData?.type || "default"} • ${nodeData?.parentId ? "child node" : "top-level"}</div>
        <div class="node-props">${props.map(p => `<span class="prop-tag ${propClass(p)}">${p[0]}</span>`).join("")}</div>
      </div>
    </div>`;

  // Filter damage scenarios for this node
  const filteredDerivs  = _allDamage.filter(d => d.nodeId === nodeId);
  const filteredDetails = _allDetails.filter(d => d.nodeId === nodeId);
  renderDamagePanel(filteredDerivs, filteredDetails, data.label);

  // Filter threat scenarios for this node
  const filteredThreats = _allThreats.filter(row =>
    row.Details && row.Details.some(d => d.nodeId === nodeId)
  );
  renderThreatsPanel(filteredThreats, data.label);
}

function propClass(p) {
  const map = {
    "Confidentiality": "prop-C", "Integrity": "prop-I", "Availability": "prop-A",
    "Authenticity": "prop-Au",   "Authorization": "prop-Az", "Non-repudiation": "prop-N"
  };
  return map[p] || "prop-N";
}

/* ── Render: Damage Scenarios panel ─────────────────────────────── */
function renderDamagePanel(derivations, details, nodeLabel) {
  DOM.panelCount.textContent = derivations.length;

  if (!derivations.length) {
    DOM.damageList.innerHTML = `
      <div class="panel-empty">
        <div class="empty-icon">${nodeLabel ? "🔍" : "📋"}</div>
        <div>${nodeLabel ? `No damage scenarios for <strong>${nodeLabel}</strong>` : "Select a report to view damage scenarios"}</div>
      </div>`;
    return;
  }

  DOM.damageList.innerHTML = derivations.map((d, i) => {
    const lossClass = lossToClass(d.loss || "");
    return `
      <div class="damage-item fade-in ${_filterNode ? "highlighted" : ""}">
        <div class="damage-header">
          <span class="damage-id">${d.id || `D-${i + 1}`}</span>
          <div>
            <div class="damage-name">${d.name || "Unnamed threat"}</div>
            <div class="damage-asset">
              <span class="loss-badge ${lossClass}">${lossIcon(d.loss)} ${d.loss || "unknown"}</span>
            </div>
          </div>
        </div>
        ${d.task ? `<div class="damage-task">${d.task}</div>` : ""}
      </div>`;
  }).join("");
}

/* ── Render: Attacks panel ───────────────────────────────────────── */
function renderAttacksPanel(scenes) {
  DOM.attackCount.textContent = scenes.length;

  if (!scenes.length) {
    DOM.attackList.innerHTML = `
      <div class="panel-empty">
        <div class="empty-icon">⚔️</div>
        <div>No attack scenes available</div>
      </div>`;
    return;
  }

  DOM.attackList.innerHTML = scenes.map((scene, i) => {
    const nodes = scene?.templates?.nodes || [];
    // Root node (nodeType: "derived") for the top-level description
    const rootNode = nodes.find(n => n.nodeType === "derived") || nodes[0];
    const desc = rootNode?.description || "";
    // Sub-attacks
    const subAttacks = nodes.filter(n => n.nodeType === "sub_attack");

    return `
      <div class="attack-item fade-in">
        <div class="attack-header">
          <span class="attack-idx">ATK-${String(i+1).padStart(2,"0")}</span>
          <div class="attack-name">${scene.Name || "Unnamed Attack"}</div>
        </div>
        ${desc ? `<div class="attack-desc">${desc.slice(0, 220)}${desc.length > 220 ? "…" : ""}</div>` : ""}
        ${subAttacks.length ? `
        <div class="attack-tree-label">Attack Vectors (${subAttacks.length})</div>
        <div class="attack-tree">
          ${subAttacks.map(sa => `
            <div class="attack-node">
              <span class="attack-node-icon">↳</span>
              <span class="attack-node-name">${sa.name || sa.label || ""}</span>
            </div>
          `).join("")}
        </div>` : ""}
      </div>`;
  }).join("");
}

/* ── Render: Threat Scenarios panel ─────────────────────────────── */
function renderThreatsPanel(rows, nodeLabel) {
  const filtered = nodeLabel
    ? rows.filter(r => r.Details && r.Details.some(d => d.node === nodeLabel || d.nodeId === _filterNode))
    : rows;

  DOM.threatCount.textContent = filtered.length;

  if (!filtered.length) {
    DOM.threatList.innerHTML = `
      <div class="panel-empty">
        <div class="empty-icon">🎯</div>
        <div>${nodeLabel ? `No threat scenarios for <strong>${nodeLabel}</strong>` : "No threat scenarios available"}</div>
      </div>`;
    return;
  }

  DOM.threatList.innerHTML = filtered.map(row => {
    const details = row.Details || [];
    return details.map(d => {
      const riskProps = (d.props || []).filter(p => p.is_risk_added);
      return `
        <div class="threat-item fade-in">
          <div class="threat-header">
            <span class="threat-ds-id">${row.id || ""}</span>
            <div class="threat-name">${d.name || "Unnamed Threat"}</div>
          </div>
          <div class="threat-meta">
            <span class="threat-node">${d.node || ""}</span>
          </div>
          ${riskProps.length ? `
          <div class="threat-props">
            ${riskProps.map(p => `<span class="prop-tag ${propClass(p.name)}" title="Risk driver">${p.name}</span>`).join("")}
          </div>` : ""}
        </div>`;
    }).join("");
  }).join("");
}

/* ── Render: Cybersecurity Requirements panel ───────────────────── */
function renderCSPanel(scenes) {
  DOM.csCount.textContent = scenes.length;

  if (!scenes.length) {
    DOM.csList.innerHTML = `
      <div class="panel-empty">
        <div class="empty-icon">🔐</div>
        <div>No cybersecurity requirements available</div>
      </div>`;
    return;
  }

  // Group by attack_scene_name
  const groups = {};
  scenes.forEach(s => {
    const key = s.attack_scene_name || "General";
    if (!groups[key]) groups[key] = [];
    groups[key].push(s);
  });

  DOM.csList.innerHTML = Object.entries(groups).map(([sceneName, reqs]) => `
    <div class="cs-group">
      <div class="cs-group-header">
        <span class="cs-attack-scene">⚔️ ${sceneName}</span>
        <span class="cs-req-count">${reqs.length}</span>
      </div>
      ${reqs.map((req, i) => `
        <div class="cs-item fade-in">
          <div class="cs-req-header">
            <span class="cs-req-id">REQ-${String(i+1).padStart(2,"0")}</span>
            <div class="cs-req-name">${req.Name || "Unnamed Requirement"}</div>
          </div>
          ${req.Description ? `<div class="cs-req-desc">${req.Description}</div>` : ""}
        </div>
      `).join("")}
    </div>
  `).join("");
}

/* ── Render: Item Definitions panel ─────────────────────────────── */
function renderItemDefPanel(items) {
  DOM.itemCount.textContent = items.length;

  if (!items.length) {
    DOM.itemList.innerHTML = `
      <div class="panel-empty">
        <div class="empty-icon">📦</div>
        <div>No item definitions available</div>
      </div>`;
    return;
  }

  // Group by type
  const byType = {};
  items.forEach(item => {
    const t = item.type || "default";
    if (!byType[t]) byType[t] = [];
    byType[t].push(item);
  });

  const typeIcons = { group: "📁", default: "📦", data: "💾", step: "🔗" };

  DOM.itemList.innerHTML = Object.entries(byType).map(([type, its]) => `
    <div class="cs-group">
      <div class="cs-group-header">
        <span class="cs-attack-scene">${typeIcons[type] || "📦"} ${type.charAt(0).toUpperCase() + type.slice(1)} (${its.length})</span>
      </div>
      ${its.map(item => `
        <div class="item-def-item fade-in">
          <div class="item-def-header">
            <div class="item-def-name">${item.name || item.nodeId || "—"}</div>
          </div>
          ${item.desc ? `<div class="item-def-desc">${item.desc}</div>` : ""}
          <div class="node-props" style="margin-top:5px;">
            ${(item.props || []).map(p => `<span class="prop-tag ${propClass(p.name)}">${p.name[0]}</span>`).join("")}
          </div>
        </div>
      `).join("")}
    </div>
  `).join("");
}

/* ── loss helpers ────────────────────────────────────────────────── */
function lossToClass(loss) {
  const l = loss.toLowerCase();
  if (l.includes("integ"))   return "loss-integrity";
  if (l.includes("confid"))  return "loss-confidential";
  if (l.includes("avail"))   return "loss-availability";
  if (l.includes("authen"))  return "loss-authenticity";
  if (l.includes("author"))  return "loss-authorization";
  return "loss-other";
}

function lossIcon(loss = "") {
  const l = loss.toLowerCase();
  if (l.includes("integ"))   return "🔒";
  if (l.includes("confid"))  return "👁";
  if (l.includes("avail"))   return "⚡";
  if (l.includes("authen"))  return "🎫";
  if (l.includes("author"))  return "🔑";
  return "⚠️";
}

/* ── Tab switching ───────────────────────────────────────────────── */
function switchTab(tabId) {
  _activeTab = tabId;

  // Buttons
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });

  // Panels
  document.querySelectorAll(".tab-panel").forEach(panel => {
    const isActive = panel.id === `panel-${tabId}`;
    panel.classList.toggle("active", isActive);
  });
}

/* ── Delete report ───────────────────────────────────────────────── */
async function deleteReport(e, id) {
  e.stopPropagation();
  if (!confirm("Delete this report from MongoDB?")) return;
  await fetch(`${API}/api/report/${id}`, { method: "DELETE" });
  await loadReports();
}

/* ── UI bindings ─────────────────────────────────────────────────── */
function bindUI() {
  DOM.searchInput.addEventListener("input", () => {
    const q = DOM.searchInput.value.toLowerCase();
    const filtered = _reports.filter(r =>
      (r.ecu_name || r.query || "").toLowerCase().includes(q)
    );
    renderReportList(filtered);
  });

  // Tab bar
  DOM.tabBar.addEventListener("click", e => {
    const btn = e.target.closest(".tab-btn");
    if (btn && btn.dataset.tab) switchTab(btn.dataset.tab);
  });

  DOM.btnZoomIn.addEventListener("click",  () => Graph.zoomIn());
  DOM.btnZoomOut.addEventListener("click", () => Graph.zoomOut());
  DOM.btnFit.addEventListener("click",     () => Graph.resetZoom());
}

function showLoading(show) {
  DOM.loadingOverlay.classList.toggle("active", show);
}

/* ── Start ───────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", boot);

// Expose globals needed by inline handlers
window.selectReport = selectReport;
window.deleteReport = deleteReport;
