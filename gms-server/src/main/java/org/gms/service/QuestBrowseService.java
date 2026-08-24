package org.gms.service;

import lombok.extern.slf4j.Slf4j;
import org.gms.model.dto.MapTreeItemDTO;
import org.gms.model.dto.QuestChainItemDTO;
import org.gms.model.dto.QuestDetailDTO;
import org.gms.model.dto.QuestSummaryDTO;
import org.springframework.stereotype.Service;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 任务浏览服务。
 *
 * <p>数据来源（均为服务端 XML，只读解析，不修改任何 WZ）：
 * <ul>
 *   <li>{@code wz-zh-CN/Quest.wz/QuestInfo.img.xml} —— 任务名 / 三段任务内容 / 链组名(parent) / 链内序号(order)；</li>
 *   <li>{@code wz-zh-CN/Quest.wz/Check.img.xml} —— Check/0 的 npc(起始)/lvmin/lvmax、Check/1 的 npc(结束)；</li>
 *   <li>{@code wz-zh-CN/Quest.wz/Act.img.xml} —— nextQuest（后继任务引用）；</li>
 *   <li>{@code wz-zh-CN,String.wz/Npc.img.xml} —— NPC 中文名；</li>
 *   <li>{@code wz-zh-CN,String.wz/Map.img.xml + wz/String.wz/Map.img.xml} —— 地区→地图→街道名（合并、zh-CN 优先）；</li>
 *   <li>{@code wz/Map.wz/Map} 下全部地图 XML —— life 节点扫描，建立 NPC→所在地图 索引。</li>
 * </ul>
 * 地区归属方案：任务起始 NPC → 出现该 NPC 的地图（多个时优先街道名明确的）→ 该地图的地区/街道。
 * 全量索引懒加载、进程内缓存（Map.wz 共 5884 个地图文件，字节级扫描约 1~2 秒，仅首次请求触发）。</p>
 */
@Slf4j
@Service
public class QuestBrowseService {

    private final String baseDir = System.getProperty("user.dir");

    /** 无法通过起始 NPC 定位地区的任务，归入该伪地区 */
    private static final String UNKNOWN_REGION = "unknown";
    private static final String UNKNOWN_REGION_LABEL = "未定位";
    private static final String UNKNOWN_STREET = "(未知街道)";

    /** 地区 key → 中文显示名（与 MapDetectService 保持一致） */
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

    // ---------------------------------------------------------------- 索引

    /** 单条任务记录（内部结构，聚合后转 DTO） */
    private static class QuestRecord {
        String questId;
        String name;
        Integer levelMin;
        Integer levelMax;
        String startNpcId;
        String endNpcId;
        String contentStart;
        String contentProgress;
        String contentComplete;
        String parentName;
        Integer order;
        String nextQuestId;
        String region;
        String town;
    }

    /** 全量索引（懒加载、进程内缓存） */
    private static class QuestIndex {
        List<QuestRecord> quests = new ArrayList<>();
        Map<String, QuestRecord> byId = new HashMap<>();
        /** 链组名 → 按序号排序的任务 id 列表 */
        Map<String, List<String>> chainGroups = new LinkedHashMap<>();
        /** 被其它任务 nextQuest 引用的任务 id（用于 inChain 判断） */
        Set<String> nextQuestTargets = new HashSet<>();
    }

    private volatile QuestIndex indexCache;

    private QuestIndex index() {
        QuestIndex idx = indexCache;
        if (idx != null) return idx;
        synchronized (this) {
            if (indexCache == null) {
                long t0 = System.currentTimeMillis();
                indexCache = buildIndex();
                log.info("QuestBrowse 索引构建完成: {} 个任务, 耗时 {}ms",
                        indexCache.quests.size(), System.currentTimeMillis() - t0);
            }
            return indexCache;
        }
    }

