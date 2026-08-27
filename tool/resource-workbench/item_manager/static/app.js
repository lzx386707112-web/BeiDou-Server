"use strict";

const apiBase = document.body.dataset.apiBase || "";
const $ = (id) => document.getElementById(id);
const state = {
  availability: "missing", category: "etc", selectedId: "", catalog: [], detail: null,
  projectionNodes: [], changes: [], nodeTarget: "projection",
};
const categoryLabels = new Map();
const nodeTypeLabels = {Short:"短整数",Int:"整数",Long:"长整数",Float:"浮点",Double:"双精度",String:"字符串",Vector:"坐标",UOL:"链接",SubProperty:"目录",Null:"空值",Canvas:"画布"};
const availabilityLabels = {missing:"仅 TMS · 待迁移",both:"两边都有",all:"全部",local:"仅本地"};

function url(path) { return `${apiBase}${path}`; }
function escapeHtml(value) { return String(value ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"); }
function pretty(value) { return value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value); }
function debounce(fn, delay) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); }; }
async function api(path, options={}) { const response=await fetch(url(path),options); const payload=await response.json().catch(()=>({})); if(!response.ok||payload.ok===false)throw new Error(payload.reason||`HTTP ${response.status}`); return payload; }
function post(path, body) { return api(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}); }
let toastTimer;
const iconObserver = new IntersectionObserver((entries)=>entries.forEach((entry)=>{
  if(!entry.isIntersecting)return;
  const image=entry.target;image.src=image.dataset.src;iconObserver.unobserve(image);
}),{root:$("itemList"),rootMargin:"180px"});
function toast(message,error=false){const box=$("toast");box.textContent=message;box.classList.toggle("error",error);box.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>box.hidden=true,error?6000:3000);}
function busy(text){$("stateText").textContent=text;} function ready(text="已同步"){$("stateText").textContent=text;}
function setAvailability(value){state.availability=value;document.querySelectorAll("[data-availability]").forEach((button)=>button.classList.toggle("active",button.dataset.availability===value));}

async function loadCatalog() {
  busy("载入统一目录");
  try {
    const params=new URLSearchParams({availability:state.availability,category:state.category,q:$("search").value.trim(),limit:"500"});
    const payload=await api(`/api/catalog?${params}`);
    if(!categoryLabels.size){payload.categories.forEach((row)=>categoryLabels.set(row.id,row.name));$("category").innerHTML=payload.categories.map((row)=>`<option value="${row.id}">${escapeHtml(row.name)}</option>`).join("");$("category").value=state.category;}
    state.catalog=payload.items;$("total").textContent=payload.total;$("scopeLabel").textContent=availabilityLabels[state.availability];
    renderCatalog();ready("已载入");
  } catch(error){toast(error.message,true);ready("载入失败");}
}

function renderCatalog(){
  $("listEmpty").hidden=state.catalog.length>0;
  $("itemList").innerHTML=state.catalog.map((item)=>{
    const icon=item.iconScope?`<img data-src="${url(`/api/item/${item.iconScope}/${state.category}/${item.id}/icon`)}" alt="">`:"<span></span>";
    const badge=item.status==="missing"?'<em class="missing">待迁移</em>':item.status==="both"?'<em class="both">本地＋TMS</em>':item.status==="local"?'<em>仅本地</em>':'<em>缺少资源</em>';
    return `<button class="item-row${item.id===state.selectedId?" active":""}" type="button" data-item-id="${item.id}">${icon}<strong>${escapeHtml(item.name||`物品 ${item.id}`)}</strong><small>${item.id}${badge}</small></button>`;
  }).join("");
  document.querySelectorAll("[data-item-id]").forEach((button)=>button.addEventListener("click",()=>openItem(button.dataset.itemId)));
  iconObserver.disconnect();document.querySelectorAll(".item-row img").forEach((image)=>{image.addEventListener("error",()=>image.style.visibility="hidden",{once:true});iconObserver.observe(image);});
}

