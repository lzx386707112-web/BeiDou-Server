"use strict";

const apiBase = document.body.dataset.apiBase || "";
const $ = (id) => document.getElementById(id);
const state = {
  catalog: {quests: [], regions: [], npcs: []},
  quest: null,
  selectedId: "",
  items: {checkStart: [], checkComplete: [], actStart: [], actComplete: []},
  mobs: {checkStart: [], checkComplete: []},
  requirements: [],
  itemNames: new Map(),
  mobNames: new Map(),
  dropAudit: {available: true, reason: "", items: {}},
  dropLookup: new Set(),
  picker: null,
  scripts: new Map(),
};

const itemGroups = [
  ["checkStart", "接取条件物品"], ["checkComplete", "完成条件物品"],
  ["actStart", "接取时物品变化"], ["actComplete", "完成奖励物品"],
];
const mobGroups = [
  ["checkStart", "接取条件怪物"], ["checkComplete", "完成所需击杀"],
];

function url(path) { return `${apiBase}${path}`; }
function escapeHtml(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;"); }
function value(id) { return $(id).value.trim(); }
function nullable(id) { const raw = value(id); return raw === "" ? null : Number(raw); }
function setValue(id, next) { $(id).value = next ?? ""; }
function setBusy(text = "处理中") { $("saveState").textContent = text; $("saveState").className = "state busy"; }
function setReady(text = "已同步") { $("saveState").textContent = text; $("saveState").className = "state"; }
function setError(text = "操作失败") { $("saveState").textContent = text; $("saveState").className = "state error"; }

async function api(path, options = {}) {
  const response = await fetch(url(path), options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) throw new Error(payload.reason || `HTTP ${response.status}`);
  return payload;
}
function post(path, body) { return api(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)}); }

let toastTimer;
function toast(message, error = false) {
  const box = $("toast"); box.textContent = message; box.classList.toggle("error", error); box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, error ? 6000 : 3000);
}
function debounce(fn, delay) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); }; }

async function loadCatalog(keepSelection = true) {
  const params = new URLSearchParams({q: value("questSearch"), region: value("regionFilter"), npc: value("npcFilter")});
  const payload = await api(`/api/catalog?${params}`);
  const firstLoad = state.catalog.regions.length === 0;
  state.catalog = payload;
  if (firstLoad) {
    $("regionFilter").innerHTML = '<option value="">全部地区</option>' + payload.regions.map((row) => `<option value="${row.id}">${escapeHtml(row.name)} (${row.count})</option>`).join("");
    $("npcFilter").innerHTML = '<option value="">全部 NPC</option>' + payload.npcs.map((row) => `<option value="${row.id}">${escapeHtml(row.name)} · ${row.id} (${row.count})</option>`).join("");
  }
  renderQuestList();
  if (!keepSelection && payload.quests.length) await openQuest(payload.quests[0].id);
}

function renderQuestList() {
  $("questCount").textContent = state.catalog.total;
  $("listEmpty").hidden = state.catalog.quests.length > 0;
  $("questList").innerHTML = state.catalog.quests.map((quest) => `
    <button class="quest-row${quest.id === state.selectedId ? " active" : ""}" type="button" data-quest-id="${quest.id}">
      <code>${quest.id}</code><strong>${escapeHtml(quest.name)}</strong>
      <small>${escapeHtml(quest.town || quest.startNpcName || "未定位")}${quest.levelMin != null ? ` · Lv.${quest.levelMin}+` : ""}</small>
    </button>`).join("");
  document.querySelectorAll("[data-quest-id]").forEach((button) => button.addEventListener("click", () => openQuest(button.dataset.questId)));
}