    private QuestIndex buildIndex() {
        QuestIndex idx = new QuestIndex();
        try {
            // 1. 地图目录（地区→地图→街道），zh-CN 优先合并 wz
            Map<String, String[]> mapLookup = buildMapLookup();
            // 2. NPC → 所在地图集合（字节级扫描 Map.wz life 节点）
            Map<String, Set<String>> npcMaps = scanNpcLocations();
            // 3. NPC id → 中文名（预热点缓存）
            buildNpcNames();
            // 4. 任务主数据 + 起止 NPC + nextQuest
            loadQuestInfo(idx);
            loadCheck(idx);
            loadAct(idx);
            // 5. 地区归属 + 链组聚合
            attribute(idx, mapLookup, npcMaps);
            aggregateChains(idx);
        } catch (Exception e) {
            log.error("QuestBrowse 索引构建失败", e);
        }
        return idx;
    }

    // ---------------------------------------------------------------- 对外接口

    /**
     * 任务地区树：大地区 → 城镇/街道（两级，带任务数）。
     * 无法定位的任务归入"未定位"伪地区（value=unknown）。
     */
    public List<MapTreeItemDTO> townTree() {
        QuestIndex idx = index();
        // region key → (town → count)，保持地区在 Map.img 中的顺序 + 未定位放最后
        Map<String, LinkedHashMap<String, Integer>> regions = new LinkedHashMap<>();
        for (QuestRecord q : idx.quests) {
            String region = q.region != null ? q.region : UNKNOWN_REGION;
            String town = q.town != null ? q.town : UNKNOWN_STREET;
            regions.computeIfAbsent(region, k -> new LinkedHashMap<>())
                    .merge(town, 1, Integer::sum);
        }
        List<MapTreeItemDTO> out = new ArrayList<>();
        for (Map.Entry<String, LinkedHashMap<String, Integer>> re : regions.entrySet()) {
            String key = re.getKey();
            List<MapTreeItemDTO> towns = new ArrayList<>();
            re.getValue().entrySet().stream()
                    .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                    .forEach(te -> {
                        MapTreeItemDTO t = new MapTreeItemDTO();
                        t.setValue(te.getKey());
                        t.setLabel(te.getKey() + " (" + te.getValue() + ")");
                        t.setCount(te.getValue());
                        t.setIsLeaf(true);
                        towns.add(t);
                    });
            int total = towns.stream().mapToInt(MapTreeItemDTO::getCount).sum();
            MapTreeItemDTO region = new MapTreeItemDTO();
            region.setValue(key);
            region.setLabel(regionLabel(key) + " (" + total + ")");
            region.setCount(total);
            region.setChildren(towns);
            out.add(region);
        }
        return out;
    }

    /**
     * 任务列表：按地区/城镇筛选，按最低等级（无等级限制的排最前）→ 任务 id 排序。
     *
     * @param region 地区 key（空=全部）
     * @param town   城镇/街道名（空=该地区全部）
     */
    public List<QuestSummaryDTO> list(String region, String town) {
        QuestIndex idx = index();
        List<QuestRecord> records = new ArrayList<>();
        for (QuestRecord q : idx.quests) {
            String qRegion = q.region != null ? q.region : UNKNOWN_REGION;
            String qTown = q.town != null ? q.town : UNKNOWN_STREET;
            if (region != null && !region.isEmpty() && !region.equals(qRegion)) continue;
            if (town != null && !town.isEmpty() && !town.equals(qTown)) continue;
            records.add(q);
        }
        records.sort(Comparator
                .comparing((QuestRecord q) -> q.levelMin == null ? 0 : q.levelMin)
                .thenComparingInt(q -> Integer.parseInt(q.questId)));
        Map<String, String> npcNames = buildNpcNamesLazy(idx);
        List<QuestSummaryDTO> out = new ArrayList<>(records.size());
        for (QuestRecord q : records) {
            QuestSummaryDTO dto = new QuestSummaryDTO();
            dto.setQuestId(q.questId);
            dto.setName(q.name);
            dto.setLevelMin(q.levelMin);
            dto.setLevelMax(q.levelMax);
            dto.setStartNpcId(q.startNpcId);
            dto.setStartNpcName(npcNames.get(q.startNpcId));
            dto.setEndNpcId(q.endNpcId);
            dto.setEndNpcName(npcNames.get(q.endNpcId));
            dto.setInChain(isInChain(idx, q));
            dto.setRegion(q.region != null ? q.region : UNKNOWN_REGION);
            dto.setTown(q.town != null ? q.town : UNKNOWN_STREET);
            out.add(dto);
        }
        return out;
    }

