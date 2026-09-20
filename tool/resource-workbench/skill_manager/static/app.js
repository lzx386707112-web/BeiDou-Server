"use strict";

const apiBase = document.body.dataset.apiBase || "";
const $ = (id) => document.getElementById(id);
const copyableTypes = new Set(["Short","Int","Long","Float","Double","String","Vector","UOL","SubProperty","Null"]);
const editableTypes = new Set(["Short","Int","Long","Float","Double","String","Vector","UOL"]);
const panes = {
  local: { side:"local", group:"", book:"", query:"", catalog:[], selectedId:"", detail:null, expanded:new Set(), selectedPath:"", nodeQuery:"" },
  tms: { side:"tms", group:"", book:"", query:"", catalog:[], selectedId:"", detail:null, expanded:new Set(), selectedPath:"", nodeQuery:"", source:"" },
};
const preview = { side:"tms", track:"", playing:false, frame:0, timer:0, source:"tms" };
const opPreview = { track:"", playing:false, frame:0, timer:0 };
const op = { localPath:"", tmsBook:"", tmsId:"", tmsDetail:null, catalog:[], checked:new Set(), expanded:new Set(), nodeQuery:"", source:"" };
let jobsLocal = [];
let jobsTms = [];
let dialogMode = "add";

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
function parentPath(path) { return path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : ""; }
function typeIcon(type) {
  return ({SubProperty:"/", Canvas:"C", Vector:"V", String:"S", Int:"I", Short:"H", Long:"L", Float:"F", Double:"D", UOL:"U", Null:"·"})[type] || "?";
}
function sideValue(node) {
  if (!node) return "—";
  if (node.type === "Canvas") return `${node.value?.width || 0}×${node.value?.height || 0}`;
  if (node.type === "SubProperty") return `${node.value?.children ?? 0} 子节点`;
  return pretty(node.value) || node.type;
}
function pickTmsDetail(payload, source) {
  if (source === "ms") return payload.ms || payload.tms;
  if (source === "canvas") return payload.canvas;
  if (source === "tms") return payload.tmsImg || (payload.tmsSource === "tms" ? payload.tms : null);
  return payload.tms || payload.ms || payload.canvas;
}

function fillJobSelect(selectId, groupId, jobs, group, book) {
  const groups = [...new Set(jobs.map((job) => job.group))];
  $(groupId).innerHTML = `<option value="">全部分组</option>` + groups.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  $(groupId).value = group;
  const filtered = jobs.filter((job) => !group || job.group === group);
  $(selectId).innerHTML = filtered.map((job) => `<option value="${escapeHtml(job.id)}">${escapeHtml(job.name)} (${job.id})</option>`).join("");
  const next = filtered.some((job) => job.id === book) ? book : (filtered[0]?.id || "");
  $(selectId).value = next;
  return next;
}

function observeIcons(rootId) {
  const root = $(rootId);
  const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    const image = entry.target; image.src = image.dataset.src; observer.unobserve(image);
  }), {root, rootMargin:"180px"});
  root.querySelectorAll("img[data-src]").forEach((image) => {
    image.addEventListener("error", () => { image.style.visibility = "hidden"; }, {once:true});
    observer.observe(image);
  });
}

function renderSkillList(side) {
  const pane = panes[side];
  const listId = side === "local" ? "localSkillList" : (side === "op" ? "opTmsSkillList" : "tmsSkillList");
  const book = side === "op" ? op.tmsBook : pane.book;
  const selected = side === "op" ? op.tmsId : pane.selectedId;
  const catalog = side === "op" ? op.catalog : pane.catalog;
  $(listId).innerHTML = catalog.map((item) => {
    const iconSource = item.iconSource || (side === "local" ? "local" : "tms");
    return `<button class="item-row${item.id === selected ? " active" : ""}" type="button" data-skill-id="${item.id}">
      <img data-src="${url(`/api/skill/${book}/${item.id}/icon?source=${iconSource}`)}" alt="">
      <strong>${escapeHtml(item.name)}</strong><small>${item.id}</small>
    </button>`;
  }).join("") || `<div class="empty">没有匹配的技能</div>`;
  $(listId).querySelectorAll("[data-skill-id]").forEach((button) => button.addEventListener("click", () => {
    if (side === "op") openOpTmsSkill(button.dataset.skillId);
    else openSkill(side, button.dataset.skillId);
  }));
  observeIcons(listId);
}

