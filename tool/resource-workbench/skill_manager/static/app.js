"use strict";

const apiBase = document.body.dataset.apiBase || "";
const $ = (id) => document.getElementById(id);
const state = {
  jobs: [], group: "", book: "", availability: "all", selectedId: "", catalog: [], detail: null,
  track: "", previewSource: "local", playing: false, frame: 0, timer: 0,
  compareSource: "", nodeQuery: "", selectedPath: "", dialogMode: "add", expanded: new Set(), treePrimed: false,
};
const nodeTypeLabels = {Short:"短整数",Int:"整数",Long:"长整数",Float:"浮点",Double:"双精度",String:"字符串",Vector:"坐标",UOL:"链接",SubProperty:"目录",Null:"空值",Canvas:"画布"};
const copyableTypes = new Set(["Short","Int","Long","Float","Double","String","Vector","UOL","SubProperty","Null"]);
const editableTypes = new Set(["Short","Int","Long","Float","Double","String","Vector","UOL"]);

function url(path) { return `${apiBase}${path}`; }
function escapeHtml(value) { return String(value ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"); }
function pretty(value) { return value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value); }
function debounce(fn, delay) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); }; }
async function api(path, options={}) {
  const response = await fetch(url(path), options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) throw new Error(payload.reason || `HTTP ${response.status}`);
  return payload;
}
function post(path, body) { return api(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)}); }
let toastTimer;
function toast(message, error=false) {
  const box = $("toast"); box.textContent = message; box.classList.toggle("error", error); box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => box.hidden = true, error ? 6000 : 3000);
}
function busy(text) { $("stateText").textContent = text; }
function ready(text="已同步") { $("stateText").textContent = text; }

const iconObserver = new IntersectionObserver((entries) => entries.forEach((entry) => {
  if (!entry.isIntersecting) return;
  const image = entry.target; image.src = image.dataset.src; iconObserver.unobserve(image);
}), {root: $("skillList"), rootMargin: "180px"});

