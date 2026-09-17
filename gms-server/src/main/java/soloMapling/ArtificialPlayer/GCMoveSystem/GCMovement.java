package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Deque;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Rope;
import soloMapling.ArtificialPlayer.BotAttackSystem.BotAttackData;
import soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands;
import soloMapling.ArtificialPlayer.BotTravelSystem.BotScriptedWarp;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationGraph;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCMovement.class */
public final class GCMovement {
    private static final Map<Integer, BotMovementState> STATES = new ConcurrentHashMap();
    private static final Map<Integer, Runnable> ARRIVAL_CALLBACKS = new ConcurrentHashMap();
    private static final int ROPECHECK_MAX_LINES = 40;

    private GCMovement() {
    }

    public static void enable(Character bot) {
        if (bot == null) {
            return;
        }
        ObserverTracker.ensureStarted();
        STATES.computeIfAbsent(Integer.valueOf(bot.getId()), id -> {
            BotMovementState st = new BotMovementState(bot, null);
            st.movementProfile = BotMovementProfile.fromCharacter(bot);
            if (bot.getMap() != null) {
                st.lastMapId = bot.getMapId();
                st.fhIndex = BotMovementManager.buildFhIndex(bot.getMap());
                Point cur = bot.getPosition();
                Point ground = BotPhysicsEngine.findGroundPoint(bot.getMap(), new Point(cur.x, cur.y - 1));
                BotPhysicsEngine.teleportTo(st, bot, ground != null ? ground : cur);
                BotMovementManager.resetEntryStateAfterTeleport(st);
                if (ObserverTracker.isActiveMap(bot.getMapId())) {
                    BotNavigationGraphProvider.warmGraphAsync(bot.getMap(), st.movementProfile);
                }
            }
            GCMovementDriver.start(st);
            MovementCommands.tryAcquireMovementLock(bot);
            return st;
        });
    }

    public static void disable(Character bot) {
        if (bot == null) {
            return;
        }
        GCFollow.cancel(bot);
        GCTravel.cancel(bot);
        GCFidget.cancel(bot);
        BotMovementState st = STATES.remove(Integer.valueOf(bot.getId()));
        if (st != null) {
            GCMovementDriver.stop(st);
            MovementCommands.releaseMovementLock(bot);
        }
        ARRIVAL_CALLBACKS.remove(Integer.valueOf(bot.getId()));
    }

    public static boolean isEnabled(Character bot) {
        return bot != null && STATES.containsKey(Integer.valueOf(bot.getId()));
    }

    static Collection<BotMovementState> enabledStates() {
        return new ArrayList(STATES.values());
    }

    public static void move(Character bot, int x, int y) {
        move(bot, x, y, null);
    }

    public static void move(Character bot, int x, int y, Runnable onArrival) {
        if (bot == null) {
            return;
        }
        enable(bot);
        BotMovementState st = STATES.get(Integer.valueOf(bot.getId()));
        if (st == null) {
            return;
        }
        st.following = false;
        st.farmAnchor = null;
        st.farmAnchorMapId = -1;
        st.moveTarget = new Point(x, y);
        st.moveTargetPrecise = true;
        st.moveTargetSource = "gcmove";
        st.moveBestDist = Integer.MAX_VALUE;
        st.moveProgressAtMs = System.currentTimeMillis();
        if (onArrival != null) {
            ARRIVAL_CALLBACKS.put(Integer.valueOf(bot.getId()), onArrival);
        } else {
            ARRIVAL_CALLBACKS.remove(Integer.valueOf(bot.getId()));
        }
    }

    public static void farmHere(Character bot, int x, int y) {
        if (bot == null) {
            return;
        }
        enable(bot);
        BotMovementState st = STATES.get(Integer.valueOf(bot.getId()));
        if (st == null) {
            return;
        }
        st.following = false;
        st.farmAnchor = new Point(x, y);
        st.farmAnchorMapId = bot.getMapId();
        st.moveTarget = new Point(x, y);
        st.moveTargetPrecise = true;
        st.moveBestDist = Integer.MAX_VALUE;
        st.moveProgressAtMs = System.currentTimeMillis();
    }