function treeIndex(nodes) {
  const children = new Map([["", []]]);
  nodes.forEach((node) => {
    const parent = parentPath(node.path);
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(node.path);
    if (node.container && !children.has(node.path)) children.set(node.path, []);
  });
  children.forEach((list, key) => children.set(key, list.sort((a, b) => a.localeCompare(b, undefined, {numeric:true}))));
  return children;
}

function visiblePaths(nodes, expanded, query) {
  const q = (query || "").trim().toLowerCase();
  const children = treeIndex(nodes);
  const keep = new Set();
  if (q) {
    nodes.forEach((node) => {
      if (!`${node.path} ${node.type} ${pretty(node.value)}`.toLowerCase().includes(q)) return;
      let cursor = node.path;
      while (cursor) { keep.add(cursor); cursor = parentPath(cursor); }
      keep.add("");
    });
  }
  const output = [];
  const visit = (parent, depth) => {
    for (const path of children.get(parent) || []) {
      if (q && !keep.has(path)) continue;
      output.push({path, depth});
      if ((expanded.has(path) || q) && children.has(path)) visit(path, depth + 1);
    }
  };
  visit("", 0);
  return {paths: output, children};
}

function renderTree(side) {
  const isOp = side === "op";
  const pane = isOp ? null : panes[side];
  const nodes = isOp ? (op.tmsDetail?.nodes || []) : (pane.detail?.nodes || []);
  const expanded = isOp ? op.expanded : pane.expanded;
  const selected = isOp ? "" : pane.selectedPath;
  const query = isOp ? op.nodeQuery : pane.nodeQuery;
  const treeId = isOp ? "opTmsTree" : (side === "local" ? "localTree" : "tmsTree");
  if (!nodes.length) {
    $(treeId).innerHTML = `<div class="empty">${isOp ? "选择 TMS 技能后显示可复制节点" : "选择技能后显示节点树"}</div>`;
    return;
  }
  const {paths, children} = visiblePaths(nodes, expanded, query);
  const byPath = new Map(nodes.map((node) => [node.path, node]));
  $(treeId).innerHTML = paths.map(({path, depth}) => {
    const node = byPath.get(path);
    const hasChildren = (children.get(path) || []).length > 0;
    const open = expanded.has(path);
    const check = isOp
      ? `<input class="node-check" type="checkbox" data-check="${escapeHtml(path)}" ${op.checked.has(path) ? "checked" : ""} ${copyableTypes.has(node.type) ? "" : "disabled"}>`
      : `<span></span>`;
    return `<div class="tree-row${path === selected ? " selected" : ""}" data-path="${escapeHtml(path)}" style="padding-left:${8 + depth * 14}px">
      <button class="twisty" type="button" data-twist="${escapeHtml(path)}" ${hasChildren ? "" : "disabled"}>${hasChildren ? (open ? "▾" : "▸") : ""}</button>
      ${check}
      <span class="node-icon">${typeIcon(node.type)}</span>
      <span class="node-name" title="${escapeHtml(path)}">${escapeHtml(node.name)}</span>
      <span class="node-value">${escapeHtml(sideValue(node))}</span>
    </div>`;
  }).join("");
  $(treeId).querySelectorAll(".twisty:not(:disabled)").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    const path = button.dataset.twist;
    if (expanded.has(path)) expanded.delete(path); else expanded.add(path);
    renderTree(side);
  }));
  $(treeId).querySelectorAll(".node-check").forEach((box) => box.addEventListener("click", (event) => {
    event.stopPropagation();
    const path = box.dataset.check;
    if (box.checked) op.checked.add(path); else op.checked.delete(path);
  }));
  $(treeId).querySelectorAll(".tree-row").forEach((row) => row.addEventListener("click", () => {
    if (isOp) {
      const path = row.dataset.path;
      if (op.checked.has(path)) op.checked.delete(path); else {
        const node = byPath.get(path);
        if (node && copyableTypes.has(node.type)) op.checked.add(path);
      }
      renderTree("op");
      return;
    }
    pane.selectedPath = row.dataset.path;
    renderTree(side);
    if (side === "local") openOpDialog(row.dataset.path);
  }));
}

