package org.gms.service;

import lombok.extern.slf4j.Slf4j;
import org.gms.model.dto.*;
import org.springframework.stereotype.Service;
import org.w3c.dom.*;
import org.xml.sax.SAXException;

import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 地图功能检测服务。
 *
 * <p>读取指定地图的 XML（wz/Map.wz/Map/MapX/<id>.img.xml），解析其全部节点结构，
 * 并对其引用的各类资源（NPC / 怪物 / 反应堆 / 物件 / 背景 / 传送目标地图 / 回城地图 /
 * BGM / 脚本 / foothold 平台）做存在性校验，最终产出分类化的诊断结果。</p>
 *
 * <p>设计要点：
 * <ul>
 *   <li>瓦片(Tile)在本客户端并非 {@code Tile/<u>.img.xml} 一对一命名（全量 47 万条瓦片引用 0 命中），
 *       因此瓦片只做汇总式 INFO 提示，不作报错，避免海量误报。</li>
 *   <li>其它资源映射已用真实地图验证，可作硬性存在性校验（缺失即 ERROR）。</li>
 *   <li>life.fh 必须存在于 foothold 层，否则标记为不兼容节点（ERROR）。</li>
 * </ul>
 * </p>
 */
@Slf4j
@Service
public class MapDetectService {

    private final String baseDir = System.getProperty("user.dir");

    private static final int SENTINEL_NO_MAP = 999999999;

    /** String.wz 名称表（Map/Mob/Npc）体积较大，解析后按路径+最后修改时间缓存，避免每次检测重复解析 */
    private static final Map<String, DocCache> docCache = new ConcurrentHashMap<>();

    private static class DocCache {
        long modified;
        Document doc;

        DocCache(long modified, Document doc) {
            this.modified = modified;
            this.doc = doc;
        }
    }

    public MapDetectResultDTO detect(String rawMapId) {
        MapDetectResultDTO result = new MapDetectResultDTO();
        List<MapDetectCategoryDTO> categories = new ArrayList<>();
        result.setCategories(categories);

        if (rawMapId == null || rawMapId.trim().isEmpty()) {
            result.setMapExists(false);
            result.setNote("请输入地图 ID");
            return result;
        }
        String mapId = rawMapId.trim();
        result.setMapId(mapId);

        Path mapFile = resolveMapFile(mapId);
        if (mapFile == null || !Files.exists(mapFile)) {
            result.setMapExists(false);
            result.setNote("未找到地图文件: wz/Map.wz/Map/Map" + firstDigit(mapId) + "/" + mapId + ".img.xml");
            return result;
        }
        result.setMapExists(true);

        // 收集脚本引用（npc/reactor/portal/字段脚本），最后单独成类
        List<MapDetectNodeDTO> scriptRefs = new ArrayList<>();

        // 收集 life 中的怪物 / NPC id（去重），用于聚合"地图信息"
        Set<String> mobIds = new LinkedHashSet<>();
        Set<String> npcIds = new LinkedHashSet<>();

        try {
            Document doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(mapFile.toFile());
            Element root = doc.getDocumentElement();

            Set<String> fhSet = collectFootholds(root);

            categories.add(buildInfoCategory(root, scriptRefs));
            categories.add(buildBackCategory(root));
            categories.addAll(buildLifeCategories(root, fhSet, scriptRefs, mobIds, npcIds));
            categories.add(buildReactorCategory(root, scriptRefs));
            categories.add(buildPortalCategory(root, scriptRefs));
            categories.add(buildObjCategory(root));
            categories.add(buildTileCategory(root));
            categories.add(buildFootholdCategory(fhSet));
            categories.add(buildScriptCategory(scriptRefs));

            // 聚合地图基础信息（名字 / 地区 / 怪物 / NPC）
            result.setMapInfo(buildMapInfo(mapId, mobIds, npcIds));
        } catch (ParserConfigurationException | SAXException | IOException e) {
            log.error("地图检测解析失败 map={}", mapId, e);
            result.setNote("解析地图失败: " + e.getMessage());
        } catch (Exception e) {
            log.error("地图检测异常 map={}", mapId, e);
            result.setNote("检测异常: " + e.getMessage());
        }

        int ok = 0, warn = 0, error = 0, info = 0, total = 0, crashRiskCount = 0;
        for (MapDetectCategoryDTO c : categories) {
            ok += c.getOk();
            warn += c.getWarn();
            error += c.getError();
            info += c.getInfo();
            total += c.getTotal();
            for (MapDetectNodeDTO n : c.getNodes()) {
                if ("CRASH".equals(n.getCrashRisk())) crashRiskCount++;
            }
        }
        result.setOk(ok);
        result.setWarn(warn);
        result.setError(error);
        result.setInfo(info);
        result.setTotal(total);
        result.setCrashRiskCount(crashRiskCount);
        return result;
    }

    // ---------------------------------------------------------------- info

