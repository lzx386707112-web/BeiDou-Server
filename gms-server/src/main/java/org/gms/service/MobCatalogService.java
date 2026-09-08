package org.gms.service;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.gms.model.dto.MobCatalogItemDTO;
import org.gms.model.dto.MobCatalogPageDTO;
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

@Service
@Slf4j
public class MobCatalogService {
    private static final String CATALOG_RESOURCE = "/mob-catalog/catalog.json";
    private static final String ATLAS_ROOT = "/mob-catalog/atlases/";
    private static final int DEFAULT_PAGE_SIZE = 60;
    private static final int MAX_PAGE_SIZE = 120;
    private static final int CELL_SIZE = 96; // 怪物图标较大

    private final Map<String, BufferedImage> atlasCache = new ConcurrentHashMap<>();
    private final Map<Integer, byte[]> iconCache = new ConcurrentHashMap<>();
    private volatile CatalogData catalogData;

    @PostConstruct
    public void load() {
        try {
            ClassPathResource resource = new ClassPathResource(CATALOG_RESOURCE);
            if (!resource.exists()) {
                log.warn("Mob catalog not found at {}, skipping load", CATALOG_RESOURCE);
                catalogData = new CatalogData(CELL_SIZE, List.of(), Map.of());
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
            JSONArray sourceItems = root.getJSONArray("mobs");
            List<CatalogMob> mobs = new ArrayList<>(sourceItems.size());
            Map<Integer, CatalogMob> byId = new LinkedHashMap<>();
            for (Object value : sourceItems) {
                JSONObject source = (JSONObject) value;
                Map<String, Integer> stats = new LinkedHashMap<>();
                JSONObject sourceStats = source.getJSONObject("stats");
                if (sourceStats != null) {
                    sourceStats.forEach((key, statValue) ->
                            stats.put(key, ((Number) statValue).intValue()));
                }
                CatalogMob mob = new CatalogMob(
                        source.getIntValue("id"),
                        source.getString("name"),
                        Collections.unmodifiableMap(stats),
                        source.getBooleanValue("icon"),
                        source.getIntValue("x"),
                        source.getIntValue("y"));
                if (byId.putIfAbsent(mob.id(), mob) == null) {
                    mobs.add(mob);
                }
            }
            catalogData = new CatalogData(cellSize, List.copyOf(mobs),
                    Collections.unmodifiableMap(byId));
            atlasCache.clear();
            iconCache.clear();
            log.info("Loaded mob preview catalog: {} mobs", mobs.size());
        } catch (IOException | RuntimeException exception) {
            log.warn("Unable to load mob preview catalog, using empty catalog", exception);
            catalogData = new CatalogData(CELL_SIZE, List.of(), Map.of());
        }
    }

    public MobCatalogPageDTO catalog(String keyword, Integer requestedPage, Integer requestedPageSize,
                                     Integer minLevel, Integer maxLevel) {
        CatalogData data = requireData();
        String query = normalize(keyword);
        int pageNo = requestedPage == null ? 1 : Math.max(1, requestedPage);
        int pageSize = requestedPageSize == null
                ? DEFAULT_PAGE_SIZE
                : Math.min(MAX_PAGE_SIZE, Math.max(1, requestedPageSize));

        List<CatalogMob> matched = data.mobs().stream()
                .filter(mob -> matches(mob, query))
                .filter(mob -> minLevel == null || getLevel(mob) >= minLevel)
                .filter(mob -> maxLevel == null || getLevel(mob) <= maxLevel)
                .sorted(Comparator.comparingInt((CatalogMob mob) -> matchRank(mob, query))
                        .thenComparingInt(CatalogMob::id))
                .toList();

        long offset = (long) (pageNo - 1) * pageSize;
        int from = (int) Math.min(offset, matched.size());
        int to = Math.min(from + pageSize, matched.size());
        List<MobCatalogItemDTO> records = matched.subList(from, to).stream()
                .map(this::toDto)
                .toList();
        return new MobCatalogPageDTO(records, pageNo, pageSize, matched.size());
    }

    private int getLevel(CatalogMob mob) {
        return mob.stats().getOrDefault("level", 0);
    }

    public byte[] icon(int mobId) {
        CatalogMob mob = requireData().byId().get(mobId);
        if (mob == null || !mob.iconAvailable()) {
            return null;
        }
        return iconCache.computeIfAbsent(mobId, ignored -> encodeIcon(mob));
    }

    private byte[] encodeIcon(CatalogMob mob) {
        try {
            BufferedImage atlas = atlasCache.computeIfAbsent("mob", this::loadAtlas);
            int size = requireData().cellSize();
            BufferedImage icon = atlas.getSubimage(mob.x(), mob.y(), size, size);
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            ImageIO.write(icon, "png", output);
            return output.toByteArray();
        } catch (RuntimeException | IOException exception) {
            log.warn("Unable to render mob icon {}", mob.id(), exception);
            return new byte[0];
        }
    }

    private BufferedImage loadAtlas(String category) {
        try {
            ClassPathResource resource = new ClassPathResource(ATLAS_ROOT + category + ".png");
            if (!resource.exists()) {
                log.warn("Mob atlas not found");
                return new BufferedImage(CELL_SIZE, CELL_SIZE, BufferedImage.TYPE_INT_ARGB);
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
            log.warn("Unable to load mob atlas", exception);
            return new BufferedImage(CELL_SIZE, CELL_SIZE, BufferedImage.TYPE_INT_ARGB);
        }
    }

    private MobCatalogItemDTO toDto(CatalogMob mob) {
        return new MobCatalogItemDTO(mob.id(), mob.name(), mob.stats(), mob.iconAvailable());
    }

    private boolean matches(CatalogMob mob, String query) {
        return query.isEmpty()
                || String.valueOf(mob.id()).contains(query)
                || mob.name().toLowerCase(Locale.ROOT).contains(query);
    }

    private int matchRank(CatalogMob mob, String query) {
        if (query.isEmpty()) {
            return 0;
        }
        String id = String.valueOf(mob.id());
        String name = mob.name().toLowerCase(Locale.ROOT);
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
            throw new IllegalStateException("Mob preview catalog is not loaded");
        }
        return data;
    }

    private record CatalogMob(int id, String name, Map<String, Integer> stats,
                              boolean iconAvailable, int x, int y) {
    }

    private record CatalogData(int cellSize, List<CatalogMob> mobs,
                               Map<Integer, CatalogMob> byId) {
    }
}