async function openItem(itemId, reset=true){
  const row=state.catalog.find((item)=>item.id===String(itemId));
  const scope=row?.tms?"tms":row?.local?"local":state.detail?.tms?"tms":"local";
  busy("生成迁移对比");
  try{
    const payload=await api(`/api/item/${scope}/${state.category}/${itemId}`);
    state.selectedId=String(itemId);state.detail=payload;
    if(reset){state.changes=[];state.projectionNodes=(payload.projection?.nodes||[]).map(cloneRow);}
    fillDetail();renderCatalog();$("detailEmpty").hidden=true;$("detail").hidden=false;ready("已载入");
  }catch(error){toast(error.message,true);ready("读取失败");}
}
function cloneRow(row){return {...row,value:row.value&&typeof row.value==="object"?{...row.value}:row.value};}

function fillDetail(){
  const payload=state.detail,local=payload.local,tms=payload.tms,selected=local||tms;
  $("itemId").textContent=selected.id;$("categoryLabel").textContent=categoryLabels.get(state.category)||state.category;
  $("availability").textContent=`本地 ${local?"✓":"—"} · TMS ${tms?"✓":"—"}`;$("itemName").textContent=(local||tms).name||`物品 ${selected.id}`;
  $("itemFile").textContent=[local?.file,tms?.file].filter(Boolean).join("  ↔  ");
  const iconScope=local?"local":"tms";$("itemIcon").src=url(`/api/item/${iconScope}/${state.category}/${selected.id}/icon`);$("itemIcon").style.visibility="visible";
  const textSource=local||tms;$("nameInput").value=textSource?.name||"";$("descInput").value=textSource?.desc||"";
  const textEditable=state.category!=="special"&&Boolean(local||tms);$("nameInput").disabled=!textEditable;$("descInput").disabled=!textEditable;
  $("saveMetadataBtn").hidden=!local;$("saveMetadataBtn").disabled=state.category==="special";
  $("metadataHint").textContent=local?"可直接保存本地文本；执行迁移时也会采用当前输入值":"当前输入值会随新物品一起迁移到客户端与服务端 String 资源";
  $("copyBtn").hidden=!tms;$("copyBtn").textContent=local?"按迁移投影更新本地":"新增到当前项目";$("copyBtn").disabled=!payload.projection||state.category==="pet";
  $("deleteBtn").hidden=!local;$("deleteBtn").disabled=state.category==="pet";
  $("addProjectionNodeBtn").disabled=!payload.projection?.mutable;$("resetProjectionBtn").disabled=!state.changes.length;
  $("addLocalNodeBtn").disabled=!local?.mutable;
  renderCompatibility();renderComparison();renderLocalNodes();renderRawTmsNodes();renderStagedCount();
}

function renderCompatibility(){
  const check=state.detail.compatibility||{safe:false,issues:[],counts:{}},counts=check.counts||{};
  $("compatBadge").textContent=state.detail.tms?(check.safe?"可兼容迁移":"存在阻断项"):"TMS 无对应物品";$("compatBadge").classList.toggle("blocked",!check.safe);
  $("compatSummary").textContent=`阻断 ${counts.blocker||0} · 转换 ${counts.convert||0} · 移除 ${counts.drop||0}`;
  $("compatIssues").innerHTML=check.issues?.length?check.issues.map((issue)=>`<div class="issue ${issue.level}"><b>${issue.level}</b><code>${escapeHtml(issue.path||"记录")}</code><span>${escapeHtml(issue.message)}</span></div>`).join(""):'<div class="empty compact">没有发现兼容问题</div>';
}

