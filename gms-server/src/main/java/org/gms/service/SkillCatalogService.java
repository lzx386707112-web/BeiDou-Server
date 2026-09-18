package org.gms.service;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import lombok.extern.slf4j.Slf4j;
import org.gms.model.dto.SkillCatalogItemDTO;
import org.gms.model.dto.SkillCatalogPageDTO;
import org.gms.model.dto.SkillJobCategoryDTO;
import org.gms.provider.Data;
import org.gms.provider.DataDirectoryEntry;
import org.gms.provider.DataFileEntry;
import org.gms.provider.DataProvider;
import org.gms.provider.DataProviderFactory;
import org.gms.provider.DataTool;
import org.gms.property.ServiceProperty;
import org.gms.provider.wz.WZFiles;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * 技能目录服务 - 提供职业技能预览功能
 */
@Service
@Slf4j
public class SkillCatalogService {
    private static final int DEFAULT_PAGE_SIZE = 120;
    private static final int MAX_PAGE_SIZE = 500;
    private static final int ICON_CELL = 40;
    private static final String ICON_MANIFEST = "skill-catalog/icons.json";
    private static final String ICON_ATLAS = "skill-catalog/atlas.png";

    // 职业ID -> 职业名称映射
    private static final Map<Integer, String> JOB_NAMES = new LinkedHashMap<>();
    static {
        // 冒险家
        JOB_NAMES.put(0, "初心者");
        JOB_NAMES.put(100, "战士");
        JOB_NAMES.put(110, "剑客");
        JOB_NAMES.put(111, "勇士");
        JOB_NAMES.put(112, "英雄");
        JOB_NAMES.put(120, "准骑士");
        JOB_NAMES.put(121, "骑士");
        JOB_NAMES.put(122, "圣骑士");
        JOB_NAMES.put(130, "枪战士");
        JOB_NAMES.put(131, "龙骑士");
        JOB_NAMES.put(132, "黑骑士");

        JOB_NAMES.put(200, "魔法师");
        JOB_NAMES.put(210, "法师(火毒)");
        JOB_NAMES.put(211, "魔法师(火毒)");
        JOB_NAMES.put(212, "大魔导师(火毒)");
        JOB_NAMES.put(220, "法师(冰雷)");
        JOB_NAMES.put(221, "魔法师(冰雷)");
        JOB_NAMES.put(222, "大魔导师(冰雷)");
        JOB_NAMES.put(230, "牧师");
        JOB_NAMES.put(231, "祭司");
        JOB_NAMES.put(232, "主教");
        JOB_NAMES.put(233, "主教(扩展)");

        JOB_NAMES.put(300, "弓箭手");
        JOB_NAMES.put(310, "猎人");
        JOB_NAMES.put(311, "射手");
        JOB_NAMES.put(312, "箭神");
        JOB_NAMES.put(320, "弩弓手");
        JOB_NAMES.put(321, "游侠");
        JOB_NAMES.put(322, "神射手");

        JOB_NAMES.put(400, "飞侠");
        JOB_NAMES.put(410, "刺客");
        JOB_NAMES.put(411, "无影人");
        JOB_NAMES.put(412, "夜使者");
        JOB_NAMES.put(420, "侠客");
        JOB_NAMES.put(421, "独行客");
        JOB_NAMES.put(422, "暗影神偷");
        JOB_NAMES.put(430, "见习刀客");
        JOB_NAMES.put(431, "双刀客");
        JOB_NAMES.put(432, "血刀");
        JOB_NAMES.put(433, "暗影双刀");
        JOB_NAMES.put(434, "暗影双刀");

        JOB_NAMES.put(500, "海盗");
        JOB_NAMES.put(510, "拳手");
        JOB_NAMES.put(511, "斗士");
        JOB_NAMES.put(512, "冲锋队长");
        JOB_NAMES.put(520, "枪手");
        JOB_NAMES.put(521, "大副");
        JOB_NAMES.put(522, "船长");

        // 皇家骑士团
        JOB_NAMES.put(1000, "初心者(骑士团)");
        JOB_NAMES.put(1100, "魂骑士");
        JOB_NAMES.put(1110, "魂骑士");
        JOB_NAMES.put(1111, "魂骑士");
        JOB_NAMES.put(1112, "魂骑士");
        JOB_NAMES.put(1200, "炎术士");
        JOB_NAMES.put(1210, "炎术士");
        JOB_NAMES.put(1211, "炎术士");
        JOB_NAMES.put(1212, "炎术士");
        JOB_NAMES.put(1300, "风行者");
        JOB_NAMES.put(1310, "风行者");
        JOB_NAMES.put(1311, "风行者");
        JOB_NAMES.put(1312, "风行者");
        JOB_NAMES.put(1400, "夜行者");
        JOB_NAMES.put(1410, "夜行者");
        JOB_NAMES.put(1411, "夜行者");
        JOB_NAMES.put(1412, "夜行者");
        JOB_NAMES.put(1500, "奇袭者");
        JOB_NAMES.put(1510, "奇袭者");
        JOB_NAMES.put(1511, "奇袭者");
        JOB_NAMES.put(1512, "奇袭者");

        // 战神
        JOB_NAMES.put(2000, "战神(初心者)");
        JOB_NAMES.put(2100, "战神");
        JOB_NAMES.put(2110, "战神");
        JOB_NAMES.put(2111, "战神");
        JOB_NAMES.put(2112, "战神");

        // 龙神
        JOB_NAMES.put(2200, "龙神(初心者)");
        JOB_NAMES.put(2210, "龙神");
        JOB_NAMES.put(2211, "龙神");
        JOB_NAMES.put(2212, "龙神");
        JOB_NAMES.put(2213, "龙神");
        JOB_NAMES.put(2214, "龙神");
        JOB_NAMES.put(2215, "龙神");
        JOB_NAMES.put(2216, "龙神");
        JOB_NAMES.put(2217, "龙神");
        JOB_NAMES.put(2218, "龙神");

        // 双弩精灵
        JOB_NAMES.put(3000, "双弩精灵(初心者)");
        JOB_NAMES.put(3100, "双弩精灵");
        JOB_NAMES.put(3110, "双弩精灵");
        JOB_NAMES.put(3111, "双弩精灵");
        JOB_NAMES.put(3112, "双弩精灵");

        // 幻影
        JOB_NAMES.put(4000, "幻影(初心者)");
        JOB_NAMES.put(4100, "幻影");
        JOB_NAMES.put(4110, "幻影");
        JOB_NAMES.put(4111, "幻影");
        JOB_NAMES.put(4112, "幻影");

        // 隐月
        JOB_NAMES.put(5000, "隐月(初心者)");
        JOB_NAMES.put(5100, "隐月");
        JOB_NAMES.put(5110, "隐月");
        JOB_NAMES.put(5111, "隐月");
        JOB_NAMES.put(5112, "隐月");

        JOB_NAMES.put(800, "管理员");
        JOB_NAMES.put(900, "GM");
        JOB_NAMES.put(910, "超级GM");
    }

