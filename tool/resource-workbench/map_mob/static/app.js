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
  $("itemId").placeholder = kind === "map" ? "9 位地图 ID" : "7 位怪物 ID";
  $("diagnosticTab").disabled = kind !== "map";
  $("mobSourceBar").hidden = kind !== "mob";
  clearWorkspace();
  updateDefaultPaths($("itemId").value.trim());
  if (kind === "mob") loadMobSources($("itemId").value.trim(), true);
  searchCatalog();
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
    $("rightPath").value = `gms-server/wz/Mob.wz/${id}.img.xml`;
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
  $("runDiagnosticBtn").addEventListener("click", runCrashDiagnostic);
  $("previewEmpty").hidden = false;
  $("mapCompareView").hidden = true;
  $("mobStage").hidden = true;
  $("leftMobImage").removeAttribute("src");
  $("leftMobImage").hidden = true;
  $("rightMobImage").removeAttribute("src");
  $("rightMobImage").hidden = true;
  state.mobActionPlanSequence += 1;
  $("migrateMobActionBtn").disabled = true;
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

function rowLabel(row) {
  const meta = row.left || row.right || {};
  return meta.name || row.path.split("/").pop() || "root";
}

function metaValue(meta) {
  if (!meta) return "缺失";
  if (meta.value && typeof meta.value === "object") return Object.values(meta.value).join(", ");
  if (meta.value !== undefined && meta.value !== null) return String(meta.value);
  if (meta.type === "canvas") return `${meta.width || 0}×${meta.height || 0}`;
  if (meta.childCount !== undefined) return `${meta.childCount}`;
  return "";
}

function typeIcon(type) {
  return ({imgdir: "D", canvas: "C", vector: "V", string: "S", int: "#", long: "L", short: "#", float: "F", double: "F", uol: "↗"})[type] || "·";
}