function nodeMap(rows){return new Map(rows.map((row)=>[row.path,row]));}
function comparisonRows(){
  const local=nodeMap(state.detail.local?.nodes||[]),projection=nodeMap(state.projectionNodes),rows=[];
  [...new Set([...local.keys(),...projection.keys()])].sort((a,b)=>a.split("/").length-b.split("/").length||a.localeCompare(b)).forEach((path)=>{
    const left=local.get(path),right=projection.get(path);let status=!right?"localOnly":!left?"tmsOnly":"same";
    if(left&&right&&(left.type!==right.type||pretty(left.value)!==pretty(right.value)))status="changed";
    rows.push({path,status,local:left,projection:right});
  });return rows;
}
function renderComparison(){
  const rows=comparisonRows(),counts={same:0,changed:0,tmsOnly:0,localOnly:0};rows.forEach((row)=>counts[row.status]++);
  $("diffSummary").innerHTML=[["same","相同"],["changed","值变化"],["tmsOnly","仅迁移投影"],["localOnly","仅本地"]].map(([key,label])=>`<span>${label}<b>${counts[key]}</b></span>`).join("");
  const filter=$("diffFilter").value,shown=rows.filter((row)=>!filter||row.status===filter),labels={same:"相同",changed:"变化",tmsOnly:"仅投影",localOnly:"仅本地"};
  $("diffTable").innerHTML='<div class="node-head"><span>状态</span><span>路径</span><span>类型</span><span>本地值</span><span>迁移投影值</span><span>投影操作</span></div>'+shown.map((row)=>{
    const projected=row.projection,actions=projected&&state.detail.projection?.mutable?`${projected.editable?`<button type="button" data-edit-projection="${escapeHtml(row.path)}">修改</button>`:""}<button type="button" data-remove-projection="${escapeHtml(row.path)}">移除</button>`:"";
    return `<div class="node-line ${row.status}"><span class="status">${labels[row.status]}</span><code title="${escapeHtml(row.path)}">${escapeHtml(row.path)}</code><span>${escapeHtml(row.local?.type||projected?.type||"")}</span><span class="value">${escapeHtml(pretty(row.local?.value))}</span><span class="value">${escapeHtml(pretty(projected?.value))}</span><span class="actions">${actions}</span></div>`;
  }).join("");
  document.querySelectorAll("[data-edit-projection]").forEach((button)=>button.addEventListener("click",()=>editProjectionNode(button.dataset.editProjection)));
  document.querySelectorAll("[data-remove-projection]").forEach((button)=>button.addEventListener("click",()=>removeProjectionNode(button.dataset.removeProjection)));
}

function renderLocalNodes(){
  const detail=state.detail.local;
  if(!detail){$("localNodeTable").innerHTML='<div class="empty compact">当前项目没有这个物品；迁移后会在这里生成本地节点</div>';return;}
  $("localNodeTable").innerHTML='<div class="node-head"><span>节点路径</span><span>类型</span><span>值</span><span>操作</span></div>'+detail.nodes.map((row)=>`<div class="node-line"><code>${escapeHtml(row.path)}</code><span>${escapeHtml(nodeTypeLabels[row.type]||row.type)}</span><span class="value">${escapeHtml(pretty(row.value))}</span><span class="actions">${detail.mutable&&row.editable?`<button type="button" data-edit-local="${escapeHtml(row.path)}">修改</button>`:""}${detail.mutable?`<button type="button" data-remove-local="${escapeHtml(row.path)}">删除</button>`:""}</span></div>`).join("");
  document.querySelectorAll("[data-edit-local]").forEach((button)=>button.addEventListener("click",()=>editLocalNode(button.dataset.editLocal)));
  document.querySelectorAll("[data-remove-local]").forEach((button)=>button.addEventListener("click",()=>removeLocalNode(button.dataset.removeLocal)));
}
function renderRawTmsNodes(){
  const detail=state.detail.tms;
  $("tmsNodeTable").innerHTML=!detail?'<div class="empty compact">TMS 没有对应物品</div>':'<div class="node-head"><span>节点路径</span><span>类型</span><span>值</span><span>说明</span></div>'+detail.nodes.map((row)=>`<div class="node-line"><code>${escapeHtml(row.path)}</code><span>${escapeHtml(nodeTypeLabels[row.type]||row.type)}</span><span class="value">${escapeHtml(pretty(row.value))}</span><span>只读</span></div>`).join("");
}
function renderStagedCount(){$("stagedCount").textContent=state.changes.length?`${state.changes.length} 项迁移调整待提交`:"未调整，将按兼容投影迁移";$("resetProjectionBtn").disabled=!state.changes.length;}