    // 转职等级映射 (jobId -> 转职次数)
    private static final Map<Integer, Integer> JOB_ADVANCEMENT = new LinkedHashMap<>();
    static {
        // 冒险家
        JOB_ADVANCEMENT.put(0, 0);
        JOB_ADVANCEMENT.put(100, 1); JOB_ADVANCEMENT.put(200, 1);
        JOB_ADVANCEMENT.put(300, 1); JOB_ADVANCEMENT.put(400, 1);
        JOB_ADVANCEMENT.put(500, 1);

        JOB_ADVANCEMENT.put(110, 2); JOB_ADVANCEMENT.put(120, 2); JOB_ADVANCEMENT.put(130, 2);
        JOB_ADVANCEMENT.put(210, 2); JOB_ADVANCEMENT.put(220, 2); JOB_ADVANCEMENT.put(230, 2);
        JOB_ADVANCEMENT.put(310, 2); JOB_ADVANCEMENT.put(320, 2);
        JOB_ADVANCEMENT.put(410, 2); JOB_ADVANCEMENT.put(420, 2);
        JOB_ADVANCEMENT.put(430, 2); JOB_ADVANCEMENT.put(431, 2);
        JOB_ADVANCEMENT.put(510, 2); JOB_ADVANCEMENT.put(520, 2);

        JOB_ADVANCEMENT.put(111, 3); JOB_ADVANCEMENT.put(121, 3); JOB_ADVANCEMENT.put(131, 3);
        JOB_ADVANCEMENT.put(211, 3); JOB_ADVANCEMENT.put(221, 3); JOB_ADVANCEMENT.put(231, 3);
        JOB_ADVANCEMENT.put(311, 3); JOB_ADVANCEMENT.put(321, 3);
        JOB_ADVANCEMENT.put(411, 3); JOB_ADVANCEMENT.put(421, 3);
        JOB_ADVANCEMENT.put(432, 3); JOB_ADVANCEMENT.put(433, 3);
        JOB_ADVANCEMENT.put(511, 3); JOB_ADVANCEMENT.put(521, 3);

        JOB_ADVANCEMENT.put(112, 4); JOB_ADVANCEMENT.put(122, 4); JOB_ADVANCEMENT.put(132, 4);
        JOB_ADVANCEMENT.put(212, 4); JOB_ADVANCEMENT.put(222, 4); JOB_ADVANCEMENT.put(232, 4);
        JOB_ADVANCEMENT.put(312, 4); JOB_ADVANCEMENT.put(322, 4);
        JOB_ADVANCEMENT.put(412, 4); JOB_ADVANCEMENT.put(422, 4);
        JOB_ADVANCEMENT.put(434, 4);
        JOB_ADVANCEMENT.put(512, 4); JOB_ADVANCEMENT.put(522, 4);

        // 皇家骑士团
        JOB_ADVANCEMENT.put(1000, 0);
        for (int j = 1100; j <= 1500; j += 100) JOB_ADVANCEMENT.put(j, 1);
        for (int j = 1110; j <= 1510; j += 100) JOB_ADVANCEMENT.put(j, 2);
        for (int j = 1111; j <= 1511; j += 100) JOB_ADVANCEMENT.put(j, 3);
        for (int j = 1112; j <= 1512; j += 100) JOB_ADVANCEMENT.put(j, 4);

        // 战神
        JOB_ADVANCEMENT.put(2000, 0);
        JOB_ADVANCEMENT.put(2100, 1); JOB_ADVANCEMENT.put(2110, 2);
        JOB_ADVANCEMENT.put(2111, 3); JOB_ADVANCEMENT.put(2112, 4);

        // 龙神
        JOB_ADVANCEMENT.put(2200, 0);
        for (int j = 2210; j <= 2218; j++) JOB_ADVANCEMENT.put(j, j - 2209);

        // 双弩精灵
        JOB_ADVANCEMENT.put(3000, 0);
        JOB_ADVANCEMENT.put(3100, 1); JOB_ADVANCEMENT.put(3110, 2);
        JOB_ADVANCEMENT.put(3111, 3); JOB_ADVANCEMENT.put(3112, 4);

        // 幻影
        JOB_ADVANCEMENT.put(4000, 0);
        JOB_ADVANCEMENT.put(4100, 1); JOB_ADVANCEMENT.put(4110, 2);
        JOB_ADVANCEMENT.put(4111, 3); JOB_ADVANCEMENT.put(4112, 4);

        // 隐月
        JOB_ADVANCEMENT.put(5000, 0);
        JOB_ADVANCEMENT.put(5100, 1); JOB_ADVANCEMENT.put(5110, 2);
        JOB_ADVANCEMENT.put(5111, 3);
        JOB_ADVANCEMENT.put(5112, 4);
        JOB_ADVANCEMENT.put(800, 0);
        JOB_ADVANCEMENT.put(900, 0);
        JOB_ADVANCEMENT.put(910, 0);
        JOB_ADVANCEMENT.put(233, 4);
    }