function visiblePaths() {
  const search = $("treeSearch").value.trim().toLowerCase();
  const diffOnly = $("diffOnly").checked;
  const keep = new Set();
  if (search || diffOnly) {
    for (const row of state.rows) {
      if (!row.path) continue;
      const haystack = `${row.path} ${metaValue(row.left)} ${metaValue(row.right)}`.toLowerCase();
      const matchesSearch = !search || haystack.includes(search);
      const matchesDiff = !diffOnly || row.status !== "same";
      if (!matchesSearch || !matchesDiff) continue;
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
      if ((search || diffOnly) && !keep.has(path)) continue;
      output.push({path, depth});
      if ((state.expanded.has(path) || search || diffOnly) && state.children.has(path)) visit(path, depth + 1);
    }
  };
  if (state.expanded.has("") || search || diffOnly) visit("", 1);
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
    return `<div class="tree-row status-${row.status} ${state.selectedPath === path ? "selected" : ""}" data-path="${escapeHtml(path)}" style="padding-left:${8 + depth * 15}px" role="treeitem" aria-selected="${state.selectedPath === path}">
      <button class="twisty" type="button" data-twist="${escapeHtml(path)}" ${hasChildren ? "" : "disabled"}>${hasChildren ? (open ? "▾" : "▸") : ""}</button>
      <span class="node-icon">${typeIcon(meta.type)}</span>
      <span class="node-body">
        <span class="node-title-line"><span class="node-name" title="${escapeHtml(path)}">${escapeHtml(rowLabel(row))}</span><span class="node-status">${statusLabel}</span>${resourceBadges}</span>
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
}

async function loadComparison() {
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
    await loadPreview(loadSequence);
  } catch (error) {
    if (loadSequence !== state.loadSequence) return;
    showResult(error.message, true);
    $("previewEmpty").innerHTML = `<strong>加载失败</strong><span>${escapeHtml(error.message)}</span>`;
  }
}

async function refreshComparisonAfterCopy(path) {
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
  await loadPreview(loadSequence);
}

async function loadPreview(loadSequence = state.loadSequence) {
  try {
    if (state.kind === "map") {
      const [leftResult, rightResult] = await Promise.allSettled([
        post("/api/preview", {kind: "map", sourcePath: state.leftPath}),
        post("/api/preview", {kind: "map", sourcePath: state.rightPath}),
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
        post("/api/preview", {kind: "mob", sourcePath: state.leftPath}),
        post("/api/preview", {kind: "mob", sourcePath: state.rightPath}),
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

function activeMobComparisonSource() {
  return state.mobSources?.sources.find((source) => source.path === state.rightPath) || null;
}

async function updateMobActionMigration() {
  const button = $("migrateMobActionBtn");
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
  const select = $("actionSelect");
  const discoveredActionNames = Array.from(new Set([
    ...(leftData?.actions || []).map((action) => action.name),
    ...(rightData?.actions || []).map((action) => action.name),
  ]));
  const preferredOrder = ["stand", "move", "fly", "jump", "hit1", "die1"];
  const actionNames = [
    ...preferredOrder.filter((name) => discoveredActionNames.includes(name)),
    ...discoveredActionNames.filter((name) => !preferredOrder.includes(name)),
  ];
  select.innerHTML = actionNames.map((name) => {
    const left = leftData?.actions.find((action) => action.name === name);
    const right = rightData?.actions.find((action) => action.name === name);
    const placeholder = right?.frames.length && !hasVisibleMobFrame(right) ? " · B 占位" : "";
    return `<option value="${escapeHtml(name)}">${escapeHtml(name)} · A ${left?.frames.length || 0} / B ${right?.frames.length || 0}${placeholder}</option>`;
  }).join("");
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
  select.value = state.mobActionName;
  state.mobElapsed = 0;
  state.mobPlaying = true;
  state.zoom = 1;
  $("zoomRange").value = 100;
  $("zoomValue").textContent = "100%";
  $("playBtn").textContent = "Ⅱ";
  $("leftMobMeta").textContent = leftData
    ? `${leftData.actions.length} 动作 · Lv.${leftData.stats.level ?? "?"}`
    : (leftError?.message || "主文件预览不可用");
  const activeSource = activeMobComparisonSource();
  $("rightMobSourceLabel").textContent = activeSource?.kind === "ms"
    ? "TMS MS 完整记录"
    : (activeSource?.label || "对比文件");
  $("rightMobMeta").textContent = rightData
    ? `${rightData.actions.length} 动作 · Lv.${rightData.stats.level ?? "?"}`
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
    {name: "left", data: state.preview, imageId: "leftMobImage", counterId: "leftFrameCounter"},
    {name: "right", data: state.rightPreview, imageId: "rightMobImage", counterId: "rightFrameCounter"},
  ];
  const remainingDelays = [];
  for (const side of sides) {
    const action = side.data?.actions.find((candidate) => candidate.name === state.mobActionName);
    const image = $(side.imageId);
    if (!action?.frames.length) {
      image.removeAttribute("src");
      image.hidden = true;
      $(side.counterId).textContent = "此侧无该动作";
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
    const frame = action.frames[index];
    image.hidden = false;
    image.src = apiUrl(frame.url);
    image.style.marginLeft = `${(frame.origin.x - frame.width / 2) * state.zoom * -1}px`;
    image.style.marginTop = `${(frame.origin.y - frame.height) * state.zoom * -1}px`;
    image.style.transform = `scale(${state.zoom})`;
    $(side.counterId).textContent = `${index + 1} / ${action.frames.length} · ${frame.delay} ms`;
  }
  if (state.mobPlaying && remainingDelays.length) {
    const nextDelay = Math.min(...remainingDelays);
    state.mobTimer = setTimeout(() => {
      state.mobElapsed += nextDelay;
      showMobFrames();
    }, nextDelay);
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

function prettyValue(meta) {
  if (!meta) return "—";
  if (meta.value !== undefined) return typeof meta.value === "object" ? JSON.stringify(meta.value) : String(meta.value);
  if (meta.type === "canvas") return `${meta.width ?? 0} × ${meta.height ?? 0} · format ${meta.format ?? "?"}`;
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
  setInspectorMode("node");
  renderInspector(row);
  revealSelectedMapContent();
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
  const unsafeDescendants = row ? state.rows.filter((candidate) => (
    (row.path === "" || candidate.path === row.path || candidate.path.startsWith(`${row.path}/`))
    && candidate.right
    && (candidate.right.compatibility?.status !== "ok" || !supportedCopyTypes.has(candidate.right.type))
  )) : [];
  const selectedSupported = Boolean(row?.right && supportedCopyTypes.has(row.right.type));
  const safeToCopy = copyCompatibility?.status === "ok" && selectedSupported;
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
  const validParent = left?.type === "imgdir" || (state.leftInfo?.format === "xml" && left?.type === "canvas");
  $("createMainBtn").hidden = leftExists || !clientImgPath;
  $("createMainBtn").disabled = leftExists || !clientImgPath;
  $("copyTmsBtn").textContent = resourceOnlyRepair
    ? "补齐选中节点的引用资源"
    : "复制选中的 TMS 节点到 A";
  $("copyTmsBtn").title = resourceOnlyRepair
    ? `保留当前地图节点不变，仅迁移 ${autoResources.length} 个不完整引用资源（NPC/怪物会同步服务端 XML 和 String）`
    : safeToCopy
    ? (unsafeDescendants.length
      ? `复制整个兼容子树；自动略过 ${unsafeDescendants.length} 个现代或不兼容后代，首个为 ${unsafeDescendants[0].path}`
      : "按原路径复制整个节点；缺失的主文件和父目录会自动建立，并同步客户端 IMG 与服务端 XML")
    : (copyCompatibility?.suggestion || "该节点不能直接复制到旧端");
  if (!resourceOnlyRepair && safeToCopy && autoResources.length) {
    $("copyTmsBtn").title += `；同时自动迁移 ${autoResources.length} 个缺失引用资源（NPC/怪物会同步 String）`;
  }
  if (safeToCopy && blockedEntities.length) {
    $("copyTmsBtn").title = `引用资源无法安全自动迁移：${blockedEntities.map((resource) => `${resource.kind.toUpperCase()} ${resource.name}`).join("、")}`;
  }
  $("copyTmsBtn").disabled = !(
    copyWritable && clientImgPath && row?.right && (!row?.left || mergeIntoEmpty || resourceOnlyRepair)
    && safeToCopy && !blockedEntities.length && state.rightInfo?.format === "img"
  );
  $("addRootBtn").disabled = !writable;
  $("addChildBtn").disabled = !(writable && validParent);
  $("deleteBtn").disabled = !(writable && left && Boolean(row.path));
  $("exportBtn").disabled = !writable;
}

function setInspectorMode(mode) {
  const compatibilityMode = mode === "compatibility";
  const diagnosticMode = mode === "diagnostic";
  $("compatibility").hidden = !compatibilityMode;
  $("crashDiagnostic").hidden = !diagnosticMode;
  $("inspector").hidden = compatibilityMode || diagnosticMode;
  $("compatibilityTab").classList.toggle("active", compatibilityMode);
  $("diagnosticTab").classList.toggle("active", diagnosticMode);
  $("nodeDetailTab").classList.toggle("active", !compatibilityMode && !diagnosticMode);
  $("compatibilityTab").setAttribute("aria-selected", String(compatibilityMode));
  $("diagnosticTab").setAttribute("aria-selected", String(diagnosticMode));
  $("nodeDetailTab").setAttribute("aria-selected", String(!compatibilityMode && !diagnosticMode));
  if (compatibilityMode || diagnosticMode) {
    $("editActions").hidden = true;
    if (diagnosticMode && state.kind === "map" && state.leftInfo?.exists !== false && state.diagnosticPath !== state.leftPath) {
      runCrashDiagnostic();
    }
  } else if (state.selectedPath !== null) {
    renderInspector(state.rowByPath.get(state.selectedPath));
  }
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
  $("runDiagnosticBtn").addEventListener("click", runCrashDiagnostic);
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
    $("runDiagnosticBtn").addEventListener("click", runCrashDiagnostic);
  }
}

async function openDiagnosticMob(id) {
  setKind("mob");
  $("itemId").value = id;
  $("leftPath").value = `clien/Data/Mob/${id}.img`;
  $("rightPath").value = `gms-server/wz/Mob.wz/${id}.img.xml`;
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
  const table = fields.map(([label, values]) => {
    if (!Array.isArray(values)) return `<tr><th>${label}</th><td colspan="2">${escapeHtml(values)}</td></tr>`;
    const different = values[0] !== values[1] ? "different" : "";
    return `<tr><th>${label}</th><td class="${different}">${escapeHtml(values[0])}</td><td class="${different}">${escapeHtml(values[1])}</td></tr>`;
  }).join("");
  const inspector = $("inspector");
  const semantic = left || right || {};
  const leftCompatibility = left?.compatibility;
  const rightCompatibility = right?.compatibility;
  const semanticMarkup = `<div class="node-explanation">
    <div class="side-label">节点解析</div>
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
  inspector.innerHTML = `${semanticMarkup}${resourceMarkup}<div class="side-label">属性对比</div><table class="compare-table"><thead><tr><th>属性</th><th><span class="column-badge a">A</span>主文件</th><th><span class="column-badge b">B</span>对比</th></tr></thead><tbody>${table}</tbody></table>${editorMarkup(left)}`;
  const leftXml = state.leftInfo?.format === "xml";
  const editable = Boolean(left?.editable && (leftXml || state.leftInfo?.format === "img"));
  $("editActions").hidden = !editable;
  updateNodeActions();
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
  if (!confirm(`写入主文件节点 ${state.selectedPath}？`)) return;
  try {
    const syncServer = $("syncServer").checked;
    const data = await post("/api/edit", {sourcePath: state.leftPath, path: state.selectedPath, value: currentEditValue(row.left), dryRun: false, backup: true, syncServer});
    const targetText = syncServer ? "客户端与服务端" : "客户端";
    const resultText = `${targetText}写入完成，已重新加载左侧节点\n${JSON.stringify(data, null, 2)}`;
    await loadComparison();
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
  if (!confirm(`删除节点 ${state.selectedPath}？`)) return;
  try {
    const syncServer = $("syncServer").checked;
    const data = await post("/api/delete", {sourcePath: state.leftPath, path: deletedPath, dryRun: false, backup: true, syncServer});
    const targetText = syncServer ? "客户端与服务端" : "客户端";
    const resultText = `${targetText}删除完成，左侧节点已重新加载\n${JSON.stringify(data, null, 2)}`;
    await loadComparison();
    revealNode(parentPath);
    showResult(resultText);
  } catch (error) {
    showResult(error.message, true);
  }
}

async function createMainFile() {
  if (!confirm(`创建空白主文件 ${state.leftPath}，并建立对应服务端 XML？`)) return;
  try {
    const data = await post("/api/create-main", {sourcePath: state.leftPath});
    const resultText = `空白主文件创建完成，可从 TMS 逐个复制兼容节点。\n${JSON.stringify(data, null, 2)}`;
    await loadComparison();
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
    const resultText = `${operation}${skipped}${migratedResources}${unresolvedResources}${recordedFiles}\n${JSON.stringify(data, null, 2)}`;
    showResult(resultText);
    await refreshComparisonAfterCopy(path);
  } catch (error) {
    showResult(error.message, true);
  } finally {
    updateNodeActions();
  }
}

async function migrateMobAction() {
  const actionName = state.mobActionName;
  const source = activeMobComparisonSource();
  const leftAction = state.preview?.actions.find((action) => action.name === actionName);
  if (!actionName || !source) return;
  const verb = leftAction ? "替换" : "新增";
  if (!confirm(
    `${verb} A 中的动作 ${actionName}？\n\n`
    + `来源：${source.label}\n`
    + "客户端只修改这个顶层动作记录，并同步服务端同名 XML 块。",
  )) return;

  const button = $("migrateMobActionBtn");
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
    await loadComparison();
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
  if (!confirm(`复制当前修改文件到 ${destination}？`)) return;
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
  if (!confirm(`写入节点 ${addedPath}？`)) return;
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
    await loadComparison();
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
$("itemId").addEventListener("input", () => {
  const id = $("itemId").value.trim();
  updateDefaultPaths(id);
  if (state.kind === "mob") loadMobSourcesDebounced(id);
  searchCatalogDebounced();
});
$("itemId").addEventListener("focus", searchCatalog);
document.addEventListener("click", (event) => {
  if (!event.target.closest(".id-field")) $("catalog").hidden = true;
});
$("compareBtn").addEventListener("click", loadComparison);
$("reloadBtn").addEventListener("click", loadComparison);
$("compatibilityTab").addEventListener("click", () => setInspectorMode("compatibility"));
$("diagnosticTab").addEventListener("click", () => setInspectorMode("diagnostic"));
$("nodeDetailTab").addEventListener("click", () => setInspectorMode("node"));
$("runDiagnosticBtn").addEventListener("click", runCrashDiagnostic);
$("swapBtn").addEventListener("click", () => {
  const left = $("leftPath").value;
  $("leftPath").value = $("rightPath").value;
  $("rightPath").value = left;
});
$("browseRightBtn").addEventListener("click", openFileBrowser);
$("fileUpBtn").addEventListener("click", () => { if (fileBrowser.parent) browseDirectory(fileBrowser.parent); });
$("fileSearch").addEventListener("input", renderFileList);
$("chooseFileBtn").addEventListener("click", chooseFile);
$("fileDialog").addEventListener("close", () => {
  if (fileBrowser.mode !== "directory") return;
  fileBrowser.mode = "file";
  if (!$("exportDialog").open) $("exportDialog").showModal();
});
$("treeSearch").addEventListener("input", renderTree);
$("diffOnly").addEventListener("change", renderTree);
$("collapseBtn").addEventListener("click", () => { state.expanded = new Set([""]); renderTree(); });
$("expandBtn").addEventListener("click", () => {
  state.expanded = new Set(state.rows.filter((row) => row.status !== "same").flatMap((row) => {
    const parts = row.path.split("/");
    return parts.map((_, index) => parts.slice(0, index + 1).join("/"));
  }));
  renderTree();
});
$("saveBtn").addEventListener("click", saveEdit);
$("createMainBtn").addEventListener("click", createMainFile);
$("copyTmsBtn").addEventListener("click", copyTmsNode);
$("exportBtn").addEventListener("click", openExportDialog);
$("browseExportBtn").addEventListener("click", openExportDirectoryBrowser);
$("exportDestination").addEventListener("input", updateExportPreview);
$("exportIncludeServer").addEventListener("change", updateExportPreview);
$("confirmExportBtn").addEventListener("click", exportFiles);
$("deleteBtn").addEventListener("click", deleteNode);
$("addRootBtn").addEventListener("click", () => openAddDialog(""));
$("addChildBtn").addEventListener("click", () => openAddDialog(state.selectedPath));
$("confirmAddBtn").addEventListener("click", addNode);
$("newNodeType").addEventListener("change", () => {
  const type = $("newNodeType").value;
  $("vectorFields").hidden = type !== "vector";
  $("newValueField").hidden = ["vector", "imgdir", "null"].includes(type);
});
$("showFootholds").addEventListener("change", drawMaps);
$("showMobs").addEventListener("change", drawMaps);
$("showNpcs").addEventListener("change", drawMaps);
$("showPortals").addEventListener("change", drawMaps);
$("showWaterAreas").addEventListener("change", drawMaps);
$("waterSelectBtn").addEventListener("click", () => {
  state.waterSelectMode = !state.waterSelectMode;
  $("waterSelectBtn").classList.toggle("active", state.waterSelectMode);
  $("waterSelectBtn").textContent = state.waterSelectMode ? "拖动框选水域" : "框选游泳区";
  for (const view of Object.values(state.mapViews)) $(view.stageId).classList.toggle("water-selecting", state.waterSelectMode);
});
$("zoomRange").addEventListener("input", () => { state.zoom = Number($("zoomRange").value) / 100; applyZoom(); });
$("fitBtn").addEventListener("click", fitPreview);
$("actionSelect").addEventListener("change", () => {
  state.mobActionName = $("actionSelect").value;
  state.mobElapsed = 0;
  showMobFrames();
  updateMobActionMigration();
});
$("playBtn").addEventListener("click", () => {
  state.mobPlaying = !state.mobPlaying;
  $("playBtn").textContent = state.mobPlaying ? "Ⅱ" : "▶";
  showMobFrames();
});
$("migrateMobActionBtn").addEventListener("click", migrateMobAction);
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

$("itemId").value = "100000000";
updateDefaultPaths("100000000");
loadComparison();