async function openQuest(questId) {
  setBusy("载入任务");
  try {
    const payload = await api(`/api/quest/${questId}`);
    state.quest = payload.quest; state.selectedId = questId;
    state.items = structuredClone(payload.quest.items);
    state.mobs = structuredClone(payload.quest.mobs || {checkStart: [], checkComplete: []});
    mobGroups.flatMap(([key]) => state.mobs[key] || []).forEach((mob) => state.mobNames.set(String(mob.id), mob.name));
    state.requirements = structuredClone(payload.quest.requirements || []);
    state.dropAudit = {available: true, reason: "", items: {}}; state.dropLookup.clear();
    buildScriptMap(payload.quest);
    fillForm(payload.quest); renderRequirements(); renderItems(); renderMobs(); renderScripts(); renderQuestList();
    $("editorEmpty").hidden = true; $("editor").hidden = false;
    setReady("已载入");
  } catch (error) { setError(); toast(error.message, true); }
}

function fillForm(quest) {
  $("questIdBadge").textContent = quest.questId; $("questTitle").textContent = quest.name || "未命名任务";
  $("questMeta").textContent = `${quest.startNpcName || "无起始 NPC"} → ${quest.endNpcName || "无结束 NPC"}`;
  ["name", "area", "levelMin", "levelMax", "parent", "order", "nextQuest", "rewardExp", "rewardMeso", "contentStart", "contentProgress", "contentComplete", "dialogStart", "dialogComplete"].forEach((id) => setValue(id, quest[id]));
  setValue("locationLabel", `${quest.regionName || "未定位"}${quest.town && quest.town !== "(未知街道)" ? ` · ${quest.town}` : ""}`);
  setValue("startNpc", quest.startNpc); setValue("endNpc", quest.endNpc);
  $("startNpcLabel").textContent = quest.startNpc ? `${quest.startNpcName} (${quest.startNpc})` : "-";
  $("endNpcLabel").textContent = quest.endNpc ? `${quest.endNpcName} (${quest.endNpc})` : "-";
  renderNpcMaps("startNpcMaps", quest.startNpcMaps || []);
  renderNpcMaps("endNpcMaps", quest.endNpcMaps || []);
  setNpcPreview("startNpcPreview", quest.startNpc);
  setNpcPreview("endNpcPreview", quest.endNpc);
  renderQuestChain(quest);
  Object.entries(quest.raw).forEach(([name, raw]) => setValue(`raw${name}`, raw));
}

function renderNpcMaps(elementId, maps) {
  $(elementId).innerHTML = maps.length ? maps.map((map) => {
    const location = map.street && map.street !== "(未知街道)" ? `${map.street} · ` : "";
    return `<span title="${escapeHtml(`${map.regionName} · ${map.street}`)}">${escapeHtml(location)}${escapeHtml(map.name)} <code>${map.id}</code></span>`;
  }).join("") : '<span class="unknown">未在地图 life 节点中找到</span>';
}

function setNpcPreview(elementId, npcId) {
  const image = $(elementId);
  image.hidden = !npcId;
  image.dataset.npcId = npcId || "";
  image.dataset.fallback = "";
  if (npcId) image.src = url(`/api/npc/${npcId}/preview`);
}

function renderQuestChain(quest) {
  const rows = quest.chain || [];
  $("questChain").hidden = !quest.parent;
  $("questChainName").textContent = quest.parent || "";
  $("questChainList").innerHTML = rows.map((row) => `
    <button type="button" class="chain-row${row.id === quest.questId ? " active" : ""}" data-chain-quest-id="${row.id}">
      <code>${row.order ?? "-"}</code><span><strong>${escapeHtml(row.name)}</strong><small>${row.id}${row.town ? ` · ${escapeHtml(row.town)}` : ""}</small><em>${escapeHtml(requirementSummary(row.requirements))}</em></span>
    </button>`).join("");
  document.querySelectorAll("[data-chain-quest-id]").forEach((button) => button.addEventListener("click", () => openChainQuest(button.dataset.chainQuestId)));
}