    private MapDetectCategoryDTO buildInfoCategory(Element root, List<MapDetectNodeDTO> scriptRefs) {
        MapDetectCategoryDTO c = newCategory("info", "地图基础信息", false);
        Element info = getDir(root, "info");
        if (info == null) {
            addNode(c, "info", "", "WARN", "未找到 info 节点", "地图基础配置（音乐/回城/限制等）的容器节点缺失", "info 节点不存在");
            return c;
        }

        // BGM
        String bgm = getVal(info, "bgm");
        if (bgm != null && !bgm.isEmpty()) {
            String[] parts = bgm.split("/", 2);
            boolean fileOk = existsInWz("Sound.wz/" + parts[0] + ".img.xml");
            boolean nodeOk = parts.length > 1 ? soundNodeExists(parts[0], parts[1]) : true;
            String status = fileOk ? (nodeOk ? "OK" : "WARN") : "ERROR";
            String msg = !fileOk ? "背景音乐文件缺失: Sound.wz/" + parts[0] + ".img.xml"
                    : (!nodeOk ? "音乐节点缺失: " + bgm : "");
            addNode(c, "bgm", bgm, status, "背景音乐(BGM)", "角色进入地图时循环播放的背景音乐", msg, kv("fileOk", String.valueOf(fileOk)));
        }

        // returnMap / forcedReturn
        int returnMap = getInt(info, "returnMap", -1);
        checkMapRef(c, "returnMap", returnMap, "死亡/指令回城后返回的地图");
        int forcedReturn = getInt(info, "forcedReturn", -1);
        checkMapRef(c, "forcedReturn", forcedReturn, "强制回城点（通常为安全复活地图）");

        // mapMark（仅提示，避免误报）
        String mapMark = getVal(info, "mapMark");
        if (mapMark != null && !mapMark.isEmpty()) {
            addNode(c, "mapMark", mapMark, "INFO", "小地图标记", "世界地图上代表该地图的图标标记", "", kv("value", mapMark));
        }

        // 字段脚本
        String onEnter = getVal(info, "onUserEnter");
        if (onEnter != null && !onEnter.isEmpty()) {
            checkFieldScript(scriptRefs, "onUserEnter", onEnter);
        }
        String onFirst = getVal(info, "onFirstUserEnter");
        if (onFirst != null && !onFirst.isEmpty()) {
            checkFieldScript(scriptRefs, "onFirstUserEnter", onFirst);
        }

        // 其余信息字段（INFO 说明作用）
        addNode(c, "mobRate", getVal(info, "mobRate"), "INFO", "怪物倍率", "该地图怪物刷新数量倍率", "");
        addNode(c, "lvLimit", getVal(info, "lvLimit"), "INFO", "等级限制", "进入该地图所需最低等级", "");
        addNode(c, "fieldLimit", getVal(info, "fieldLimit"), "INFO", "地图限制", "地图功能限制（如禁止技能/跳跃等）", "");
        addNode(c, "town", getVal(info, "town"), "INFO", "村庄标记", "是否为安全村庄（不可 PK）", "");
        addNode(c, "swim", getVal(info, "swim"), "INFO", "游泳标记", "是否水域地图", "");
        addNode(c, "fly", getVal(info, "fly"), "INFO", "飞行标记", "是否允许飞行", "");
        addNode(c, "version", getVal(info, "version"), "INFO", "数据版本", "地图数据版本号", "");
        return c;
    }

    private void checkMapRef(MapDetectCategoryDTO c, String refType, int mapVal, String func) {
        if (mapVal == SENTINEL_NO_MAP || mapVal <= 0) {
            addNode(c, refType, String.valueOf(mapVal), "INFO", "地图引用 " + mapVal, func,
                    "目标地图ID=" + mapVal + (mapVal == SENTINEL_NO_MAP ? "（无/占位）" : "（无效）"));
            return;
        }
        boolean ok = mapFileExists(String.valueOf(mapVal));
        addNode(c, refType, String.valueOf(mapVal), ok ? "OK" : "ERROR", "地图引用 " + mapVal, func,
                ok ? "" : "目标地图不存在: " + mapVal, kv("exists", String.valueOf(ok)));
    }

    private void checkFieldScript(List<MapDetectNodeDTO> scriptRefs, String kind, String name) {
        boolean ok = existsInScripts("map/" + kind + "/" + name + ".js");
        String status = ok ? "OK" : "WARN";
        String msg = ok ? "" : "脚本缺失: scripts/" + kind + "/" + name + ".js（字段脚本未触发）";
        scriptRefs.add(newNode("script", "script", name, status, "地图脚本(" + kind + ")",
                "玩家进入地图时触发的脚本(" + kind + ")", msg, kv("kind", "map/" + kind)));
    }

    // ---------------------------------------------------------------- back

    private MapDetectCategoryDTO buildBackCategory(Element root) {
        MapDetectCategoryDTO c = newCategory("back", "背景图层", false);
        Element back = getDir(root, "back");
        if (back != null) {
            for (Element e : getDirs(back)) {
                String bS = getVal(e, "bS");
                if (bS == null) continue;
                boolean wzOk = existsInWz("Map.wz/Back/" + bS + ".img.xml");
                boolean clientOk = existsInClient("Data/Map/Back/" + bS + ".img");
                String front = getVal(e, "front");
                String type = getVal(e, "type");
                String status = wzOk ? (clientOk ? "OK" : "WARN") : "ERROR";
                String msg = !wzOk ? "背景资源缺失(服务端): Map.wz/Back/" + bS + ".img.xml"
                        : (!clientOk ? "背景客户端资源缺失: Data/Map/Back/" + bS + ".img" : "");
                addNode(c, "back", bS, status, "背景 " + bS,
                        "背景图层，营造地图纵深与氛围（front=" + front + ", type=" + type + "）", msg,
                        kv("front", front), kv("type", type), kv("clientOk", String.valueOf(clientOk)));
            }
        }
        if (c.getNodes().isEmpty()) {
            addNode(c, "back", "", "INFO", "无背景", "该地图未配置背景图层", "");
        }
        return c;
    }

    // ---------------------------------------------------------------- life (npc / mob)