function expandAll(side) {
  const nodes = side === "op" ? (op.tmsDetail?.nodes || []) : (panes[side].detail?.nodes || []);
  const expanded = side === "op" ? op.expanded : panes[side].expanded;
  nodes.forEach((node) => expanded.add(parentPath(node.path)));
  nodes.filter((node) => node.container).forEach((node) => expanded.add(node.path));
  expanded.add("");
  renderTree(side);
}

function fillTmsSourceSelect(selectId, sources, current) {
  const options = [["ms", sources.ms?.label || "TMS MS"], ["tms", sources.tms?.label || "TMS IMG"], ["canvas", sources.canvas?.label || "TMS _Canvas"]]
    .filter(([key]) => sources[key]?.exists);
  $(selectId).innerHTML = options.map(([key, label]) => `<option value="${key}">${escapeHtml(label)}</option>`).join("") || '<option value="">无 TMS</option>';
  const next = options.some(([key]) => key === current) ? current : (options[0]?.[0] || "");
  $(selectId).value = next;
  return next;
}

function currentTrack(detail, name) {
  return (detail?.preview?.tracks || []).find((track) => track.name === name) || detail?.preview?.tracks?.[0];
}

function stopPreview(target) {
  target.playing = false;
  if (target.timer) { clearTimeout(target.timer); target.timer = 0; }
  const button = target === opPreview ? $("opPlayBtn") : $("playBtn");
  button.textContent = "播放";
}

function drawPreview(canvasId, detail, target) {
  const canvas = $(canvasId);
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const track = currentTrack(detail, target.track);
  const frame = track?.frames?.[target.frame];
  if (!frame) return;
  const image = new Image();
  image.onload = () => {
    const scale = Math.min(canvas.width / Math.max(image.width, 1), canvas.height / Math.max(image.height, 1), 1);
    const width = image.width * scale, height = image.height * scale;
    ctx.drawImage(image, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height);
  };
  image.src = url(frame.url);
}

function playPreview(canvasId, detail, target, buttonId) {
  const track = currentTrack(detail, target.track);
  if (!track?.frames?.length) return;
  target.playing = true;
  $(buttonId).textContent = "暂停";
  const tick = () => {
    if (!target.playing) return;
    drawPreview(canvasId, detail, target);
    const delay = track.frames[target.frame]?.delay || 100;
    target.frame = (target.frame + 1) % track.frames.length;
    target.timer = setTimeout(tick, delay);
  };
  tick();
}

function renderTmsPreview(detail, trackSelectId, canvasId, target) {
  const tracks = detail?.preview?.tracks || [];
  $(trackSelectId).innerHTML = tracks.map((track) => `<option value="${escapeHtml(track.name)}">${escapeHtml(track.name)} (${track.frames.length})</option>`).join("") || '<option value="">无预览</option>';
  if (!tracks.some((track) => track.name === target.track)) target.track = tracks[0]?.name || "";
  $(trackSelectId).value = target.track;
  target.frame = 0;
  drawPreview(canvasId, detail, target);
}

function applyTmsJobs(jobs) {
  jobsTms = jobs || [];
  panes.tms.book = fillJobSelect("tmsJob", "tmsJobGroup", jobsTms, panes.tms.group, panes.tms.book || panes.local.book);
  $("opTmsJob").innerHTML = $("tmsJob").innerHTML;
  $("opTmsJob").value = panes.tms.book;
}