function requirementStateLabel(stateValue) { return ({0: "未开始", 1: "进行中", 2: "已完成"})[stateValue] || `状态 ${stateValue}`; }
function requirementSummary(rows = []) {
  if (!rows.length) return "无前置任务";
  return rows.map((row) => `需${requirementStateLabel(row.state)}：${row.name || row.id} (${row.id})`).join(" · ");
}

function renderRequirements() {
  $("requirementList").innerHTML = state.requirements.map((row, index) => `
    <div class="requirement-row">
      <label>任务 ID<input type="number" value="${escapeHtml(row.id)}" data-requirement-id="${index}"></label>
      <label>要求状态<select data-requirement-state="${index}">
        <option value="0"${Number(row.state) === 0 ? " selected" : ""}>未开始</option>
        <option value="1"${Number(row.state) === 1 ? " selected" : ""}>进行中</option>
        <option value="2"${Number(row.state) === 2 ? " selected" : ""}>已完成</option>
      </select></label>
      <button type="button" data-remove-requirement="${index}" title="移除" aria-label="移除">×</button>
    </div>`).join("") || '<div class="empty">无前置任务条件</div>';
  document.querySelectorAll("[data-requirement-id]").forEach((input) => input.addEventListener("input", () => {
    state.requirements[Number(input.dataset.requirementId)].id = input.value.trim();
  }));
  document.querySelectorAll("[data-requirement-state]").forEach((select) => select.addEventListener("change", () => {
    state.requirements[Number(select.dataset.requirementState)].state = Number(select.value);
  }));
  document.querySelectorAll("[data-remove-requirement]").forEach((button) => button.addEventListener("click", () => {
    state.requirements.splice(Number(button.dataset.removeRequirement), 1); renderRequirements();
  }));
}

async function openChainQuest(questId) {
  setValue("regionFilter", ""); setValue("npcFilter", ""); setValue("questSearch", questId);
  await loadCatalog();
  await openQuest(questId);
  const row = [...document.querySelectorAll("[data-quest-id]")].find((button) => button.dataset.questId === questId);
  row?.scrollIntoView({block: "center"});
}

function basicPayload() {
  return {
    questId: state.selectedId, name: value("name"), area: nullable("area"),
    contentStart: value("contentStart"), contentProgress: value("contentProgress"), contentComplete: value("contentComplete"),
    parent: value("parent"), order: nullable("order"), startNpc: nullable("startNpc"), endNpc: nullable("endNpc"),
    levelMin: nullable("levelMin"), levelMax: nullable("levelMax"), nextQuest: nullable("nextQuest"),
    rewardExp: nullable("rewardExp"), rewardMeso: nullable("rewardMeso"), dialogStart: value("dialogStart"), dialogComplete: value("dialogComplete"),
    items: state.items, mobs: state.mobs,
    requirements: state.requirements.map((row) => ({id: row.id, state: Number(row.state)})),
  };
}

async function saveQuest() {
  setBusy("验证并同步"); $("saveBtn").disabled = true;
  try {
    const payload = await post("/api/quest/save", basicPayload());
    state.quest = payload.quest; state.items = structuredClone(payload.quest.items); state.mobs = structuredClone(payload.quest.mobs || {checkStart: [], checkComplete: []}); state.requirements = structuredClone(payload.quest.requirements || []); buildScriptMap(payload.quest);
    fillForm(payload.quest); renderRequirements(); renderItems(); renderMobs(); renderScripts(); await loadCatalog(); setReady(); toast("客户端 IMG 与服务端 XML 已同步");
  } catch (error) { setError(); toast(error.message, true); }
  finally { $("saveBtn").disabled = false; }
}