function editedValue(row,promptText){
  if(row.type==="Vector"){const raw=prompt(promptText,`${row.value.x},${row.value.y}`);if(raw===null)return null;const parts=raw.split(",").map(Number);if(parts.length!==2||parts.some(Number.isNaN)){toast("坐标格式应为 X,Y",true);return null;}return {values:{x:parts[0],y:parts[1]},value:{x:parts[0],y:parts[1]}};}
  const raw=prompt(promptText,pretty(row.value));if(raw===null)return null;const value=["String","UOL"].includes(row.type)?raw:Number(raw);if(typeof value==="number"&&Number.isNaN(value)){toast("请输入有效数字",true);return null;}return {values:{value},value};
}
function editProjectionNode(path){const row=state.projectionNodes.find((item)=>item.path===path);if(!row)return;const next=editedValue(row,`修改迁移投影 ${path}`);if(!next)return;row.value=next.value;state.changes.push({operation:"edit",path,values:next.values});renderComparison();renderStagedCount();}
function removeProjectionNode(path){if(!confirm(`从迁移投影中移除节点 ${path} 吗？TMS 原始资源不会改变。`))return;state.projectionNodes=state.projectionNodes.filter((row)=>row.path!==path&&!row.path.startsWith(`${path}/`));state.changes.push({operation:"remove",path});renderComparison();renderStagedCount();}
function resetProjection(){state.changes=[];state.projectionNodes=(state.detail.projection?.nodes||[]).map(cloneRow);renderComparison();renderStagedCount();}

async function editLocalNode(path){const row=state.detail.local?.nodes.find((item)=>item.path===path);if(!row)return;const next=editedValue(row,`修改本地节点 ${path}`);if(next)await mutateLocalNode({operation:"edit",path,values:next.values});}
async function removeLocalNode(path){if(confirm(`确定删除本地节点 ${path} 吗？`))await mutateLocalNode({operation:"remove",path});}
async function mutateLocalNode(change){busy("增量修改本地节点");try{await post("/api/item/node",{category:state.category,id:state.selectedId,...change});await openItem(state.selectedId);toast("客户端 IMG 与服务端 XML 已同步");}catch(error){toast(error.message,true);ready("修改失败");}}

function openNodeDialog(target){state.nodeTarget=target;$("nodeDialogTitle").textContent=target==="projection"?"添加迁移投影节点":"添加本地物品节点";$("nodeForm").reset();$("vectorInputs").hidden=true;$("nodeValueLabel").hidden=false;$("nodeDialog").showModal();}
function nodeValues(kind){if(kind==="Vector")return {x:Number($("nodeX").value),y:Number($("nodeY").value)};if(["SubProperty","Null"].includes(kind))return {};return {value:["String","UOL"].includes(kind)?$("nodeValue").value:Number($("nodeValue").value)};}
function stageAddedNode(parent,name,kind,values){
  const path=[parent,name].filter(Boolean).join("/");if(state.projectionNodes.some((row)=>row.path===path))return toast("迁移投影中已存在同名节点",true);
  if(parent){const owner=state.projectionNodes.find((row)=>row.path===parent);if(!owner||owner.type!=="SubProperty")return toast("父节点路径必须是迁移投影中的目录节点",true);}
  const value=kind==="Vector"?{x:values.x,y:values.y}:kind==="SubProperty"?{children:0}:kind==="Null"?null:values.value;
  state.projectionNodes.push({path,name,type:kind,value,depth:path.split("/").length-1,container:kind==="SubProperty",editable:Object.hasOwn(nodeTypeLabels,kind)&&!["SubProperty","Null","Canvas"].includes(kind)});
  state.changes.push({operation:"add",path:parent,name,kind,values});renderComparison();renderStagedCount();
}

