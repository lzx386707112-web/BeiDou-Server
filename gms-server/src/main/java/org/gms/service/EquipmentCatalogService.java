package org.gms.service;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.gms.model.dto.EquipmentCatalogCategoryDTO;
import org.gms.model.dto.EquipmentCatalogItemDTO;
import org.gms.model.dto.EquipmentCatalogPageDTO;
import org.gms.model.dto.SetItemEquipmentDTO;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

@Service
@Slf4j
public class EquipmentCatalogService {
    static final String CATALOG_RESOURCE = "/equipment-catalog/catalog.json";
    private static final String ATLAS_ROOT = "/equipment-catalog/atlases/";
    private static final int DEFAULT_PAGE_SIZE = 60;
    private static final int MAX_PAGE_SIZE = 120;

    private final Map<String, BufferedImage> atlasCache = new ConcurrentHashMap<>();
    private final Map<Integer, byte[]> iconCache = new ConcurrentHashMap<>();
    private volatile CatalogData catalogData;

    @PostConstruct
    public void load() {
        try {
            ClassPathResource resource = new ClassPathResource(CATALOG_RESOURCE);
            String json;
            try (InputStream input = resource.getInputStream()) {
                json = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            }
            JSONObject root = JSON.parseObject(json);
            int cellSize = root.getIntValue("cellSize");
            if (cellSize <= 0) {
                cellSize = 48;
            }
            JSONArray sourceItems = root.getJSONArray("items");
            List<CatalogItem> items = new ArrayList<>(sourceItems.size());
            Map<Integer, CatalogItem> byId = new LinkedHashMap<>();
            Map<String, Integer> categoryCounts = new LinkedHashMap<>();
            for (Object value : sourceItems) {
                JSONObject source = (JSONObject) value;
                Map<String, Integer> stats = new LinkedHashMap<>();
                JSONObject sourceStats = source.getJSONObject("stats");
                if (sourceStats != null) {
                    sourceStats.forEach((key, statValue) ->
                            stats.put(key, ((Number) statValue).intValue()));
                }
                boolean isCash = sourceStats != null && sourceStats.getIntValue("cash") == 1;
                String equipKind = resolveEquipKind(source.getIntValue("id"));
                CatalogItem item = new CatalogItem(
                        source.getIntValue("id"),
                        source.getString("name"),
                        source.getString("desc"),
                        source.getString("category"),
                        Collections.unmodifiableMap(stats),
                        source.getBooleanValue("icon"),
                        isCash,
                        equipKind,
                        source.getIntValue("x"),
                        source.getIntValue("y"));
                if (byId.putIfAbsent(item.id(), item) == null) {
                    items.add(item);
                    categoryCounts.merge(item.category(), 1, Integer::sum);
                }
            }
            List<EquipmentCatalogCategoryDTO> categories = categoryCounts.entrySet().stream()
                    .map(entry -> new EquipmentCatalogCategoryDTO(
                            entry.getKey(), entry.getValue()))
                    .toList();
            catalogData = new CatalogData(cellSize, List.copyOf(items),
                    Collections.unmodifiableMap(byId), categories);
            atlasCache.clear();
            iconCache.clear();
            log.info("Loaded equipment preview catalog: {} items, {} categories",
                    items.size(), categories.size());
        } catch (IOException | RuntimeException exception) {
            throw new IllegalStateException(
                    "Unable to load generated equipment preview catalog", exception);
        }
    }