async function saveRaw() {
  setBusy("验证原始记录");
  try {
    const raw = {}; ["QuestInfo", "Check", "Act", "Say"].forEach((name) => { raw[name] = value(`raw${name}`); });
    const payload = await post("/api/quest/raw", {questId: state.selectedId, raw});
    state.quest = payload.quest; state.items = structuredClone(payload.quest.items); state.mobs = structuredClone(payload.quest.mobs || {checkStart: [], checkComplete: []}); state.requirements = structuredClone(payload.quest.requirements || []); buildScriptMap(payload.quest);
    fillForm(payload.quest); renderRequirements(); renderItems(); renderMobs(); renderScripts(); await loadCatalog(); setReady(); toast("四条任务记录已增量替换");
  } catch (error) { setError(); toast(error.message, true); }
}

async function deleteQuest() {
  if (!state.selectedId || !confirm(`确定删除任务 ${state.selectedId} 的 QuestInfo、Check、Act、Say 记录吗？\n脚本不会自动删除。`)) return;
  setBusy("删除任务");
  try {
    await post("/api/quest/delete", {questId: state.selectedId, confirm: state.selectedId});
    state.selectedId = ""; state.quest = null; $("editor").hidden = true; $("editorEmpty").hidden = false;
    await loadCatalog(); setReady(); toast("任务四件套已删除，关联脚本已保留");
  } catch (error) { setError(); toast(error.message, true); }
}

function itemName(itemId) { return state.itemNames.get(String(itemId)) || `物品 ${itemId}`; }
function iconUrl(itemId) { return url(`/api/item/${itemId}/icon`); }
function chanceLabel(chance) { const percent = Number(chance) / 10000; return `${percent.toFixed(percent < 1 ? 2 : percent < 10 ? 1 : 0)}%`; }
function dropAuditHtml(itemId) {
  const audit = state.dropAudit.items[String(itemId)];
  if (!audit) return '<div class="drop-state pending">查询掉落...</div>';
  if (!state.dropAudit.available) return `<div class="drop-state unavailable" title="${escapeHtml(state.dropAudit.reason)}">无法读取掉落表</div>`;
  const labels = {available: `本任务可掉落 · ${audit.drops.filter((drop) => drop.usable).length} 个来源`, otherQuest: "仅其他任务可掉落", missing: "缺失掉落 · 没有怪物配置"};
  const sources = audit.drops.slice(0, 6).map((drop) => {
    const quest = drop.questId === 0 ? "不限任务" : `任务 ${drop.questId}`;
    const name = drop.source === "mob" ? `${drop.dropperName} (${drop.dropperId})` : drop.dropperName;
    return `<span class="drop-source${drop.usable ? "" : " foreign"}" title="${escapeHtml(name)} · ${chanceLabel(drop.chance)} · ${quest}"><b>${escapeHtml(name)}</b><small>${chanceLabel(drop.chance)} · ${quest}</small></span>`;
  }).join("");
  const more = audit.drops.length > 6 ? `<span class="drop-more">另有 ${audit.drops.length - 6} 个来源</span>` : "";
  return `<div class="drop-state ${audit.status}">${labels[audit.status]}</div><div class="drop-sources">${sources}${more}</div>`;
}
function attachIconFallback(root = document) {
  root.querySelectorAll("img[data-item-icon]").forEach((img) => img.addEventListener("error", () => {
    if (!img.dataset.fallback) { img.dataset.fallback = "1"; img.src = `https://maplestory.io/api/GMS/83/item/${img.dataset.itemIcon}/icon`; }
    else img.style.visibility = "hidden";
  }, {once: false}));
}