async function loadLocalJobs() {
  busy("载入本仓库职业");
  const payload = await api("/api/jobs?side=local");
  jobsLocal = payload.jobs || [];
  panes.local.book = fillJobSelect("localJob", "localJobGroup", jobsLocal, panes.local.group, panes.local.book);
  ready("本仓库职业已载入");
}

async function loadTmsJobs() {
  $("tmsSourceHint").textContent = "载入中…";
  busy("载入 TMS 职业");
  const payload = await api("/api/jobs?side=tms");
  applyTmsJobs(payload.jobs || []);
  ready("TMS 职业已载入");
}

async function loadSkills(side) {
  const pane = panes[side];
  if (!pane.book) return;
  busy(side === "local" ? "载入本仓库技能" : "载入 TMS 技能");
  try {
    const params = new URLSearchParams({job: pane.book, side, q: pane.query});
    const payload = await api(`/api/skills?${params}`);
    pane.catalog = payload.items || [];
    $(side === "local" ? "localTotal" : "tmsTotal").textContent = payload.total || 0;
    const sources = payload.sources || {};
    if (side === "local") {
      $("localSourceHint").textContent = sources.local?.exists ? "本地 IMG" : "无本地技能书";
    } else {
      $("tmsSourceHint").textContent = [sources.ms?.exists ? (sources.ms.pack || "MS") : null, sources.tms?.exists ? "TMS IMG" : null, sources.canvas?.exists ? "_Canvas" : null].filter(Boolean).join(" · ");
      pane.source = fillTmsSourceSelect("tmsSource", sources, pane.source);
    }
    renderSkillList(side);
    ready("已载入");
  } catch (error) {
    toast(error.message, true); ready("载入失败");
  }
}

async function openSkill(side, skillId) {
  const pane = panes[side];
  pane.selectedId = String(skillId);
  pane.expanded = new Set([""]);
  pane.selectedPath = "";
  busy("载入节点");
  try {
    const source = side === "local" ? "local" : (pane.source || "tms");
    const previewFlag = side === "tms" ? "&preview=1" : "";
    const payload = await api(`/api/skill/${pane.book}/${skillId}?source=${encodeURIComponent(source)}${previewFlag}`);
    pane.detail = side === "local" ? payload.local : pickTmsDetail(payload, source);
    if (side === "tms") {
      pane.detail = pane.detail || payload.tms;
      preview.source = payload.preview?.source || source;
      stopPreview(preview);
      renderTmsPreview(payload, "trackSelect", "previewCanvas", preview);
      pane.preview = payload.preview;
    }
    if (!pane.detail) throw new Error("没有可显示的技能节点");
    renderSkillList(side);
    const roots = (pane.detail.nodes || []).filter((node) => !node.path.includes("/"));
    roots.slice(0, 12).forEach((node) => pane.expanded.add(node.path));
    renderTree(side);
    if (side === "local") $("addLocalRootBtn").disabled = !payload.local?.mutable;
    ready("已载入");
  } catch (error) {
    toast(error.message, true); ready("读取失败");
  }
}

function localNode(path) {
  return (panes.local.detail?.nodes || []).find((node) => node.path === path) || null;
}

