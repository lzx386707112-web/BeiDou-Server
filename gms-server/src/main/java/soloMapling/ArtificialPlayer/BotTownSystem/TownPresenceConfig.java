package soloMapling.ArtificialPlayer.BotTownSystem;

import com.esotericsoftware.yamlbeans.YamlReader;
import java.awt.Point;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import soloMapling.ArtificialPlayer.BotTownSystem.TownOverrides;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownPresenceConfig.class */
public final class TownPresenceConfig {
    private static final String YAML_PATH = "soloMapling/ArtificialPlayer/BotTownSystem/TownPresence.yaml";
    private static volatile List<TownEntry> cached;

    private TownPresenceConfig() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownPresenceConfig$MapShare.class */
    public static final class MapShare {
        private final int mapId;
        private final int count;
        private final TownOverrides overrides;

        public MapShare(int mapId, int count, TownOverrides overrides) {
            this.mapId = mapId;
            this.count = count;
            this.overrides = overrides;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public int mapId() {
            return this.mapId;
        }

        public int count() {
            return this.count;
        }

        public TownOverrides overrides() {
            return this.overrides;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownPresenceConfig$TownEntry.class */
    public static final class TownEntry {
        private final String name;
        private final int levelLo;
        private final int levelHi;
        private final int wanderers;
        private final List<MapShare> maps;
        private final String dialogueOverride;

        public TownEntry(String name, int levelLo, int levelHi, int wanderers, List<MapShare> maps, String dialogueOverride) {
            this.name = name;
            this.levelLo = levelLo;
            this.levelHi = levelHi;
            this.wanderers = wanderers;
            this.maps = maps;
            this.dialogueOverride = dialogueOverride;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public String name() {
            return this.name;
        }

        public int levelLo() {
            return this.levelLo;
        }

        public int levelHi() {
            return this.levelHi;
        }

        public int wanderers() {
            return this.wanderers;
        }

        public List<MapShare> maps() {
            return this.maps;
        }

        public String dialogueOverride() {
            return this.dialogueOverride;
        }

        public int mainMapId() {
            if (this.maps.isEmpty()) {
                return -1;
            }
            return this.maps.get(0).mapId();
        }
    }

    public static List<TownEntry> towns() {
        List<TownEntry> local = cached;
        if (local == null) {
            local = load();
            cached = local;
        }
        return local;
    }

    public static List<TownEntry> reload() {
        cached = load();
        return cached;
    }

    public static Set<Integer> allTownMapIds() {
        Set<Integer> ids = new LinkedHashSet<>();
        for (TownEntry t : towns()) {
            for (MapShare m : t.maps()) {
                ids.add(Integer.valueOf(m.mapId()));
            }
        }
        return ids;
    }

    private static List<TownEntry> load() {
        List<TownEntry> out = new ArrayList<>();
        try {
            YamlReader reader = new YamlReader(soloMapling.server.SoloMaplingResource.openReader(YAML_PATH));
            Map<String, Object> root = (Map) reader.read();
            if (root == null) {
                return out;
            }
            Object townsNode = root.get("towns");
            if (!(townsNode instanceof List)) {
                return out;
            }
            List<?> townList = (List) townsNode;
            Map<Integer, List<Point>> sidecarPins = TownPinsStore.load();
            for (Object t : townList) {
                if (t instanceof Map) {
                    Map<?, ?> town = (Map) t;
                    String name = str(town.get("name"), "town");
                    int lo = toInt(town.get("level_lo"), 10);
                    int hi = toInt(town.get("level_hi"), lo);
                    int wanderers = toInt(town.get("wanderers"), 0);
                    String dialogue = str(town.get("dialogue"), null);
                    List<MapShare> shares = new ArrayList<>();
                    Object mapsNode = town.get("maps");
                    if (mapsNode instanceof List) {
                        List<?> mapList = (List) mapsNode;
                        for (Object m : mapList) {
                            if (m instanceof Map) {
                                Map<?, ?> mm = (Map) m;
                                int mapId = toInt(mm.get("map"), -1);
                                int count = toInt(mm.get("count"), 0);
                                if (mapId > 0 && count > 0) {
                                    shares.add(new MapShare(mapId, count, parseOverrides(mm, sidecarPins.getOrDefault(Integer.valueOf(mapId), List.of()))));
                                }
                            }
                        }
                    }
                    if (!shares.isEmpty()) {
                        out.add(new TownEntry(name, lo, hi, wanderers, shares, dialogue));
                    }
                }
            }
            return out;
        } catch (Exception e) {
            System.out.println("[TownPresenceConfig] failed to load BotTownSystem/TownPresence.yaml: " + e.getMessage());
            return new ArrayList();
        }
    }

    public static TownOverrides overridesFor(int mapId) {
        for (TownEntry t : towns()) {
            for (MapShare m : t.maps()) {
                if (m.mapId() == mapId) {
                    return m.overrides();
                }
            }
        }
        List<Point> sidecar = TownPinsStore.forMap(mapId);
        return sidecar.isEmpty() ? TownOverrides.EMPTY : new TownOverrides(List.of(), List.of(), sidecar);
    }

    private static TownOverrides parseOverrides(Map<?, ?> mm, List<Point> sidecarPins) {
        List<TownOverrides.Zone> ban = parseZones(mm.get("ban"), 1.0d);
        List<TownOverrides.Zone> boost = parseZones(mm.get("boost"), 2.0d);
        List<Point> pins = new ArrayList<>();
        Object pinsNode = mm.get("pins");
        if (pinsNode instanceof List) {
            List<?> pinList = (List) pinsNode;
            for (Object p : pinList) {
                if (p instanceof Map) {
                    Map<?, ?> pm = (Map) p;
                    int x = toInt(pm.get("x"), Integer.MIN_VALUE);
                    int y = toInt(pm.get("y"), Integer.MIN_VALUE);
                    if (x != Integer.MIN_VALUE && y != Integer.MIN_VALUE) {
                        pins.add(new Point(x, y));
                    }
                }
            }
        }
        pins.addAll(sidecarPins);
        if (ban.isEmpty() && boost.isEmpty() && pins.isEmpty()) {
            return TownOverrides.EMPTY;
        }
        return new TownOverrides(ban, boost, pins);
    }

    private static List<TownOverrides.Zone> parseZones(Object node, double defaultMult) {
        List<TownOverrides.Zone> out = new ArrayList<>();
        if (!(node instanceof List)) {
            return out;
        }
        List<?> list = (List) node;
        for (Object z : list) {
            if (z instanceof Map) {
                Map<?, ?> zm = (Map) z;
                int x1 = toInt(zm.get("x1"), Integer.MIN_VALUE);
                int x2 = toInt(zm.get("x2"), Integer.MAX_VALUE);
                int y1 = toInt(zm.get("y1"), Integer.MIN_VALUE);
                int y2 = toInt(zm.get("y2"), Integer.MAX_VALUE);
                double mult = toDouble(zm.get("mult"), defaultMult);
                out.add(new TownOverrides.Zone(x1, y1, x2, y2, mult));
            }
        }
        return out;
    }

    private static double toDouble(Object o, double fallback) {
        if (o instanceof Number) {
            Number n = (Number) o;
            return n.doubleValue();
        }
        if (o != null) {
            try {
                return Double.parseDouble(o.toString().trim());
            } catch (NumberFormatException e) {
            }
        }
        return fallback;
    }

    private static int toInt(Object o, int fallback) {
        if (o instanceof Number) {
            Number n = (Number) o;
            return n.intValue();
        }
        if (o != null) {
            try {
                return Integer.parseInt(o.toString().trim());
            } catch (NumberFormatException e) {
            }
        }
        return fallback;
    }

    private static String str(Object o, String fallback) {
        return o != null ? o.toString() : fallback;
    }
}
