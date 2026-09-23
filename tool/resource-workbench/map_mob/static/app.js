window.onerror = function(msg, src, line, col, err) {
  window._lastError = {msg: msg, line: line, col: col, stack: err ? err.stack : ""};
};
const $ = (id) => document.getElementById(id);
const apiBase = document.body.dataset.apiBase || "";
const tmsDataRoot = document.body.dataset.tmsDataRoot;
const defaultExportRoot = document.body.dataset.defaultExportRoot;

function apiUrl(path) {
  return `${apiBase}${path}`;
}

const state = {
  kind: "map",
  rows: [],
  rowByPath: new Map(),
  children: new Map(),
  expanded: new Set([""]),
  selectedPath: null,
  addParentPath: "",
  leftPath: "",
  rightPath: "",
  leftInfo: null,
  rightInfo: null,
  compatibility: null,
  diagnostic: null,
  diagnosticPath: "",
  diagnosticPhase: "unknown",
  diagnosticPeers: "",
  preview: null,
  rightPreview: null,
  mobSources: null,
  mobSourceSequence: 0,
  mobManifestSequence: 0,
  mobActionPlanSequence: 0,
  zoom: 1,
  waterSelectMode: false,
  mapViews: {
    left: {preview: null, images: [], lifeImages: [], portalImages: [], hitRegions: [], canvasId: "mapCanvas", stageId: "leftMapStage", coordinateId: "leftMapCoordinate", selectionId: "leftWaterSelection"},
    right: {preview: null, images: [], lifeImages: [], portalImages: [], hitRegions: [], canvasId: "rightMapCanvas", stageId: "rightMapStage", coordinateId: "rightMapCoordinate", selectionId: "rightWaterSelection"},
  },
  mobActionName: "",
  mobElapsed: 0,
  mobPlaying: true,
  mobTimer: null,
  mobFrameIndices: {left: -1, right: -1},
  mobSkills: [],
  mobSkillSelected: null,
  mobSkillLevel: 1,
  loadSequence: 0,
  exportSourcePath: "",
  exportFiles: new Set(),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(text, kind = "") {
  const el = $("connectionStatus");
  el.textContent = text;
  el.className = `status-dot ${kind}`.trim();
}

async function api(url, options = {}) {
  setStatus("处理中", "busy");
  try {
    const response = await fetch(apiUrl(url), options);
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
    setStatus("就绪");
    return payload;
  } catch (error) {
    setStatus("操作失败", "error");
    throw error;
  }
}

function post(url, body) {
  return api(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
}

async function postQuiet(url, body) {
  const response = await fetch(apiUrl(url), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
  return payload;
}

function get(url) {
  return api(url, {method: "GET"});
}

function debounce(fn, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function setKind(kind) {
  state.kind = kind;
  document.body.classList.toggle("mob-mode", kind === "mob");
  document.querySelectorAll(".segment").forEach((button) => button.classList.toggle("active", button.dataset.kind === kind));
  $("previewTitle").textContent = kind === "map" ? "地图预览" : "怪物预览";
  $("mapControls").hidden = kind !== "map";
  $("mobControls").hidden = kind !== "mob";
  $("mobControlsInline").hidden = kind !== "mob";
  $("mobPreviewBar").hidden = kind !== "mob";
  $("itemId").placeholder = kind === "map" ? "9 位地图 ID" : "7 位怪物 ID";
  $("diagnosticTab").disabled = kind !== "map";
  $("mobSourceBar").hidden = kind !== "mob";
  clearWorkspace();
  updateDefaultPaths($("itemId").value.trim());
  if (kind === "mob") loadMobSources($("itemId").value.trim(), true);
  searchCatalog();
}

// 怪物模式下动画在检查器面板的内联区域，地图模式在预览面板。
// 用这些辅助函数统一获取当前模式对应的 DOM 元素。
function _mobEl(prefix) {
  const inline = state.kind === "mob";
  const map = {
    leftImage: inline ? "leftMobImageInline" : "leftMobImage",
    rightImage: inline ? "rightMobImageInline" : "rightMobImage",
    leftCounter: inline ? "leftFrameCounterInline" : "leftFrameCounter",
    rightCounter: inline ? "rightFrameCounterInline" : "rightFrameCounter",
    leftReal: inline ? "leftRealResourceInline" : "leftRealResource",
    rightReal: inline ? "rightRealResourceInline" : "rightRealResource",
    actionSelect: inline ? "actionSelectInline" : "actionSelect",
    resetBtn: inline ? "resetBtnInline" : "resetBtn",
    prevBtn: inline ? "prevFrameBtnInline" : "prevFrameBtn",
    playBtn: inline ? "playBtnInline" : "playBtn",
    nextBtn: inline ? "nextFrameBtnInline" : "nextFrameBtn",
    frameCounter: inline ? "frameCounterInline" : "frameCounter",
    copyBtoA: inline ? "copyFrameBtoAInline" : "copyFrameBtoA",
    copyAtoB: inline ? "copyFrameAtoBInline" : "copyFrameAtoB",
    migrateBtn: inline ? "migrateMobActionBtnInline" : "migrateMobActionBtn",
  };
  return map[prefix] ? $(map[prefix]) : null;
}

function updateDefaultPaths(id) {
  if (!/^\d+$/.test(id)) return;
  if (state.kind === "map") {
    if (id.length !== 9) return;
    const bucket = `Map${id[0]}`;
    $("leftPath").value = `clien/Data/Map/Map/${bucket}/${id}.img`;
    $("rightPath").value = `${tmsDataRoot}/Map/Map/${bucket}/${id}.img`;
  } else {
    $("leftPath").value = `clien/Data/Mob/${id}.img`;
    $("rightPath").value = `${tmsDataRoot}/Mob/_Canvas/${id}.img`;
  }
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function renderMobSources(data) {
  state.mobSources = data;
  $("mobSourceIdentity").innerHTML = `<strong>${escapeHtml(data.id)}${data.name ? ` · ${escapeHtml(data.name)}` : ""}</strong><span>${escapeHtml(data.msEntry || "TMS 未发现同 ID 的 MS 条目")}</span>`;
  $("mobSourceOptions").innerHTML = data.sources.map((source) => `
    <button class="mob-source-button ${source.path === $("rightPath").value.trim() ? "active" : ""}" type="button" data-source-path="${escapeHtml(source.path)}" title="${escapeHtml(source.path)}">
      <b>${escapeHtml(source.label)}</b><small>${escapeHtml(source.pack || `${source.rootCount} 根节点`)}</small>
    </button>`).join("");
  const ms = data.sources.find((source) => source.kind === "ms");
  $("mobSourceStatus").textContent = ms
    ? `${ms.rootCount} 根节点 · ${formatBytes(ms.size)} · BMS`
    : `${data.sources.length} 个可用来源`;
  $("mobSourceOptions").querySelectorAll("[data-source-path]").forEach((button) => button.addEventListener("click", async () => {
    $("rightPath").value = button.dataset.sourcePath;
    $("mobSourceOptions").querySelectorAll(".mob-source-button").forEach((item) => item.classList.toggle("active", item === button));
    await loadComparison();
  }));
}

async function loadMobSources(id, selectPreferred = false) {
  if (state.kind !== "mob" || !/^\d{7}$/.test(id)) {
    if (state.kind === "mob") {
      $("mobSourceIdentity").innerHTML = "<strong>输入 7 位怪物 ID</strong><span>–</span>";
      $("mobSourceOptions").innerHTML = "";
      $("mobSourceStatus").textContent = "";
    }
    return null;
  }
  const sequence = ++state.mobSourceSequence;
  $("mobSourceStatus").textContent = "正在读取 MS 索引…";
  try {
    const data = await api(`/api/mob-sources?id=${encodeURIComponent(id)}`);
    if (sequence !== state.mobSourceSequence || state.kind !== "mob" || $("itemId").value.trim() !== id) return null;
    if (selectPreferred && data.comparisonPath) $("rightPath").value = data.comparisonPath;
    $("leftPath").value = data.clientPath;
    renderMobSources(data);
    return data;
  } catch (error) {
    if (sequence === state.mobSourceSequence) {
      $("mobSourceStatus").textContent = error.message;
      $("mobSourceOptions").innerHTML = "";
    }
    return null;
  }
}

function clearWorkspace() {
  state.rows = [];
  state.rowByPath.clear();
  state.children.clear();
  state.selectedPath = null;
  state.preview = null;
  state.rightPreview = null;
  state.compatibility = null;
  state.diagnostic = null;
  state.diagnosticPath = "";
  for (const view of Object.values(state.mapViews)) {
    view.preview = null;
    view.images = [];
    view.lifeImages = [];
    view.portalImages = [];
    view.hitRegions = [];
    $(view.coordinateId).hidden = true;
    $(view.selectionId).hidden = true;
  }
  stopMobTimer();
  $("tree").innerHTML = "";
  $("nodeCount").textContent = "0";
  $("changedCount").textContent = "0";
  $("leftOnlyCount").textContent = "0";
  $("rightOnlyCount").textContent = "0";
  $("compatibilityCount").textContent = "0";
  $("diagnosticCount").textContent = "–";
  state.waterSelectMode = false;
  $("waterSelectBtn").classList.remove("active");
  $("waterSelectionValue").hidden = true;
  $("crashDiagnostic").innerHTML = diagnosticPromptMarkup();
  $("runDiagnosticBtn")?.addEventListener("click", runCrashDiagnostic);
  $("previewEmpty").hidden = false;
  $("mapCompareView").hidden = true;
  $("mobStage").hidden = true;
  $("mobPreviewBar").hidden = true;
  for (const id of ["leftMobImage", "rightMobImage", "leftMobImageInline", "rightMobImageInline"]) {
    const el = $(id);
    if (el) { el.removeAttribute("src"); el.hidden = true; }
  }
  state.mobActionPlanSequence += 1;
  for (const btn of [_mobEl("migrateBtn")].filter(Boolean)) btn.disabled = true;
  $("previewMeta").textContent = "未加载";
  $("inspector").className = "inspector empty-state compact";
  $("inspector").innerHTML = '<span class="empty-mark small" aria-hidden="true">⌖</span><strong>选择左侧节点</strong><span>这里会显示属性、差异与可编辑值。</span>';
  $("compatibility").innerHTML = '<div class="empty-state compact"><strong>等待对比结果</strong><span>加载后会分析 B 独有节点和现代资源兼容风险。</span></div>';
  setInspectorMode("compatibility");
  $("selectedPath").textContent = "未选择节点";
  $("selectedPath").title = "";
  $("nodeActions").hidden = true;
  $("createMainBtn").hidden = true;
  $("createMainBtn").disabled = true;
  $("copyTmsBtn").disabled = true;
  $("addRootBtn").disabled = true;
  $("addChildBtn").disabled = true;
  $("deleteBtn").disabled = true;
  $("exportBtn").disabled = true;
  $("editActions").hidden = true;
  $("operationResult").hidden = true;
  closeNodeDetailDialog();
}

async function searchCatalog() {
  const query = $("itemId").value.trim();
  try {
    const data = await api(`/api/catalog?kind=${encodeURIComponent(state.kind)}&q=${encodeURIComponent(query)}`);
    renderCatalog(data.items);
  } catch (error) {
    renderCatalog([]);
  }
}

function renderCatalog(items) {
  const catalog = $("catalog");
  catalog.innerHTML = items.length
    ? items.map((item) => `<button class="catalog-item ${state.kind === "mob" ? "rich" : ""}" type="button" data-id="${escapeHtml(item.id)}" data-left="${escapeHtml(item.leftPath)}" data-right="${escapeHtml(item.rightPath)}">
      <span class="catalog-item-main"><strong>${escapeHtml(item.id)}</strong>${item.name ? `<span>${escapeHtml(item.name)}</span>` : ""}</span>
      <small class="catalog-source-list">${escapeHtml((item.sources || []).join(" · ") || (item.hasXml ? "A + B" : "仅 A"))}</small>
    </button>`).join("")
    : '<div class="empty-state compact"><span>没有匹配文件</span></div>';
  catalog.hidden = false;
  catalog.querySelectorAll(".catalog-item").forEach((button) => {
    button.addEventListener("click", async () => {
      $("itemId").value = button.dataset.id;
      $("leftPath").value = button.dataset.left;
      $("rightPath").value = button.dataset.right;
      catalog.hidden = true;
      if (state.kind === "mob") await loadMobSources(button.dataset.id, true);
      await loadComparison();
    });
  });
}

function buildTreeIndex() {
  state.rowByPath = new Map(state.rows.map((row) => [row.path, row]));
  state.children = new Map();
  for (const row of state.rows) {
    if (!row.path) continue;
    const parent = row.parent || "";
    if (!state.children.has(parent)) state.children.set(parent, []);
    state.children.get(parent).push(row.path);
  }
}

function isLinkNode(meta) {
  if (!meta) return false;
  const type = String(meta.type || "").toLowerCase();
  const name = String(meta.name || "");
  return type === "uol" || name === "_inlink" || name === "_outlink";
}

function linkTarget(meta) {
  if (!meta) return "";
  if (meta.value !== undefined && meta.value !== null && typeof meta.value !== "object") return String(meta.value);
  if (meta.target) return String(meta.target);
  return "";
}

function resolveUolTarget(fromPath, target) {
  if (!target) return "";
  const parts = fromPath.split("/").filter(Boolean);
  parts.pop();
  for (const segment of String(target).replaceAll("\\", "/").split("/")) {
    if (!segment || segment === ".") continue;
    if (segment === "..") parts.pop();
    else parts.push(segment);
  }
  return parts.join("/");
}

function rowLabel(row) {
  const meta = row.left || row.right || {};
  return meta.name || row.path.split("/").pop() || "root";
}

function metaValue(meta) {
  if (!meta) return "缺失";
  if (isLinkNode(meta)) {
    const target = linkTarget(meta);
    if (String(meta.type || "").toLowerCase() === "uol") return target ? `↗ ${target}` : "UOL";
    return target ? `${meta.name} → ${target}` : meta.name;
  }
  if (meta.canvasStoreMissing && (meta.type === "gap" || meta.value === "Canvas 库未收录")) return "库未收录";
  if (meta.value && typeof meta.value === "object") return Object.values(meta.value).join(", ");
  if (meta.value !== undefined && meta.value !== null) return String(meta.value);
  if (meta.type === "canvas") return `${meta.width || 0}×${meta.height || 0}`;
  if (meta.childCount !== undefined) return `${meta.childCount}`;
  return "";
}

function typeIcon(type) {
  return ({imgdir: "D", canvas: "C", vector: "V", string: "S", int: "#", long: "L", short: "#", float: "F", double: "F", uol: "↗", video: "🎬", gap: "○"})[type] || "·";
}

function visiblePaths() {
  const search = $("treeSearch").value.trim().toLowerCase();
  const diffOnly = $("diffOnly").checked;
  const uolOnly = $("uolOnly")?.checked;
  const keep = new Set();
  if (search || diffOnly || uolOnly) {
    for (const row of state.rows) {
      if (!row.path) continue;
      const haystack = `${row.path} ${row.left?.type || ""} ${row.right?.type || ""} ${metaValue(row.left)} ${metaValue(row.right)}`.toLowerCase();
      const matchesSearch = !search || haystack.includes(search);
      const matchesDiff = !diffOnly || row.status !== "same";
      const matchesUol = !uolOnly || isLinkNode(row.left) || isLinkNode(row.right);
      if (!matchesSearch || !matchesDiff || !matchesUol) continue;
      let cursor = row.path;
      while (cursor) {
        keep.add(cursor);
        cursor = cursor.includes("/") ? cursor.slice(0, cursor.lastIndexOf("/")) : "";
      }
    }
  }
  const output = [];
  if (state.rowByPath.has("")) output.push({path: "", depth: 0});
  const visit = (parent, depth) => {
    for (const path of state.children.get(parent) || []) {
      if ((search || diffOnly || uolOnly) && !keep.has(path)) continue;
      output.push({path, depth});
      if ((state.expanded.has(path) || search || diffOnly || uolOnly) && state.children.has(path)) visit(path, depth + 1);
    }
  };
  if (state.expanded.has("") || search || diffOnly || uolOnly) visit("", 1);
  return output;
}

function renderTree() {
  const paths = visiblePaths();
  $("tree").innerHTML = paths.map(({path, depth}) => {
    const row = state.rowByPath.get(path);
    const meta = row.left || row.right || {};
    const hasChildren = state.children.has(path);
    const open = state.expanded.has(path);
    const statusLabel = ({same: "一致", changed: "修改", leftOnly: "仅 A", rightOnly: "仅 B"})[row.status];
    const resourceLabels = {npc: "NPC", mob: "怪物", obj: "OBJ", tile: "Tile", back: "Back"};
    const resourceBadges = (row.resources || []).filter((resource) => resource.status !== "ready").map((resource) => {
      const label = resourceLabels[resource.kind] || resource.kind;
      const prefix = resource.status === "missingFile" ? `缺 ${label}` : `${label} 不完整`;
      return `<span class="node-resource-status" title="${escapeHtml((resource.issues || []).join("；") || "引用资源缺失或不兼容")}">${escapeHtml(prefix)} ${escapeHtml(resource.name)}</span>`;
    }).join("");
    const linkMeta = [row.left, row.right].find((meta) => isLinkNode(meta));
    const linkBadge = linkMeta
      ? `<span class="node-uol-status" title="${escapeHtml(linkTarget(linkMeta) || "引用节点")}">${String(linkMeta.type || "").toLowerCase() === "uol" ? "UOL" : escapeHtml(linkMeta.name)}</span>`
      : "";
    return `<div class="tree-row status-${row.status} ${state.selectedPath === path ? "selected" : ""}" data-path="${escapeHtml(path)}" style="padding-left:${8 + depth * 15}px" role="treeitem" aria-selected="${state.selectedPath === path}">
      <button class="twisty" type="button" data-twist="${escapeHtml(path)}" ${hasChildren ? "" : "disabled"}>${hasChildren ? (open ? "▾" : "▸") : ""}</button>
      <span class="node-icon">${typeIcon(meta.type)}</span>
      <span class="node-body">
        <span class="node-title-line"><span class="node-name" title="${escapeHtml(path)}">${escapeHtml(rowLabel(row))}</span><span class="node-status">${statusLabel}</span>${linkBadge}${resourceBadges}${meta.type === "video" ? `<button class="video-preview-btn" type="button" data-path="${escapeHtml(path)}" title="预览 MCV 视频">🎬</button>` : ""}</span>
        <span class="node-compare-values">
          <span class="node-side side-a ${row.left ? "" : "missing"}" title="A 主文件：${escapeHtml(metaValue(row.left))}"><b>A</b><span>${escapeHtml(metaValue(row.left))}</span></span>
          <span class="node-side side-b ${row.right ? "" : "missing"}" title="B 对比文件：${escapeHtml(metaValue(row.right))}"><b>B</b><span>${escapeHtml(metaValue(row.right))}</span></span>
        </span>
      </span>
    </div>`;
  }).join("");
  $("tree").querySelectorAll(".twisty:not(:disabled)").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    const path = button.dataset.twist;
    if (state.expanded.has(path)) state.expanded.delete(path); else state.expanded.add(path);
    renderTree();
  }));
  $("tree").querySelectorAll(".tree-row").forEach((row) => row.addEventListener("click", () => selectNode(row.dataset.path)));
  $("tree").querySelectorAll(".video-preview-btn").forEach((btn) => btn.addEventListener("click", (event) => {
    event.stopPropagation();
    previewVideo(btn.dataset.path);
  }));
}

async function previewVideo(nodePath) {
  const file = state.leftPath;
  if (!file) {
    alert("请先加载怪物 IMG 文件");
    return;
  }
  try {
    const response = await fetch(apiUrl(`/api/video?file=${encodeURIComponent(file)}&path=${encodeURIComponent(nodePath)}`));
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    // 创建模态框显示视频
    document.querySelectorAll(".video-modal").forEach(m => m.remove());
    const modal = document.createElement("div");
    modal.className = "video-modal";
    modal.innerHTML = `
      <div class="video-modal-content">
        <div class="video-modal-header">
          <h3>MCV 视频预览</h3>
          <button class="video-modal-close" type="button">×</button>
        </div>
        <div class="video-modal-body">
          <video controls autoplay loop width="1280" height="720" style="max-width:100%; background:#000;">
            <source src="${url}" type="video/mp4">
            <source src="${url}" type="video/webm">
            浏览器不支持视频播放
          </video>
          <div class="video-info">
            <p>节点路径: ${escapeHtml(nodePath)}</p>
            <p>文件: ${escapeHtml(file)}</p>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector(".video-modal-close").addEventListener("click", () => {
      URL.revokeObjectURL(url);
      modal.remove();
    });
    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        URL.revokeObjectURL(url);
        modal.remove();
      }
    });
  } catch (error) {
    console.error("视频预览失败:", error);
    alert(`视频预览失败: ${error.message}`);
  }
}

async function loadComparison({backgroundPreview = false} = {}) {
  const leftPath = $("leftPath").value.trim();
  const rightPath = $("rightPath").value.trim();
  if (!leftPath || !rightPath) return;
  const loadSequence = ++state.loadSequence;
  $("catalog").hidden = true;
  clearWorkspace();
  try {
    const data = await post("/api/compare", {kind: state.kind, leftPath, rightPath});
    if (loadSequence !== state.loadSequence) return;
    if (state.exportSourcePath !== data.leftPath) {
      state.exportSourcePath = data.leftPath;
      state.exportFiles = new Set();
    }
    state.rows = data.nodes;
    state.leftPath = data.leftPath;
    state.rightPath = data.rightPath;
    state.leftInfo = data.leftInfo;
    state.rightInfo = data.rightInfo;
    state.compatibility = data.compatibility;
    if (state.kind === "mob" && state.mobSources) renderMobSources(state.mobSources);
    buildTreeIndex();
    state.expanded = new Set([""]);
    $("nodeCount").textContent = `${data.nodes.length} 节点`;
    $("changedCount").textContent = data.counts.changed;
    $("leftOnlyCount").textContent = data.counts.leftOnly;
    $("rightOnlyCount").textContent = data.counts.rightOnly;
    renderCompatibility(data.compatibility);
    renderTree();
    $("nodeActions").hidden = false;
    updateNodeActions();
    setInspectorMode("compatibility");
    if (backgroundPreview) {
      void loadPreview(loadSequence, true);
    } else {
      await loadPreview(loadSequence);
    }
  } catch (error) {
    if (loadSequence !== state.loadSequence) return;
    showResult(error.message, true);
    $("previewEmpty").innerHTML = `<strong>加载失败</strong><span>${escapeHtml(error.message)}</span>`;
  }
}

async function refreshComparisonAfterCopy(path, {backgroundPreview = false} = {}) {
  const loadSequence = ++state.loadSequence;
  const data = await post("/api/compare", {
    kind: state.kind,
    leftPath: state.leftPath,
    rightPath: state.rightPath,
  });
  if (loadSequence !== state.loadSequence) return;
  state.rows = data.nodes;
  state.leftPath = data.leftPath;
  state.rightPath = data.rightPath;
  state.leftInfo = data.leftInfo;
  state.rightInfo = data.rightInfo;
  state.compatibility = data.compatibility;
  if (state.kind === "mob" && state.mobSources) renderMobSources(state.mobSources);
  buildTreeIndex();
  for (let parent = path; parent; parent = parent.includes("/") ? parent.slice(0, parent.lastIndexOf("/")) : "") {
    state.expanded.add(parent);
  }
  state.expanded.add("");
  $("nodeCount").textContent = `${data.nodes.length} 节点`;
  $("changedCount").textContent = data.counts.changed;
  $("leftOnlyCount").textContent = data.counts.leftOnly;
  $("rightOnlyCount").textContent = data.counts.rightOnly;
  renderCompatibility(data.compatibility);
  renderTree();
  $("nodeActions").hidden = false;
  if (state.rowByPath.has(path)) selectNode(path); else updateNodeActions();
  if (backgroundPreview) {
    void loadPreview(loadSequence, true);
  } else {
    await loadPreview(loadSequence);
  }
}

async function refreshTreeAfterDelete(parentPath) {
  const tree = $("tree");
  const scrollTop = tree.scrollTop;
  const loadSequence = ++state.loadSequence;
  const data = await post("/api/compare", {
    kind: state.kind,
    leftPath: state.leftPath,
    rightPath: state.rightPath,
  });
  if (loadSequence !== state.loadSequence) return;
  state.rows = data.nodes;
  state.leftPath = data.leftPath;
  state.rightPath = data.rightPath;
  state.leftInfo = data.leftInfo;
  state.rightInfo = data.rightInfo;
  state.compatibility = data.compatibility;
  if (state.kind === "mob" && state.mobSources) renderMobSources(state.mobSources);
  buildTreeIndex();
  for (let parent = parentPath; parent; parent = parent.includes("/") ? parent.slice(0, parent.lastIndexOf("/")) : "") {
    state.expanded.add(parent);
  }
  state.expanded.add("");
  $("nodeCount").textContent = `${data.nodes.length} 节点`;
  $("changedCount").textContent = data.counts.changed;
  $("leftOnlyCount").textContent = data.counts.leftOnly;
  $("rightOnlyCount").textContent = data.counts.rightOnly;
  renderCompatibility(data.compatibility);
  renderTree();
  tree.scrollTop = scrollTop;
  $("nodeActions").hidden = false;
  if (state.rowByPath.has(parentPath)) selectNode(parentPath); else updateNodeActions();
  // selectNode may call renderTree() again, so restore scroll again
  tree.scrollTop = scrollTop;
}

async function loadPreview(loadSequence = state.loadSequence, quiet = false) {
  const previewPost = quiet ? postQuiet : post;
  try {
    if (state.kind === "map") {
      const [leftResult, rightResult] = await Promise.allSettled([
        previewPost("/api/preview", {kind: "map", sourcePath: state.leftPath}),
        previewPost("/api/preview", {kind: "map", sourcePath: state.rightPath}),
      ]);
      if (loadSequence !== state.loadSequence) return;
      const leftData = leftResult.status === "fulfilled" ? leftResult.value : null;
      const rightData = rightResult.status === "fulfilled" ? rightResult.value : null;
      if (!leftData && !rightData) throw leftResult.reason || rightResult.reason;
      state.preview = leftData;
      state.rightPreview = rightData;
      $("previewEmpty").hidden = true;
      await prepareMapPreview(
        leftData,
        rightData,
        leftResult.status === "rejected" ? leftResult.reason : null,
        rightResult.status === "rejected" ? rightResult.reason : null,
      );
    } else {
      const [leftResult, rightResult] = await Promise.allSettled([
        previewPost("/api/preview", {kind: "mob", sourcePath: state.leftPath}),
        previewPost("/api/preview", {kind: "mob", sourcePath: state.rightPath}),
      ]);
      if (loadSequence !== state.loadSequence) return;
      const leftData = leftResult.status === "fulfilled" ? leftResult.value : null;
      const rightData = rightResult.status === "fulfilled" ? rightResult.value : null;
      if (!leftData && !rightData) throw leftResult.reason || rightResult.reason;
      state.preview = leftData;
      state.rightPreview = rightData;
      $("previewEmpty").hidden = true;
      prepareMobPreview(
        leftData,
        rightData,
        leftResult.status === "rejected" ? leftResult.reason : null,
        rightResult.status === "rejected" ? rightResult.reason : null,
      );
    }
  } catch (error) {
    if (loadSequence !== state.loadSequence) return;
    $("previewEmpty").hidden = false;
    $("previewEmpty").innerHTML = `<strong>预览不可用</strong><span>${escapeHtml(error.message)}</span>`;
  }
}

async function prepareMapPreview(leftData, rightData, leftError = null, rightError = null) {
  stopMobTimer();
  $("mobStage").hidden = true;
  $("mapCompareView").hidden = false;
  const leftSummary = leftData?.summary;
  const rightSummary = rightData?.summary;
  const leftUnavailable = state.leftInfo?.exists === false;
  const rightUnavailable = state.rightInfo?.exists === false;
  $("previewMeta").textContent = `${leftSummary ? `A ${leftSummary.elements} 个场景元素` : (leftUnavailable ? "A 主文件不存在" : "A 预览不可用")} · ${rightSummary ? `B ${rightSummary.elements} 个场景元素` : (rightUnavailable ? "B 对比文件不存在" : "B 预览不可用")}`;
  $("leftMapMeta").textContent = leftSummary
    ? `${leftSummary.mobs} 怪 · ${leftSummary.npcs} NPC · ${leftSummary.portals} 门`
    : (state.leftInfo?.exists === false ? "主文件不存在，可先创建空白主文件" : (leftError?.message || "无法生成预览"));
  $("rightMapSourceLabel").textContent = state.rightPath.includes("/TMS/") ? "TMS 对比" : "对比文件";
  $("rightMapMeta").textContent = rightSummary
    ? `${rightSummary.mobs} 怪 · ${rightSummary.npcs} NPC · ${rightSummary.portals} 门`
    : (rightUnavailable ? "对比文件不存在，仅显示 A" : (rightError?.message || "无法生成预览"));
  const imageCache = new Map();
  const loadImage = (url) => {
    if (!imageCache.has(url)) {
      imageCache.set(url, (async () => {
        const image = new Image();
        image.src = apiUrl(url);
        try { await image.decode(); return image; } catch (_error) { return null; }
      })());
    }
    return imageCache.get(url);
  };
  await Promise.all([
    prepareMapView("left", leftData, loadImage),
    prepareMapView("right", rightData, loadImage),
  ]);
  drawMaps();
  fitPreview();
}

async function prepareMapView(side, data, loadImage) {
  const view = state.mapViews[side];
  view.preview = data;
  view.hitRegions = [];
  if (!data) {
    const canvas = $(view.canvasId);
    canvas.width = 0;
    canvas.height = 0;
    return;
  }
  view.images = await Promise.all(data.elements.map(async (element) => ({element, image: await loadImage(element.url)})));
  view.lifeImages = await Promise.all(data.life.map(async (point) => ({point, image: point.sprite ? await loadImage(point.sprite.url) : null})));
  view.portalImages = await Promise.all(data.portals.map(async (point) => ({point, image: point.sprite ? await loadImage(point.sprite.url) : null})));
}

function drawMaps() {
  drawMap("left");
  drawMap("right");
  applyZoom();
}

function drawMap(side) {
  const view = state.mapViews[side];
  if (!view.preview || view.preview.kind !== "map") return;
  const canvas = $(view.canvasId);
  const context = canvas.getContext("2d");
  const bounds = view.preview.bounds;
  const width = Math.max(320, Math.min(7000, bounds.right - bounds.left));
  const height = Math.max(240, Math.min(5000, bounds.bottom - bounds.top));
  canvas.width = width;
  canvas.height = height;
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#111619";
  context.fillRect(0, 0, width, height);
  view.hitRegions = [];
  const ox = -bounds.left;
  const oy = -bounds.top;
  for (const {element, image} of view.images) {
    if (!image) continue;
    const x = element.x + ox - element.origin.x;
    const y = element.y + oy - element.origin.y;
    context.save();
    if (element.flip) {
      context.translate(element.x + ox, 0);
      context.scale(-1, 1);
      context.drawImage(image, -element.origin.x, y);
      registerMapHitRect(view, element.path, element.x + ox + element.origin.x - element.width, y, element.width, element.height, element.kind);
    } else {
      context.drawImage(image, x, y);
      registerMapHitRect(view, element.path, x, y, element.width, element.height, element.kind);
    }
    context.restore();
  }
  if ($("showFootholds").checked) {
    context.lineWidth = 2;
    context.strokeStyle = "#69d0a0";
    context.beginPath();
    for (const line of view.preview.footholds) {
      context.moveTo(line.x1 + ox, line.y1 + oy);
      context.lineTo(line.x2 + ox, line.y2 + oy);
      view.hitRegions.push({type: "line", path: line.path, x1: line.x1 + ox, y1: line.y1 + oy, x2: line.x2 + ox, y2: line.y2 + oy, label: "foothold"});
    }
    context.stroke();
  }
  if ($("showWaterAreas").checked) {
    for (const area of view.preview.waterAreas || []) {
      const x = area.x1 + ox;
      const y = area.y1 + oy;
      const width = area.x2 - area.x1;
      const height = area.y2 - area.y1;
      context.fillStyle = area.kind === "swimArea" ? "rgba(61, 194, 222, .22)" : "rgba(105, 128, 235, .18)";
      context.strokeStyle = area.kind === "swimArea" ? "#63d7ee" : "#91a4ff";
      context.lineWidth = 2;
      context.fillRect(x, y, width, height);
      context.strokeRect(x, y, width, height);
      context.fillStyle = "#d9f8ff";
      context.font = "bold 11px system-ui";
      context.textAlign = "left";
      context.textBaseline = "top";
      context.fillText(`${area.kind} · ${area.path.split("/").pop()}`, x + 6, y + 5);
      registerMapHitRect(view, area.path, x, y, width, height, area.kind);
    }
  }
  drawMapSprites(view, context, view.portalImages, ox, oy, $("showPortals").checked, "#70a7cf", "P");
  drawMapSprites(view, context, view.lifeImages.filter(({point}) => point.kind === "mob"), ox, oy, $("showMobs").checked, "#e26e67", "M");
  drawMapSprites(view, context, view.lifeImages.filter(({point}) => point.kind === "npc"), ox, oy, $("showNpcs").checked, "#e7bd6c", "N");
  drawMapSelection(context, selectedMapRegions(view));
}

function drawMapSprites(view, context, entries, ox, oy, visible, color, label) {
  if (!visible) return;
  for (const {point, image} of entries) {
    if (!image || !point.sprite) {
      drawPoints(context, [point], ox, oy, color, true, label);
      registerMapHitRect(view, point.path, point.x + ox - 9, point.y + oy - 9, 18, 18, point.kind || "portal");
      continue;
    }
    const x = point.x + ox;
    const y = point.y + oy;
    context.save();
    context.shadowColor = "rgba(0, 0, 0, .45)";
    context.shadowBlur = 6;
    if (point.flip) {
      context.translate(x, 0);
      context.scale(-1, 1);
      context.drawImage(image, -point.sprite.origin.x, y - point.sprite.origin.y);
      registerMapHitRect(view, point.path, x + point.sprite.origin.x - point.sprite.width, y - point.sprite.origin.y, point.sprite.width, point.sprite.height, point.kind || "portal");
    } else {
      context.drawImage(image, x - point.sprite.origin.x, y - point.sprite.origin.y);
      registerMapHitRect(view, point.path, x - point.sprite.origin.x, y - point.sprite.origin.y, point.sprite.width, point.sprite.height, point.kind || "portal");
    }
    context.restore();
  }
}

function registerMapHitRect(view, path, x, y, width, height, label) {
  if (path) view.hitRegions.push({type: "rect", path, x, y, width, height, label});
}

function mapPathsRelated(first, second) {
  return first === second || first.startsWith(`${second}/`) || second.startsWith(`${first}/`);
}

function selectedMapRegions(view) {
  if (!state.selectedPath) return [];
  return view.hitRegions.filter((region) => mapPathsRelated(state.selectedPath, region.path));
}

function drawMapSelection(context, regions) {
  if (!regions.length) return;
  const lineWidth = Math.max(3, 3 / Math.max(state.zoom, .1));
  context.save();
  context.lineJoin = "round";
  context.lineCap = "round";
  context.setLineDash([Math.max(7, 7 / Math.max(state.zoom, .1)), Math.max(4, 4 / Math.max(state.zoom, .1))]);
  for (const region of regions) {
    context.beginPath();
    if (region.type === "line") {
      context.moveTo(region.x1, region.y1);
      context.lineTo(region.x2, region.y2);
    } else {
      context.rect(region.x - lineWidth, region.y - lineWidth, region.width + lineWidth * 2, region.height + lineWidth * 2);
    }
    context.strokeStyle = "rgba(12, 16, 14, .9)";
    context.lineWidth = lineWidth * 2.6;
    context.stroke();
    context.strokeStyle = "#ffd166";
    context.lineWidth = lineWidth;
    context.stroke();
  }
  context.restore();
}

function mapRegionBounds(regions) {
  if (!regions.length) return null;
  const edges = regions.map((region) => region.type === "line"
    ? {left: Math.min(region.x1, region.x2), top: Math.min(region.y1, region.y2), right: Math.max(region.x1, region.x2), bottom: Math.max(region.y1, region.y2)}
    : {left: region.x, top: region.y, right: region.x + region.width, bottom: region.y + region.height});
  return {
    left: Math.min(...edges.map((edge) => edge.left)),
    top: Math.min(...edges.map((edge) => edge.top)),
    right: Math.max(...edges.map((edge) => edge.right)),
    bottom: Math.max(...edges.map((edge) => edge.bottom)),
  };
}

function revealSelectedMapContent() {
  if (state.kind !== "map" || !state.selectedPath) return;
  const path = state.selectedPath;
  if (mapPathsRelated(path, "foothold")) $("showFootholds").checked = true;
  if (mapPathsRelated(path, "portal")) $("showPortals").checked = true;
  if (mapPathsRelated(path, "swimArea") || mapPathsRelated(path, "rapidStream")) $("showWaterAreas").checked = true;
  if (mapPathsRelated(path, "life")) {
    const points = Object.values(state.mapViews).flatMap((view) => view.preview?.life || [])
      .filter((point) => mapPathsRelated(path, point.path));
    if (!points.length || points.some((point) => point.kind === "mob")) $("showMobs").checked = true;
    if (!points.length || points.some((point) => point.kind === "npc")) $("showNpcs").checked = true;
  }
  drawMaps();
  requestAnimationFrame(() => {
    for (const view of Object.values(state.mapViews)) {
      const bounds = mapRegionBounds(selectedMapRegions(view));
      if (!bounds) continue;
      const canvas = $(view.canvasId);
      const stage = $(view.stageId);
      const marginLeft = Number.parseFloat(canvas.style.marginLeft) || 0;
      const marginTop = Number.parseFloat(canvas.style.marginTop) || 0;
      const centerX = (bounds.left + bounds.right) / 2 * state.zoom + marginLeft;
      const centerY = (bounds.top + bounds.bottom) / 2 * state.zoom + marginTop;
      stage.scrollTo({
        left: Math.max(0, centerX - stage.clientWidth / 2),
        top: Math.max(0, centerY - stage.clientHeight / 2),
        behavior: "smooth",
      });
    }
  });
}

function distanceToSegment(px, py, line) {
  const dx = line.x2 - line.x1;
  const dy = line.y2 - line.y1;
  const lengthSquared = dx * dx + dy * dy;
  const ratio = lengthSquared ? Math.max(0, Math.min(1, ((px - line.x1) * dx + (py - line.y1) * dy) / lengthSquared)) : 0;
  return Math.hypot(px - (line.x1 + ratio * dx), py - (line.y1 + ratio * dy));
}

function mapHitAt(side, clientX, clientY) {
  const view = state.mapViews[side];
  if (state.kind !== "map" || !view.preview) return null;
  const canvas = $(view.canvasId);
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) return null;
  const x = (clientX - rect.left) * canvas.width / rect.width;
  const y = (clientY - rect.top) * canvas.height / rect.height;
  const tolerance = 7 / Math.max(state.zoom, .1);
  for (let index = view.hitRegions.length - 1; index >= 0; index -= 1) {
    const region = view.hitRegions[index];
    if (region.type === "line") {
      if (distanceToSegment(x, y, region) <= tolerance) return region;
    } else if (x >= region.x - tolerance && x <= region.x + region.width + tolerance && y >= region.y - tolerance && y <= region.y + region.height + tolerance) {
      return region;
    }
  }
  return null;
}

function mapCoordinateAt(side, clientX, clientY) {
  const view = state.mapViews[side];
  if (state.kind !== "map" || !view.preview) return null;
  const canvas = $(view.canvasId);
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) return null;
  const bounds = view.preview.bounds;
  return {
    x: Math.round(bounds.left + (clientX - rect.left) / rect.width * (bounds.right - bounds.left)),
    y: Math.round(bounds.top + (clientY - rect.top) / rect.height * (bounds.bottom - bounds.top)),
  };
}

function updateMapCoordinate(side, event) {
  const view = state.mapViews[side];
  const badge = $(view.coordinateId);
  const point = mapCoordinateAt(side, event.clientX, event.clientY);
  if (!point) {
    badge.hidden = true;
    return;
  }
  const stage = $(view.stageId);
  const rect = stage.getBoundingClientRect();
  const bounds = view.preview.bounds;
  badge.textContent = `WZ 地图  X ${point.x}  Y ${point.y}\n范围  X ${bounds.left}…${bounds.right}  Y ${bounds.top}…${bounds.bottom}`;
  badge.hidden = false;
  const localX = event.clientX - rect.left;
  const localY = event.clientY - rect.top;
  const left = Math.max(6, Math.min(stage.clientWidth - badge.offsetWidth - 6, localX + 14));
  const top = Math.max(6, Math.min(stage.clientHeight - badge.offsetHeight - 6, localY + 14));
  badge.style.left = `${stage.scrollLeft + left}px`;
  badge.style.top = `${stage.scrollTop + top}px`;
}

function positionWaterSelection(side, startEvent, currentEvent) {
  const view = state.mapViews[side];
  const stage = $(view.stageId);
  const rect = stage.getBoundingClientRect();
  const selection = $(view.selectionId);
  const startX = startEvent.clientX - rect.left + stage.scrollLeft;
  const startY = startEvent.clientY - rect.top + stage.scrollTop;
  const currentX = currentEvent.clientX - rect.left + stage.scrollLeft;
  const currentY = currentEvent.clientY - rect.top + stage.scrollTop;
  selection.hidden = false;
  selection.style.left = `${Math.min(startX, currentX)}px`;
  selection.style.top = `${Math.min(startY, currentY)}px`;
  selection.style.width = `${Math.abs(currentX - startX)}px`;
  selection.style.height = `${Math.abs(currentY - startY)}px`;
}

function drawPoints(context, points, ox, oy, color, visible, label) {
  if (!visible) return;
  context.font = "10px system-ui";
  context.textAlign = "center";
  context.textBaseline = "middle";
  for (const point of points) {
    context.beginPath();
    context.fillStyle = color;
    context.arc(point.x + ox, point.y + oy, 7, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#101315";
    context.fillText(label, point.x + ox, point.y + oy + 1);
  }
}

function hasVisibleMobFrame(action) {
  return Boolean(action?.frames.some((frame) => frame.width > 4 && frame.height > 4));
}

function mobPreviewRealSummary(data) {
  const actions = data?.actions || [];
  if (!actions.length) return "";
  let linked = 0;
  let orphan = 0;
  for (const action of actions) {
    linked += action.linkedFrames || 0;
    orphan += action.orphanFrames || 0;
  }
  const files = Array.from(new Set(actions.flatMap((action) => action.realFiles || [])));
  const parts = [];
  if (linked) parts.push(`占位→真实 ${linked}`);
  if (orphan) parts.push(`空占位 ${orphan}`);
  if (files.length) parts.push(`真实源 ${files.length} 个`);
  return parts.length ? ` · ${parts.join(" · ")}` : "";
}

function activeMobComparisonSource() {
  return state.mobSources?.sources.find((source) => source.path === state.rightPath) || null;
}

async function updateMobActionMigration() {
  const button = _mobEl("migrateBtn");
  const actionName = state.mobActionName;
  const leftAction = state.preview?.actions.find((action) => action.name === actionName);
  const rightAction = state.rightPreview?.actions.find((action) => action.name === actionName);
  const source = activeMobComparisonSource();
  const sourceSupported = ["ms", "img", "canvas"].includes(source?.kind);
  const targetSupported = state.leftPath.startsWith("clien/Data/Mob/") && state.leftInfo?.format === "img";
  const sequence = ++state.mobActionPlanSequence;
  button.textContent = "→ A";
  button.disabled = true;
  if (!actionName) button.title = "没有可迁移的动作";
  else if (!sourceSupported) button.title = "请先选择 MS 完整记录、TMS IMG 或 TMS Canvas 来源";
  else if (!targetSupported) button.title = "A 必须是当前项目 clien/Data/Mob 下的 IMG";
  else if (!rightAction) button.title = `${actionName} 在 B 侧没有可迁移的动作记录`;
  else {
    button.textContent = "…";
    button.title = `正在验证 ${actionName} 的增量记录与 Canvas…`;
    try {
      const data = await post("/api/mob-action-plan", {
        sourcePath: state.leftPath,
        tmsPath: state.rightPath,
        action: actionName,
      });
      if (sequence !== state.mobActionPlanSequence || actionName !== state.mobActionName) return;
      button.textContent = "→ A";
      button.disabled = !data.allowed;
      button.title = data.allowed
        ? `${leftAction ? "兼容替换" : "兼容新增"} ${actionName}：`
          + `${data.plan.canvas.visible}/${data.plan.canvas.canvases} 个可见 Canvas，`
          + `${data.plan.rawScope.protectedRecords} 个其他记录保持不变`
        : `不能安全迁移 ${actionName}：${data.reason}`;
    } catch (error) {
      if (sequence !== state.mobActionPlanSequence) return;
      button.textContent = "→ A";
      button.disabled = true;
      button.title = `迁移预检失败：${error.message}`;
    }
  }
}

function prepareMobPreview(leftData, rightData, leftError = null, rightError = null) {
  $("mapCompareView").hidden = true;
  $("mobStage").hidden = false;
  $("mobPreviewBar").hidden = state.kind !== "mob";
  // 同时填充两个动作选择器（预览面板的和检查器内联的）
  const selects = [$("actionSelect"), $("actionSelectInline")].filter(Boolean);
  const discoveredActionNames = Array.from(new Set([
    ...(leftData?.actions || []).map((action) => action.name),
    ...(rightData?.actions || []).map((action) => action.name),
  ]));
  const preferredOrder = ["stand", "move", "fly", "jump", "hit1", "die1"];
  const actionNames = [
    ...preferredOrder.filter((name) => discoveredActionNames.includes(name)),
    ...discoveredActionNames.filter((name) => !preferredOrder.includes(name)),
  ];
  const optionsHtml = actionNames.map((name) => {
    const left = leftData?.actions.find((action) => action.name === name);
    const right = rightData?.actions.find((action) => action.name === name);
    const blank = right?.frames.length && !hasVisibleMobFrame(right) ? " · B 全空占位" : "";
    const realHint = right?.realFiles?.length
      ? ` · 真实源 ${right.realFiles.map((f) => f.split("/").slice(-1)[0]).join("+")}`
      : "";
    return `<option value="${escapeHtml(name)}">${escapeHtml(name)} · A ${left?.frames.length || 0} / B ${right?.frames.length || 0}${blank}${realHint}</option>`;
  }).join("");
  for (const sel of selects) sel.innerHTML = optionsHtml;
  state.mobActionName = preferredOrder.find((name) => (
    hasVisibleMobFrame(leftData?.actions.find((action) => action.name === name))
    && hasVisibleMobFrame(rightData?.actions.find((action) => action.name === name))
  ))
    || actionNames.find((name) => (
      hasVisibleMobFrame(leftData?.actions.find((action) => action.name === name))
      && hasVisibleMobFrame(rightData?.actions.find((action) => action.name === name))
    ))
    || preferredOrder.find((name) => hasVisibleMobFrame(rightData?.actions.find((action) => action.name === name)))
    || actionNames.find((name) => hasVisibleMobFrame(rightData?.actions.find((action) => action.name === name)))
    || preferredOrder.find((name) => hasVisibleMobFrame(leftData?.actions.find((action) => action.name === name)))
    || actionNames[0]
    || "";
  for (const sel of selects) sel.value = state.mobActionName;
  state.mobElapsed = 0;
  state.mobPlaying = true;
  state.zoom = 1;
  $("zoomRange").value = 100;
  $("zoomValue").textContent = "100%";
  const playBtn = _mobEl("playBtn");
  if (playBtn) playBtn.textContent = "Ⅱ";
  $("leftMobMeta").textContent = leftData
    ? `${leftData.actions.length} 动作 · Lv.${leftData.stats.level ?? "?"}`
    : (leftError?.message || "主文件预览不可用");
  const activeSource = activeMobComparisonSource();
  $("rightMobSourceLabel").textContent = activeSource?.kind === "ms"
    ? "TMS MS 完整记录"
    : (activeSource?.label || "对比文件");
  $("rightMobMeta").textContent = rightData
    ? `${rightData.actions.length} 动作 · Lv.${rightData.stats.level ?? "?"}${mobPreviewRealSummary(rightData)}`
    : (rightError?.message || "对比预览不可用");
  $("previewMeta").textContent = actionNames.length
    ? `${actionNames.length} 个合并动作 · A/B 同步播放`
    : "没有可播放动作";
  showMobFrames();
  updateMobActionMigration();
}

function stopMobTimer() {
  clearTimeout(state.mobTimer);
  state.mobTimer = null;
}

function showMobFrames() {
  stopMobTimer();
  const sides = [
    {name: "left", data: state.preview, imageKey: "leftImage", counterKey: "leftCounter", realKey: "leftReal"},
    {name: "right", data: state.rightPreview, imageKey: "rightImage", counterKey: "rightCounter", realKey: "rightReal"},
  ];
  const remainingDelays = [];
  state.mobFrameIndices = {left: -1, right: -1};
  for (const side of sides) {
    const action = side.data?.actions.find((candidate) => candidate.name === state.mobActionName);
    const image = _mobEl(side.imageKey);
    const realBox = _mobEl(side.realKey);
    if (!image) continue;
    if (!action?.frames.length) {
      image.removeAttribute("src");
      image.hidden = true;
      const counter = _mobEl(side.counterKey);
      if (counter) counter.textContent = "此侧无该动作";
      if (realBox) realBox.innerHTML = "";
      continue;
    }
    const elapsed = state.mobElapsed % action.duration;
    let cursor = 0;
    let index = 0;
    for (let frameIndex = 0; frameIndex < action.frames.length; frameIndex += 1) {
      const end = cursor + action.frames[frameIndex].delay;
      if (elapsed < end) {
        index = frameIndex;
        remainingDelays.push(end - elapsed);
        break;
      }
      cursor = end;
    }
    state.mobFrameIndices[side.name] = index;
    const frame = action.frames[index];
    image.hidden = false;
    image.src = apiUrl(frame.url);
    image.style.marginLeft = `${(frame.origin.x - frame.width / 2) * state.zoom * -1}px`;
    image.style.marginTop = `${(frame.origin.y - frame.height) * state.zoom * -1}px`;
    image.style.transform = `scale(${state.zoom})`;
    const counter = _mobEl(side.counterKey);
    if (counter) counter.textContent = `${index + 1} / ${action.frames.length} · ${frame.delay} ms`;
    if (realBox) renderMobRealHint(realBox, frame, action);
  }
  updateFrameControls();
  if (state.mobPlaying && remainingDelays.length) {
    const nextDelay = Math.min(...remainingDelays);
    state.mobTimer = setTimeout(() => {
      state.mobElapsed += nextDelay;
      showMobFrames();
    }, nextDelay);
  }
}

function renderMobRealHint(box, frame, action) {
  const resolved = frame.resolved;
  if (frame.state === "linked" && resolved) {
    box.className = "real-hint linked";
    const displayPath = resolved.absPath || resolved.fileLabel || "";
    box.title = `本帧声明 ${frame.declaredWidth}×${frame.declaredHeight}，真实像素在 ${displayPath}/${resolved.path}`;
    box.innerHTML = `真实资源：<b>${resolved.width}×${resolved.height}</b> ← <code title="${escapeHtml(displayPath)}">${escapeHtml(displayPath)}/${escapeHtml(resolved.path)}</code>${frame.crossMob ? '<span class="real-chip cross">跨怪</span>' : ""}`;
    return;
  }
  if (frame.state === "orphan") {
    box.className = "real-hint orphan";
    box.title = "TMS 里这一帧确实没有可见像素";
    box.innerHTML = `本帧是<b>空占位</b>（${frame.declaredWidth}×${frame.declaredHeight}），TMS 侧没有可复制的像素`;
    return;
  }
  if (frame.state === "broken") {
    box.className = "real-hint orphan";
    box.title = frame.error || "";
    box.innerHTML = `真实资源解析失败：${escapeHtml(frame.error || "未知原因")}`;
    return;
  }
  const files = action.realFiles || [];
  box.className = "real-hint";
  box.innerHTML = files.length
    ? `本帧为真实像素 · 该动作真实资源：<code>${escapeHtml(files.join("</code>、<code>"))}</code>`
    : "";
}

function updateFrameControls() {
  const leftAction = state.preview?.actions.find((a) => a.name === state.mobActionName);
  const rightAction = state.rightPreview?.actions.find((a) => a.name === state.mobActionName);
  const leftIdx = state.mobFrameIndices?.left ?? -1;
  const rightIdx = state.mobFrameIndices?.right ?? -1;
  const leftTotal = leftAction?.frames.length || 0;
  const rightTotal = rightAction?.frames.length || 0;
  const hasBoth = leftTotal > 0 && rightTotal > 0;
  for (const key of ["prevBtn", "nextBtn", "copyBtoA", "copyAtoB", "frameCounter"]) {
    const el = _mobEl(key);
    if (!el) continue;
    if (key === "prevBtn" || key === "nextBtn") el.disabled = state.mobPlaying;
    else if (key === "copyBtoA") el.disabled = !hasBoth || rightIdx < 0;
    else if (key === "copyAtoB") el.disabled = !hasBoth || leftIdx < 0;
    else if (key === "frameCounter") {
      const globalIdx = Math.max(leftIdx, rightIdx);
      const globalTotal = Math.max(leftTotal, rightTotal);
      el.textContent = globalTotal > 0 ? `${globalIdx + 1} / ${globalTotal}` : "";
    }
  }
}

function stepMobFrame(delta) {
  if (state.mobPlaying) return;
  const leftAction = state.preview?.actions.find((a) => a.name === state.mobActionName);
  const rightAction = state.rightPreview?.actions.find((a) => a.name === state.mobActionName);
  const maxFrames = Math.max(leftAction?.frames.length || 0, rightAction?.frames.length || 0);
  if (!maxFrames) return;
  const currentIdx = Math.max(state.mobFrameIndices?.left ?? 0, state.mobFrameIndices?.right ?? 0);
  let newIdx = currentIdx + delta;
  if (newIdx < 0) newIdx = maxFrames - 1;
  if (newIdx >= maxFrames) newIdx = 0;
  // Convert frame index to elapsed time by summing delays up to that frame
  function elapsedForFrame(action, idx) {
    if (!action) return 0;
    let t = 0;
    for (let i = 0; i < idx && i < action.frames.length; i++) t += action.frames[i].delay;
    return t;
  }
  // Use left action timing if available, otherwise right
  const refAction = leftAction?.frames.length ? leftAction : rightAction;
  state.mobElapsed = elapsedForFrame(refAction, newIdx);
  showMobFrames();
}

async function copyMobFrame(fromSide) {
  const fromData = fromSide === "right" ? state.rightPreview : state.preview;
  const toPath = fromSide === "right" ? state.leftPath : state.rightPath;
  const fromAction = fromData?.actions.find((a) => a.name === state.mobActionName);
  const fromIdx = state.mobFrameIndices?.[fromSide] ?? -1;
  if (!fromAction || fromIdx < 0 || fromIdx >= fromAction.frames.length) return;
  const fromFrame = fromAction.frames[fromIdx];
  try {
    const data = await writeMobFrame({
      sourcePath: fromSide === "right" ? state.rightPath : state.leftPath,
      targetPath: toPath,
      sourceFramePath: fromFrame.path,
      actionName: state.mobActionName,
      frameIndex: fromIdx,
    });
    if (!data) return;
    if (!data.ok) throw new Error(data.error || "复制失败");
    showResult(`帧复制完成\n${data.sourceSummary}\n客户端：${data.clientOperation} · 服务端：${data.serverOperation}\n未受影响的记录：${data.rawScope?.protectedRecords ?? "?"} 条`);
    await loadComparison({backgroundPreview: true});
  } catch (error) {
    showResult(`复制失败: ${error.message}`, true);
  }
}

function applyZoom() {
  const percent = Math.round(state.zoom * 100);
  $("zoomValue").textContent = `${percent}%`;
  $("zoomRange").value = percent;
  if (state.kind === "map") {
    for (const view of Object.values(state.mapViews)) {
      const canvas = $(view.canvasId);
      const stage = $(view.stageId);
      if (!canvas.width) continue;
      const scaledWidth = canvas.width * state.zoom;
      const scaledHeight = canvas.height * state.zoom;
      canvas.style.transform = "none";
      canvas.style.width = `${scaledWidth}px`;
      canvas.style.height = `${scaledHeight}px`;
      canvas.style.marginLeft = `${Math.max(0, (stage.clientWidth - scaledWidth) / 2)}px`;
      canvas.style.marginTop = `${Math.max(0, (stage.clientHeight - scaledHeight) / 2)}px`;
    }
  }
  else showMobFrames();
}

function fitPreview() {
  if (state.kind === "map") {
    const ratios = Object.values(state.mapViews).flatMap((view) => {
      const canvas = $(view.canvasId);
      const stage = $(view.stageId);
      return canvas.width ? [(stage.clientWidth - 18) / canvas.width, (stage.clientHeight - 18) / canvas.height] : [];
    });
    state.zoom = ratios.length ? Math.max(.1, Math.min(2, ...ratios)) : 1;
  } else {
    state.zoom = 1;
  }
  applyZoom();
  for (const view of Object.values(state.mapViews)) $(view.stageId).scrollTo({left: 0, top: 0});
}

function nodeTypeExplanation(type, semantic) {
  const explanations = {
    canvas: `<div class="type-explain"><strong>Canvas（画布）</strong> — 存储实际图片像素数据的节点。<br>
      包含 ARGB4444 格式的 PNG 图片、尺寸（width×height）、origin（锚点坐标，用于对齐到角色脚底）、delay（帧显示时长 ms）。<br>
      <em>格式说明：</em> format=1 为 ARGB4444（标准格式），format2=0 为无额外压缩。</div>`,
    uol: `<div class="type-explain type-explain-uol"><strong>UOL（引用）</strong> — 不存储实际数据，而是指向另一个节点的"快捷方式"。<br>
      值是相对路径。戴米安 skill2 的 0–9 是 <code>../skill1/N</code>；skill4 的 0–1 是 <code>../skill3/N</code>（TMS 1×1 _outlink），不是 skill1。<br>
      客户端从 0 连播到最后一帧；缺目标会崩。复制时保持原序号，不要把缺口压成 0..n-1，也不要用 stand 去填。</div>`,
    imgdir: `<div class="type-explain"><strong>imgdir（容器）</strong> — 组织子节点的文件夹节点，本身没有值。<br>
      用于构建树形结构，如 <code>attack1/</code> 下包含帧 0~N 和 info。</div>`,
    vector: `<div class="type-explain"><strong>Vector（向量）</strong> — 存储两个整数 (x, y) 的节点。<br>
      常用于 origin（锚点）、range（范围）、lt/rb（判定框角点）。</div>`,
    string: `<div class="type-explain"><strong>String（字符串）</strong> — 文本值节点。</div>`,
    int: `<div class="type-explain"><strong>Int（整数）</strong> — 32 位整数值节点。</div>`,
    short: `<div class="type-explain"><strong>Short（短整数）</strong> — 16 位整数值节点，范围 -32768~32767。</div>`,
    long: `<div class="type-explain"><strong>Long（长整数）</strong> — 64 位整数值节点。</div>`,
    float: `<div class="type-explain"><strong>Float（浮点数）</strong> — 单精度浮点值节点。</div>`,
    double: `<div class="type-explain"><strong>Double（双精度浮点）</strong> — 双精度浮点值节点。</div>`,
    "null": `<div class="type-explain"><strong>Null（空节点）</strong> — 无值的占位节点。</div>`,
  };
  return explanations[type] || "";
}

function prettyValue(meta) {
  if (!meta) return "—";
  if (meta.value !== undefined) return typeof meta.value === "object" ? JSON.stringify(meta.value) : String(meta.value);
  if (meta.type === "canvas") {
    const w = meta.width ?? 0, h = meta.height ?? 0;
    const placeholder = (w <= 4 && h <= 4) ? " (占位)" : "";
    return `${w} × ${h} · format ${meta.format ?? "?"}${placeholder}`;
  }
  if (meta.childCount !== undefined) return `${meta.childCount} 个子节点`;
  return "—";
}

function selectNode(path) {
  state.selectedPath = path;
  renderTree();
  const row = state.rowByPath.get(path);
  if (!row) return;
  $("selectedPath").textContent = path || "/";
  $("selectedPath").title = path || "/";
  updateNodeActions();
  revealSelectedMapContent();
  // 怪物模式下，点击动作节点（stand/attack1 等）自动切换动画到该动作
  if (state.kind === "mob" && path) {
    const topLevel = path.split("/")[0];
    const actionNames = Array.from(new Set([
      ...(state.preview?.actions || []).map((a) => a.name),
      ...(state.rightPreview?.actions || []).map((a) => a.name),
    ]));
    if (actionNames.includes(topLevel) && topLevel !== state.mobActionName) {
      state.mobActionName = topLevel;
      state.mobElapsed = 0;
      for (const sel of [$("actionSelect"), $("actionSelectInline")].filter(Boolean)) sel.value = topLevel;
      showMobFrames();
      updateMobActionMigration();
    }
  }
}

function updateNodeActions() {
  const leftExists = state.leftInfo?.exists !== false;
  const projectPath = state.leftPath.startsWith("clien/") || state.leftPath.startsWith("gms-server/");
  const clientImgPath = state.leftPath.startsWith("clien/") && state.leftInfo?.format === "img";
  const writable = Boolean(state.leftInfo && leftExists && projectPath);
  const copyWritable = Boolean(state.leftInfo && projectPath);
  const row = state.selectedPath === null ? null : state.rowByPath.get(state.selectedPath);
  const left = row?.left;
  const copyCompatibility = row?.right?.compatibility;
  const supportedCopyTypes = new Set(["imgdir", "short", "int", "long", "float", "double", "string", "vector", "uol", "null"]);
  const mobProjectableTypes = new Set(["imgdir", "canvas", "uol", "short", "int", "long", "float", "double", "string", "vector", "null"]);
  const unsafeDescendants = row ? state.rows.filter((candidate) => (
    (row.path === "" || candidate.path === row.path || candidate.path.startsWith(`${row.path}/`))
    && candidate.right
    && (candidate.right.compatibility?.status !== "ok" || !supportedCopyTypes.has(candidate.right.type))
  )) : [];
  const selectedSupported = Boolean(row?.right && supportedCopyTypes.has(row.right.type));
  const mobProjectable = state.kind === "mob" && Boolean(row?.right && mobProjectableTypes.has(row.right.type));
  const safeToCopy = mobProjectable || (copyCompatibility?.status === "ok" && selectedSupported);
  const relatedRows = row ? state.rows.filter((candidate) => (
    row.path === "" || candidate.path === row.path || candidate.path.startsWith(`${row.path}/`)
  )) : [];
  const referencedResources = Array.from(new Map(relatedRows.flatMap((candidate) => candidate.resources || []).map((resource) => (
    [`${resource.kind}:${resource.name}`, resource]
  ))).values()).filter((resource) => resource.status !== "ready");
  const autoResources = referencedResources.filter((resource) => resource.autoCopy);
  const blockedEntities = referencedResources.filter((resource) => ["npc", "mob"].includes(resource.kind) && !resource.autoCopy);
  const mergeIntoEmpty = Boolean(
    left?.type === "imgdir" && Number(left.childCount || 0) === 0 && row?.right?.type === "imgdir"
  );
  const resourceOnlyRepair = Boolean(left && autoResources.length && !blockedEntities.length && !mergeIntoEmpty);
  const mergeMissing = Boolean(
    state.kind === "mob" && left?.type === "imgdir" && row?.right?.type === "imgdir"
  );
  const validParent = left?.type === "imgdir" || (state.leftInfo?.format === "xml" && left?.type === "canvas");
  $("createMainBtn").hidden = leftExists || !clientImgPath;
  $("createMainBtn").disabled = leftExists || !clientImgPath;
  $("copyTmsBtn").textContent = resourceOnlyRepair
    ? "补齐选中节点的引用资源"
    : mergeMissing
    ? "补齐选中节点的兼容投影"
    : "复制选中的 TMS 节点到 A";
  $("copyTmsBtn").title = resourceOnlyRepair
    ? `保留当前地图节点不变，仅迁移 ${autoResources.length} 个不完整引用资源（NPC/怪物会同步服务端 XML 和 String）`
    : safeToCopy
    ? (unsafeDescendants.length
      ? `复制整个兼容子树；自动略过 ${unsafeDescendants.length} 个现代或不兼容后代，首个为 ${unsafeDescendants[0].path}`
      : "按原路径复制整个节点；缺失的主文件和父目录会自动建立，并同步客户端 IMG 与服务端 XML")
    : (copyCompatibility?.suggestion || "该节点不能直接复制到旧端");
  if (mobProjectable) {
    const infoCopy = row?.path === "info" || (row?.path || "").startsWith("info/");
    $("copyTmsBtn").title = infoCopy
      ? "投影 info：补伤害字段并把 PDRate/MDRate>70 清 0；戴米安技能表改成 100/101/123/128，不占用 185/176"
      : mergeMissing
      ? "只补 A 里缺失的子节点：按 TMS 时间轴接 UOL（跨动作 _outlink 如 skill4→skill3），Canvas 投影，并过滤不兼容字段"
      : unsafeDescendants.length
      ? `自动投影为旧端结构：Canvas 转 ARGB4444，UOL 补到 A 已有目标，并略过 ${unsafeDescendants.length} 个现代/不兼容节点`
      : "自动投影为旧端结构：Canvas 转 ARGB4444；保持 TMS 帧号（skill2 起手 skill1，skill4 起手 skill3）";
  }
  if (!resourceOnlyRepair && safeToCopy && autoResources.length) {
    $("copyTmsBtn").title += `；同时自动迁移 ${autoResources.length} 个缺失引用资源（NPC/怪物会同步 String）`;
  }
  if (safeToCopy && blockedEntities.length) {
    $("copyTmsBtn").title = `引用资源无法安全自动迁移：${blockedEntities.map((resource) => `${resource.kind.toUpperCase()} ${resource.name}`).join("、")}`;
  }
  $("copyTmsBtn").disabled = !(
    copyWritable && clientImgPath && row?.right && (!row?.left || mergeIntoEmpty || resourceOnlyRepair || mergeMissing)
    && safeToCopy && !blockedEntities.length && state.rightInfo?.format === "img"
  );
  $("addRootBtn").disabled = !writable;
  $("addChildBtn").disabled = !(writable && validParent);
  $("deleteBtn").disabled = !(writable && left && Boolean(row.path));
  $("exportBtn").disabled = !writable;
  const dialogCopy = $("dialogCopyBtn");
  if (dialogCopy) {
    dialogCopy.disabled = $("copyTmsBtn").disabled;
    dialogCopy.textContent = $("copyTmsBtn").textContent;
    dialogCopy.title = $("copyTmsBtn").title;
  }
  if ($("dialogAddChildBtn")) $("dialogAddChildBtn").disabled = $("addChildBtn").disabled;
  if ($("dialogDeleteBtn")) $("dialogDeleteBtn").disabled = $("deleteBtn").disabled;
}

function setInspectorMode(mode) {
  if (mode === "node") {
    openNodeDetailDialog();
    return;
  }
  const compatibilityMode = mode === "compatibility";
  const diagnosticMode = mode === "diagnostic";
  const serverControlMode = mode === "serverControl";
  $("compatibility").hidden = !compatibilityMode;
  $("crashDiagnostic").hidden = !diagnosticMode;
  if ($("serverControlHelp")) $("serverControlHelp").hidden = !serverControlMode;
  $("compatibilityTab").classList.toggle("active", compatibilityMode);
  $("diagnosticTab").classList.toggle("active", diagnosticMode);
  $("nodeDetailTab").classList.toggle("active", false);
  $("serverControlTab")?.classList.toggle("active", serverControlMode);
  $("compatibilityTab").setAttribute("aria-selected", String(compatibilityMode));
  $("diagnosticTab").setAttribute("aria-selected", String(diagnosticMode));
  $("nodeDetailTab").setAttribute("aria-selected", "false");
  $("serverControlTab")?.setAttribute("aria-selected", String(serverControlMode));
  $("serverControlTab") && ($("serverControlTab").hidden = state.kind !== "mob");
  if (diagnosticMode && state.kind === "map" && state.leftInfo?.exists !== false && state.diagnosticPath !== state.leftPath) {
    runCrashDiagnostic();
  } else if (serverControlMode) {
    renderServerControlHelp(state.selectedPath === null ? null : state.rowByPath.get(state.selectedPath));
  }
}

function closeNodeDetailDialog() {
  $("nodeDetailDialog")?.setAttribute("hidden", "");
  $("nodeDetailTab")?.classList.remove("active");
  $("nodeDetailTab")?.setAttribute("aria-selected", "false");
}

function openNodeDetailDialog() {
  const dialog = $("nodeDetailDialog");
  if (!dialog) return;
  $("nodeDetailPath").textContent = state.selectedPath || "/";
  $("nodeDetailPath").title = state.selectedPath || "/";
  $("nodeDetailTab").classList.add("active");
  $("nodeDetailTab").setAttribute("aria-selected", "true");
  if (state.selectedPath !== null && state.rowByPath.has(state.selectedPath)) {
    renderInspector(state.rowByPath.get(state.selectedPath));
  } else {
    $("inspector").className = "inspector empty-state compact";
    $("inspector").innerHTML = '<span class="empty-mark small" aria-hidden="true">⌖</span><strong>选择左侧节点</strong><span>对比树里点选节点后，会在这里显示属性、差异和可编辑值。</span>';
    $("editActions").hidden = true;
  }
  dialog.hidden = false;
}

function diagnosticConfidence(value) {
  return ({high: "高", medium: "中", low: "低"})[value] || value;
}

function diagnosticPhaseOptions(selected = state.diagnosticPhase) {
  const options = [
    ["unknown", "时机未知"],
    ["map_load", "进图瞬间（尚未看到怪物）"],
    ["entity_appear", "怪物/NPC 首次出现"],
    ["attack", "怪物攻击时"],
    ["death", "怪物死亡时"],
  ];
  return options.map(([value, label]) => `<option value="${value}"${value === selected ? " selected" : ""}>${label}</option>`).join("");
}

function diagnosticPromptMarkup(title = "检查地图还是生命资源导致崩溃", detail = "解析场景源链接、区域稀有度、实际 Canvas 和生命资源。", button = "运行崩溃诊断") {
  return `<div class="empty-state compact"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span><label class="diagnostic-phase-label">崩溃发生阶段<select id="crashPhase">${diagnosticPhaseOptions()}</select></label><label class="diagnostic-phase-label">同样崩溃地图<input id="crashPeerMaps" value="${escapeHtml(state.diagnosticPeers)}" placeholder="450005242" inputmode="numeric"></label><button id="runDiagnosticBtn" class="primary-button" type="button">${escapeHtml(button)}</button></div>`;
}

function renderCaseControl(report) {
  const comparison = report.caseControl;
  if (!comparison?.enabled) return "";
  const exclusive = comparison.exclusive.length
    ? comparison.exclusive.map((item) => `<tr><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.mapPath || "–")}</td><td>${escapeHtml(Object.entries(item.casePaths).map(([id, paths]) => `${id}: ${paths.join(", ") || "–"}`).join("；"))}</td><td>${item.controlCount}/${comparison.parsedControlCount}</td></tr>`).join("")
    : '<tr><td colspan="4">没有崩溃组独占的静态特征。</td></tr>';
  const counterexamples = comparison.counterexamples.length
    ? `<p class="diagnostic-counterexamples">可工作反例：${comparison.counterexamples.map((item) => `${escapeHtml(item.title)} → ${escapeHtml(item.controlMaps.join(", "))}`).join("；")}</p>`
    : "";
  return `<section class="diagnostic-section"><h3>地区病例对照</h3><p>${escapeHtml(comparison.caseMaps.join(" + "))} 对比 ${comparison.parsedControlCount} 张同地区地图。${escapeHtml(comparison.conclusion)}</p><div class="diagnostic-table-wrap"><table class="diagnostic-table"><thead><tr><th>独占特征</th><th>节点</th><th>崩溃图路径</th><th>对照命中</th></tr></thead><tbody>${exclusive}</tbody></table></div>${counterexamples}</section>`;
}

function renderCrashDiagnostic(report) {
  const container = $("crashDiagnostic");
  const findings = report.findings.length ? report.findings.map((item) => `
    <div class="diagnostic-finding">
      <div class="diagnostic-finding-head"><strong>${escapeHtml(item.title)}</strong><span class="diagnostic-badge ${escapeHtml(item.severity)}">${item.severity === "crash" ? "高风险" : "嫌疑"} · ${escapeHtml(diagnosticConfidence(item.confidence))}置信</span></div>
      <p>${escapeHtml(item.detail)}</p>
      ${item.evidence?.length ? `<ul class="diagnostic-evidence">${item.evidence.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>` : ""}
      <p class="diagnostic-action">${escapeHtml(item.action)}</p>
      <div class="diagnostic-links">
        ${item.mapPath ? `<button type="button" data-diagnostic-path="${escapeHtml(item.mapPath)}">定位地图节点 ${escapeHtml(item.mapPath)}</button>` : ""}
        ${item.entityKind === "mob" && item.entityId ? `<button type="button" data-diagnostic-entity="${escapeHtml(item.entityId)}">打开怪物 ${escapeHtml(item.entityId)}</button>` : ""}
      </div>
    </div>`).join("") : '<span class="compat-empty">没有发现静态崩溃风险。</span>';
  const entities = report.entities.length
    ? report.entities.map((item) => `${item.kind === "mob" ? "怪物" : "NPC"} ${item.id} × ${item.spawns}${item.canvases !== undefined ? ` · ${item.visible}/${item.canvases} 可见 Canvas` : ""}`).join("<br>")
    : "无生命节点";
  container.innerHTML = `
    <div class="diagnostic-toolbar"><label>崩溃阶段<select id="crashPhase">${diagnosticPhaseOptions(report.phase)}</select></label><label>同样崩溃地图<input id="crashPeerMaps" value="${escapeHtml(state.diagnosticPeers)}" placeholder="450005242" inputmode="numeric"></label><button id="runDiagnosticBtn" type="button">重新诊断</button></div>
    <div class="diagnostic-overview">
      <strong>${escapeHtml(report.conclusion)}</strong>
      <span>${escapeHtml(report.confidence)}置信度 · ${escapeHtml(report.phaseLabel)} · 地图 ${report.scores.map + report.scores.resource} 分 · 生命资源 ${report.scores.entity} 分 · 服务端 ${report.scores.server} 分</span>
      <div class="diagnostic-counts">
        <span><b>${report.counts.checked}</b><small>检查组</small></span>
        <span><b>${report.counts.crash}</b><small>高风险</small></span>
        <span><b>${report.counts.warn}</b><small>嫌疑</small></span>
        <span><b>${report.counts.verified}</b><small>已排除</small></span>
      </div>
      <p>${escapeHtml(report.note)}</p>
    </div>
    <section class="diagnostic-section"><h3>场景证据链</h3><p>追踪 ${report.sceneResources.resources.length} 条 Back/Obj/Tile 引用；同区域 ${report.sceneResources.parsedMapCount}/${report.sceneResources.regionalMapCount} 张地图解析成功，发现 ${report.sceneResources.suspects.length} 条优先 A/B 候选。</p></section>
    ${renderCaseControl(report)}
    <section class="diagnostic-section"><h3>地图生命资源</h3><p>${entities}</p></section>
    <section class="diagnostic-section"><h3>风险与嫌疑</h3>${findings}</section>
    <section class="diagnostic-section"><h3>已通过检查</h3><ul class="diagnostic-verified">${report.verified.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
    <section class="diagnostic-section"><h3>最小 A/B 隔离顺序</h3><ol class="diagnostic-isolation">${report.isolation.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol></section>`;
  container.querySelectorAll("[data-diagnostic-path]").forEach((button) => button.addEventListener("click", () => revealNode(button.dataset.diagnosticPath)));
  container.querySelectorAll("[data-diagnostic-entity]").forEach((button) => button.addEventListener("click", () => openDiagnosticMob(button.dataset.diagnosticEntity)));
  $("runDiagnosticBtn")?.addEventListener("click", runCrashDiagnostic);
}

async function runCrashDiagnostic() {
  if (state.kind !== "map" || !state.leftPath || state.leftInfo?.exists === false) return;
  const requestedPath = state.leftPath;
  state.diagnosticPhase = $("crashPhase")?.value || state.diagnosticPhase;
  state.diagnosticPeers = $("crashPeerMaps")?.value ?? state.diagnosticPeers;
  const caseMapIds = state.diagnosticPeers.split(/[\s,，]+/).map((value) => value.trim()).filter(Boolean);
  $("crashDiagnostic").innerHTML = '<div class="empty-state compact"><strong>正在检查地图和生命资源</strong><span>会解码被引用实体的实际 Canvas 像素。</span></div>';
  try {
    const report = await post("/api/diagnose-map", {sourcePath: requestedPath, phase: state.diagnosticPhase, caseMapIds});
    if (state.leftPath !== requestedPath) return;
    state.diagnostic = report;
    state.diagnosticPath = requestedPath;
    $("diagnosticCount").textContent = report.counts.crash + report.counts.warn;
    renderCrashDiagnostic(report);
  } catch (error) {
    $("crashDiagnostic").innerHTML = diagnosticPromptMarkup("诊断失败", error.message, "重新诊断");
    $("runDiagnosticBtn")?.addEventListener("click", runCrashDiagnostic);
  }
}

async function openDiagnosticMob(id) {
  setKind("mob");
  $("itemId").value = id;
  $("leftPath").value = `clien/Data/Mob/${id}.img`;
  $("rightPath").value = `${tmsDataRoot}/Mob/_Canvas/${id}.img`;
  await loadMobSources(id, true);
  await loadComparison();
}

function renderCompatibility(report) {
  const container = $("compatibility");
  if (!report) {
    $("compatibilityCount").textContent = "0";
    container.innerHTML = '<div class="empty-state compact"><strong>当前类型暂无兼容分析</strong><span>节点详情仍可查看完整 A/B 差异。</span></div>';
    return;
  }
  if (report.rightAvailable === false) {
    $("compatibilityCount").textContent = "0";
    container.innerHTML = '<div class="empty-state compact"><strong>没有 TMS 对比文件</strong><span>已加载 A 主文件的节点和地图预览；当前仅浏览本地资源，不进行 A/B 兼容分析。</span></div>';
    return;
  }
  $("compatibilityCount").textContent = report.missingResourceCount + report.modernCandidateCount;
  const statusText = {ready: "旧客户端可解析", missingFile: "旧客户端缺文件", missingCanvas: "Canvas 路径不兼容", missingServer: "服务端资源缺失", missingString: "名称记录缺失"};
  const statusAdvice = {
    ready: "可复用现有资源，但节点仍需投影到旧版结构。",
    missingFile: "不要整包复制 TMS IMG；提取必要 Canvas，转换为 GMS ARGB4444 后通过新增资源或增量记录迁移。",
    missingCanvas: "同名文件不等于兼容；映射到旧客户端支持的层级，并保留 origin、delay、z 和动画顺序。",
    missingServer: "客户端资源存在，但服务端实体 XML 不完整；复制 NPC/怪物节点时会同步补齐。",
    missingString: "实体动画存在，但客户端或服务端 String 记录不完整；复制 NPC/怪物节点时会增量补齐。",
  };
  const roots = report.addedRoots.length
    ? report.addedRoots.slice(0, 16).map((path) => `<button class="compat-path" type="button" data-compat-path="${escapeHtml(path)}">${escapeHtml(path)}</button>`).join("")
    : '<span class="compat-empty">没有 B 独有根分支</span>';
  const categories = report.categories.map((group) => `
    <section class="compat-section">
      <div class="compat-section-head"><strong>${escapeHtml(group.title)}</strong><span class="risk risk-${group.risk === "高" ? "high" : group.risk === "中" ? "medium" : "unknown"}">${escapeHtml(group.risk)}风险 · ${group.count}</span></div>
      <p>${escapeHtml(group.guidance)}</p>
      <div class="compat-path-list">${group.paths.slice(0, 8).map((path) => `<button class="compat-path" type="button" data-compat-path="${escapeHtml(path)}">${escapeHtml(path)}</button>`).join("")}</div>
      ${group.count > 8 ? `<small>另有 ${group.count - 8} 个节点，可在左侧勾选“仅差异”后搜索。</small>` : ""}
    </section>`).join("");
  const changedNodes = report.changedNodes.length ? report.changedNodes.slice(0, 14).map((item) => `
    <div class="finding-row">
      <button class="compat-path" type="button" data-compat-path="${escapeHtml(item.path)}">${escapeHtml(item.path)}</button>
      <div class="finding-values"><span>A ${escapeHtml(JSON.stringify(item.leftValue))}</span><span>B ${escapeHtml(JSON.stringify(item.rightValue))}</span></div>
      <strong>${escapeHtml(item.meaning)}</strong>
      <p>${escapeHtml(item.scope)}</p>
      <p class="migration-advice">${escapeHtml(item.migration)}</p>
    </div>`).join("") : '<span class="compat-empty">没有标量或 Canvas 关键变化</span>';
  const findings = report.findings.length ? report.findings.slice(0, 16).map((item) => `
    <div class="finding-row finding-${item.status}">
      <div class="resource-title"><button class="compat-path" type="button" data-compat-path="${escapeHtml(item.path)}">${escapeHtml(item.path)}</button><span>${escapeHtml(item.label)}</span></div>
      <strong>${escapeHtml(item.meaning)}</strong>
      <p>${escapeHtml(item.reason)}</p>
      <p class="migration-advice">${escapeHtml(item.suggestion || item.migration)}</p>
    </div>`).join("") : '<span class="compat-empty">B 独有节点中没有命中已知现代规则</span>';
  const resources = report.resources.length ? report.resources.map((item) => `
    <div class="resource-row status-${item.status}">
      <div class="resource-title"><strong>${escapeHtml(item.kind.toUpperCase())} · ${escapeHtml(item.name)}</strong><span>${statusText[item.status] || item.status}</span></div>
      <code>${escapeHtml(item.clientPath)}${item.canvasPaths.length ? ` → ${escapeHtml(item.canvasPaths.join(" · "))}` : ""}</code>
      ${item.contract?.issues?.length ? `<p class="resource-issues">缺失项：${escapeHtml(item.contract.issues.join("；"))}</p>` : ""}
      <p>${statusAdvice[item.status]}</p>
      ${item.autoCopy ? `<small>复制引用节点时将自动迁移该资源${["npc", "mob"].includes(item.kind) ? "、服务端 XML 和 String 记录" : "的兼容 Canvas 分支"}。</small>` : ""}
      ${item.nodes[0] ? `<button class="compat-path resource-node" type="button" data-compat-path="${escapeHtml(item.nodes[0])}">定位引用节点：${escapeHtml(item.nodes[0])}</button>` : ""}
    </div>`).join("") : '<span class="compat-empty">没有可审计的地图资源引用</span>';
  container.innerHTML = `
    <div class="compat-overview">
      <strong>B 比 A 多 ${report.rightOnlyCount} 个节点</strong>
      <span>${report.addedRootCount} 个新增根分支 · ${report.incompatibleCount} 个不兼容 · ${report.modernCandidateCount} 个现代 · ${report.reviewCount} 个待审 · ${report.missingResourceCount} 个资源问题</span>
      <p>“B 独有”只表示旧客户端同路径不存在；只有命中已知现代结构或资源审计失败时才标记兼容风险。</p>
    </div>
    <section class="compat-section priority-section"><div class="compat-section-head"><strong>关键值变化与修改指引</strong><span>${report.changedNodes.length}</span></div>${changedNodes}</section>
    <section class="compat-section priority-section"><div class="compat-section-head"><strong>B 独有现代/不兼容节点</strong><span>${report.findings.length}</span></div>${findings}</section>
    <section class="compat-section"><div class="compat-section-head"><strong>B 新增根分支</strong><span>${report.addedRootCount}</span></div><div class="compat-path-list">${roots}</div></section>
    ${categories}
    <section class="compat-section resources"><div class="compat-section-head"><strong>现代资源与旧客户端覆盖</strong><span>${report.resources.length}</span></div>${resources}</section>`;
  container.querySelectorAll("[data-compat-path]").forEach((button) => button.addEventListener("click", () => revealNode(button.dataset.compatPath)));
}

function revealNode(path) {
  if (!state.rowByPath.has(path)) return;
  $("treeSearch").value = "";
  $("diffOnly").checked = false;
  const parts = path.split("/");
  for (let index = 1; index < parts.length; index += 1) state.expanded.add(parts.slice(0, index).join("/"));
  selectNode(path);
  requestAnimationFrame(() => {
    const target = Array.from($("tree").querySelectorAll(".tree-row")).find((row) => row.dataset.path === path);
    target?.scrollIntoView({block: "center"});
  });
}

function renderInspector(row) {
  const left = row.left;
  const right = row.right;
  const fields = [
    ["状态", ({same: "一致", changed: "已修改", leftOnly: "仅主文件", rightOnly: "仅对比文件"})[row.status]],
    ["类型", [left?.type ?? "—", right?.type ?? "—"]],
    ["值", [prettyValue(left), prettyValue(right)]],
  ];
  if (left?.origin || right?.origin) fields.push(["原点", [JSON.stringify(left?.origin ?? "—"), JSON.stringify(right?.origin ?? "—")]]);
  if (isLinkNode(left) || isLinkNode(right)) {
    fields.push(["引用目标", [linkTarget(left) || "—", linkTarget(right) || "—"]]);
    const resolved = resolveUolTarget(row.path, linkTarget(right) || linkTarget(left));
    if (resolved) fields.push(["解析路径", resolved]);
  }
  const table = fields.map(([label, values]) => {
    if (!Array.isArray(values)) return `<tr><th>${label}</th><td colspan="2">${escapeHtml(values)}</td></tr>`;
    const different = values[0] !== values[1] ? "different" : "";
    return `<tr><th>${label}</th><td class="${different}">${escapeHtml(values[0])}</td><td class="${different}">${escapeHtml(values[1])}</td></tr>`;
  }).join("");
  const inspector = $("inspector");
  const semantic = left || right || {};
  const leftCompatibility = left?.compatibility;
  const rightCompatibility = right?.compatibility;
  // Modern node badge
  const isModern = row.status === "rightOnly" || (rightCompatibility?.status === "modern");
  const modernBadge = isModern ? '<span class="modern-badge">现代节点</span>' : "";
  // Canvas preview
  let canvasPreview = "";
  if (left?.type === "canvas" && left.width > 0 && left.height > 0) {
    const url = apiUrl(`/api/canvas?file=${encodeURIComponent(state.leftPath)}&path=${encodeURIComponent(row.path)}`);
    canvasPreview = `<div class="canvas-preview-section">
      <div class="side-label">Canvas 预览</div>
      <div class="canvas-preview-wrap">
        <img class="canvas-preview-img" src="${url}" alt="${escapeHtml(row.path)}" onerror="this.style.display='none'">
        <div class="canvas-preview-info">${left.width}×${left.height} · format ${left.format ?? "?"}${left.delay != null ? ` · ${left.delay}ms` : ""}</div>
      </div>
    </div>`;
  }
  if (right?.type === "canvas" && right.width > 0 && right.height > 0 && !canvasPreview) {
    const url = apiUrl(`/api/canvas?file=${encodeURIComponent(state.rightPath)}&path=${encodeURIComponent(row.path)}`);
    canvasPreview = `<div class="canvas-preview-section">
      <div class="side-label">Canvas 预览 (B)</div>
      <div class="canvas-preview-wrap">
        <img class="canvas-preview-img" src="${url}" alt="${escapeHtml(row.path)}" onerror="this.style.display='none'">
        <div class="canvas-preview-info">${right.width}×${right.height} · format ${right.format ?? "?"}</div>
      </div>
    </div>`;
  }
  // Node type explanation
  const typeExplanation = nodeTypeExplanation(left?.type || right?.type, semantic);
  const uolJumpTarget = resolveUolTarget(row.path, linkTarget([right, left].find(isLinkNode)));
  const uolJumpMarkup = uolJumpTarget
    ? `<p><button id="jumpUolBtn" type="button" data-path="${escapeHtml(uolJumpTarget)}">跳转到 ${escapeHtml(uolJumpTarget)}</button></p>`
    : "";
  const semanticMarkup = `<div class="node-explanation">
    <div class="side-label">节点解析 ${modernBadge}</div>
    ${typeExplanation}
    <dl>
      <dt>意义</dt><dd>${escapeHtml(semantic.meaning || "暂无专用说明")}</dd>
      <dt>值域</dt><dd>${escapeHtml(semantic.valueGuide || "需结合客户端读取逻辑判断")}</dd>
      <dt>影响范围</dt><dd>${escapeHtml(semantic.scope || "当前节点")}</dd>
      <dt>兼容动作</dt><dd class="migration-advice">${escapeHtml(semantic.migration || "先对照旧端可工作结构")}</dd>
      ${semantic.placement ? `<dt>添加位置</dt><dd>${escapeHtml(semantic.placement)}</dd>` : ""}
    </dl>
    ${semantic.structure ? `<div class="side-label">目标节点结构</div><pre class="node-structure">${escapeHtml(semantic.structure)}</pre>` : ""}
    <div class="compat-verdicts">
      <span class="verdict verdict-${escapeHtml(leftCompatibility?.status || "missing")}">A ${escapeHtml(leftCompatibility?.label || "缺失")}</span>
      <span class="verdict verdict-${escapeHtml(rightCompatibility?.status || "missing")}">B ${escapeHtml(rightCompatibility?.label || "缺失")}</span>
    </div>
    ${leftCompatibility?.reason ? `<p><b>A：</b>${escapeHtml(leftCompatibility.reason)}</p>` : ""}
    ${rightCompatibility?.reason ? `<p><b>B：</b>${escapeHtml(rightCompatibility.reason)}</p>` : ""}
  </div>`;
  const resourceMarkup = (row.resources || []).length ? `<div class="node-explanation"><div class="side-label">引用资源状态</div>${row.resources.map((resource) => `
    <p><b>${escapeHtml(resource.kind.toUpperCase())} ${escapeHtml(resource.name)}</b> · ${resource.status === "ready" ? "完整" : escapeHtml((resource.issues || []).join("；") || "缺失或不兼容")}${resource.autoCopy ? "；复制该节点时自动迁移" : ""}</p>
    <code>${escapeHtml(resource.clientPath)}</code>`).join("")}</div>` : "";
  inspector.className = "inspector";
  const childFramesMarkup = `<div id="childFramesSection" class="node-explanation" style="display:none"><div class="side-label">子节点 / 帧详情</div><div id="childFramesContent">加载中…</div></div>`;
  const mobManifestMarkup = state.kind === "mob"
    ? `<div id="mobResourceSection" class="node-explanation"><div class="side-label">TMS 真实资源清单</div><div id="mobResourceContent" class="compat-empty">待解析…</div></div>`
    : "";
  inspector.innerHTML = `<div class="node-detail-col">${canvasPreview}${semanticMarkup}${resourceMarkup}${mobManifestMarkup}${serverControlMarkup(row)}</div><div class="node-detail-col"><div class="side-label">属性对比</div><table class="compare-table"><thead><tr><th>属性</th><th><span class="column-badge a">A</span>主文件</th><th><span class="column-badge b">B</span>对比</th></tr></thead><tbody>${table}</tbody></table>${childFramesMarkup}${editorMarkup(left)}</div>`;
  const leftXml = state.leftInfo?.format === "xml";
  const editable = Boolean(left?.editable && (leftXml || state.leftInfo?.format === "img"));
  $("editActions").hidden = false;
  $("saveBtn").hidden = !editable;
  $("saveBtn").disabled = !editable;
  updateNodeActions();
  // B 侧真实资源清单：把占位帧解析回真实文件，解决"只看到 1×1 占位"
  if (state.kind === "mob" && state.rightPath) {
    loadMobResourceManifest(state.rightPath);
  }
  // Load child frames if node is a container (imgdir with children)
  if (row.path && ((left?.type === "imgdir" && Number(left.childCount || 0) > 0) || (row?.right?.type === "imgdir" && Number(row.right.childCount || 0) > 0))) {
    loadChildFrames(row.path, left?.childCount || row?.right?.childCount);
  }
  $("openServerControlBtn")?.addEventListener("click", () => setInspectorMode("serverControl"));
  bindMobSkillOpenButtons($("inspector"));
}

function serverControlMarkup(row) {
  const help = row?.serverControl;
  if (!help) return "";
  return `<div class="node-explanation server-control-card">
    <div class="side-label">服务端控制</div>
    <p><b>${escapeHtml(help.template?.title || "")}</b> · ${escapeHtml(help.playback || "")}</p>
    ${(help.timeline || []).length ? `<ol class="playback-timeline">${help.timeline.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>` : ""}
    <p>${escapeHtml(help.javaHint || "")}</p>
    ${mobSkillCardMarkup(help.mobSkill)}
    <p><button id="openServerControlBtn" type="button">打开帮助模块</button></p>
  </div>`;
}

function mobSkillCardMarkup(mapping) {
  if (!mapping) return "";
  const advice = mapping.advice || {};
  const tms = mapping.tmsCanvas || {};
  const openId = mapping.skillId;
  const openLv = mapping.level || 1;
  return `<div class="mob-skill-map">
    <div class="side-label">MobSkill 对应</div>
    <p>类型 <b>${escapeHtml(String(mapping.skillId ?? "未绑定"))}</b> ${escapeHtml(mapping.typeName || "")}
      · 档 <b>${escapeHtml(String(mapping.level ?? "—"))}</b>
      · 动作 skill${escapeHtml(String(mapping.action ?? "—"))}
      · 节点 <code>${escapeHtml(mapping.nodePath || "—")}</code></p>
    <p class="verdict verdict-${escapeHtml(advice.verdict || "keep")}">${escapeHtml(advice.reason || "")}</p>
    <p>改这份表？ <b>${advice.edit ? "要" : "不要"}</b>
      ${tms.exists ? ` · TMS 分文件 ${escapeHtml(String(mapping.tmsSkillId || mapping.skillId))}.img ${(tms.size / 1024).toFixed(0)} KB` : " · 无对应 TMS _Canvas 文件"}</p>
    <ul>${(mapping.files || []).map((item) => `<li>${escapeHtml(item.role)} · <code>${escapeHtml(item.path)}</code></li>`).join("")}</ul>
    ${openId ? `<p><button type="button" class="open-mob-skill-btn" data-skill-id="${openId}" data-level="${openLv}">打开 MobSkill ${openId}/${openLv}</button></p>` : ""}
  </div>`;
}

function renderServerControlHelp(row) {
  const panel = $("serverControlHelp");
  if (!panel) return;
  const paint = (help) => {
    const templates = help?.templates || [];
    const steps = help?.howToStart || [];
    const related = help?.related || [];
    const slots = (help?.slots || []).map((slot) =>
      `<li>槽 ${escapeHtml(String(slot.index))} → skill ${escapeHtml(String(slot.skill ?? "—"))} / action ${escapeHtml(String(slot.action ?? "—"))}</li>`
    ).join("");
    panel.className = "server-control-help";
    panel.innerHTML = `
      <div class="side-label">怎么入手</div>
      <ol class="server-control-steps">${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
      <div class="side-label">MobSkill 是什么、何时改</div>
      <p>${escapeHtml(help?.mobSkillGuide?.whatItDoes || "")}</p>
      <p><b>要改时</b></p>
      <ul>${(help?.mobSkillGuide?.whenToEdit || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ul>
      <p><b>不要改时</b></p>
      <ul>${(help?.mobSkillGuide?.whenNotToEdit || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ul>
      ${mobSkillCardMarkup(help?.mobSkill)}
      <div class="side-label">可复用模板</div>
      <div class="server-control-templates">${templates.map((item) => `
        <article>
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.summary)}</p>
          <pre>${escapeHtml(item.start)}</pre>
        </article>`).join("")}</div>
      ${help ? `<div class="side-label">当前节点 ${escapeHtml(help.path || "")}</div>
        <p><b>${escapeHtml(help.template?.title || "")}</b></p>
        <p>${escapeHtml(help.playback || "")}</p>
        ${(help.timeline || []).length ? `<ol class="playback-timeline">${help.timeline.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>` : ""}
        <p>${escapeHtml(help.javaHint || "")}</p>
        ${slots ? `<ul>${slots}</ul>` : ""}
        <div class="side-label">相关资源</div>
        <ul>${related.map((item) => `<li>${escapeHtml(item.kind)} ${escapeHtml(item.name)} · <code>${escapeHtml(item.path)}</code></li>`).join("")}</ul>
        ${help.template?.start ? `<pre>${escapeHtml(help.template.start)}</pre>` : ""}` : ""}
    `;
    bindMobSkillOpenButtons(panel);
  };
  if (row?.serverControl) {
    paint(row.serverControl);
    return;
  }
  const mobId = (String(state.leftPath).match(/(\d{7})\.img/) || [])[1] || "";
  get(`/api/server-control-help?path=${encodeURIComponent(row?.path || "skill2")}&mobId=${encodeURIComponent(mobId)}`)
    .then(paint)
    .catch((error) => {
      panel.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
    });
}

async function loadChildFrames(path, childCount) {
  const section = $("childFramesSection");
  const content = $("childFramesContent");
  if (!section || !content) return;
  section.style.display = "";
  try {
    const leftData = await post("/api/child-frames", {sourcePath: state.leftPath, path});
    const rightData = state.rightPath ? await post("/api/child-frames", {sourcePath: state.rightPath, path}).catch(() => null) : null;
    renderChildFrames(leftData, rightData, path);
  } catch (error) {
    content.innerHTML = `<span class="compat-empty">加载失败: ${escapeHtml(error.message)}</span>`;
  }
}

const MOB_RESOURCE_OWNER_LABEL = {
  tms: "TMS 只读", ms: "MS 包", client: "项目客户端", server: "项目服务端",
};

async function loadMobResourceManifest(sourcePath) {
  const box = $("mobResourceContent");
  if (!box || state.kind !== "mob") return;
  const sequence = ++state.mobManifestSequence;
  box.innerHTML = '<span class="compat-empty">正在解析 TMS 真实资源…</span>';
  try {
    const data = await post("/api/mob-resource-manifest", {sourcePath});
    if (sequence !== state.mobManifestSequence || !$("mobResourceContent")) return;
    renderMobResourceManifest(data);
  } catch (error) {
    if (sequence === state.mobManifestSequence && $("mobResourceContent")) {
      $("mobResourceContent").innerHTML = `<span class="compat-empty">真实资源清单不可用: ${escapeHtml(error.message)}</span>`;
    }
  }
}

function renderMobResourceManifest(data) {
  const box = $("mobResourceContent");
  if (!box) return;
  const counts = data.stateCounts || {};
  const files = data.realFiles || [];
  const realCount = counts.real || 0;
  const linkedCount = counts.linked || 0;
  const orphanCount = counts.orphan || 0;
  const brokenCount = counts.broken || 0;
  const orphanAll = (data.orphanPaths || []).length === data.frameCount && data.frameCount > 0;
  let html = `<div class="manifest-summary">
    <span>共 <b>${data.frameCount}</b> 帧</span>
    <span>真实帧 <b>${realCount}</b></span>
    <span class="linked">占位→真实 <b>${linkedCount}</b></span>
    <span class="orphan">空占位 <b>${orphanCount}</b></span>
    ${brokenCount ? `<span class="orphan">链接失效 <b>${brokenCount}</b></span>` : ""}
    <span class="manifest-source" title="${escapeHtml(data.sourceLabel)}">源：${escapeHtml(data.sourceLabel)}</span>
  </div>`;
  if (orphanAll) {
    html += `<p class="manifest-note">该文件所有帧都是空占位：TMS 侧没有可复制的像素。请改用本怪物其它动作，或换用带真实资源的来源文件。</p>`;
  }
  if (files.length) {
    html += `<table class="manifest-table"><thead><tr>
      <th>真实资源文件</th><th>帧数</th><th>动作</th><th></th>
    </tr></thead><tbody>`;
    for (const file of files) {
      const actions = (file.actions || []);
      // 用后端解析出的首个真实节点路径做跳转目标；actions[0]/0 只是兜底，
      // 因为目标文件里该动作未必存在 0 号帧。
      const firstPath = (file.framePaths || [])[0] || (actions[0] ? `${actions[0]}/0` : "");
      const chips = [
        file.crossMob ? '<span class="real-chip cross">跨怪引用</span>' : "",
        file.isCanvasStore ? '<span class="real-chip">Mob/_Canvas</span>' : "",
        `<span class="real-chip owner-${escapeHtml(file.owner)}">${escapeHtml(MOB_RESOURCE_OWNER_LABEL[file.owner] || file.owner)}</span>`,
      ].join("");
      html += `<tr>
        <td class="manifest-file">
          <code class="real-path" title="${escapeHtml(file.absPath)}">${escapeHtml(file.label)}</code>
          ${chips}
        </td>
        <td>${file.frameCount}</td>
        <td class="real-actions" title="${escapeHtml(actions.join(", "))}">${escapeHtml(actions.slice(0, 8).join(", "))}${actions.length > 8 ? ` …(+${actions.length - 8})` : ""}</td>
        <td><button class="real-open-btn" type="button"
          data-real-file="${escapeHtml(file.file)}"
          data-real-path="${escapeHtml(firstPath)}"
          data-real-label="${escapeHtml(file.label)}">在 B 侧查看</button></td>
      </tr>`;
    }
    html += `</tbody></table>`;
  }
  if (data.orphanPaths?.length) {
    html += `<p class="manifest-note">空占位帧（TMS 里确实没有可见像素）：<code>${escapeHtml(data.orphanPaths.slice(0, 24).join(", "))}</code>${data.orphanPaths.length > 24 ? ` …(+${data.orphanPaths.length - 24})` : ""}</p>`;
  }
  if (data.brokenPaths?.length) {
    html += `<p class="manifest-note">链接无法解析的帧：${data.brokenPaths.slice(0, 8).map((item) => `<code>${escapeHtml(item.path)}</code> ${escapeHtml(item.error)}`).join("；")}</p>`;
  }
  html += `<p class="manifest-note">提示：复制单帧只会改动指定帧的记录；若该帧所属动作在 A 侧不存在，请用「迁移该动作到 A」一次带入全部真实帧。</p>`;
  box.innerHTML = html;
  box.querySelectorAll(".real-open-btn").forEach((button) => button.addEventListener("click", () => {
    openRealResource({
      file: button.dataset.realFile,
      path: button.dataset.realPath,
      fileLabel: button.dataset.realLabel,
    });
  }));
}

const MOB_FIELD_MEANINGS = {
  level: "怪物等级", maxHP: "最大HP", maxMP: "最大MP", mpRecovery: "MP恢复速度",
  speed: "移动速度（负值=向左）", PADamage: "物理攻击力", MADamage: "魔法攻击力",
  exp: "经验值", acc: "命中率", eva: "回避率", push: "击退力",
  HPRecovery: "HP恢复速度", boss: "是否Boss（1=是）",
  undead: "是否不死族", friendly: "是否友好怪物",
  bodyAttack: "是否接触伤害", elemAttr: "元素属性",
  attack: "攻击力", defense: "防御力",
  attackAfter: "攻击后硬直(ms)", onlyFsm: "TMS仅FSM；旧端投影为stand UOL",
  range: "攻击范围", hit: "命中判定", lt: "判定框左上", rb: "判定框右下",
  mobCount: "召唤数量", mob: "召唤怪物ID", type: "攻击类型",
  delay: "帧延迟(ms)", origin: "锚点坐标",
  affect: "是否影响角色", spell: "魔法攻击", fatal: "致死攻击",
  buff: "附加Buff", area: "攻击区域", knockback: "击退距离",
  mpConsume: "MP消耗", cooltime: "冷却时间(ms)",
};
function _mobFieldMeaning(name) {
  return MOB_FIELD_MEANINGS[name] || "";
}

// ── TMS 真实资源展示 ────────────────────────────────────────────────
// TMS 怪物记录里的帧常常声明成 1×1，真实像素在 Mob/_Canvas/<怪ID>.img，且可能跨怪。
// 后端已经把每一帧解析成 {state, resolved:{fileLabel,path,width,height,...}}，这里只负责展示与跳转。
const MOB_FRAME_STATE_LABEL = {
  real: "",
  linked: "占位→真实",
  orphan: "空占位",
  broken: "链接失效",
  missing: "无节点",
};

function mobFrameStateBadge(child) {
  return MOB_FRAME_STATE_LABEL[child?.state] || "";
}

function mobFrameSizeText(child) {
  const real = child?.resolved;
  const declared = child?.declaredWidth != null && child?.declaredHeight != null
    ? `${child.declaredWidth}×${child.declaredHeight}` : null;
  if (real) {
    const realText = `${real.width}×${real.height}`;
    return child.state === "linked" ? `${declared || "占位"} → ${realText}` : realText;
  }
  return declared || "—";
}

function mobFrameResourceText(child) {
  const real = child?.resolved;
  if (!real) return child?.error ? `无真实资源（${child.error}）` : "无真实资源";
  const cross = child.crossMob ? "（跨怪引用）" : "";
  return `${real.fileLabel}/${real.path}${cross}`;
}

async function openRealResource(resolved) {
  if (!resolved?.file) return;
  $("rightPath").value = resolved.file;
  state.mobSourceOptions = null;
  await loadComparison();
  if (state.rowByPath.has(resolved.path)) {
    selectNode(resolved.path);
    revealNode(resolved.path);
  }
  setStatus(`B 侧已切换到真实资源 ${resolved.fileLabel}/${resolved.path}`);
}

function renderChildFrames(leftData, rightData, parentPath) {
  const content = $("childFramesContent");
  if (!leftData?.ok) {
    content.innerHTML = '<span class="compat-empty">无子节点数据</span>';
    return;
  }
  const leftChildren = leftData.children || [];
  const rightChildren = rightData?.children || [];
  const rightMap = new Map(rightChildren.map((c) => [c.name, c]));
  const placeholderCount = leftChildren.filter((c) => c.isPlaceholder).length;
  const linkedCount = leftChildren.filter((c) => c.state === "linked").length;
  const orphanCount = leftChildren.filter((c) => c.state === "orphan").length;
  let html = "";
  const playback = leftData.playback?.length ? leftData.playback : rightData?.playback;
  if (playback?.length) {
    html += `<div class="child-note"><strong>TMS 播放时间轴</strong><ol>${playback.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol></div>`;
  }
  // 说明占位帧的真实出处
  if (placeholderCount) {
    html += `<div class="child-note">
      <strong>⚠️ 包含 ${placeholderCount} 个占位帧 (≤4×4)</strong>
      <p>1×1 或极小的 Canvas 只是<strong>声明尺寸</strong>：真实像素在别的文件里。本工具已解析每一帧的出处，
      占位帧不会再“什么都不知道”。</p>
      <p><b>${linkedCount}</b> 个占位帧能解析到真实资源（
      <span class="real-chip">占位→真实</span> 可点击跳转）；<b>${orphanCount}</b> 个是
      <span class="real-chip orphan">空占位</span>，TMS 里该帧确实没有可见像素。</p>
    </div>`;
  }
  // Frame grid with thumbnails
  const numericChildren = leftChildren.filter((c) => /^\d+$/.test(c.name));
  const nonNumeric = leftChildren.filter((c) => !/^\d+$/.test(c.name));
  if (numericChildren.length > 0) {
    html += `<div class="frame-grid">`;
    for (const child of numericChildren) {
      const right = rightMap.get(child.name);
      const isPlaceholder = child.isPlaceholder;
      const rightPlaceholder = right?.isPlaceholder;
      const leftUrl = child.url ? apiUrl(child.url) : "";
      const rightUrl = right?.url ? apiUrl(right.url) : "";
      const badge = mobFrameStateBadge(child) || mobFrameStateBadge(right)
        || (isPlaceholder && rightPlaceholder ? "占位"
          : isPlaceholder ? "A占位"
          : rightPlaceholder ? "B占位"
          : !right ? "仅A"
          : child.width !== right.width || child.height !== right.height ? "尺寸异" : "");
      const blankFrame = child.state === "orphan" || child.state === "broken";
      const badgeKind = child.state || right?.state || "";
      html += `<div class="frame-card${isPlaceholder ? ' placeholder' : ''}${blankFrame ? ' blank' : ''}" data-frame-name="${escapeHtml(child.name)}" data-parent="${escapeHtml(parentPath)}">
        <div class="frame-card-thumbs">
          ${leftUrl ? `<div class="frame-thumb-wrap a"><img class="frame-thumb" src="${leftUrl}" alt="A" loading="lazy" onerror="this.style.display='none'"><span class="frame-thumb-label">A</span></div>` : `<div class="frame-thumb-wrap a"><span class="frame-thumb-empty">无</span></div>`}
          ${rightUrl ? `<div class="frame-thumb-wrap b"><img class="frame-thumb" src="${rightUrl}" alt="B" loading="lazy" onerror="this.style.display='none'"><span class="frame-thumb-label">B</span></div>` : `<div class="frame-thumb-wrap b"><span class="frame-thumb-empty">${right ? '无' : '—'}</span></div>`}
        </div>
        <div class="frame-card-info">
          <span class="frame-card-name">${escapeHtml(child.name)}</span>
          ${badge ? `<span class="frame-card-badge${badgeKind ? ` state-${escapeHtml(badgeKind)}` : ""}">${escapeHtml(badge)}</span>` : ""}
        </div>
        <div class="frame-card-meta">
          ${child.type === "canvas" || child.type === "uol" ? mobFrameSizeText(child) : child.type}
          ${child.delay != null ? ` · ${child.delay}ms` : ""}
          ${child.origin ? ` · (${child.origin.x},${child.origin.y})` : ""}
        </div>
        <div class="frame-card-real ${child.state === "real" ? "muted" : ""}${child.resolved ? " clickable" : ""}" title="${escapeHtml(mobFrameResourceText(child))}"${child.resolved ? ` data-real-file="${escapeHtml(child.resolved.file)}" data-real-path="${escapeHtml(child.resolved.path)}" data-real-label="${escapeHtml(child.resolved.fileLabel)}"` : ""}>${escapeHtml(mobFrameResourceText(child))}</div>
      </div>`;
    }
    html += `</div>`;
  }
  // Non-numeric children with meanings
  if (nonNumeric.length > 0) {
    html += `<div class="child-note"><strong>非帧子节点 (${nonNumeric.length})</strong>`;
    for (const c of nonNumeric) {
      const meaning = c.meaning || "";
      const valueStr = c.value != null ? ` = ${escapeHtml(String(c.value))}` : "";
      const childStr = c.childCount != null ? ` (${c.childCount} 个子属性)` : "";
      html += `<div class="child-node-row">
        <code>${escapeHtml(c.name)}</code>
        <span class="child-node-type">${escapeHtml(c.type)}</span>
        ${valueStr ? `<span class="child-node-value">${valueStr}</span>` : ""}
        ${meaning ? `<span class="child-node-meaning">${escapeHtml(meaning)}</span>` : ""}
      </div>`;
      // Show info sub-fields
      if (c.subFields?.length) {
        html += `<div class="child-sub-fields">`;
        for (const sub of c.subFields) {
          const subMeaning = _mobFieldMeaning(sub.name);
          html += `<span class="child-sub-field"><code>${escapeHtml(sub.name)}</code>${sub.value != null ? `=${escapeHtml(String(sub.value))}` : ""}${subMeaning ? ` <em>${escapeHtml(subMeaning)}</em>` : ""}</span>`;
        }
        html += `</div>`;
      }
    }
    html += "</div>";
  }
  content.innerHTML = html;
  // Click frame card to open comparison modal
  content.querySelectorAll(".frame-card").forEach((card) => card.addEventListener("click", () => {
    openFrameCompareModal(card.dataset.parent, card.dataset.frameName, leftChildren, rightMap);
  }));
  // 点击“真实资源”行：把 B 侧直接切到真实文件并选中对应节点
  content.querySelectorAll(".frame-card-real[data-real-file]").forEach((line) => line.addEventListener("click", (event) => {
    event.stopPropagation();
    openRealResource({
      file: line.dataset.realFile,
      path: line.dataset.realPath,
      fileLabel: line.dataset.realLabel,
    });
  }));
}

async function writeMobFrame(options) {
  const {
    sourcePath, targetPath, sourceFramePath, actionName, frameIndex,
  } = options;
  return post("/api/copy-mob-frame", {
    sourcePath, targetPath, sourceFramePath, actionName, frameIndex,
  });
}

async function copyFrameBetweenSides(fromSide, parentPath, frameName, button) {
  const fromPath = fromSide === "right" ? state.rightPath : state.leftPath;
  const toPath = fromSide === "right" ? state.leftPath : state.rightPath;
  const fromLabel = fromSide === "right" ? "B" : "A";
  const toLabel = fromSide === "right" ? "A" : "B";
  button.disabled = true;
  button.textContent = "…";
  try {
    const data = await writeMobFrame({
      sourcePath: fromPath,
      targetPath: toPath,
      sourceFramePath: `${parentPath}/${frameName}`,
      actionName: parentPath,
      frameIndex: parseInt(frameName, 10),
    });
    if (!data.ok) throw new Error(data.error || "复制失败");
    button.textContent = "✓ 完成";
    button.disabled = false;
    setStatus(`${fromLabel}→${toLabel} 已完成：${data.sourceSummary}`);
    // Reload comparison to reflect changes
    await loadComparison({backgroundPreview: true});
  } catch (error) {
    alert(`复制失败: ${error.message}`);
    button.textContent = `${fromLabel}→${toLabel}`;
    button.disabled = false;
  }
}

function frameCompareSideMarkup(child, sideClass, sideLabel, missingText) {
  if (!child) return `<div class="frame-compare-empty">${escapeHtml(missingText)}</div>`;
  const url = child.url ? apiUrl(child.url) : "";
  const isImage = ["canvas", "uol"].includes(child.type) && url;
  const detail = ["canvas", "uol"].includes(child.type)
    ? `${mobFrameSizeText(child)} · delay=${child.delay ?? "—"}ms${child.origin ? ` · origin=(${child.origin.x},${child.origin.y})` : ""}`
    : `${child.type}${child.value != null ? " → " + child.value : ""}`;
  let real = "";
  if (child.state === "linked" && child.resolved) {
    real = `<div class="frame-compare-real linked" title="${escapeHtml(mobFrameResourceText(child))}">真实资源：<b>${child.resolved.width}×${child.resolved.height}</b> ← <code>${escapeHtml(child.resolved.fileLabel)}/${escapeHtml(child.resolved.path)}</code>${child.crossMob ? '<span class="real-chip cross">跨怪</span>' : ""}</div>`;
  } else if (child.state === "orphan") {
    real = `<div class="frame-compare-real orphan">空占位：TMS 里这一帧没有可见像素</div>`;
  } else if (child.state === "broken") {
    real = `<div class="frame-compare-real orphan">真实资源解析失败：${escapeHtml(child.error || "未知原因")}</div>`;
  }
  return `
    ${isImage
      ? `<img src="${url}" alt="${escapeHtml(sideLabel)}">`
      : `<div class="frame-compare-empty">${child.type === "uol" ? "链接不可解析" : "无图片"}</div>`}
    <div class="frame-compare-detail">${escapeHtml(detail)}</div>
    ${real}`;
}

function openFrameCompareModal(parentPath, frameName, leftChildren, rightMap) {
  const leftChild = leftChildren.find((c) => c.name === frameName);
  const rightChild = rightMap.get(frameName);
  if (!leftChild) return;
  // Remove existing modal
  document.querySelectorAll(".frame-compare-modal").forEach((m) => m.remove());
  const hasLeft = ["canvas", "uol"].includes(leftChild.type) && Boolean(leftChild.url);
  const hasRight = ["canvas", "uol"].includes(rightChild?.type) && Boolean(rightChild?.url);
  const isDifferent = hasLeft && hasRight && (leftChild.width !== rightChild.width || leftChild.height !== rightChild.height || leftChild.delay !== rightChild.delay);
  const modal = document.createElement("div");
  modal.className = "frame-compare-modal";
  modal.innerHTML = `
    <div class="frame-compare-inner">
      <div class="frame-compare-header">
        <h3>${escapeHtml(parentPath)} / ${escapeHtml(frameName)}</h3>
        <div class="frame-compare-actions">
          ${hasRight ? `<button class="frame-copy-btn" id="copyBtoA" type="button" title="将 B 侧此帧的真实像素复制替换到 A">◀◆ B→A</button>` : ""}
          ${hasLeft ? `<button class="frame-copy-btn" id="copyAtoB" type="button" title="将 A 侧此帧复制替换到 B">A→B ◆▶</button>` : ""}
          <button class="frame-compare-close" type="button">×</button>
        </div>
      </div>
      ${isDifferent ? '<div class="frame-compare-diff-hint">⚠️ 两侧帧不同</div>' : ""}
      <div class="frame-compare-body">
        <div class="frame-compare-side a">
          <div class="frame-compare-label"><span class="column-badge a">A</span> 主文件</div>
          ${frameCompareSideMarkup(leftChild, "a", "A", "无图片")}
        </div>
        <div class="frame-compare-side b">
          <div class="frame-compare-label"><span class="column-badge b">B</span> 对比</div>
          ${frameCompareSideMarkup(rightChild, "b", "B", "B 侧无此节点")}
        </div>
      </div>
      <div class="frame-compare-nav">
        <button class="icon-button small" id="frameCmpPrev" type="button">◀</button>
        <span id="frameCmpLabel">${escapeHtml(frameName)}</span>
        <button class="icon-button small" id="frameCmpNext" type="button">▶</button>
      </div>
    </div>`;
  document.body.appendChild(modal);
  // Close
  modal.querySelector(".frame-compare-close").addEventListener("click", () => modal.remove());
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
  // Copy frame handlers
  const copyBtoA = modal.querySelector("#copyBtoA");
  const copyAtoB = modal.querySelector("#copyAtoB");
  if (copyBtoA) copyBtoA.addEventListener("click", async () => {
    await copyFrameBetweenSides("right", parentPath, frameName, copyBtoA);
  });
  if (copyAtoB) copyAtoB.addEventListener("click", async () => {
    await copyFrameBetweenSides("left", parentPath, frameName, copyAtoB);
  });
  // Navigate
  const numericNames = leftChildren.filter((c) => /^\d+$/.test(c.name)).map((c) => c.name);
  let currentIdx = numericNames.indexOf(frameName);
  function navigate(delta) {
    currentIdx = (currentIdx + delta + numericNames.length) % numericNames.length;
    modal.remove();
    openFrameCompareModal(parentPath, numericNames[currentIdx], leftChildren, rightMap);
  }
  modal.querySelector("#frameCmpPrev").addEventListener("click", () => navigate(-1));
  modal.querySelector("#frameCmpNext").addEventListener("click", () => navigate(1));
  document.addEventListener("keydown", function handler(e) {
    if (e.key === "Escape") { modal.remove(); document.removeEventListener("keydown", handler); }
    if (e.key === "ArrowLeft") { e.preventDefault(); navigate(-1); }
    if (e.key === "ArrowRight") { e.preventDefault(); navigate(1); }
  });
}

function editorMarkup(meta) {
  if (!meta?.editable) return `<p class="editor-note">该节点没有可直接编辑的值。可使用上方“添加子节点”或“删除节点”；二进制 IMG 会按原始记录增量修改并校验未触碰的兄弟记录。</p>`;
  let control = "";
  if (meta.type === "vector") {
    control = `<div class="vector-editor"><input id="editX" type="number" value="${escapeHtml(meta.value?.x ?? 0)}" aria-label="X"><input id="editY" type="number" value="${escapeHtml(meta.value?.y ?? 0)}" aria-label="Y"></div>`;
  } else if (meta.type === "canvas") {
    control = `<div class="vector-editor"><input id="editWidth" type="number" min="0" value="${escapeHtml(meta.width ?? 0)}" aria-label="宽度"><input id="editHeight" type="number" min="0" value="${escapeHtml(meta.height ?? 0)}" aria-label="高度"></div>`;
  } else if (["string", "uol"].includes(meta.type)) {
    control = `<textarea id="editValue" spellcheck="false">${escapeHtml(meta.value ?? "")}</textarea>`;
  } else {
    control = `<input id="editValue" type="number" step="${["float", "double"].includes(meta.type) ? "any" : "1"}" value="${escapeHtml(meta.value ?? 0)}">`;
  }
  const note = state.leftInfo?.format === "img"
    ? `IMG 安全模式：优先原位写入；编码长度变化时只替换当前属性记录，并校验其他兄弟记录不变${meta.byteLength !== undefined ? `（当前字符串槽位 ${meta.byteLength} 字节）` : ""}。`
    : "XML 写入只替换当前节点标签，不重排其他节点。";
  return `<div class="side-label">编辑主文件</div><div class="value-editor">${control}<span class="editor-note">${escapeHtml(note)}</span></div>`;
}

function currentEditValue(meta) {
  if (meta.type === "vector") return {x: Number($("editX").value), y: Number($("editY").value)};
  if (meta.type === "canvas") return {width: Number($("editWidth").value), height: Number($("editHeight").value)};
  const raw = $("editValue").value;
  return ["int", "short", "long"].includes(meta.type) ? Number.parseInt(raw, 10) : ["float", "double"].includes(meta.type) ? Number.parseFloat(raw) : raw;
}

async function saveEdit() {
  const row = state.rowByPath.get(state.selectedPath);
  if (!row?.left) return;
  const editedPath = state.selectedPath;
  try {
    const syncServer = $("syncServer").checked;
    const data = await post("/api/edit", {sourcePath: state.leftPath, path: state.selectedPath, value: currentEditValue(row.left), dryRun: false, backup: true, syncServer});
    const targetText = syncServer ? "客户端与服务端" : "客户端";
    const resultText = `${targetText}写入完成，已重新加载左侧节点\n${JSON.stringify(data, null, 2)}`;
    await loadComparison({backgroundPreview: true});
    revealNode(editedPath);
    showResult(resultText);
  } catch (error) {
    showResult(error.message, true);
  }
}

async function deleteNode() {
  if (!state.selectedPath) return;
  const deletedPath = state.selectedPath;
  const parentPath = deletedPath.includes("/") ? deletedPath.slice(0, deletedPath.lastIndexOf("/")) : "";
  try {
    const syncServer = $("syncServer").checked;
    const data = await post("/api/delete", {sourcePath: state.leftPath, path: deletedPath, dryRun: false, backup: true, syncServer});
    const targetText = syncServer ? "客户端与服务端" : "客户端";
    const resultText = `${targetText}删除完成，左侧节点已重新加载\n${JSON.stringify(data, null, 2)}`;
    await refreshTreeAfterDelete(parentPath);
    revealNode(parentPath);
    showResult(resultText);
  } catch (error) {
    showResult(error.message, true);
  }
}

async function createMainFile() {
  try {
    const data = await post("/api/create-main", {sourcePath: state.leftPath});
    const resultText = `空白主文件创建完成，可从 TMS 逐个复制兼容节点。\n${JSON.stringify(data, null, 2)}`;
    await loadComparison({backgroundPreview: true});
    showResult(resultText);
  } catch (error) {
    showResult(error.message, true);
  }
}

async function copyTmsNode() {
  const path = state.selectedPath;
  if (path === null) return;
  const button = $("copyTmsBtn");
  const operationLabel = button.textContent.startsWith("补齐") ? "正在补齐引用资源…" : "正在复制节点…";
  button.disabled = true;
  button.textContent = operationLabel;
  showResult(`${operationLabel}\n请稍候，完成后会自动刷新对比结果。`);
  try {
    const data = await post("/api/copy-tms-node", {
      sourcePath: state.leftPath,
      tmsPath: state.rightPath,
      path,
    });
    for (const file of data.modifiedFiles || data.resources?.files || []) state.exportFiles.add(file);
    const skipped = data.skippedPaths?.length ? `\n已自动略过 ${data.skippedPaths.length} 个现代或不兼容节点。` : "";
    const migratedResources = data.resources?.migrated?.length
      ? `\n已同步迁移 ${data.resources.migrated.map((item) => `${item.kind.toUpperCase()} ${item.id}`).join("、")} 引用资源。`
      : "";
    const unresolvedResources = data.resources?.unresolved?.length
      ? `\n仍有 ${data.resources.unresolved.length} 个资源不能自动覆盖，请查看结果中的 unresolved 原因。`
      : "";
    const recordedFiles = data.modifiedFiles?.length
      ? `\n已记录本次修改的 ${data.modifiedFiles.length} 个文件，复制到下载目录时会一并导出。`
      : "";
    const operation = data.resourceOnly
      ? "地图节点保持不变，引用资源已执行补齐。"
      : "TMS 节点已按原路径复制到 A，并同步服务端 XML。";
    const canvasNote = data.materialized?.canvases
      ? `\n已把 ${data.materialized.canvases} 个 Canvas 投影为 GMS ARGB4444。`
      : "";
    const densifyNote = data.densifiedFrames
      ? `\n已连续化 ${data.densifiedFrames} 个子目录数字帧（如 areaWarning）。动作根帧号保持 TMS 原序号。`
      : "";
    const uolNote = data.uolsKept
      ? `\n已保留 ${data.uolsKept} 个 TMS 真实 UOL（目标在 A 中存在）。`
      : "";
    const resultText = `${operation}${skipped}${canvasNote}${densifyNote}${uolNote}${migratedResources}${unresolvedResources}${recordedFiles}\n${JSON.stringify(data, null, 2)}`;
    showResult(resultText);
    await refreshComparisonAfterCopy(path, {backgroundPreview: true});
  } catch (error) {
    showResult(error.message, true);
  } finally {
    updateNodeActions();
  }
}

async function migrateMobAction() {
  const actionName = state.mobActionName;
  const source = activeMobComparisonSource();
  if (!actionName || !source) return;

  const button = _mobEl("migrateBtn");
  button.disabled = true;
  button.textContent = "…";
  showResult(`正在兼容迁移 ${actionName}…\n将验证原始记录范围、Canvas 格式和可见像素。`);
  try {
    const data = await post("/api/migrate-mob-action", {
      sourcePath: state.leftPath,
      tmsPath: state.rightPath,
      action: actionName,
    });
    for (const file of data.modifiedFiles || []) state.exportFiles.add(file);
    await loadComparison({backgroundPreview: true});
    if (Array.from($("actionSelect").options).some((option) => option.value === actionName)) {
      state.mobActionName = actionName;
      state.mobElapsed = 0;
      $("actionSelect").value = actionName;
      showMobFrames();
    }
    const resultText = data.changed
      ? `${actionName} 已迁移到 A：客户端 ${data.clientOperation}，服务端 ${data.serverOperation}；`
        + `${data.canvas.visible}/${data.canvas.canvases} 个 Canvas 有可见像素，格式 ${data.canvas.formats.join("、")}；`
        + `${data.rawScope.protectedRecords} 个未授权记录保持不变。`
      : `${actionName} 已是相同的兼容结果，本次没有产生文件变化。`;
    showResult(`${resultText}\n${JSON.stringify(data, null, 2)}`);
  } catch (error) {
    showResult(error.message, true);
  } finally {
    button.textContent = "→ A";
    updateMobActionMigration();
  }
}

function showResult(text, error = false) {
  const result = $("operationResult");
  result.hidden = false;
  result.textContent = text;
  result.style.color = error ? "#ef918a" : "#bad7c9";
}

const fileBrowser = {path: "", parent: null, items: [], selected: null, mode: "file"};

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function renderFileList() {
  const query = $("fileSearch").value.trim().toLowerCase();
  const matches = fileBrowser.items.filter((item) => {
    if (fileBrowser.mode === "directory" && item.type !== "directory") return false;
    return !query || item.name.toLowerCase().includes(query);
  });
  const items = matches.slice(0, 200);
  const list = $("fileList");
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = `<div class="file-list-empty">当前目录没有可选择的${fileBrowser.mode === "directory" ? "子目录" : "文件"}</div>`;
    return;
  }
  for (const item of items) {
    const entry = document.createElement("button");
    entry.type = "button";
    entry.className = `file-entry ${item.type}${fileBrowser.selected?.path === item.path ? " selected" : ""}`;
    entry.setAttribute("role", "option");
    entry.setAttribute("aria-selected", String(fileBrowser.selected?.path === item.path));
    entry.innerHTML = `<span class="file-entry-icon">${item.type === "directory" ? "▸" : "◇"}</span><span class="file-entry-name">${escapeHtml(item.name)}</span><small>${item.type === "file" ? formatFileSize(item.size) : "目录"}</small>`;
    entry.addEventListener("click", () => {
      if (item.type === "directory") {
        browseDirectory(item.path);
        return;
      }
      fileBrowser.selected = item;
      $("selectedFileName").textContent = item.path;
      $("chooseFileBtn").disabled = false;
      renderFileList();
    });
    entry.addEventListener("dblclick", () => {
      if (item.type === "file") chooseFile();
    });
    list.appendChild(entry);
  }
  if (matches.length > items.length) {
    const more = document.createElement("div");
    more.className = "file-list-more";
    more.textContent = `还有 ${matches.length - items.length} 项，请输入名称筛选`;
    list.appendChild(more);
  }
}

async function browseDirectory(path) {
  try {
    const data = await api(`/api/files?path=${encodeURIComponent(path || "")}`);
    fileBrowser.path = data.path;
    fileBrowser.parent = data.parent;
    fileBrowser.items = data.items;
    fileBrowser.selected = null;
    $("fileBrowserPath").textContent = data.path;
    $("fileBrowserPath").title = data.path;
    $("fileUpBtn").disabled = !data.parent;
    $("selectedFileName").textContent = fileBrowser.mode === "directory" ? `当前目录：${data.path}` : "未选择文件";
    $("chooseFileBtn").disabled = fileBrowser.mode !== "directory";
    renderFileList();
  } catch (error) {
    $("fileList").innerHTML = `<div class="file-list-empty">${escapeHtml(error.message)}</div>`;
  }
}

function openFileBrowser() {
  fileBrowser.mode = "file";
  $("fileDialogTitle").textContent = "选择对比文件";
  $("chooseFileBtn").textContent = "选择文件";
  $("fileSearch").value = "";
  $("fileDialog").showModal();
  browseDirectory($("rightPath").value.trim());
}

function chooseFile() {
  if (fileBrowser.mode === "directory") {
    $("exportDestination").value = fileBrowser.path;
    updateExportPreview();
    $("fileDialog").close();
    return;
  }
  if (!fileBrowser.selected) return;
  $("rightPath").value = fileBrowser.selected.path;
  $("fileDialog").close();
}

function updateExportPreview() {
  const destination = $("exportDestination").value.trim() || defaultExportRoot;
  const includeServer = $("exportIncludeServer").checked && !$("exportIncludeServer").disabled;
  const tracked = Array.from(state.exportFiles).filter((path) => includeServer || !path.startsWith("gms-server/"));
  const files = [state.leftPath, ...tracked.filter((path) => path !== state.leftPath)];
  const hasTrackedServer = files.some((path) => path.startsWith("gms-server/"));
  const lines = files.map((path, index) => `${index === files.length - 1 && (!includeServer || hasTrackedServer) ? "└" : "├"}─ ${path}`);
  if (includeServer && !hasTrackedServer) lines.push("└─ 对应服务端 XML（按仓库目录）");
  $("exportStructurePreview").textContent = `${destination}/\n${lines.join("\n")}`;
}

function openExportDialog() {
  $("exportSourcePath").textContent = state.leftPath;
  $("exportSourcePath").title = state.leftPath;
  if (!$("exportDestination").value) $("exportDestination").value = defaultExportRoot;
  const canIncludeServer = state.leftInfo?.format === "img";
  const hasTrackedServer = Array.from(state.exportFiles).some((path) => path.startsWith("gms-server/"));
  $("exportIncludeServer").disabled = !canIncludeServer;
  $("exportIncludeServer").checked = canIncludeServer && ($("syncServer").checked || hasTrackedServer);
  updateExportPreview();
  $("exportDialog").showModal();
}

function openExportDirectoryBrowser() {
  $("exportDialog").close();
  fileBrowser.mode = "directory";
  $("fileDialogTitle").textContent = "选择下载目录";
  $("chooseFileBtn").textContent = "选择当前目录";
  $("fileSearch").value = "";
  $("fileDialog").showModal();
  browseDirectory($("exportDestination").value.trim() || defaultExportRoot);
}

async function exportFiles() {
  const destination = $("exportDestination").value.trim() || defaultExportRoot;
  const includeServer = $("exportIncludeServer").checked && !$("exportIncludeServer").disabled;
  try {
    const data = await post("/api/export", {
      sourcePath: state.leftPath,
      destination,
      includeServer,
      additionalFiles: Array.from(state.exportFiles),
    });
    $("exportDialog").close();
    const files = data.files.map((item) => `${item.target}\nSHA-256 ${item.sha256}`).join("\n\n");
    showResult(`已复制 ${data.files.length} 个文件，并保持原目录结构：\n${files}`);
  } catch (error) {
    showResult(error.message, true);
  }
}

function addNodeValue() {
  const type = $("newNodeType").value;
  if (type === "vector") return {x: Number($("newVectorX").value), y: Number($("newVectorY").value)};
  if (["int", "short", "long"].includes(type)) return Number.parseInt($("newNodeValue").value || "0", 10);
  if (["float", "double"].includes(type)) return Number.parseFloat($("newNodeValue").value || "0");
  return $("newNodeValue").value;
}

function openAddDialog(parentPath) {
  state.addParentPath = parentPath;
  const rootTarget = parentPath === "";
  $("addDialogTitle").textContent = rootTarget ? "添加根节点" : "添加子节点";
  $("addParentPath").textContent = `父节点：${rootTarget ? "/" : parentPath}`;
  $("addParentPath").title = rootTarget ? "/" : parentPath;
  $("newNodeName").value = "";
  $("addDialog").showModal();
  $("newNodeName").focus();
}

async function addNode() {
  const name = $("newNodeName").value.trim();
  const addedPath = `${state.addParentPath}/${name}`.replace(/^\//, "");
  try {
    const syncServer = $("syncServer").checked;
    const data = await post("/api/add", {
      sourcePath: state.leftPath,
      parentPath: state.addParentPath,
      name,
      type: $("newNodeType").value,
      value: addNodeValue(),
      dryRun: false,
      backup: true,
      syncServer,
    });
    $("addDialog").close();
    const targetText = syncServer ? "客户端与服务端" : "客户端";
    const resultText = `${targetText}添加完成，左侧节点已重新加载并定位到 ${addedPath}。\n${JSON.stringify(data, null, 2)}`;
    await loadComparison({backgroundPreview: true});
    revealNode(addedPath);
    showResult(resultText);
  } catch (error) {
    showResult(error.message, true);
    $("addDialog").close();
  }
}

document.querySelectorAll(".segment").forEach((button) => button.addEventListener("click", () => setKind(button.dataset.kind)));
const searchCatalogDebounced = debounce(searchCatalog, 180);
const loadMobSourcesDebounced = debounce((id) => loadMobSources(id, true), 220);
$("itemId")?.addEventListener("input", () => {
  const id = $("itemId").value.trim();
  updateDefaultPaths(id);
  if (state.kind === "mob") loadMobSourcesDebounced(id);
  searchCatalogDebounced();
});
$("itemId")?.addEventListener("focus", searchCatalog);
document.addEventListener("click", (event) => {
  if (!event.target.closest(".id-field")) $("catalog").hidden = true;
});
$("compareBtn")?.addEventListener("click", loadComparison);
$("reloadBtn")?.addEventListener("click", loadComparison);
$("compatibilityTab")?.addEventListener("click", () => setInspectorMode("compatibility"));
$("diagnosticTab")?.addEventListener("click", () => setInspectorMode("diagnostic"));
$("nodeDetailTab")?.addEventListener("click", () => setInspectorMode("node"));
$("openNodeDetailBtn")?.addEventListener("click", () => openNodeDetailDialog());
$("closeNodeDetailBtn")?.addEventListener("click", closeNodeDetailDialog);
$("nodeDetailDialog")?.addEventListener("click", (event) => {
  if (event.target === $("nodeDetailDialog")) closeNodeDetailDialog();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if ($("addDialog")?.open || $("exportDialog")?.open || $("fileDialog")?.open || $("mobSkillDialog")?.open) return;
  if (!$("nodeDetailDialog")?.hidden) closeNodeDetailDialog();
});
$("dialogCopyBtn")?.addEventListener("click", copyTmsNode);
$("dialogAddChildBtn")?.addEventListener("click", () => openAddDialog(state.selectedPath));
$("dialogDeleteBtn")?.addEventListener("click", deleteNode);
$("serverControlTab")?.addEventListener("click", () => setInspectorMode("serverControl"));
$("runDiagnosticBtn")?.addEventListener("click", runCrashDiagnostic);
$("swapBtn")?.addEventListener("click", () => {
  const left = $("leftPath").value;
  $("leftPath").value = $("rightPath").value;
  $("rightPath").value = left;
});
$("browseRightBtn")?.addEventListener("click", openFileBrowser);
$("fileUpBtn")?.addEventListener("click", () => { if (fileBrowser.parent) browseDirectory(fileBrowser.parent); });
$("fileSearch")?.addEventListener("input", renderFileList);
$("chooseFileBtn")?.addEventListener("click", chooseFile);
$("fileDialog")?.addEventListener("close", () => {
  if (fileBrowser.mode !== "directory") return;
  fileBrowser.mode = "file";
  if (!$("exportDialog").open) $("exportDialog").showModal();
});
$("treeSearch")?.addEventListener("input", renderTree);
$("diffOnly")?.addEventListener("change", renderTree);
$("collapseBtn")?.addEventListener("click", () => { state.expanded = new Set([""]); renderTree(); });
$("expandBtn")?.addEventListener("click", () => {
  state.expanded = new Set(state.rows.filter((row) => row.status !== "same").flatMap((row) => {
    const parts = row.path.split("/");
    return parts.map((_, index) => parts.slice(0, index + 1).join("/"));
  }));
  renderTree();
});
$("saveBtn")?.addEventListener("click", saveEdit);
$("createMainBtn")?.addEventListener("click", createMainFile);
$("copyTmsBtn")?.addEventListener("click", copyTmsNode);
$("exportBtn")?.addEventListener("click", openExportDialog);
$("browseExportBtn")?.addEventListener("click", openExportDirectoryBrowser);
$("exportDestination")?.addEventListener("input", updateExportPreview);
$("exportIncludeServer")?.addEventListener("change", updateExportPreview);
$("confirmExportBtn")?.addEventListener("click", exportFiles);
$("deleteBtn")?.addEventListener("click", deleteNode);
$("addRootBtn")?.addEventListener("click", () => openAddDialog(""));
$("addChildBtn")?.addEventListener("click", () => openAddDialog(state.selectedPath));
$("confirmAddBtn")?.addEventListener("click", addNode);
$("newNodeType")?.addEventListener("change", () => {
  const type = $("newNodeType").value;
  $("vectorFields").hidden = type !== "vector";
  $("newValueField").hidden = ["vector", "imgdir", "null"].includes(type);
});
$("showFootholds")?.addEventListener("change", drawMaps);
$("showMobs")?.addEventListener("change", drawMaps);
$("showNpcs")?.addEventListener("change", drawMaps);
$("showPortals")?.addEventListener("change", drawMaps);
$("showWaterAreas")?.addEventListener("change", drawMaps);
$("waterSelectBtn")?.addEventListener("click", () => {
  state.waterSelectMode = !state.waterSelectMode;
  $("waterSelectBtn").classList.toggle("active", state.waterSelectMode);
  $("waterSelectBtn").textContent = state.waterSelectMode ? "拖动框选水域" : "框选游泳区";
  for (const view of Object.values(state.mapViews)) $(view.stageId).classList.toggle("water-selecting", state.waterSelectMode);
});
$("zoomRange")?.addEventListener("input", () => { state.zoom = Number($("zoomRange").value) / 100; applyZoom(); });
$("fitBtn")?.addEventListener("click", fitPreview);
$("actionSelect")?.addEventListener("change", () => {
  state.mobActionName = $("actionSelect").value;
  state.mobElapsed = 0;
  showMobFrames();
  updateMobActionMigration();
});
$("actionSelectInline")?.addEventListener("change", () => {
  state.mobActionName = $("actionSelectInline").value;
  state.mobElapsed = 0;
  showMobFrames();
  updateMobActionMigration();
});
function _togglePlay() {
  state.mobPlaying = !state.mobPlaying;
  for (const btn of [_mobEl("playBtn")].filter(Boolean)) btn.textContent = state.mobPlaying ? "Ⅱ" : "▶";
  showMobFrames();
}
$("playBtn")?.addEventListener("click", _togglePlay);
$("playBtnInline")?.addEventListener("click", _togglePlay);
function _resetMob() {
  state.mobElapsed = 0;
  state.mobPlaying = true;
  for (const btn of [_mobEl("playBtn")].filter(Boolean)) btn.textContent = "Ⅱ";
  showMobFrames();
}
$("resetBtn")?.addEventListener("click", _resetMob);
$("resetBtnInline")?.addEventListener("click", _resetMob);
function _prevFrame() {
  if (state.mobPlaying) { state.mobPlaying = false; for (const btn of [_mobEl("playBtn")].filter(Boolean)) btn.textContent = "▶"; }
  stepMobFrame(-1);
}
function _nextFrame() {
  if (state.mobPlaying) { state.mobPlaying = false; for (const btn of [_mobEl("playBtn")].filter(Boolean)) btn.textContent = "▶"; }
  stepMobFrame(1);
}
$("prevFrameBtn")?.addEventListener("click", _prevFrame);
$("prevFrameBtnInline")?.addEventListener("click", _prevFrame);
$("nextFrameBtn")?.addEventListener("click", _nextFrame);
$("nextFrameBtnInline")?.addEventListener("click", _nextFrame);
$("copyFrameBtoA")?.addEventListener("click", () => copyMobFrame("right"));
$("copyFrameAtoB")?.addEventListener("click", () => copyMobFrame("left"));
$("copyFrameBtoAInline")?.addEventListener("click", () => copyMobFrame("right"));
$("copyFrameAtoBInline")?.addEventListener("click", () => copyMobFrame("left"));
$("migrateMobActionBtn")?.addEventListener("click", migrateMobAction);
$("migrateMobActionBtnInline")?.addEventListener("click", migrateMobAction);
function attachMapStageInteraction(side) {
  const stage = $(state.mapViews[side].stageId);
  let dragStart = null;
  stage.addEventListener("pointerdown", (event) => {
    if (state.kind !== "map" || event.button !== 0) return;
    const point = mapCoordinateAt(side, event.clientX, event.clientY);
    if (!point) return;
    if (state.waterSelectMode) $(state.mapViews[side].selectionId).removeAttribute("data-coordinates");
    dragStart = {x: event.clientX, y: event.clientY, left: stage.scrollLeft, top: stage.scrollTop, moved: false, selecting: state.waterSelectMode, point};
    stage.setPointerCapture(event.pointerId);
    stage.classList.add(state.waterSelectMode ? "water-selecting" : "dragging");
  });
  stage.addEventListener("pointermove", (event) => {
    updateMapCoordinate(side, event);
    if (!dragStart) {
      stage.classList.toggle("clickable", Boolean(mapHitAt(side, event.clientX, event.clientY)));
      return;
    }
    if (Math.hypot(event.clientX - dragStart.x, event.clientY - dragStart.y) > 4) dragStart.moved = true;
    if (dragStart.selecting) {
      positionWaterSelection(side, dragStart, event);
      return;
    }
    stage.scrollLeft = dragStart.left - (event.clientX - dragStart.x);
    stage.scrollTop = dragStart.top - (event.clientY - dragStart.y);
  });
  const stopDragging = (event, allowSelection) => {
    if (!dragStart) return;
    const moved = dragStart.moved;
    const selecting = dragStart.selecting;
    const startPoint = dragStart.point;
    dragStart = null;
    if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
    stage.classList.remove("dragging");
    if (selecting) {
      const endPoint = mapCoordinateAt(side, event.clientX, event.clientY);
      if (allowSelection && moved && endPoint) {
        const area = {
          x1: Math.min(startPoint.x, endPoint.x), y1: Math.min(startPoint.y, endPoint.y),
          x2: Math.max(startPoint.x, endPoint.x), y2: Math.max(startPoint.y, endPoint.y),
        };
        const text = `x1=${area.x1}  y1=${area.y1}  x2=${area.x2}  y2=${area.y2}`;
        const output = $("waterSelectionValue");
        const selection = $(state.mapViews[side].selectionId);
        output.textContent = text;
        output.title = text;
        output.hidden = false;
        selection.dataset.coordinates = text;
        const badge = $(state.mapViews[side].coordinateId);
        badge.textContent = `框选结果\n${text}`;
        badge.hidden = false;
      } else {
        $(state.mapViews[side].selectionId).hidden = true;
      }
      return;
    }
    const hit = allowSelection && !moved ? mapHitAt(side, event.clientX, event.clientY) : null;
    if (hit) revealNode(hit.path);
  };
  stage.addEventListener("pointerup", (event) => stopDragging(event, true));
  stage.addEventListener("pointercancel", (event) => stopDragging(event, false));
  stage.addEventListener("pointerleave", () => {
    $(state.mapViews[side].coordinateId).hidden = true;
    if (!dragStart) stage.classList.remove("clickable");
  });
}
attachMapStageInteraction("left");
attachMapStageInteraction("right");
document.querySelectorAll(".mobile-tabs button").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".mobile-tabs button").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".workspace .panel").forEach((panel) => panel.classList.toggle("mobile-active", panel.id === button.dataset.panel));
  if (button.dataset.panel === "previewPanel" && state.preview) requestAnimationFrame(fitPreview);
}));
window.addEventListener("resize", debounce(() => { if (state.preview) fitPreview(); }, 180));

// ── MCV Boss Skill Catalog ─────────────────────────────────────
let mcvCatalogData = null;

async function loadMcvCatalog() {
  const content = $("mcvCatalogContent");
  content.innerHTML = '<div class="empty-state compact"><strong>加载中…</strong></div>';
  $("mcvCatalogDialog").showModal();
  try {
    const data = await get("/api/mcv-catalog");
    if (!data.ok) throw new Error(data.error || "加载失败");
    mcvCatalogData = data;
    renderMcvCatalog(data);
  } catch (error) {
    content.innerHTML = `<div class="empty-state compact"><strong>加载失败</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

function renderMcvCatalog(data) {
  const content = $("mcvCatalogContent");
  const totalLayers = data.bosses.reduce((sum, b) => sum + b.layers.length, 0);
  const connectedLayers = data.bosses.reduce((sum, b) => sum + b.layers.filter(l => l.mcvFile).length, 0);
  let html = `<div class="mcv-summary">
    <span>共 <strong>${data.bosses.length}</strong> 个 Boss/职业类别</span>
    <span><strong>${totalLayers}</strong> 个视频层</span>
    <span><strong>${connectedLayers}</strong> 个已连接 MCV 文件</span>
    <span><strong>${totalLayers - connectedLayers}</strong> 个未连接</span>
  </div>`;
  for (const boss of data.bosses) {
    const connected = boss.layers.filter(l => l.mcvFile).length;
    html += `<div class="mcv-boss-group">
      <div class="mcv-boss-header">
        <strong>${escapeHtml(boss.label)}</strong>
        <code>${escapeHtml(boss.name)}</code>
        <span class="mcv-count">${connected}/${boss.layers.length} MCV</span>
      </div>
      <div class="mcv-layers">`;
    for (const layer of boss.layers) {
      const statusClass = layer.mcvFile ? "connected" : "disconnected";
      const statusIcon = layer.mcvFile ? "✅" : "❌";
      html += `<div class="mcv-layer-row ${statusClass}">
        <span class="mcv-layer-status">${statusIcon}</span>
        <span class="mcv-layer-name">${escapeHtml(layer.name)}</span>
        <code class="mcv-layer-path">${escapeHtml(layer.path)}</code>`;
      if (layer.mcvFile) {
        html += `<button class="mcv-play-btn" type="button" data-mcv="${escapeHtml(layer.mcvFile)}" data-label="${escapeHtml(boss.label)} - ${escapeHtml(layer.name)}">▶ 预览</button>`;
        html += `<button class="mcv-edit-btn" type="button" data-mcv="${escapeHtml(layer.mcvFile)}">✏️ 编辑</button>`;
      } else {
        html += `<span class="mcv-no-file">无 MCV 文件</span>`;
      }
      html += `</div>`;
    }
    html += `</div></div>`;
  }
  content.innerHTML = html;
  content.querySelectorAll(".mcv-play-btn").forEach((btn) => btn.addEventListener("click", () => {
    playMcvFile(btn.dataset.mcv, btn.dataset.label);
  }));
  content.querySelectorAll(".mcv-edit-btn").forEach((btn) => btn.addEventListener("click", () => {
    openMcvEdit(btn.dataset.mcv);
  }));
}

function playMcvFile(fileName, label) {
  const url = apiUrl(`/api/mcv-file?name=${encodeURIComponent(fileName)}`);
  // Remove any existing mcv modal
  document.querySelectorAll(".video-modal").forEach(m => m.remove());
  const modal = document.createElement("div");
  modal.className = "video-modal";
  modal.innerHTML = `
    <div class="video-modal-content">
      <div class="video-modal-header">
        <h3>🎬 ${escapeHtml(label)}</h3>
        <button class="video-modal-close" type="button">×</button>
      </div>
      <div class="video-modal-body">
          <video controls autoplay loop width="1280" height="720" style="max-width:100%; background:#000;">
            <source src="${url}" type="video/webm">
            浏览器不支持播放此视频格式
          </video>
          <div class="video-info">
            <p>文件: ${escapeHtml(fileName)}</p>
            <p>格式: MCV → WebM (VP9) 转换播放</p>
        </div>
      </div>
    </div>`;
  document.body.appendChild(modal);
  modal.querySelector(".video-modal-close").addEventListener("click", () => modal.remove());
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
}

$("mcvCatalogBtn")?.addEventListener("click", loadMcvCatalog);
$("mcvCatalogClose")?.addEventListener("click", () => $("mcvCatalogDialog").close());
$("mcvEditClose")?.addEventListener("click", () => $("mcvEditDialog").close());

// ── Project Mob Comparison ─────────────────────────────────────
let projectMobSearchTimer = null;

async function loadProjectMobs(query = "") {
  const list = $("projectMobList");
  list.innerHTML = '<div class="empty-state compact"><strong>加载中…</strong></div>';
  $("projectMobDialog").showModal();
  $("projectMobSearch").value = query;
  await searchProjectMobs(query);
}

async function searchProjectMobs(query) {
  const list = $("projectMobList");
  try {
    const data = await get(`/api/project-mobs?q=${encodeURIComponent(query)}`);
    if (!data.ok) throw new Error(data.error);
    renderProjectMobList(data.mobs, query);
  } catch (error) {
    list.innerHTML = `<div class="empty-state compact"><strong>加载失败</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

function renderProjectMobList(mobs, query) {
  const list = $("projectMobList");
  const filtered = mobs;
  const currentId = $("itemId").value.trim();
  if (!filtered.length) {
    list.innerHTML = '<div class="empty-state compact"><span>没有匹配的怪物</span></div>';
    return;
  }
  let html = `<table class="project-mob-table"><thead><tr><th>ID</th><th>名称</th><th>大小</th><th></th></tr></thead><tbody>`;
  for (const mob of filtered) {
    const isCurrent = mob.id === currentId;
    html += `<tr class="${isCurrent ? 'current-mob' : ''}">
      <td class="project-mob-id">${escapeHtml(mob.id)}</td>
      <td class="project-mob-name">${escapeHtml(mob.name || "—")}</td>
      <td class="project-mob-size">${formatBytes(mob.size)}</td>
      <td>${isCurrent ? '<span class="project-mob-current">当前</span>' : `<button class="project-mob-compare-btn" type="button" data-mob-id="${escapeHtml(mob.id)}" data-mob-path="${escapeHtml(mob.path)}">对比</button>`}</td>
    </tr>`;
  }
  html += "</tbody></table>";
  list.innerHTML = html;
  list.querySelectorAll(".project-mob-compare-btn").forEach((btn) => btn.addEventListener("click", () => {
    $("rightPath").value = btn.dataset.mobPath;
    $("projectMobDialog").close();
    loadComparison();
    // Update mob source buttons
    $("mobSourceOptions").querySelectorAll(".mob-source-button").forEach((b) => b.classList.remove("active"));
  }));
}

$("compareProjectMobBtn")?.addEventListener("click", () => loadProjectMobs());
$("projectMobClose")?.addEventListener("click", () => $("projectMobDialog").close());
$("projectMobSearch")?.addEventListener("input", (e) => {
  clearTimeout(projectMobSearchTimer);
  projectMobSearchTimer = setTimeout(() => searchProjectMobs(e.target.value), 200);
});

// ── MCV Edit ─────────────────────────────────────────────────
async function openMcvEdit(mcvFile) {
  $("mcvEditTitle").textContent = `🎬 ${mcvFile}`;
  $("mcvEditSubtitle").textContent = "加载中…";
  $("mcvEditContent").innerHTML = '<div class="empty-state compact"><strong>加载中…</strong></div>';
  $("mcvEditDialog").showModal();
  try {
    const data = await get(`/api/mcv-info?name=${encodeURIComponent(mcvFile)}`);
    if (!data.ok) throw new Error(data.error);
    $("mcvEditSubtitle").textContent = `${data.width}×${data.height} · ${data.frameCount} 帧 · ${data.totalDurationSec}s · ${(data.fileSize/1024).toFixed(1)}KB`;
    renderMcvEditor(data);
  } catch (error) {
    $("mcvEditContent").innerHTML = `<div class="empty-state compact"><strong>加载失败</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

function renderMcvEditor(info) {
  const content = $("mcvEditContent");
  const refs = info.effectRefs || [];
  let html = `<div class="mcv-info-grid">
    <div class="mcv-info-item"><label>视频分辨率</label><span>${info.width}×${info.height}</span></div>
    <div class="mcv-info-item"><label>帧数</label><span>${info.frameCount}</span></div>
    <div class="mcv-info-item"><label>总时长</label><span>${info.totalDurationSec}s</span></div>
    <div class="mcv-info-item"><label>FourCC</label><span>${escapeHtml(info.fourcc)}</span></div>
    <div class="mcv-info-item"><label>文件大小</label><span>${(info.fileSize/1024).toFixed(1)}KB</span></div>
    <div class="mcv-info-item"><label>Marker 尺寸</label><span>${refs.length ? refs[0].markerWidth + '×' + refs[0].markerHeight : '—'}</span></div>
    <div class="mcv-info-item"><label>播放锚点 (origin)</label><span>${refs.length && refs[0].originX != null ? '(' + refs[0].originX + ', ' + refs[0].originY + ')' : '—'}</span></div>
    <div class="mcv-info-item"><label>Effect.img 引用</label><span>${refs.length} 处</span></div>
  </div>`;
  // Show effect references
  if (refs.length) {
    html += `<div class="mcv-effect-refs"><h3>📍 播放坐标定义（Effect.img）</h3>`;
    for (const ref of refs) {
      html += `<div class="mcv-ref-row">
        <code>${escapeHtml(ref.path)}</code>
        <span class="mcv-ref-detail">
          ${ref.markerWidth != null ? `Marker ${ref.markerWidth}×${ref.markerHeight}` : ''}
          ${ref.originX != null ? ` · origin(${ref.originX}, ${ref.originY})` : ''}
          ${ref.markerDelay != null ? ` · delay=${ref.markerDelay}ms` : ''}
        </span>
      </div>`;
    }
    html += `<p class="mcv-ref-note">视频以1280×720全屏渲染，origin 是 marker canvas 的锚点。修改坐标请在节点浏览器中编辑 Effect.img 对应节点的 origin vector。</p></div>`;
  }
  html += `<div class="mcv-actions">
    <button class="primary-button" id="mcvExportFrames" type="button">📦 导出帧序列</button>
    <label class="primary-button mcv-replace-label">🔄 替换视频<input type="file" id="mcvReplaceFile" accept="video/*,.webm,.mp4,.avi,.mov" hidden></label>
    <button class="primary-button" id="mcvSaveDelays" type="button" style="display:none">💾 保存延迟修改</button>
  </div>
  <div class="mcv-preview-area">
    <div class="mcv-preview-nav">
      <button class="icon-button small" id="mcvPrevFrame" type="button">◀</button>
      <span id="mcvFrameLabel" class="mcv-frame-label">1 / ${info.frameCount}</span>
      <button class="icon-button small" id="mcvNextFrame" type="button">▶</button>
      <label class="mcv-delay-edit">延迟 <input id="mcvDelayInput" type="number" min="16" max="10000" value="${info.frames[0]?.delayMs || 60}" style="width:60px"> ms</label>
    </div>
    <div class="mcv-preview-stage">
      <img id="mcvPreviewImg" alt="帧预览" style="max-width:100%; background:#111;">
      <div class="mcv-preview-empty" id="mcvPreviewEmpty">加载中…</div>
    </div>
  </div>
  <h3>帧详情</h3>
  <div class="mcv-frame-table-wrap">
    <table class="mcv-frame-table">
      <thead><tr><th>#</th><th>延迟</th><th>Color</th><th>Alpha</th><th>累积时间</th></tr></thead>
      <tbody>`;
  let cumMs = 0;
  for (const frame of info.frames) {
    cumMs += frame.delayMs;
    html += `<tr data-frame-idx="${frame.index}">
      <td>${frame.index + 1}</td>
      <td class="mcv-delay-cell">${frame.delayMs}ms</td>
      <td>${frame.colorSize > 0 ? (frame.colorSize/1024).toFixed(1) + 'KB' : '-'}</td>
      <td>${frame.alphaSize > 0 ? (frame.alphaSize/1024).toFixed(1) + 'KB' : '-'}</td>
      <td>${(cumMs/1000).toFixed(2)}s</td>
    </tr>`;
  }
  html += `</tbody></table></div>`;
  content.innerHTML = html;

  // State
  let currentFrame = 0;
  let modifiedDelays = info.frames.map((f) => f.delayMs);
  let dirty = false;

  function showFrame(idx) {
    currentFrame = Math.max(0, Math.min(idx, info.frameCount - 1));
    $("mcvFrameLabel").textContent = `${currentFrame + 1} / ${info.frameCount}`;
    $("mcvDelayInput").value = modifiedDelays[currentFrame];
    const img = $("mcvPreviewImg");
    const empty = $("mcvPreviewEmpty");
    img.src = apiUrl(`/api/mcv-frame?name=${encodeURIComponent(info.name)}&frame=${currentFrame}`);
    img.onload = () => { img.style.display = ""; empty.style.display = "none"; };
    img.onerror = () => { img.style.display = "none"; empty.style.display = ""; empty.textContent = "帧加载失败"; };
    // Highlight row in table
    content.querySelectorAll(".mcv-frame-table tr").forEach((tr) => {
      tr.classList.toggle("selected", Number(tr.dataset.frameIdx) === currentFrame);
    });
    // Scroll row into view
    const row = content.querySelector(`tr[data-frame-idx="${currentFrame}"]`);
    if (row) row.scrollIntoView({block: "nearest"});
  }

  $("mcvPrevFrame")?.addEventListener("click", () => showFrame(currentFrame - 1));
  $("mcvNextFrame")?.addEventListener("click", () => showFrame(currentFrame + 1));
  $("mcvDelayInput")?.addEventListener("change", () => {
    const val = Math.max(16, parseInt($("mcvDelayInput").value, 10) || 60);
    modifiedDelays[currentFrame] = val;
    dirty = true;
    $("mcvSaveDelays").style.display = "";
    // Update table cell
    const row = content.querySelector(`tr[data-frame-idx="${currentFrame}"]`);
    if (row) row.querySelector(".mcv-delay-cell").textContent = `${val}ms`;
  });
  // Click row to select frame
  content.querySelectorAll(".mcv-frame-table tr[data-frame-idx]").forEach((tr) => {
    tr.addEventListener("click", () => showFrame(Number(tr.dataset.frameIdx)));
    tr.style.cursor = "pointer";
  });
  // Save delays
  $("mcvSaveDelays")?.addEventListener("click", async () => {
    try {
      const result = await post("/api/mcv-update-delays", {name: info.name, delays: modifiedDelays});
      if (!result.ok) throw new Error(result.error);
      dirty = false;
      $("mcvSaveDelays").style.display = "none";
      $("mcvEditSubtitle").textContent = `${info.width}×${info.height} · ${info.frameCount} 帧 · ${result.totalDurationSec}s`;
      alert("延迟已保存");
    } catch (error) {
      alert(`保存失败: ${error.message}`);
    }
  });
  // Export frames
  $("mcvExportFrames")?.addEventListener("click", () => {
    window.location.href = apiUrl(`/api/mcv-export-frames?name=${encodeURIComponent(info.name)}`);
  });
  // Replace video
  $("mcvReplaceFile")?.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("name", info.name);
    formData.append("file", file);
    try {
      $("mcvEditSubtitle").textContent = "上传并转码中…";
      const response = await fetch(apiUrl("/api/mcv-replace"), {method: "POST", body: formData});
      const result = await response.json();
      if (!result.ok) throw new Error(result.error);
      alert(`替换成功！${result.frameCount} 帧，${(result.totalDurationMs/1000).toFixed(2)}s`);
      openMcvEdit(info.name);
    } catch (error) {
      alert(`替换失败: ${error.message}`);
      $("mcvEditSubtitle").textContent = `${info.width}×${info.height} · ${info.frameCount} 帧`;
    }
  });
  // Keyboard navigation
  const keyHandler = (e) => {
    if (e.key === "ArrowLeft") { e.preventDefault(); showFrame(currentFrame - 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); showFrame(currentFrame + 1); }
  };
  document.addEventListener("keydown", keyHandler);
  $("mcvEditDialog")?.addEventListener("close", () => {
    document.removeEventListener("keydown", keyHandler);
  });
  // Load first frame
  showFrame(0);
}

// ── MobSkill 编辑器 ───────────────────────────────────────────────
// 通过 /img-editor/ API 访问 MobSkill.img，提供技能浏览、特效预览和字段编辑。

// MobSkill 编辑器状态挂在全局 state 上（避免 const TDZ）
state.mobSkills = [];
state.mobSkillSelected = null;
state.mobSkillLevel = 1;

// 跨模块调用 img-editor API（不经过 apiUrl 拼接 apiBase）
async function _msApi(path, body = null) {
  const options = body ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : {};
  const url = path.startsWith("/") ? path : `/img-editor/api/${path}`;
  const response = await fetch(url, options);
  const text = await response.text();
  let payload;
  try { payload = JSON.parse(text); } catch {
    throw new Error(`HTTP ${response.status} ${url}: ${text.slice(0, 120)}`);
  }
  if (!response.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${response.status} ${url}`);
  return payload;
}

function bindMobSkillOpenButtons(root) {
  if (!root) return;
  root.querySelectorAll(".open-mob-skill-btn").forEach((button) => {
    button.addEventListener("click", () => {
      openMobSkillEditor(Number(button.dataset.skillId), Number(button.dataset.level || 1));
    });
  });
}

async function openMobSkillEditor(skillId, level) {
  const dialog = $("mobSkillDialog");
  if (!dialog) return;
  dialog.showModal();
  if (!state.mobSkills.length) {
    $("mobSkillList").innerHTML = '<div class="empty-state compact"><strong>加载中…</strong></div>';
    try {
      const res = await _msApi("/img-editor/api/mob-skills");
      state.mobSkills = res.skills || [];
      _renderMobSkillList(state.mobSkills);
    } catch (e) {
      $("mobSkillList").innerHTML = `<div class="empty-state compact"><strong>加载失败</strong><span>${escapeHtml(e.message)}</span></div>`;
      return;
    }
  }
  if (skillId && state.mobSkills.length) {
    const found = state.mobSkills.find((item) => Number(item.id) === Number(skillId));
    if (found) await _selectMobSkill(found.id, found.name, found.level_count, level);
  }
}

function _renderMobSkillList(skills) {
  const box = $("mobSkillList");
  if (!skills.length) {
    box.innerHTML = '<div class="empty-state compact"><strong>无技能数据</strong></div>';
    return;
  }
  box.innerHTML = skills.map((s) =>
    `<button class="mob-skill-item${state.mobSkillSelected?.id === s.id ? " active" : ""}" data-id="${s.id}" data-name="${escapeHtml(s.name)}" data-levels="${s.level_count}">
      <span>${escapeHtml(s.name)} <small>#${s.id}</small></span>
      <small>${s.level_count} 级</small>
    </button>`
  ).join("");
  box.querySelectorAll(".mob-skill-item").forEach((btn) => btn.addEventListener("click", () => {
    _selectMobSkill(Number(btn.dataset.id), btn.dataset.name, Number(btn.dataset.levels));
  }));
}

async function _selectMobSkill(id, name, levelCount, level) {
  state.mobSkillSelected = { id, name, levelCount };
  const startLevel = Math.min(Math.max(Number(level) || 1, 1), Math.max(1, levelCount));
  state.mobSkillLevel = startLevel;
  // 高亮
  $("mobSkillList").querySelectorAll(".mob-skill-item").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.id) === id);
  });
  // 填充等级选择器
  const sel = $("mobSkillLevel");
  sel.innerHTML = Array.from({ length: levelCount }, (_, i) =>
    `<option value="${i + 1}">${i + 1}</option>`
  ).join("");
  sel.value = String(startLevel);
  $("mobSkillName").textContent = `${name} #${id}`;
  $("mobSkillDetailEmpty").hidden = true;
  $("mobSkillDetail").hidden = false;
  await _loadMobSkillEffect(id, startLevel);
}

async function _loadMobSkillEffect(skillId, level) {
  const effectBox = $("mobSkillEffectFrames");
  const mobBox = $("mobSkillMobFrames");
  const fieldsBox = $("mobSkillFields");
  effectBox.innerHTML = '<span class="compat-empty">加载中…</span>';
  mobBox.innerHTML = "";
  fieldsBox.innerHTML = "";
  try {
    const data = await _msApi(`/img-editor/api/mob-skill-effect?skillId=${skillId}&level=${level}`);
    // Effect 帧
    if (data.effect_frames?.length) {
      effectBox.innerHTML = data.effect_frames.map((f) =>
        `<div class="mob-skill-frame">
          <img src="/img-editor/api/mob-skill-canvas?skillId=${skillId}&level=${level}&frame=${f.name}&kind=effect" alt="effect ${f.name}" loading="lazy" onerror="this.style.display='none'">
          <small>${f.width}×${f.height} · origin(${f.origin?.x || 0},${f.origin?.y || 0}) · ${f.delay}ms</small>
        </div>`
      ).join("");
    } else {
      effectBox.innerHTML = '<span class="compat-empty">无特效帧</span>';
    }
    // Mob 帧
    $("mobSkillMobSection").hidden = !data.mob_frames?.length;
    if (data.mob_frames?.length) {
      mobBox.innerHTML = data.mob_frames.map((f) =>
        `<div class="mob-skill-frame">
          <img src="/img-editor/api/mob-skill-canvas?skillId=${skillId}&level=${level}&frame=${f.name}&kind=mob" alt="mob ${f.name}" loading="lazy" onerror="this.style.display='none'">
          <small>${f.width}×${f.height} · origin(${f.origin?.x || 0},${f.origin?.y || 0})</small>
        </div>`
      ).join("");
    }
    // 参数字段
    $("mobSkillFieldsSection").hidden = !data.fields || !Object.keys(data.fields).length;
    if (data.fields && Object.keys(data.fields).length) {
      fieldsBox.innerHTML = Object.entries(data.fields).map(([key, val]) =>
        `<div class="mob-skill-field">
          <label>${escapeHtml(key)}</label>
          <input type="text" value="${escapeHtml(String(val))}" data-field="${escapeHtml(key)}" data-skill="${skillId}" data-level="${level}">
        </div>`
      ).join("");
      fieldsBox.querySelectorAll("input[data-field]").forEach((input) => {
        input.addEventListener("change", () => _saveMobSkillField(input));
      });
    }
  } catch (e) {
    effectBox.innerHTML = `<span class="compat-empty">加载失败: ${escapeHtml(e.message)}</span>`;
  }
}

async function _saveMobSkillField(input) {
  const field = input.dataset.field;
  const skillId = Number(input.dataset.skill);
  const level = Number(input.dataset.level);
  const value = input.value;
  // 解析数值
  let parsed = value;
  if (/^-?\d+$/.test(value)) parsed = Number(value);
  else if (/^-?\d+\.\d+$/.test(value)) parsed = Number(value);
  try {
    await _msApi("/img-editor/api/mutate", {
      slot: "a",
      operation: "edit",
      path: [String(skillId), "level", String(level), field],
      values: { value: parsed },
    });
    input.style.borderColor = "var(--accent)";
    setTimeout(() => { input.style.borderColor = ""; }, 1500);
  } catch (e) {
    input.style.borderColor = "var(--red)";
    alert(`保存失败: ${e.message}`);
  }
}

// 搜索过滤
function _filterMobSkillList() {
  const q = ($("mobSkillSearch").value || "").toLowerCase();
  const filtered = q
    ? state.mobSkills.filter((s) => s.name.toLowerCase().includes(q) || String(s.id).includes(q))
    : state.mobSkills;
  _renderMobSkillList(filtered);
}

// 事件绑定
console.log("[MobSkill] 绑定事件, btn=", !!$("mobSkillBtn"), "dialog=", !!$("mobSkillDialog"));
$("mobSkillBtn")?.addEventListener("click", openMobSkillEditor);
$("mobSkillClose")?.addEventListener("click", () => $("mobSkillDialog")?.close());
$("mobSkillSearch")?.addEventListener("input", _filterMobSkillList);
$("mobSkillLevel")?.addEventListener("change", () => {
  if (!state.mobSkillSelected) return;
  state.mobSkillLevel = Number($("mobSkillLevel").value);
  _loadMobSkillEffect(state.mobSkillSelected.id, state.mobSkillLevel);
});
$("mobSkillDialog")?.addEventListener("click", (event) => {
  if (event.target === $("mobSkillDialog")) $("mobSkillDialog").close();
});

$("itemId").value = "100000000";
updateDefaultPaths("100000000");
loadComparison();