function renderItems() {
  $("itemGroups").innerHTML = itemGroups.map(([key, label]) => `
    <section class="item-group"><div class="item-group-head"><h3>${label}</h3><button type="button" data-add-item="${key}">＋ 添加物品</button></div>
    <div class="item-list">${(state.items[key] || []).map((item, index) => {
      const id = item.values.id || 0; const count = item.values.count ?? 1;
      return `<div class="item-row"><img data-item-icon="${id}" src="${iconUrl(id)}" alt=""><div class="item-detail"><strong>${escapeHtml(itemName(id))}</strong><small>${id}</small>${dropAuditHtml(id)}</div><label>数量<input type="number" value="${count}" data-item-count="${key}:${index}"></label><button type="button" data-remove-item="${key}:${index}" title="移除" aria-label="移除">×</button></div>`;
    }).join("") || '<div class="empty">未配置物品</div>'}</div></section>`).join("");
  attachIconFallback($("itemGroups"));
  document.querySelectorAll("[data-add-item]").forEach((button) => button.addEventListener("click", () => openItemPicker(button.dataset.addItem)));
  document.querySelectorAll("[data-remove-item]").forEach((button) => button.addEventListener("click", () => { const [key, raw] = button.dataset.removeItem.split(":"); state.items[key].splice(Number(raw), 1); renderItems(); }));
  document.querySelectorAll("[data-item-count]").forEach((input) => input.addEventListener("change", () => { const [key, raw] = input.dataset.itemCount.split(":"); state.items[key][Number(raw)].values.count = Number(input.value); }));
  hydrateItemNames();
  hydrateDropAudit();
}

function mobPreviewUrl(mobId) { return url(`/api/mob/${mobId}/preview`); }
function renderMobs() {
  $("mobGroups").innerHTML = mobGroups.map(([key, label]) => `
    <section class="mob-group"><div class="item-group-head"><h3>${label}</h3><button type="button" data-add-mob="${key}">＋ 添加怪物</button></div>
    <div class="mob-list">${(state.mobs[key] || []).map((mob, index) => {
      const id = String(mob.id || ""); const name = mob.name || state.mobNames.get(id) || `怪物 ${id}`;
      return `<div class="mob-row"><img data-mob-preview src="${mobPreviewUrl(id)}" alt=""><div class="item-detail"><strong>${escapeHtml(name)}</strong><small>${escapeHtml(id)}</small></div><label>击杀数<input type="number" min="1" value="${mob.count ?? 1}" data-mob-count="${key}:${index}"></label><button type="button" data-remove-mob="${key}:${index}" title="移除" aria-label="移除">×</button></div>`;
    }).join("") || '<div class="empty">未配置击杀条件</div>'}</div></section>`).join("");
  document.querySelectorAll("[data-mob-preview]").forEach((image) => image.addEventListener("error", () => { image.style.visibility = "hidden"; }, {once: true}));
  document.querySelectorAll("[data-add-mob]").forEach((button) => button.addEventListener("click", () => openMobPicker(button.dataset.addMob)));
  document.querySelectorAll("[data-remove-mob]").forEach((button) => button.addEventListener("click", () => { const [key, raw] = button.dataset.removeMob.split(":"); state.mobs[key].splice(Number(raw), 1); renderMobs(); }));
  document.querySelectorAll("[data-mob-count]").forEach((input) => input.addEventListener("change", () => { const [key, raw] = input.dataset.mobCount.split(":"); state.mobs[key][Number(raw)].count = Number(input.value); }));
}

async function hydrateItemNames() {
  const ids = [...new Set(itemGroups.flatMap(([key]) => (state.items[key] || []).map((row) => String(row.values.id || ""))))].filter((id) => id && !state.itemNames.has(id));
  await Promise.all(ids.map(async (id) => { try { const data = await api(`/api/items?q=${id}`); const exact = data.items.find((item) => item.id === id); if (exact) state.itemNames.set(id, exact.name); } catch (_) {} }));
  if (ids.some((id) => state.itemNames.has(id))) renderItems();
}