    private List<MapDetectCategoryDTO> buildLifeCategories(Element root, Set<String> fhSet, List<MapDetectNodeDTO> scriptRefs, Set<String> mobIds, Set<String> npcIds) {
        List<MapDetectCategoryDTO> list = new ArrayList<>();
        MapDetectCategoryDTO npc = newCategory("npc", "NPC", false);
        MapDetectCategoryDTO mob = newCategory("mob", "怪物", false);
        Element life = getDir(root, "life");
        if (life != null) {
            for (Element e : getDirs(life)) {
                String type = getVal(e, "type");
                String id = getVal(e, "id");
                String fh = getVal(e, "fh");
                String x = getVal(e, "x");
                String y = getVal(e, "y");
                String hide = getVal(e, "hide");
                if ("n".equalsIgnoreCase(type)) {
                    npcIds.add(id);
                    boolean wzOk = existsInWz(padded("Npc.wz", id, 7));
                    boolean clientOk = existsInClientPadded("Npc", id, 7);
                    String status = wzOk ? (clientOk ? "OK" : "WARN") : "ERROR";
                    String msg = !wzOk ? "NPC 资源缺失(服务端): Npc.wz/" + pad7(id) + ".img.xml"
                            : (!clientOk ? "NPC 客户端资源缺失: Data/Npc/" + pad7(id) + ".img（可能加载异常但通常不崩溃）" : "");
                    addNode(npc, "npc", id, status, "NPC #" + id,
                            "地图中的非玩家角色（对话/商店/任务）", msg,
                            kv("x", x), kv("y", y), kv("fh", fh), kv("hide", hide),
                            kv("clientOk", String.valueOf(clientOk)));
                    if (wzOk) checkScriptRef(scriptRefs, "npc", id, false);
                    addFhProblem(npc, fh, fhSet, id, "NPC");
                } else if ("m".equalsIgnoreCase(type)) {
                    mobIds.add(id);
                    boolean wzOk = existsInWz(padded("Mob.wz", id, 7));
                    boolean clientOk = existsInClientPadded("Mob", id, 7);
                    String status = wzOk ? (clientOk ? "OK" : "WARN") : "ERROR";
                    String msg = !wzOk ? "怪物资源缺失(服务端): Mob.wz/" + pad7(id) + ".img.xml"
                            : (!clientOk ? "怪物客户端资源缺失: Data/Mob/" + pad7(id) + ".img（客户端进图极可能崩溃）" : "");
                    MapDetectNodeDTO node = newNode("mob", "mob", id, status, "怪物 #" + id,
                            "地图中的怪物刷新点", msg,
                            kv("x", x), kv("y", y), kv("fh", fh), kv("hide", hide),
                            kv("clientOk", String.valueOf(clientOk)));
                    if (!clientOk && wzOk) node.setCrashRisk("CRASH");
                    mob.getNodes().add(node);
                    mob.setTotal(mob.getTotal() + 1);
                    tally(mob, status);
                    addFhProblem(mob, fh, fhSet, id, "怪物");
                } else {
                    addNode(npc, "life", id, "WARN", "未知 life 类型: " + type,
                            "无法识别的 life 类型", "type=" + type, kv("x", x), kv("y", y));
                }
            }
        }
        if (npc.getNodes().isEmpty()) addNode(npc, "npc", "", "INFO", "无 NPC", "该地图未配置 NPC", "");
        if (mob.getNodes().isEmpty()) addNode(mob, "mob", "", "INFO", "无怪物", "该地图未配置怪物", "");
        list.add(npc);
        list.add(mob);
        return list;
    }

    private void addFhProblem(MapDetectCategoryDTO c, String fh, Set<String> fhSet, String lifeId, String lifeLabel) {
        if (fh == null || fh.isEmpty()) return;
        if (!fhSet.contains(fh)) {
            MapDetectNodeDTO node = newNode("foothold", "foothold", fh, "ERROR",
                    lifeLabel + " #" + lifeId + " 的 Foothold 引用",
                    "该" + lifeLabel + "挂在不存在的碰撞平台上（不兼容，可能崩溃或掉出地图）",
                    "Foothold #" + fh + " 不存在",
                    kv("lifeId", lifeId));
            node.setCrashRisk("CRASH");
            c.getNodes().add(node);
            c.setTotal(c.getTotal() + 1);
            tally(c, "ERROR");
        }
    }

    // ---------------------------------------------------------------- reactor

    private MapDetectCategoryDTO buildReactorCategory(Element root, List<MapDetectNodeDTO> scriptRefs) {
        MapDetectCategoryDTO c = newCategory("reactor", "反应堆", false);
        Element r = getDir(root, "reactor");
        if (r != null) {
            for (Element e : getDirs(r)) {
                String id = getVal(e, "id");
                String x = getVal(e, "x");
                String y = getVal(e, "y");
                if (id == null) continue;
                boolean wzOk = existsInWz(padded("Reactor.wz", id, 7));
                boolean clientOk = existsInClient("Data/Reactor/" + pad7(id) + ".img");
                String status = wzOk ? (clientOk ? "OK" : "WARN") : "ERROR";
                String msg = !wzOk ? "反应堆资源缺失(服务端): Reactor.wz/" + pad7(id) + ".img.xml"
                        : (!clientOk ? "反应堆客户端资源缺失: Data/Reactor/" + pad7(id) + ".img" : "");
                addNode(c, "reactor", id, status, "反应堆 #" + id,
                        "玩家可交互的机关/采集点（触发脚本）", msg,
                        kv("x", x), kv("y", y), kv("clientOk", String.valueOf(clientOk)));
                if (wzOk) checkScriptRef(scriptRefs, "reactor", id, false);
            }
        }
        if (c.getNodes().isEmpty()) addNode(c, "reactor", "", "INFO", "无反应堆", "该地图未配置反应堆", "");
        return c;
    }

    // ---------------------------------------------------------------- portal

    private MapDetectCategoryDTO buildPortalCategory(Element root, List<MapDetectNodeDTO> scriptRefs) {
        MapDetectCategoryDTO c = newCategory("portal", "传送点", false);
        Element p = getDir(root, "portal");
        if (p != null) {
            for (Element e : getDirs(p)) {
                String pn = getVal(e, "pn");
                String pt = getVal(e, "pt");
                String tm = getVal(e, "tm");
                String tn = getVal(e, "tn");
                String script = getVal(e, "script");
                String ref = (pn != null ? pn : "portal") + " -> " + (tm != null ? tm : "?");

                int tmVal = -1;
                try {
                    tmVal = Integer.parseInt(tm);
                } catch (Exception ignore) {
                }

                String status = "OK";
                String msg = "";

                if (tmVal != SENTINEL_NO_MAP && tmVal > 0) {
                    boolean ok = mapFileExists(String.valueOf(tmVal));
                    if (!ok) {
                        status = "ERROR";
                        msg = "传送目标地图不存在: " + tm;
                    }
                }

                if (script != null && !script.isEmpty()) {
                    boolean ok = existsInScripts("portal/" + script + ".js");
                    if (!ok) {
                        status = "ERROR";
                        msg = (msg.isEmpty() ? "" : msg + "; ") + "传送脚本缺失: scripts/portal/" + script + ".js";
                    }
                    checkScriptRef(scriptRefs, "portal", script, true);
                }

                addNode(c, "portal", ref, status, "传送点 " + (pn != null ? pn : ""),
                        "连接本图与其他地图的传送点 (pn=" + pn + ", pt=" + pt + ", 目标=" + tn + ")",
                        msg, kv("pn", pn), kv("pt", pt), kv("tm", tm), kv("tn", tn), kv("script", script));
            }
        }
        if (c.getNodes().isEmpty()) addNode(c, "portal", "", "INFO", "无传送点", "该地图未配置传送点", "");
        return c;
    }

