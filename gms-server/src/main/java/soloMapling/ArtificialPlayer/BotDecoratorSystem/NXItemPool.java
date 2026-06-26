package soloMapling.ArtificialPlayer.BotDecoratorSystem;

import com.esotericsoftware.yamlbeans.YamlReader;
import org.gms.constants.inventory.EquipType;
import soloMapling.itemPool.EquipMetadataCache;

import java.io.File;
import java.io.FileReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Loads and serves the curated list of NX / cash cosmetic equips.
 * No level filter (NX has no reqLevel). Gender is resolved per item at load
 * time: explicit YAML override > body-slot ID-digit convention > unisex default.
 *
 * Call {@link #load()} once at startup (BotDecorateNX does this lazily).
 * Use {@link #getRandom(String, int)} to pick a random item for a given
 * category and bot gender.
 */
public class NXItemPool {

    private static final String YAML_PATH =
            "src/main/java/soloMapling/ArtificialPlayer/BotDecoratorSystem/NXItemPool.yaml";
    private static final String YAML_RESOURCE =
            "soloMapling/ArtificialPlayer/BotDecoratorSystem/NXItemPool.yaml";

    public static final int GENDER_MALE = 0;
    public static final int GENDER_FEMALE = 1;
    public static final int GENDER_UNISEX = 2;

    // Categories whose gender follows the v83 body-equip ID-digit convention.
    // Non-body categories (weapons/earrings/face/eye/rings) don't encode gender
    // in the ID the same way, so they default to unisex unless the YAML says
    // otherwise.
    private static final Set<String> BODY_SLOT_CATEGORIES = Set.of(
            "caps", "tops", "bottoms", "overalls", "shoes", "gloves", "capes"
    );

    public static class PoolItem {
        final int id;
        final int gender; // 0 male, 1 female, 2 unisex

        PoolItem(int id, int gender) {
            this.id = id;
            this.gender = gender;
        }
    }

    /**
     * Maps NXItemPool category names to EquipType(s) for auto-population
     * from the {@link EquipMetadataCache} when the YAML list is empty.
     * Weapons span many EquipTypes so they get their own array.
     */
    private static final Map<String, EquipType[]> CATEGORY_TO_EQUIP_TYPES = Map.ofEntries(
            Map.entry("caps",      new EquipType[]{EquipType.CAP}),
            Map.entry("tops",      new EquipType[]{EquipType.COAT}),
            Map.entry("bottoms",   new EquipType[]{EquipType.PANTS}),
            Map.entry("overalls",  new EquipType[]{EquipType.LONGCOAT}),
            Map.entry("shoes",     new EquipType[]{EquipType.SHOES}),
            Map.entry("gloves",    new EquipType[]{EquipType.GLOVES}),
            Map.entry("capes",     new EquipType[]{EquipType.CAPE}),
            Map.entry("earrings",  new EquipType[]{EquipType.EARRING}),
            Map.entry("face",      new EquipType[]{EquipType.FACE}),
            Map.entry("eye",       new EquipType[]{EquipType.ACCESSORY}),
            Map.entry("rings",     new EquipType[]{EquipType.RING}),
            Map.entry("weapons",   new EquipType[]{
                    EquipType.SWORD, EquipType.AXE, EquipType.MACE, EquipType.DAGGER,
                    EquipType.WAND, EquipType.STAFF, EquipType.SWORD_2H, EquipType.AXE_2H,
                    EquipType.MACE_2H, EquipType.SPEAR, EquipType.POLEARM, EquipType.BOW,
                    EquipType.CROSSBOW, EquipType.CLAW, EquipType.KNUCKLER, EquipType.PISTOL
            })
    );

    private static final Map<String, int[]> FALLBACK_ITEMS = Map.ofEntries(
            Map.entry("weapons", new int[]{
                    1702022, 1702036, 1702181, 1702220, 1702340, 1702585,
                    1702631, 1702750, 1702787, 1702988
            }),
            Map.entry("overalls", new int[]{
                    1052248, 1052512, 1052923, 1053156, 1053552, 1053625
            }),
            Map.entry("tops", new int[]{
                    1042270, 1042264, 1042099, 1042072, 1042114, 1042339
            }),
            Map.entry("bottoms", new int[]{
                    1062219, 1062231, 1062033, 1062147, 1062184, 1062281
            }),
            Map.entry("shoes", new int[]{
                    1072010, 1072153, 1072337, 1072344, 1072455
            }),
            Map.entry("gloves", new int[]{
                    1082145, 1082173, 1082232, 1082276
            }),
            Map.entry("capes", new int[]{
                    1102041, 1102084, 1102140, 1102172
            })
    );

    private static final Map<String, List<PoolItem>> pools = new HashMap<>();
    private static boolean loaded = false;

    @SuppressWarnings("unchecked")
    public static synchronized void load() {
        if (loaded) return;

        try {
            YamlReader reader = new YamlReader(openYamlReader());
            Map<String, Object> root = (Map<String, Object>) reader.read();
            if (root == null) root = Collections.emptyMap();

            int itemCount = 0;
            for (Map.Entry<String, Object> entry : root.entrySet()) {
                String category = entry.getKey();
                Object val = entry.getValue();
                if (!(val instanceof List)) continue;

                List<PoolItem> list = new ArrayList<>();
                for (Object raw : (List<?>) val) {
                    PoolItem item = parseEntry(raw, category);
                    if (item != null) {
                        list.add(item);
                        itemCount++;
                    }
                }
                pools.put(category, list);
            }

            // Auto-populate empty categories from EquipMetadataCache
            int cacheCount = 0;
            if (hasEmptyAutoCategory() && !EquipMetadataCache.isInitialized()) {
                EquipMetadataCache.initialize();
            }
            if (EquipMetadataCache.isInitialized()) {
                EquipMetadataCache cache = EquipMetadataCache.get();
                for (Map.Entry<String, EquipType[]> mapping : CATEGORY_TO_EQUIP_TYPES.entrySet()) {
                    String category = mapping.getKey();
                    List<PoolItem> existing = pools.get(category);
                    if (existing != null && !existing.isEmpty()) continue;

                    List<PoolItem> cacheItems = loadCashItemsFromCache(cache, category, mapping.getValue());
                    if (!cacheItems.isEmpty()) {
                        pools.put(category, cacheItems);
                        cacheCount += cacheItems.size();
                        System.out.println("[NXItemPool]   Auto-populated '" + category
                                + "' with " + cacheItems.size() + " cash items from cache");
                    }
                }
            } else {
                System.out.println("[NXItemPool]   EquipMetadataCache not initialized — "
                        + "empty categories will have no NX items");
            }

            int fallbackCount = addFallbackItemsForEmptyCategories();

            loaded = true;
            System.out.println("[NXItemPool] Loaded " + itemCount + " curated + "
                    + cacheCount + " cache-auto + " + fallbackCount
                    + " fallback items across " + pools.size() + " categories");
        } catch (Exception e) {
            System.err.println("[NXItemPool] Failed to load YAML: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private static boolean hasEmptyAutoCategory() {
        for (String category : CATEGORY_TO_EQUIP_TYPES.keySet()) {
            List<PoolItem> existing = pools.get(category);
            if (existing == null || existing.isEmpty()) {
                return true;
            }
        }
        return false;
    }

    private static int addFallbackItemsForEmptyCategories() {
        int count = 0;
        for (Map.Entry<String, int[]> entry : FALLBACK_ITEMS.entrySet()) {
            String category = entry.getKey();
            List<PoolItem> existing = pools.get(category);
            if (existing != null && !existing.isEmpty()) {
                continue;
            }

            List<PoolItem> fallback = new ArrayList<>();
            for (int itemId : entry.getValue()) {
                fallback.add(new PoolItem(itemId, GENDER_UNISEX));
            }
            pools.put(category, fallback);
            count += fallback.size();
            System.out.println("[NXItemPool]   Fallback-populated '" + category
                    + "' with " + fallback.size() + " built-in items");
        }
        return count;
    }

    private static java.io.Reader openYamlReader() throws Exception {
        File file = new File(YAML_PATH);
        if (file.exists()) {
            return new FileReader(file);
        }
        InputStream input = NXItemPool.class.getClassLoader().getResourceAsStream(YAML_RESOURCE);
        if (input == null) {
            throw new IllegalStateException("Cannot find " + YAML_RESOURCE + " on classpath");
        }
        return new InputStreamReader(input, StandardCharsets.UTF_8);
    }

    /**
     * Pull all cash equips for the given EquipTypes from the pre-built cache.
     * Pure in-memory — no WZ access.
     */
    private static List<PoolItem> loadCashItemsFromCache(EquipMetadataCache cache,
                                                          String category, EquipType[] equipTypes) {
        List<PoolItem> result = new ArrayList<>();
        for (EquipType eqType : equipTypes) {
            for (EquipMetadataCache.EquipEntry entry : cache.getCashByType(eqType)) {
                result.add(new PoolItem(entry.id, deriveGender(entry.id, category, null)));
            }
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private static PoolItem parseEntry(Object raw, String category) {
        if (raw == null) return null;
        if (raw instanceof Number || raw instanceof String) {
            int id = toInt(raw);
            return new PoolItem(id, deriveGender(id, category, null));
        }
        if (raw instanceof Map) {
            Map<String, Object> m = (Map<String, Object>) raw;
            int id = toInt(m.get("id"));
            Integer override = parseGender(m.get("gender"));
            return new PoolItem(id, deriveGender(id, category, override));
        }
        return null;
    }

    private static int deriveGender(int itemId, String category, Integer override) {
        if (override != null) return override;
        if (BODY_SLOT_CATEGORIES.contains(category)) {
            int digit = (itemId / 1000) % 10;
            return (digit == GENDER_MALE || digit == GENDER_FEMALE) ? digit : GENDER_UNISEX;
        }
        return GENDER_UNISEX;
    }

    private static Integer parseGender(Object raw) {
        if (raw == null) return null;
        String s = raw.toString().toLowerCase();
        switch (s) {
            case "male":
            case "0":
                return GENDER_MALE;
            case "female":
            case "1":
                return GENDER_FEMALE;
            case "unisex":
            case "2":
                return GENDER_UNISEX;
            default:
                return null;
        }
    }

    /**
     * Pick a random NX item from the given category for a bot of the given
     * gender. Filters by gender (unisex items always pass). Returns null if the
     * category is empty, the pool isn't loaded, or no item is eligible.
     */
    public static Integer getRandom(String category, int botGender) {
        if (!loaded) return null;
        List<PoolItem> list = pools.get(category);
        if (list == null || list.isEmpty()) return null;

        List<PoolItem> eligible = new ArrayList<>(list.size());
        for (PoolItem item : list) {
            if (item.gender == GENDER_UNISEX || item.gender == botGender) {
                eligible.add(item);
            }
        }
        if (eligible.isEmpty()) return null;

        return eligible.get(ThreadLocalRandom.current().nextInt(eligible.size())).id;
    }

    private static int toInt(Object obj) {
        if (obj instanceof Number) return ((Number) obj).intValue();
        if (obj instanceof String) return Integer.parseInt((String) obj);
        return 0;
    }

    public static boolean isLoaded() {
        return loaded;
    }

    /**
     * Force a reload — clears existing pools and re-reads YAML + cache.
     * Useful for hot-reloading curated lists without restarting the server.
     */
    public static synchronized void forceReload() {
        pools.clear();
        loaded = false;
        load();
    }
}