    /**
     * 任务详情：含三段任务内容与任务链（同 parent 组按 order 排序；无链时仅含自身）。
     */
    public QuestDetailDTO detail(String questId) {
        QuestIndex idx = index();
        if (questId == null || questId.trim().isEmpty()) return null;
        QuestRecord q = idx.byId.get(questId.trim());
        if (q == null) return null;
        Map<String, String> npcNames = buildNpcNamesLazy(idx);

        QuestDetailDTO dto = new QuestDetailDTO();
        dto.setQuestId(q.questId);
        dto.setName(q.name);
        dto.setLevelMin(q.levelMin);
        dto.setLevelMax(q.levelMax);
        dto.setStartNpcId(q.startNpcId);
        dto.setStartNpcName(npcNames.get(q.startNpcId));
        dto.setEndNpcId(q.endNpcId);
        dto.setEndNpcName(npcNames.get(q.endNpcId));
        dto.setContentStart(q.contentStart);
        dto.setContentProgress(q.contentProgress);
        dto.setContentComplete(q.contentComplete);
        dto.setParentName(q.parentName);
        dto.setOrder(q.order);
        dto.setRegion(q.region != null ? q.region : UNKNOWN_REGION);
        dto.setTown(q.town != null ? q.town : UNKNOWN_STREET);

        List<QuestChainItemDTO> chain = new ArrayList<>();
        List<String> members = q.parentName != null ? idx.chainGroups.get(q.parentName) : null;
        if (members == null || members.isEmpty()) {
            members = Collections.singletonList(q.questId);
        }
        for (String mid : members) {
            QuestRecord m = idx.byId.get(mid);
            if (m == null) continue;
            QuestChainItemDTO item = new QuestChainItemDTO();
            item.setQuestId(m.questId);
            item.setName(m.name);
            item.setLevelMin(m.levelMin);
            item.setCurrent(m.questId.equals(q.questId));
            chain.add(item);
        }
        dto.setChain(chain);
        return dto;
    }

    // ---------------------------------------------------------------- 数据装载

    /** QuestInfo：任务名 / 三段内容 / parent / order。QuestInfo 中存在的任务为全集。 */
    private void loadQuestInfo(QuestIndex idx) throws Exception {
        Document doc = loadDoc(Paths.get(baseDir, "wz-zh-CN", "Quest.wz", "QuestInfo.img.xml"));
        for (Element q : getDirs(doc.getDocumentElement())) {
            QuestRecord r = new QuestRecord();
            r.questId = q.getAttribute("name");
            r.name = orEmpty(getVal(q, "name"));
            r.contentStart = getVal(q, "0");
            r.contentProgress = getVal(q, "1");
            r.contentComplete = getVal(q, "2");
            r.parentName = getVal(q, "parent");
            r.order = getInt(q, "order", null);
            idx.quests.add(r);
            idx.byId.put(r.questId, r);
        }
    }

    /** Check：Check/0 的 npc(起始)/lvmin/lvmax，Check/1 的 npc(结束)。 */
    private void loadCheck(QuestIndex idx) throws Exception {
        Document doc = loadDoc(Paths.get(baseDir, "wz-zh-CN", "Quest.wz", "Check.img.xml"));
        for (Element q : getDirs(doc.getDocumentElement())) {
            QuestRecord r = idx.byId.get(q.getAttribute("name"));
            if (r == null) continue;
            Element start = getDir(q, "0");
            if (start != null) {
                r.startNpcId = getVal(start, "npc");
                r.levelMin = getInt(start, "lvmin", null);
                r.levelMax = getInt(start, "lvmax", null);
            }
            Element end = getDir(q, "1");
            if (end != null) {
                r.endNpcId = getVal(end, "npc");
            }
        }
    }