    // ---------------------------------------------------------------- obj

    private MapDetectCategoryDTO buildObjCategory(Element root) {
        MapDetectCategoryDTO c = newCategory("obj", "地图物件(Obj)", false);
        Map<String, String> oSstatus = new LinkedHashMap<>();
        Map<String, Boolean> oSclient = new LinkedHashMap<>();
        int total = 0;
        for (int L = 0; L <= 7; L++) {
            Element layer = getDir(root, String.valueOf(L));
            if (layer == null) continue;
            Element obj = getDir(layer, "obj");
            if (obj == null) continue;
            for (Element o : getDirs(obj)) {
                String oS = getVal(o, "oS");
                if (oS == null) continue;
                total++;
                oSstatus.putIfAbsent(oS, existsInWz("Map.wz/Obj/" + oS + ".img.xml") ? "OK" : "ERROR");
                oSclient.putIfAbsent(oS, existsInClient("Data/Map/Obj/" + oS + ".img"));
            }
        }
        for (Map.Entry<String, String> en : oSstatus.entrySet()) {
            boolean ok = "OK".equals(en.getValue());
            boolean clientOk = oSclient.getOrDefault(en.getKey(), true);
            String status = ok ? (clientOk ? "OK" : "WARN") : "ERROR";
            String msg = !ok ? "物件资源缺失(服务端): Map.wz/Obj/" + en.getKey() + ".img.xml"
                    : (!clientOk ? "物件客户端资源缺失: Data/Map/Obj/" + en.getKey() + ".img" : "");
            addNode(c, "obj", en.getKey(), status, "物件 " + en.getKey(),
                    "地图静态/动态物件（建筑/装饰/机关外观）", msg,
                    kv("clientOk", String.valueOf(clientOk)));
        }
        c.setTotal(Math.max(total, oSstatus.size()));
        if (c.getNodes().isEmpty()) addNode(c, "obj", "", "INFO", "无物件", "该地图未配置 Obj", "");
        return c;
    }

    // ---------------------------------------------------------------- tile (summary / INFO only)

    private MapDetectCategoryDTO buildTileCategory(Element root) {
        MapDetectCategoryDTO c = newCategory("tile", "瓦片(Tile)", true);
        Set<String> seen = new LinkedHashSet<>();
        int total = 0;
        for (int L = 0; L <= 7; L++) {
            Element layer = getDir(root, String.valueOf(L));
            if (layer == null) continue;
            Element tile = getDir(layer, "tile");
            if (tile == null) continue;
            for (Element t : getDirs(tile)) {
                String u = getVal(t, "u");
                if (u == null) continue;
                total++;
                if (seen.add(u)) {
                    boolean ok = existsInWz("Map.wz/Tile/" + u + ".img.xml");
                    // 本客户端瓦片多为通用命名，未一对一映射为文件，仅作 INFO 提示
                    String status = ok ? "OK" : "INFO";
                    String msg = ok ? "" : "瓦片资源未在 Tile.wz 找到（通用瓦片/客户端内建，通常为正常现象）";
                    addNode(c, "tile", u, status, "瓦片 " + u, "构成地图地面/墙壁的贴图单元", msg);
                }
            }
        }
        c.setTotal(total);
        if (c.getNodes().isEmpty()) addNode(c, "tile", "", "INFO", "无瓦片", "该地图未配置 Tile", "");
        return c;
    }

    // ---------------------------------------------------------------- foothold (summary)

    private MapDetectCategoryDTO buildFootholdCategory(Set<String> fhSet) {
        MapDetectCategoryDTO c = newCategory("foothold", "碰撞平台(Foothold)", true);
        c.setTotal(fhSet.size());
        if (fhSet.isEmpty()) {
            MapDetectNodeDTO node = newNode("foothold", "foothold", "", "WARN",
                    "无 Foothold", "地图没有碰撞平台，角色将无法站立/行走",
                    "该地图未定义任何 foothold");
            node.setCrashRisk("CRASH");
            c.getNodes().add(node);
            c.setWarn(c.getWarn() + 1);
        } else {
            addNode(c, "foothold", fhSet.size() + " 个", "OK", "碰撞平台",
                    "决定角色可站立/行走的地面线段", "共 " + fhSet.size() + " 个 foothold");
        }
        return c;
    }

    // ---------------------------------------------------------------- script

    private MapDetectCategoryDTO buildScriptCategory(List<MapDetectNodeDTO> scriptRefs) {
        MapDetectCategoryDTO c = newCategory("script", "脚本引用", false);
        c.setNodes(scriptRefs);
        c.setTotal(scriptRefs.size());
        for (MapDetectNodeDTO n : scriptRefs) {
            tally(c, n.getStatus());
        }
        if (scriptRefs.isEmpty()) {
            addNode(c, "script", "", "INFO", "无脚本引用", "该地图未引用任何脚本", "");
        }
        return c;
    }

    private void checkScriptRef(List<MapDetectNodeDTO> scriptRefs, String kind, String ref, boolean required) {
        boolean ok = existsInScripts(kind + "/" + ref + ".js");
        String status = ok ? "OK" : (required ? "ERROR" : "WARN");
        String msg = ok ? "" : (required ? "脚本缺失(必需): scripts/" + kind + "/" + ref + ".js"
                : "脚本缺失(可选): scripts/" + kind + "/" + ref + ".js");
        scriptRefs.add(newNode("script", "script", ref, status, "脚本(" + kind + ")",
                "地图脚本: " + kind, msg, kv("kind", kind)));
    }

    // ---------------------------------------------------------------- map info (名字 / 地区 / 怪物 / NPC)

