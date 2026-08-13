(() => {
  "use strict";

  const data = window.LIMBO_MANIFEST;
  const byId = (id) => document.getElementById(id);
  const els = {
    sourceNote: byId("source-note"), summary: byId("summary"), stageTabs: byId("stage-tabs"),
    scene: byId("scene"), sceneMap: byId("scene-map"), spineLayers: byId("spine-layers"),
    objectLayers: byId("object-layers"), bossFrame: byId("boss-frame"), patternFrame: byId("pattern-frame"),
    sceneStatus: byId("scene-status"), mobSelect: byId("mob-select"), actionSelect: byId("action-select"),
    patternSelect: byId("pattern-select"), playToggle: byId("play-toggle"), speedSelect: byId("speed-select"),
    toggleBackground: byId("toggle-background"), toggleBoss: byId("toggle-boss"),
    togglePattern: byId("toggle-pattern"), timeline: byId("timeline"), mapPanel: byId("map-panel"),
    mobPanel: byId("mob-panel"), patternPanel: byId("pattern-panel"), videoPanel: byId("video-panel"),
  };

  const state = {
    stageId: data.maps[0].id,
    playing: true,
    speed: 1,
    boss: { sequence: null, index: 0, elapsed: 0 },
    pattern: { sequence: null, index: 0, elapsed: 0 },
    objectRuntimes: [],
    spinePlayers: [],
    spineStageHosts: new Map(),
    lastTick: performance.now(),
  };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  })[char]);
  const formatBytes = (bytes) => {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const order = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
    return `${(bytes / (1024 ** order)).toFixed(order ? 1 : 0)} ${units[order]}`;
  };
  const currentMap = () => data.maps.find((item) => item.id === state.stageId);
  const currentMobs = () => data.mobs.filter((item) => item.stage === state.stageId);
  const currentPatterns = () => data.patterns.filter((item) => item.stage === state.stageId || item.stage === "all");

  function sequenceDuration(sequence) {
    return sequence ? sequence.frames.reduce((sum, frame) => sum + frame.delay, 0) : 0;
  }

  function stageMetrics() {
    const map = currentMap();
    const width = els.scene.clientWidth;
    const height = els.scene.clientHeight;
    const mapWidth = Math.max(1, map.vr[2] - map.vr[0]);
    const mapHeight = Math.max(1, map.vr[3] - map.vr[1]);
    const scale = Math.min(width / mapWidth, height / mapHeight);
    return {
      width, height, scale,
      offsetX: (width - mapWidth * scale) / 2,
      offsetY: (height - mapHeight * scale) / 2,
      x(value) { return this.offsetX + (value - map.vr[0]) * scale; },
      y(value) { return this.offsetY + (value - map.vr[1]) * scale; },
    };
  }

  function frameGeometry(sequence, frame, mode, anchorX = 0, anchorY = 0) {
    const metrics = stageMetrics();
    if (mode === "screen") {
      const [left, top, right, bottom] = sequence.bounds;
      const boundsWidth = Math.max(1, right - left);
      const boundsHeight = Math.max(1, bottom - top);
      const scale = Math.min(metrics.width / boundsWidth, metrics.height / boundsHeight);
      return {
        width: frame.width * scale,
        left: (metrics.width - boundsWidth * scale) / 2 + (-frame.origin[0] - left) * scale,
        top: (metrics.height - boundsHeight * scale) / 2 + (-frame.origin[1] - top) * scale,
      };
    }
    const scale = metrics.scale;
    const originX = mode === "boss" && frame.origin[0] === 0 && frame.origin[1] === 0
      ? Math.round(frame.width / 2)
      : frame.origin[0];
    const originY = mode === "boss" && frame.origin[0] === 0 && frame.origin[1] === 0
      ? frame.height
      : frame.origin[1];
    return {
      width: frame.width * scale,
      left: metrics.x(anchorX) - originX * scale,
      top: metrics.y(anchorY) - originY * scale,
    };
  }

  function drawSequence(runtime, image, mode, anchorX = 0, anchorY = 0) {
    if (!runtime.sequence || !runtime.sequence.frames.length) {
      image.removeAttribute("src");
      image.hidden = true;
      return;
    }
    const frame = runtime.sequence.frames[runtime.index % runtime.sequence.frames.length];
    const geometry = frameGeometry(runtime.sequence, frame, mode, anchorX, anchorY);
    if (image.dataset.src !== frame.src) {
      image.src = frame.src;
      image.dataset.src = frame.src;
    }
    image.hidden = false;
    image.style.width = `${geometry.width}px`;
    image.style.left = `${geometry.left}px`;
    image.style.top = `${geometry.top}px`;
  }

  function resetRuntime(runtime, sequence) {
    runtime.sequence = sequence || null;
    runtime.index = 0;
    runtime.elapsed = 0;
  }

  function advance(runtime, delta) {
    if (!runtime.sequence || runtime.sequence.frames.length < 2) return false;
    runtime.elapsed += delta * state.speed;
    let changed = false;
    let frame = runtime.sequence.frames[runtime.index];
    while (runtime.elapsed >= frame.delay) {
      runtime.elapsed -= frame.delay;
      runtime.index = (runtime.index + 1) % runtime.sequence.frames.length;
      frame = runtime.sequence.frames[runtime.index];
      changed = true;
    }
    return changed;
  }

  function renderMainFrames() {
    drawSequence(state.boss, els.bossFrame, "boss", 0, state.stageId === "p2d" ? -10 : 0);
    const patternMode = state.pattern.sequence?.fullScreen ? "screen" : "field";
    drawSequence(state.pattern, els.patternFrame, patternMode, 0, -100);
    state.objectRuntimes.forEach((runtime) => drawSequence(runtime, runtime.image, "field", runtime.layer.x, runtime.layer.y));
    els.bossFrame.style.display = els.toggleBoss.checked && state.boss.sequence ? "block" : "none";
    els.patternFrame.style.display = els.togglePattern.checked && state.pattern.sequence ? "block" : "none";
    els.spineLayers.style.display = els.toggleBackground.checked ? "block" : "none";
    els.objectLayers.style.display = els.toggleBackground.checked ? "block" : "none";
    const bossText = state.boss.sequence ? `${state.boss.sequence.path} · ${state.boss.index + 1}/${state.boss.sequence.frames.length}` : "无 Boss 资源";
    const patternText = state.pattern.sequence ? `${state.pattern.sequence.path} · ${state.pattern.index + 1}/${state.pattern.sequence.frames.length}` : "未选择场景技能";
    els.sceneStatus.textContent = `${currentMap().label} ｜ ${bossText} ｜ ${patternText}`;
    const total = state.pattern.sequence?.frames.length || state.boss.sequence?.frames.length || 1;
    const index = state.pattern.sequence ? state.pattern.index : state.boss.index;
    els.timeline.style.setProperty("--progress", `${((index + 1) / total) * 100}%`);
  }

  function createSpineLayers() {
    state.spineStageHosts.forEach((wrapper) => { wrapper.style.display = "none"; });
    const cached = state.spineStageHosts.get(state.stageId);
    if (cached) {
      cached.style.display = "block";
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "spine-stage";
    wrapper.dataset.stage = state.stageId;
    els.spineLayers.appendChild(wrapper);
    state.spineStageHosts.set(state.stageId, wrapper);
    const candidates = currentMap().layers.filter((layer) => layer.type === "spine");
    const selected = candidates;
    selected.forEach((layer, index) => {
      const host = document.createElement("div");
      host.id = `spine-layer-${state.stageId}-${index}`;
      host.className = "spine-layer";
      host.dataset.x = String(layer.x);
      host.dataset.y = String(layer.y);
      host.style.zIndex = String(Math.max(1, layer.z + 120));
      wrapper.appendChild(host);
      const map = currentMap();
      const config = {
        skelUrl: layer.resource.skel,
        atlasUrl: layer.resource.atlas,
        alpha: true,
        premultipliedAlpha: true,
        backgroundColor: "00000000",
        showControls: false,
        showLoading: false,
        mipmaps: true,
        viewport: {
          x: map.vr[0] - layer.x,
          y: layer.y - map.vr[3],
          width: map.dimensions[0],
          height: map.dimensions[1],
          padLeft: 0,
          padRight: 0,
          padTop: 0,
          padBottom: 0,
          transitionTime: 0,
        },
        success(player) {
          player.speed = state.speed * (layer.timeScale / 100);
          if (!state.playing) player.pause();
        },
      };
      if (layer.animation) config.animation = layer.animation;
      try {
        const player = new spine.SpinePlayer(host.id, config);
        state.spinePlayers.push(player);
      } catch (error) {
        host.textContent = `Spine 加载失败：${error.message}`;
      }
    });
  }

  function createObjectLayers() {
    els.objectLayers.replaceChildren();
    state.objectRuntimes = [];
    currentMap().layers.filter((layer) => layer.type === "frames").forEach((layer) => {
      const image = document.createElement("img");
      image.className = "scene-object";
      image.alt = "";
      image.style.zIndex = String(Math.max(1, layer.z + 300));
      if (layer.flip) image.style.transform = "scaleX(-1)";
      els.objectLayers.appendChild(image);
      state.objectRuntimes.push({ sequence: layer.resource, index: 0, elapsed: 0, image, layer });
    });
  }

  function populateSelectors() {
    const mobs = currentMobs();
    els.mobSelect.innerHTML = mobs.length
      ? mobs.map((mob) => `<option value="${mob.id}">${escapeHtml(mob.label)} · ${mob.id}</option>`).join("")
      : '<option value="">本阶段无独立 Mob Canvas</option>';
    populateActions();
    const patterns = currentPatterns();
    els.patternSelect.innerHTML = '<option value="">不叠加场景技能</option>' + patterns.map((pattern) => {
      const type = pattern.fullScreen ? "全屏/大特效" : "局部机制";
      return `<option value="${escapeHtml(pattern.path)}">${escapeHtml(pattern.path)} · ${type} · ${pattern.sourceFrameCount}帧</option>`;
    }).join("");
    els.patternSelect.value = "";
    selectPattern();
  }

  function populateActions() {
    const mob = data.mobs.find((item) => item.id === els.mobSelect.value) || currentMobs()[0];
    if (!mob) {
      els.actionSelect.innerHTML = '<option value="">无动作</option>';
      resetRuntime(state.boss, null);
      return;
    }
    els.mobSelect.value = mob.id;
    els.actionSelect.innerHTML = mob.actions.map((action) =>
      `<option value="${escapeHtml(action.path)}">${escapeHtml(action.path.split("/").slice(1).join("/"))} · ${action.sourceFrameCount}帧</option>`
    ).join("");
    const preferred = mob.actions.find((action) => action.path.endsWith("/stand")) || mob.actions[0];
    if (preferred) els.actionSelect.value = preferred.path;
    selectAction();
  }

  function selectAction() {
    const mob = data.mobs.find((item) => item.id === els.mobSelect.value);
    const sequence = mob?.actions.find((action) => action.path === els.actionSelect.value) || null;
    resetRuntime(state.boss, sequence);
    renderMainFrames();
  }

  function selectPattern() {
    const sequence = data.patterns.find((pattern) => pattern.path === els.patternSelect.value) || null;
    resetRuntime(state.pattern, sequence);
    renderMainFrames();
  }

  function renderStage() {
    document.querySelectorAll(".stage-tab").forEach((button) => button.classList.toggle("active", button.dataset.stage === state.stageId));
    const palette = {
      p1: "radial-gradient(circle at 50% 34%, #2d1d45, #08070d 68%)",
      p2c: "radial-gradient(circle at 50% 42%, #162b35, #07090d 68%)",
      middle: "radial-gradient(circle at 50% 48%, #30233b, #08070d 65%)",
      p2d: "radial-gradient(circle at 48% 38%, #132f39, #07090d 70%)",
      p3: "radial-gradient(circle at 50% 45%, #2a2930, #030305 72%)",
    };
    els.sceneMap.style.background = palette[state.stageId];
    populateSelectors();
    createObjectLayers();
    createSpineLayers();
    renderCatalog();
    renderMainFrames();
  }

  function renderMapPanel() {
    const map = currentMap();
    const spineCount = map.layers.filter((layer) => layer.type === "spine").length;
    const frameCount = map.layers.filter((layer) => layer.type === "frames").length;
    const missingPages = map.layers.filter((layer) => layer.type === "spine").flatMap((layer) =>
      (layer.resource.missingPages || []).map((page) => `${layer.resource.path}/${page.name} (${page.width}×${page.height})`)
    );
    els.mapPanel.innerHTML = `${missingPages.length ? `<div class="notice"><strong>源资源缺页：</strong>以下 atlas 纹理页没有出现在 TMS _Canvas 中，预览使用透明占位，迁移前需要另行补齐：<br>${missingPages.map((page) => `<code>${escapeHtml(page)}</code>`).join("<br>")}</div>` : ""}<div class="map-layout">
      ${map.minimap ? `<img class="minimap" src="${escapeHtml(map.minimap)}" alt="${map.mapId} 小地图">` : '<div class="empty">该地图没有可导出小地图</div>'}
      <div class="table-wrap"><table><tbody>
        <tr><th>阶段</th><td>${escapeHtml(map.label)}</td></tr>
        <tr><th>地图 ID</th><td><code>${map.mapId}</code></td></tr>
        <tr><th>fieldType</th><td>${map.fieldType}</td></tr>
        <tr><th>模式</th><td>${escapeHtml(map.mode)}</td></tr>
        <tr><th>场景边界</th><td>${map.vr.join(", ")}（${map.dimensions[0]} × ${map.dimensions[1]}）</td></tr>
        <tr><th>BGM</th><td><code>${escapeHtml(map.bgm)}</code></td></tr>
        <tr><th>已解析场景层</th><td>${map.layers.length} 层：${spineCount} 个 Spine、${frameCount} 个 Canvas 动画/物件</td></tr>
      </tbody></table></div>
    </div>`;
  }

  function renderMobPanel() {
    const mobs = currentMobs();
    if (!mobs.length) {
      els.mobPanel.innerHTML = '<p class="empty">中场以地图 Spine 转场为主，没有单独归入该阶段的 Mob Canvas。</p>';
      return;
    }
    els.mobPanel.innerHTML = `<div class="resource-grid">${mobs.map((mob) => {
      const skills = mob.actions.filter((action) => /skill|attack/i.test(action.path)).length;
      const totalFrames = mob.actions.reduce((sum, action) => sum + action.sourceFrameCount, 0);
      return `<article class="resource-card">
        <h3>${escapeHtml(mob.label)}</h3>
        <p><code>${mob.id}</code> · ${formatBytes(mob.sourceBytes)}</p>
        <p>${mob.actions.length} 个动作，${totalFrames} 帧；其中 ${skills} 个技能/攻击动作</p>
        <div>${mob.actions.slice(0, 10).map((action) => `<span class="tag">${escapeHtml(action.path.split("/").pop())} · ${action.sourceFrameCount}</span>`).join("")}</div>
        <button type="button" data-preview-mob="${mob.id}">放入场景预览</button>
      </article>`;
    }).join("")}</div>`;
    els.mobPanel.querySelectorAll("[data-preview-mob]").forEach((button) => button.addEventListener("click", () => {
      els.mobSelect.value = button.dataset.previewMob;
      populateActions();
      els.scene.scrollIntoView({ behavior: "smooth", block: "center" });
    }));
  }

  function renderPatternPanel(filter = "") {
    const normalized = filter.trim().toLowerCase();
    const patterns = currentPatterns().filter((pattern) => pattern.path.toLowerCase().includes(normalized));
    const visible = patterns.slice(0, 160);
    els.patternPanel.innerHTML = `<div class="notice">${escapeHtml(data.classificationNote)}</div>
      <div class="filter-row"><input id="pattern-filter" type="search" value="${escapeHtml(filter)}" placeholder="按 BossPattern 路径筛选，例如 screen、alert、1023"></div>
      <div class="table-wrap"><table><thead><tr><th>资源路径</th><th>类型</th><th>帧数</th><th>预览</th></tr></thead><tbody>
      ${visible.map((pattern) => `<tr>
        <td><code>${escapeHtml(pattern.path)}</code></td>
        <td>${pattern.fullScreen ? '<span class="tag cyan">全屏 / 大特效 / MCV 候选</span>' : '<span class="tag">局部机制</span>'}</td>
        <td>${pattern.sourceFrameCount}${data.quick && pattern.frameCount < pattern.sourceFrameCount ? `（快速版导出 ${pattern.frameCount}）` : ""}</td>
        <td><button type="button" data-preview-pattern="${escapeHtml(pattern.path)}">叠加</button></td>
      </tr>`).join("")}</tbody></table></div>
      ${patterns.length > visible.length ? `<p class="empty">当前显示前 ${visible.length} / ${patterns.length} 项，请继续输入路径缩小范围。</p>` : ""}`;
    const input = byId("pattern-filter");
    input.addEventListener("input", () => renderPatternPanel(input.value));
    els.patternPanel.querySelectorAll("[data-preview-pattern]").forEach((button) => button.addEventListener("click", () => {
      els.patternSelect.value = button.dataset.previewPattern;
      selectPattern();
      els.scene.scrollIntoView({ behavior: "smooth", block: "center" });
    }));
  }

  function renderVideoPanel() {
    const video = data.video;
    els.videoPanel.innerHTML = `<div class="notice"><strong>已确认的播放冲突：</strong>${escapeHtml(video.playbackConstraint)}<br>
      预览站逐帧播放 Boss 动画，不占 MCV 通道；迁移时应仅把大背景/转场作为 MCV 候选，战斗中的常驻技能优先保留 Canvas。</div>
      <div class="resource-grid">
        <article class="resource-card"><h3>原生 Canvas#Video</h3><p>${video.nativeCanvasVideoCount} 项</p><p>BossLimbo 的 BossPattern、地图和 Mob 资源中未发现原生视频节点。</p></article>
        <article class="resource-card"><h3>现有职业 MCV</h3><p>${video.existingMcv.length} 项</p><p>这些文件正在共享当前客户端的单实例 MCV 播放链。</p></article>
        <article class="resource-card"><h3>林波 MCV 候选</h3><p>${video.limboMcvCandidates.length} 项</p><p>按全屏尺寸、screen 路径或大画幅自动筛出；当前页可直接逐帧验证。</p></article>
      </div>
      <h3>现有 MCV 文件</h3>
      <div class="table-wrap"><table><thead><tr><th>文件</th><th>大小</th></tr></thead><tbody>${video.existingMcv.map((item) => `<tr><td><code>${escapeHtml(item.name)}</code></td><td>${formatBytes(item.bytes)}</td></tr>`).join("")}</tbody></table></div>
      <h3 style="margin-top:24px">林波全屏 / 大特效候选</h3>
      <div class="table-wrap"><table><thead><tr><th>路径</th><th>阶段初分</th><th>帧数</th></tr></thead><tbody>${video.limboMcvCandidates.map((item) => `<tr><td><code>${escapeHtml(item.path)}</code></td><td>${escapeHtml(item.stage)}</td><td>${item.frames}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function renderCatalog() {
    renderMapPanel();
    renderMobPanel();
    renderPatternPanel();
    renderVideoPanel();
  }

  function bindEvents() {
    els.mobSelect.addEventListener("change", populateActions);
    els.actionSelect.addEventListener("change", selectAction);
    els.patternSelect.addEventListener("change", selectPattern);
    els.playToggle.addEventListener("click", () => {
      state.playing = !state.playing;
      els.playToggle.textContent = state.playing ? "暂停" : "播放";
      state.spinePlayers.forEach((player) => {
        try { state.playing ? player.play() : player.pause(); } catch (_) { /* still loading */ }
      });
    });
    els.speedSelect.addEventListener("change", () => {
      state.speed = Number(els.speedSelect.value);
      state.spinePlayers.forEach((player) => { player.speed = state.speed; });
    });
    [els.toggleBackground, els.toggleBoss, els.togglePattern].forEach((input) => input.addEventListener("change", renderMainFrames));
    document.querySelectorAll(".catalog-tab").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll(".catalog-tab").forEach((tab) => tab.classList.toggle("active", tab === button));
      document.querySelectorAll(".catalog-panel").forEach((panel) => panel.classList.toggle("active", panel.id === button.dataset.panel));
    }));
    window.addEventListener("resize", () => {
      createSpineLayers();
      renderMainFrames();
    });
  }

  function tick(now) {
    const delta = Math.min(100, now - state.lastTick);
    state.lastTick = now;
    if (state.playing) {
      let changed = advance(state.boss, delta) || advance(state.pattern, delta);
      state.objectRuntimes.forEach((runtime) => { changed = advance(runtime, delta) || changed; });
      if (changed) renderMainFrames();
    }
    requestAnimationFrame(tick);
  }

  function init() {
    els.sourceNote.textContent = `源：${data.source} ｜ ${data.quick ? "快速导出（每段最多 8 帧）" : "完整逐帧导出"}`;
    const totalMobFrames = data.mobs.reduce((sum, mob) => sum + mob.actions.reduce((inner, action) => inner + action.sourceFrameCount, 0), 0);
    const totalPatternFrames = data.patterns.reduce((sum, pattern) => sum + pattern.sourceFrameCount, 0);
    els.summary.innerHTML = [
      [data.maps.length, "困难阶段"], [data.mobs.length, "怪物形象"], [totalMobFrames, "怪物动作帧"],
      [data.patterns.length, "场景技能段"], [totalPatternFrames, "场景技能帧"], [data.spines.length, "Spine 场景资源"],
    ].map(([value, label]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
    els.stageTabs.innerHTML = data.maps.map((map) => `<button type="button" class="stage-tab" data-stage="${map.id}">${escapeHtml(map.label)}<br><small>${map.mapId}</small></button>`).join("");
    els.stageTabs.querySelectorAll(".stage-tab").forEach((button) => button.addEventListener("click", () => {
      state.stageId = button.dataset.stage;
      renderStage();
    }));
    bindEvents();
    renderStage();
    requestAnimationFrame(tick);
  }

  init();
})();