    /** Act：nextQuest（后继任务引用，取首次出现）。 */
    private void loadAct(QuestIndex idx) throws Exception {
        Document doc = loadDoc(Paths.get(baseDir, "wz-zh-CN", "Quest.wz", "Act.img.xml"));
        for (Element q : getDirs(doc.getDocumentElement())) {
            QuestRecord r = idx.byId.get(q.getAttribute("name"));
            if (r == null) continue;
            for (Element act : getDirs(q)) {
                String nq = getVal(act, "nextQuest");
                if (nq != null && !nq.isEmpty()) {
                    r.nextQuestId = nq;
                    break;
                }
            }
        }
    }

    /**
     * 合并 wz-zh-CN 与 wz 的 String.wz/Map.img.xml：递归展开嵌套分组，
     * 得到 无前导零地图id → [地图名, 街道名]，同时填充 regionOfMap（地图id → 地区 key）。
     */
    private Map<String, String[]> buildMapLookup() throws Exception {
        Map<String, String[]> lookup = new HashMap<>();
        Set<String> seen = new HashSet<>();
        for (String base : new String[]{"wz-zh-CN", "wz"}) {
            Path p = Paths.get(baseDir, base, "String.wz", "Map.img.xml");
            if (!Files.exists(p)) continue;
            Document doc = loadDoc(p);
            for (Element regionEl : getDirs(doc.getDocumentElement())) {
                String regionKey = regionEl.getAttribute("name");
                collectMapNodes(regionEl, regionKey, lookup, seen);
            }
        }
        return lookup;
    }

    /** 递归收集地区（含 china/chinese 等嵌套分组）下的地图节点；分组节点自带 mapName 时也算一张地图。 */
    private void collectMapNodes(Element el, String regionKey, Map<String, String[]> out, Set<String> seen) {
        List<Element> children = getDirs(el);
        addMapNode(el, regionKey, out, seen);
        for (Element c : children) collectMapNodes(c, regionKey, out, seen);
    }

    private void addMapNode(Element el, String regionKey, Map<String, String[]> out, Set<String> seen) {
        String raw = el.getAttribute("name");
        String key = normalizeId(raw);
        if (key == null || !seen.add(key)) return;
        String street = getVal(el, "streetName");
        String mapName = getVal(el, "mapName");
        out.put(key, new String[]{
                (mapName == null || mapName.isEmpty()) ? "(无名地图)" : mapName,
                (street == null || street.isEmpty()) ? UNKNOWN_STREET : street});
        regionOfMap.put(key, regionKey);
    }

    /**
     * 字节级扫描 wz/Map.wz 全部地图 XML 的 life 节点，建立 NPC id → 所在地图集合。
     * life 子项为扁平结构（只含 string 值），用非贪婪正则逐项提取 type/id；
     * 以 ISO-8859-1 1:1 映射读字节（仅匹配 ASCII 属性名与数字 id，不受 UTF-8 中文影响）。
     */
    private Map<String, Set<String>> scanNpcLocations() throws IOException {
        Map<String, Set<String>> npcMaps = new HashMap<>();
        Path mapDir = Paths.get(baseDir, "wz", "Map.wz", "Map");
        if (!Files.isDirectory(mapDir)) return npcMaps;
        byte[] marker = "<imgdir name=\"life\">".getBytes(StandardCharsets.ISO_8859_1);
        Pattern entryP = Pattern.compile("<imgdir name=\"[^\"]+\">(.*?)</imgdir>", Pattern.DOTALL);
        Pattern typeP = Pattern.compile("<string name=\"type\" value=\"([^\"]*)\"");
        Pattern idP = Pattern.compile("<string name=\"id\" value=\"([^\"]*)\"");
        int files = 0;
        try (DirectoryStream<Path> subs = Files.newDirectoryStream(mapDir)) {
            for (Path sub : subs) {
                if (!Files.isDirectory(sub)) continue;
                try (DirectoryStream<Path> mapFiles = Files.newDirectoryStream(sub, "*.img.xml")) {
                    for (Path f : mapFiles) {
                        files++;
                        byte[] data = Files.readAllBytes(f);
                        int i = indexOf(data, marker);
                        if (i < 0) continue;
                        String mid = normalizeId(fileNameBase(f));
                        if (mid == null) continue;
                        int end = findSectionEnd(data, i);
                        String section = new String(data, i, end - i, StandardCharsets.ISO_8859_1);
                        Matcher m = entryP.matcher(section);
                        while (m.find()) {
                            String body = m.group(1);
                            Matcher tm = typeP.matcher(body);
                            Matcher im = idP.matcher(body);
                            if (tm.find() && im.find() && "n".equals(tm.group(1))) {
                                npcMaps.computeIfAbsent(im.group(1), k -> new HashSet<>()).add(mid);
                            }
                        }
                    }
                }
            }
        }
        log.info("QuestBrowse NPC 位置扫描: {} 个地图文件, {} 个 NPC", files, npcMaps.size());
        return npcMaps;
    }

