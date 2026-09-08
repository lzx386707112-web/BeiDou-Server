package org.gms.service;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.gms.model.dto.EquipmentCatalogCategoryDTO;
import org.gms.model.dto.ItemCatalogItemDTO;
import org.gms.model.dto.ItemCatalogPageDTO;
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
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

@Service
@Slf4j
public class ItemCatalogService {
    static final String CATALOG_RESOURCE = "/item-catalog/catalog.json";
    private static final String ATLAS_ROOT = "/item-catalog/atlases/";
    private static final int DEFAULT_PAGE_SIZE = 60;
    private static final int MAX_PAGE_SIZE = 120;
    private static final int CELL_SIZE = 48;

    private final Map<String, BufferedImage> atlasCache = new ConcurrentHashMap<>();
    private final Map<Integer, byte[]> iconCache = new ConcurrentHashMap<>();
    private volatile CatalogData catalogData;

    @PostConstruct
    public void load() {
        try {
            ClassPathResource resource = new ClassPathResource(CATALOG_RESOURCE);
            if (!resource.exists()) {
                log.warn("Item catalog not found at {}, skipping load", CATALOG_RESOURCE);
                catalogData = new CatalogData(CELL_SIZE, List.of(), Map.of(), List.of());
                return;
            }
            String json;
            try (InputStream input = resource.getInputStream()) {
                json = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            }
            JSONObject root = JSON.parseObject(json);
            int cellSize = root.getIntValue("cellSize");
            if (cellSize <= 0) {
                cellSize = CELL_SIZE;
            }
            JSONArray sourceItems = root.getJSONArray("items");
            List<CatalogItem> items = new ArrayList<>(sourceItems.size());
            Map<Integer, CatalogItem> byId = new LinkedHashMap<>();
            Map<String, Integer> categoryCounts = new LinkedHashMap<>();
            for (Object value : sourceItems) {
                JSONObject source = (JSONObject) value;
                Map<String, Object> specs = new LinkedHashMap<>();
                JSONObject sourceSpecs = source.getJSONObject("specs");
                if (sourceSpecs != null) {
                    sourceSpecs.forEach((key, specValue) -> specs.put(key, specValue));
                }
                CatalogItem item = new CatalogItem(
                        source.getIntValue("id"),
                        source.getString("name"),
                        source.getString("desc"),
                        source.getString("category"),
                        Collections.unmodifiableMap(specs),
                        source.getBooleanValue("icon"),
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
            log.info("Loaded item preview catalog: {} items, {} categories",
                    items.size(), categories.size());
        } catch (IOException | RuntimeException exception) {
            log.warn("Unable to load item preview catalog, using empty catalog", exception);
            catalogData = new CatalogData(CELL_SIZE, List.of(), Map.of(), List.of());
        }
    }

    public ItemCatalogPageDTO catalog(String keyword, String category,
                                      Integer requestedPage, Integer requestedPageSize) {
        CatalogData data = requireData();
        String query = normalize(keyword);
        String categoryFilter = category == null ? "" : category.trim();
        int pageNo = requestedPage == null ? 1 : Math.max(1, requestedPage);
        int pageSize = requestedPageSize == null
                ? DEFAULT_PAGE_SIZE
                : Math.min(MAX_PAGE_SIZE, Math.max(1, requestedPageSize));

        List<CatalogItem> matched = data.items().stream()
                .filter(item -> categoryFilter.isEmpty()
                        || item.category().equals(categoryFilter))
                .filter(item -> matches(item, query))
                .sorted(Comparator.comparingInt((CatalogItem item) -> matchRank(item, query))
                        .thenComparingInt(CatalogItem::id))
                .toList();

        long offset = (long) (pageNo - 1) * pageSize;
        int from = (int) Math.min(offset, matched.size());
        int to = Math.min(from + pageSize, matched.size());
        List<ItemCatalogItemDTO> records = matched.subList(from, to).stream()
                .map(this::toDto)
                .toList();
        return new ItemCatalogPageDTO(records, data.categories(), pageNo,
                pageSize, matched.size());
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
            log.warn("Unable to render item icon {}", item.id(), exception);
            return new byte[0];
        }
    }

    private BufferedImage loadAtlas(String category) {
        try {
            ClassPathResource resource = new ClassPathResource(
                    ATLAS_ROOT + category + ".png");
            if (!resource.exists()) {
                log.warn("Item atlas not found for category: {}", category);
                return createEmptyAtlas();
            }
            BufferedImage image;
            try (InputStream input = resource.getInputStream()) {
                image = ImageIO.read(input);
            }
            if (image == null) {
                throw new IOException("unsupported atlas image");
            }
            return image;
        } catch (IOException exception) {
            log.warn("Unable to load item atlas: {}", category, exception);
            return createEmptyAtlas();
        }
    }

    private BufferedImage createEmptyAtlas() {
        BufferedImage empty = new BufferedImage(CELL_SIZE, CELL_SIZE, BufferedImage.TYPE_INT_ARGB);
        return empty;
    }

    private ItemCatalogItemDTO toDto(CatalogItem item) {
        return new ItemCatalogItemDTO(item.id(), item.name(),
                item.description(), item.category(), item.specs(),
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
            throw new IllegalStateException("Item preview catalog is not loaded");
        }
        return data;
    }

    private record CatalogItem(int id, String name, String description,
                               String category, Map<String, Object> specs,
                               boolean iconAvailable, int x, int y) {
    }

    private record CatalogData(int cellSize, List<CatalogItem> items,
                               Map<Integer, CatalogItem> byId,
                               List<EquipmentCatalogCategoryDTO> categories) {
    }
}