    public EquipmentCatalogPageDTO catalog(String keyword, String category,
                                           Integer requestedPage, Integer requestedPageSize,
                                           Boolean cashFilter, String weaponTypeFilter,
                                           Integer jobFilter, Integer minLevelFilter, Integer maxLevelFilter) {
        CatalogData data = requireData();
        String query = normalize(keyword);
        String categoryFilter = category == null ? "" : category.trim();
        String weaponFilter = weaponTypeFilter == null ? "" : weaponTypeFilter.trim();
        int pageNo = requestedPage == null ? 1 : Math.max(1, requestedPage);
        int pageSize = requestedPageSize == null
                ? DEFAULT_PAGE_SIZE
                : Math.min(MAX_PAGE_SIZE, Math.max(1, requestedPageSize));

        List<CatalogItem> base = data.items().stream()
                .filter(item -> categoryFilter.isEmpty()
                        || item.category().equals(categoryFilter))
                .filter(item -> matches(item, query))
                .toList();

        // 武器类型分面计数：受现金筛选影响，但不受自身选择影响
        List<CatalogItem> forWeaponCounts = cashFilter == null
                ? base
                : base.stream().filter(item -> item.cash() == cashFilter).toList();
        List<EquipmentCatalogCategoryDTO> weaponTypes = forWeaponCounts.stream()
                .map(CatalogItem::equipKind)
                .filter(Objects::nonNull)
                .collect(Collectors.groupingBy(name -> name, Collectors.counting()))
                .entrySet().stream()
                .map(entry -> new EquipmentCatalogCategoryDTO(entry.getKey(), entry.getValue().intValue()))
                .sorted(Comparator.comparing(EquipmentCatalogCategoryDTO::key))
                .toList();

        // 现金分面计数：受武器类型筛选影响，但不受自身选择影响
        List<CatalogItem> forCashCounts = weaponFilter.isEmpty()
                ? base
                : base.stream().filter(item -> isEquipKind(item, weaponFilter)).toList();
        long cashCount = forCashCounts.stream().filter(CatalogItem::cash).count();
        long nonCashCount = forCashCounts.stream().filter(item -> !item.cash()).count();

        // 最终匹配：叠加全部筛选条件
        List<CatalogItem> matched = base.stream()
                .filter(item -> cashFilter == null || item.cash() == cashFilter)
                .filter(item -> weaponFilter.isEmpty() || isEquipKind(item, weaponFilter))
                .filter(item -> jobFilter == null || jobFilter == 0 || matchesJob(item, jobFilter))
                .filter(item -> minLevelFilter == null || getReqLevel(item) >= minLevelFilter)
                .filter(item -> maxLevelFilter == null || getReqLevel(item) <= maxLevelFilter)
                .sorted(Comparator.comparingInt((CatalogItem item) -> matchRank(item, query))
                        .thenComparingInt(CatalogItem::id))
                .toList();

        long offset = (long) (pageNo - 1) * pageSize;
        int from = (int) Math.min(offset, matched.size());
        int to = Math.min(from + pageSize, matched.size());
        List<EquipmentCatalogItemDTO> records = matched.subList(from, to).stream()
                .map(this::toDto)
                .toList();
        return new EquipmentCatalogPageDTO(records, data.categories(), pageNo,
                pageSize, matched.size(), weaponTypes, (int) cashCount, (int) nonCashCount);
    }

    public List<SetItemEquipmentDTO> searchSimple(String keyword) {
        String query = normalize(keyword);
        if (query.isEmpty()) {
            return List.of();
        }
        return requireData().items().stream()
                .filter(item -> matches(item, query))
                .sorted(Comparator.comparingInt((CatalogItem item) -> matchRank(item, query))
                        .thenComparingInt(CatalogItem::id))
                .limit(30)
                .map(item -> new SetItemEquipmentDTO(item.id(), item.name()))
                .toList();
    }

    public byte[] icon(int itemId) {
        CatalogItem item = requireData().byId().get(itemId);
        if (item == null || !item.iconAvailable()) {
            return null;
        }
        return iconCache.computeIfAbsent(itemId, ignored -> encodeIcon(item));
    }

    private byte[] encodeIcon(CatalogItem item) {
        try {
            BufferedImage atlas = atlasCache.computeIfAbsent(
                    item.category(), this::loadAtlas);
            int size = requireData().cellSize();
            BufferedImage icon = atlas.getSubimage(item.x(), item.y(), size, size);
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            ImageIO.write(icon, "png", output);
            return output.toByteArray();
        } catch (RuntimeException | IOException exception) {
            log.warn("Unable to render equipment icon {}", item.id(), exception);
            return new byte[0];
        }
    }