    /**
     * 聚合"地图信息"：从 String.wz 名称表解析地图名 / 街道名，并将 life 中的怪物、NPC id 解析为中文名。
     */
    private MapInfoDTO buildMapInfo(String mapId, Set<String> mobIds, Set<String> npcIds) {
        MapInfoDTO info = new MapInfoDTO();
        info.setMapId(mapId);
        info.setName(readStringValue("String.wz/Map.img.xml", mapId, "mapName"));
        info.setRegion(readStringValue("String.wz/Map.img.xml", mapId, "streetName"));
        info.setHasMonster(!mobIds.isEmpty());

        List<MapDetectRefDTO> monsters = new ArrayList<>();
        for (String id : mobIds) {
            MapDetectRefDTO r = new MapDetectRefDTO();
            r.setId(id);
            r.setName(readStringValue("String.wz/Mob.img.xml", normalizeId(id), "name"));
            monsters.add(r);
        }
        info.setMonsters(monsters);

        List<MapDetectRefDTO> npcs = new ArrayList<>();
        for (String id : npcIds) {
            MapDetectRefDTO r = new MapDetectRefDTO();
            r.setId(id);
            r.setName(readStringValue("String.wz/Npc.img.xml", normalizeId(id), "name"));
            npcs.add(r);
        }
        info.setNpcs(npcs);
        info.setNpcCount(npcs.size());
        return info;
    }

    // ---------------------------------------------------------------- compare

    /**
     * 地图对比：检测两张地图的结构差异，快速定位崩溃点。
     * 对比维度：life（怪物/NPC）、foothold、portal、obj、back、info。
     */
    public MapCompareResultDTO compare(String rawMapIdA, String rawMapIdB) {
        MapCompareResultDTO result = new MapCompareResultDTO();
        result.setMapIdA(rawMapIdA);
        result.setMapIdB(rawMapIdB);
        List<MapCompareResultDTO.MapCompareDiffDTO> diffs = new ArrayList<>();
        result.setDiffs(diffs);

        if (rawMapIdA == null || rawMapIdA.trim().isEmpty() || rawMapIdB == null || rawMapIdB.trim().isEmpty()) {
            result.setCrashSummary("请提供两个地图 ID");
            return result;
        }
        String mapIdA = rawMapIdA.trim();
        String mapIdB = rawMapIdB.trim();

        MapDetectResultDTO detA = detect(mapIdA);
        MapDetectResultDTO detB = detect(mapIdB);

        result.setInfoA(buildCompareInfo(detA));
        result.setInfoB(buildBuildCompareInfo(detB));

        // life 差异
        Set<String> mobsA = extractLifeIds(detA, "m");
        Set<String> mobsB = extractLifeIds(detB, "m");
        Set<String> npcsA = extractLifeIds(detA, "n");
        Set<String> npcsB = extractLifeIds(detB, "n");

        addDiffIfDifferent(diffs, "life", "怪物种类", String.join(",", mobsA), String.join(",", mobsB),
                mobsA.equals(mobsB) ? null : "CRASH");
        addDiffIfDifferent(diffs, "life", "怪物数量", String.valueOf(mobCount(detA)), String.valueOf(mobCount(detB)),
                Math.abs(mobCount(detA) - mobCount(detB)) > 5 ? "DEGRADED" : null);
        addDiffIfDifferent(diffs, "life", "NPC 种类", String.join(",", npcsA), String.join(",", npcsB), null);

        // crashRisk 差异
        addDiffIfDifferent(diffs, "crash", "崩溃风险项数",
                String.valueOf(detA.getCrashRiskCount()), String.valueOf(detB.getCrashRiskCount()),
                detA.getCrashRiskCount() != detB.getCrashRiskCount() ? "CRASH" : null);

        // error 差异
        addDiffIfDifferent(diffs, "error", "错误总数",
                String.valueOf(detA.getError()), String.valueOf(detB.getError()),
                Math.abs(detA.getError() - detB.getError()) > 3 ? "DEGRADED" : null);

        // 文件大小差异
        Path fileA = resolveMapFile(mapIdA);
        Path fileB = resolveMapFile(mapIdB);
        long sizeA = 0, sizeB = 0;
        try { if (fileA != null) sizeA = Files.size(fileA); } catch (Exception ignore) {}
        try { if (fileB != null) sizeB = Files.size(fileB); } catch (Exception ignore) {}
        addDiffIfDifferent(diffs, "info", "文件大小(字节)", String.valueOf(sizeA), String.valueOf(sizeB),
                Math.abs(sizeA - sizeB) > 5000 ? "DEGRADED" : null);

        // 汇总
        long crashDiffs = diffs.stream().filter(d -> "CRASH".equals(d.getCrashRisk())).count();
        if (crashDiffs > 0) {
            result.setCrashSummary("发现 " + crashDiffs + " 项关键差异可能导致崩溃");
        } else {
            result.setCrashSummary("未发现关键结构差异（崩溃可能在二进制层面）");
        }

        return result;
    }

    private MapCompareResultDTO.MapCompareInfoDTO buildCompareInfo(MapDetectResultDTO det) {
        MapCompareResultDTO.MapCompareInfoDTO info = new MapCompareResultDTO.MapCompareInfoDTO();
        info.setMapId(det.getMapId());
        info.setMapExists(det.isMapExists());
        info.setCrashRiskCount(det.getCrashRiskCount());
        if (!det.isMapExists()) return info;

        for (MapDetectCategoryDTO c : det.getCategories()) {
            switch (c.getCategory()) {
                case "mob" -> info.setMobCount((int) c.getNodes().stream()
                        .filter(n -> !"无怪物".equals(n.getTitle())).count());
                case "npc" -> info.setNpcCount((int) c.getNodes().stream()
                        .filter(n -> !"无 NPC".equals(n.getTitle()) && !"无NPC".equals(n.getTitle())).count());
                case "portal" -> info.setPortalCount(c.getTotal());
                case "obj" -> info.setObjCount(c.getTotal());
                case "back" -> info.setBackCount(c.getTotal());
                case "foothold" -> info.setFhCount(c.getTotal());
            }
        }
        info.setLifeCount(info.getMobCount() + info.getNpcCount());

        // 文件大小
        Path f = resolveMapFile(det.getMapId());
        try { if (f != null) info.setFileSize((int) Files.size(f)); } catch (Exception ignore) {}

        return info;
    }

    /** 从检测结果中提取 life 类型集合 */
    private Set<String> extractLifeIds(MapDetectResultDTO det, String type) {
        Set<String> ids = new LinkedHashSet<>();
        for (MapDetectCategoryDTO c : det.getCategories()) {
            if ("mob".equals(c.getCategory()) && "m".equals(type)) {
                for (MapDetectNodeDTO n : c.getNodes()) {
                    if (n.getRef() != null && !n.getRef().isEmpty() && !"无怪物".equals(n.getTitle()))
                        ids.add(n.getRef());
                }
            }
            if ("npc".equals(c.getCategory()) && "n".equals(type)) {
                for (MapDetectNodeDTO n : c.getNodes()) {
                    if (n.getRef() != null && !n.getRef().isEmpty() && !"无 NPC".equals(n.getTitle()))
                        ids.add(n.getRef());
                }
            }
        }
        return ids;
    }