function openOpDialog(path) {
  if (!panes.local.selectedId) return toast("先选择本仓库技能", true);
  op.localPath = path;
  const node = localNode(path);
  $("opLocalPath").textContent = path || "(技能根)";
  $("opLocalMeta").innerHTML = node
    ? `<dt>类型</dt><dd>${escapeHtml(node.type)}</dd><dt>值</dt><dd>${escapeHtml(pretty(node.value) || "—")}</dd>`
    : `<dt>说明</dt><dd>技能根节点，可添加子节点</dd>`;
  const canvasBox = $("opLocalCanvas");
  if (node?.type === "Canvas") {
    canvasBox.hidden = false;
    canvasBox.innerHTML = `<img src="${url(`/api/skill/${panes.local.book}/${panes.local.selectedId}/canvas?source=local&path=${encodeURIComponent(path)}`)}" alt="本地画布">`;
  } else {
    canvasBox.hidden = true;
    canvasBox.innerHTML = "";
  }
  $("opEditBtn").disabled = !node?.editable;
  $("opRemoveBtn").disabled = !node;
  $("opAddBtn").disabled = !(node?.container || !path);
  op.tmsBook = panes.tms.book || op.tmsBook;
  $("opTmsJob").innerHTML = $("tmsJob").innerHTML;
  $("opTmsJob").value = op.tmsBook;
  $("opTmsSearch").value = "";
  op.checked = new Set();
  $("opDialog").showModal();
  loadOpTmsSkills().then(() => {
    const preferred = panes.tms.selectedId || panes.local.selectedId;
    if (preferred && op.catalog.some((item) => item.id === preferred)) openOpTmsSkill(preferred);
  });
}

async function loadOpTmsSkills() {
  if (!op.tmsBook) return;
  const params = new URLSearchParams({job: op.tmsBook, side:"tms", q: $("opTmsSearch").value.trim()});
  const payload = await api(`/api/skills?${params}`);
  op.catalog = payload.items || [];
  renderSkillList("op");
}

async function openOpTmsSkill(skillId) {
  op.tmsId = String(skillId);
  op.expanded = new Set([""]);
  $("opTmsSkillLabel").textContent = `${op.tmsBook} / ${op.tmsId}`;
  renderSkillList("op");
  busy("载入 TMS 对照");
  try {
    const source = panes.tms.source || "tms";
    const payload = await api(`/api/skill/${op.tmsBook}/${op.tmsId}?source=${encodeURIComponent(source)}&preview=1`);
    op.tmsDetail = pickTmsDetail(payload, source);
    op.source = payload.tmsSource || source;
    op.preview = payload.preview;
    stopPreview(opPreview);
    renderTmsPreview(payload, "opTrackSelect", "opPreviewCanvas", opPreview);
    const roots = (op.tmsDetail?.nodes || []).filter((node) => !node.path.includes("/"));
    roots.slice(0, 12).forEach((node) => op.expanded.add(node.path));
    const match = (op.tmsDetail?.nodes || []).find((node) => node.path === op.localPath && copyableTypes.has(node.type));
    if (match) op.checked.add(match.path);
    renderTree("op");
    ready("已载入");
  } catch (error) {
    toast(error.message, true); ready("TMS 读取失败");
  }
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
  syncValueFields($("nodeType").value, dialogMode === "edit");
}

function openNodeDialog(mode, path, seed) {
  dialogMode = mode;
  $("nodeType").disabled = false;
  $("nodeForm").reset();
  if (mode === "edit") {
    const parts = path.split("/");
    $("nodeDialogTitle").textContent = "修改本仓库节点";
    $("nodeDialogHint").textContent = `编辑 ${path} 的值；类型保持不变。`;
    $("nodeParentLabel").hidden = true;
    $("nodeParent").value = parts.slice(0, -1).join("/");
    $("nodeName").value = parts.at(-1);
    $("nodeName").readOnly = true;
    $("nodeSubmitBtn").textContent = "保存";
    fillValueFields(seed);
  } else {
    $("nodeDialogTitle").textContent = "添加本仓库节点";
    $("nodeDialogHint").textContent = "新节点会增量写入客户端 IMG 与服务端 XML。";
    $("nodeParentLabel").hidden = false;
    $("nodeParent").value = path || "";
    $("nodeName").readOnly = false;
    $("nodeSubmitBtn").textContent = "添加";
    fillValueFields({type:"Int", value:0});
  }
  $("nodeDialog").showModal();
}

function nodeValues(kind) {
  if (kind === "Vector") return {x:Number($("nodeX").value), y:Number($("nodeY").value)};
  if (["SubProperty", "Null"].includes(kind)) return {};
  const raw = $("nodeValue").value;
  return {value: ["String", "UOL"].includes(kind) ? raw : Number(raw)};
}