    /** NPC id → 中文名（zh-CN 优先，wz 补齐；两份 Npc.img.xml 合并后缓存于索引调用侧）。 */
    private Map<String, String> npcNameCache;

    private synchronized Map<String, String> buildNpcNames() {
        return buildNpcNames0();
    }

    private Map<String, String> buildNpcNamesLazy(QuestIndex idx) {
        Map<String, String> names = npcNameCache;
        if (names == null) {
            synchronized (this) {
                if (npcNameCache == null) npcNameCache = buildNpcNames0();
                names = npcNameCache;
            }
        }
        return names;
    }

    private Map<String, String> buildNpcNames0() {
        Map<String, String> names = new HashMap<>();
        for (String base : new String[]{"wz", "wz-zh-CN"}) {
            // 先 wz 打底、zh-CN 覆盖（zh-CN 优先）
            Path p = Paths.get(baseDir, base, "String.wz", "Npc.img.xml");
            if (!Files.exists(p)) continue;
            try {
                Document doc = loadDoc(p);
                for (Element n : getDirs(doc.getDocumentElement())) {
                    String v = getVal(n, "name");
                    if (v != null && !v.isEmpty()) names.put(n.getAttribute("name"), v);
                }
            } catch (Exception e) {
                log.warn("解析 NPC 名称表失败 {}: {}", base, e.getMessage());
            }
        }
        return names;
    }

    /** 地区归属：起始 NPC → 所在地图（优先街道名明确的，同级按 mapId 数值升序确定性选取）→ 地区/街道。无法定位则 region=unknown。 */
    private void attribute(QuestIndex idx, Map<String, String[]> mapLookup, Map<String, Set<String>> npcMaps) {
        for (QuestRecord q : idx.quests) {
            if (q.startNpcId == null || q.startNpcId.isEmpty()) continue;
            Set<String> maps = npcMaps.get(q.startNpcId);
            if (maps == null || maps.isEmpty()) continue;
            String bestMap = null;
            String bestStreet = null;
            for (String mid : maps) {
                String[] info = mapLookup.get(mid);
                if (info == null) continue;
                String street = info[1];
                if (bestMap == null) {
                    bestMap = mid; bestStreet = street; continue;
                }
                boolean curUnknown = UNKNOWN_STREET.equals(street);
                boolean bestUnknown = UNKNOWN_STREET.equals(bestStreet);
                // 优先街道名确定的地图；同级时按 mapId 数值升序（确定性选取）
                if (bestUnknown && !curUnknown) {
                    bestMap = mid; bestStreet = street;
                } else if (curUnknown == bestUnknown) {
                    // 同属 known 或同属 unknown，取 mapId 较小者
                    long curId; try { curId = Long.parseLong(mid); } catch (Exception e) { curId = Long.MAX_VALUE; }
                    long bestId; try { bestId = Long.parseLong(bestMap); } catch (Exception e) { bestId = Long.MAX_VALUE; }
                    if (curId < bestId) { bestMap = mid; bestStreet = street; }
                }
            }
            if (bestMap == null) continue;
            q.town = mapLookup.get(bestMap)[1];
            q.region = regionOfMap.getOrDefault(bestMap, UNKNOWN_REGION);
        }
    }