async function saveMetadata(){busy("保存本地文本");try{await post("/api/item/metadata",{category:state.category,id:state.selectedId,name:$("nameInput").value,desc:$("descInput").value});await loadCatalog();await openItem(state.selectedId);toast("物品名称与描述已同步");}catch(error){toast(error.message,true);ready("保存失败");}}
async function copyItem(){
  const exists=Boolean(state.detail.local),message=exists?`按当前迁移投影更新本地物品 ${state.selectedId} 吗？`:`把 TMS 物品 ${state.selectedId} 新增到当前项目吗？`;
  if(!confirm(message))return;busy(exists?"应用迁移投影":"迁移新物品");
  try{await post("/api/item/copy",{category:state.category,id:state.selectedId,overwrite:exists,confirm:exists?state.selectedId:"",changes:state.changes,metadata:{name:$("nameInput").value,desc:$("descInput").value}});setAvailability("both");await loadCatalog();await openItem(state.selectedId);toast(exists?"本地物品已按迁移投影更新":"TMS 物品已新增到当前项目");}catch(error){toast(error.message,true);ready("迁移失败");}
}
async function deleteItem(){if(!confirm(`确定删除本地物品 ${state.selectedId} 的物品记录和名称记录吗？`))return;const confirmation=prompt("再次输入物品 ID 确认删除","");if(confirmation!==state.selectedId)return;busy("删除物品");try{await post("/api/item/delete",{category:state.category,id:state.selectedId,confirm:confirmation});state.selectedId="";state.detail=null;$("detail").hidden=true;$("detailEmpty").hidden=false;await loadCatalog();toast("本地物品已删除");}catch(error){toast(error.message,true);ready("删除失败");}}

document.querySelectorAll("[data-availability]").forEach((button)=>button.addEventListener("click",()=>{setAvailability(button.dataset.availability);state.selectedId="";loadCatalog();}));
document.querySelectorAll("[data-close]").forEach((button)=>button.addEventListener("click",()=>$(button.dataset.close).close()));
$("category").addEventListener("change",()=>{state.category=$("category").value;state.selectedId="";loadCatalog();});$("search").addEventListener("input",debounce(loadCatalog,220));$("diffFilter").addEventListener("change",renderComparison);
$("reloadBtn").addEventListener("click",()=>openItem(state.selectedId));$("copyBtn").addEventListener("click",copyItem);$("deleteBtn").addEventListener("click",deleteItem);$("saveMetadataBtn").addEventListener("click",saveMetadata);
$("itemIcon").addEventListener("error",()=>$("itemIcon").style.visibility="hidden");$("resetProjectionBtn").addEventListener("click",resetProjection);$("addProjectionNodeBtn").addEventListener("click",()=>openNodeDialog("projection"));$("addLocalNodeBtn").addEventListener("click",()=>openNodeDialog("local"));
$("nodeType").addEventListener("change",()=>{const vector=$("nodeType").value==="Vector";$("vectorInputs").hidden=!vector;$("nodeValueLabel").hidden=vector||["SubProperty","Null"].includes($("nodeType").value);});
$("nodeForm").addEventListener("submit",async(event)=>{event.preventDefault();const parent=$("nodeParent").value.trim(),name=$("nodeName").value.trim(),kind=$("nodeType").value,values=nodeValues(kind);$("nodeDialog").close();if(state.nodeTarget==="projection")stageAddedNode(parent,name,kind,values);else await mutateLocalNode({operation:"add",path:parent,name,kind,values});});

loadCatalog();