    private BufferedImage loadAtlas(String category) {
        try {
            ClassPathResource resource = new ClassPathResource(
                    ATLAS_ROOT + category + ".png");
            BufferedImage image;
            try (InputStream input = resource.getInputStream()) {
                image = ImageIO.read(input);
            }
            if (image == null) {
                throw new IOException("unsupported atlas image");
            }
            return image;
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to load equipment atlas: "
                    + category, exception);
        }
    }

    private EquipmentCatalogItemDTO toDto(CatalogItem item) {
        return new EquipmentCatalogItemDTO(item.id(), item.name(),
                item.description(), item.category(), item.stats(),
                item.iconAvailable());
    }

    private boolean matches(CatalogItem item, String query) {
        return query.isEmpty()
                || String.valueOf(item.id()).contains(query)
                || item.name().toLowerCase(Locale.ROOT).contains(query);
    }

    private int matchRank(CatalogItem item, String query) {
        if (query.isEmpty()) {
            return 0;
        }
        String id = String.valueOf(item.id());
        String name = item.name().toLowerCase(Locale.ROOT);
        if (id.equals(query) || name.equals(query)) {
            return 0;
        }
        if (id.startsWith(query)) {
            return 1;
        }
        return name.startsWith(query) ? 2 : 3;
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private CatalogData requireData() {
        CatalogData data = catalogData;
        if (data == null) {
            throw new IllegalStateException("Equipment preview catalog is not loaded");
        }
        return data;
    }
    // 装备种类映射：itemId/10000 前缀 -> 中文名（覆盖防具/装饰/武器全部段）
    private static final Map<Integer, String> EQUIP_KIND_NAMES = Map.ofEntries(
            // 防具 / 装饰
            Map.entry(100, "帽子"),
            Map.entry(101, "脸饰"),
            Map.entry(102, "眼饰"),
            Map.entry(103, "耳环"),
            Map.entry(104, "上衣"),
            Map.entry(105, "套服"),
            Map.entry(106, "裤子"),
            Map.entry(107, "鞋子"),
            Map.entry(108, "手套"),
            Map.entry(109, "盾牌"),
            Map.entry(110, "披风"),
            Map.entry(111, "戒指"),
            Map.entry(112, "项环"),
            Map.entry(113, "腰带"),
            Map.entry(114, "勋章"),
            Map.entry(115, "护肩"),
            Map.entry(118, "纹章"),
            Map.entry(119, "徽章"),
            // 武器
            Map.entry(130, "单手剑"),
            Map.entry(131, "单手斧"),
            Map.entry(132, "单手钝器"),
            Map.entry(133, "短刀"),
            Map.entry(134, "副刀"),
            Map.entry(137, "短杖"),
            Map.entry(138, "长杖"),
            Map.entry(140, "双手剑"),
            Map.entry(141, "双手斧"),
            Map.entry(142, "双手钝器"),
            Map.entry(143, "长枪"),
            Map.entry(144, "枪戟"),
            Map.entry(145, "弓"),
            Map.entry(146, "弩"),
            Map.entry(147, "拳套"),
            Map.entry(148, "指虎"),
            Map.entry(149, "短枪"),
            // 其他
            Map.entry(167, "心脏"),
            Map.entry(170, "扇子"),
            Map.entry(180, "头饰"));

    private static String resolveEquipKind(int itemId) {
        return EQUIP_KIND_NAMES.get(itemId / 10000);
    }

    private static boolean isEquipKind(CatalogItem item, String equipKindName) {
        return equipKindName.equals(item.equipKind());
    }

    private static boolean matchesJob(CatalogItem item, int jobFilter) {
        int reqJob = item.stats().getOrDefault("reqJob", 0);
        // reqJob == 0 表示全职业可用
        if (reqJob == 0) {
            return true;
        }
        // 检查位掩码：jobFilter 是单个职业的位值（1,2,4,8,16）
        return (reqJob & jobFilter) != 0;
    }

    private static int getReqLevel(CatalogItem item) {
        return item.stats().getOrDefault("reqLevel", 0);
    }

private record CatalogItem(int id, String name, String description,
                               String category, Map<String, Integer> stats,
                               boolean iconAvailable, boolean cash, String equipKind,
                               int x, int y) {
    }

    private record CatalogData(int cellSize, List<CatalogItem> items,
                               Map<Integer, CatalogItem> byId,
                               List<EquipmentCatalogCategoryDTO> categories) {
    }
}