async function mutateLocalNode(change) {
  if (!panes.local.selectedId) return toast("没有选中的本仓库技能", true);
  busy("增量修改本仓库节点");
  try {
    await post("/api/skill/node", {book: panes.local.book, id: panes.local.selectedId, ...change});
    await openSkill("local", panes.local.selectedId);
    if ($("opDialog").open && op.localPath) openOpDialog(op.localPath);
    toast("客户端 IMG 与服务端 XML 已同步");
  } catch (error) {
    toast(error.message, true); ready("修改失败");
  }
}

async function copyChecked() {
  if (!panes.local.selectedId) return toast("没有选中的本仓库技能", true);
  if (!op.tmsId) return toast("先选择要对比的 TMS 技能", true);
  const paths = [...op.checked];
  if (!paths.length) return toast("勾选要复制的 TMS 节点", true);
  busy("从 TMS 复制节点");
  try {
    const result = await post("/api/skill/node", {
      book: panes.local.book, id: panes.local.selectedId, operation:"copyFromTms",
      paths, source: op.source || panes.tms.source, sourceBook: op.tmsBook, sourceId: op.tmsId, recursive:true,
    });
    await openSkill("local", panes.local.selectedId);
    toast(`已复制 ${result.copied} 个节点操作`);
  } catch (error) {
    toast(error.message, true); ready("复制失败");
  }
}

function visibleOpPaths() {
  const nodes = op.tmsDetail?.nodes || [];
  return visiblePaths(nodes, op.expanded, op.nodeQuery).paths.map((row) => row.path);
}

