"use strict";

const state = {
  opened: false,
  addTypes: [],
  selectedPath: null,
  selectedNode: null,
  expanded: new Set(),
};

const $ = (selector) => document.querySelector(selector);

async function api(path, body = null) {
  const options = body === null ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const response = await fetch(path, options);
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

function setOpenPanel(visible) {
  $("#open-panel").hidden = !visible;
  document.body.classList.toggle("open-visible", visible);
}

async function refreshState() {
  const payload = await api("/api/state");
  state.opened = payload.opened;
  if (!payload.opened) return;
  state.addTypes = payload.add_types;
  $("#img-path").value = payload.img_path;
  $("#xml-path").value = payload.xml_path;
  $("#region-badge").textContent = payload.region;
  $("#img-label").textContent = payload.img_path;
  $("#xml-label").textContent = payload.xml_path;
  $("#size-label").textContent = `${formatBytes(payload.img_bytes)} · ${payload.img_sha256.slice(0, 12)}`;
  $("#file-strip").hidden = false;
  $("#empty-tree").hidden = true;
}

async function openFiles() {
  const button = $("#open-button");
  button.disabled = true;
  try {
    const payload = await api("/api/open", {
      img_path: $("#img-path").value.trim(),
      xml_path: $("#xml-path").value.trim(),
      region: $("#region").value,
    });
    state.opened = true;
    state.addTypes = payload.add_types;
    state.expanded.clear();
    state.selectedPath = null;
    await refreshState();
    setOpenPanel(false);
    await renderRoot();
    showRootDetail();
    toast("IMG 与 XML 已打开");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function suggestXml() {
  const imgPath = $("#img-path").value.trim();
  if (!imgPath || $("#xml-path").value.trim()) return;
  try {
    const payload = await api("/api/suggest-xml", { img_path: imgPath });
    if (payload.xml_path) $("#xml-path").value = payload.xml_path;
  } catch (_) {
    // A missing suggestion is normal for files outside this repository.
  }
}

function nodeRow(node) {
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
  row.append(expander, button, count);
  group.append(row);

  button.addEventListener("click", () => selectNode(node.path));
  if (node.container) {
    expander.addEventListener("click", () => toggleNode(group, node, expander));
  }
  return group;
}

async function toggleNode(group, node, expander, forceOpen = false) {
  const key = pathKey(node.path);
  let children = group.querySelector(":scope > .tree-children");
  const opening = forceOpen || !state.expanded.has(key);
  if (!opening) {
    state.expanded.delete(key);
    expander.textContent = "›";
    if (children) children.hidden = true;
    return;
  }
  state.expanded.add(key);
  expander.textContent = "⌄";
  if (!children) {
    children = document.createElement("div");
    children.className = "tree-children";
    group.append(children);
    const payload = await api("/api/children", { path: node.path });
    payload.children.forEach((child) => children.append(nodeRow(child)));
  }
  children.hidden = false;
}

async function renderRoot() {
  const tree = $("#tree");
  tree.replaceChildren();
  if (!state.opened) return;
  const payload = await api("/api/children", { path: [] });
  payload.children.forEach((node) => tree.append(nodeRow(node)));
}

function markSelected(path) {
  document.querySelectorAll(".tree-row.selected").forEach((row) => row.classList.remove("selected"));
  const target = [...document.querySelectorAll(".tree-row")]
    .find((row) => row.dataset.path === pathKey(path));
  if (target) target.classList.add("selected");
}

async function selectNode(path) {
  try {
    const payload = await api("/api/node", { path });
    state.selectedPath = path;
    state.selectedNode = payload.node;
    markSelected(path);
    renderDetail(payload.node);
  } catch (error) {
    toast(error.message, true);
  }
}

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
    x.id = "value-x";
    x.value = node.value.x;
    x.setAttribute("aria-label", "X");
    const y = document.createElement("input");
    y.type = "number";
    y.id = "value-y";
    y.value = node.value.y;
    y.setAttribute("aria-label", "Y");
    pair.append(x, y);
    return pair;
  }
  const input = document.createElement("input");
  input.id = "value-input";
  input.value = node.value ?? "";
  input.type = ["Short", "Int", "Long", "Float", "Double"].includes(node.type) ? "number" : "text";
  if (["Float", "Double"].includes(node.type)) input.step = "any";
  input.autocomplete = "off";
  return input;
}

function currentValues(node) {
  if (node.type === "Vector") {
    return { x: $("#value-x").value, y: $("#value-y").value };
  }
  return { value: $("#value-input").value };
}

function renderDetail(node) {
  $("#breadcrumbs").textContent = pathLabel(node.path);
  const detail = $("#detail");
  detail.className = "detail-content";
  detail.replaceChildren();

  const title = document.createElement("div");
  title.className = "detail-title";
  const heading = document.createElement("h2");
  heading.textContent = node.name;
  const type = document.createElement("span");
  type.className = "badge";
  type.textContent = node.type;
  title.append(heading, type);

  const grid = document.createElement("div");
  grid.className = "field-grid";
  const nameLabel = document.createElement("label");
  nameLabel.htmlFor = "node-name";
  nameLabel.textContent = "名称";
  const nameInput = document.createElement("input");
  nameInput.id = "node-name";
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
    add.addEventListener("click", () => openAddDialog(node.path));
    actions.append(add);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger-button";
  remove.textContent = "删除节点";
  remove.addEventListener("click", removeSelected);
  actions.append(remove);

  detail.append(title, grid, actions);
}

function showRootDetail() {
  state.selectedPath = [];
  state.selectedNode = null;
  $("#breadcrumbs").textContent = "IMG 根节点";
  const detail = $("#detail");
  detail.className = "detail-content";
  detail.innerHTML = "";
  const title = document.createElement("div");
  title.className = "detail-title";
  const heading = document.createElement("h2");
  heading.textContent = "IMG 根节点";
  title.append(heading);
  const add = document.createElement("button");
  add.type = "button";
  add.className = "primary-button";
  add.textContent = "新增根节点";
  add.addEventListener("click", () => openAddDialog([]));
  detail.append(title, add);
}

async function performMutation(body, successMessage) {
  const payload = await api("/api/mutate", body);
  await refreshState();
  state.expanded.clear();
  await renderRoot();
  toast(`${successMessage} · IMG ${payload.byte_delta >= 0 ? "+" : ""}${payload.byte_delta} B`);
  return payload;
}

async function applyDetail(event) {
  const node = state.selectedNode;
  if (!node) return;
  const button = event.currentTarget;
  button.disabled = true;
  try {
    let path = [...node.path];
    const newName = $("#node-name").value.trim();
    if (!newName) throw new Error("名称不能为空");
    if (newName !== node.name) {
      const renamed = await performMutation({ operation: "rename", path, name: newName }, "节点已重命名并同步");
      path = renamed.path_after;
    }
    if (node.editable) {
      await performMutation({ operation: "edit", path, values: currentValues(node) }, "节点值已修改并同步");
    }
    await selectNode(path);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function removeSelected() {
  const node = state.selectedNode;
  if (!node || !confirm(`删除节点 ${pathLabel(node.path)}？`)) return;
  try {
    await performMutation({ operation: "remove", path: node.path }, "节点已删除并同步");
    showRootDetail();
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

function openAddDialog(parentPath) {
  if (!state.opened) return;
  $("#add-parent").value = pathLabel(parentPath);
  $("#add-parent").dataset.path = pathKey(parentPath);
  $("#add-name").value = "";
  const select = $("#add-kind");
  select.replaceChildren(...state.addTypes.map((kind) => new Option(kind, kind)));
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
    const payload = await performMutation({
      operation: "add",
      path: parentPath,
      name,
      kind: $("#add-kind").value,
      values,
    }, "节点已新增并同步");
    $("#add-dialog").close();
    await selectNode(payload.path_after);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

let searchTimer = null;
async function search() {
  const query = $("#search-input").value.trim();
  const box = $("#search-results");
  if (!query) {
    box.hidden = true;
    box.replaceChildren();
    return;
  }
  try {
    const payload = await api("/api/search", { query });
    box.replaceChildren();
    payload.results.forEach((node) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-result";
      button.append(document.createTextNode(node.name + " "));
      const small = document.createElement("small");
      small.textContent = `${node.type} · ${pathLabel(node.path)}`;
      button.append(small);
      button.addEventListener("click", () => selectNode(node.path));
      box.append(button);
    });
    box.hidden = false;
  } catch (error) {
    toast(error.message, true);
  }
}

$("#open-toggle").addEventListener("click", () => setOpenPanel($("#open-panel").hidden));
$("#open-button").addEventListener("click", openFiles);
$("#img-path").addEventListener("blur", suggestXml);
$("#add-root").addEventListener("click", () => openAddDialog([]));
$("#add-kind").addEventListener("change", addValueFields);
$("#add-form").addEventListener("submit", submitAdd);
$("#add-close").addEventListener("click", () => $("#add-dialog").close());
$("#add-cancel").addEventListener("click", () => $("#add-dialog").close());
$("#search-input").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(search, 220);
});

refreshState().then(async () => {
  if (state.opened) {
    setOpenPanel(false);
    await renderRoot();
    showRootDetail();
  } else {
    setOpenPanel(true);
  }
}).catch((error) => toast(error.message, true));