    /** 地图id → 地区 key（buildMapLookup 时一并填充） */
    private final Map<String, String> regionOfMap = new HashMap<>();

    // ---------------------------------------------------------------- 链聚合

    /** 按 parent 聚合链组（组内按 order → id 排序）；记录被 nextQuest 引用的任务。 */
    private void aggregateChains(QuestIndex idx) {
        Map<String, List<QuestRecord>> groups = new LinkedHashMap<>();
        for (QuestRecord q : idx.quests) {
            if (q.parentName != null && !q.parentName.isEmpty()) {
                groups.computeIfAbsent(q.parentName, k -> new ArrayList<>()).add(q);
            }
            if (q.nextQuestId != null && !q.nextQuestId.isEmpty()) {
                idx.nextQuestTargets.add(q.nextQuestId);
            }
        }
        for (Map.Entry<String, List<QuestRecord>> e : groups.entrySet()) {
            e.getValue().sort(Comparator
                    .comparing((QuestRecord q) -> q.order == null ? 0 : q.order)
                    .thenComparingInt(q -> Integer.parseInt(q.questId)));
            List<String> ids = new ArrayList<>();
            for (QuestRecord q : e.getValue()) ids.add(q.questId);
            idx.chainGroups.put(e.getKey(), ids);
        }
    }

    private boolean isInChain(QuestIndex idx, QuestRecord q) {
        if (q.parentName != null && !q.parentName.isEmpty()) return true;
        if (q.nextQuestId != null && !q.nextQuestId.isEmpty()) return true;
        return idx.nextQuestTargets.contains(q.questId);
    }

    // ---------------------------------------------------------------- helpers

    private String regionLabel(String key) {
        if (UNKNOWN_REGION.equals(key)) return UNKNOWN_REGION_LABEL;
        return REGION_NAMES.getOrDefault(key, key);
    }

    private String fileNameBase(Path p) {
        String n = p.getFileName().toString();
        int dot = n.indexOf('.');
        return dot > 0 ? n.substring(0, dot) : n;
    }

    /** 去前导零归一化 id（非数字返回 null）。 */
    private String normalizeId(String id) {
        if (id == null) return null;
        try {
            return String.valueOf(Long.parseLong(id.trim()));
        } catch (Exception e) {
            return null;
        }
    }

    private int indexOf(byte[] data, byte[] marker) {
        outer:
        for (int i = 0; i <= data.length - marker.length; i++) {
            for (int j = 0; j < marker.length; j++) {
                if (data[i + j] != marker[j]) continue outer;
            }
            return i;
        }
        return -1;
    }

    /** 从 start（指向 life 开始标签）起做 imgdir 深度计数，返回 life 区段结束位置（含闭合标签）。 */
    private int findSectionEnd(byte[] data, int start) {
        int depth = 0;
        int k = start;
        while (k < data.length) {
            int open = indexOfAt(data, k, "<imgdir".getBytes(StandardCharsets.ISO_8859_1));
            int close = indexOfAt(data, k, "</imgdir>".getBytes(StandardCharsets.ISO_8859_1));
            if (close < 0) return data.length;
            if (open >= 0 && open < close) {
                depth++;
                k = open + 7;
            } else {
                depth--;
                k = close + 9;
                if (depth == 0) return k;
            }
        }
        return data.length;
    }

    private int indexOfAt(byte[] data, int from, byte[] marker) {
        outer:
        for (int i = from; i <= data.length - marker.length; i++) {
            for (int j = 0; j < marker.length; j++) {
                if (data[i + j] != marker[j]) continue outer;
            }
            return i;
        }
        return -1;
    }

    private Document loadDoc(Path p) throws ParserConfigurationException, SAXException, IOException {
        return DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(p.toFile());
    }

    private String orEmpty(String s) {
        return s == null ? "" : s;
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

    private Integer getInt(Element parent, String attrName, Integer def) {
        String v = getVal(parent, attrName);
        if (v == null || v.isEmpty()) return def;
        try {
            return Integer.parseInt(v);
        } catch (Exception e) {
            return def;
        }
    }
}