    public static void follow(Character bot, Character target) {
        if (bot == null || target == null) {
            return;
        }
        enable(bot);
        GCFollow.start(bot, target);
    }

    public static boolean isFollowing(Character bot) {
        return GCFollow.isFollowing(bot);
    }

    public static void stop(Character bot) {
        if (bot == null) {
            return;
        }
        GCFollow.cancel(bot);
        GCTravel.cancel(bot);
        clearMoveIntent(bot);
        BotMovementState st = STATES.get(Integer.valueOf(bot.getId()));
        if (st != null) {
            st.following = false;
            st.owner = null;
        }
    }

    public static void teleportTo(Character bot, int x, int y) {
        if (bot == null) {
            return;
        }
        enable(bot);
        BotMovementState st = STATES.get(Integer.valueOf(bot.getId()));
        if (st == null) {
            return;
        }
        Point ground = BotPhysicsEngine.findGroundPoint(bot.getMap(), new Point(x, y));
        BotPhysicsEngine.teleportTo(st, bot, ground != null ? ground : new Point(x, y));
        BotMovementManager.resetEntryStateAfterTeleport(st);
        BotMovementManager.broadcastMovement(st);
    }

    public static void markAlerted(Character bot) {
        BotMovementState st;
        if (bot != null && (st = STATES.get(Integer.valueOf(bot.getId()))) != null) {
            BotContactDamage.markAlerted(st);
        }
    }

    public static boolean teleport(Character bot, int targetX, int targetY) {
        BotMovementState st;
        return (bot == null || (st = STATES.get(Integer.valueOf(bot.getId()))) == null || !GCMovementSkills.execTeleport(st, bot, targetX, targetY)) ? false : true;
    }

    public static boolean flashJump(Character bot, int targetX, float scaleCap) {
        BotMovementState st;
        return (bot == null || (st = STATES.get(Integer.valueOf(bot.getId()))) == null || !GCMovementSkills.execFlashJump(st, bot, targetX, scaleCap)) ? false : true;
    }

    public static boolean debugFlashJump(Character bot, int dir, float scale) {
        BotMovementState st;
        return (bot == null || (st = STATES.get(Integer.valueOf(bot.getId()))) == null || !GCMovementSkills.execFlashJumpForced(st, bot, dir, scale)) ? false : true;
    }

    public static Boolean isFacingLeft(Character bot) {
        BotMovementState st;
        if (bot == null || (st = STATES.get(Integer.valueOf(bot.getId()))) == null) {
            return null;
        }
        return Boolean.valueOf(st.facingDir < 0);
    }

