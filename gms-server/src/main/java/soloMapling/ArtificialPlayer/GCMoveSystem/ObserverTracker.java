package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.gms.client.Character;
import org.gms.net.server.Server;
import org.gms.net.server.world.World;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import soloMapling.ArtificialPlayer.BotHelpers;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/ObserverTracker.class */
final class ObserverTracker {
    private static final long POLL_MS = 2000;
    private static final int HALO_PORTAL_RADIUS_PX = 350;
    private static final double HALO_PORTAL_RADIUS_SQ = 122500.0d;
    private static final long FORCE_TTL_MS = 2000;
    private static volatile Set<Integer> fullMaps = Set.of();
    private static volatile Set<Integer> haloMaps = Set.of();
    private static final long DWELL_MS = 4000;
    private static final TierDwell DWELL = new TierDwell(DWELL_MS);
    private static final AtomicBoolean STARTED = new AtomicBoolean(false);
    private static final Map<Integer, Long> forcedFull = new ConcurrentHashMap();

    private ObserverTracker() {
    }

    static boolean hasRealPlayerNow(MapleMap map) {
        if (map == null) {
            return false;
        }
        for (Character c : map.getAllPlayers()) {
            if (c != null && !BotHelpers.isBot(c)) {
                return true;
            }
        }
        return false;
    }

    static void markObservedNow(int mapId) {
        forcedFull.put(Integer.valueOf(mapId), Long.valueOf(System.currentTimeMillis() + FORCE_TTL_MS));
    }

    private static boolean forced(int mapId) {
        Long until = forcedFull.get(Integer.valueOf(mapId));
        if (until == null) {
            return false;
        }
        if (until.longValue() < System.currentTimeMillis()) {
            forcedFull.remove(Integer.valueOf(mapId));
            return false;
        }
        return true;
    }

    static void ensureStarted() {
        if (!STARTED.compareAndSet(false, true)) {
            return;
        }
        ScheduledExecutorService pool = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "gcmove-observer");
            t.setDaemon(true);
            return t;
        });
        pool.scheduleAtFixedRate(ObserverTracker::safeRefresh, 0L, POLL_MS, TimeUnit.MILLISECONDS);
    }

    static boolean started() {
        return STARTED.get();
    }

    static boolean isFull(int mapId) {
        return fullMaps.contains(Integer.valueOf(mapId)) || forced(mapId);
    }

    static boolean isHalo(int mapId) {
        return haloMaps.contains(Integer.valueOf(mapId));
    }

    static boolean isActiveMap(int mapId) {
        return DWELL.isActive(mapId) || forced(mapId);
    }

    static int fullCount() {
        return fullMaps.size();
    }

    static int haloCount() {
        return haloMaps.size();
    }

    static int activeCount() {
        return DWELL.size();
    }

    static Set<Integer> fullMaps() {
        return fullMaps;
    }

    static Set<Integer> haloMaps() {
        return haloMaps;
    }

    private static void safeRefresh() {
        try {
            refresh();
        } catch (Throwable th) {
        }
    }

    private static void refresh() {
        Server server = Server.getInstance();
        if (server == null) {
            return;
        }
        Set<Integer> full = new HashSet<>();
        List<Character> realPlayers = new ArrayList<>();
        for (World world : server.getWorlds()) {
            if (world != null) {
                for (Character chr : world.getPlayerStorage().getAllCharacters()) {
                    if (chr != null && !BotHelpers.isBot(chr)) {
                        full.add(Integer.valueOf(chr.getMapId()));
                        realPlayers.add(chr);
                    }
                }
            }
        }
        HashSet hashSet = new HashSet();
        if (GCWorldGraph.isReady()) {
            Iterator<Character> it = realPlayers.iterator();
            while (it.hasNext()) {
                addNearbyPortalMaps(it.next(), full, hashSet);
            }
        }
        Set<Integer> observed = new HashSet<>(full);
        observed.addAll(hashSet);
        DWELL.observe(observed, System.currentTimeMillis());
        fullMaps = full.isEmpty() ? Set.of() : Set.copyOf(full);
        haloMaps = hashSet.isEmpty() ? Set.of() : Set.copyOf(hashSet);
    }

    private static void addNearbyPortalMaps(Character chr, Set<Integer> full, Set<Integer> halo) {
        Point pos;
        int target;
        Point pp;
        MapleMap map = chr.getMap();
        if (map == null) {
            return;
        }
        int[] walkable = GCWorldGraph.portalNeighbors(chr.getMapId());
        if (walkable.length == 0 || (pos = chr.getPosition()) == null) {
            return;
        }
        for (Portal portal : map.getPortals()) {
            if (portal != null && (target = portal.getTargetMapId()) > 0 && !full.contains(Integer.valueOf(target)) && contains(walkable, target) && (pp = portal.getPosition()) != null && pos.distanceSq(pp) <= HALO_PORTAL_RADIUS_SQ) {
                halo.add(Integer.valueOf(target));
            }
        }
    }

    private static boolean contains(int[] arr, int value) {
        for (int x : arr) {
            if (x == value) {
                return true;
            }
        }
        return false;
    }
}