async function hydrateDropAudit() {
  const ids = [...new Set(itemGroups.flatMap(([key]) => (state.items[key] || []).map((row) => String(row.values.id || ""))))]
    .filter((id) => id && !state.dropAudit.items[id] && !state.dropLookup.has(id));
  if (!ids.length || !state.selectedId) return;
  ids.forEach((id) => state.dropLookup.add(id));
  try {
    const data = await api(`/api/item-drops?questId=${encodeURIComponent(state.selectedId)}&ids=${ids.join(",")}`);
    state.dropAudit.available = data.dropAudit.available; state.dropAudit.reason = data.dropAudit.reason;
    Object.assign(state.dropAudit.items, data.dropAudit.items);
  } catch (error) {
    state.dropAudit.available = false; state.dropAudit.reason = error.message;
    ids.forEach((id) => { state.dropAudit.items[id] = {status: "unavailable", drops: []}; });
  } finally {
    ids.forEach((id) => state.dropLookup.delete(id)); renderItems();
  }
}

function openItemPicker(group) { state.picker = {type: "item", group}; $("pickerTitle").textContent = "选择任务物品"; $("pickerSearch").value = ""; $("pickerDialog").showModal(); searchPicker(); }
function openMobPicker(group) { state.picker = {type: "mob", group}; $("pickerTitle").textContent = "选择击杀怪物"; $("pickerSearch").value = ""; $("pickerDialog").showModal(); searchPicker(); }
function openNpcPicker(inputId) { state.picker = {type: "npc", inputId}; $("pickerTitle").textContent = "选择 NPC"; $("pickerSearch").value = ""; $("pickerDialog").showModal(); searchPicker(); }

async function searchPicker() {
  const query = value("pickerSearch").toLowerCase();
  if (state.picker?.type === "npc") {
    const rows = state.catalog.npcs.filter((row) => !query || row.id.includes(query) || row.name.toLowerCase().includes(query)).slice(0, 100);
    $("pickerResults").innerHTML = rows.map((row) => `<button class="picker-item" type="button" data-pick-value="${row.id}"><img src="https://maplestory.io/api/GMS/83/npc/${row.id}/icon" alt=""><strong>${escapeHtml(row.name)}</strong><small>${row.id} · ${row.count} 个任务</small></button>`).join("");
  } else if (state.picker?.type === "mob") {
    const data = await api(`/api/mobs?q=${encodeURIComponent(query)}`);
    data.mobs.forEach((mob) => state.mobNames.set(mob.id, mob.name));
    $("pickerResults").innerHTML = data.mobs.map((mob) => `<button class="picker-item" type="button" data-pick-value="${mob.id}"><img data-mob-preview src="${mobPreviewUrl(mob.id)}" alt=""><strong>${escapeHtml(mob.name)}</strong><small>${mob.id}</small></button>`).join("");
    document.querySelectorAll("#pickerResults [data-mob-preview]").forEach((image) => image.addEventListener("error", () => { image.style.visibility = "hidden"; }, {once: true}));
  } else {
    const data = await api(`/api/items?q=${encodeURIComponent(query)}`);
    data.items.forEach((item) => state.itemNames.set(item.id, item.name));
    $("pickerResults").innerHTML = data.items.map((item) => `<button class="picker-item" type="button" data-pick-value="${item.id}"><img data-item-icon="${item.id}" src="${iconUrl(item.id)}" alt=""><strong>${escapeHtml(item.name)}</strong><small>${item.id} · ${item.category}</small></button>`).join("");
    attachIconFallback($("pickerResults"));
  }
  document.querySelectorAll("[data-pick-value]").forEach((button) => button.addEventListener("click", () => selectPickerValue(button.dataset.pickValue)));
}

function selectPickerValue(selected) {
  if (state.picker.type === "npc") setValue(state.picker.inputId, selected);
  else if (state.picker.type === "mob") state.mobs[state.picker.group].push({id: selected, count: 1, name: state.mobNames.get(selected) || selected});
  else state.items[state.picker.group].push({values: {id: Number(selected), count: 1}});
  $("pickerDialog").close();
  if (state.picker.type === "mob") renderMobs(); else renderItems();
}

