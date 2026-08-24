const $ = (id) => document.getElementById(id);
const tmsDataRoot = document.body.dataset.tmsDataRoot;

const state = {
  kind: "map",
  rows: [],
  rowByPath: new Map(),
  children: new Map(),
  expanded: new Set([""]),
  selectedPath: null,
  leftPath: "",
  rightPath: "",
  leftInfo: null,
  rightInfo: null,
  compatibility: null,
  preview: null,
  rightPreview: null,
  zoom: 1,
  mapViews: {
    left: {preview: null, images: [], lifeImages: [], portalImages: [], hitRegions: [], canvasId: "mapCanvas", stageId: "leftMapStage"},
    right: {preview: null, images: [], lifeImages: [], portalImages: [], hitRegions: [], canvasId: "rightMapCanvas", stageId: "rightMapStage"},
  },
  mobAction: null,
  mobFrame: 0,
  mobPlaying: true,
  mobTimer: null,
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
    const response = await fetch(url, options);
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
  document.querySelectorAll(".segment").forEach((button) => button.classList.toggle("active", button.dataset.kind === kind));
  $("previewTitle").textContent = kind === "map" ? "地图预览" : "怪物预览";
  $("mapControls").hidden = kind !== "map";
  $("mobControls").hidden = kind !== "mob";
  $("itemId").placeholder = kind === "map" ? "9 位地图 ID" : "7 位怪物 ID";
  clearWorkspace();
  updateDefaultPaths($("itemId").value.trim());
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
    $("rightPath").value = `${tmsDataRoot}/Mob/${id}.img`;
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
  for (const view of Object.values(state.mapViews)) {
    view.preview = null;
    view.images = [];
    view.lifeImages = [];
    view.portalImages = [];
    view.hitRegions = [];
  }
  stopMobTimer();
  $("tree").innerHTML = "";
  $("nodeCount").textContent = "0";
  $("changedCount").textContent = "0";
  $("leftOnlyCount").textContent = "0";
  $("rightOnlyCount").textContent = "0";
  $("compatibilityCount").textContent = "0";
  $("previewEmpty").hidden = false;
  $("mapCompareView").hidden = true;
  $("mobStage").hidden = true;
  $("previewMeta").textContent = "未加载";
  $("inspector").className = "inspector empty-state compact";
  $("inspector").innerHTML = '<span class="empty-mark small" aria-hidden="true">⌖</span><strong>选择左侧节点</strong><span>这里会显示属性、差异与可编辑值。</span>';
  $("compatibility").innerHTML = '<div class="empty-state compact"><strong>等待对比结果</strong><span>加载后会分析 B 独有节点和现代资源兼容风险。</span></div>';
  setInspectorMode("compatibility");
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
    ? items.map((item) => `<button class="catalog-item" type="button" data-id="${escapeHtml(item.id)}" data-left="${escapeHtml(item.leftPath)}" data-right="${escapeHtml(item.rightPath)}"><span>${escapeHtml(item.id)}</span><small>${item.hasXml ? "A + B" : "仅 A"}</small></button>`).join("")
    : '<div class="empty-state compact"><span>没有匹配文件</span></div>';
  catalog.hidden = false;
  catalog.querySelectorAll(".catalog-item").forEach((button) => {
    button.addEventListener("click", () => {
      $("itemId").value = button.dataset.id;
      $("leftPath").value = button.dataset.left;
      $("rightPath").value = button.dataset.right;
      catalog.hidden = true;
      loadComparison();
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
  const visit = (parent, depth) => {
    for (const path of state.children.get(parent) || []) {
      if ((search || diffOnly) && !keep.has(path)) continue;
      output.push({path, depth});
      if ((state.expanded.has(path) || search || diffOnly) && state.children.has(path)) visit(path, depth + 1);
    }
  };
  visit("", 0);
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
    return `<div class="tree-row status-${row.status} ${state.selectedPath === path ? "selected" : ""}" data-path="${escapeHtml(path)}" style="padding-left:${8 + depth * 15}px" role="treeitem" aria-selected="${state.selectedPath === path}">
      <button class="twisty" type="button" data-twist="${escapeHtml(path)}" ${hasChildren ? "" : "disabled"}>${hasChildren ? (open ? "▾" : "▸") : ""}</button>
      <span class="node-icon">${typeIcon(meta.type)}</span>
      <span class="node-body">
        <span class="node-title-line"><span class="node-name" title="${escapeHtml(path)}">${escapeHtml(rowLabel(row))}</span><span class="node-status">${statusLabel}</span></span>
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
  $("catalog").hidden = true;
  clearWorkspace();
  try {
    const data = await post("/api/compare", {kind: state.kind, leftPath, rightPath});
    state.rows = data.nodes;
    state.leftPath = data.leftPath;
    state.rightPath = data.rightPath;
    state.leftInfo = data.leftInfo;
    state.rightInfo = data.rightInfo;
    state.compatibility = data.compatibility;
    buildTreeIndex();
    state.expanded = new Set([""]);
    $("nodeCount").textContent = `${data.nodes.length} 节点`;
    $("changedCount").textContent = data.counts.changed;
    $("leftOnlyCount").textContent = data.counts.leftOnly;
    $("rightOnlyCount").textContent = data.counts.rightOnly;
    renderCompatibility(data.compatibility);
    renderTree();
    setInspectorMode("compatibility");
    await loadPreview();
  } catch (error) {
    showResult(error.message, true);
    $("previewEmpty").innerHTML = `<strong>加载失败</strong><span>${escapeHtml(error.message)}</span>`;
  }
}

async function loadPreview() {
  try {
    if (state.kind === "map") {
      const [leftResult, rightResult] = await Promise.allSettled([
        post("/api/preview", {kind: "map", sourcePath: state.leftPath}),
        post("/api/preview", {kind: "map", sourcePath: state.rightPath}),
      ]);
      if (leftResult.status === "rejected") throw leftResult.reason;
      state.preview = leftResult.value;
      state.rightPreview = rightResult.status === "fulfilled" ? rightResult.value : null;
      $("previewEmpty").hidden = true;
      await prepareMapPreview(state.preview, state.rightPreview, rightResult.status === "rejected" ? rightResult.reason : null);
    } else {
      const data = await post("/api/preview", {kind: "mob", sourcePath: state.leftPath});
      state.preview = data;
      $("previewEmpty").hidden = true;
      prepareMobPreview(data);
    }
  } catch (error) {
    $("previewEmpty").hidden = false;
    $("previewEmpty").innerHTML = `<strong>预览不可用</strong><span>${escapeHtml(error.message)}</span>`;
  }
}

async function prepareMapPreview(leftData, rightData, rightError = null) {
  stopMobTimer();
  $("mobStage").hidden = true;
  $("mapCompareView").hidden = false;
  $("previewMeta").textContent = rightData
    ? `A ${leftData.summary.elements} 个场景元素 · B ${rightData.summary.elements} 个场景元素`
    : `A ${leftData.summary.elements} 个场景元素 · B 预览不可用`;
  $("leftMapMeta").textContent = `${leftData.summary.mobs} 怪 · ${leftData.summary.npcs} NPC · ${leftData.summary.portals} 门`;
  $("rightMapSourceLabel").textContent = state.rightPath.includes("/TMS/") ? "TMS 对比" : "对比文件";
  $("rightMapMeta").textContent = rightData
    ? `${rightData.summary.mobs} 怪 · ${rightData.summary.npcs} NPC · ${rightData.summary.portals} 门`
    : (rightError?.message || "无法生成预览");
  const imageCache = new Map();
  const loadImage = (url) => {
    if (!imageCache.has(url)) {
      imageCache.set(url, (async () => {
        const image = new Image();
        image.src = url;
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
  drawMapSprites(view, context, view.portalImages, ox, oy, $("showPortals").checked, "#70a7cf", "P");
  drawMapSprites(view, context, view.lifeImages.filter(({point}) => point.kind === "mob"), ox, oy, $("showMobs").checked, "#e26e67", "M");
  drawMapSprites(view, context, view.lifeImages.filter(({point}) => point.kind === "npc"), ox, oy, $("showNpcs").checked, "#e7bd6c", "N");
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

function prepareMobPreview(data) {
  $("mapCompareView").hidden = true;
  $("mobStage").hidden = false;
  const select = $("actionSelect");
  select.innerHTML = data.actions.map((action) => `<option value="${escapeHtml(action.name)}">${escapeHtml(action.name)} · ${action.frames.length}</option>`).join("");
  state.mobAction = data.actions[0] || null;
  state.mobFrame = 0;
  state.mobPlaying = true;
  state.zoom = 1;
  $("zoomRange").value = 100;
  $("zoomValue").textContent = "100%";
  $("playBtn").textContent = "Ⅱ";
  $("previewMeta").textContent = data.actions.length ? `${data.actions.length} 个动作 · Lv.${data.stats.level ?? "?"}` : "没有可播放动作";
  showMobFrame();
}

function stopMobTimer() {
  clearTimeout(state.mobTimer);
  state.mobTimer = null;
}

function showMobFrame() {
  stopMobTimer();
  const action = state.mobAction;
  if (!action || !action.frames.length) {
    $("mobImage").removeAttribute("src");
    $("frameCounter").textContent = "0 / 0";
    return;
  }
  const frame = action.frames[state.mobFrame % action.frames.length];
  const image = $("mobImage");
  image.src = frame.url;
  image.style.marginLeft = `${(frame.origin.x - frame.width / 2) * state.zoom * -1}px`;
  image.style.marginTop = `${(frame.origin.y - frame.height) * state.zoom * -1}px`;
  image.style.transform = `scale(${state.zoom})`;
  $("frameCounter").textContent = `${state.mobFrame + 1} / ${action.frames.length} · ${frame.delay} ms`;
  if (state.mobPlaying) {
    state.mobTimer = setTimeout(() => {
      state.mobFrame = (state.mobFrame + 1) % action.frames.length;
      showMobFrame();
    }, frame.delay);
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
  else showMobFrame();
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
  $("selectedPath").textContent = path;
  $("selectedPath").title = path;
  setInspectorMode("node");
  renderInspector(row);
}

function setInspectorMode(mode) {
  const compatibilityMode = mode === "compatibility";
  $("compatibility").hidden = !compatibilityMode;
  $("inspector").hidden = compatibilityMode;
  $("compatibilityTab").classList.toggle("active", compatibilityMode);
  $("nodeDetailTab").classList.toggle("active", !compatibilityMode);
  $("compatibilityTab").setAttribute("aria-selected", String(compatibilityMode));
  $("nodeDetailTab").setAttribute("aria-selected", String(!compatibilityMode));
  if (compatibilityMode) {
    $("editActions").hidden = true;
  } else if (state.selectedPath) {
    renderInspector(state.rowByPath.get(state.selectedPath));
  }
}

function renderCompatibility(report) {
  const container = $("compatibility");
  if (!report) {
    $("compatibilityCount").textContent = "0";
    container.innerHTML = '<div class="empty-state compact"><strong>当前类型暂无兼容分析</strong><span>节点详情仍可查看完整 A/B 差异。</span></div>';
    return;
  }
  $("compatibilityCount").textContent = report.missingResourceCount + report.modernCandidateCount;
  const statusText = {ready: "旧客户端可解析", missingFile: "旧客户端缺文件", missingCanvas: "Canvas 路径不兼容"};
  const statusAdvice = {
    ready: "可复用现有资源，但节点仍需投影到旧版结构。",
    missingFile: "不要整包复制 TMS IMG；提取必要 Canvas，转换为 GMS ARGB4444 后通过新增资源或增量记录迁移。",
    missingCanvas: "同名文件不等于兼容；映射到旧客户端支持的层级，并保留 origin、delay、z 和动画顺序。",
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
      <div class="resource-title"><strong>${escapeHtml(item.kind.toUpperCase())} · ${escapeHtml(item.name)}</strong><span>${statusText[item.status]}</span></div>
      <code>${escapeHtml(item.clientPath)}${item.canvasPaths.length ? ` → ${escapeHtml(item.canvasPaths.join(" · "))}` : ""}</code>
      <p>${statusAdvice[item.status]}</p>
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
    </dl>
    <div class="compat-verdicts">
      <span class="verdict verdict-${escapeHtml(leftCompatibility?.status || "missing")}">A ${escapeHtml(leftCompatibility?.label || "缺失")}</span>
      <span class="verdict verdict-${escapeHtml(rightCompatibility?.status || "missing")}">B ${escapeHtml(rightCompatibility?.label || "缺失")}</span>
    </div>
    ${leftCompatibility?.reason ? `<p><b>A：</b>${escapeHtml(leftCompatibility.reason)}</p>` : ""}
    ${rightCompatibility?.reason ? `<p><b>B：</b>${escapeHtml(rightCompatibility.reason)}</p>` : ""}
  </div>`;
  inspector.className = "inspector";
  inspector.innerHTML = `${semanticMarkup}<div class="side-label">属性对比</div><table class="compare-table"><thead><tr><th>属性</th><th><span class="column-badge a">A</span>主文件</th><th><span class="column-badge b">B</span>对比</th></tr></thead><tbody>${table}</tbody></table>${editorMarkup(left)}`;
  const leftXml = state.leftInfo?.format === "xml";
  const editable = Boolean(left?.editable && (leftXml || state.leftInfo?.format === "img"));
  $("editActions").hidden = !editable;
  $("addBtn").disabled = !(leftXml && ["imgdir", "canvas"].includes(left?.type));
  $("deleteBtn").disabled = !(leftXml && left && row.path);
}

function editorMarkup(meta) {
  if (!meta?.editable) return `<p class="editor-note">该节点在主文件中只读。二进制 IMG 只开放等长标量原位编辑，增删节点请在 XML 中完成。</p>`;
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
    ? `IMG 安全模式：编码长度必须保持不变${meta.byteLength !== undefined ? `，字符串槽位 ${meta.byteLength} 字节` : ""}。`
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
  const dryRun = $("dryRun").checked;
  if (!dryRun && !confirm(`写入主文件节点 ${state.selectedPath}？`)) return;
  try {
    const data = await post("/api/edit", {sourcePath: state.leftPath, path: state.selectedPath, value: currentEditValue(row.left), dryRun, backup: true});
    showResult(`${dryRun ? "预演完成" : "写入完成"}\n${JSON.stringify(data, null, 2)}`);
    if (!dryRun) await loadComparison();
  } catch (error) {
    showResult(error.message, true);
  }
}

async function deleteNode() {
  if (!state.selectedPath) return;
  const dryRun = $("dryRun").checked;
  if (!confirm(`${dryRun ? "预演删除" : "删除"}节点 ${state.selectedPath}？`)) return;
  try {
    const data = await post("/api/delete", {sourcePath: state.leftPath, path: state.selectedPath, dryRun, backup: true});
    showResult(`${dryRun ? "预演完成" : "删除完成"}\n${JSON.stringify(data, null, 2)}`);
    if (!dryRun) await loadComparison();
  } catch (error) {
    showResult(error.message, true);
  }
}

function showResult(text, error = false) {
  const result = $("operationResult");
  result.hidden = false;
  result.textContent = text;
  result.style.color = error ? "#ef918a" : "#bad7c9";
}

const fileBrowser = {path: "", parent: null, items: [], selected: null};

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function renderFileList() {
  const query = $("fileSearch").value.trim().toLowerCase();
  const matches = fileBrowser.items.filter((item) => !query || item.name.toLowerCase().includes(query));
  const items = matches.slice(0, 200);
  const list = $("fileList");
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = '<div class="file-list-empty">当前目录没有可选择的文件</div>';
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
    $("selectedFileName").textContent = "未选择文件";
    $("chooseFileBtn").disabled = true;
    renderFileList();
  } catch (error) {
    $("fileList").innerHTML = `<div class="file-list-empty">${escapeHtml(error.message)}</div>`;
  }
}

function openFileBrowser() {
  $("fileSearch").value = "";
  $("fileDialog").showModal();
  browseDirectory($("rightPath").value.trim());
}

function chooseFile() {
  if (!fileBrowser.selected) return;
  $("rightPath").value = fileBrowser.selected.path;
  $("fileDialog").close();
}

function addNodeValue() {
  const type = $("newNodeType").value;
  if (type === "vector") return {x: Number($("newVectorX").value), y: Number($("newVectorY").value)};
  if (["int", "short", "long"].includes(type)) return Number.parseInt($("newNodeValue").value || "0", 10);
  if (["float", "double"].includes(type)) return Number.parseFloat($("newNodeValue").value || "0");
  return $("newNodeValue").value;
}

async function addNode() {
  const dryRun = $("dryRun").checked;
  try {
    const data = await post("/api/add", {
      sourcePath: state.leftPath,
      parentPath: state.selectedPath,
      name: $("newNodeName").value.trim(),
      type: $("newNodeType").value,
      value: addNodeValue(),
      dryRun,
      backup: true,
    });
    $("addDialog").close();
    showResult(`${dryRun ? "预演完成" : "添加完成"}\n${JSON.stringify(data, null, 2)}`);
    if (!dryRun) await loadComparison();
  } catch (error) {
    showResult(error.message, true);
    $("addDialog").close();
  }
}

document.querySelectorAll(".segment").forEach((button) => button.addEventListener("click", () => setKind(button.dataset.kind)));
$("itemId").addEventListener("input", debounce(() => {
  updateDefaultPaths($("itemId").value.trim());
  searchCatalog();
}, 180));
$("itemId").addEventListener("focus", searchCatalog);
document.addEventListener("click", (event) => {
  if (!event.target.closest(".id-field")) $("catalog").hidden = true;
});
$("compareBtn").addEventListener("click", loadComparison);
$("reloadBtn").addEventListener("click", loadComparison);
$("compatibilityTab").addEventListener("click", () => setInspectorMode("compatibility"));
$("nodeDetailTab").addEventListener("click", () => setInspectorMode("node"));
$("swapBtn").addEventListener("click", () => {
  const left = $("leftPath").value;
  $("leftPath").value = $("rightPath").value;
  $("rightPath").value = left;
});
$("browseRightBtn").addEventListener("click", openFileBrowser);
$("fileUpBtn").addEventListener("click", () => { if (fileBrowser.parent) browseDirectory(fileBrowser.parent); });
$("fileSearch").addEventListener("input", renderFileList);
$("chooseFileBtn").addEventListener("click", chooseFile);
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
$("deleteBtn").addEventListener("click", deleteNode);
$("addBtn").addEventListener("click", () => {
  $("newNodeName").value = "";
  $("addDialog").showModal();
  $("newNodeName").focus();
});
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
$("zoomRange").addEventListener("input", () => { state.zoom = Number($("zoomRange").value) / 100; applyZoom(); });
$("fitBtn").addEventListener("click", fitPreview);
$("actionSelect").addEventListener("change", () => {
  state.mobAction = state.preview.actions.find((action) => action.name === $("actionSelect").value) || null;
  state.mobFrame = 0;
  showMobFrame();
});
$("playBtn").addEventListener("click", () => {
  state.mobPlaying = !state.mobPlaying;
  $("playBtn").textContent = state.mobPlaying ? "Ⅱ" : "▶";
  showMobFrame();
});
function attachMapStageInteraction(side) {
  const stage = $(state.mapViews[side].stageId);
  let dragStart = null;
  stage.addEventListener("pointerdown", (event) => {
    if (state.kind !== "map" || event.button !== 0) return;
    dragStart = {x: event.clientX, y: event.clientY, left: stage.scrollLeft, top: stage.scrollTop, moved: false};
    stage.setPointerCapture(event.pointerId);
    stage.classList.add("dragging");
  });
  stage.addEventListener("pointermove", (event) => {
    if (!dragStart) {
      stage.classList.toggle("clickable", Boolean(mapHitAt(side, event.clientX, event.clientY)));
      return;
    }
    if (Math.hypot(event.clientX - dragStart.x, event.clientY - dragStart.y) > 4) dragStart.moved = true;
    stage.scrollLeft = dragStart.left - (event.clientX - dragStart.x);
    stage.scrollTop = dragStart.top - (event.clientY - dragStart.y);
  });
  const stopDragging = (event, allowSelection) => {
    if (!dragStart) return;
    const moved = dragStart.moved;
    dragStart = null;
    if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
    stage.classList.remove("dragging");
    const hit = allowSelection && !moved ? mapHitAt(side, event.clientX, event.clientY) : null;
    if (hit) revealNode(hit.path);
  };
  stage.addEventListener("pointerup", (event) => stopDragging(event, true));
  stage.addEventListener("pointercancel", (event) => stopDragging(event, false));
  stage.addEventListener("pointerleave", () => { if (!dragStart) stage.classList.remove("clickable"); });
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
