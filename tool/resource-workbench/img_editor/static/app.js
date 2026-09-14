"use strict";

/* 每个槽位（a/b）是一份独立的编辑会话：独立的树、选中节点、展开状态。 */
const panes = {
  a: newPane(),
  b: newPane(),
};

function newPane() {
  return {
    opened: false,
    addTypes: [],
    selectedPath: null,
    selectedNode: null,
    expanded: new Set(),
    imgPath: null,
    xmlPath: null,
    defaultExportRoot: "",
    diffStatus: null, // 对比模式下的 path → status 缓存
  };
}

let dualMode = false;
let syncingSelection = false;
let addTargetSlot = "a";
let exportSlot = "a";

const $ = (selector) => document.querySelector(selector);
const apiBase = document.body.dataset.apiBase || "";
const other = (slot) => (slot === "a" ? "b" : "a");

function q(slot, selector) {
  return document.querySelector(`[data-slot="${slot}"] ${selector}`);
}

async function api(path, body = null) {
  const options = body === null ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const response = await fetch(`${apiBase}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function pathKey(path) { return JSON.stringify(path); }
function pathLabel(path) { return path.length ? path.join(" / ") : "IMG 根节点"; }

let toastTimer = null;
function toast(message, error = false) {
  const box = $("#toast");
  box.textContent = message;
  box.classList.toggle("error", error);
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, error ? 6500 : 3200);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function updateLayout() {
  dualMode = panes.a.opened && panes.b.opened;
  $("#workspace").classList.toggle("dual", dualMode);
  $("#compare-badge").hidden = !dualMode;
  if (dualMode) loadDiff();
}

async function refreshState() {
  const payload = await api("/api/state");
  for (const slot of ["a", "b"]) applySlotState(slot, payload[slot]);
  updateLayout();
}

function applySlotState(slot, data) {
  const pane = panes[slot];
  pane.opened = Boolean(data.opened);
  if (!pane.opened) {
    q(slot, ".pane-file").textContent = "未打开";
    q(slot, ".pane-export-toggle").disabled = true;
    q(slot, ".pane-reload").disabled = true;
    q(slot, ".add-root").disabled = true;
    q(slot, ".empty-state").hidden = false;
    return;
  }
  pane.addTypes = data.add_types;
  pane.imgPath = data.img_path;
  pane.xmlPath = data.xml_path;
  pane.defaultExportRoot = data.default_export_root || "";
  q(slot, ".img-path").value = data.img_path;
  q(slot, ".xml-path").value = data.xml_path;
  const fileName = data.img_path.split("/").pop();
  const paneFile = q(slot, ".pane-file");
  paneFile.textContent = fileName;
  paneFile.title = data.img_path;
  const regionBadge = q(slot, ".pane-region");
  regionBadge.textContent = data.region;
  regionBadge.hidden = false;
  q(slot, ".pane-open-panel").hidden = true;
  q(slot, ".pane-export-toggle").disabled = false;
  q(slot, ".pane-reload").disabled = false;
  q(slot, ".add-root").disabled = false;
  q(slot, ".pane-size").hidden = false;
  q(slot, ".pane-size").textContent = `${formatBytes(data.img_bytes)} · ${data.img_sha256.slice(0, 12)}`;
  q(slot, ".empty-state").hidden = true;
}

async function openFiles(slot) {
  const button = q(slot, ".pane-open-button");
  button.disabled = true;
  try {
    const payload = await api("/api/open", {
      slot,
      img_path: q(slot, ".img-path").value.trim(),
      xml_path: q(slot, ".xml-path").value.trim(),
      region: q(slot, ".region").value,
    });
    const pane = panes[slot];
    pane.opened = true;
    pane.addTypes = payload.add_types;
    pane.expanded.clear();
    pane.selectedPath = null;
    await refreshState();
    await renderRoot(slot);
    showRootDetail(slot);
    toast(`${slot.toUpperCase()} 的 IMG 与 XML 已打开`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function suggestXml(slot, force = false) {
  const input = q(slot, ".img-path");
  const imgPath = input.value.trim();
  if (!imgPath || (!force && q(slot, ".xml-path").value.trim())) return;
  try {
    const payload = await api("/api/suggest-xml", { img_path: imgPath });
    if (force || payload.xml_path) q(slot, ".xml-path").value = payload.xml_path;
  } catch (_) {
    // A missing suggestion is normal for files outside this repository.
  }
}

async function pickFile(slot, kind) {
  const input = q(slot, kind === "img" ? ".img-path" : ".xml-path");
  const button = q(slot, kind === "img" ? ".pick-img" : ".pick-xml");
  button.disabled = true;
  try {
    const payload = await api("/api/pick-file", { kind, current: input.value.trim() });
    if (!payload.path) return;
    input.value = payload.path;
    if (kind === "img") await suggestXml(slot, true);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

// ── 对比（双开时加载 path → status 缓存） ──────────────────────────

async function loadDiff() {
  try {
    const payload = await api("/api/compare-slots");
    panes.a.diffStatus = payload.rows;
    panes.b.diffStatus = payload.rows;
    document.querySelectorAll(".tree").forEach((tree) => refreshTreeDiffDots(tree));
  } catch (error) {
    panes.a.diffStatus = null;
    panes.b.diffStatus = null;
    toast("对比失败：" + error.message, true);
  }
}

function refreshTreeDiffDots(treeEl) {
  const slot = treeEl.closest("[data-slot]").dataset.slot;
  treeEl.querySelectorAll(".tree-row").forEach((row) => {
    const path = JSON.parse(row.dataset.path);
    updateRowDiffDot(slot, row, path);
  });
}

const DIFF_DOT_STATUS = { same: "diff-same", changed: "diff-changed", aOnly: "diff-only", bOnly: "diff-only" };

function updateRowDiffDot(slot, row, path) {
  const pane = panes[slot];
  let dot = row.querySelector(":scope > .diff-dot");
  const status = pane.diffStatus ? pane.diffStatus[path.join("/")] : null;
  if (!status || !DIFF_DOT_STATUS[status]) {
    if (dot) dot.remove();
    return;
  }
  if (!dot) {
    dot = document.createElement("span");
    dot.className = "diff-dot";
    row.append(dot);
  }
  dot.classList.add(DIFF_DOT_STATUS[status]);
  const labels = { same: "一致", changed: "已修改", aOnly: "仅 A", bOnly: "仅 B" };
  dot.title = labels[status];
}

// ── 树 ────────────────────────────────────────────────────────────

function nodeRow(slot, node) {
  const group = document.createElement("div");
  group.className = "tree-group";
  const row = document.createElement("div");
  row.className = "tree-row";
  row.dataset.path = pathKey(node.path);

  const expander = document.createElement("button");
  expander.type = "button";
  expander.className = `tree-expander${node.container ? "" : " empty"}`;
  expander.textContent = node.container ? "›" : "·";
  expander.setAttribute("aria-label", node.container ? "展开节点" : "叶节点");

  const button = document.createElement("button");
  button.type = "button";
  button.className = "tree-node";
  button.title = pathLabel(node.path);
  const chip = document.createElement("span");
  chip.className = "type-chip";
  chip.textContent = node.type;
  button.append(chip, document.createTextNode(node.name));

  const count = document.createElement("span");
  count.className = "type-chip";
  count.textContent = node.container ? String(node.child_count) : "";
  const compat = node.compat && node.compat.status !== "ok" ? node.compat.status : "";
  if (compat) {
    const dot = document.createElement("span");
    dot.className = `compat-dot compat-${compat}`;
    dot.title = node.compat.label + "：" + node.compat.reason;
    count.append(dot);
  }
  row.append(expander, button, count);
  updateRowDiffDot(slot, row, node.path);
  group.append(row);

  button.addEventListener("click", () => selectNode(slot, node.path));
  if (node.container) {
    expander.addEventListener("click", () => toggleNode(slot, group, node, expander));
  }
  return group;
}

async function toggleNode(slot, group, node, expander, forceOpen = false) {
  const pane = panes[slot];
  const key = pathKey(node.path);
  let children = group.querySelector(":scope > .tree-children");
  const opening = forceOpen || !pane.expanded.has(key);
  if (!opening) {
    pane.expanded.delete(key);
    expander.textContent = "›";
    if (children) children.hidden = true;
    return;
  }
  pane.expanded.add(key);
  expander.textContent = "⌄";
  if (!children) {
    children = document.createElement("div");
    children.className = "tree-children";
    group.append(children);
    const payload = await api("/api/children", { slot, path: node.path });
    payload.children.forEach((child) => children.append(nodeRow(slot, child)));
  }
  children.hidden = false;
}

async function renderRoot(slot) {
  const pane = panes[slot];
  const tree = q(slot, ".tree");
  tree.replaceChildren();
  if (!pane.opened) return;
  const payload = await api("/api/children", { slot, path: [] });
  payload.children.forEach((node) => tree.append(nodeRow(slot, node)));
}

// 重载后按之前的展开顺序重新打开树（从浅到深，保证祖先先展开、行才会存在）
async function restoreExpanded(slot, expandedPaths) {
  const sorted = [...expandedPaths].sort((a, b) => a.length - b.length);
  for (const path of sorted) {
    const row = [...q(slot, ".tree").querySelectorAll(".tree-row")].find((r) => {
      try {
        return JSON.parse(r.dataset.path).join("/") === path.join("/");
      } catch (_) {
        return false;
      }
    });
    if (!row) continue;
    const group = row.closest(".tree-group");
    const expander = group.querySelector(":scope > .tree-row .tree-expander");
    if (!expander || expander.classList.contains("empty")) continue;
    await toggleNode(slot, group, { path, container: true }, expander, true);
  }
}

// 重载：从磁盘重新读取当前文件，但保留已选文件、已展开节点与选中节点
async function reloadSlot(slot) {
  const button = q(slot, ".pane-reload");
  button.disabled = true;
  try {
    const payload = await api("/api/reload", { slot });
    // 仅更新顶栏大小/sha 徽标，不触碰已展开与选中状态
    applySlotState(slot, payload);
    const expanded = [...panes[slot].expanded].map((k) => JSON.parse(k));
    const selected = panes[slot].selectedPath;
    await renderRoot(slot);
    if (expanded.length) await restoreExpanded(slot, expanded);
    if (selected && selected.length) {
      try {
        await selectNode(slot, selected);
      } catch (_) {
        // 节点路径可能在重载后变更/移除，回退到根详情
        showRootDetail(slot);
      }
    } else {
      showRootDetail(slot);
    }
    if (dualMode) updateLayout();
    toast(`${slot.toUpperCase()} 已重新加载，当前选择已保留`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function markSelected(slot, path) {
  q(slot, ".tree").querySelectorAll(".tree-row.selected").forEach((row) => row.classList.remove("selected"));
  const target = [...q(slot, ".tree").querySelectorAll(".tree-row")]
    .find((row) => row.dataset.path === pathKey(path));
  if (target) target.classList.add("selected");
}

async function selectNode(slot, path, sync = true) {
  try {
    const payload = await api("/api/node", { slot, path });
    const pane = panes[slot];
    pane.selectedPath = path;
    pane.selectedNode = payload.node;
    markSelected(slot, path);
    renderDetail(slot, payload.node);
    if (sync && dualMode && !syncingSelection) {
      syncingSelection = true;
      try {
        await selectNode(other(slot), path, false);
      } catch (_) {
        // 对方文件没有同路径节点是正常的
      } finally {
        syncingSelection = false;
      }
    }
  } catch (error) {
    if (!sync) return; // 同步选中失败静默忽略
    toast(error.message, true);
  }
}

// ── 详情面板 ──────────────────────────────────────────────────────

function valueInput(node) {
  if (!node.editable) {
    const box = document.createElement("div");
    box.className = "readonly-value";
    box.textContent = JSON.stringify(node.value, null, 2);
    return box;
  }
  if (node.type === "Vector") {
    const pair = document.createElement("div");
    pair.className = "span-value";
    const x = document.createElement("input");
    x.type = "number";
    x.className = "value-x";
    x.value = node.value.x;
    x.setAttribute("aria-label", "X");
    const y = document.createElement("input");
    y.type = "number";
    y.className = "value-y";
    y.value = node.value.y;
    y.setAttribute("aria-label", "Y");
    pair.append(x, y);
    return pair;
  }
  const input = document.createElement("input");
  input.className = "value-input";
  input.value = node.value ?? "";
  input.type = ["Short", "Int", "Long", "Float", "Double"].includes(node.type) ? "number" : "text";
  if (["Float", "Double"].includes(node.type)) input.step = "any";
  input.autocomplete = "off";
  return input;
}

function currentValues(node) {
  const scope = `[data-slot="${currentDetailSlot}"] `;
  if (node.type === "Vector") {
    return { x: $(scope + ".value-x").value, y: $(scope + ".value-y").value };
  }
  return { value: $(scope + ".value-input").value };
}

function nodeTypeExplanation(type) {
  const explanations = {
    Canvas: `<div class="type-explain"><strong>Canvas（画布）</strong> — 存储实际图片像素数据的节点。<br>
      包含 ARGB4444 格式的 PNG 图片、尺寸（width×height）、origin（锚点坐标，用于对齐到角色脚底）、delay（帧显示时长 ms）。<br>
      <em>格式说明：</em> format=1 为 ARGB4444（标准格式），format2=0 为无额外压缩。</div>`,
    UOL: `<div class="type-explain type-explain-uol"><strong>UOL（引用）</strong> — 不存储实际数据，而是指向另一个节点的"快捷方式"。<br>
      值是一个相对路径（如 <code>../stand/0</code>），表示"去那里取数据"。<br>
      用途：多个动作共享同一帧图片，避免重复存储。客户端解析时会自动跟随引用。<br>
      <em>注意：</em> 引用目标必须存在，否则客户端崩溃。</div>`,
    SubProperty: `<div class="type-explain"><strong>SubProperty（容器）</strong> — 组织子节点的文件夹节点，本身没有值。<br>
      用于构建树形结构，如 <code>attack1/</code> 下包含帧 0~N 和 info。</div>`,
    Vector: `<div class="type-explain"><strong>Vector（向量）</strong> — 存储两个整数 (x, y) 的节点。<br>
      常用于 origin（锚点）、range（范围）、lt/rb（判定框角点）。</div>`,
    String: `<div class="type-explain"><strong>String（字符串）</strong> — 文本值节点。</div>`,
    Int: `<div class="type-explain"><strong>Int（整数）</strong> — 32 位整数值节点。</div>`,
    Short: `<div class="type-explain"><strong>Short（短整数）</strong> — 16 位整数值节点，范围 -32768~32767。</div>`,
    Long: `<div class="type-explain"><strong>Long（长整数）</strong> — 64 位整数值节点。</div>`,
    Float: `<div class="type-explain"><strong>Float（浮点数）</strong> — 单精度浮点值节点。</div>`,
    Double: `<div class="type-explain"><strong>Double（双精度浮点）</strong> — 双精度浮点值节点。</div>`,
    Null: `<div class="type-explain"><strong>Null（空节点）</strong> — 无值的占位节点。</div>`,
    Convex: `<div class="type-explain"><strong>Convex（多边形）</strong> — 存储 (x, y) 点集的节点，常用于不规则判定区域。</div>`,
    Sound: `<div class="type-explain"><strong>Sound（音效）</strong> — 存储音频数据的节点。</div>`,
    Video: `<div class="type-explain type-explain-modern"><strong>Video（视频）</strong> — <em>现代节点</em>，存储现代客户端的视频资源，旧端没有对应播放实现，不能保留。</div>`,
    RawData: `<div class="type-explain type-explain-modern"><strong>RawData（原始数据）</strong> — <em>现代节点</em>，现代运行时的原始数据块，旧端没有对应解码实现，不能保留。</div>`,
  };
  return explanations[type] || "";
}

const COMPAT_DETAIL = {
  modern: { cls: "compat-badge-modern", text: "现代节点" },
  incompatible: { cls: "compat-badge-incompatible", text: "不兼容" },
  review: { cls: "compat-badge-review", text: "待审" },
};

function canvasPreview(slot, node) {
  const box = document.createElement("div");
  box.className = "canvas-preview-box";
  const img = document.createElement("img");
  img.className = "canvas-preview";
  img.alt = `Canvas 预览 ${node.name}`;
  img.src = `${apiBase}/api/canvas?slot=${slot}&path=${encodeURIComponent(JSON.stringify(node.path))}`;
  img.addEventListener("error", () => {
    box.classList.add("canvas-preview-failed");
    box.textContent = "预览失败：Canvas 无法解码";
  });
  const meta = node.value || {};
  const caption = document.createElement("div");
  caption.className = "canvas-preview-caption";
  caption.textContent = `${meta.width ?? "?"} × ${meta.height ?? "?"} · format ${meta.format ?? "?"}/${meta.format2 ?? "?"} · ${(meta.payload_bytes ?? 0)} B`;
  box.append(img, caption);
  return box;
}

function compatBlock(compat) {
  const meta = COMPAT_DETAIL[compat.status];
  if (!meta) return null;
  const box = document.createElement("div");
  box.className = `compat-detail ${meta.cls}`;
  const head = document.createElement("strong");
  head.textContent = `${meta.text}：${compat.reason}`;
  box.append(head);
  if (compat.suggestion) {
    const tip = document.createElement("div");
    tip.className = "compat-suggestion";
    tip.textContent = "建议：" + compat.suggestion;
    box.append(tip);
  }
  return box;
}

let currentDetailSlot = "a";

function renderDetail(slot, node) {
  currentDetailSlot = slot;
  q(slot, ".breadcrumbs").textContent = pathLabel(node.path);
  const detail = q(slot, ".detail");
  detail.classList.remove("detail-empty");
  detail.classList.add("detail-content");
  detail.replaceChildren();

  const title = document.createElement("div");
  title.className = "detail-title";
  const heading = document.createElement("h2");
  heading.textContent = node.name;
  const type = document.createElement("span");
  type.className = "badge";
  type.textContent = node.type;
  title.append(heading, type);
  if (node.compat && node.compat.status !== "ok") {
    const badge = document.createElement("span");
    badge.className = `compat-badge ${COMPAT_DETAIL[node.compat.status]?.cls || ""}`;
    badge.textContent = node.compat.label;
    badge.title = node.compat.reason;
    title.append(badge);
  }

  const grid = document.createElement("div");
  grid.className = "field-grid";
  const nameLabel = document.createElement("label");
  nameLabel.textContent = "名称";
  const nameInput = document.createElement("input");
  nameInput.className = "node-name";
  nameInput.value = node.name;
  nameInput.autocomplete = "off";
  grid.append(nameLabel, nameInput);

  const valueLabel = document.createElement("label");
  valueLabel.textContent = node.editable ? (node.type === "Vector" ? "X / Y" : "值") : "节点信息";
  grid.append(valueLabel, valueInput(node));

  const actions = document.createElement("div");
  actions.className = "detail-actions";
  const apply = document.createElement("button");
  apply.type = "button";
  apply.className = "primary-button";
  apply.textContent = "应用并同步";
  apply.addEventListener("click", applyDetail);
  actions.append(apply);

  if (node.container) {
    const add = document.createElement("button");
    add.type = "button";
    add.className = "command-button";
    add.textContent = "新增子节点";
    add.addEventListener("click", () => openAddDialog(slot, node.path));
    actions.append(add);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger-button";
  remove.textContent = "删除节点";
  remove.addEventListener("click", removeSelected);
  actions.append(remove);

  detail.append(title, grid, actions);

  if (node.type === "Canvas") {
    detail.append(canvasPreview(slot, node));
  }
  const compat = node.compat && node.compat.status !== "ok" ? compatBlock(node.compat) : null;
  if (compat) detail.append(compat);
  const explain = nodeTypeExplanation(node.type);
  if (explain) {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = explain;
    detail.append(wrapper);
  }

  // UOL 联动：若选中节点本身是 UOL（引用），内联展示被引用节点的 Canvas 与说明
  if (node.type === "UOL") {
    const uolEl = document.createElement("div");
    uolEl.className = "uol-link";
    detail.append(uolEl);
    renderUolLink(slot, node, uolEl);
  }

  // MobSkill 联动：若节点所属技能引用了 mobSkillID，内联展示对应特效
  let linkEl = q(slot, ".pane-detail").querySelector(".mob-skill-link");
  if (!linkEl) {
    linkEl = document.createElement("div");
    linkEl.className = "mob-skill-link";
    linkEl.hidden = true;
    q(slot, ".pane-detail").append(linkEl);
  }
  renderMobSkillLink(slot, node, linkEl);
}

function showRootDetail(slot) {
  const pane = panes[slot];
  pane.selectedPath = [];
  pane.selectedNode = null;
  q(slot, ".breadcrumbs").textContent = "IMG 根节点";
  const detail = q(slot, ".detail");
  detail.classList.remove("detail-empty");
  detail.classList.add("detail-content");
  detail.replaceChildren();
  const title = document.createElement("div");
  title.className = "detail-title";
  const heading = document.createElement("h2");
  heading.textContent = "IMG 根节点";
  title.append(heading);
  const add = document.createElement("button");
  add.type = "button";
  add.className = "primary-button";
  add.textContent = "新增根节点";
  add.addEventListener("click", () => openAddDialog(slot, []));
  detail.append(title, add);

  const linkEl = q(slot, ".pane-detail").querySelector(".mob-skill-link");
  if (linkEl) {
    linkEl.hidden = true;
    linkEl.replaceChildren();
  }
}

// ── 修改操作 ──────────────────────────────────────────────────────

async function performMutation(slot, body, successMessage) {
  const payload = await api("/api/mutate", { slot, ...body });
  await refreshState();
  const pane = panes[slot];
  pane.expanded.clear();
  await renderRoot(slot);
  toast(`${successMessage} · IMG ${payload.byte_delta >= 0 ? "+" : ""}${payload.byte_delta} B`);
  return payload;
}

async function applyDetail(event) {
  const slot = currentDetailSlot;
  const node = panes[slot].selectedNode;
  if (!node) return;
  const button = event.currentTarget;
  button.disabled = true;
  try {
    let path = [...node.path];
    const newName = q(slot, ".node-name").value.trim();
    if (!newName) throw new Error("名称不能为空");
    if (newName !== node.name) {
      const renamed = await performMutation(slot, { operation: "rename", path, name: newName }, `${slot.toUpperCase()} 节点已重命名并同步`);
      path = renamed.path_after;
    }
    if (node.editable) {
      await performMutation(slot, { operation: "edit", path, values: currentValues(node) }, `${slot.toUpperCase()} 节点值已修改并同步`);
    }
    await selectNode(slot, path);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function removeSelected(event) {
  const slot = currentDetailSlot;
  const node = panes[slot].selectedNode;
  if (!node || !confirm(`删除节点 ${pathLabel(node.path)}？`)) return;
  try {
    await performMutation(slot, { operation: "remove", path: node.path }, `${slot.toUpperCase()} 节点已删除并同步`);
    showRootDetail(slot);
  } catch (error) {
    toast(error.message, true);
  }
}

function addValueFields() {
  const kind = $("#add-kind").value;
  const box = $("#add-value-fields");
  box.replaceChildren();
  if (["SubProperty", "Null"].includes(kind)) return;
  const fields = kind === "Vector" ? [["X", "x"], ["Y", "y"]] : [["值", "value"]];
  fields.forEach(([labelText, key]) => {
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.dataset.valueKey = key;
    input.value = "0";
    if (["String", "UOL"].includes(kind)) input.value = "";
    if (!["String", "UOL"].includes(kind)) input.type = "number";
    if (["Float", "Double"].includes(kind)) input.step = "any";
    label.append(input);
    box.append(label);
  });
}

function openAddDialog(slot, parentPath) {
  if (!panes[slot].opened) return;
  addTargetSlot = slot;
  $("#add-parent").value = `${slot.toUpperCase()} · ${pathLabel(parentPath)}`;
  $("#add-parent").dataset.path = pathKey(parentPath);
  $("#add-name").value = "";
  const select = $("#add-kind");
  select.replaceChildren(...panes[slot].addTypes.map((kind) => new Option(kind, kind)));
  addValueFields();
  $("#add-dialog").showModal();
  $("#add-name").focus();
}

async function submitAdd(event) {
  event.preventDefault();
  const name = $("#add-name").value.trim();
  if (!name) return;
  const values = {};
  document.querySelectorAll("#add-value-fields input").forEach((input) => {
    values[input.dataset.valueKey] = input.value;
  });
  const parentPath = JSON.parse($("#add-parent").dataset.path);
  const button = $("#add-submit");
  button.disabled = true;
  try {
    const payload = await performMutation(addTargetSlot, {
      operation: "add",
      path: parentPath,
      name,
      kind: $("#add-kind").value,
      values,
    }, `${addTargetSlot.toUpperCase()} 节点已新增并同步`);
    $("#add-dialog").close();
    await selectNode(addTargetSlot, payload.path_after);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

// ── 导出 ──────────────────────────────────────────────────────────

function updateExportPreview() {
  const pane = panes[exportSlot];
  const destination = $("#export-destination").value.trim() || pane.defaultExportRoot;
  const includeServer = $("#export-include-server").checked;
  const files = [];
  if (pane.imgPath) files.push(pane.imgPath);
  if (includeServer && pane.xmlPath) files.push(pane.xmlPath);
  const lines = files.map((p, i) => (
    `${files.length > 1 && i === files.length - 1 ? "└" : "├"}─ ${p}`
  ));
  $("#export-preview").textContent = `${destination}/\n${lines.join("\n")}`;
}

function openExportDialog(slot) {
  if (!panes[slot].opened) return;
  exportSlot = slot;
  $("#export-source").textContent = panes[slot].imgPath || "";
  if (!$("#export-destination").value) $("#export-destination").value = panes[slot].defaultExportRoot;
  updateExportPreview();
  $("#export-dialog").showModal();
}

async function submitExport(event) {
  event.preventDefault();
  const button = $("#export-submit");
  button.disabled = true;
  try {
    const data = await api("/api/export", {
      slot: exportSlot,
      destination: $("#export-destination").value.trim(),
      includeServer: $("#export-include-server").checked,
    });
    $("#export-dialog").close();
    const detail = data.files.map((item) => `${item.source} → ${item.target}`).join("\n");
    toast(`已复制 ${data.files.length} 个文件，保持仓库目录结构：\n${detail}`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

// ── 搜索 ──────────────────────────────────────────────────────────

let searchTimers = { a: null, b: null };
async function search(slot) {
  const query = q(slot, ".search-input").value.trim();
  const box = q(slot, ".search-results");
  if (!query) {
    box.hidden = true;
    box.replaceChildren();
    return;
  }
  try {
    const payload = await api("/api/search", { slot, query });
    box.replaceChildren();
    payload.results.forEach((node) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-result";
      button.append(document.createTextNode(node.name + " "));
      const small = document.createElement("small");
      small.textContent = `${node.type} · ${pathLabel(node.path)}`;
      button.append(small);
      button.addEventListener("click", () => {
        box.hidden = true;
        selectNode(slot, node.path);
      });
      box.append(button);
    });
    box.hidden = false;
  } catch (error) {
    toast(error.message, true);
  }
}

// ── 事件绑定 ──────────────────────────────────────────────────────

for (const slot of ["a", "b"]) {
  q(slot, ".pane-open-toggle").addEventListener("click", () => {
    const panel = q(slot, ".pane-open-panel");
    panel.hidden = !panel.hidden;
  });
  q(slot, ".pane-open-button").addEventListener("click", () => openFiles(slot));
  q(slot, ".pane-reload").addEventListener("click", () => reloadSlot(slot));
  q(slot, ".img-path").addEventListener("blur", () => suggestXml(slot));
  q(slot, ".pick-img").addEventListener("click", () => pickFile(slot, "img"));
  q(slot, ".pick-xml").addEventListener("click", () => pickFile(slot, "xml"));
  q(slot, ".pane-export-toggle").addEventListener("click", () => openExportDialog(slot));
  q(slot, ".add-root").addEventListener("click", () => openAddDialog(slot, []));
  q(slot, ".search-input").addEventListener("input", () => {
    clearTimeout(searchTimers[slot]);
    searchTimers[slot] = setTimeout(() => search(slot), 220);
  });
}

// ── MobSkill 特效浏览 ─────────────────────────────────────────────

let mobSkillCache = null;
let activeMobSkill = null;

async function loadMobSkills() {
  if (mobSkillCache) return mobSkillCache;
  try {
    const payload = await api("/api/mob-skills");
    mobSkillCache = payload.skills;
    return mobSkillCache;
  } catch (error) {
    toast("加载 MobSkill 列表失败：" + error.message, true);
    return [];
  }
}

function renderMobSkillList(skills) {
  const list = $("#mob-skill-list");
  list.replaceChildren();
  skills.forEach((skill) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mob-skill-item";
    btn.dataset.id = String(skill.id);
    btn.innerHTML = `${skill.id}<small>${skill.name}</small>`;
    btn.addEventListener("click", () => selectMobSkill(skill.id, skill.name, skill.level_count));
    list.append(btn);
  });
}

function mobSkillFrameCard(skillId, frame, kind, level) {
  const card = document.createElement("div");
  card.className = "mob-skill-frame";
  const img = document.createElement("img");
  img.src = `${apiBase}/api/mob-skill-canvas?skillId=${skillId}&level=${level}&frame=${encodeURIComponent(frame.name)}&kind=${kind}`;
  img.alt = `${kind}/${frame.name}`;
  img.addEventListener("error", () => {
    img.classList.add("mob-skill-frame-failed");
    img.alt = `${kind}/${frame.name} 解码失败`;
  });
  const cap = document.createElement("div");
  cap.className = "mob-skill-frame-caption";
  cap.textContent = `${frame.width}×${frame.height}${frame.delay ? " " + frame.delay + "ms" : ""}`;
  card.append(img, cap);
  return card;
}

function renderMobSkillSections(container, payload, skillId, level) {
  container.replaceChildren();
  let hasContent = false;
  if (payload.effect_frames.length > 0) {
    hasContent = true;
    const sec = document.createElement("div");
    sec.className = "mob-skill-section";
    sec.innerHTML = `<h4>Effect 特效 (${payload.effect_frames.length} 帧)</h4>`;
    const grid = document.createElement("div");
    grid.className = "mob-skill-frames";
    payload.effect_frames.forEach((frame) => grid.append(mobSkillFrameCard(skillId, frame, "effect", level)));
    sec.append(grid);
    container.append(sec);
  }
  if (payload.mob_frames.length > 0) {
    hasContent = true;
    const sec = document.createElement("div");
    sec.className = "mob-skill-section";
    sec.innerHTML = `<h4>Mob 覆盖图层 (${payload.mob_frames.length} 帧)</h4>`;
    const grid = document.createElement("div");
    grid.className = "mob-skill-frames";
    payload.mob_frames.forEach((frame) => grid.append(mobSkillFrameCard(skillId, frame, "mob", level)));
    sec.append(grid);
    container.append(sec);
  }
  if (Object.keys(payload.fields).length > 0) {
    hasContent = true;
    const sec = document.createElement("div");
    sec.className = "mob-skill-section";
    sec.innerHTML = "<h4>参数</h4>";
    const grid = document.createElement("div");
    grid.className = "field-grid";
    Object.entries(payload.fields).forEach(([k, v]) => {
      const label = document.createElement("label");
      label.textContent = k;
      const val = document.createElement("div");
      val.className = "readonly-value";
      val.textContent = typeof v === "object" ? JSON.stringify(v) : String(v);
      grid.append(label, val);
    });
    sec.append(grid);
    container.append(sec);
  }
  if (!hasContent) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "此技能等级无特效帧";
    container.append(empty);
  }
}

async function selectMobSkill(skillId, skillName, levelCount) {
  activeMobSkill = skillId;
  document.querySelectorAll(".mob-skill-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.id === String(skillId));
  });
  const detail = $("#mob-skill-detail");
  detail.replaceChildren();
  const info = document.createElement("div");
  info.className = "mob-skill-info";
  info.innerHTML = `<strong>${skillId} · ${skillName}</strong> — ${levelCount} 个等级`;
  detail.append(info);
  try {
    const payload = await api(`/api/mob-skill-effect?skillId=${skillId}&level=1`);
    renderMobSkillSections(detail, payload, skillId, 1);
  } catch (error) {
    const fail = document.createElement("div");
    fail.className = "empty-state";
    fail.textContent = "加载失败：" + error.message;
    detail.append(fail);
  }
}

// 选中节点时，若其所属技能引用了 MobSkill，则在详情面板内联展示对应特效
async function renderMobSkillLink(slot, node, container) {
  container.replaceChildren();
  container.hidden = true;
  let link;
  try {
    link = await api(`/api/node-mob-skill?slot=${slot}&path=${encodeURIComponent(JSON.stringify(node.path))}`);
  } catch (error) {
    return;
  }
  if (!link.found) return;
  const msid = link.mobSkillId;
  const name = link.mobSkillName;
  container.hidden = false;

  const banner = document.createElement("div");
  banner.className = "mob-skill-link-banner";
  banner.innerHTML = `<span class="mob-skill-link-icon" aria-hidden="true">⚡</span>
    <span>此技能关联 <strong>MobSkill 特效 #${msid} · ${name}</strong></span>`;
  const openBtn = document.createElement("button");
  openBtn.type = "button";
  openBtn.className = "command-button mob-skill-link-open";
  openBtn.textContent = "在特效浏览器中打开";
  openBtn.addEventListener("click", async () => {
    await openMobSkillDialog();
    await selectMobSkill(msid, name, 1);
  });
  banner.append(openBtn);
  container.append(banner);

  const hint = document.createElement("div");
  hint.className = "mob-skill-link-hint";
  hint.textContent = "对应特效的详细内容与预览：";
  container.append(hint);

  const preview = document.createElement("div");
  preview.className = "mob-skill-link-preview";
  container.append(preview);

  const loading = document.createElement("div");
  loading.className = "empty-state";
  loading.textContent = "加载特效中...";
  preview.append(loading);

  let payload;
  try {
    payload = await api(`/api/mob-skill-effect?skillId=${msid}&level=${link.previewLevel}`);
  } catch (e1) {
    try {
      payload = await api(`/api/mob-skill-effect?skillId=${msid}&level=1`);
    } catch (e2) {
      preview.replaceChildren();
      const fail = document.createElement("div");
      fail.className = "empty-state";
      fail.textContent = "加载特效失败：" + (e2.message || e1.message);
      preview.append(fail);
      return;
    }
  }
  renderMobSkillSections(preview, payload, msid, payload.level || link.previewLevel);
}

async function renderUolLink(slot, node, container) {
  container.replaceChildren();
  let data;
  try {
    data = await api(`/api/node-uol?slot=${slot}&path=${encodeURIComponent(JSON.stringify(node.path))}`);
  } catch (error) {
    return;
  }
  if (!data.isUol) return;

  const banner = document.createElement("div");
  banner.className = "uol-link-banner";
  const icon = document.createElement("span");
  icon.className = "uol-link-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "🔗";
  const text = document.createElement("span");
  banner.append(icon, text);

  if (!data.resolved) {
    text.innerHTML = `<strong>UOL 引用无法解析</strong><br>
      <span class="uol-link-reason">链接值 <code>${data.uolLink}</code> ｜ ${data.reason || ""}</span>`;
    container.append(banner);
    return;
  }

  text.innerHTML = `<strong>UOL 引用</strong> — 指向 <code>${data.targetPath}</code>（${data.targetType}）<br>
    <span class="uol-link-sub">链接值 <code>${data.uolLink}</code> ｜ 从 <code>${data.selectedPath}</code> 解析得到</span>`;
  container.append(banner);

  const explain = document.createElement("div");
  explain.className = "uol-link-explain";
  explain.textContent =
    "此节点本身不存储像素，客户端渲染时会自动跳转到上方目标节点取数据。" +
    "常用于多个动作共享同一帧图片，避免重复存储；目标节点必须存在，否则客户端崩溃。";
  container.append(explain);

  if (data.canvas) {
    const section = document.createElement("div");
    section.className = "uol-link-canvas-section";
    const h = document.createElement("h4");
    h.textContent = `被引用节点的 Canvas 预览：${data.canvas.path}`;
    section.append(h);

    const box = document.createElement("div");
    box.className = "canvas-preview-box";
    const img = document.createElement("img");
    img.className = "canvas-preview";
    img.alt = `UOL 目标 Canvas ${data.canvas.path}`;

    const canvasPathArr = data.canvas.path.split("/");
    img.src = `${apiBase}/api/canvas?slot=${slot}&path=${encodeURIComponent(JSON.stringify(canvasPathArr))}`;
    img.addEventListener("error", () => {
      box.classList.add("canvas-preview-failed");
      box.textContent = "预览失败：目标 Canvas 无法解码";
    });

    const cap = document.createElement("div");
    cap.className = "canvas-preview-caption";
    const o = data.canvas.origin ? `origin (${data.canvas.origin.x}, ${data.canvas.origin.y})` : "无 origin";
    const d = data.canvas.delay != null ? `delay ${data.canvas.delay}ms` : "无 delay";
    cap.textContent = `${data.canvas.width} × ${data.canvas.height} · ${o} · ${d}`;
    box.append(img, cap);
    section.append(box);
    container.append(section);
  } else {
    const note = document.createElement("div");
    note.className = "uol-link-note";
    note.textContent = `目标节点 ${data.targetPath}（${data.targetType}）下未找到可渲染的 Canvas 像素。`;
    container.append(note);
  }
}

async function openMobSkillDialog() {
  $("#mob-skill-dialog").showModal();
  const skills = await loadMobSkills();
  renderMobSkillList(skills);
  if (skills.length > 0 && !activeMobSkill) {
    selectMobSkill(skills[0].id, skills[0].name, skills[0].level_count);
  }
}

$("#mob-skill-btn").addEventListener("click", openMobSkillDialog);
$("#mob-skill-close").addEventListener("click", () => $("#mob-skill-dialog").close());

$("#add-kind").addEventListener("change", addValueFields);
$("#add-form").addEventListener("submit", submitAdd);
$("#add-close").addEventListener("click", () => $("#add-dialog").close());
$("#add-cancel").addEventListener("click", () => $("#add-dialog").close());
$("#export-destination").addEventListener("input", updateExportPreview);
$("#export-include-server").addEventListener("change", updateExportPreview);
$("#export-form").addEventListener("submit", submitExport);
$("#export-close").addEventListener("click", () => $("#export-dialog").close());
$("#export-cancel").addEventListener("click", () => $("#export-dialog").close());

refreshState().then(async () => {
  for (const slot of ["a", "b"]) {
    if (panes[slot].opened) {
      await renderRoot(slot);
      showRootDetail(slot);
    }
  }
}).catch((error) => toast(error.message, true));