function buildScriptMap(quest) {
  state.scripts.clear();
  state.scripts.set(`quest:${quest.questId}`, quest.questScript);
  quest.npcScripts.forEach((script) => state.scripts.set(`npc:${script.id}`, script));
}
function renderScripts() {
  const select = $("scriptTarget"); const current = select.value;
  select.innerHTML = [...state.scripts.entries()].map(([key, script]) => `<option value="${key}">${script.kind === "quest" ? "任务" : "NPC"} ${script.id}</option>`).join("");
  if (state.scripts.has(current)) select.value = current;
  showScript();
}
function showScript() {
  const script = state.scripts.get(value("scriptTarget")); if (!script) return;
  const locale = value("scriptLocale"); const selected = script[locale];
  $("scriptEditor").value = selected.content || ""; $("scriptPath").textContent = `${locale === "main" ? "scripts" : "scripts-zh-CN"}/${script.kind}/${script.id}.js${selected.exists ? "" : " · 新文件"}`;
}
async function saveScript(remove = false) {
  const script = state.scripts.get(value("scriptTarget")); if (!script) return;
  if (remove && !confirm(`确定删除 ${script.kind}/${script.id}.js 吗？`)) return;
  setBusy(remove ? "删除脚本" : "保存脚本");
  try {
    const payload = await post("/api/script", {kind: script.kind, id: script.id, locale: value("scriptLocale"), content: $("scriptEditor").value, delete: remove, confirm: remove ? script.id : ""});
    state.scripts.set(`${script.kind}:${script.id}`, payload.script); renderScripts(); setReady(); toast(remove ? "脚本已删除" : "脚本已保存");
  } catch (error) { setError(); toast(error.message, true); }
}

document.querySelectorAll(".editor-tabs button").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".editor-tabs button").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".tab-content").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === button.dataset.tab));
}));
document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => $(button.dataset.closeDialog).close()));
document.querySelectorAll("[data-pick-npc]").forEach((button) => button.addEventListener("click", () => openNpcPicker(button.dataset.pickNpc)));
$("regionFilter").addEventListener("change", () => loadCatalog()); $("npcFilter").addEventListener("change", () => loadCatalog());
$("questSearch").addEventListener("input", debounce(() => loadCatalog(), 220)); $("pickerSearch").addEventListener("input", debounce(searchPicker, 180));
$("saveBtn").addEventListener("click", saveQuest); $("saveRawBtn").addEventListener("click", saveRaw); $("deleteBtn").addEventListener("click", deleteQuest); $("reloadBtn").addEventListener("click", () => openQuest(state.selectedId));
$("addRequirementBtn").addEventListener("click", () => { state.requirements.push({id: "", state: 2}); renderRequirements(); });
$("createBtn").addEventListener("click", () => $("createDialog").showModal());
$("createForm").addEventListener("submit", async (event) => {
  event.preventDefault(); setBusy("创建任务");
  try {
    const body = {questId: value("newQuestId"), name: value("newQuestName"), startNpc: value("newStartNpc") || null, endNpc: value("newEndNpc") || null, items: {}};
    const payload = await post("/api/quest/create", body); $("createDialog").close(); await loadCatalog(); await openQuest(payload.quest.questId); toast("任务四件套已创建");
  } catch (error) { setError(); toast(error.message, true); }
});
$("scriptTarget").addEventListener("change", showScript); $("scriptLocale").addEventListener("change", showScript);
$("saveScriptBtn").addEventListener("click", () => saveScript(false)); $("deleteScriptBtn").addEventListener("click", () => saveScript(true));
document.querySelectorAll("[data-npc-preview]").forEach((image) => image.addEventListener("error", () => {
  if (!image.dataset.fallback && image.dataset.npcId) {
    image.dataset.fallback = "1";
    image.src = `https://maplestory.io/api/GMS/83/npc/${image.dataset.npcId}/icon`;
  } else image.hidden = true;
}));

loadCatalog(false).catch((error) => { setError(); toast(error.message, true); });