    static void clearMoveIntent(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st == null) {
            return;
        }
        st.moveTarget = null;
        st.moveTargetPrecise = false;
        st.farmAnchor = null;
        st.farmAnchorMapId = -1;
        BotMovementManager.clearNavigationState(st);
        ARRIVAL_CALLBACKS.remove(Integer.valueOf(bot.getId()));
    }

    static void armSameMapFollow(Character bot, Character target) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st == null || target == null) {
            return;
        }
        st.owner = target;
        st.followTargetId = target.getId();
        st.following = true;
        st.moveTarget = null;
        st.farmAnchor = null;
        st.farmAnchorMapId = -1;
    }

    static void pauseFollowForTravel(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null) {
            st.following = false;
        }
    }

    static void endFollowState(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null) {
            st.following = false;
            st.owner = null;
        }
    }

    public static void travel(Character bot, int destMapId) {
        GCTravel.travel(bot, destMapId, null);
    }

    public static void travel(Character bot, int destMapId, Consumer<Boolean> onDone) {
        GCTravel.travel(bot, destMapId, onDone);
    }

    public static boolean isTraveling(Character bot) {
        return GCTravel.isTraveling(bot);
    }

    public static void cancelTravel(Character bot) {
        GCTravel.cancel(bot);
    }

    public static void travelTo(Character bot, int mapId, int x, int y) {
        travelTo(bot, mapId, x, y, null);
    }

    public static void travelTo(Character bot, int mapId, int x, int y, Consumer<Boolean> onDone) {
        if (bot == null) {
            return;
        }
        Runnable arrive = onDone == null ? null : () -> {
            onDone.accept(true);
        };
        if (bot.getMap() != null && bot.getMapId() == mapId) {
            move(bot, x, y, arrive);
        } else {
            GCTravel.travel(bot, mapId, ok -> {
                if (ok.booleanValue()) {
                    move(bot, x, y, arrive);
                } else if (onDone != null) {
                    onDone.accept(false);
                }
            });
        }
    }

    public static String routeReport(Character bot, int destMapId) {
        if (bot == null || bot.getMap() == null) {
            return "GCTravel: no map.";
        }
        int from = bot.getMapId();
        long startedAt = System.nanoTime();
        List<Integer> route = GCWorldGraph.route(from, destMapId, 12);
        long ms = (System.nanoTime() - startedAt) / 1000000;
        if (route == null) {
            return String.format("GCTravel route %d -> %d: NONE (warp; %d maps indexed, %dms)", Integer.valueOf(from), Integer.valueOf(destMapId), Integer.valueOf(GCWorldGraph.mapCount()), Long.valueOf(ms));
        }
        if (route.isEmpty()) {
            return "GCTravel: already on map " + destMapId;
        }
        return String.format("GCTravel route %d -> %d: %d hops %s (%dms)", Integer.valueOf(from), Integer.valueOf(destMapId), Integer.valueOf(route.size()), route, Long.valueOf(ms));
    }

    public static boolean isMoving(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        return st != null && (st.moveTarget != null || st.following || st.inAir || st.climbing || st.navEdge != null || st.portalDropAtMs > 0);
    }

    public static boolean isClimbing(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        return st != null && st.climbing;
    }

    public static void setGrinding(Character bot, boolean grinding) {
        if (bot == null) {
            return;
        }
        if (grinding) {
            enable(bot);
        }
        BotMovementState st = STATES.get(Integer.valueOf(bot.getId()));
        if (st != null) {
            st.grinding = grinding;
        }
    }

    public static void setRestHold(Character bot, boolean resting) {
        if (bot == null) {
            return;
        }
        if (resting) {
            enable(bot);
        }
        BotMovementState st = STATES.get(Integer.valueOf(bot.getId()));
        if (st != null) {
            st.resting = resting;
        }
    }

    public static boolean isResting(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        return st != null && st.resting;
    }

    public static void dismountRope(Character bot, int dx) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null && st.climbing) {
            BotMovementManager.jumpOffRope(st, bot, dx);
        }
    }

    public static boolean isNavigatingClimb(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        return (st == null || !st.climbing || st.navEdge == null) ? false : true;
    }

    public static void jumpInPlace(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null && !st.inAir && !st.climbing) {
            BotMovementManager.initiateJump(st, bot, 0);
        }
    }

    public static void jumpToward(Character bot, int dx) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null && !st.inAir && !st.climbing) {
            BotMovementManager.initiateJump(st, bot, dx);
        }
    }

    public static void turnAround(Character bot) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null) {
            st.facingDir = -st.facingDir;
        }
    }

    public static void face(Character bot, boolean left) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null) {
            st.facingDir = left ? -1 : 1;
            BotMovementManager.broadcastMovement(st);
        }
    }

    public static void duck(Character bot, int durationMs) {
        BotMovementState st = bot == null ? null : STATES.get(Integer.valueOf(bot.getId()));
        if (st != null && !st.inAir && !st.climbing) {
            st.duckUntilMs = System.currentTimeMillis() + Math.max(1, durationMs);
        }
    }

    public static void nudgeTo(Character bot, int x, int y) {
        move(bot, x, y);
    }

    public static void setFidget(Character bot, boolean on) {
        if (bot == null) {
            return;
        }
        if (on) {
            enable(bot);
            GCFidget.start(bot);
        } else {
            GCFidget.cancel(bot);
        }
    }

    public static boolean isFidgeting(Character bot) {
        return GCFidget.isActive(bot);
    }

    public static boolean isMapObserved(int mapId) {
        return ObserverTracker.isActiveMap(mapId);
    }

    public static void markObservedNow(int mapId) {
        ObserverTracker.markObservedNow(mapId);
    }

    public static String lodTier(int mapId) {
        if (ObserverTracker.isFull(mapId)) {
            return "full";
        }
        if (ObserverTracker.isHalo(mapId)) {
            return "halo";
        }
        if (ObserverTracker.isActiveMap(mapId)) {
            return "dwell";
        }
        return "coarse";
    }

    public static Set<Integer> observedFullMaps() {
        return ObserverTracker.fullMaps();
    }

    public static Set<Integer> observedHaloMaps() {
        return ObserverTracker.haloMaps();
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCMovement$Ledge.class */
    public static final class Ledge {
        private final int regionId;
        private final int minX;
        private final int maxX;
        private final int centerX;
        private final int centerY;

        public Ledge(int regionId, int minX, int maxX, int centerX, int centerY) {
            this.regionId = regionId;
            this.minX = minX;
            this.maxX = maxX;
            this.centerX = centerX;
            this.centerY = centerY;
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

        public int minX() {
            return this.minX;
        }

        public int maxX() {
            return this.maxX;
        }

        public int centerX() {
            return this.centerX;
        }

        public int centerY() {
            return this.centerY;
        }
    }

    public static List<Ledge> walkableLedges(MapleMap map) {
        BotNavigationGraph g = BotNavigationGraphProvider.getGraph(map);
        if (g == null) {
            return List.of();
        }
        List<Ledge> out = new ArrayList<>();
        for (BotNavigationGraph.Region r : g.regions) {
            if (!r.isRopeRegion && !r.isLadder) {
                Point c = r.centerPoint();
                out.add(new Ledge(r.id, r.minX, r.maxX, c.x, c.y));
            }
        }
        return out;
    }

    public static int regionIdAt(MapleMap map, int x, int y) {
        BotNavigationGraph g = BotNavigationGraphProvider.getGraph(map);
        if (g == null) {
            return -1;
        }
        return g.findRegionId(map, new Point(x, y));
    }

    public static boolean onDifferentLedge(MapleMap map, int ax, int ay, int bx, int by) {
        BotNavigationGraph g = BotNavigationGraphProvider.peekGraph(map);
        if (g == null) {
            return false;
        }
        int ra = g.findRegionId(map, new Point(ax, ay));
        int rb = g.findRegionId(map, new Point(bx, by));
        return ra >= 0 && rb >= 0 && ra != rb;
    }

    public static Set<Integer> reachableRegions(MapleMap map, int fromX, int fromY) {
        BotNavigationGraph g = BotNavigationGraphProvider.getGraph(map);
        if (g == null) {
            return Set.of();
        }
        int start = g.findRegionId(map, new Point(fromX, fromY));
        if (start < 0) {
            return Set.of();
        }
        Set<Integer> seen = new HashSet<>();
        Deque<Integer> queue = new ArrayDeque<>();
        seen.add(Integer.valueOf(start));
        queue.add(Integer.valueOf(start));
        while (!queue.isEmpty()) {
            int rid = queue.poll().intValue();
            for (BotNavigationGraph.Edge e : g.getOutgoing(rid)) {
                if (e.toRegionId != rid && seen.add(Integer.valueOf(e.toRegionId))) {
                    queue.add(Integer.valueOf(e.toRegionId));
                }
            }
        }
        return seen;
    }

    public static Point groundPointInRegion(MapleMap map, int regionId, int x) {
        BotNavigationGraph.Region r;
        BotNavigationGraph g = BotNavigationGraphProvider.getGraph(map);
        if (g == null || (r = g.getRegion(regionId)) == null) {
            return null;
        }
        return r.pointAt(x);
    }

    public static Point groundPointBelow(MapleMap map, int x, int y) {
        return BotPhysicsEngine.findGroundPoint(map, new Point(x, y));
    }

    public static List<Integer> mapsWithinHops(int fromMapId, int maxHops) {
        return new ArrayList(mapsWithinHopsByDepth(fromMapId, maxHops).keySet());
    }

    public static Map<Integer, Integer> mapsWithinHopsByDepth(int fromMapId, int maxHops) {
        LinkedHashMap<Integer, Integer> out = new LinkedHashMap<>();
        if (maxHops <= 0) {
            return out;
        }
        Map<Integer, int[]> g = GCWorldGraph.isReady() ? GCWorldGraph.get() : Map.of();
        Set<Integer> seen = new HashSet<>();
        ArrayDeque<Integer> frontier = new ArrayDeque<>();
        seen.add(Integer.valueOf(fromMapId));
        frontier.add(Integer.valueOf(fromMapId));
        int depth = 0;
        while (!frontier.isEmpty() && depth < maxHops) {
            depth++;
            for (int level = frontier.size(); level > 0; level--) {
                int current = frontier.poll().intValue();
                for (int next : g.getOrDefault(Integer.valueOf(current), new int[0])) {
                    if (seen.add(Integer.valueOf(next))) {
                        out.put(Integer.valueOf(next), Integer.valueOf(depth));
                        frontier.add(Integer.valueOf(next));
                    }
                }
                for (int next2 : BotScriptedWarp.destinations(current)) {
                    if (seen.add(Integer.valueOf(next2))) {
                        out.put(Integer.valueOf(next2), Integer.valueOf(depth));
                        frontier.add(Integer.valueOf(next2));
                    }
                }
            }
        }
        return out;
    }

    public static List<String> lodStats() {
        return LodMetrics.stats();
    }

    public static int lodLoad(int n) {
        return LodMetrics.load(n);
    }

    public static int lodUnload() {
        return LodMetrics.unload();
    }

    public static String bakeReport(Character bot) {
        if (bot == null || bot.getMap() == null) {
            return "GCMove: no map.";
        }
        BotMovementProfile profile = BotMovementProfile.fromCharacter(bot);
        long startedAt = System.nanoTime();
        BotNavigationGraph g = BotNavigationGraphProvider.rebuildGraph(bot.getMap(), profile);
        long ms = (System.nanoTime() - startedAt) / 1000000;
        if (g == null) {
            return "GCMove: bake FAILED for map " + bot.getMapId();
        }
        int regions = g.regions.size();
        int walk = 0;
        int jump = 0;
        int drop = 0;
        int climb = 0;
        int portal = 0;
        int total = 0;
        for (List<BotNavigationGraph.Edge> edges : g.outgoingByRegionId.values()) {
            for (BotNavigationGraph.Edge e : edges) {
                total++;
                switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[e.type.ordinal()]) {
                    case 1:
                        walk++;
                        break;
                    case 2:
                        jump++;
                        break;
                    case 3:
                        drop++;
                        break;
                    case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                        climb++;
                        break;
                    case 5:
                        portal++;
                        break;
                }
            }
        }
        int ropes = bot.getMap().getRopes().size();
        return String.format("GCMove bake map %d in %dms: regions=%d ropes=%d edges=%d (walk=%d jump=%d drop=%d climb=%d portal=%d)", Integer.valueOf(bot.getMapId()), Long.valueOf(ms), Integer.valueOf(regions), Integer.valueOf(ropes), Integer.valueOf(total), Integer.valueOf(walk), Integer.valueOf(jump), Integer.valueOf(drop), Integer.valueOf(climb), Integer.valueOf(portal));
    }

    /* renamed from: soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement$1, reason: invalid class name */
    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCMovement$1.class */
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
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.DROP.ordinal()] = 3;
            } catch (NoSuchFieldError e3) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.CLIMB.ordinal()] = 4;
            } catch (NoSuchFieldError e4) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.PORTAL.ordinal()] = 5;
            } catch (NoSuchFieldError e5) {
            }
        }
    }

    public static List<String> ropeCheckReport(Character player) {
        String verdict;
        List<String> out = new ArrayList<>();
        if (player == null || player.getMap() == null) {
            out.add("GCMove ropecheck: no map.");
            return out;
        }
        MapleMap map = player.getMap();
        List<Rope> ropes = map.getRopes();
        int oldStrictBand = BotPhysicsEngine.climbStepPerTick() + 2;
        out.add("=== !gcmove ropecheck map " + player.getMapId() + " (" + ropes.size() + " ropes) ===");
        out.add(String.format("tol: up=%d down=%d x=%d (old band: rope.x, topY-3..topY+%d)", 24, 20, 8, Integer.valueOf(oldStrictBand)));
        int oldPassCount = 0;
        int newPassCount = 0;
        int recovered = 0;
        int stillFail = 0;
        int shown = 0;
        for (Rope rope : ropes) {
            int topY = rope.topY();
            Point oldGround = BotPhysicsEngine.pointBelowIndexed(map, new Point(rope.x(), topY - 3));
            boolean oldPass = oldGround != null && oldGround.y <= topY + oldStrictBand;
            Point newLanding = BotPhysicsEngine.findTopExitLanding(map, rope);
            boolean newPass = newLanding != null;
            if (oldPass) {
                oldPassCount++;
            }
            if (newPass) {
                newPassCount++;
            }
            if (!oldPass && newPass) {
                recovered++;
            }
            if (!oldPass && !newPass) {
                stillFail++;
            }
            if (shown < ROPECHECK_MAX_LINES) {
                if (oldPass) {
                    verdict = "OK";
                } else if (!newPass) {
                    verdict = "STILL-FAIL (no foothold in widened band)";
                } else if (newLanding.x != rope.x()) {
                    verdict = "recovered FM-3 (off-axis dx=" + (newLanding.x - rope.x()) + ")";
                } else if (newLanding.y < topY) {
                    verdict = "recovered FM-2 (above top by " + (topY - newLanding.y) + ")";
                } else {
                    verdict = "recovered FM-1 (below top by " + (newLanding.y - topY) + ")";
                }
                Object[] objArr = new Object[7];
                objArr[0] = Integer.valueOf(rope.x());
                objArr[1] = Integer.valueOf(topY);
                objArr[2] = Integer.valueOf(rope.bottomY());
                objArr[3] = rope.isLadder() ? "ladder" : "rope";
                objArr[4] = newPass ? String.valueOf(newLanding.y) : "none";
                objArr[5] = oldPass ? "pass" : "fail";
                objArr[6] = verdict;
                out.add(String.format("  x=%d topY=%d botY=%d %s | new landY=%s | old=%s -> %s", objArr));
                shown++;
            }
        }
        if (shown < ropes.size()) {
            out.add("  ... " + (ropes.size() - shown) + " more (capped at 40)");
        }
        out.add(String.format("summary: old-pass=%d new-pass=%d recovered=%d still-fail=%d", Integer.valueOf(oldPassCount), Integer.valueOf(newPassCount), Integer.valueOf(recovered), Integer.valueOf(stillFail)));
        return out;
    }

    static void abandonMove(BotMovementState entry) {
        if (entry != null && entry.bot != null) {
            ARRIVAL_CALLBACKS.remove(Integer.valueOf(entry.bot.getId()));
        }
    }

    static void fireArrival(BotMovementState entry) {
        Runnable cb;
        if (entry != null && entry.bot != null && (cb = ARRIVAL_CALLBACKS.remove(Integer.valueOf(entry.bot.getId()))) != null) {
            try {
                cb.run();
            } catch (Throwable th) {
            }
        }
    }
}