    private int mobCount(MapDetectResultDTO det) {
        for (MapDetectCategoryDTO c : det.getCategories()) {
            if ("mob".equals(c.getCategory())) {
                return (int) c.getNodes().stream()
                        .filter(n -> n.getRef() != null && !n.getRef().isEmpty() && !"无怪物".equals(n.getTitle()))
                        .count();
            }
        }
        return 0;
    }

    private void addDiffIfDifferent(List<MapCompareResultDTO.MapCompareDiffDTO> diffs,
                                    String category, String desc, String va, String vb, String crashRisk) {
        if (va.equals(vb)) return;
        MapCompareResultDTO.MapCompareDiffDTO d = new MapCompareResultDTO.MapCompareDiffDTO();
        d.setCategory(category);
        d.setDescription(desc);
        d.setValueA(va);
        d.setValueB(vb);
        d.setCrashRisk(crashRisk);
        diffs.add(d);
    }

    private MapCompareResultDTO.MapCompareInfoDTO buildBuildCompareInfo(MapDetectResultDTO det) {
        return buildCompareInfo(det);
    }

    /** 地区 key → 中文显示名（String.wz/Map.img 的顶层 imgdir 名） */
    private static final Map<String, String> REGION_NAMES = Map.ofEntries(
            Map.entry("victoria", "金银岛"),
            Map.entry("ossyria", "神秘岛"),
            Map.entry("elin", "艾琳森林"),
            Map.entry("china", "东方神州"),
            Map.entry("jp", "日本"),
            Map.entry("thai", "泰国"),
            Map.entry("singapore", "新加坡·马来西亚"),
            Map.entry("maple", "彩虹岛"),
            Map.entry("MasteriaGL", "马斯特里亚"),
            Map.entry("weddingGL", "婚礼村"),
            Map.entry("HalloweenGL", "万圣节"),
            Map.entry("Episode1GL", "剧情活动"),
            Map.entry("event", "活动地图"),
            Map.entry("etc", "其他"),
            Map.entry("grandis", "格兰蒂斯"));

    /** 地图目录树缓存（按 zh-CN 与 wz 两份 Map.img.xml 的组合修改时间失效） */
    private volatile List<MapTreeItemDTO> mapTreeCache;
    private volatile long mapTreeCacheMod;

    /**
     * 构建地图目录树：大地区 → 城镇/街道 → 具体地图。
     *
     * <p>数据来源 String.wz/Map.img.xml，合并 wz-zh-CN（优先，中文名）与 wz（补齐 zh-CN 缺失的地图），
     * 并递归展开 china/chinese 等嵌套分组节点。叶子 value 为 9 位补零地图 id，
     * 与 Map.wz 文件名一致，选中后可直接传给 {@link #detect(String)}。</p>
     */
    public synchronized List<MapTreeItemDTO> buildMapTree() {
        Path zhPath = Paths.get(baseDir, "wz-zh-CN", "String.wz", "Map.img.xml");
        Path wzPath = Paths.get(baseDir, "wz", "String.wz", "Map.img.xml");
        long zhMod = 0, wzMod = 0;
        try {
            if (Files.exists(zhPath)) zhMod = Files.getLastModifiedTime(zhPath).toMillis();
            if (Files.exists(wzPath)) wzMod = Files.getLastModifiedTime(wzPath).toMillis();
        } catch (IOException e) {
            // 忽略，走解析
        }
        if (zhMod == 0 && wzMod == 0) return new ArrayList<>();
        long cacheKey = zhMod * 31 + wzMod;
        if (mapTreeCache != null && mapTreeCacheMod == cacheKey) return mapTreeCache;
        try {
            // 地区 key → (9位地图id → [mapName, streetName])，LinkedHashMap 保持文件顺序，zh-CN 优先
            LinkedHashMap<String, LinkedHashMap<String, String[]>> merged = new LinkedHashMap<>();
            for (Path p : new Path[]{zhPath, wzPath}) {
                if (!Files.exists(p)) continue;
                Document doc = loadDoc(p);
                for (Element regionEl : getDirs(doc.getDocumentElement())) {
                    LinkedHashMap<String, String[]> maps =
                            merged.computeIfAbsent(regionEl.getAttribute("name"), k -> new LinkedHashMap<>());
                    collectMaps(regionEl, maps);
                }
            }
            List<MapTreeItemDTO> tree = buildTreeFromMerged(merged);
            mapTreeCache = tree;
            mapTreeCacheMod = cacheKey;
            return tree;
        } catch (Exception e) {
            log.warn("解析地图目录树失败: {}", e.getMessage());
            return new ArrayList<>();
        }
    }

    /**
     * 递归收集地区（或其嵌套分组，如 china/chinese 含 642 张地图）下全部地图节点。
     * 分组节点自身若带 mapName 也视为一张地图（如 victoria/106021800）。已存在的 id 不覆盖。
     */
    private void collectMaps(Element el, LinkedHashMap<String, String[]> out) {
        List<Element> children = getDirs(el);
        if (children.isEmpty()) {
            addMapNode(el, out);
            return;
        }
        String mapName = getVal(el, "mapName");
        if (mapName != null && !mapName.isEmpty()) addMapNode(el, out);
        for (Element c : children) collectMaps(c, out);
    }

    /** 把单个地图节点加入收集表（非法 id 或重复 id 跳过）。 */
    private void addMapNode(Element el, LinkedHashMap<String, String[]> out) {
        String id = pad9(el.getAttribute("name"));
        if (id == null || out.containsKey(id)) return;
        String mapName = getVal(el, "mapName");
        String streetName = getVal(el, "streetName");
        out.put(id, new String[]{
                (mapName == null || mapName.isEmpty()) ? "(无名地图)" : mapName,
                (streetName == null || streetName.isEmpty()) ? "" : streetName});
    }