    private final ServiceProperty serviceProperty;
    private final Map<Integer, SkillCatalogItemDTO> allSkills = new ConcurrentHashMap<>();
    private final Map<Integer, SkillJobCategoryDTO> jobCategories = new ConcurrentHashMap<>();
    private final Map<Integer, int[]> iconCoords = new ConcurrentHashMap<>();
    private final Map<Integer, byte[]> iconCache = new ConcurrentHashMap<>();
    private volatile BufferedImage iconAtlas;
    private volatile int iconCell = ICON_CELL;
    private volatile boolean loaded = false;
    private volatile boolean fallbackAttempted = false;
    private volatile String lastLoadError;

    public SkillCatalogService(ServiceProperty serviceProperty) {
        this.serviceProperty = serviceProperty;
    }

    /**
     * 不能在 {@code @PostConstruct} 阶段加载：解析 WZ 数据会触发
     * {@code GameConstants -> GameConfig} 的静态初始化，而它依赖
     * {@code ServerManager.getApplicationContext()}（此时 ServerManager 尚未创建，必为 null）。
     * 放到容器就绪后执行，并保留首次访问时的兜底重试。
     */
    @EventListener(ApplicationReadyEvent.class)
    public void init() {
        loadCatalog();
    }

    /**
     * 加载技能目录
     */
    public void loadCatalog() {
        log.info("Loading skill catalog...");
        allSkills.clear();
        jobCategories.clear();
        lastLoadError = null;
        boolean completed = false;

        try {
            loadIconAtlas();

            String language = serviceProperty == null ? null : serviceProperty.getLanguage();
            DataProvider skillProvider = DataProviderFactory.getDataProvider(WZFiles.SKILL, language);
            DataProvider stringProvider = DataProviderFactory.getDataProvider(WZFiles.STRING, language);

            Map<Integer, List<String>> skillStrings = loadSkillStrings(stringProvider);

            DataDirectoryEntry root = skillProvider.getRoot();
            int fileCount = 0;
            for (DataFileEntry fileEntry : root.getFiles()) {
                String fileName = fileEntry.getName();
                if (!fileName.matches("\\d+\\.img")) {
                    continue;
                }
                String jobIdStr = fileName.substring(0, fileName.length() - 4);
                try {
                    int jobId = Integer.parseInt(jobIdStr);
                    loadSkillsFromFile(skillProvider, skillStrings, jobId, fileName);
                    fileCount++;
                } catch (NumberFormatException e) {
                    log.debug("Skipping non-job skill file: {}", fileName);
                }
            }

            Map<Integer, Integer> jobSkillCounts = new LinkedHashMap<>();
            for (SkillCatalogItemDTO skill : allSkills.values()) {
                jobSkillCounts.merge(skill.jobId(), 1, Integer::sum);
            }

            for (Map.Entry<Integer, Integer> entry : jobSkillCounts.entrySet()) {
                int jobId = entry.getKey();
                String jobName = JOB_NAMES.getOrDefault(jobId, "职业 " + jobId);
                jobCategories.put(jobId, new SkillJobCategoryDTO(jobId, jobName, entry.getValue()));
            }

            completed = true;
            if (allSkills.isEmpty()) {
                lastLoadError = "未从 Skill.wz 读到职业技能，请确认服务端 wz/Skill.wz 是否完整";
            }
            log.info("Skill catalog loaded: {} skills from {} files, {} jobs",
                    allSkills.size(), fileCount, jobCategories.size());
        } catch (Throwable e) {
            lastLoadError = e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage());
            log.error("Failed to load skill catalog", e);
        } finally {
            loaded = completed || !allSkills.isEmpty();
        }
    }

    public int reload() {
        fallbackAttempted = false;
        loadCatalog();
        return allSkills.size();
    }

    /**
     * 从 String.wz/Skill.img 加载技能名称、描述和等级描述
     * 返回 Map<skillId, [name, desc, h1, h2, ...]>
     */
    private Map<Integer, List<String>> loadSkillStrings(DataProvider stringProvider) {
        Map<Integer, List<String>> result = new LinkedHashMap<>();
        try {
            Data skillStringData = stringProvider.getData("Skill.img");
            if (skillStringData == null) {
                log.warn("Skill.img not found in String.wz");
                return result;
            }

            int count = 0;
            for (Data entry : skillStringData) {
                try {
                    int skillId = Integer.parseInt(entry.getName());
                    String name = DataTool.getString("name", entry, "");
                    String desc = DataTool.getString("desc", entry, "");

                    List<String> data = new ArrayList<>();
                    data.add(name);  // index 0: name
                    data.add(desc);  // index 1: desc

                    // 加载等级描述 h1, h2, ...
                    for (int i = 1; i <= 30; i++) {
                        String h = DataTool.getString("h" + i, entry, "");
                        data.add(h.trim());
                    }

                    result.put(skillId, data);
                    count++;
                } catch (NumberFormatException e) {
                    // 跳过非数字节点（如 "000" 这种职业名称节点）
                }
            }
            log.info("Loaded {} skill strings from String.wz", count);
        } catch (Throwable e) {
            log.warn("Failed to load skill strings", e);
        }
        return result;
    }

    /**
     * 从单个技能文件加载技能
     */
    private void loadSkillsFromFile(DataProvider skillProvider, Map<Integer, List<String>> skillStrings,
                                    int jobId, String fileName) {
        try {
            Data jobData = skillProvider.getData(fileName);
            if (jobData == null) return;

            Data skillNode = jobData.getChildByPath("skill");
            if (skillNode == null) {
                for (Data child : jobData) {
                    if ("skill".equals(child.getName())) {
                        skillNode = child;
                        break;
                    }
                }
            }
            if (skillNode == null) return;

            for (Data skillEntry : skillNode) {
                try {
                    int skillId = Integer.parseInt(skillEntry.getName());
                    int skillJobId = skillId / 10000;

                    List<String> strings = skillStrings.get(skillId);
                    String name = "";
                    String desc = "";
                    List<String> levelDescs = new ArrayList<>();

                    if (strings != null && strings.size() >= 2) {
                        name = strings.get(0);
                        desc = strings.get(1);
                        // 获取等级描述 (index 2 开始是 h1, h2, ...)
                        for (int i = 2; i < strings.size(); i++) {
                            String h = strings.get(i);
                            if (!h.isEmpty()) {
                                levelDescs.add(h);
                            }
                        }
                    }

                    // 计算最大等级
                    Data levelNode = skillEntry.getChildByPath("level");
                    int maxLevel = 0;
                    if (levelNode != null) {
                        for (Data level : levelNode) {
                            try {
                                int levelNum = Integer.parseInt(level.getName());
                                maxLevel = Math.max(maxLevel, levelNum);
                            } catch (NumberFormatException ignored) {}
                        }
                    }

                    // 如果没有从 String.wz 获取到等级描述，尝试从技能数据本身获取
                    if (levelDescs.isEmpty() && levelNode != null) {
                        for (int i = 1; i <= Math.min(maxLevel, 30); i++) {
                            Data levelData = levelNode.getChildByPath(String.valueOf(i));
                            if (levelData != null) {
                                String h = DataTool.getString("h" + i, levelData, "");
                                if (!h.isEmpty()) {
                                    levelDescs.add(h.trim());
                                }
                            }
                        }
                    }

                    Map<String, Object> attributes = readAttributes(skillEntry, levelNode, maxLevel);
                    String jobName = JOB_NAMES.getOrDefault(skillJobId, JOB_NAMES.getOrDefault(jobId, "职业 " + skillJobId));

                    SkillCatalogItemDTO item = new SkillCatalogItemDTO(
                            skillId, name, desc, jobName, skillJobId, maxLevel,
                            iconCoords.containsKey(skillId), attributes, levelDescs
                    );

                    allSkills.putIfAbsent(skillId, item);
                } catch (NumberFormatException e) {
                    // 跳过非数字节点
                }
            }
        } catch (Throwable e) {
            // 单个技能文件解析失败不应中断整体加载，也不应冒泡成启动失败
            log.warn("Failed to load skills from file: {}", fileName, e);
        }
    }

    /**
     * 查询技能目录
     */
    public SkillCatalogPageDTO catalog(String keyword, Integer jobId, Integer advancement,
                                        Integer pageNo, Integer pageSize) {
        ensureLoaded();

        String query = keyword == null ? "" : keyword.trim().toLowerCase(Locale.ROOT);
        int page = pageNo == null ? 1 : Math.max(1, pageNo);
        int size = pageSize == null ? DEFAULT_PAGE_SIZE : Math.min(MAX_PAGE_SIZE, Math.max(1, pageSize));

        List<SkillCatalogItemDTO> filtered = allSkills.values().stream()
                .filter(skill -> jobId == null || skill.jobId() == jobId)
                .filter(skill -> advancement == null || getAdvancement(skill.jobId()) == advancement)
                .filter(skill -> matchesQuery(skill, query))
                .sorted(Comparator.comparingInt(SkillCatalogItemDTO::jobId)
                        .thenComparingInt(SkillCatalogItemDTO::id))
                .collect(Collectors.toList());

        int total = filtered.size();
        int from = Math.min((page - 1) * size, total);
        int to = Math.min(from + size, total);
        List<SkillCatalogItemDTO> records = filtered.subList(from, to);

        List<SkillJobCategoryDTO> jobs = jobCategories.values().stream()
                .sorted(Comparator.comparingInt(SkillJobCategoryDTO::jobId))
                .collect(Collectors.toList());

        return new SkillCatalogPageDTO(records, jobs, page, size, total, loaded, lastLoadError);
    }

    /**
     * 获取单个技能详情
     */
    public SkillCatalogItemDTO getSkill(int skillId) {
        ensureLoaded();
        return allSkills.get(skillId);
    }

    public List<SkillJobCategoryDTO> getJobCategories() {
        ensureLoaded();
        return new ArrayList<>(jobCategories.values());
    }

    public byte[] icon(int skillId) {
        ensureLoaded();
        if (!iconCoords.containsKey(skillId) || iconAtlas == null) {
            return null;
        }
        return iconCache.computeIfAbsent(skillId, this::encodeIcon);
    }

    private byte[] encodeIcon(int skillId) {
        int[] xy = iconCoords.get(skillId);
        if (xy == null || iconAtlas == null) {
            return new byte[0];
        }
        try {
            BufferedImage icon = iconAtlas.getSubimage(xy[0], xy[1], iconCell, iconCell);
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            ImageIO.write(icon, "png", output);
            return output.toByteArray();
        } catch (RuntimeException | IOException exception) {
            log.warn("Unable to render skill icon {}", skillId, exception);
            return new byte[0];
        }
    }

    private void loadIconAtlas() {
        iconCoords.clear();
        iconCache.clear();
        iconAtlas = null;
        try {
            ClassPathResource manifestResource = new ClassPathResource(ICON_MANIFEST);
            if (!manifestResource.exists()) {
                log.warn("Skill icon manifest missing at {}", ICON_MANIFEST);
                return;
            }
            String json;
            try (InputStream input = manifestResource.getInputStream()) {
                json = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            }
            JSONObject root = JSON.parseObject(json);
            iconCell = Math.max(1, root.getIntValue("cellSize", ICON_CELL));
            JSONObject icons = root.getJSONObject("icons");
            if (icons != null) {
                icons.forEach((key, value) -> {
                    try {
                        JSONObject point = (JSONObject) value;
                        iconCoords.put(Integer.parseInt(key),
                                new int[]{point.getIntValue("x"), point.getIntValue("y")});
                    } catch (RuntimeException ignored) {
                    }
                });
            }
            ClassPathResource atlasResource = new ClassPathResource(ICON_ATLAS);
            if (!atlasResource.exists()) {
                log.warn("Skill icon atlas missing at {}", ICON_ATLAS);
                return;
            }
            try (InputStream input = atlasResource.getInputStream()) {
                iconAtlas = ImageIO.read(input);
            }
            log.info("Loaded skill icon atlas: {} icons", iconCoords.size());
        } catch (IOException | RuntimeException exception) {
            log.warn("Unable to load skill icon atlas", exception);
        }
    }

    private Map<String, Object> readAttributes(Data skillEntry, Data levelNode, int maxLevel) {
        Map<String, Object> attributes = new LinkedHashMap<>();
        String elem = DataTool.getString("elemAttr", skillEntry, "");
        if (!elem.isBlank()) {
            attributes.put("elemAttr", elem);
        }
        int skillType = DataTool.getInt("skillType", skillEntry, -1);
        if (skillType >= 0) {
            attributes.put("skillType", skillType);
        }
        Data sample = null;
        if (levelNode != null && maxLevel > 0) {
            sample = levelNode.getChildByPath(String.valueOf(maxLevel));
            if (sample == null) {
                sample = levelNode.getChildByPath("1");
            }
        }
        if (sample != null) {
            putStat(attributes, "cooltime", readLevelInt(sample, 0, "cooltime", "coolTime"), true);
            putStat(attributes, "mpCon", readLevelInt(sample, 0, "mpCon", "mpcon"), true);
            putStat(attributes, "time", readLevelInt(sample, 0, "time"), false);
            putStat(attributes, "damage", readLevelInt(sample, 0, "damage"), false);
            putStat(attributes, "attackCount", readLevelInt(sample, 0, "attackCount"), false);
            putStat(attributes, "mobCount", readLevelInt(sample, 0, "mobCount"), false);
        }
        return attributes;
    }

    private void putStat(Map<String, Object> attributes, String key, int value, boolean always) {
        if (always || value > 0) {
            attributes.put(key, value);
        }
    }

    private int readLevelInt(Data sample, int def, String... names) {
        for (String name : names) {
            Data child = sample.getChildByPath(name);
            if (child != null) {
                return DataTool.getIntConvert(child, def);
            }
        }
        return def;
    }

    private void ensureLoaded() {
        if (!loaded && !fallbackAttempted) {
            fallbackAttempted = true;
            loadCatalog();
        }
    }

    private boolean matchesQuery(SkillCatalogItemDTO skill, String query) {
        if (query.isEmpty()) return true;
        return String.valueOf(skill.id()).contains(query)
                || skill.name().toLowerCase(Locale.ROOT).contains(query)
                || skill.jobName().toLowerCase(Locale.ROOT).contains(query);
    }

    private int getAdvancement(int jobId) {
        return JOB_ADVANCEMENT.getOrDefault(jobId, 0);
    }
}