function fillJobSelects() {
  const groups = [...new Set(state.jobs.map((job) => job.group))];
  $("jobGroup").innerHTML = `<option value="">全部分组</option>` + groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`).join("");
  $("jobGroup").value = state.group;
  const jobs = state.jobs.filter((job) => !state.group || job.group === state.group);
  $("job").innerHTML = jobs.map((job) => {
    const marks = [job.local ? "本地" : null, job.ms ? "MS" : null, job.canvas ? "画布" : null, job.tms ? "TMS" : null].filter(Boolean).join("/");
    return `<option value="${escapeHtml(job.id)}">${escapeHtml(job.name)} (${job.id}) ${marks}</option>`;
  }).join("");
  if (!jobs.some((job) => job.id === state.book)) state.book = jobs[0]?.id || "";
  $("job").value = state.book;
}

async function loadJobs() {
  busy("载入职业");
  const payload = await api("/api/jobs");
  state.jobs = payload.jobs || [];
  fillJobSelects();
  ready("已载入职业");
}

async function loadSkills() {
  if (!state.book) return;
  busy("载入技能");
  try {
    const params = new URLSearchParams({job: state.book, availability: state.availability, q: $("search").value.trim()});
    const payload = await api(`/api/skills?${params}`);
    state.catalog = payload.items || [];
    $("total").textContent = payload.total || 0;
    const sources = payload.sources || {};
    $("sourceHint").textContent = [
      sources.local?.exists ? "本地" : null,
      sources.ms?.exists ? (sources.ms.pack || "MS") : null,
      sources.canvas?.exists ? "_Canvas" : null,
      sources.tms?.exists ? "TMS IMG" : null,
    ].filter(Boolean).join(" · ");
    renderCatalog();
    ready("已载入");
  } catch (error) {
    toast(error.message, true); ready("载入失败");
  }
}

function renderCatalog() {
  $("listEmpty").hidden = state.catalog.length > 0;
  $("skillList").innerHTML = state.catalog.map((item) => {
    const iconSource = item.iconSource || (item.local ? "local" : "tms");
    const icon = `<img data-src="${url(`/api/skill/${state.book}/${item.id}/icon?source=${iconSource}`)}" alt="">`;
    const badge = item.status === "missing" ? '<em class="missing">仅 TMS</em>' : item.status === "both" ? '<em class="both">本地＋TMS</em>' : '<em>仅本地</em>';
    return `<button class="item-row${item.id === state.selectedId ? " active" : ""}" type="button" data-skill-id="${item.id}">${icon}<strong>${escapeHtml(item.name)}</strong><small>${item.id}${badge}</small></button>`;
  }).join("");
  document.querySelectorAll("[data-skill-id]").forEach((button) => button.addEventListener("click", () => openSkill(button.dataset.skillId)));
  iconObserver.disconnect();
  document.querySelectorAll(".item-row img").forEach((image) => {
    image.addEventListener("error", () => { image.style.visibility = "hidden"; }, {once: true});
    iconObserver.observe(image);
  });
}

async function openSkill(skillId, previewSource) {
  const sameSkill = String(skillId) === state.selectedId;
  state.selectedId = String(skillId);
  $("detailEmpty").hidden = true;
  $("detail").hidden = false;
  $("skillId").textContent = skillId;
  if (!sameSkill) $("skillName").textContent = "载入中…";
  busy("载入对比");
  try {
    const source = previewSource || "local";
    const payload = await api(`/api/skill/${state.book}/${skillId}?source=${source}`);
    state.detail = payload;
    state.previewSource = payload.preview?.source || source;
    if (!sameSkill) {
      state.track = payload.preview?.tracks?.[0]?.name || "";
      state.frame = 0;
      state.expanded = new Set();
      state.selectedPath = "";
      state.treePrimed = false;
    }
    stopPreview();
    fillDetail();
    renderCatalog();
    ready("已载入");
  } catch (error) {
    toast(error.message, true); ready("读取失败");
  }
}

function fillDetail() {
  const payload = state.detail;
  const local = payload.local, tms = payload.tms, selected = local || tms;
  $("skillId").textContent = selected.id;
  $("jobLabel").textContent = state.jobs.find((job) => job.id === state.book)?.name || state.book;
  $("availability").textContent = `本地 ${local ? "✓" : "—"} · TMS ${tms ? "✓" : "—"}`;
  $("skillName").textContent = payload.skill?.name || `技能 ${selected.id}`;
  const files = [local?.file, tms?.file].filter(Boolean);
  $("skillFile").textContent = files.join("  ↔  ");
  $("skillFile").title = files.join("\n");
  const iconSource = local ? "local" : (state.catalog.find((item) => item.id === selected.id)?.iconSource || payload.tmsSource || "tms");
  $("skillIcon").src = url(`/api/skill/${state.book}/${selected.id}/icon?source=${iconSource}`);
  $("skillIcon").style.visibility = "visible";
  $("addLocalNodeBtn").disabled = !local?.mutable;
  fillCompareSourceSelect();
  renderSources();
  renderPreview();
  renderComparison();
}

function renderSources() {
  const sources = state.detail.sources || {};
  $("sourceBadges").innerHTML = ["local", "ms", "tms", "canvas"].map((key) => {
    const row = sources[key] || {};
    return `<span class="${row.exists ? "on" : ""}">${escapeHtml(row.label || key)}${row.exists ? "" : " · 无"}${row.error ? ` · ${escapeHtml(row.error)}` : ""}</span>`;
  }).join("");
}

function currentTrack() {
  return (state.detail.preview?.tracks || []).find((track) => track.name === state.track) || state.detail.preview?.tracks?.[0];
}

function renderPreview() {
  const tracks = state.detail.preview?.tracks || [];
  $("trackSelect").innerHTML = tracks.map((track) => `<option value="${escapeHtml(track.name)}">${escapeHtml(track.name)} (${track.frames.length})</option>`).join("");
  if (!tracks.some((track) => track.name === state.track)) state.track = tracks[0]?.name || "";
  $("trackSelect").value = state.track;
  const sources = state.detail.sources || {};
  $("previewSource").innerHTML = ["local", "ms", "tms", "canvas"].filter((key) => sources[key]?.exists).map((key) => `<option value="${key}">${escapeHtml(sources[key].label)}</option>`).join("");
  $("previewSource").value = sources[state.previewSource]?.exists ? state.previewSource : (state.detail.preview?.source || "local");
  const track = currentTrack();
  $("previewHint").textContent = track ? `${track.name} · ${track.frames.length} 帧 · ${track.frames.reduce((sum, frame) => sum + (frame.delay || 0), 0)}ms` : "没有可预览的动画帧";
  if (!$("previewDialog").open) {
    $("frameStrip").innerHTML = "";
    return;
  }
  $("frameStrip").innerHTML = (track?.frames || []).map((frame, index) => `
    <button type="button" data-frame="${index}" class="${index === state.frame ? "active" : ""}">
      <img src="${url(frame.url)}" alt="${escapeHtml(frame.path)}">
      <small>${escapeHtml(frame.name)} ${frame.delay}ms</small>
    </button>`).join("");
  document.querySelectorAll("[data-frame]").forEach((button) => button.addEventListener("click", () => {
    state.frame = Number(button.dataset.frame); stopPreview(); drawFrame(); renderPreview();
  }));
  drawFrame();
}

async function ensurePreviewTracks() {
  if ((state.detail.preview?.tracks || []).length) return;
  const source = state.previewSource || "local";
  const payload = await api(`/api/skill/${state.book}/${state.selectedId}?source=${encodeURIComponent(source)}&preview=1`);
  state.detail.preview = payload.preview;
}

function drawFrame() {
  const canvas = $("previewCanvas");
  const ctx = canvas.getContext("2d");
  const track = currentTrack();
  const frame = track?.frames?.[state.frame];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!frame) return;
  const image = new Image();
  image.onload = () => {
    const scale = Math.min(canvas.width / Math.max(image.width, 1), canvas.height / Math.max(image.height, 1), 1);
    const width = image.width * scale, height = image.height * scale;
    ctx.drawImage(image, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height);
  };
  image.src = url(frame.url);
}

function stopPreview() {
  state.playing = false;
  if (state.timer) { clearTimeout(state.timer); state.timer = 0; }
  $("playBtn").textContent = "播放";
}

function playPreview() {
  const track = currentTrack();
  if (!track?.frames?.length) return;
  state.playing = true;
  $("playBtn").textContent = "暂停";
  const tick = () => {
    if (!state.playing) return;
    drawFrame();
    const delay = track.frames[state.frame]?.delay || 100;
    state.frame = (state.frame + 1) % track.frames.length;
    state.timer = setTimeout(tick, delay);
  };
  tick();
}

function fillCompareSourceSelect() {
  const sources = state.detail.sources || {};
  const options = [["ms", sources.ms?.label || "TMS MS"], ["tms", sources.tms?.label || "TMS IMG"], ["canvas", sources.canvas?.label || "TMS _Canvas"]]
    .filter(([key]) => sources[key]?.exists);
  $("compareSource").innerHTML = options.map(([key, label]) => `<option value="${key}">${escapeHtml(label)}</option>`).join("") || '<option value="">无 TMS</option>';
  if (!options.some(([key]) => key === state.compareSource)) {
    state.compareSource = state.detail.tmsSource || options[0]?.[0] || "";
  }
  $("compareSource").value = state.compareSource;
}

function compareDetail() {
  if (state.compareSource === "ms") return state.detail.ms;
  if (state.compareSource === "canvas") return state.detail.canvas;
  if (state.compareSource === "tms") return state.detail.tmsImg || state.detail.tms;
  return state.detail.tms;
}

function comparisonRows() {
  const local = new Map((state.detail.local?.nodes || []).map((row) => [row.path, row]));
  const tms = new Map((compareDetail()?.nodes || []).map((row) => [row.path, row]));
  return [...new Set([...local.keys(), ...tms.keys()])].sort((a, b) => a.split("/").length - b.split("/").length || a.localeCompare(b, undefined, {numeric: true})).map((path) => {
    const left = local.get(path), right = tms.get(path);
    let status = !right ? "localOnly" : !left ? "tmsOnly" : "same";
    if (left && right && (left.type !== right.type || pretty(left.value) !== pretty(right.value))) status = "changed";
    return {path, status, local: left, tms: right, depth: path.split("/").length - 1, name: path.split("/").at(-1)};
  });
}

function parentPath(path) {
  return path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
}

function typeIcon(type) {
  return ({SubProperty:"/", Canvas:"C", Vector:"V", String:"S", Int:"I", Short:"H", Long:"L", Float:"F", Double:"D", UOL:"U", Null:"·"})[type] || "?";
}

function statusLabel(status) {
  return ({same:"一致", changed:"修改", localOnly:"仅 A", tmsOnly:"仅 B"})[status] || status;
}

function sideValue(node) {
  if (!node) return "—";
  if (node.type === "Canvas") return `${node.value?.width || 0}×${node.value?.height || 0}`;
  if (node.type === "SubProperty") return `${node.value?.children ?? 0} 子节点`;
  const text = pretty(node.value);
  return text || node.type;
}

function expandDiffAncestors(rows) {
  state.expanded.add("");
  rows.forEach((row) => {
    if (row.status === "same") return;
    let cursor = row.path;
    while (cursor) {
      state.expanded.add(parentPath(cursor));
      cursor = parentPath(cursor);
    }
  });
  const roots = rows.filter((row) => !row.path.includes("/"));
  roots.slice(0, 8).forEach((row) => state.expanded.add(row.path));
}

function comparisonIndex(rows) {
  const children = new Map([["", []]]);
  rows.forEach((row) => {
    const parent = parentPath(row.path);
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(row.path);
    if ((row.local?.container || row.tms?.container) && !children.has(row.path)) children.set(row.path, []);
  });
  children.forEach((list, key) => children.set(key, list.sort((a, b) => a.localeCompare(b, undefined, {numeric: true}))));
  return children;
}

function rowMatches(row, query, diffOnly) {
  if (diffOnly && row.status === "same") return false;
  if (!query) return true;
  return `${row.path} ${row.local?.type || ""} ${row.tms?.type || ""} ${pretty(row.local?.value)} ${pretty(row.tms?.value)}`.toLowerCase().includes(query);
}

function visibleTreePaths(rows) {
  const query = (state.nodeQuery || $("nodeSearch").value).trim().toLowerCase();
  const diffOnly = $("diffOnly").checked;
  const children = comparisonIndex(rows);
  const keep = new Set();
  if (query || diffOnly) {
    rows.forEach((row) => {
      if (!rowMatches(row, query, diffOnly)) return;
      let cursor = row.path;
      while (cursor) {
        keep.add(cursor);
        cursor = parentPath(cursor);
      }
      keep.add("");
    });
  }
  const output = [];
  const visit = (parent, depth) => {
    for (const path of children.get(parent) || []) {
      if ((query || diffOnly) && !keep.has(path)) continue;
      output.push({path, depth});
      const open = state.expanded.has(path) || query || diffOnly;
      if (open && children.has(path)) visit(path, depth + 1);
    }
  };
  visit("", 0);
  return {paths: output, children};
}

function selectedRow() {
  return comparisonRows().find((row) => row.path === state.selectedPath) || null;
}

function renderComparison() {
  const rows = comparisonRows();
  if (!state.treePrimed) {
    expandDiffAncestors(rows);
    state.treePrimed = true;
  }
  const mutable = Boolean(state.detail.local?.mutable);
  $("compareHint").textContent = mutable
    ? `${rows.length} 个节点 · TMS ${state.compareSource || "无"}`
    : "没有本地技能，只能查看 TMS";
  const {paths, children} = visibleTreePaths(rows);
  const byPath = new Map(rows.map((row) => [row.path, row]));
  if (state.selectedPath && !byPath.has(state.selectedPath)) state.selectedPath = "";
  if (!state.selectedPath && paths[0]) state.selectedPath = paths[0].path;
  $("tree").innerHTML = paths.map(({path, depth}) => {
    const row = byPath.get(path);
    const meta = row.local || row.tms || {};
    const hasChildren = (children.get(path) || []).length > 0;
    const open = state.expanded.has(path);
    return `<div class="tree-row status-${row.status}${path === state.selectedPath ? " selected" : ""}" data-path="${escapeHtml(path)}" style="padding-left:${8 + depth * 15}px" role="treeitem">
      <button class="twisty" type="button" data-twist="${escapeHtml(path)}" ${hasChildren ? "" : "disabled"}>${hasChildren ? (open ? "▾" : "▸") : ""}</button>
      <span class="node-icon">${typeIcon(meta.type)}</span>
      <span class="node-body">
        <span class="node-title-line"><span class="node-name" title="${escapeHtml(path)}">${escapeHtml(row.name)}</span><span class="node-status">${statusLabel(row.status)}</span></span>
        <span class="node-compare-values">
          <span class="node-side side-a ${row.local ? "" : "missing"}" title="${escapeHtml(sideValue(row.local))}"><b>A</b><span>${escapeHtml(sideValue(row.local))}</span></span>
          <span class="node-side side-b ${row.tms ? "" : "missing"}" title="${escapeHtml(sideValue(row.tms))}"><b>B</b><span>${escapeHtml(sideValue(row.tms))}</span></span>
        </span>
      </span>
    </div>`;
  }).join("") || '<div class="empty compact">没有匹配的节点</div>';
  $("tree").querySelectorAll(".twisty:not(:disabled)").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    const path = button.dataset.twist;
    if (state.expanded.has(path)) state.expanded.delete(path); else state.expanded.add(path);
    renderComparison();
  }));
  $("tree").querySelectorAll(".tree-row").forEach((line) => line.addEventListener("click", () => {
    state.selectedPath = line.dataset.path;
    renderComparison();
  }));
  renderInspector(selectedRow());
}

function canvasUrl(source, path) {
  return url(`/api/skill/${state.book}/${state.selectedId}/canvas?source=${source}&path=${encodeURIComponent(path)}`);
}

function renderInspector(row) {
  const box = $("inspector");
  if (!row) {
    box.className = "inspector empty-state";
    box.innerHTML = "<strong>选择左侧节点</strong><span>对照树里点选后，这里显示 A/B 详情和操作。</span>";
    $("selectedPath").textContent = "未选择节点";
    updateActionButtons(null);
    return;
  }
  $("selectedPath").textContent = row.path;
  const fields = [
    ["状态", statusLabel(row.status)],
    ["类型", [row.local?.type || "—", row.tms?.type || "—"]],
    ["值", [pretty(row.local?.value) || "—", pretty(row.tms?.value) || "—"]],
  ];
  const table = fields.map(([label, values]) => {
    if (!Array.isArray(values)) return `<tr><th>${label}</th><td colspan="2">${escapeHtml(values)}</td></tr>`;
    const different = values[0] !== values[1] ? "different" : "";
    return `<tr><th>${label}</th><td class="${different}">${escapeHtml(values[0])}</td><td class="${different}">${escapeHtml(values[1])}</td></tr>`;
  }).join("");
  const localCanvas = row.local?.type === "Canvas";
  const tmsCanvas = row.tms?.type === "Canvas";
  const preview = (localCanvas || tmsCanvas) ? `<div class="canvas-preview"><div class="side-label">画布预览</div>
    ${localCanvas ? `<div class="node-side side-a"><b>A</b></div><img src="${canvasUrl("local", row.path)}" alt="本地画布">` : ""}
    ${tmsCanvas ? `<div class="node-side side-b"><b>B</b></div><img src="${canvasUrl(state.compareSource || "canvas", row.path)}" alt="TMS 画布">` : ""}
  </div>` : "";
  box.className = "inspector";
  box.innerHTML = `${preview}<div class="side-label">属性对比</div>
    <table class="compare-table"><thead><tr><th>属性</th><th><span class="source-chip a"><b>A</b></span> 本地</th><th><span class="source-chip b"><b>B</b></span> TMS</th></tr></thead><tbody>${table}</tbody></table>`;
  updateActionButtons(row);
}

function updateActionButtons(row) {
  const mutable = Boolean(state.detail?.local?.mutable);
  const set = (id, enabled) => { $(id).disabled = !enabled; };
  set("editNodeBtn", mutable && row?.local?.editable);
  set("removeNodeBtn", mutable && Boolean(row?.local));
  set("addChildBtn", mutable && Boolean(row?.local?.container));
  set("applyTmsBtn", mutable && row?.status === "changed" && row.tms && editableTypes.has(row.tms.type) && row.local?.editable);
  set("copyTmsBtn", mutable && row?.status === "tmsOnly" && row.tms && copyableTypes.has(row.tms.type));
  set("fillChildrenBtn", mutable && row?.local?.container && row?.tms?.container && copyableTypes.has(row.tms.type));
}

function expandAllDiffs() {
  comparisonRows().forEach((row) => {
    if (row.status === "same") return;
    let cursor = row.path;
    while (cursor) {
      state.expanded.add(cursor);
      cursor = parentPath(cursor);
    }
  });
  renderComparison();
}

function syncValueFields(kind, locked) {
  const vector = kind === "Vector";
  $("vectorInputs").hidden = !vector;
  $("nodeValueLabel").hidden = vector || ["SubProperty", "Null"].includes(kind);
  $("nodeType").disabled = Boolean(locked);
}

function fillValueFields(row) {
  const kind = row?.type || $("nodeType").value;
  $("nodeType").value = copyableTypes.has(kind) ? kind : "Int";
  if (kind === "Vector") {
    $("nodeX").value = row?.value?.x ?? 0;
    $("nodeY").value = row?.value?.y ?? 0;
  } else if (!["SubProperty", "Null"].includes(kind)) {
    $("nodeValue").value = row?.value == null ? "" : pretty(row.value);
  }
  syncValueFields($("nodeType").value, state.dialogMode === "edit");
}

function openNodeDialog(mode, path, seed) {
  state.dialogMode = mode;
  $("nodeType").disabled = false;
  $("nodeForm").reset();
  if (mode === "edit") {
    const parts = path.split("/");
    $("nodeDialogTitle").textContent = "修改本地节点";
    $("nodeDialogHint").textContent = `编辑 ${path} 的值；类型保持不变。`;
    $("nodeParentLabel").hidden = true;
    $("nodeParent").value = parts.slice(0, -1).join("/");
    $("nodeName").value = parts.at(-1);
    $("nodeName").readOnly = true;
    $("nodeSubmitBtn").textContent = "保存";
    fillValueFields(seed);
  } else {
    $("nodeDialogTitle").textContent = "添加本地节点";
    $("nodeDialogHint").textContent = "新节点会增量写入客户端 IMG 与服务端 XML。";
    $("nodeParentLabel").hidden = false;
    $("nodeParent").value = path || "";
    $("nodeName").readOnly = false;
    $("nodeSubmitBtn").textContent = "添加";
    fillValueFields({type: "Int", value: 0});
  }
  $("nodeDialog").showModal();
}

function handleNodeAction(act, path) {
  const row = comparisonRows().find((item) => item.path === path);
  if (act === "edit" && row?.local) openNodeDialog("edit", path, row.local);
  if (act === "add") openNodeDialog("add", path);
  if (act === "remove") removeLocalNode(path);
  if (act === "apply") copyFromTms(path, false);
  if (act === "copy") copyFromTms(path, Boolean(row?.tms?.container));
}

async function copyFromTms(path, recursive) {
  if (!state.detail.local?.mutable) return toast("没有本地技能记录，无法写入", true);
  busy(recursive ? "从 TMS 复制目录" : "从 TMS 写入节点");
  try {
    await post("/api/skill/node", {
      book: state.book, id: state.selectedId, operation: "copyFromTms",
      path, source: state.compareSource, recursive,
    });
    await openSkill(state.selectedId, state.previewSource);
    toast("已按 TMS 对照写入本地节点");
  } catch (error) {
    toast(error.message, true); ready("复制失败");
  }
}

async function removeLocalNode(path) {
  if (confirm(`确定删除本地节点 ${path} 及其子节点吗？`)) await mutateLocalNode({operation:"remove", path});
}
async function mutateLocalNode(change) {
  busy("增量修改本地节点");
  try {
    await post("/api/skill/node", {book: state.book, id: state.selectedId, ...change});
    await openSkill(state.selectedId, state.previewSource);
    toast("客户端 IMG 与服务端 XML 已同步");
  } catch (error) {
    toast(error.message, true); ready("修改失败");
  }
}

function nodeValues(kind) {
  if (kind === "Vector") return {x:Number($("nodeX").value), y:Number($("nodeY").value)};
  if (["SubProperty", "Null"].includes(kind)) return {};
  const raw = $("nodeValue").value;
  return {value: ["String", "UOL"].includes(kind) ? raw : Number(raw)};
}

document.querySelectorAll("[data-availability]").forEach((button) => button.addEventListener("click", () => {
  state.availability = button.dataset.availability;
  document.querySelectorAll("[data-availability]").forEach((item) => item.classList.toggle("active", item.dataset.availability === state.availability));
  loadSkills();
}));
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(button.dataset.close).close()));
$("jobGroup").addEventListener("change", () => { state.group = $("jobGroup").value; fillJobSelects(); state.selectedId = ""; loadSkills(); });
$("job").addEventListener("change", () => { state.book = $("job").value; state.selectedId = ""; loadSkills(); });
$("search").addEventListener("input", debounce(loadSkills, 220));
$("compareSource").addEventListener("change", () => { state.compareSource = $("compareSource").value; state.expanded = new Set(); state.treePrimed = false; renderComparison(); });
$("nodeSearch").addEventListener("input", debounce(() => { state.nodeQuery = $("nodeSearch").value; renderComparison(); }, 160));
$("diffOnly").addEventListener("change", renderComparison);
$("collapseBtn").addEventListener("click", () => { state.expanded = new Set(); state.treePrimed = true; renderComparison(); });
$("expandBtn").addEventListener("click", expandAllDiffs);
$("reloadBtn").addEventListener("click", () => openSkill(state.selectedId, state.previewSource));
$("openPreviewBtn").addEventListener("click", async () => {
  $("previewDialog").showModal();
  busy("载入预览");
  try {
    await ensurePreviewTracks();
    renderPreview();
    ready("已载入");
  } catch (error) {
    toast(error.message, true); ready("预览失败");
  }
});
$("previewDialog").addEventListener("close", stopPreview);
$("addLocalNodeBtn").addEventListener("click", () => {
  const row = selectedRow();
  const parent = row?.local?.container ? row.path : parentPath(state.selectedPath);
  openNodeDialog("add", parent);
});
$("editNodeBtn").addEventListener("click", () => handleNodeAction("edit", state.selectedPath));
$("removeNodeBtn").addEventListener("click", () => handleNodeAction("remove", state.selectedPath));
$("addChildBtn").addEventListener("click", () => handleNodeAction("add", selectedRow()?.local?.container ? state.selectedPath : parentPath(state.selectedPath)));
$("applyTmsBtn").addEventListener("click", () => handleNodeAction("apply", state.selectedPath));
$("copyTmsBtn").addEventListener("click", () => handleNodeAction("copy", state.selectedPath));
$("fillChildrenBtn").addEventListener("click", () => copyFromTms(state.selectedPath, true));
$("nodeType").addEventListener("change", () => syncValueFields($("nodeType").value, state.dialogMode === "edit"));
$("nodeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const parent = $("nodeParent").value.trim(), name = $("nodeName").value.trim(), kind = $("nodeType").value;
  const values = nodeValues(kind);
  $("nodeDialog").close();
  if (state.dialogMode === "edit") {
    await mutateLocalNode({operation:"edit", path: [parent, name].filter(Boolean).join("/"), kind, values});
  } else {
    await mutateLocalNode({operation:"add", path: parent, name, kind, values});
  }
});
$("trackSelect").addEventListener("change", () => { state.track = $("trackSelect").value; state.frame = 0; stopPreview(); renderPreview(); });
$("previewSource").addEventListener("change", () => { state.previewSource = $("previewSource").value; openSkill(state.selectedId, state.previewSource); });
$("playBtn").addEventListener("click", () => { if (state.playing) stopPreview(); else playPreview(); });
$("skillIcon").addEventListener("error", () => { $("skillIcon").style.visibility = "hidden"; });

(async function start() {
  try {
    await loadJobs();
    loadSkills().catch((error) => { toast(error.message, true); ready("载入失败"); });
  } catch (error) {
    toast(error.message, true); ready("启动失败");
  }
})();