$("localJobGroup").addEventListener("change", () => {
  panes.local.group = $("localJobGroup").value;
  panes.local.book = fillJobSelect("localJob", "localJobGroup", jobsLocal, panes.local.group, panes.local.book);
  panes.local.selectedId = ""; panes.local.detail = null; renderTree("local"); loadSkills("local");
});
$("tmsJobGroup").addEventListener("change", () => {
  panes.tms.group = $("tmsJobGroup").value;
  panes.tms.book = fillJobSelect("tmsJob", "tmsJobGroup", jobsTms, panes.tms.group, panes.tms.book);
  panes.tms.selectedId = ""; panes.tms.detail = null; renderTree("tms"); loadSkills("tms");
});
$("localJob").addEventListener("change", () => { panes.local.book = $("localJob").value; panes.local.selectedId = ""; panes.local.detail = null; renderTree("local"); loadSkills("local"); });
$("tmsJob").addEventListener("change", () => { panes.tms.book = $("tmsJob").value; panes.tms.selectedId = ""; panes.tms.detail = null; renderTree("tms"); loadSkills("tms"); });
$("localSearch").addEventListener("input", debounce(() => { panes.local.query = $("localSearch").value; loadSkills("local"); }, 220));
$("tmsSearch").addEventListener("input", debounce(() => { panes.tms.query = $("tmsSearch").value; loadSkills("tms"); }, 220));
$("localNodeSearch").addEventListener("input", debounce(() => { panes.local.nodeQuery = $("localNodeSearch").value; renderTree("local"); }, 160));
$("tmsNodeSearch").addEventListener("input", debounce(() => { panes.tms.nodeQuery = $("tmsNodeSearch").value; renderTree("tms"); }, 160));
$("localCollapseBtn").addEventListener("click", () => { panes.local.expanded = new Set(); renderTree("local"); });
$("tmsCollapseBtn").addEventListener("click", () => { panes.tms.expanded = new Set(); renderTree("tms"); });
$("localExpandBtn").addEventListener("click", () => expandAll("local"));
$("tmsExpandBtn").addEventListener("click", () => expandAll("tms"));
$("tmsSource").addEventListener("change", () => {
  panes.tms.source = $("tmsSource").value;
  if (panes.tms.selectedId) openSkill("tms", panes.tms.selectedId);
});
$("addLocalRootBtn").addEventListener("click", () => {
  if (!panes.local.selectedId) return toast("先选择本仓库技能", true);
  openNodeDialog("add", "");
});
$("opEditBtn").addEventListener("click", () => {
  const node = localNode(op.localPath);
  if (node) openNodeDialog("edit", op.localPath, node);
});
$("opAddBtn").addEventListener("click", () => {
  const node = localNode(op.localPath);
  openNodeDialog("add", node?.container || !op.localPath ? op.localPath : parentPath(op.localPath));
});
$("opRemoveBtn").addEventListener("click", () => {
  if (op.localPath && confirm(`确定删除本仓库节点 ${op.localPath} 及其子节点吗？`)) mutateLocalNode({operation:"remove", path: op.localPath});
});
$("opTmsJob").addEventListener("change", () => { op.tmsBook = $("opTmsJob").value; op.tmsId = ""; op.tmsDetail = null; loadOpTmsSkills(); renderTree("op"); });
$("opTmsSearch").addEventListener("input", debounce(loadOpTmsSkills, 220));
$("opUseRightBtn").addEventListener("click", () => {
  if (!panes.tms.selectedId) return toast("右侧还没有选中 TMS 技能", true);
  op.tmsBook = panes.tms.book;
  $("opTmsJob").value = op.tmsBook;
  loadOpTmsSkills().then(() => openOpTmsSkill(panes.tms.selectedId));
});
$("opTmsNodeSearch").addEventListener("input", debounce(() => { op.nodeQuery = $("opTmsNodeSearch").value; renderTree("op"); }, 160));
$("opSelectVisible").addEventListener("change", () => {
  const nodes = new Map((op.tmsDetail?.nodes || []).map((node) => [node.path, node]));
  visibleOpPaths().forEach((path) => {
    const node = nodes.get(path);
    if (!node || !copyableTypes.has(node.type)) return;
    if ($("opSelectVisible").checked) op.checked.add(path); else op.checked.delete(path);
  });
  renderTree("op");
});
$("opCopyBtn").addEventListener("click", copyChecked);
$("trackSelect").addEventListener("change", () => { preview.track = $("trackSelect").value; preview.frame = 0; stopPreview(preview); drawPreview("previewCanvas", {preview: panes.tms.preview}, preview); });
$("playBtn").addEventListener("click", () => {
  if (preview.playing) stopPreview(preview);
  else playPreview("previewCanvas", {preview: panes.tms.preview}, preview, "playBtn");
});
$("opTrackSelect").addEventListener("change", () => { opPreview.track = $("opTrackSelect").value; opPreview.frame = 0; stopPreview(opPreview); drawPreview("opPreviewCanvas", {preview: op.preview}, opPreview); });
$("opPlayBtn").addEventListener("click", () => {
  if (opPreview.playing) stopPreview(opPreview);
  else playPreview("opPreviewCanvas", {preview: op.preview}, opPreview, "opPlayBtn");
});
$("nodeType").addEventListener("change", () => syncValueFields($("nodeType").value, dialogMode === "edit"));
$("nodeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const parent = $("nodeParent").value.trim(), name = $("nodeName").value.trim(), kind = $("nodeType").value;
  const values = nodeValues(kind);
  $("nodeDialog").close();
  if (dialogMode === "edit") {
    await mutateLocalNode({operation:"edit", path: [parent, name].filter(Boolean).join("/"), kind, values});
  } else {
    await mutateLocalNode({operation:"add", path: parent, name, kind, values});
  }
});
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(button.dataset.close).close()));
$("opDialog").addEventListener("close", () => stopPreview(opPreview));

(async function start() {
  renderTree("local");
  renderTree("tms");
  try {
    await loadLocalJobs();
    await loadSkills("local");
  } catch (error) {
    toast(error.message, true); ready("本仓库载入失败");
  }
  loadTmsJobs()
    .then(() => loadSkills("tms"))
    .catch((error) => { toast(error.message, true); ready("TMS 载入失败"); $("tmsSourceHint").textContent = "载入失败"; });
})();