    /** 把合并后的 地区→(地图id→[名,街道]) 原始数据组装为三级树（同 id 跨地区只保留首次出现）。 */
    private List<MapTreeItemDTO> buildTreeFromMerged(LinkedHashMap<String, LinkedHashMap<String, String[]>> merged) {
        List<MapTreeItemDTO> regions = new ArrayList<>();
        Set<String> seenIds = new HashSet<>();
        for (Map.Entry<String, LinkedHashMap<String, String[]>> re : merged.entrySet()) {
            String key = re.getKey();
            LinkedHashMap<String, List<MapTreeItemDTO>> streets = new LinkedHashMap<>();
            for (Map.Entry<String, String[]> me : re.getValue().entrySet()) {
                String id = me.getKey();
                if (!seenIds.add(id)) continue;
                MapTreeItemDTO leaf = new MapTreeItemDTO();
                leaf.setValue(id);
                leaf.setLabel(me.getValue()[0] + " (" + id + ")");
                leaf.setIsLeaf(true);
                String street = me.getValue()[1].isEmpty() ? "(未知街道)" : me.getValue()[1];
                streets.computeIfAbsent(street, k -> new ArrayList<>()).add(leaf);
            }
            if (streets.isEmpty()) continue;
            List<MapTreeItemDTO> streetNodes = new ArrayList<>();
            int total = 0;
            for (Map.Entry<String, List<MapTreeItemDTO>> se : streets.entrySet()) {
                MapTreeItemDTO s = new MapTreeItemDTO();
                s.setValue(key + "/" + se.getKey());
                s.setLabel(se.getKey() + " (" + se.getValue().size() + ")");
                s.setCount(se.getValue().size());
                s.setChildren(se.getValue());
                streetNodes.add(s);
                total += se.getValue().size();
            }
            MapTreeItemDTO region = new MapTreeItemDTO();
            region.setValue(key);
            region.setLabel(REGION_NAMES.getOrDefault(key, key) + " (" + total + ")");
            region.setCount(total);
            region.setChildren(streetNodes);
            regions.add(region);
        }
        return regions;
    }

