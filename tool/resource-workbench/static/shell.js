"use strict";

const moduleNames = new Set(["map-mob", "img-editor", "quests"]);
const moduleTitles = {"map-mob": "地图与怪物", "img-editor": "IMG 节点", quests: "任务管理"};

function moduleFromUrl() {
  const selected = new URLSearchParams(location.search).get("module");
  return moduleNames.has(selected) ? selected : "map-mob";
}

function activateModule(name, updateHistory = false) {
  if (!moduleNames.has(name)) name = "map-mob";
  document.querySelectorAll("[data-module-panel]").forEach((panel) => {
    const active = panel.dataset.modulePanel === name;
    panel.hidden = !active;
    if (active) {
      const frame = panel.querySelector("iframe");
      if (!frame.hasAttribute("src")) frame.src = frame.dataset.src;
    }
  });
  document.querySelectorAll(".suite-link[data-module]").forEach((link) => {
    const active = link.dataset.module === name;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${moduleTitles[name]} · BeiDou 资源工作台`;
  if (updateHistory) {
    const nextUrl = name === "map-mob" ? "/" : `/?module=${name}`;
    history.pushState({module: name}, "", nextUrl);
  }
}

document.querySelectorAll("[data-module]").forEach((link) => link.addEventListener("click", (event) => {
  event.preventDefault();
  activateModule(link.dataset.module, true);
}));
window.addEventListener("popstate", () => activateModule(moduleFromUrl()));
activateModule(document.body.dataset.initialModule || moduleFromUrl());
