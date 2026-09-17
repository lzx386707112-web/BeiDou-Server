package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.OpenOption;
import java.nio.file.Path;
import java.nio.file.attribute.FileAttribute;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.gms.server.maps.Foothold;
import org.gms.server.maps.MapManager;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import org.gms.server.maps.Rope;
import soloMapling.ArtificialPlayer.BotAttackSystem.BotAttackData;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotMovementManager;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationGraph;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotPhysicsEngine;
import soloMapling.DebugUtilities;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider.class */
final class BotNavigationGraphProvider {
    private static final int GRAPH_VERSION = 61;
    private static final int MAX_DROP_PX = 300;
    private static final int DOWN_JUMP_MAX_DROP_PX = 200;
    private static final int DOWN_JUMP_COST_PENALTY_MS = 2000;
    private static final int ENDPOINT_ANCHOR_SPACING_PX = 10;
    private static final int SAME_SOLID_NEST_GAP_PX = 8;
    private static final int ROPE_ANCHOR_INTERVAL_PX = 30;
    private static final int JUMP_POST_LANDING_STABILITY_TICKS = 3;
    private static final int MAX_PROFILED_JUMP_REGIONS = 5;
    private static final int FAST_WARMUP_MAX_FOOTHOLDS = 200;
    private static final Logger log = LoggerFactory.getLogger(BotNavigationGraphProvider.class);
    private static final Path CACHE_DIR = Path.of("cache", "bot-nav", "v61");
    private static final Map<GraphCacheKey, BotNavigationGraph> GRAPHS = new ConcurrentHashMap();
    private static final Map<GraphCacheKey, CompletableFuture<BotNavigationGraph>> PENDING_GRAPHS = new ConcurrentHashMap();
    private static final Map<GraphCacheKey, GraphBuildReport> LAST_BUILD_REPORTS = new ConcurrentHashMap();
    private static final Map<Integer, Set<Integer>> COLLIDABLE_WALL_IDS_BY_MAP_ID = new ConcurrentHashMap();
    private static final Map<Integer, Set<Integer>> COLLIDABLE_FROM_BELOW_IDS_BY_MAP_ID = new ConcurrentHashMap();
    private static final ThreadLocal<BuildProfileBuilder> ACTIVE_BUILD_PROFILE = new ThreadLocal<>();
    private static final ExecutorService GRAPH_WARMUP_EXECUTOR = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "bot-nav-graph-warmup");
        thread.setDaemon(true);
        return thread;
    });
    private static final ExecutorService FAST_GRAPH_WARMUP_EXECUTOR = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "bot-nav-graph-warmup-fast");
        thread.setDaemon(true);
        return thread;
    });

    BotNavigationGraphProvider() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$GraphCacheKey.class */
    private static final class GraphCacheKey {
        private final int mapId;
        private final int totalSpeedStat;
        private final int totalJumpStat;
        private final boolean snowShoes;

        private GraphCacheKey(int mapId, int totalSpeedStat, int totalJumpStat, boolean snowShoes) {
            this.mapId = mapId;
            this.totalSpeedStat = totalSpeedStat;
            this.totalJumpStat = totalJumpStat;
            this.snowShoes = snowShoes;
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

        public int totalSpeedStat() {
            return this.totalSpeedStat;
        }

        public int totalJumpStat() {
            return this.totalJumpStat;
        }

        public boolean snowShoes() {
            return this.snowShoes;
        }

        static GraphCacheKey from(int mapId, BotMovementProfile profile) {
            BotMovementProfile effective = profile == null ? BotMovementProfile.base() : profile;
            return new GraphCacheKey(mapId, effective.totalSpeedStat(), effective.totalJumpStat(), effective.snowShoes());
        }
    }

    private static BotMovementProfile canonicalProfile(MapleMap map, BotMovementProfile profile) {
        if (profile == null || !profile.snowShoes() || BotPhysicsEngine.slipperyGround(map)) {
            return profile;
        }
        return new BotMovementProfile(profile.totalSpeedStat(), profile.totalJumpStat(), false);
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$GraphBuildReport.class */
    static final class GraphBuildReport {
        final long buildAnchorPointsNs;
        final int mapId;
        final int totalSpeedStat;
        final int totalJumpStat;
        final int footholdCount;
        final int walkableFootholdCount;
        final int ropeCount;
        final int regionCount;
        final int totalEdgeCount;
        final int walkEdgeCount;
        final int jumpEdgeCount;
        final int dropEdgeCount;
        final int climbEdgeCount;
        final int portalEdgeCount;
        final long collectFootholdsNs;
        final long buildRegionsNs;
        final long addRopeRegionsNs;
        final long buildFeatureXsNs;
        final long buildWalkEdgesNs;
        final long buildDropEdgesNs;
        final long buildJumpEdgesNs;
        final long buildRopeEntryEdgesNs;
        final long buildRopeExitEdgesNs;
        final long buildPortalEdgesNs;
        final long totalBuildNs;
        final long jumpSampleCount;
        final long jumpCacheHitCount;
        final long jumpCacheMissCount;
        final long jumpBoundaryRefineProbeCount;
        final List<JumpRegionProfile> slowestJumpRegions;

        GraphBuildReport(int mapId, int totalSpeedStat, int totalJumpStat, int footholdCount, int walkableFootholdCount, int ropeCount, int regionCount, int totalEdgeCount, int walkEdgeCount, int jumpEdgeCount, int dropEdgeCount, int climbEdgeCount, int portalEdgeCount, long buildAnchorPointsNs, long collectFootholdsNs, long buildRegionsNs, long addRopeRegionsNs, long buildFeatureXsNs, long buildWalkEdgesNs, long buildDropEdgesNs, long buildJumpEdgesNs, long buildRopeEntryEdgesNs, long buildRopeExitEdgesNs, long buildPortalEdgesNs, long totalBuildNs, long jumpSampleCount, long jumpCacheHitCount, long jumpCacheMissCount, long jumpBoundaryRefineProbeCount, List<JumpRegionProfile> slowestJumpRegions) {
            this.buildAnchorPointsNs = buildAnchorPointsNs;
            this.mapId = mapId;
            this.totalSpeedStat = totalSpeedStat;
            this.totalJumpStat = totalJumpStat;
            this.footholdCount = footholdCount;
            this.walkableFootholdCount = walkableFootholdCount;
            this.ropeCount = ropeCount;
            this.regionCount = regionCount;
            this.totalEdgeCount = totalEdgeCount;
            this.walkEdgeCount = walkEdgeCount;
            this.jumpEdgeCount = jumpEdgeCount;
            this.dropEdgeCount = dropEdgeCount;
            this.climbEdgeCount = climbEdgeCount;
            this.portalEdgeCount = portalEdgeCount;
            this.collectFootholdsNs = collectFootholdsNs;
            this.buildRegionsNs = buildRegionsNs;
            this.addRopeRegionsNs = addRopeRegionsNs;
            this.buildFeatureXsNs = buildFeatureXsNs;
            this.buildWalkEdgesNs = buildWalkEdgesNs;
            this.buildDropEdgesNs = buildDropEdgesNs;
            this.buildJumpEdgesNs = buildJumpEdgesNs;
            this.buildRopeEntryEdgesNs = buildRopeEntryEdgesNs;
            this.buildRopeExitEdgesNs = buildRopeExitEdgesNs;
            this.buildPortalEdgesNs = buildPortalEdgesNs;
            this.totalBuildNs = totalBuildNs;
            this.jumpSampleCount = jumpSampleCount;
            this.jumpCacheHitCount = jumpCacheHitCount;
            this.jumpCacheMissCount = jumpCacheMissCount;
            this.jumpBoundaryRefineProbeCount = jumpBoundaryRefineProbeCount;
            this.slowestJumpRegions = new ArrayList(slowestJumpRegions);
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$JumpRegionProfile.class */
    static final class JumpRegionProfile {
        private final int regionId;
        private final int width;
        private final int sampleCount;
        private final int edgeCount;
        private final int cacheHits;
        private final int cacheMisses;
        private final long elapsedNs;

        JumpRegionProfile(int regionId, int width, int sampleCount, int edgeCount, int cacheHits, int cacheMisses, long elapsedNs) {
            this.regionId = regionId;
            this.width = width;
            this.sampleCount = sampleCount;
            this.edgeCount = edgeCount;
            this.cacheHits = cacheHits;
            this.cacheMisses = cacheMisses;
            this.elapsedNs = elapsedNs;
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

        public int regionId() {
            return this.regionId;
        }

        public int width() {
            return this.width;
        }

        public int sampleCount() {
            return this.sampleCount;
        }

        public int edgeCount() {
            return this.edgeCount;
        }

        public int cacheHits() {
            return this.cacheHits;
        }

        public int cacheMisses() {
            return this.cacheMisses;
        }

        public long elapsedNs() {
            return this.elapsedNs;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$BuildProfileBuilder.class */
    private static final class BuildProfileBuilder {
        private long buildAnchorPointsNs;
        private final int mapId;
        private final int totalSpeedStat;
        private final int totalJumpStat;
        private int footholdCount;
        private int walkableFootholdCount;
        private int ropeCount;
        private int regionCount;
        private int totalEdgeCount;
        private int walkEdgeCount;
        private int jumpEdgeCount;
        private int dropEdgeCount;
        private int climbEdgeCount;
        private int portalEdgeCount;
        private long collectFootholdsNs;
        private long buildRegionsNs;
        private long addRopeRegionsNs;
        private long buildFeatureXsNs;
        private long buildWalkEdgesNs;
        private long buildDropEdgesNs;
        private long buildJumpEdgesNs;
        private long buildRopeEntryEdgesNs;
        private long buildRopeExitEdgesNs;
        private long buildPortalEdgesNs;
        private long jumpSampleCount;
        private long jumpCacheHitCount;
        private long jumpCacheMissCount;
        private long jumpBoundaryRefineProbeCount;
        private final long buildStartedAtNs = System.nanoTime();
        private final List<JumpRegionProfile> slowestJumpRegions = new ArrayList();

        private BuildProfileBuilder(int mapId, BotMovementProfile movementProfile) {
            this.mapId = mapId;
            this.totalSpeedStat = movementProfile.totalSpeedStat();
            this.totalJumpStat = movementProfile.totalJumpStat();
        }

        private void recordEdge(BotNavigationGraph.EdgeType type) {
            this.totalEdgeCount++;
            switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[type.ordinal()]) {
                case 1:
                    this.walkEdgeCount++;
                    break;
                case 2:
                    this.jumpEdgeCount++;
                    break;
                case BotNavigationGraphProvider.JUMP_POST_LANDING_STABILITY_TICKS /* 3 */:
                    this.dropEdgeCount++;
                    break;
                case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                    this.climbEdgeCount++;
                    break;
                case BotNavigationGraphProvider.MAX_PROFILED_JUMP_REGIONS /* 5 */:
                    this.portalEdgeCount++;
                    break;
            }
        }

        private void recordJumpSample(boolean cacheHit) {
            this.jumpSampleCount++;
            if (cacheHit) {
                this.jumpCacheHitCount++;
            } else {
                this.jumpCacheMissCount++;
            }
        }

        private void recordJumpBoundaryRefineProbe() {
            this.jumpBoundaryRefineProbeCount++;
        }

        private void recordJumpRegion(JumpRegionProfile profile) {
            this.slowestJumpRegions.add(profile);
            this.slowestJumpRegions.sort(Comparator.comparingLong((JumpRegionProfile v0) -> v0.elapsedNs()).reversed());
            if (this.slowestJumpRegions.size() > BotNavigationGraphProvider.MAX_PROFILED_JUMP_REGIONS) {
                this.slowestJumpRegions.removeLast();
            }
        }

        private GraphBuildReport finish() {
            return new GraphBuildReport(this.mapId, this.totalSpeedStat, this.totalJumpStat, this.footholdCount, this.walkableFootholdCount, this.ropeCount, this.regionCount, this.totalEdgeCount, this.walkEdgeCount, this.jumpEdgeCount, this.dropEdgeCount, this.climbEdgeCount, this.portalEdgeCount, this.buildAnchorPointsNs, this.collectFootholdsNs, this.buildRegionsNs, this.addRopeRegionsNs, this.buildFeatureXsNs, this.buildWalkEdgesNs, this.buildDropEdgesNs, this.buildJumpEdgesNs, this.buildRopeEntryEdgesNs, this.buildRopeExitEdgesNs, this.buildPortalEdgesNs, System.nanoTime() - this.buildStartedAtNs, this.jumpSampleCount, this.jumpCacheHitCount, this.jumpCacheMissCount, this.jumpBoundaryRefineProbeCount, this.slowestJumpRegions);
        }
    }

    /* renamed from: soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationGraphProvider$1, reason: invalid class name */
    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$1.class */
    static /* synthetic */ class AnonymousClass1 {
        static final /* synthetic */ int[] $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType = new int[BotNavigationGraph.EdgeType.values().length];

        static {
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.WALK.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.JUMP.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.DROP.ordinal()] = BotNavigationGraphProvider.JUMP_POST_LANDING_STABILITY_TICKS;
            } catch (NoSuchFieldError e3) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.CLIMB.ordinal()] = 4;
            } catch (NoSuchFieldError e4) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.PORTAL.ordinal()] = BotNavigationGraphProvider.MAX_PROFILED_JUMP_REGIONS;
            } catch (NoSuchFieldError e5) {
            }
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$JumpLaunchWindow.class */
    private static final class JumpLaunchWindow {
        private final int minX;
        private final int maxX;
        private final Point startPoint;
        private final Point endPoint;
        private final int landingTimeMs;

        private JumpLaunchWindow(int minX, int maxX, Point startPoint, Point endPoint, int landingTimeMs) {
            this.minX = minX;
            this.maxX = maxX;
            this.startPoint = startPoint;
            this.endPoint = endPoint;
            this.landingTimeMs = landingTimeMs;
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

        public int minX() {
            return this.minX;
        }

        public int maxX() {
            return this.maxX;
        }

        public Point startPoint() {
            return this.startPoint;
        }

        public Point endPoint() {
            return this.endPoint;
        }

        public int landingTimeMs() {
            return this.landingTimeMs;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$JumpBuildStats.class */
    private static final class JumpBuildStats {
        int sampleCount;
        int edgeCount;
        int cacheHits;
        int cacheMisses;

        private JumpBuildStats() {
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$JumpLandingKey.class */
    private static final class JumpLandingKey {
        private final int x;
        private final int y;
        private final int launchStepX;

        private JumpLandingKey(int x, int y, int launchStepX) {
            this.x = x;
            this.y = y;
            this.launchStepX = launchStepX;
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

        public int x() {
            return this.x;
        }

        public int y() {
            return this.y;
        }

        public int launchStepX() {
            return this.launchStepX;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$JumpLandingCache.class */
    private static final class JumpLandingCache {
        private final Map<JumpLandingKey, BotPhysicsEngine.PostLandingJump> hits = new HashMap();
        private final Set<JumpLandingKey> misses = new HashSet();

        private JumpLandingCache() {
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$RopeGrabKey.class */
    private static final class RopeGrabKey {
        private final int x;
        private final int y;
        private final int launchStepX;
        private final int ropeX;
        private final int ropeTopY;
        private final int ropeBottomY;

        private RopeGrabKey(int x, int y, int launchStepX, int ropeX, int ropeTopY, int ropeBottomY) {
            this.x = x;
            this.y = y;
            this.launchStepX = launchStepX;
            this.ropeX = ropeX;
            this.ropeTopY = ropeTopY;
            this.ropeBottomY = ropeBottomY;
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

        public int x() {
            return this.x;
        }

        public int y() {
            return this.y;
        }

        public int launchStepX() {
            return this.launchStepX;
        }

        public int ropeX() {
            return this.ropeX;
        }

        public int ropeTopY() {
            return this.ropeTopY;
        }

        public int ropeBottomY() {
            return this.ropeBottomY;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$RopeGrabCache.class */
    private static final class RopeGrabCache {
        private final Map<RopeGrabKey, Point> hits = new HashMap();
        private final Set<RopeGrabKey> misses = new HashSet();

        private RopeGrabCache() {
        }
    }

    static BotNavigationGraph getGraph(MapleMap map) {
        return getGraph(map, BotMovementProfile.base());
    }

    static BotNavigationGraph getGraph(MapleMap map, BotMovementProfile movementProfile) {
        if (map == null) {
            return null;
        }
        BotMovementProfile movementProfile2 = canonicalProfile(map, movementProfile);
        GraphCacheKey key = GraphCacheKey.from(map.getId(), movementProfile2);
        BotNavigationGraph cached = GRAPHS.get(key);
        if (cached != null) {
            return cached;
        }
        return getOrStartGraphLoad(map, movementProfile2, key, false).join();
    }

    static BotNavigationGraph peekGraph(MapleMap map) {
        if (map == null) {
            return null;
        }
        for (Map.Entry<GraphCacheKey, BotNavigationGraph> entry : GRAPHS.entrySet()) {
            if (entry.getKey().mapId() == map.getId()) {
                return entry.getValue();
            }
        }
        return null;
    }

    static BotNavigationGraph peekGraph(MapleMap map, BotMovementProfile movementProfile) {
        if (map == null) {
            return null;
        }
        return GRAPHS.get(GraphCacheKey.from(map.getId(), canonicalProfile(map, movementProfile)));
    }

    static BotNavigationGraph peekClosestGraph(MapleMap map, BotMovementProfile movementProfile) {
        if (map == null) {
            return null;
        }
        GraphCacheKey requested = GraphCacheKey.from(map.getId(), canonicalProfile(map, movementProfile));
        BotNavigationGraph bestGraph = null;
        int bestDistance = Integer.MAX_VALUE;
        for (Map.Entry<GraphCacheKey, BotNavigationGraph> entry : GRAPHS.entrySet()) {
            GraphCacheKey key = entry.getKey();
            if (key.mapId() == requested.mapId()) {
                int distance = Math.abs(key.totalSpeedStat() - requested.totalSpeedStat()) + Math.abs(key.totalJumpStat() - requested.totalJumpStat()) + (key.snowShoes() != requested.snowShoes() ? 1000 : 0);
                if (bestGraph == null || distance < bestDistance) {
                    bestGraph = entry.getValue();
                    bestDistance = distance;
                }
            }
        }
        return bestGraph;
    }

    static BotNavigationGraph peekBestGraph(MapleMap map, BotMovementProfile movementProfile) {
        BotNavigationGraph exact = peekGraph(map, movementProfile);
        return exact != null ? exact : peekClosestGraph(map, movementProfile);
    }

    static void warmGraphAsync(MapleMap map, BotMovementProfile movementProfile) {
        if (map == null) {
            return;
        }
        BotMovementProfile movementProfile2 = canonicalProfile(map, movementProfile);
        GraphCacheKey key = GraphCacheKey.from(map.getId(), movementProfile2);
        if (GRAPHS.containsKey(key)) {
            return;
        }
        getOrStartGraphLoad(map, movementProfile2, key, true);
    }

    static void warmGraphsForRouteAsync(MapManager mapFactory, List<Integer> mapIds, BotMovementProfile movementProfile) {
        GRAPH_WARMUP_EXECUTOR.execute(() -> {
            Iterator it = mapIds.iterator();
            while (it.hasNext()) {
                int mapId = ((Integer) it.next()).intValue();
                try {
                    warmGraphAsync(mapFactory.getMap(mapId), movementProfile);
                } catch (RuntimeException e) {
                    log.warn("Route prewarm failed for map {}", Integer.valueOf(mapId), e);
                }
            }
        });
    }

    static BotNavigationGraph rebuildGraph(MapleMap map) {
        return rebuildGraph(map, BotMovementProfile.base());
    }

    static BotNavigationGraph rebuildGraph(MapleMap map, BotMovementProfile movementProfile) {
        GraphCacheKey key = GraphCacheKey.from(map.getId(), movementProfile);
        BotNavigationGraph rebuilt = buildGraph(map, movementProfile);
        GRAPHS.put(key, rebuilt);
        CompletableFuture<BotNavigationGraph> pending = PENDING_GRAPHS.remove(key);
        if (pending != null) {
            pending.complete(rebuilt);
        }
        saveGraph(rebuilt);
        return rebuilt;
    }

    private static CompletableFuture<BotNavigationGraph> getOrStartGraphLoad(MapleMap map, BotMovementProfile movementProfile, GraphCacheKey key, boolean async) {
        BotNavigationGraph cached = GRAPHS.get(key);
        if (cached != null) {
            return CompletableFuture.completedFuture(cached);
        }
        CompletableFuture<BotNavigationGraph> existing = PENDING_GRAPHS.get(key);
        if (existing != null) {
            return existing;
        }
        CompletableFuture<BotNavigationGraph> future = new CompletableFuture<>();
        CompletableFuture<BotNavigationGraph> race = PENDING_GRAPHS.putIfAbsent(key, future);
        if (race != null) {
            return race;
        }
        Runnable task = () -> {
            try {
                try {
                    BotNavigationGraph graph = loadOrBuildGraph(map, movementProfile, key);
                    GRAPHS.put(key, graph);
                    future.complete(graph);
                    PENDING_GRAPHS.remove(key, future);
                } catch (Throwable t) {
                    future.completeExceptionally(t);
                    log.warn("Failed to warm bot nav graph for map {} speed={} jump={}", new Object[]{Integer.valueOf(key.mapId()), Integer.valueOf(key.totalSpeedStat()), Integer.valueOf(key.totalJumpStat()), t});
                    PENDING_GRAPHS.remove(key, future);
                }
            } catch (Throwable th) {
                PENDING_GRAPHS.remove(key, future);
                throw th;
            }
        };
        if (async) {
            selectWarmupExecutor(map).execute(task);
        } else {
            task.run();
        }
        return future;
    }

    private static ExecutorService selectWarmupExecutor(MapleMap map) {
        return isFastWarmupCandidate(map) ? FAST_GRAPH_WARMUP_EXECUTOR : GRAPH_WARMUP_EXECUTOR;
    }

    private static boolean isFastWarmupCandidate(MapleMap map) {
        return (map == null || map.getFootholds() == null || map.getFootholds().getAllFootholds().size() > 200) ? false : true;
    }

    private static BotNavigationGraph loadOrBuildGraph(MapleMap map, BotMovementProfile movementProfile, GraphCacheKey key) {
        BotNavigationGraph cached = loadGraph(key);
        if (cached != null) {
            return cached;
        }
        BotNavigationGraph built = buildGraph(map, movementProfile);
        saveGraph(built);
        return built;
    }

    private static BotNavigationGraph loadGraph(GraphCacheKey key) {
        Path file = graphFile(key);
        if (!Files.isRegularFile(file, new LinkOption[0])) {
            return null;
        }
        try {
            ObjectInputStream in = new ObjectInputStream(Files.newInputStream(file, new OpenOption[0]));
            try {
                Object loaded = in.readObject();
                if (!(loaded instanceof BotNavigationGraph)) {
                    in.close();
                    return null;
                }
                BotNavigationGraph graph = (BotNavigationGraph) loaded;
                if (graph.version != GRAPH_VERSION || graph.mapId != key.mapId() || graph.movementProfile.totalSpeedStat() != key.totalSpeedStat() || graph.movementProfile.totalJumpStat() != key.totalJumpStat()) {
                    in.close();
                    return null;
                }
                seedCachedFootholdCollisionIds(graph);
                in.close();
                return graph;
            } catch (Throwable th) {
                try {
                    in.close();
                } catch (Throwable th2) {
                    th.addSuppressed(th2);
                }
                throw th;
            }
        } catch (IOException | ClassNotFoundException e) {
            log.debug("Failed to load bot nav graph cache for map {} speed={} jump={}", new Object[]{Integer.valueOf(key.mapId()), Integer.valueOf(key.totalSpeedStat()), Integer.valueOf(key.totalJumpStat()), e});
            return null;
        }
    }

    private static void saveGraph(BotNavigationGraph graph) {
        try {
            Files.createDirectories(CACHE_DIR, new FileAttribute[0]);
            ObjectOutputStream out = new ObjectOutputStream(Files.newOutputStream(graphFile(GraphCacheKey.from(graph.mapId, graph.movementProfile)), new OpenOption[0]));
            try {
                out.writeObject(graph);
                out.close();
            } finally {
            }
        } catch (IOException e) {
            log.debug("Failed to save bot nav graph cache for map {}", Integer.valueOf(graph.mapId), e);
        }
    }

    private static Path graphFile(GraphCacheKey key) {
        return CACHE_DIR.resolve(key.mapId() + "-s" + key.totalSpeedStat() + "-j" + key.totalJumpStat() + ".bin");
    }

    private static BotNavigationGraph buildGraph(MapleMap map, BotMovementProfile movementProfile) {
        BotMovementProfile movementProfile2 = movementProfile == null ? BotMovementProfile.base() : movementProfile;
        BuildProfileBuilder buildProfile = new BuildProfileBuilder(map.getId(), movementProfile2);
        ACTIVE_BUILD_PROFILE.set(buildProfile);
        try {
            List<Foothold> footholds = map.getFootholds() == null ? List.of() : map.getFootholds().getAllFootholds();
            Map<Integer, Foothold> footholdsById = new HashMap<>();
            List<Foothold> walkableFootholds = new ArrayList<>();
            long phaseStartedAt = System.nanoTime();
            Set<Integer> collidableWallIds = new HashSet<>();
            for (Foothold foothold : footholds) {
                footholdsById.put(Integer.valueOf(foothold.getId()), foothold);
                if (!foothold.isWall()) {
                    walkableFootholds.add(foothold);
                }
            }
            Set<Integer> collidableFromBelowIds = classifyCollidableFromBelowFootholds(footholdsById);
            for (Foothold foothold2 : footholds) {
                if (Foothold.isCollidableWall(foothold2, footholdsById)) {
                    collidableWallIds.add(Integer.valueOf(foothold2.getId()));
                }
            }
            buildProfile.collectFootholdsNs = System.nanoTime() - phaseStartedAt;
            buildProfile.footholdCount = footholds.size();
            buildProfile.walkableFootholdCount = walkableFootholds.size();
            buildProfile.ropeCount = map.getRopes().size();
            COLLIDABLE_WALL_IDS_BY_MAP_ID.put(Integer.valueOf(map.getId()), new HashSet(collidableWallIds));
            COLLIDABLE_FROM_BELOW_IDS_BY_MAP_ID.put(Integer.valueOf(map.getId()), new HashSet(collidableFromBelowIds));
            List<BotNavigationGraph.Region> regions = new ArrayList<>();
            Map<Integer, BotNavigationGraph.Region> regionsById = new HashMap<>();
            Map<Integer, Integer> regionIdByFootholdId = new HashMap<>();
            long phaseStartedAt2 = System.nanoTime();
            buildRegions(walkableFootholds, footholdsById, collidableFromBelowIds, regions, regionsById, regionIdByFootholdId);
            buildProfile.buildRegionsNs = System.nanoTime() - phaseStartedAt2;
            long phaseStartedAt3 = System.nanoTime();
            int nextRegionId = regions.stream().mapToInt(r -> {
                return r.id;
            }).max().orElse(0) + 1;
            for (Rope rope : map.getRopes()) {
                int i = nextRegionId;
                nextRegionId++;
                BotNavigationGraph.Region ropeRegion = new BotNavigationGraph.Region(i, rope.x(), rope.topY(), rope.bottomY(), rope.isLadder());
                regions.add(ropeRegion);
                regionsById.put(Integer.valueOf(ropeRegion.id), ropeRegion);
            }
            buildProfile.addRopeRegionsNs = System.nanoTime() - phaseStartedAt3;
            buildProfile.regionCount = regions.size();
            long phaseStartedAt4 = System.nanoTime();
            Map<Integer, List<Integer>> featureXsByRegionId = buildFeatureXsByRegionId(map, regions, regionIdByFootholdId);
            buildProfile.buildFeatureXsNs = System.nanoTime() - phaseStartedAt4;
            long phaseStartedAt5 = System.nanoTime();
            Map<Integer, List<Point>> anchorsByRegionId = buildAnchorsByRegionId(map, regions, featureXsByRegionId, movementProfile2);
            buildProfile.buildAnchorPointsNs = System.nanoTime() - phaseStartedAt5;
            List<BotNavigationGraph.Region> groundRegions = new ArrayList<>();
            List<BotNavigationGraph.Region> ropeRegions = new ArrayList<>();
            for (BotNavigationGraph.Region region : regions) {
                if (region.isRopeRegion) {
                    ropeRegions.add(region);
                } else {
                    groundRegions.add(region);
                }
            }
            Map<Integer, Rope> ropeByRegionId = buildRopeByRegionId(map, ropeRegions);
            Map<Integer, List<BotNavigationGraph.Edge>> outgoing = new HashMap<>();
            Set<String> edgeKeys = new HashSet<>();
            JumpLandingCache jumpLandingCache = new JumpLandingCache();
            RopeGrabCache ropeGrabCache = new RopeGrabCache();
            BotPhysicsEngine.setBuildWalkRegionLookup(map, regionsById, regionIdByFootholdId, footholdsById);
            long phaseStartedAt6 = System.nanoTime();
            Iterator<Foothold> it = walkableFootholds.iterator();
            while (it.hasNext()) {
                addWalkEdges(it.next(), footholdsById, regionsById, regionIdByFootholdId, outgoing, edgeKeys, movementProfile2);
            }
            buildProfile.buildWalkEdgesNs = System.nanoTime() - phaseStartedAt6;
            long phaseStartedAt7 = System.nanoTime();
            for (BotNavigationGraph.Region region2 : groundRegions) {
                addDropEdges(region2, map, regionsById, regionIdByFootholdId, anchorsByRegionId.getOrDefault(Integer.valueOf(region2.id), List.of()), outgoing, edgeKeys, movementProfile2);
            }
            buildProfile.buildDropEdgesNs = System.nanoTime() - phaseStartedAt7;
            long phaseStartedAt8 = System.nanoTime();
            for (BotNavigationGraph.Region region3 : groundRegions) {
                addJumpEdges(region3, map, regionsById, regionIdByFootholdId, anchorsByRegionId.getOrDefault(Integer.valueOf(region3.id), List.of()), outgoing, edgeKeys, jumpLandingCache, movementProfile2);
            }
            buildProfile.buildJumpEdgesNs = System.nanoTime() - phaseStartedAt8;
            long phaseStartedAt9 = System.nanoTime();
            for (BotNavigationGraph.Region region4 : ropeRegions) {
                addRopeEntryEdges(region4, groundRegions, ropeByRegionId, map, anchorsByRegionId, outgoing, edgeKeys, ropeGrabCache, movementProfile2);
            }
            buildProfile.buildRopeEntryEdgesNs = System.nanoTime() - phaseStartedAt9;
            long phaseStartedAt10 = System.nanoTime();
            for (BotNavigationGraph.Region region5 : ropeRegions) {
                addRopeExitEdges(region5, ropeRegions, ropeByRegionId, map, regionsById, regionIdByFootholdId, outgoing, edgeKeys, movementProfile2);
            }
            buildProfile.buildRopeExitEdgesNs = System.nanoTime() - phaseStartedAt10;
            long phaseStartedAt11 = System.nanoTime();
            for (Portal portal : map.getPortals()) {
                addPortalEdges(portal, map, regionsById, regionIdByFootholdId, outgoing, edgeKeys);
            }
            buildProfile.buildPortalEdgesNs = System.nanoTime() - phaseStartedAt11;
            BotNavigationGraph graph = new BotNavigationGraph(map.getId(), GRAPH_VERSION, movementProfile2, regions, regionsById, regionIdByFootholdId, outgoing, collidableWallIds, collidableFromBelowIds);
            GraphBuildReport report = buildProfile.finish();
            LAST_BUILD_REPORTS.put(GraphCacheKey.from(map.getId(), movementProfile2), report);
            DebugUtilities.debugprint(new Object[]{"Built bot nav graph map {} speed={} jump={} in {} ms (regions={}, edges={}, drop={} ms, jump={} ms, jumpSamples={}, cacheHits={})", Integer.valueOf(map.getId()), Integer.valueOf(movementProfile2.totalSpeedStat()), Integer.valueOf(movementProfile2.totalJumpStat()), String.format("%.2f", Double.valueOf(report.totalBuildNs / 1000000.0d)), Integer.valueOf(report.regionCount), Integer.valueOf(report.totalEdgeCount), String.format("%.2f", Double.valueOf(report.buildDropEdgesNs / 1000000.0d)), String.format("%.2f", Double.valueOf(report.buildJumpEdgesNs / 1000000.0d)), Long.valueOf(report.jumpSampleCount), Long.valueOf(report.jumpCacheHitCount)});
            BotPhysicsEngine.clearBuildWalkRegionLookup();
            ACTIVE_BUILD_PROFILE.remove();
            return graph;
        } catch (Throwable th) {
            BotPhysicsEngine.clearBuildWalkRegionLookup();
            ACTIVE_BUILD_PROFILE.remove();
            throw th;
        }
    }

    static GraphBuildReport getLastBuildReport(int mapId) {
        return getLastBuildReport(mapId, BotMovementProfile.base());
    }

    static GraphBuildReport getLastBuildReport(int mapId, BotMovementProfile movementProfile) {
        return LAST_BUILD_REPORTS.get(GraphCacheKey.from(mapId, movementProfile));
    }

    static Set<Integer> getCachedCollidableWallIds(int mapId) {
        return COLLIDABLE_WALL_IDS_BY_MAP_ID.get(Integer.valueOf(mapId));
    }

    static Set<Integer> getCachedCollidableFromBelowIds(int mapId) {
        return COLLIDABLE_FROM_BELOW_IDS_BY_MAP_ID.get(Integer.valueOf(mapId));
    }

    static Set<Integer> computeCollidableFromBelowIds(MapleMap map) {
        if (map == null || map.getFootholds() == null) {
            return Set.of();
        }
        Set<Integer> cached = COLLIDABLE_FROM_BELOW_IDS_BY_MAP_ID.get(Integer.valueOf(map.getId()));
        if (cached != null) {
            return cached;
        }
        Map<Integer, Foothold> footholdsById = new HashMap<>();
        for (Foothold foothold : map.getFootholds().getAllFootholds()) {
            footholdsById.put(Integer.valueOf(foothold.getId()), foothold);
        }
        Set<Integer> computed = classifyCollidableFromBelowFootholds(footholdsById);
        COLLIDABLE_FROM_BELOW_IDS_BY_MAP_ID.put(Integer.valueOf(map.getId()), new HashSet(computed));
        return computed;
    }

    private static void seedCachedFootholdCollisionIds(BotNavigationGraph graph) {
        COLLIDABLE_WALL_IDS_BY_MAP_ID.put(Integer.valueOf(graph.mapId), new HashSet(graph.collidableWallIds));
        COLLIDABLE_FROM_BELOW_IDS_BY_MAP_ID.put(Integer.valueOf(graph.mapId), new HashSet(graph.collidableFromBelowIds));
    }

    static Set<Integer> classifyCollidableFromBelowFootholds(Map<Integer, Foothold> footholdsById) {
        List<ClassifiedLoop> loops = classifyClosedLoops(buildClosedLoops(footholdsById));
        if (loops.isEmpty()) {
            return Set.of();
        }
        Set<Integer> result = new HashSet<>();
        for (ClassifiedLoop classifiedLoop : loops) {
            if (classifiedLoop.solid()) {
                ClosedLoop loop = classifiedLoop.loop();
                for (int footholdId : loop.footholdIds()) {
                    Foothold foothold = footholdsById.get(Integer.valueOf(footholdId));
                    if (foothold != null && !foothold.isWall() && foothold.getY1() == foothold.getY2()) {
                        double midX = (foothold.getX1() + foothold.getX2()) / 2.0d;
                        double y = foothold.getY1();
                        boolean insideAbove = isPointInLoop(loop, midX, y - 1.0d);
                        boolean insideBelow = isPointInLoop(loop, midX, y + 1.0d);
                        if (insideAbove && !insideBelow) {
                            result.add(Integer.valueOf(foothold.getId()));
                        }
                    }
                }
            }
        }
        return result;
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$ClosedLoop.class */
    private static final class ClosedLoop {
        private final int[] footholdIds;
        private final double[] xs;
        private final double[] ys;
        private final double minX;
        private final double maxX;
        private final double minY;
        private final double maxY;

        private ClosedLoop(int[] footholdIds, double[] xs, double[] ys, double minX, double maxX, double minY, double maxY) {
            this.footholdIds = footholdIds;
            this.xs = xs;
            this.ys = ys;
            this.minX = minX;
            this.maxX = maxX;
            this.minY = minY;
            this.maxY = maxY;
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

        public int[] footholdIds() {
            return this.footholdIds;
        }

        public double[] xs() {
            return this.xs;
        }

        public double[] ys() {
            return this.ys;
        }

        public double minX() {
            return this.minX;
        }

        public double maxX() {
            return this.maxX;
        }

        public double minY() {
            return this.minY;
        }

        public double maxY() {
            return this.maxY;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$ClassifiedLoop.class */
    private static final class ClassifiedLoop {
        private final ClosedLoop loop;
        private final int depth;
        private final boolean solid;

        private ClassifiedLoop(ClosedLoop loop, int depth, boolean solid) {
            this.loop = loop;
            this.depth = depth;
            this.solid = solid;
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

        public ClosedLoop loop() {
            return this.loop;
        }

        public int depth() {
            return this.depth;
        }

        public boolean solid() {
            return this.solid;
        }
    }

    private static List<ClosedLoop> buildClosedLoops(Map<Integer, Foothold> footholdsById) {
        List<ClosedLoop> loops = new ArrayList<>();
        Set<Integer> visited = new HashSet<>();
        for (Foothold start : footholdsById.values()) {
            if (!visited.contains(Integer.valueOf(start.getId()))) {
                List<Foothold> chain = new ArrayList<>();
                Set<Integer> seenInChain = new HashSet<>();
                Foothold current = start;
                boolean closed = false;
                while (true) {
                    if (current == null || !seenInChain.add(Integer.valueOf(current.getId())) || chain.size() > footholdsById.size()) {
                        break;
                    }
                    chain.add(current);
                    Foothold next = footholdsById.get(Integer.valueOf(current.getNext()));
                    if (next != null && next.getId() == start.getId()) {
                        closed = true;
                        break;
                    }
                    current = next;
                }
                if (closed && chain.size() >= JUMP_POST_LANDING_STABILITY_TICKS && isEndpointConnectedLoop(chain)) {
                    visited.addAll(seenInChain);
                    loops.add(toClosedLoop(chain));
                }
            }
        }
        return loops;
    }

    private static boolean isEndpointConnectedLoop(List<Foothold> chain) {
        for (int i = 0; i < chain.size(); i++) {
            Foothold current = chain.get(i);
            Foothold next = chain.get((i + 1) % chain.size());
            if (current.getX2() != next.getX1() || current.getY2() != next.getY1()) {
                return false;
            }
        }
        return true;
    }

    private static ClosedLoop toClosedLoop(List<Foothold> chain) {
        int size = chain.size();
        int[] footholdIds = new int[size];
        double[] xs = new double[size];
        double[] ys = new double[size];
        double minX = Double.POSITIVE_INFINITY;
        double maxX = Double.NEGATIVE_INFINITY;
        double minY = Double.POSITIVE_INFINITY;
        double maxY = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < size; i++) {
            Foothold foothold = chain.get(i);
            footholdIds[i] = foothold.getId();
            xs[i] = foothold.getX1();
            ys[i] = foothold.getY1();
            minX = Math.min(minX, Math.min(foothold.getX1(), foothold.getX2()));
            maxX = Math.max(maxX, Math.max(foothold.getX1(), foothold.getX2()));
            minY = Math.min(minY, Math.min(foothold.getY1(), foothold.getY2()));
            maxY = Math.max(maxY, Math.max(foothold.getY1(), foothold.getY2()));
        }
        return new ClosedLoop(footholdIds, xs, ys, minX, maxX, minY, maxY);
    }

    private static List<ClassifiedLoop> classifyClosedLoops(List<ClosedLoop> loops) {
        boolean z;
        List<ClosedLoop> ordered = new ArrayList<>(loops);
        ordered.sort(Comparator.comparingDouble(BotNavigationGraphProvider::loopBoundingArea).reversed());
        List<ClassifiedLoop> classified = new ArrayList<>(ordered.size());
        for (ClosedLoop loop : ordered) {
            ClassifiedLoop parent = null;
            double parentArea = Double.POSITIVE_INFINITY;
            for (ClassifiedLoop candidate : classified) {
                if (loopContainsLoop(candidate.loop(), loop)) {
                    double area = loopBoundingArea(candidate.loop());
                    if (area < parentArea) {
                        parent = candidate;
                        parentArea = area;
                    }
                }
            }
            int depth = parent == null ? 0 : parent.depth() + 1;
            if (parent == null || isThinNestedShell(parent.loop(), loop)) {
                z = parent == null || parent.solid();
            } else {
                z = !parent.solid();
            }
            boolean solid = z;
            ClassifiedLoop classifiedLoop = new ClassifiedLoop(loop, depth, solid);
            classified.add(classifiedLoop);
        }
        return classified;
    }

    private static double loopBoundingArea(ClosedLoop loop) {
        return (loop.maxX() - loop.minX()) * (loop.maxY() - loop.minY());
    }

    private static boolean loopContainsLoop(ClosedLoop outer, ClosedLoop inner) {
        if (outer.minX() > inner.minX() || outer.maxX() < inner.maxX() || outer.minY() > inner.minY() || outer.maxY() < inner.maxY()) {
            return false;
        }
        return isPointInLoop(outer, inner.xs()[0], inner.ys()[0]);
    }

    private static boolean isThinNestedShell(ClosedLoop outer, ClosedLoop inner) {
        return inner.minX() - outer.minX() <= 8.0d && outer.maxX() - inner.maxX() <= 8.0d && inner.minY() - outer.minY() <= 8.0d && outer.maxY() - inner.maxY() <= 8.0d;
    }

    private static boolean isPointInLoop(ClosedLoop loop, double x, double y) {
        boolean inside = false;
        double[] xs = loop.xs();
        double[] ys = loop.ys();
        int i = 0;
        int length = xs.length - 1;
        while (true) {
            int j = length;
            if (i < xs.length) {
                boolean intersects = ((ys[i] > y ? 1 : (ys[i] == y ? 0 : -1)) > 0) != ((ys[j] > y ? 1 : (ys[j] == y ? 0 : -1)) > 0) && x < (((xs[j] - xs[i]) * (y - ys[i])) / ((ys[j] - ys[i]) + 0.0d)) + xs[i];
                if (intersects) {
                    inside = !inside;
                }
                length = i;
                i++;
            } else {
                return inside;
            }
        }
    }

    private static void buildRegions(List<Foothold> footholds, Map<Integer, Foothold> footholdsById, Set<Integer> collidableFromBelowIds, List<BotNavigationGraph.Region> regions, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId) {
        UnionFind unionFind = new UnionFind();
        Iterator<Foothold> it = footholds.iterator();
        while (it.hasNext()) {
            unionFind.add(it.next().getId());
        }
        for (Foothold foothold : footholds) {
            unionWalkableFootholds(unionFind, foothold, footholdsById.get(Integer.valueOf(foothold.getPrev())));
            unionWalkableFootholds(unionFind, foothold, footholdsById.get(Integer.valueOf(foothold.getNext())));
        }
        Map<Integer, List<Foothold>> groupedFootholds = new HashMap<>();
        for (Foothold foothold2 : footholds) {
            groupedFootholds.computeIfAbsent(Integer.valueOf(unionFind.find(foothold2.getId())), ignored -> {
                return new ArrayList();
            }).add(foothold2);
        }
        List<List<Foothold>> groups = new ArrayList<>(groupedFootholds.values());
        groups.sort(Comparator.comparingInt(BotNavigationGraphProvider::groupMinY).thenComparingInt(BotNavigationGraphProvider::groupMinX));
        int nextRegionId = 1;
        for (List<Foothold> group : groups) {
            group.sort(Comparator.comparingInt(BotNavigationGraphProvider::footholdMinX).thenComparingInt(foothold3 -> {
                return Math.min(foothold3.getY1(), foothold3.getY2());
            }).thenComparingInt((v0) -> {
                return v0.getId();
            }));
            List<BotNavigationGraph.Segment> segments = new ArrayList<>(group.size());
            for (Foothold foothold4 : group) {
                segments.add(new BotNavigationGraph.Segment(foothold4, collidableFromBelowIds.contains(Integer.valueOf(foothold4.getId()))));
            }
            int i = nextRegionId;
            nextRegionId++;
            BotNavigationGraph.Region region = new BotNavigationGraph.Region(i, segments);
            regions.add(region);
            regionsById.put(Integer.valueOf(region.id), region);
            Iterator<Foothold> it2 = group.iterator();
            while (it2.hasNext()) {
                regionIdByFootholdId.put(Integer.valueOf(it2.next().getId()), Integer.valueOf(region.id));
            }
        }
    }

    private static void unionWalkableFootholds(UnionFind unionFind, Foothold first, Foothold second) {
        if (!BotPhysicsEngine.canWalkAcrossFootholds(first, second)) {
            return;
        }
        unionFind.union(first.getId(), second.getId());
    }

    private static void addWalkEdges(Foothold foothold, Map<Integer, Foothold> footholdsById, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys, BotMovementProfile movementProfile) {
        addWalkEdge(foothold, footholdsById.get(Integer.valueOf(foothold.getPrev())), regionsById, regionIdByFootholdId, outgoing, edgeKeys, movementProfile);
        addWalkEdge(foothold, footholdsById.get(Integer.valueOf(foothold.getNext())), regionsById, regionIdByFootholdId, outgoing, edgeKeys, movementProfile);
    }

    private static void addWalkEdge(Foothold fromFoothold, Foothold targetFoothold, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys, BotMovementProfile movementProfile) {
        EndpointConnection connection;
        if (fromFoothold == null || targetFoothold == null || targetFoothold.isWall()) {
            return;
        }
        int fromRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(fromFoothold.getId()), -1).intValue();
        int toRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(targetFoothold.getId()), -1).intValue();
        if (fromRegionId < 0 || toRegionId < 0 || fromRegionId == toRegionId || (connection = closestEndpointConnection(fromFoothold, targetFoothold)) == null || !isWalkConnection(connection)) {
            return;
        }
        BotNavigationGraph.Region from = regionsById.get(Integer.valueOf(fromRegionId));
        BotNavigationGraph.Region to = regionsById.get(Integer.valueOf(toRegionId));
        if (from == null || to == null) {
            return;
        }
        Point start = from.pointAt(connection.from.x);
        Point end = to.pointAt(connection.to.x);
        int cost = estimateWalkCost(start, end, movementProfile);
        addEdge(from.id, to.id, BotNavigationGraph.EdgeType.WALK, start, end, 0, 0, cost, outgoing, edgeKeys);
        addEdge(to.id, from.id, BotNavigationGraph.EdgeType.WALK, end, start, 0, 0, cost, outgoing, edgeKeys);
    }

    private static void addDropEdges(BotNavigationGraph.Region from, MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, List<Point> anchors, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys, BotMovementProfile movementProfile) {
        JumpLaunchWindow launchWindow;
        addDirectionalDropEdge(from, map, regionsById, regionIdByFootholdId, -1, outgoing, edgeKeys, movementProfile);
        addDirectionalDropEdge(from, map, regionsById, regionIdByFootholdId, 1, outgoing, edgeKeys, movementProfile);
        for (Point anchor : anchors) {
            if (dropLaunchStep(from, map, anchor, movementProfile) == 0 && (launchWindow = expandDownJumpLaunchWindow(from, map, regionIdByFootholdId, anchor.x, movementProfile)) != null) {
                int toRegionId = findRegionIdBelow(map, regionIdByFootholdId, launchWindow.endPoint());
                BotNavigationGraph.Region below = regionsById.get(Integer.valueOf(toRegionId));
                if (below != null && below.id != from.id) {
                    addEdge(from.id, below.id, BotNavigationGraph.EdgeType.DROP, launchWindow.startPoint(), launchWindow.endPoint(), launchWindow.minX(), launchWindow.maxX(), 0, 0, launchWindow.landingTimeMs() + DOWN_JUMP_COST_PENALTY_MS, outgoing, edgeKeys);
                }
            }
        }
    }

    private static void addDirectionalDropEdge(BotNavigationGraph.Region from, MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, int direction, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys, BotMovementProfile movementProfile) {
        int launchX;
        int stepX;
        BotPhysicsEngine.JumpLanding landing;
        if (direction == 0) {
            return;
        }
        Point endpoint = direction < 0 ? from.leftPoint() : from.rightPoint();
        if (from.isForbidFallDownAt(endpoint.x)) {
            return;
        }
        int runwayPx = BotPhysicsEngine.launchRunwayPx(map, movementProfile);
        if (direction < 0) {
            launchX = Math.min(from.maxX, endpoint.x + runwayPx);
        } else {
            launchX = Math.max(from.minX, endpoint.x - runwayPx);
        }
        int actualRunway = Math.abs(launchX - endpoint.x);
        if (actualRunway < Math.min(runwayPx, 20)) {
            return;
        }
        Point startPoint = from.pointAt(launchX);
        if (BotPhysicsEngine.isGroundRunwayBlockedByWall(map, startPoint, endpoint) || (landing = BotPhysicsEngine.simulateFallLanding(map, endpoint, (stepX = BotPhysicsEngine.walkStep(map, movementProfile) * direction))) == null) {
            return;
        }
        int toRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(landing.foothold().getId()), -1).intValue();
        BotNavigationGraph.Region below = regionsById.get(Integer.valueOf(toRegionId));
        if (below == null || below.id == from.id || landing.point().y <= endpoint.y + 4 || landing.point().y - endpoint.y > MAX_DROP_PX) {
            return;
        }
        int travelMs = BotPhysicsEngine.estimateFallLandingTimeMs(map, endpoint, stepX) + estimateHorizontalTravelTimeMs(actualRunway, movementProfile);
        addEdge(from.id, below.id, BotNavigationGraph.EdgeType.DROP, startPoint, landing.point(), stepX, 0, travelMs, outgoing, edgeKeys);
    }

    private static void addJumpEdges(BotNavigationGraph.Region from, MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, List<Point> anchors, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys, JumpLandingCache jumpLandingCache, BotMovementProfile movementProfile) {
        JumpLaunchWindow launchWindow;
        long startedAt = System.nanoTime();
        int jumpStep = BotPhysicsEngine.walkStep(map, movementProfile);
        JumpBuildStats stats = new JumpBuildStats();
        for (Point anchor : anchors) {
            for (int launchStepX : new int[]{-jumpStep, 0, jumpStep}) {
                BotPhysicsEngine.PostLandingJump simulatedLanding = simulateJumpLandingCached(map, anchor, launchStepX, jumpLandingCache, stats, movementProfile);
                if (simulatedLanding != null && !simulatedLanding.lostGround()) {
                    BotPhysicsEngine.JumpLanding landing = simulatedLanding.landing();
                    int toRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(simulatedLanding.finalFoothold().getId()), -1).intValue();
                    BotNavigationGraph.Region to = regionsById.get(Integer.valueOf(toRegionId));
                    if (to != null && to.id != from.id && ((Math.abs(landing.point().x - anchor.x) >= 6 || Math.abs(landing.point().y - anchor.y) >= 6) && (launchWindow = expandJumpLaunchWindow(from, map, regionIdByFootholdId, anchor.x, launchStepX, to.id, stats, jumpLandingCache, movementProfile)) != null)) {
                        addEdge(from.id, to.id, BotNavigationGraph.EdgeType.JUMP, launchWindow.startPoint(), launchWindow.endPoint(), launchWindow.minX(), launchWindow.maxX(), launchStepX, 0, launchWindow.landingTimeMs(), outgoing, edgeKeys);
                        stats.edgeCount++;
                    }
                }
            }
        }
        BuildProfileBuilder profile = ACTIVE_BUILD_PROFILE.get();
        if (profile != null) {
            profile.recordJumpRegion(new JumpRegionProfile(from.id, from.width(), stats.sampleCount, stats.edgeCount, stats.cacheHits, stats.cacheMisses, System.nanoTime() - startedAt));
        }
    }

    private static BotPhysicsEngine.PostLandingJump simulateJumpLandingCached(MapleMap map, Point start, int launchStepX, JumpLandingCache jumpLandingCache, JumpBuildStats stats, BotMovementProfile movementProfile) {
        JumpLandingKey key = new JumpLandingKey(start.x, start.y, launchStepX);
        BotPhysicsEngine.PostLandingJump cachedLanding = jumpLandingCache.hits.get(key);
        if (cachedLanding != null) {
            recordJumpSample(stats, true);
            return cachedLanding;
        }
        if (jumpLandingCache.misses.contains(key)) {
            recordJumpSample(stats, true);
            return null;
        }
        BotPhysicsEngine.PostLandingJump landing = BotPhysicsEngine.simulateJumpLandingWithPostLandingTicks(map, start, launchStepX, movementProfile, JUMP_POST_LANDING_STABILITY_TICKS);
        if (landing == null) {
            jumpLandingCache.misses.add(key);
        } else {
            jumpLandingCache.hits.put(key, landing);
        }
        recordJumpSample(stats, false);
        return landing;
    }

    private static Point simulateGroundJumpRopeGrabCached(MapleMap map, Point start, int launchStepX, Rope rope, RopeGrabCache ropeGrabCache, JumpBuildStats stats, BotMovementProfile movementProfile) {
        RopeGrabKey key = new RopeGrabKey(start.x, start.y, launchStepX, rope.x(), rope.topY(), rope.bottomY());
        Point cachedGrab = ropeGrabCache.hits.get(key);
        if (cachedGrab != null) {
            recordJumpSample(stats, true);
            return new Point(cachedGrab);
        }
        if (ropeGrabCache.misses.contains(key)) {
            recordJumpSample(stats, true);
            return null;
        }
        Point grab = BotPhysicsEngine.simulateGroundJumpRopeGrab(map, start, launchStepX, rope, movementProfile);
        if (grab == null) {
            ropeGrabCache.misses.add(key);
        } else {
            ropeGrabCache.hits.put(key, new Point(grab));
        }
        recordJumpSample(stats, false);
        return grab;
    }

    private static void recordJumpSample(JumpBuildStats stats, boolean cacheHit) {
        BuildProfileBuilder profile = ACTIVE_BUILD_PROFILE.get();
        if (profile != null) {
            profile.recordJumpSample(cacheHit);
        }
        stats.sampleCount++;
        if (cacheHit) {
            stats.cacheHits++;
        } else {
            stats.cacheMisses++;
        }
    }

    private static Map<Integer, List<Point>> buildAnchorsByRegionId(MapleMap map, List<BotNavigationGraph.Region> regions, Map<Integer, List<Integer>> featureXsByRegionId, BotMovementProfile movementProfile) {
        Map<Integer, List<Point>> anchorsByRegionId = new HashMap<>();
        for (BotNavigationGraph.Region region : regions) {
            if (!region.isRopeRegion) {
                anchorsByRegionId.put(Integer.valueOf(region.id), anchorPoints(map, region, featureXsByRegionId.getOrDefault(Integer.valueOf(region.id), List.of()), movementProfile));
            }
        }
        return anchorsByRegionId;
    }

    private static JumpLaunchWindow expandJumpLaunchWindow(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int anchorX, int launchStepX, int targetRegionId, JumpBuildStats stats, JumpLandingCache jumpLandingCache, BotMovementProfile movementProfile) {
        if (!isValidJumpLaunchX(from, map, regionIdByFootholdId, anchorX, launchStepX, targetRegionId, stats, jumpLandingCache, movementProfile)) {
            return null;
        }
        int minX = findJumpBoundary(from, map, regionIdByFootholdId, anchorX, launchStepX, targetRegionId, true, stats, jumpLandingCache, movementProfile);
        int maxX = findJumpBoundary(from, map, regionIdByFootholdId, anchorX, launchStepX, targetRegionId, false, stats, jumpLandingCache, movementProfile);
        int representativeX = (minX + maxX) / 2;
        Point representativeStart = from.pointAt(representativeX);
        BotPhysicsEngine.PostLandingJump representativeSimulation = simulateJumpLandingCached(map, representativeStart, launchStepX, jumpLandingCache, stats, movementProfile);
        if (representativeSimulation == null || representativeSimulation.lostGround()) {
            return null;
        }
        int landingRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(representativeSimulation.finalFoothold().getId()), -1).intValue();
        if (landingRegionId != targetRegionId) {
            return null;
        }
        return new JumpLaunchWindow(minX, maxX, representativeStart, representativeSimulation.landing().point(), representativeSimulation.landing().timeMs());
    }

    private static JumpLaunchWindow expandDownJumpLaunchWindow(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int anchorX, BotMovementProfile movementProfile) {
        int targetRegionId;
        BotPhysicsEngine.JumpLanding anchorLanding = validateDownJumpLaunchX(from, map, regionIdByFootholdId, anchorX, movementProfile);
        if (anchorLanding == null || (targetRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(anchorLanding.foothold().getId()), -1).intValue()) < 0) {
            return null;
        }
        int minX = findDownJumpBoundary(from, map, regionIdByFootholdId, anchorX, targetRegionId, true, movementProfile);
        int maxX = findDownJumpBoundary(from, map, regionIdByFootholdId, anchorX, targetRegionId, false, movementProfile);
        int representativeX = (minX + maxX) / 2;
        Point representativeStart = from.pointAt(representativeX);
        BotPhysicsEngine.JumpLanding representativeLanding = validateDownJumpLaunchX(from, map, regionIdByFootholdId, representativeX, movementProfile, targetRegionId);
        if (representativeLanding == null) {
            return null;
        }
        return new JumpLaunchWindow(minX, maxX, representativeStart, representativeLanding.point(), representativeLanding.timeMs());
    }

    private static int findJumpBoundary(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int startX, int launchStepX, int targetRegionId, boolean searchLeft, JumpBuildStats stats, JumpLandingCache jumpLandingCache, BotMovementProfile movementProfile) {
        int iMin;
        int limitX = searchLeft ? from.minX : from.maxX;
        int validX = startX;
        int invalidX = startX;
        int i = 1;
        while (true) {
            int step = i;
            if (searchLeft) {
                iMin = Math.max(limitX, startX - step);
            } else {
                iMin = Math.min(limitX, startX + step);
            }
            int probeX = iMin;
            if (probeX == validX) {
                break;
            }
            if (!isValidJumpLaunchX(from, map, regionIdByFootholdId, probeX, launchStepX, targetRegionId, stats, jumpLandingCache, movementProfile)) {
                invalidX = probeX;
                break;
            }
            validX = probeX;
            if (probeX == limitX) {
                return probeX;
            }
            i = step * 2;
        }
        while (Math.abs(validX - invalidX) > 1) {
            int probeX2 = (validX + invalidX) / 2;
            if (isValidJumpLaunchX(from, map, regionIdByFootholdId, probeX2, launchStepX, targetRegionId, stats, jumpLandingCache, movementProfile)) {
                validX = probeX2;
            } else {
                invalidX = probeX2;
            }
        }
        return validX;
    }

    private static int findDownJumpBoundary(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int startX, int targetRegionId, boolean searchLeft, BotMovementProfile movementProfile) {
        int iMin;
        int limitX = searchLeft ? from.minX : from.maxX;
        int validX = startX;
        int invalidX = startX;
        int i = 1;
        while (true) {
            int step = i;
            if (searchLeft) {
                iMin = Math.max(limitX, startX - step);
            } else {
                iMin = Math.min(limitX, startX + step);
            }
            int probeX = iMin;
            if (probeX == validX) {
                break;
            }
            if (!isValidDownJumpLaunchX(from, map, regionIdByFootholdId, probeX, movementProfile, targetRegionId)) {
                invalidX = probeX;
                break;
            }
            validX = probeX;
            if (probeX == limitX) {
                return probeX;
            }
            i = step * 2;
        }
        while (Math.abs(validX - invalidX) > 1) {
            int probeX2 = (validX + invalidX) / 2;
            if (isValidDownJumpLaunchX(from, map, regionIdByFootholdId, probeX2, movementProfile, targetRegionId)) {
                validX = probeX2;
            } else {
                invalidX = probeX2;
            }
        }
        return validX;
    }

    private static boolean isValidJumpLaunchX(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int launchX, int launchStepX, int targetRegionId, JumpBuildStats stats, JumpLandingCache jumpLandingCache, BotMovementProfile movementProfile) {
        BotPhysicsEngine.PostLandingJump landing;
        return isApproachableJumpLaunchX(from, map, launchX) && (landing = simulateJumpLandingCached(map, from.pointAt(launchX), launchStepX, jumpLandingCache, stats, movementProfile)) != null && !landing.lostGround() && regionIdByFootholdId.getOrDefault(Integer.valueOf(landing.finalFoothold().getId()), -1).intValue() == targetRegionId;
    }

    private static BotPhysicsEngine.JumpLanding validateDownJumpLaunchX(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int launchX, BotMovementProfile movementProfile) {
        return validateDownJumpLaunchX(from, map, regionIdByFootholdId, launchX, movementProfile, Integer.MIN_VALUE);
    }

    private static boolean isValidDownJumpLaunchX(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int launchX, BotMovementProfile movementProfile, int targetRegionId) {
        return validateDownJumpLaunchX(from, map, regionIdByFootholdId, launchX, movementProfile, targetRegionId) != null;
    }

    private static BotPhysicsEngine.JumpLanding validateDownJumpLaunchX(BotNavigationGraph.Region from, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, int launchX, BotMovementProfile movementProfile, int requiredTargetRegionId) {
        BotPhysicsEngine.JumpLanding landing;
        int landingRegionId;
        if (from == null || from.isRopeRegion || map == null) {
            return null;
        }
        Point launchPoint = from.pointAt(launchX);
        if (isBlockedWallBoundaryLaunch(map, launchPoint) || !BotPhysicsEngine.canStartDownJump(map, launchPoint) || from.isForbidFallDownAt(launchX) || dropLaunchStep(from, map, launchPoint, movementProfile) != 0 || (landing = BotPhysicsEngine.simulateDownJumpLanding(map, launchPoint)) == null || landing.point().y <= launchPoint.y + 4 || landing.point().y - launchPoint.y > 200 || (landingRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(landing.foothold().getId()), -1).intValue()) < 0 || landingRegionId == from.id) {
            return null;
        }
        if (requiredTargetRegionId != Integer.MIN_VALUE && landingRegionId != requiredTargetRegionId) {
            return null;
        }
        return landing;
    }

    private static boolean isApproachableJumpLaunchX(BotNavigationGraph.Region from, MapleMap map, int launchX) {
        if (from == null || from.isRopeRegion || map == null) {
            return false;
        }
        Point launchPoint = from.pointAt(launchX);
        if (isBlockedWallBoundaryLaunch(map, launchPoint)) {
            return false;
        }
        if (launchX <= from.minX || !canWalkToLaunchX(from, map, launchX - 1, launchX)) {
            return launchX < from.maxX && canWalkToLaunchX(from, map, launchX + 1, launchX);
        }
        return true;
    }

    private static JumpLaunchWindow expandRopeGrabLaunchWindow(BotNavigationGraph.Region from, MapleMap map, int anchorX, int launchStepX, Rope rope, JumpBuildStats stats, RopeGrabCache ropeGrabCache, BotMovementProfile movementProfile) {
        if (!isValidRopeGrabLaunchX(from, map, anchorX, launchStepX, rope, stats, ropeGrabCache, movementProfile)) {
            return null;
        }
        int minX = findRopeGrabBoundary(from, map, anchorX, launchStepX, rope, true, stats, ropeGrabCache, movementProfile);
        int maxX = findRopeGrabBoundary(from, map, anchorX, launchStepX, rope, false, stats, ropeGrabCache, movementProfile);
        int representativeX = (minX + maxX) / 2;
        Point representativeStart = from.pointAt(representativeX);
        Point representativeGrab = simulateGroundJumpRopeGrabCached(map, representativeStart, launchStepX, rope, ropeGrabCache, stats, movementProfile);
        if (representativeGrab == null) {
            return null;
        }
        int travelMs = BotPhysicsEngine.estimateGroundJumpRopeGrabTimeMs(map, representativeStart, launchStepX, rope, movementProfile);
        return new JumpLaunchWindow(minX, maxX, representativeStart, representativeGrab, travelMs);
    }

    private static int findRopeGrabBoundary(BotNavigationGraph.Region from, MapleMap map, int startX, int launchStepX, Rope rope, boolean searchLeft, JumpBuildStats stats, RopeGrabCache ropeGrabCache, BotMovementProfile movementProfile) {
        int iMin;
        int limitX = searchLeft ? from.minX : from.maxX;
        int validX = startX;
        int invalidX = startX;
        int i = 1;
        while (true) {
            int step = i;
            if (searchLeft) {
                iMin = Math.max(limitX, startX - step);
            } else {
                iMin = Math.min(limitX, startX + step);
            }
            int probeX = iMin;
            if (probeX == validX) {
                break;
            }
            if (!isValidRopeGrabLaunchX(from, map, probeX, launchStepX, rope, stats, ropeGrabCache, movementProfile)) {
                invalidX = probeX;
                break;
            }
            validX = probeX;
            if (probeX == limitX) {
                return probeX;
            }
            i = step * 2;
        }
        while (Math.abs(validX - invalidX) > 1) {
            int probeX2 = (validX + invalidX) / 2;
            if (isValidRopeGrabLaunchX(from, map, probeX2, launchStepX, rope, stats, ropeGrabCache, movementProfile)) {
                validX = probeX2;
            } else {
                invalidX = probeX2;
            }
        }
        return validX;
    }

    private static boolean isValidRopeGrabLaunchX(BotNavigationGraph.Region from, MapleMap map, int launchX, int launchStepX, Rope rope, JumpBuildStats stats, RopeGrabCache ropeGrabCache, BotMovementProfile movementProfile) {
        if (!isApproachableJumpLaunchX(from, map, launchX)) {
            return false;
        }
        Point grab = simulateGroundJumpRopeGrabCached(map, from.pointAt(launchX), launchStepX, rope, ropeGrabCache, stats, movementProfile);
        return grab != null;
    }

    private static boolean isBlockedWallBoundaryLaunch(MapleMap map, Point launchPoint) {
        Set<Integer> collidableWallIds;
        if (map == null || map.getFootholds() == null || launchPoint == null || (collidableWallIds = getCachedCollidableWallIds(map.getId())) == null || collidableWallIds.isEmpty()) {
            return false;
        }
        for (Foothold foothold : map.getFootholds().getAllFootholds()) {
            if (foothold.isWall() && collidableWallIds.contains(Integer.valueOf(foothold.getId())) && foothold.getX1() == launchPoint.x) {
                int minY = Math.min(foothold.getY1(), foothold.getY2());
                int maxY = Math.max(foothold.getY1(), foothold.getY2());
                if (launchPoint.y > minY && launchPoint.y <= maxY) {
                    return true;
                }
            }
        }
        return false;
    }

    private static boolean canWalkToLaunchX(BotNavigationGraph.Region from, MapleMap map, int fromX, int launchX) {
        Point fromPoint = from.pointAt(fromX);
        Point launchPoint = from.pointAt(launchX);
        if (fromPoint == null || launchPoint == null || fromPoint.equals(launchPoint)) {
            return false;
        }
        return BotPhysicsEngine.canWalkGroundStep(map, fromPoint, launchPoint.x - fromPoint.x);
    }

    private static void addRopeEntryEdges(BotNavigationGraph.Region ropeRegion, List<BotNavigationGraph.Region> groundRegions, Map<Integer, Rope> ropeByRegionId, MapleMap map, Map<Integer, List<Point>> anchorsByRegionId, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys, RopeGrabCache ropeGrabCache, BotMovementProfile movementProfile) {
        Point ropeGrab;
        Rope rope = ropeByRegionId.get(Integer.valueOf(ropeRegion.id));
        if (rope == null) {
            return;
        }
        int ropeX = rope.x();
        int walkStep = BotMovementManager.walkStep(map, movementProfile);
        JumpBuildStats stats = new JumpBuildStats();
        for (BotNavigationGraph.Region ground : groundRegions) {
            for (Point anchor : anchorsByRegionId.getOrDefault(Integer.valueOf(ground.id), List.of())) {
                int firstClimbableY = BotPhysicsEngine.firstClimbableY(rope);
                boolean canGrab = Math.abs(anchor.x - ropeX) <= BotMovementManager.cfg.ROPE_GRAB_X && anchor.y >= firstClimbableY && anchor.y <= rope.bottomY();
                boolean canTopGrab = Math.abs(anchor.x - ropeX) <= BotMovementManager.cfg.ROPE_GRAB_X && anchor.y < rope.topY() && rope.topY() - anchor.y <= BotPhysicsEngine.cfg.MAX_SNAP_DROP;
                boolean canJumpGrab = BotMovementManager.canReachRopeFromGround(map, anchor, rope, movementProfile);
                boolean canTopStep = anchor.y <= rope.topY() + BotMovementManager.cfg.JUMP_Y_THRESH && Math.abs(anchor.x - ropeX) <= BotMovementManager.cfg.ROPE_GRAB_X;
                if (canGrab) {
                    Point ropePoint = new Point(ropeX, Math.max(firstClimbableY, Math.min(anchor.y, rope.bottomY())));
                    addEdge(ground.id, ropeRegion.id, BotNavigationGraph.EdgeType.CLIMB, anchor, ropePoint, 0, 0, BotPhysicsEngine.cfg.TICK_MS, outgoing, edgeKeys);
                } else if (canTopGrab) {
                    addEdge(ground.id, ropeRegion.id, BotNavigationGraph.EdgeType.CLIMB, anchor, new Point(ropeX, firstClimbableY), 0, 0, BotPhysicsEngine.cfg.TICK_MS, outgoing, edgeKeys);
                } else {
                    if (canTopStep && (ropeGrab = BotPhysicsEngine.simulateDownJumpRopeGrab(map, anchor, rope)) != null) {
                        int cost = BotPhysicsEngine.estimateDownJumpRopeGrabTimeMs(map, anchor, rope);
                        addEdge(ground.id, ropeRegion.id, BotNavigationGraph.EdgeType.CLIMB, anchor, ropeGrab, 0, 0, cost, outgoing, edgeKeys);
                    }
                    if (canJumpGrab) {
                        for (int jumpStep : new int[]{-walkStep, 0, walkStep}) {
                            JumpLaunchWindow launchWindow = expandRopeGrabLaunchWindow(ground, map, anchor.x, jumpStep, rope, stats, ropeGrabCache, movementProfile);
                            if (launchWindow != null) {
                                addEdge(ground.id, ropeRegion.id, BotNavigationGraph.EdgeType.CLIMB, launchWindow.startPoint(), launchWindow.endPoint(), launchWindow.minX(), launchWindow.maxX(), jumpStep, 0, launchWindow.landingTimeMs(), outgoing, edgeKeys);
                            }
                        }
                    }
                }
            }
        }
    }

    private static void addRopeExitEdges(BotNavigationGraph.Region ropeRegion, List<BotNavigationGraph.Region> ropeRegions, Map<Integer, Rope> ropeByRegionId, MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys, BotMovementProfile movementProfile) {
        Rope targetRope;
        Rope rope = ropeByRegionId.get(Integer.valueOf(ropeRegion.id));
        if (rope == null) {
            return;
        }
        int ropeX = rope.x();
        int jumpStep = BotMovementManager.walkStep(map, movementProfile);
        int maxRopeJumpDx = BotPhysicsEngine.maxRopeGrabSimulationHorizontalTravel(map, movementProfile);
        addTopStepOffEdge(ropeRegion, rope, map, regionsById, regionIdByFootholdId, outgoing, edgeKeys);
        Iterator<Integer> it = ropeAnchorYs(rope).iterator();
        while (it.hasNext()) {
            int anchorY = it.next().intValue();
            Point ropePoint = new Point(ropeX, anchorY);
            for (int stepX : new int[]{-jumpStep, 0, jumpStep}) {
                BotMovementManager.JumpLanding landing = BotMovementManager.simulateRopeJumpLanding(map, ropePoint, stepX, movementProfile);
                if (landing != null) {
                    int toRegionId = regionIdByFootholdId.getOrDefault(Integer.valueOf(landing.foothold().getId()), -1).intValue();
                    BotNavigationGraph.Region toRegion = regionsById.get(Integer.valueOf(toRegionId));
                    if (toRegion != null && !toRegion.isRopeRegion) {
                        int cost = BotPhysicsEngine.estimateRopeJumpLandingTimeMs(map, ropePoint, stepX, movementProfile);
                        addEdge(ropeRegion.id, toRegion.id, BotNavigationGraph.EdgeType.CLIMB, ropePoint, landing.point(), stepX, 0, cost, outgoing, edgeKeys);
                    }
                }
            }
        }
        Iterator<Integer> it2 = ropeTransferAnchorYs(rope).iterator();
        while (it2.hasNext()) {
            int anchorY2 = it2.next().intValue();
            Point ropePoint2 = new Point(ropeX, anchorY2);
            for (BotNavigationGraph.Region otherRope : ropeRegions) {
                if (otherRope.id != ropeRegion.id && (targetRope = ropeByRegionId.get(Integer.valueOf(otherRope.id))) != null) {
                    int dx = Math.abs(ropeX - targetRope.x());
                    if (dx <= maxRopeJumpDx) {
                        int launchDir = targetRope.x() > ropeX ? jumpStep : -jumpStep;
                        Point ropeGrab = BotPhysicsEngine.simulateRopeJumpGrab(map, ropePoint2, launchDir, targetRope, movementProfile);
                        if (ropeGrab != null) {
                            int cost2 = BotPhysicsEngine.estimateRopeJumpGrabTimeMs(map, ropePoint2, launchDir, targetRope, movementProfile);
                            addEdge(ropeRegion.id, otherRope.id, BotNavigationGraph.EdgeType.CLIMB, ropePoint2, ropeGrab, launchDir, 0, cost2, outgoing, edgeKeys);
                        }
                    }
                }
            }
        }
    }

    private static void addTopStepOffEdge(BotNavigationGraph.Region ropeRegion, Rope rope, MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys) {
        Foothold foothold;
        BotNavigationGraph.Region ground;
        Point landPoint = BotPhysicsEngine.findTopExitLanding(map, rope);
        if (landPoint == null || (foothold = BotPhysicsEngine.findGroundFoothold(map, landPoint)) == null || (ground = regionsById.get(regionIdByFootholdId.getOrDefault(Integer.valueOf(foothold.getId()), -1))) == null || ground.isRopeRegion) {
            return;
        }
        Point ropePoint = new Point(rope.x(), rope.topY());
        addEdge(ropeRegion.id, ground.id, BotNavigationGraph.EdgeType.CLIMB, ropePoint, landPoint, 0, 0, BotPhysicsEngine.cfg.TICK_MS, outgoing, edgeKeys);
    }

    private static List<Integer> ropeAnchorYs(Rope rope) {
        List<Integer> ys = new ArrayList<>();
        int firstClimbableY = BotPhysicsEngine.firstClimbableY(rope);
        ys.add(Integer.valueOf(firstClimbableY));
        for (int y = rope.topY() + ROPE_ANCHOR_INTERVAL_PX; y < rope.bottomY(); y += ROPE_ANCHOR_INTERVAL_PX) {
            if (y > firstClimbableY) {
                ys.add(Integer.valueOf(y));
            }
        }
        if (((Integer) ys.getLast()).intValue() != rope.bottomY()) {
            ys.add(Integer.valueOf(rope.bottomY()));
        }
        return ys;
    }

    private static Map<Integer, Rope> buildRopeByRegionId(MapleMap map, List<BotNavigationGraph.Region> ropeRegions) {
        Map<Integer, Rope> ropeByRegionId = new HashMap<>();
        for (BotNavigationGraph.Region ropeRegion : ropeRegions) {
            Rope rope = findRopeFromRegion(map, ropeRegion);
            if (rope != null) {
                ropeByRegionId.put(Integer.valueOf(ropeRegion.id), rope);
            }
        }
        return ropeByRegionId;
    }

    private static List<Integer> ropeTransferAnchorYs(Rope rope) {
        List<Integer> ys = new ArrayList<>();
        int step = Math.max(1, BotPhysicsEngine.climbStepPerTick());
        int firstClimbableY = BotPhysicsEngine.firstClimbableY(rope);
        int i = firstClimbableY;
        while (true) {
            int y = i;
            if (y > rope.bottomY()) {
                break;
            }
            ys.add(Integer.valueOf(y));
            i = y + step;
        }
        if (ys.isEmpty() || ((Integer) ys.getLast()).intValue() != rope.bottomY()) {
            ys.add(Integer.valueOf(rope.bottomY()));
        }
        return ys;
    }

    static Rope findRopeFromRegion(MapleMap map, BotNavigationGraph.Region ropeRegion) {
        if (ropeRegion == null || !ropeRegion.isRopeRegion) {
            return null;
        }
        for (Rope rope : map.getRopes()) {
            if (rope.x() == ropeRegion.minX && rope.topY() == ropeRegion.minY && rope.bottomY() == ropeRegion.maxY) {
                return rope;
            }
        }
        return null;
    }

    private static void addPortalEdges(Portal portal, MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys) {
        Portal targetPortal;
        if (portal.getTargetMapId() != map.getId() || (targetPortal = map.getPortal(portal.getTarget())) == null || targetPortal.getId() == portal.getId()) {
            return;
        }
        int snapUp = BotPhysicsEngine.cfg.MAX_SNAP_DROP;
        BotNavigationGraph.Region from = findRegionBelow(map, regionsById, regionIdByFootholdId, new Point(portal.getPosition().x, portal.getPosition().y - snapUp));
        BotNavigationGraph.Region to = findRegionBelow(map, regionsById, regionIdByFootholdId, new Point(targetPortal.getPosition().x, targetPortal.getPosition().y - snapUp));
        if (from == null || to == null) {
            return;
        }
        Point start = from.pointAt(portal.getPosition().x);
        Point end = to.pointAt(targetPortal.getPosition().x);
        addEdge(from.id, to.id, BotNavigationGraph.EdgeType.PORTAL, start, end, 0, portal.getId(), 0, outgoing, edgeKeys);
    }

    private static Map<Integer, List<Integer>> buildFeatureXsByRegionId(MapleMap map, List<BotNavigationGraph.Region> regions, Map<Integer, Integer> regionIdByFootholdId) {
        Portal targetPortal;
        Map<Integer, Set<Integer>> featureXs = new HashMap<>();
        for (Rope rope : map.getRopes()) {
            addFeatureX(featureXs, findRegionIdBelow(map, regionIdByFootholdId, new Point(rope.x(), rope.bottomY() - 1)), rope.x());
            addFeatureX(featureXs, findRegionIdBelow(map, regionIdByFootholdId, new Point(rope.x(), rope.topY() - 1)), rope.x());
            addFeatureX(featureXs, findRegionIdBelow(map, regionIdByFootholdId, new Point(rope.x(), rope.topY() - (BotMovementManager.cfg.JUMP_Y_THRESH * 2))), rope.x());
        }
        for (Portal portal : map.getPortals()) {
            int snapUp = BotPhysicsEngine.cfg.MAX_SNAP_DROP;
            Point portalProbe = new Point(portal.getPosition().x, portal.getPosition().y - snapUp);
            addFeatureX(featureXs, findRegionIdBelow(map, regionIdByFootholdId, portalProbe), portal.getPosition().x);
            if (portal.getTargetMapId() == map.getId() && (targetPortal = map.getPortal(portal.getTarget())) != null) {
                Point targetProbe = new Point(targetPortal.getPosition().x, targetPortal.getPosition().y - snapUp);
                addFeatureX(featureXs, findRegionIdBelow(map, regionIdByFootholdId, targetProbe), targetPortal.getPosition().x);
            }
        }
        for (BotNavigationGraph.Region region : regions) {
            if (!region.isRopeRegion) {
                projectRegionXsToRegionBelow(featureXs, map, regionIdByFootholdId, region.leftPoint());
                projectRegionXsToRegionBelow(featureXs, map, regionIdByFootholdId, region.rightPoint());
                if (region.width() <= 64) {
                    projectRegionXsToRegionBelow(featureXs, map, regionIdByFootholdId, region.centerPoint());
                }
            }
        }
        Map<Integer, List<Integer>> featuresByRegionId = new HashMap<>();
        for (Map.Entry<Integer, Set<Integer>> entry : featureXs.entrySet()) {
            List<Integer> xs = new ArrayList<>(entry.getValue());
            xs.sort((v0, v1) -> {
                return v0.compareTo(v1);
            });
            featuresByRegionId.put(entry.getKey(), xs);
        }
        return featuresByRegionId;
    }

    private static void projectRegionXsToRegionBelow(Map<Integer, Set<Integer>> featureXs, MapleMap map, Map<Integer, Integer> regionIdByFootholdId, Point point) {
        if (point == null) {
            return;
        }
        addFeatureX(featureXs, findRegionIdBelow(map, regionIdByFootholdId, new Point(point.x, point.y + 1)), point.x);
    }

    private static void addFeatureX(Map<Integer, Set<Integer>> featureXs, int regionId, int x) {
        if (regionId < 0) {
            return;
        }
        featureXs.computeIfAbsent(Integer.valueOf(regionId), ignored -> {
            return new HashSet();
        }).add(Integer.valueOf(x));
    }

    private static int findRegionIdBelow(MapleMap map, Map<Integer, Integer> regionIdByFootholdId, Point point) {
        Foothold foothold;
        if (map.getFootholds() == null || (foothold = BotPhysicsEngine.findBelowIndexed(map, point)) == null) {
            return -1;
        }
        return regionIdByFootholdId.getOrDefault(Integer.valueOf(foothold.getId()), -1).intValue();
    }

    private static BotNavigationGraph.Region findRegionBelow(MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Point point) {
        int regionId = findRegionIdBelow(map, regionIdByFootholdId, point);
        if (regionId < 0) {
            return null;
        }
        return regionsById.get(Integer.valueOf(regionId));
    }

    private static List<Point> anchorPoints(MapleMap map, BotNavigationGraph.Region region, List<Integer> featureXs, BotMovementProfile movementProfile) {
        List<Point> points = new ArrayList<>();
        addAnchor(points, region.leftPoint());
        int edgeInset = Math.max(SAME_SOLID_NEST_GAP_PX, (int) Math.round((movementProfile.walkVelocityPxs() * BotPhysicsEngine.cfg.TICK_MS) / 1000.0d));
        if (region.width() > edgeInset * 2) {
            addAnchor(points, region.pointAt(region.minX + edgeInset), ENDPOINT_ANCHOR_SPACING_PX);
            addAnchor(points, region.pointAt(region.maxX - edgeInset), ENDPOINT_ANCHOR_SPACING_PX);
        }
        int ticksToApex = Math.max(1, (int) Math.ceil(BotPhysicsEngine.jumpForcePerTick(movementProfile) / Math.max(0.001f, BotPhysicsEngine.gravityPerTick())));
        int jumpInset = Math.max(edgeInset * JUMP_POST_LANDING_STABILITY_TICKS, BotPhysicsEngine.walkStep(map, movementProfile) * ticksToApex);
        if (region.width() > jumpInset * 2) {
            addAnchor(points, region.pointAt(region.minX + jumpInset), ENDPOINT_ANCHOR_SPACING_PX);
            addAnchor(points, region.pointAt(region.maxX - jumpInset), ENDPOINT_ANCHOR_SPACING_PX);
        }
        int walkStep = BotPhysicsEngine.walkStep(map, movementProfile);
        int interiorSpacing = Math.max(walkStep, 1);
        if (region.width() > edgeInset * 2) {
            int i = region.minX;
            int i2 = edgeInset;
            while (true) {
                int x = i + i2;
                if (x > region.maxX - edgeInset) {
                    break;
                }
                addAnchor(points, region.pointAt(x), 0);
                i = x;
                i2 = interiorSpacing;
            }
        }
        for (BotNavigationGraph.Segment segment : region.segments) {
            addAnchor(points, new Point(segment.x1, segment.y1), ENDPOINT_ANCHOR_SPACING_PX);
            addAnchor(points, new Point(segment.x2, segment.y2), ENDPOINT_ANCHOR_SPACING_PX);
        }
        if (region.width() >= Math.max(BotMovementManager.cfg.FOLLOW_DIST * 2, 140)) {
            addAnchor(points, region.centerPoint());
        }
        if (region.width() >= Math.max(BotMovementManager.cfg.FOLLOW_DIST * 4, 260)) {
            addAnchor(points, region.pointAt(region.minX + (region.width() / JUMP_POST_LANDING_STABILITY_TICKS)));
            addAnchor(points, region.pointAt(region.maxX - (region.width() / JUMP_POST_LANDING_STABILITY_TICKS)));
        }
        addAnchor(points, region.rightPoint());
        Iterator<Integer> it = featureXs.iterator();
        while (it.hasNext()) {
            int featureX = it.next().intValue();
            if (featureX >= region.minX && featureX <= region.maxX) {
                addAnchor(points, region.pointAt(featureX));
            }
        }
        points.sort(Comparator.comparingInt((Point point) -> point.x).thenComparingInt((Point point2) -> point2.y));
        return points;
    }

    private static void addAnchor(List<Point> points, Point point) {
        addAnchor(points, point, 0);
    }

    private static void addAnchor(List<Point> points, Point point, int minSpacingPx) {
        for (Point existing : points) {
            if (existing.equals(point)) {
                return;
            }
            if (minSpacingPx > 0 && Math.abs(existing.x - point.x) <= minSpacingPx && Math.abs(existing.y - point.y) <= SAME_SOLID_NEST_GAP_PX) {
                return;
            }
        }
        points.add(point);
    }

    private static boolean isWalkConnection(EndpointConnection connection) {
        int dx = Math.abs(connection.to.x - connection.from.x);
        int dy = connection.to.y - connection.from.y;
        return BotPhysicsEngine.isWalkableEndpointStep(dx, dy);
    }

    private static void addEdge(int fromRegionId, int toRegionId, BotNavigationGraph.EdgeType type, Point startPoint, Point endPoint, int launchMinX, int launchMaxX, int launchStepX, int portalId, int cost, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys) {
        addEdge(fromRegionId, toRegionId, type, startPoint, endPoint, launchMinX, launchMaxX, launchStepX, portalId, 0, 0, 0, cost, outgoing, edgeKeys);
    }

    private static void addEdge(int fromRegionId, int toRegionId, BotNavigationGraph.EdgeType type, Point startPoint, Point endPoint, int launchStepX, int portalId, int cost, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys) {
        addEdge(fromRegionId, toRegionId, type, startPoint, endPoint, startPoint.x, startPoint.x, launchStepX, portalId, 0, 0, 0, cost, outgoing, edgeKeys);
    }

    private static void addEdge(int fromRegionId, int toRegionId, BotNavigationGraph.EdgeType type, Point startPoint, Point endPoint, int launchMinX, int launchMaxX, int launchStepX, int portalId, int ropeX, int ropeTopY, int ropeBottomY, int cost, Map<Integer, List<BotNavigationGraph.Edge>> outgoing, Set<String> edgeKeys) {
        String key = fromRegionId + ":" + toRegionId + ":" + String.valueOf(type) + ":" + startPoint.x + ":" + startPoint.y + ":" + endPoint.x + ":" + endPoint.y + ":" + launchStepX + ":" + portalId + ":" + ropeX + ":" + ropeTopY + ":" + ropeBottomY + ":" + launchMinX + ":" + launchMaxX;
        if (!edgeKeys.add(key)) {
            return;
        }
        outgoing.computeIfAbsent(Integer.valueOf(fromRegionId), ignored -> {
            return new ArrayList();
        }).add(new BotNavigationGraph.Edge(fromRegionId, toRegionId, type, startPoint, endPoint, launchMinX, launchMaxX, launchStepX, portalId, ropeX, ropeTopY, ropeBottomY, cost));
        BuildProfileBuilder profile = ACTIVE_BUILD_PROFILE.get();
        if (profile != null) {
            profile.recordEdge(type);
        }
    }

    private static EndpointConnection closestEndpointConnection(Foothold first, Foothold second) {
        Point[] firstEndpoints = {new Point(first.getX1(), first.getY1()), new Point(first.getX2(), first.getY2())};
        Point[] secondEndpoints = {new Point(second.getX1(), second.getY1()), new Point(second.getX2(), second.getY2())};
        EndpointConnection best = null;
        int bestDistance = Integer.MAX_VALUE;
        for (Point from : firstEndpoints) {
            for (Point to : secondEndpoints) {
                int distance = Math.abs(to.x - from.x) + Math.abs(to.y - from.y);
                if (distance < bestDistance) {
                    best = new EndpointConnection(from, to);
                    bestDistance = distance;
                }
            }
        }
        return best;
    }

    private static EndpointConnection sharedEndpointConnection(Foothold first, Foothold second) {
        Point[] firstEndpoints = {new Point(first.getX1(), first.getY1()), new Point(first.getX2(), first.getY2())};
        Point[] secondEndpoints = {new Point(second.getX1(), second.getY1()), new Point(second.getX2(), second.getY2())};
        for (Point from : firstEndpoints) {
            for (Point to : secondEndpoints) {
                if (from.equals(to)) {
                    return new EndpointConnection(from, to);
                }
            }
        }
        return null;
    }

    private static int footholdMinX(Foothold foothold) {
        return Math.min(foothold.getX1(), foothold.getX2());
    }

    private static int groupMinX(List<Foothold> footholds) {
        int minX = Integer.MAX_VALUE;
        for (Foothold foothold : footholds) {
            minX = Math.min(minX, footholdMinX(foothold));
        }
        return minX;
    }

    private static int groupMinY(List<Foothold> footholds) {
        int minY = Integer.MAX_VALUE;
        for (Foothold foothold : footholds) {
            minY = Math.min(minY, Math.min(foothold.getY1(), foothold.getY2()));
        }
        return minY;
    }

    private static int estimateWalkCost(Point start, Point end) {
        return estimateWalkCost(start, end, BotMovementProfile.base());
    }

    private static int estimateWalkCost(Point start, Point end, BotMovementProfile movementProfile) {
        return estimateHorizontalTravelTimeMs(Math.abs(end.x - start.x), movementProfile);
    }

    private static int estimateHorizontalTravelTimeMs(int dx, BotMovementProfile movementProfile) {
        return Math.max(0, (int) Math.round((dx * 1000.0d) / Math.max(1.0d, movementProfile.walkVelocityPxs())));
    }

    private static int dropLaunchStep(BotNavigationGraph.Region region, MapleMap map, Point anchor, BotMovementProfile movementProfile) {
        Point left = region.leftPoint();
        if (Math.abs(anchor.x - left.x) <= ENDPOINT_ANCHOR_SPACING_PX && Math.abs(anchor.y - left.y) <= 12) {
            return -BotMovementManager.walkStep(map, movementProfile);
        }
        Point right = region.rightPoint();
        if (Math.abs(anchor.x - right.x) <= ENDPOINT_ANCHOR_SPACING_PX && Math.abs(anchor.y - right.y) <= 12) {
            return BotMovementManager.walkStep(map, movementProfile);
        }
        return 0;
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$EndpointConnection.class */
    private static final class EndpointConnection {
        private final Point from;
        private final Point to;

        private EndpointConnection(Point from, Point to) {
            this.from = from;
            this.to = to;
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

        public Point from() {
            return this.from;
        }

        public Point to() {
            return this.to;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraphProvider$UnionFind.class */
    private static final class UnionFind {
        private final Map<Integer, Integer> parent = new HashMap();
        private final Map<Integer, Integer> rank = new HashMap();

        private UnionFind() {
        }

        void add(int value) {
            this.parent.putIfAbsent(Integer.valueOf(value), Integer.valueOf(value));
            this.rank.putIfAbsent(Integer.valueOf(value), 0);
        }

        int find(int value) {
            Integer parentValue = this.parent.get(Integer.valueOf(value));
            if (parentValue == null) {
                add(value);
                return value;
            }
            if (parentValue.intValue() == value) {
                return value;
            }
            int root = find(parentValue.intValue());
            this.parent.put(Integer.valueOf(value), Integer.valueOf(root));
            return root;
        }

        void union(int first, int second) {
            int firstRoot = find(first);
            int secondRoot = find(second);
            if (firstRoot == secondRoot) {
                return;
            }
            int firstRank = this.rank.getOrDefault(Integer.valueOf(firstRoot), 0).intValue();
            int secondRank = this.rank.getOrDefault(Integer.valueOf(secondRoot), 0).intValue();
            if (firstRank < secondRank) {
                this.parent.put(Integer.valueOf(firstRoot), Integer.valueOf(secondRoot));
            } else if (firstRank > secondRank) {
                this.parent.put(Integer.valueOf(secondRoot), Integer.valueOf(firstRoot));
            } else {
                this.parent.put(Integer.valueOf(secondRoot), Integer.valueOf(firstRoot));
                this.rank.put(Integer.valueOf(firstRoot), Integer.valueOf(firstRank + 1));
            }
        }
    }
}
