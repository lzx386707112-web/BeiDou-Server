package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;
import org.gms.provider.Data;
import org.gms.provider.DataProvider;
import org.gms.provider.DataProviderFactory;
import org.gms.provider.DataTool;
import org.gms.provider.wz.WZFiles;
import soloMapling.ArtificialPlayer.BotTravelSystem.BotScriptedWarp;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCWorldGraph.class */
final class GCWorldGraph {
    private static final int NO_TARGET_MAPID = 999999999;
    private static final int[] EMPTY = new int[0];
    private static volatile Map<Integer, int[]> edges;

    private GCWorldGraph() {
    }

    static Map<Integer, int[]> get() {
        Map<Integer, int[]> map;
        Map<Integer, int[]> cached = edges;
        if (cached != null) {
            return cached;
        }
        synchronized (GCWorldGraph.class) {
            if (edges == null) {
                edges = build();
            }
            map = edges;
        }
        return map;
    }

    static boolean isReady() {
        return edges != null;
    }

    static int[] portalNeighbors(int mapId) {
        Map<Integer, int[]> g = edges;
        return g == null ? EMPTY : g.getOrDefault(Integer.valueOf(mapId), EMPTY);
    }

    static int mapCount() {
        Map<Integer, int[]> g = edges;
        return g == null ? 0 : g.size();
    }

    static List<Integer> route(int fromMapId, int toMapId, int maxHops) {
        if (fromMapId == toMapId) {
            return List.of();
        }
        if (maxHops <= 0) {
            return null;
        }
        Map<Integer, int[]> g = edges;
        if (g == null) {
            return null;
        }
        Map<Integer, Integer> cameFrom = new HashMap<>();
        ArrayDeque<Integer> frontier = new ArrayDeque<>();
        cameFrom.put(Integer.valueOf(fromMapId), Integer.valueOf(fromMapId));
        frontier.add(Integer.valueOf(fromMapId));
        int depth = 0;
        while (!frontier.isEmpty() && depth < maxHops) {
            depth++;
            for (int level = frontier.size(); level > 0; level--) {
                int current = frontier.poll().intValue();
                for (int next : neighbors(g, current)) {
                    if (cameFrom.putIfAbsent(Integer.valueOf(next), Integer.valueOf(current)) == null) {
                        if (next == toMapId) {
                            return reconstruct(cameFrom, fromMapId, toMapId);
                        }
                        frontier.add(Integer.valueOf(next));
                    }
                }
            }
        }
        return null;
    }

    private static int[] neighbors(Map<Integer, int[]> g, int mapId) {
        int[] portals = g.getOrDefault(Integer.valueOf(mapId), EMPTY);
        int[] taxi = GCTaxi.destinations(mapId);
        int[] warp = BotScriptedWarp.destinations(mapId);
        if (taxi.length == 0 && warp.length == 0) {
            return portals;
        }
        int[] all = new int[portals.length + taxi.length + warp.length];
        System.arraycopy(portals, 0, all, 0, portals.length);
        System.arraycopy(taxi, 0, all, portals.length, taxi.length);
        System.arraycopy(warp, 0, all, portals.length + taxi.length, warp.length);
        return all;
    }

    private static List<Integer> reconstruct(Map<Integer, Integer> cameFrom, int from, int to) {
        List<Integer> hops = new ArrayList<>();
        int iIntValue = to;
        while (true) {
            int at = iIntValue;
            if (at != from) {
                hops.add(Integer.valueOf(at));
                iIntValue = cameFrom.get(Integer.valueOf(at)).intValue();
            } else {
                Collections.reverse(hops);
                return List.copyOf(hops);
            }
        }
    }

    private static Map<Integer, int[]> build() {
        Map<Integer, int[]> out = new ConcurrentHashMap<>();
        ThreadLocal<DataProvider> mapSources = ThreadLocal.withInitial(() -> {
            return DataProviderFactory.getDataProvider(WZFiles.MAP);
        });
        ExecutorService pool = Executors.newFixedThreadPool(Math.max(2, Math.min(8, Runtime.getRuntime().availableProcessors())));
        Path mapRoot = Path.of(WZFiles.MAP.getFilePath(), "Map");
        for (int area = 0; area <= 9; area++) {
            Path areaDir = mapRoot.resolve("Map" + area);
            if (Files.isDirectory(areaDir, new LinkOption[0])) {
                try {
                    Stream<Path> files = Files.list(areaDir);
                    try {
                        Objects.requireNonNull(files);
                        Iterable<Path> iterable = files::iterator;
                        for (Path file : iterable) {
                            String name = file.getFileName().toString();
                            if (name.endsWith(".img.xml")) {
                                int fileArea = area;
                                try {
                                    int mapId = Integer.parseInt(name.substring(0, name.length() - ".img.xml".length()));
                                    pool.execute(() -> {
                                        try {
                                            readMap((DataProvider) mapSources.get(), fileArea, mapId, out);
                                        } catch (RuntimeException e) {
                                        }
                                    });
                                } catch (NumberFormatException e) {
                                }
                            }
                        }
                        if (files != null) {
                            files.close();
                        }
                    } catch (Throwable th) {
                        if (files != null) {
                            try {
                                files.close();
                            } catch (Throwable th2) {
                                th.addSuppressed(th2);
                            }
                        }
                        throw th;
                    }
                } catch (IOException e2) {
                }
            }
        }
        pool.shutdown();
        try {
            pool.awaitTermination(10L, TimeUnit.MINUTES);
        } catch (InterruptedException e3) {
            Thread.currentThread().interrupt();
        }
        return Collections.unmodifiableMap(out);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void readMap(DataProvider mapSource, int area, int mapId, Map<Integer, int[]> out) throws NumberFormatException {
        Data mapData = mapSource.getData(mapImgPath(area, mapId));
        if (mapData == null) {
            return;
        }
        Data info = mapData.getChildByPath("info");
        String link = info != null ? DataTool.getString("link", info, "") : "";
        if (!link.isEmpty()) {
            try {
                int linkId = Integer.parseInt(link);
                mapData = mapSource.getData(mapImgPath(linkId / 100000000, linkId));
                if (mapData == null) {
                    out.put(Integer.valueOf(mapId), EMPTY);
                    return;
                }
            } catch (NumberFormatException e) {
            }
        }
        Data portals = mapData.getChildByPath("portal");
        if (portals == null) {
            out.put(Integer.valueOf(mapId), EMPTY);
            return;
        }
        Set<Integer> targets = new TreeSet<>();
        for (Data portal : portals) {
            int targetMapId = DataTool.getInt("tm", portal, NO_TARGET_MAPID);
            if (targetMapId != NO_TARGET_MAPID && targetMapId != mapId && DataTool.getInt("pt", portal, 0) != 6) {
                String script = DataTool.getString("script", portal, "");
                if (script.isEmpty() && true) {
                    targets.add(Integer.valueOf(targetMapId));
                }
            }
        }
        int[] arr = new int[targets.size()];
        int i = 0;
        Iterator<Integer> it = targets.iterator();
        while (it.hasNext()) {
            int t = it.next().intValue();
            int i2 = i;
            i++;
            arr[i2] = t;
        }
        out.put(Integer.valueOf(mapId), arr);
    }

    private static String mapImgPath(int area, int mapId) {
        return "Map/Map" + area + "/" + String.format("%09d", Integer.valueOf(mapId)) + ".img";
    }
}