    /** 补零为 9 位地图 id（与 Map.wz 文件名一致）；非法输入返回 null。 */
    private String pad9(String id) {
        if (id == null) return null;
        try {
            return String.format("%09d", Long.parseLong(id.trim()));
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 从 String.wz 名称表读取某 id 下的字段值（优先 wz-zh-CN，回退 wz）。
     */
    private String readStringValue(String imgRel, String id, String field) {
        for (String base : new String[]{"wz-zh-CN", "wz"}) {
            Path p = Paths.get(baseDir, base, imgRel);
            if (!Files.exists(p)) continue;
            try {
                Document doc = loadDoc(p);
                String v = findStringInTree(doc.getDocumentElement(), id, field);
                if (v != null) return v;
            } catch (Exception e) {
                log.warn("读取名称表失败 {}/{} id={}: {}", base, imgRel, id, e.getMessage());
            }
        }
        return null;
    }

    /** 在整棵 XML 树中查找 name==dirName 的 imgdir，并返回其下 name==strName 的字符串值（DFS，返回首个命中）。 */
    private String findStringInTree(Element root, String dirName, String strName) {
        if (root == null) return null;
        Deque<Element> stack = new ArrayDeque<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            Element cur = stack.pop();
            if ("imgdir".equals(cur.getTagName()) && dirName.equals(cur.getAttribute("name"))) {
                String v = getVal(cur, strName);
                if (v != null) return v;
            }
            NodeList nl = cur.getChildNodes();
            for (int i = 0; i < nl.getLength(); i++) {
                Node n = nl.item(i);
                if (n.getNodeType() == Node.ELEMENT_NODE) {
                    stack.push((Element) n);
                }
            }
        }
        return null;
    }

    /** 解析并缓存 XML 文档（按路径 + 最后修改时间失效）。 */
    private Document loadDoc(Path p) throws ParserConfigurationException, SAXException, IOException {
        long mod = Files.getLastModifiedTime(p).toMillis();
        DocCache c = docCache.get(p.toString());
        if (c != null && c.modified == mod) {
            return c.doc;
        }
        Document doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(p.toFile());
        docCache.put(p.toString(), new DocCache(mod, doc));
        return doc;
    }

    /** 去掉 id 前导零（地图 life 节点用 7 位补零 id，而名称表以整数形式存储，需归一化后查表）。 */
    private String normalizeId(String id) {
        if (id == null) return null;
        try {
            return String.valueOf(Integer.parseInt(id.trim()));
        } catch (Exception e) {
            return id;
        }
    }

    // ---------------------------------------------------------------- helpers

    private MapDetectCategoryDTO newCategory(String cat, String label, boolean summaryOnly) {
        MapDetectCategoryDTO c = new MapDetectCategoryDTO();
        c.setCategory(cat);
        c.setLabel(label);
        c.setSummaryOnly(summaryOnly);
        c.setNodes(new ArrayList<>());
        c.setTotal(0);
        c.setOk(0);
        c.setWarn(0);
        c.setError(0);
        c.setInfo(0);
        return c;
    }

    private void addNode(MapDetectCategoryDTO c, String refType, String ref, String status, String title,
                         String func, String msg, Map.Entry<String, String>... metas) {
        MapDetectNodeDTO n = new MapDetectNodeDTO();
        n.setCategory(c.getCategory());
        n.setRefType(refType);
        n.setRef(ref);
        n.setStatus(status);
        n.setTitle(title);
        n.setFunctionDesc(func);
        n.setMessage(msg == null ? "" : msg);
        if (metas != null && metas.length > 0) {
            Map<String, String> m = new LinkedHashMap<>();
            for (Map.Entry<String, String> e : metas) {
                if (e != null) m.put(e.getKey(), e.getValue());
            }
            if (!m.isEmpty()) n.setMeta(m);
        }
        c.getNodes().add(n);
        c.setTotal(c.getTotal() + 1);
        tally(c, status);
    }

    private MapDetectNodeDTO newNode(String category, String refType, String ref, String status, String title,
                                     String func, String msg, Map.Entry<String, String>... metas) {
        MapDetectNodeDTO n = new MapDetectNodeDTO();
        n.setCategory(category);
        n.setRefType(refType);
        n.setRef(ref);
        n.setStatus(status);
        n.setTitle(title);
        n.setFunctionDesc(func);
        n.setMessage(msg == null ? "" : msg);
        if (metas != null && metas.length > 0) {
            Map<String, String> m = new LinkedHashMap<>();
            for (Map.Entry<String, String> e : metas) {
                if (e != null) m.put(e.getKey(), e.getValue());
            }
            if (!m.isEmpty()) n.setMeta(m);
        }
        return n;
    }

    private void tally(MapDetectCategoryDTO c, String status) {
        if ("OK".equals(status)) c.setOk(c.getOk() + 1);
        else if ("WARN".equals(status)) c.setWarn(c.getWarn() + 1);
        else if ("ERROR".equals(status)) c.setError(c.getError() + 1);
        else if ("INFO".equals(status)) c.setInfo(c.getInfo() + 1);
    }

    private Map.Entry<String, String> kv(String k, String v) {
        return v == null ? null : new AbstractMap.SimpleEntry<>(k, v);
    }

    /**
     * 收集地图中所有有效的 Foothold ID。
     * Foothold XML 结构为 4 层：foothold → group → platform → individual(fh)。
     * life 节点的 fh 引用的是第三层 individual foothold 的 name。
     */
    private Set<String> collectFootholds(Element root) {
        Set<String> set = new HashSet<>();
        Element fh = getDir(root, "foothold");
        if (fh != null) {
            for (Element group : getDirs(fh)) {
                for (Element platform : getDirs(group)) {
                    for (Element entry : getDirs(platform)) {
                        set.add(entry.getAttribute("name"));
                    }
                }
            }
        }
        return set;
    }

    private Element getDir(Element parent, String name) {
        if (parent == null) return null;
        NodeList nl = parent.getChildNodes();
        for (int i = 0; i < nl.getLength(); i++) {
            Node n = nl.item(i);
            if (n.getNodeType() == Node.ELEMENT_NODE) {
                Element e = (Element) n;
                if ("imgdir".equals(e.getTagName()) && name.equals(e.getAttribute("name"))) {
                    return e;
                }
            }
        }
        return null;
    }

    private List<Element> getDirs(Element parent) {
        List<Element> out = new ArrayList<>();
        if (parent == null) return out;
        NodeList nl = parent.getChildNodes();
        for (int i = 0; i < nl.getLength(); i++) {
            Node n = nl.item(i);
            if (n.getNodeType() == Node.ELEMENT_NODE) {
                Element e = (Element) n;
                if ("imgdir".equals(e.getTagName())) {
                    out.add(e);
                }
            }
        }
        return out;
    }

    private String getVal(Element parent, String attrName) {
        if (parent == null) return null;
        NodeList nl = parent.getChildNodes();
        for (int i = 0; i < nl.getLength(); i++) {
            Node n = nl.item(i);
            if (n.getNodeType() == Node.ELEMENT_NODE) {
                Element e = (Element) n;
                if (attrName.equals(e.getAttribute("name"))) {
                    return e.getAttribute("value");
                }
            }
        }
        return null;
    }

    private int getInt(Element parent, String attrName, int def) {
        String v = getVal(parent, attrName);
        if (v == null || v.isEmpty()) return def;
        try {
            return Integer.parseInt(v);
        } catch (Exception e) {
            return def;
        }
    }

    private String firstDigit(String mapId) {
        if (mapId == null || mapId.isEmpty()) return "0";
        char c = mapId.charAt(0);
        return Character.isDigit(c) ? String.valueOf(c) : "0";
    }

    private Path resolveMapFile(String mapId) {
        String fd = firstDigit(mapId);
        Path p = Paths.get(baseDir, "wz-zh-CN", "Map.wz", "Map", "Map" + fd, mapId + ".img.xml");
        if (Files.exists(p)) return p;
        return Paths.get(baseDir, "wz", "Map.wz", "Map", "Map" + fd, mapId + ".img.xml");
    }

    private boolean mapFileExists(String id) {
        String fd = firstDigit(id);
        return Files.exists(Paths.get(baseDir, "wz-zh-CN", "Map.wz", "Map", "Map" + fd, id + ".img.xml"))
                || Files.exists(Paths.get(baseDir, "wz", "Map.wz", "Map", "Map" + fd, id + ".img.xml"));
    }

    private String padded(String dir, String id, int len) {
        try {
            int v = Integer.parseInt(id);
            return dir + "/" + String.format("%0" + len + "d", v) + ".img.xml";
        } catch (Exception e) {
            return dir + "/" + id + ".img.xml";
        }
    }

    private String pad7(String id) {
        try {
            return String.format("%07d", Integer.parseInt(id));
        } catch (Exception e) {
            return id;
        }
    }

    private boolean existsInWz(String rel) {
        if (Files.exists(Paths.get(baseDir, "wz-zh-CN", rel))) return true;
        return Files.exists(Paths.get(baseDir, "wz", rel));
    }

    /** 检查客户端 Data/ 目录下是否存在指定的 .img 文件（相对于项目根目录的 clien/） */
    private boolean existsInClient(String rel) {
        return Files.exists(Paths.get(baseDir, "clien", rel));
    }

    /** 检查客户端 Data/ 目录下是否存在指定的 .img 文件（相对于项目根目录的 clien/）—— pad7 版本 */
    private boolean existsInClientPadded(String dir, String id, int len) {
        try {
            int v = Integer.parseInt(id);
            return Files.exists(Paths.get(baseDir, "clien", "Data", dir, String.format("%0" + len + "d", v) + ".img"));
        } catch (Exception e) {
            return Files.exists(Paths.get(baseDir, "clien", "Data", dir, id + ".img"));
        }
    }

    private boolean existsInScripts(String rel) {
        if (Files.exists(Paths.get(baseDir, "scripts-zh-CN", rel))) return true;
        return Files.exists(Paths.get(baseDir, "scripts", rel));
    }

    private boolean soundNodeExists(String filePart, String nodePart) {
        Path p = Paths.get(baseDir, "wz-zh-CN", "Sound.wz", filePart + ".img.xml");
        if (!Files.exists(p)) p = Paths.get(baseDir, "wz", "Sound.wz", filePart + ".img.xml");
        if (!Files.exists(p)) return false;
        try {
            String content = new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
            return content.contains("name=\"" + nodePart + "\"");
        } catch (IOException e) {
            return false;
        }
    }
}
