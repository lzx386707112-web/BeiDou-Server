package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import org.gms.client.Character;
import org.gms.constants.game.CharacterStance;
import org.gms.server.maps.Foothold;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import org.gms.server.maps.Rope;
import soloMapling.ArtificialPlayer.BotAttackSystem.BotAttackData;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationGraph;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotPhysicsEngine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager.class */
final class BotNavigationManager {
    private static final int JUMP_READY_X_TOLERANCE = 10;
    private static final int EDGE_READY_X_TOLERANCE = 14;
    private static final int NO_MOVEMENT_WALK_TOLERANCE = 4;
    private static final int BLOCKED_POS_GIVE_UP_MIN_TICKS = 6;
    private static final int BLOCKED_POS_GIVE_UP_JITTER_TICKS = 4;
    private static final int LAUNCH_WINDOW_STEER_INSET_PX = 4;
    private static final long PORTAL_USE_COOLDOWN_MS = 250;
    private static final int PORTAL_ENTER_EXTRA_TICKS_MAX = 3;
    private static final long SLOW_PATHFIND_WARN_NS = 250000000;
    private static final long SLOW_PATHFIND_WARN_COOLDOWN_MS = 10000;
    private static final long EPSILON_SALT = 15290385;
    private static final Logger log = LoggerFactory.getLogger(BotNavigationManager.class);
    private static final AtomicLong slowPathfindNextWarnAtMs = new AtomicLong();
    private static final AtomicInteger slowPathfindSuppressed = new AtomicInteger();
    private static final Map<Integer, Map<Integer, Long>> WARMUP_NOTIFIED = new ConcurrentHashMap();
    static boolean useAdmissibleHeuristic = true;
    static double JITTER_FRAC = 0.55d;
    static double EPSILON_SPAN = 0.15d;

    BotNavigationManager() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager$NavigationDirective.class */
    static final class NavigationDirective {
        final Point targetPos;
        final boolean consumedTick;

        NavigationDirective(Point targetPos, boolean consumedTick) {
            this.targetPos = targetPos;
            this.consumedTick = consumedTick;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager$SearchNode.class */
    private static final class SearchNode {
        final SearchState state;
        final int cost;
        final int score;

        SearchNode(SearchState state, int cost, int score) {
            this.state = state;
            this.cost = cost;
            this.score = score;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager$SearchState.class */
    private static final class SearchState {
        private final int regionId;
        private final Point point;
        private final boolean viaPortal;

        private SearchState(int regionId, Point point, boolean viaPortal) {
            this.regionId = regionId;
            this.point = point;
            this.viaPortal = viaPortal;
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

        public Point point() {
            return this.point;
        }

        public boolean viaPortal() {
            return this.viaPortal;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager$PathfindProfile.class */
    private static final class PathfindProfile {
        private final long elapsedNs;
        private final int expandedNodes;
        private final int staleNodes;
        private final int edgeChecks;
        private final int usableEdges;
        private final int relaxations;
        private final int openPeak;
        private final int bestGoalCost;
        private final int resultEdges;

        private PathfindProfile(long elapsedNs, int expandedNodes, int staleNodes, int edgeChecks, int usableEdges, int relaxations, int openPeak, int bestGoalCost, int resultEdges) {
            this.elapsedNs = elapsedNs;
            this.expandedNodes = expandedNodes;
            this.staleNodes = staleNodes;
            this.edgeChecks = edgeChecks;
            this.usableEdges = usableEdges;
            this.relaxations = relaxations;
            this.openPeak = openPeak;
            this.bestGoalCost = bestGoalCost;
            this.resultEdges = resultEdges;
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

        public long elapsedNs() {
            return this.elapsedNs;
        }

        public int expandedNodes() {
            return this.expandedNodes;
        }

        public int staleNodes() {
            return this.staleNodes;
        }

        public int edgeChecks() {
            return this.edgeChecks;
        }

        public int usableEdges() {
            return this.usableEdges;
        }

        public int relaxations() {
            return this.relaxations;
        }

        public int openPeak() {
            return this.openPeak;
        }

        public int bestGoalCost() {
            return this.bestGoalCost;
        }

        public int resultEdges() {
            return this.resultEdges;
        }
    }

    static NavigationDirective resolveTarget(BotMovementState entry, Point rawTargetPos, boolean runAiTick) {
        BotNavigationGraph.Edge refreshedGroundEdge;
        long startedAt = System.nanoTime();
        try {
            Character bot = entry.bot;
            if (bot.getMap().getFootholds() == null) {
                entry.graphWarmupFallback = false;
                clearNavigation(entry);
                NavigationDirective navigationDirective = new NavigationDirective(rawTargetPos, false);
                BotPerformanceMonitor.record("nav-resolve", System.nanoTime() - startedAt);
                return navigationDirective;
            }
            if (bot.getMap().isSwim()) {
                entry.graphWarmupFallback = true;
                clearNavigation(entry);
                NavigationDirective navigationDirective2 = new NavigationDirective(rawTargetPos, false);
                BotPerformanceMonitor.record("nav-resolve", System.nanoTime() - startedAt);
                return navigationDirective2;
            }
            BotNavigationGraph graph = resolveActiveGraph(bot.getMap(), entry.movementProfile);
            if (graph == null) {
                BotNavigationGraphProvider.warmGraphAsync(bot.getMap(), entry.movementProfile);
                entry.graphWarmupFallback = true;
                notifyWarmup(entry, bot);
                entry.lastNavDecision = "graph-warmup";
                clearNavigation(entry);
                Point fallbackTarget = rawTargetPos != null ? new Point(rawTargetPos) : bot.getPosition();
                NavigationDirective navigationDirective3 = new NavigationDirective(fallbackTarget, false);
                BotPerformanceMonitor.record("nav-resolve", System.nanoTime() - startedAt);
                return navigationDirective3;
            }
            if (BotNavigationGraphProvider.peekGraph(bot.getMap(), entry.movementProfile) == null) {
                BotNavigationGraphProvider.warmGraphAsync(bot.getMap(), entry.movementProfile);
                entry.lastNavDecision = "graph-fallback-profile";
            }
            entry.graphWarmupFallback = false;
            if (entry.navGraph != graph) {
                if (entry.navGraph != null) {
                    BotMovementManager.clearNavigationState(entry);
                }
                entry.navGraph = graph;
            }
            Point botPos = bot.getPosition();
            int startRegionId = resolveCurrentRegionId(graph, entry, bot.getMap(), botPos);
            int targetRegionId = resolveTargetRegionId(graph, entry, bot.getMap(), rawTargetPos);
            Point pathTargetPos = adjustPathTarget(entry, graph, targetRegionId, rawTargetPos);
            if (runAiTick && entry.navEdge != null && entry.navBlockedPosTicks > 0 && entry.navBlockedPosTicks >= entry.navBlockedPosGiveUpTicks) {
                clearNavigation(entry);
            }
            BotNavigationGraph.Edge edge = reuseCommittedEdge(graph, entry, startRegionId, targetRegionId);
            boolean edgeReused = edge != null;
            if (edgeReused) {
                BotNavigationGraph.Edge refreshedEdge = refreshPendingClimbExitEdge(graph, entry, bot, botPos, startRegionId, targetRegionId, pathTargetPos, edge, runAiTick);
                if (refreshedEdge != edge) {
                    edge = refreshedEdge;
                    edgeReused = edge != null;
                }
                if (edgeReused && (refreshedGroundEdge = refreshCommittedGroundEdge(graph, entry, bot, startRegionId, targetRegionId, pathTargetPos, edge, runAiTick)) != edge) {
                    edge = refreshedGroundEdge;
                    edgeReused = edge != null;
                }
            }
            if (edge == null && runAiTick && startRegionId >= 0 && targetRegionId >= 0) {
                edge = findNextEdge(graph, bot, startRegionId, targetRegionId, pathTargetPos);
                if (edge != null) {
                    entry.navEdge = edge;
                    entry.navTargetRegionId = targetRegionId;
                }
            }
            if (edge == null) {
                entry.lastNavDecision = !runAiTick ? "no-ai" : (startRegionId < 0 || targetRegionId < 0) ? "no-region" : startRegionId == targetRegionId ? "same-region" : "no-path";
                clearNavigation(entry);
                NavigationDirective navigationDirective4 = new NavigationDirective(rawTargetPos, false);
                BotPerformanceMonitor.record("nav-resolve", System.nanoTime() - startedAt);
                return navigationDirective4;
            }
            NavigationDirective executionDirective = tryExecuteEdge(graph, entry, bot, botPos, rawTargetPos, edge, runAiTick);
            if (executionDirective != null) {
                entry.lastNavDecision = "exec";
                entry.navBlockedPosTicks = 0;
                BotPerformanceMonitor.record("nav-resolve", System.nanoTime() - startedAt);
                return executionDirective;
            }
            entry.lastNavDecision = edgeReused ? "reuse" : "new";
            trackBlockedPositionGate(entry, botPos, edgeReused);
            entry.navPreciseTarget = shouldUsePreciseTarget(graph, entry, botPos, edge);
            entry.navTargetPos = selectWaypoint(entry, graph, botPos, edge);
            NavigationDirective navigationDirective5 = new NavigationDirective(new Point(entry.navTargetPos), false);
            BotPerformanceMonitor.record("nav-resolve", System.nanoTime() - startedAt);
            return navigationDirective5;
        } catch (Throwable th) {
            BotPerformanceMonitor.record("nav-resolve", System.nanoTime() - startedAt);
            throw th;
        }
    }

    static boolean tryExecuteCommittedEdgeAfterGroundMovement(BotMovementState entry, Point rawTargetPos) {
        if (entry == null || entry.bot == null || entry.navEdge == null || entry.inAir || entry.climbing) {
            return false;
        }
        BotNavigationGraph graph = resolveActiveGraph(entry.bot.getMap(), entry.movementProfile);
        if (graph == null) {
            BotNavigationGraphProvider.warmGraphAsync(entry.bot.getMap(), entry.movementProfile);
            return false;
        }
        Point botPos = entry.bot.getPosition();
        int startRegionId = resolveCurrentRegionId(graph, entry, entry.bot.getMap(), botPos);
        BotNavigationGraph.Edge edge = reuseCommittedEdge(graph, entry, startRegionId, entry.navTargetRegionId);
        if (edge == null) {
            BotMovementManager.clearNavigationState(entry);
            return false;
        }
        NavigationDirective directive = tryExecuteEdge(graph, entry, entry.bot, botPos, rawTargetPos, edge, true);
        if (directive == null || !directive.consumedTick) {
            return false;
        }
        entry.lastNavDecision = "exec";
        return true;
    }

    private static void clearNavigation(BotMovementState entry) {
        BotMovementManager.clearNavigationState(entry);
    }

    private static void trackBlockedPositionGate(BotMovementState entry, Point botPos, boolean edgeReused) {
        boolean blockedPos = edgeReused && entry.lastEdgeBlockReason != null && entry.lastEdgeBlockReason.endsWith("-pos");
        if (!blockedPos) {
            entry.navBlockedPosTicks = 0;
            return;
        }
        if (entry.navBlockedPosTicks == 0 || botPos.x != entry.navBlockedPosX || botPos.y != entry.navBlockedPosY) {
            entry.navBlockedPosTicks = 0;
            entry.navBlockedPosGiveUpTicks = BLOCKED_POS_GIVE_UP_MIN_TICKS + ThreadLocalRandom.current().nextInt(5);
            entry.navBlockedPosX = botPos.x;
            entry.navBlockedPosY = botPos.y;
        }
        entry.navBlockedPosTicks++;
    }

    private static void notifyWarmup(BotMovementState entry, Character bot) {
        Long last;
        Character owner = entry.owner;
        if (owner == null) {
            return;
        }
        int ownerId = owner.getId();
        int mapId = bot.getMap().getId();
        long now = System.currentTimeMillis();
        Map<Integer, Long> byMap = WARMUP_NOTIFIED.get(Integer.valueOf(ownerId));
        if (byMap == null || (last = byMap.get(Integer.valueOf(mapId))) == null || now - last.longValue() >= SLOW_PATHFIND_WARN_COOLDOWN_MS) {
            long walkable = bot.getMap().getFootholds().getAllFootholds().stream().filter(fh -> {
                return !fh.isWall();
            }).count();
            if (walkable < 100) {
                return;
            }
            WARMUP_NOTIFIED.computeIfAbsent(Integer.valueOf(ownerId), k -> {
                return new ConcurrentHashMap();
            }).put(Integer.valueOf(mapId), Long.valueOf(now));
            owner.dropMessage(5, bot.getName() + " is warming map navigation cache, using fallback movement...");
        }
    }

    private static BotNavigationGraph.Edge refreshPendingClimbExitEdge(BotNavigationGraph graph, BotMovementState entry, Character bot, Point botPos, int startRegionId, int targetRegionId, Point targetPos, BotNavigationGraph.Edge edge, boolean runAiTick) {
        if (!runAiTick || edge == null || !entry.climbing || edge.type != BotNavigationGraph.EdgeType.CLIMB || edge.launchStepX == 0 || startRegionId < 0 || targetRegionId < 0 || startRegionId == targetRegionId) {
            return edge;
        }
        if (canExecuteClimbExitFromCurrentPosition(graph, bot.getMap(), botPos, edge)) {
            return edge;
        }
        BotNavigationGraph.Edge bestEdge = findNextEdge(graph, bot, startRegionId, targetRegionId, targetPos);
        if (sameEdge(edge, bestEdge) || bestEdge == null) {
            return edge;
        }
        entry.navEdge = bestEdge;
        entry.navTargetRegionId = targetRegionId;
        entry.navTargetPos = null;
        entry.navPreciseTarget = false;
        return bestEdge;
    }

    private static BotNavigationGraph.Edge refreshCommittedGroundEdge(BotNavigationGraph graph, BotMovementState entry, Character bot, int startRegionId, int targetRegionId, Point targetPos, BotNavigationGraph.Edge edge, boolean runAiTick) {
        if (!runAiTick || edge == null || entry.inAir || entry.climbing || startRegionId < 0 || targetRegionId < 0 || startRegionId == targetRegionId) {
            return edge;
        }
        BotNavigationGraph.Edge bestEdge = findNextEdge(graph, bot, startRegionId, targetRegionId, targetPos);
        if (bestEdge == null || sameEdge(edge, bestEdge)) {
            return edge;
        }
        if (shouldRetainCommittedGroundEdge(edge, bestEdge)) {
            return edge;
        }
        entry.navEdge = bestEdge;
        entry.navTargetRegionId = targetRegionId;
        entry.navTargetPos = null;
        entry.navPreciseTarget = false;
        return bestEdge;
    }

    static BotNavigationGraph.Edge reuseCommittedEdge(BotNavigationGraph graph, BotMovementState entry, int startRegionId, int targetRegionId) {
        BotNavigationGraph.Edge edge = entry.navEdge;
        if (edge == null || targetRegionId < 0) {
            return null;
        }
        int previousTargetRegionId = entry.navTargetRegionId;
        entry.navTargetRegionId = targetRegionId;
        if (!isEdgeUsable(graph, entry.bot, edge)) {
            return null;
        }
        if (entry.climbing && isRopeEntryEdge(graph, edge)) {
            return null;
        }
        if (startRegionId == edge.toRegionId && !entry.inAir && !entry.climbing && edge.fromRegionId != edge.toRegionId) {
            return null;
        }
        if (!entry.inAir && !entry.climbing && startRegionId >= 0 && startRegionId == targetRegionId && edge.toRegionId != startRegionId && previousTargetRegionId != targetRegionId) {
            return null;
        }
        if (startRegionId == edge.fromRegionId) {
            if (!entry.inAir && !entry.climbing && previousTargetRegionId >= 0 && previousTargetRegionId != targetRegionId && edge.toRegionId != targetRegionId) {
                return null;
            }
            return edge;
        }
        if (entry.climbing && (startRegionId < 0 || startRegionId != edge.toRegionId)) {
            return edge;
        }
        if (entry.inAir && ((startRegionId < 0 || startRegionId == edge.toRegionId) && (edge.type == BotNavigationGraph.EdgeType.DROP || edge.type == BotNavigationGraph.EdgeType.JUMP))) {
            return edge;
        }
        if (entry.inAir && edge.type == BotNavigationGraph.EdgeType.CLIMB && edge.launchStepX != 0) {
            return edge;
        }
        return null;
    }

    private static NavigationDirective tryExecuteEdge(BotNavigationGraph graph, BotMovementState entry, Character bot, Point botPos, Point rawTargetPos, BotNavigationGraph.Edge edge, boolean runAiTick) {
        if (!runAiTick) {
            return null;
        }
        switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[edge.type.ordinal()]) {
            case 1:
                return tryExecuteJump(graph, entry, bot, rawTargetPos, edge);
            case 2:
                return tryExecuteDrop(graph, entry, bot, botPos, rawTargetPos, edge);
            case PORTAL_ENTER_EXTRA_TICKS_MAX /* 3 */:
                return tryExecuteClimb(graph, entry, bot, botPos, rawTargetPos, edge);
            case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                return tryExecutePortalEdge(entry, bot, botPos, rawTargetPos, edge);
            default:
                return null;
        }
    }

    /* renamed from: soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationManager$1, reason: invalid class name */
    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager$1.class */
    static /* synthetic */ class AnonymousClass1 {
        static final /* synthetic */ int[] $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType = new int[BotNavigationGraph.EdgeType.values().length];

        static {
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.JUMP.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.DROP.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.CLIMB.ordinal()] = BotNavigationManager.PORTAL_ENTER_EXTRA_TICKS_MAX;
            } catch (NoSuchFieldError e3) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.PORTAL.ordinal()] = 4;
            } catch (NoSuchFieldError e4) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[BotNavigationGraph.EdgeType.WALK.ordinal()] = 5;
            } catch (NoSuchFieldError e5) {
            }
        }
    }

    private static NavigationDirective tryExecuteJump(BotNavigationGraph graph, BotMovementState entry, Character bot, Point rawTargetPos, BotNavigationGraph.Edge edge) {
        BotNavigationGraph.Region fromRegion;
        Rope rope;
        if (entry.inAir || entry.climbing) {
            return null;
        }
        if (BotNavigationGraphProvider.peekGraph(bot.getMap(), entry.movementProfile) != graph) {
            entry.lastEdgeBlockReason = "jump-graph-warmup";
            return null;
        }
        Point botPos = bot.getPosition();
        if (!canExecuteSelectedJumpFromCurrentPosition(graph, entry, bot.getMap(), botPos, edge)) {
            if (edge.startPoint.y > botPos.y && (fromRegion = graph.getRegion(edge.fromRegionId)) != null && fromRegion.isRopeRegion && (rope = findRopeForRegion(bot.getMap(), fromRegion)) != null && canGrabRopeAtCurrentPosition(botPos, rope)) {
                startClimbing(entry, bot, rope, botPos.y);
                return new NavigationDirective(rawTargetPos, true);
            }
            entry.lastEdgeBlockReason = "jump-pos";
            return null;
        }
        if (deepenJumpLaunchOneStep(graph, entry, bot.getMap(), edge)) {
            entry.lastEdgeBlockReason = "jump-delay";
            return null;
        }
        if (edge.launchStepX == 0 && BotPhysicsEngine.slipperyGround(bot.getMap()) && BotPhysicsEngine.carriedAirVelX(bot.getMap(), entry) != 0) {
            entry.lastEdgeBlockReason = "jump-slide";
            return null;
        }
        entry.lastEdgeBlockReason = null;
        setEdgeExecutionTarget(entry, edge);
        BotMovementManager.initiateJump(entry, bot, edge.launchStepX);
        entry.navJumpLaunchEdge = null;
        entry.navJumpLaunchX = Integer.MIN_VALUE;
        entry.navJumpLaunchDelaySteps = Integer.MIN_VALUE;
        return new NavigationDirective(rawTargetPos, true);
    }

    private static boolean deepenJumpLaunchOneStep(BotNavigationGraph graph, BotMovementState entry, MapleMap map, BotNavigationGraph.Edge edge) {
        int dir;
        if (entry.navJumpLaunchX == Integer.MIN_VALUE || (dir = Integer.signum(edge.launchStepX)) == 0) {
            return false;
        }
        if (entry.navJumpLaunchDelaySteps == Integer.MIN_VALUE) {
            entry.navJumpLaunchDelaySteps = ThreadLocalRandom.current().nextInt(PORTAL_ENTER_EXTRA_TICKS_MAX);
        }
        if (entry.navJumpLaunchDelaySteps <= 0) {
            return false;
        }
        int deeperX = entry.navJumpLaunchX + (dir * BotPhysicsEngine.walkStep(map, entry.movementProfile));
        BotNavigationGraph.Region fromRegion = graph.getRegion(edge.fromRegionId);
        if (!edge.containsLaunchX(deeperX) || fromRegion == null || fromRegion.isRopeRegion || deeperX < fromRegion.minX || deeperX > fromRegion.maxX) {
            entry.navJumpLaunchDelaySteps = 0;
            return false;
        }
        entry.navJumpLaunchDelaySteps--;
        entry.navJumpLaunchX = deeperX;
        return true;
    }

    private static NavigationDirective tryExecuteDrop(BotNavigationGraph graph, BotMovementState entry, Character bot, Point botPos, Point rawTargetPos, BotNavigationGraph.Edge edge) {
        if (entry.inAir || entry.climbing || entry.downJumpPending || edge.launchStepX != 0) {
            return null;
        }
        if (!canExecuteDropFromCurrentPosition(graph, bot.getMap(), botPos, edge)) {
            entry.lastEdgeBlockReason = "drop-pos";
            return null;
        }
        entry.lastEdgeBlockReason = null;
        setEdgeExecutionTarget(entry, edge);
        BotPhysicsEngine.queueDownJump(entry, bot);
        BotMovementManager.broadcastMovement(entry);
        return new NavigationDirective(rawTargetPos, true);
    }

    private static NavigationDirective tryExecuteClimb(BotNavigationGraph graph, BotMovementState entry, Character bot, Point botPos, Point rawTargetPos, BotNavigationGraph.Edge edge) {
        if (entry.inAir || entry.downJumpPending) {
            return null;
        }
        if (entry.climbing) {
            return tryExecuteClimbExit(graph, entry, bot, botPos, rawTargetPos, edge);
        }
        return tryExecuteClimbEntry(graph, entry, bot, botPos, rawTargetPos, edge);
    }

    private static NavigationDirective tryExecuteClimbEntry(BotNavigationGraph graph, BotMovementState entry, Character bot, Point botPos, Point rawTargetPos, BotNavigationGraph.Edge edge) {
        BotNavigationGraph.Region toRegion = graph.getRegion(edge.toRegionId);
        Rope rope = findRopeForRegion(bot.getMap(), toRegion);
        if (rope == null) {
            return null;
        }
        if (!canExecuteClimbEntryFromCurrentPosition(bot.getMap(), botPos, edge, rope)) {
            entry.lastEdgeBlockReason = "climb-pos";
            return null;
        }
        if (canGrabRopeAtCurrentPosition(botPos, rope)) {
            entry.lastEdgeBlockReason = null;
            startClimbing(entry, bot, rope, botPos.y);
            return new NavigationDirective(rawTargetPos, true);
        }
        if (canAttachToRopeFromTopPlatform(edge, botPos, rope)) {
            entry.lastEdgeBlockReason = null;
            startClimbing(entry, bot, rope, edge.endPoint.y);
            return new NavigationDirective(rawTargetPos, true);
        }
        if (canGrabRopeFromTopPlatform(edge, botPos, rope)) {
            entry.lastEdgeBlockReason = null;
            BotPhysicsEngine.queueTopRopeEntry(entry, bot, rope, edge.endPoint.y);
            BotMovementManager.broadcastMovement(entry);
            return new NavigationDirective(rawTargetPos, true);
        }
        if (canExecuteGroundRopeJumpEntryFromCurrentPosition(botPos, edge)) {
            entry.lastEdgeBlockReason = null;
            BotMovementManager.initiateRopeJump(entry, bot, edge.launchStepX);
            return new NavigationDirective(rawTargetPos, true);
        }
        entry.lastEdgeBlockReason = "climb-reach";
        return null;
    }

    private static NavigationDirective tryExecuteClimbExit(BotNavigationGraph graph, BotMovementState entry, Character bot, Point botPos, Point rawTargetPos, BotNavigationGraph.Edge edge) {
        if (!canExecuteClimbExitFromCurrentPosition(graph, bot.getMap(), botPos, edge)) {
            return null;
        }
        BotNavigationGraph.Region toRegion = graph.getRegion(edge.toRegionId);
        if (toRegion != null && toRegion.isRopeRegion) {
            Rope targetRope = findRopeForRegion(bot.getMap(), toRegion);
            if (targetRope == null || BotMovementManager.sameRope(entry.climbRope, targetRope)) {
                return null;
            }
            BotMovementManager.jumpToRope(entry, bot, edge.launchStepX);
            return new NavigationDirective(rawTargetPos, true);
        }
        if (edge.launchStepX == 0) {
            return null;
        }
        Rope sourceRope = findRopeForRegion(bot.getMap(), graph.getRegion(edge.fromRegionId));
        if (isTopRopeJumpExitReady(sourceRope, botPos, edge) && botPos.y != edge.startPoint.y) {
            startClimbing(entry, bot, sourceRope, edge.startPoint.y);
        }
        BotMovementManager.jumpOffRope(entry, bot, edge.launchStepX);
        return new NavigationDirective(rawTargetPos, true);
    }

    static boolean canExecuteDropFromCurrentPosition(BotNavigationGraph graph, MapleMap map, Point botPos, BotNavigationGraph.Edge edge) {
        if (edge.type != BotNavigationGraph.EdgeType.DROP || edge.launchStepX != 0 || !isWithinDropLaunchWindow(graph, botPos, edge)) {
            return false;
        }
        return true;
    }

    private static NavigationDirective tryExecutePortalEdge(BotMovementState entry, Character bot, Point botPos, Point rawTargetPos, BotNavigationGraph.Edge edge) {
        if (entry.inAir || !isReadyForEdge(botPos, edge)) {
            entry.portalEnterReadyTicks = -1;
            return null;
        }
        if (entry.portalEnterReadyTicks < 0) {
            entry.portalEnterReadyTicks = ThreadLocalRandom.current().nextInt(4);
        }
        if (entry.portalEnterReadyTicks > 0) {
            entry.portalEnterReadyTicks--;
            return null;
        }
        entry.portalEnterReadyTicks = -1;
        return tryExecutePortal(entry, bot, rawTargetPos, edge);
    }

    private static NavigationDirective tryExecutePortal(BotMovementState entry, Character bot, Point rawTargetPos, BotNavigationGraph.Edge edge) {
        if (System.currentTimeMillis() < entry.portalUseCooldownUntilMs || !usePortal(bot, edge.portalId)) {
            return null;
        }
        entry.portalUseCooldownUntilMs = System.currentTimeMillis() + PORTAL_USE_COOLDOWN_MS;
        clearNavigation(entry);
        BotMovementManager.resetEntryState(entry);
        return new NavigationDirective(rawTargetPos, true);
    }

    /* JADX INFO: Thrown type has an unknown type hierarchy: java.lang.MatchException */
    private static boolean shouldUsePreciseTarget(BotNavigationGraph graph, BotMovementState entry, Point botPos, BotNavigationGraph.Edge edge) throws MatchException {
        if (entry.inAir) {
            return false;
        }
        switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[edge.type.ordinal()]) {
            case 1:
                return !canExecuteSelectedJumpFromCurrentPosition(graph, entry, entry.bot.getMap(), botPos, edge);
            case 2:
                return edge.launchStepX == 0 && !canExecuteDropFromCurrentPosition(graph, entry.bot.getMap(), botPos, edge);
            case PORTAL_ENTER_EXTRA_TICKS_MAX /* 3 */:
                return entry.climbing ? (edge.launchStepX == 0 || canExecuteClimbExitFromCurrentPosition(graph, entry.bot.getMap(), botPos, edge)) ? false : true : !canExecuteClimbEntryFromCurrentPosition(entry.bot.getMap(), botPos, edge, findRopeForRegion(entry.bot.getMap(), graph.getRegion(edge.toRegionId)));
            case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                return !isReadyForEdge(botPos, edge) || entry.portalEnterReadyTicks > 0;
            case 5:
                return shouldUsePreciseWalkTarget(edge);
            default:
                throw new MatchException((String) null, (Throwable) null);
        }
    }

    /* JADX INFO: Thrown type has an unknown type hierarchy: java.lang.MatchException */
    private static Point selectWaypoint(BotMovementState entry, BotNavigationGraph graph, Point botPos, BotNavigationGraph.Edge edge) throws MatchException {
        switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[edge.type.ordinal()]) {
            case 1:
                return entry.inAir ? new Point(edge.endPoint) : selectJumpWaypoint(graph, entry, botPos, edge);
            case 2:
                return selectDropWaypoint(entry, graph, botPos, edge);
            case PORTAL_ENTER_EXTRA_TICKS_MAX /* 3 */:
                return selectClimbWaypoint(graph, entry, botPos, edge);
            case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                return new Point(edge.startPoint);
            case 5:
                return new Point(edge.endPoint);
            default:
                throw new MatchException((String) null, (Throwable) null);
        }
    }

    static Point selectJumpWaypoint(BotMovementState entry, Point botPos, BotNavigationGraph.Edge edge) {
        BotNavigationGraph graph = BotNavigationGraphProvider.getGraph(entry.bot.getMap(), entry.movementProfile);
        return selectJumpWaypoint(graph, entry, botPos, edge);
    }

    static Point selectJumpWaypoint(BotNavigationGraph graph, Point botPos, BotNavigationGraph.Edge edge) {
        return selectJumpWaypoint(graph, null, botPos, edge);
    }

    private static Point selectJumpWaypoint(BotNavigationGraph graph, BotMovementState entry, Point botPos, BotNavigationGraph.Edge edge) {
        int iSelectedJumpLaunchX;
        BotNavigationGraph.Region fromRegion = graph.getRegion(edge.fromRegionId);
        if (fromRegion == null || fromRegion.isRopeRegion) {
            return new Point(edge.startPoint);
        }
        if (entry == null) {
            iSelectedJumpLaunchX = edge.containsLaunchX(botPos.x) ? botPos.x : botPos.x < edge.launchMinX ? edge.launchMinX : edge.launchMaxX;
        } else {
            iSelectedJumpLaunchX = selectedJumpLaunchX(entry, graph, edge);
        }
        int targetX = iSelectedJumpLaunchX;
        return fromRegion.pointAt(targetX);
    }

    static Point selectClimbWaypoint(BotMovementState entry, Point botPos, BotNavigationGraph.Edge edge) {
        BotNavigationGraph graph = resolveActiveGraph(entry.bot.getMap(), entry.movementProfile);
        return selectClimbWaypoint(graph, entry, botPos, edge);
    }

    static Point selectClimbWaypoint(BotNavigationGraph graph, BotMovementState entry, Point botPos, BotNavigationGraph.Edge edge) {
        if (entry.inAir) {
            return new Point(edge.endPoint);
        }
        if (entry.climbing && edge.launchStepX != 0) {
            if (graph != null && canExecuteClimbExitFromCurrentPosition(graph, entry.bot.getMap(), botPos, edge)) {
                return new Point(botPos);
            }
            return new Point(edge.startPoint);
        }
        if (entry.climbing) {
            int ropeX = entry.climbRope != null ? entry.climbRope.x() : edge.startPoint.x;
            return new Point(ropeX, edge.endPoint.y);
        }
        if (edge.launchStepX != 0 && edge.launchMaxX > edge.launchMinX) {
            return new Point(steerXWithinLaunchWindow(edge, botPos.x), edge.startPoint.y);
        }
        return new Point(edge.startPoint);
    }

    static int steerXWithinLaunchWindow(BotNavigationGraph.Edge edge, int botX) {
        int inset = Math.min((edge.launchMaxX - edge.launchMinX) / 2, 4);
        return Math.clamp(botX, edge.launchMinX + inset, edge.launchMaxX - inset);
    }

    private static BotNavigationGraph resolveActiveGraph(MapleMap map, BotMovementProfile movementProfile) {
        return BotNavigationGraphProvider.peekBestGraph(map, movementProfile);
    }

    static Point selectDropWaypoint(BotMovementState entry, BotNavigationGraph graph, Point botPos, BotNavigationGraph.Edge edge) {
        int iSteerXWithinLaunchWindow;
        if (entry.inAir) {
            return new Point(edge.endPoint);
        }
        if (edge.launchStepX == 0) {
            BotNavigationGraph.Region fromRegion = graph != null ? graph.getRegion(edge.fromRegionId) : null;
            if (fromRegion == null || fromRegion.isRopeRegion) {
                return new Point(edge.startPoint);
            }
            if (edge.containsLaunchX(botPos.x)) {
                iSteerXWithinLaunchWindow = botPos.x;
            } else {
                iSteerXWithinLaunchWindow = steerXWithinLaunchWindow(edge, botPos.x);
            }
            int targetX = iSteerXWithinLaunchWindow;
            return fromRegion.pointAt(targetX);
        }
        if (hasReachedDirectionalDropRunway(botPos, edge)) {
            return new Point(edge.endPoint);
        }
        BotNavigationGraph.Region fromRegion2 = graph.getRegion(edge.fromRegionId);
        if (fromRegion2 == null || fromRegion2.isRopeRegion) {
            return new Point(edge.endPoint);
        }
        BotPhysicsEngine.WalkOffLanding liveOutcome = BotPhysicsEngine.simulateWalkOffLanding(entry.bot.getMap(), botPos, Integer.signum(edge.launchStepX), new BotPhysicsEngine.GroundTravelState(entry.physX, entry.hspeed, entry.groundPhysicsCarryMs), entry.movementProfile);
        if (matchesDirectionalDrop(edge, graph, liveOutcome)) {
            return new Point(edge.endPoint);
        }
        return new Point(edge.startPoint);
    }

    private static boolean hasReachedDirectionalDropRunway(Point botPos, BotNavigationGraph.Edge edge) {
        if (botPos == null || edge == null || edge.launchStepX == 0) {
            return false;
        }
        int direction = Integer.signum(edge.launchStepX);
        return direction > 0 ? botPos.x >= edge.startPoint.x : botPos.x <= edge.startPoint.x;
    }

    private static boolean matchesDirectionalDrop(BotNavigationGraph.Edge edge, BotNavigationGraph graph, BotPhysicsEngine.WalkOffLanding outcome) {
        Foothold landingFoothold;
        if (outcome == null || outcome.landing() == null || (landingFoothold = outcome.landing().foothold()) == null || graph.regionIdByFootholdId.getOrDefault(Integer.valueOf(landingFoothold.getId()), -1).intValue() != edge.toRegionId) {
            return false;
        }
        int xTolerance = Math.max(BLOCKED_POS_GIVE_UP_MIN_TICKS, Math.abs(edge.launchStepX) + 2);
        int yTolerance = BotMovementManager.cfg.JUMP_Y_THRESH * 2;
        return Math.abs(outcome.landing().point().x - edge.endPoint.x) <= xTolerance && Math.abs(outcome.landing().point().y - edge.endPoint.y) <= yTolerance;
    }

    private static BotNavigationGraph.Edge findNextEdge(BotNavigationGraph graph, Character bot, int startRegionId, int targetRegionId, Point targetPos) {
        List<BotNavigationGraph.Edge> path = findPath(graph, bot.getMap(), bot.getPosition(), startRegionId, targetRegionId, targetPos, null, routeSeed(bot));
        if (path.isEmpty()) {
            return null;
        }
        return collapseLeadingWalkEdges(path);
    }

    static List<BotNavigationGraph.Edge> findPath(BotNavigationGraph graph, Character bot, int startRegionId, int targetRegionId, Point targetPos) {
        return findPath(graph, bot.getMap(), bot.getPosition(), startRegionId, targetRegionId, targetPos, null, routeSeed(bot));
    }

    static List<BotNavigationGraph.Edge> findPath(BotNavigationGraph graph, MapleMap map, Point startPos, int startRegionId, int targetRegionId, Point targetPos) {
        return findPath(graph, map, startPos, startRegionId, targetRegionId, targetPos, null);
    }

    static List<BotNavigationGraph.Edge> findPathForTargetScore(BotNavigationGraph graph, MapleMap map, Point startPos, int startRegionId, int targetRegionId, Point targetPos) {
        return findPath(graph, map, startPos, startRegionId, targetRegionId, targetPos, "target-score");
    }

    private static List<BotNavigationGraph.Edge> findPath(BotNavigationGraph graph, MapleMap map, Point startPos, int startRegionId, int targetRegionId, Point targetPos, String pathfindCaller) {
        return findPath(graph, map, startPos, startRegionId, targetRegionId, targetPos, pathfindCaller, 0L);
    }

    private static List<BotNavigationGraph.Edge> findPath(BotNavigationGraph graph, MapleMap map, Point startPos, int startRegionId, int targetRegionId, Point targetPos, String pathfindCaller, long routeSeed) {
        return runSearch(graph, map, startPos, startRegionId, targetRegionId, targetPos, pathfindCaller, useAdmissibleHeuristic, true, routeSeed).path();
    }

    static SearchOutcome runSearch(BotNavigationGraph graph, MapleMap map, Point startPos, int startRegionId, int targetRegionId, Point targetPos, String pathfindCaller, boolean zeroHeuristic, boolean instrument, long routeSeed) {
        Point pointPointAtNearestLaunchX;
        Point point;
        int goalCost;
        long startedAt = System.nanoTime();
        PathfindProfile profile = null;
        boolean randomized = routeSeed != 0;
        double epsilon = randomized ? 1.0d + (hashFrac(routeSeed, EPSILON_SALT) * EPSILON_SPAN) : 0.0d;
        try {
            PriorityQueue<SearchNode> open = new PriorityQueue<>(Comparator.comparingInt((SearchNode node) -> node.score));
            Map<SearchState, Integer> gScore = new HashMap<>();
            Map<SearchState, SearchState> cameFrom = new HashMap<>();
            Map<SearchState, BotNavigationGraph.Edge> cameByEdge = new HashMap<>();
            SearchState startState = new SearchState(startRegionId, new Point(startPos), false);
            SearchState bestGoalState = null;
            int bestGoalCost = Integer.MAX_VALUE;
            int expandedNodes = 0;
            int staleNodes = 0;
            int edgeChecks = 0;
            int usableEdges = 0;
            int relaxations = 0;
            int openPeak = 1;
            gScore.put(startState, 0);
            open.add(new SearchNode(startState, 0, hValue(graph, startPos, targetPos, zeroHeuristic, randomized, epsilon)));
            while (!open.isEmpty()) {
                SearchNode current = open.poll();
                if (current.cost != gScore.getOrDefault(current.state, Integer.MAX_VALUE).intValue()) {
                    staleNodes++;
                } else {
                    if (bestGoalState != null && current.score >= bestGoalCost) {
                        break;
                    }
                    expandedNodes++;
                    if (current.state.regionId == targetRegionId && (goalCost = current.cost + intraRegionTravelCost(graph, current.state.regionId, current.state.point, targetPos)) < bestGoalCost) {
                        bestGoalCost = goalCost;
                        bestGoalState = current.state;
                    }
                    for (BotNavigationGraph.Edge edge : graph.getOutgoing(current.state.regionId)) {
                        edgeChecks++;
                        if (isEdgeUsable(graph, map, edge)) {
                            usableEdges++;
                            boolean isPortal = edge.type == BotNavigationGraph.EdgeType.PORTAL;
                            boolean enteredThroughExit = current.state.viaPortal && current.state.point.equals(edge.startPoint);
                            int edgeCost = (isPortal && enteredThroughExit) ? 250 : edge.cost;
                            boolean straightDrop = edge.type == BotNavigationGraph.EdgeType.DROP && edge.launchStepX == 0;
                            if (straightDrop) {
                                pointPointAtNearestLaunchX = edge.pointAtNearestLaunchX(current.state.point.x);
                            } else {
                                pointPointAtNearestLaunchX = edge.startPoint;
                            }
                            Point approachPoint = pointPointAtNearestLaunchX;
                            if (straightDrop) {
                                point = new Point(approachPoint.x, edge.endPoint.y);
                            } else {
                                point = edge.endPoint;
                            }
                            Point landingPoint = point;
                            int stepCost = intraRegionTravelCost(graph, current.state.regionId, current.state.point, approachPoint) + edgeCost;
                            if (randomized) {
                                stepCost += (int) Math.round(stepCost * JITTER_FRAC * hashFrac(routeSeed, edgeKey(edge)));
                            }
                            int tentativeCost = current.cost + stepCost;
                            SearchState nextState = new SearchState(edge.toRegionId, landingPoint, isPortal);
                            if (tentativeCost < gScore.getOrDefault(nextState, Integer.MAX_VALUE).intValue()) {
                                relaxations++;
                                gScore.put(nextState, Integer.valueOf(tentativeCost));
                                cameFrom.put(nextState, current.state);
                                cameByEdge.put(nextState, edge);
                                int fScore = tentativeCost + hValue(graph, edge.endPoint, targetPos, zeroHeuristic, randomized, epsilon);
                                open.add(new SearchNode(nextState, tentativeCost, fScore));
                                openPeak = Math.max(openPeak, open.size());
                            }
                        }
                    }
                }
            }
            List<BotNavigationGraph.Edge> path = reconstructPath(startState, bestGoalState, cameFrom, cameByEdge);
            profile = new PathfindProfile(System.nanoTime() - startedAt, expandedNodes, staleNodes, edgeChecks, usableEdges, relaxations, openPeak, bestGoalCost, path.size());
            boolean usesPortal = false;
            Iterator<BotNavigationGraph.Edge> it = path.iterator();
            while (true) {
                if (!it.hasNext()) {
                    break;
                }
                if (it.next().type == BotNavigationGraph.EdgeType.PORTAL) {
                    usesPortal = true;
                    break;
                }
            }
            SearchOutcome searchOutcome = new SearchOutcome(path, bestGoalCost, expandedNodes, usesPortal);
            if (instrument) {
                if (profile == null) {
                    profile = new PathfindProfile(System.nanoTime() - startedAt, 0, 0, 0, 0, 0, 0, Integer.MAX_VALUE, 0);
                }
                logSlowPathfind(graph, map, startPos, startRegionId, targetRegionId, targetPos, pathfindCaller, profile);
                BotPerformanceMonitor.recordPathfind(pathfindCaller, System.nanoTime() - startedAt);
            }
            return searchOutcome;
        } catch (Throwable th) {
            if (instrument) {
                if (profile == null) {
                    profile = new PathfindProfile(System.nanoTime() - startedAt, 0, 0, 0, 0, 0, 0, Integer.MAX_VALUE, 0);
                }
                logSlowPathfind(graph, map, startPos, startRegionId, targetRegionId, targetPos, pathfindCaller, profile);
                BotPerformanceMonitor.recordPathfind(pathfindCaller, System.nanoTime() - startedAt);
            }
            throw th;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager$SearchOutcome.class */
    static final class SearchOutcome {
        private final List<BotNavigationGraph.Edge> path;
        private final int cost;
        private final int expandedNodes;
        private final boolean usesPortal;

        SearchOutcome(List<BotNavigationGraph.Edge> path, int cost, int expandedNodes, boolean usesPortal) {
            this.path = path;
            this.cost = cost;
            this.expandedNodes = expandedNodes;
            this.usesPortal = usesPortal;
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

        public List<BotNavigationGraph.Edge> path() {
            return this.path;
        }

        public int cost() {
            return this.cost;
        }

        public int expandedNodes() {
            return this.expandedNodes;
        }

        public boolean usesPortal() {
            return this.usesPortal;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationManager$PathOptimality.class */
    static final class PathOptimality {
        private final int currentCost;
        private final int optimalCost;
        private final boolean currentUsesPortal;
        private final boolean optimalUsesPortal;
        private final int currentExpanded;
        private final int optimalExpanded;

        PathOptimality(int currentCost, int optimalCost, boolean currentUsesPortal, boolean optimalUsesPortal, int currentExpanded, int optimalExpanded) {
            this.currentCost = currentCost;
            this.optimalCost = optimalCost;
            this.currentUsesPortal = currentUsesPortal;
            this.optimalUsesPortal = optimalUsesPortal;
            this.currentExpanded = currentExpanded;
            this.optimalExpanded = optimalExpanded;
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

        public int currentCost() {
            return this.currentCost;
        }

        public int optimalCost() {
            return this.optimalCost;
        }

        public boolean currentUsesPortal() {
            return this.currentUsesPortal;
        }

        public boolean optimalUsesPortal() {
            return this.optimalUsesPortal;
        }

        public int currentExpanded() {
            return this.currentExpanded;
        }

        public int optimalExpanded() {
            return this.optimalExpanded;
        }

        boolean reachable() {
            return (this.currentCost == Integer.MAX_VALUE || this.optimalCost == Integer.MAX_VALUE) ? false : true;
        }

        boolean suboptimal() {
            return reachable() && this.currentCost > this.optimalCost;
        }

        int costDelta() {
            if (reachable()) {
                return this.currentCost - this.optimalCost;
            }
            return 0;
        }

        boolean portalSkipped() {
            return suboptimal() && this.optimalUsesPortal && !this.currentUsesPortal;
        }
    }

    static PathOptimality measureOptimality(BotNavigationGraph graph, MapleMap map, Point startPos, int startRegionId, int targetRegionId, Point targetPos) {
        SearchOutcome current = runSearch(graph, map, startPos, startRegionId, targetRegionId, targetPos, "measure", false, false, 0L);
        SearchOutcome optimal = runSearch(graph, map, startPos, startRegionId, targetRegionId, targetPos, "measure", true, false, 0L);
        return new PathOptimality(current.cost(), optimal.cost(), current.usesPortal(), optimal.usesPortal(), current.expandedNodes(), optimal.expandedNodes());
    }

    private static void logSlowPathfind(BotNavigationGraph graph, MapleMap map, Point startPos, int startRegionId, int targetRegionId, Point targetPos, String pathfindCaller, PathfindProfile profile) {
        if (profile.elapsedNs() < SLOW_PATHFIND_WARN_NS) {
            return;
        }
        long now = System.currentTimeMillis();
        long next = slowPathfindNextWarnAtMs.get();
        if (now < next || !slowPathfindNextWarnAtMs.compareAndSet(next, now + SLOW_PATHFIND_WARN_COOLDOWN_MS)) {
            slowPathfindSuppressed.incrementAndGet();
            return;
        }
        int suppressed = slowPathfindSuppressed.getAndSet(0);
        int regionCount = (graph == null || graph.regions == null) ? -1 : graph.regions.size();
        int outgoingFromStart = graph != null ? graph.getOutgoing(startRegionId).size() : -1;
        String caller = (pathfindCaller == null || pathfindCaller.isBlank()) ? "default" : pathfindCaller;
        int bestGoalCost = profile.bestGoalCost() == Integer.MAX_VALUE ? -1 : profile.bestGoalCost();
        Logger logger = log;
        String str = "Slow bot pathfind (suppressedSinceLast=" + suppressed + "): caller={} took {} ms map={} startRegion={} targetRegion={} regions={} startOut={} startPos=({}, {}) targetPos=({}, {}) expanded={} stale={} edgeChecks={} usableEdges={} relaxations={} openPeak={} bestGoalCost={} resultEdges={}";
        Object[] objArr = new Object[19];
        objArr[0] = caller;
        objArr[1] = String.format("%.1f", Double.valueOf(profile.elapsedNs() / 1000000.0d));
        objArr[2] = Integer.valueOf(map != null ? map.getId() : -1);
        objArr[PORTAL_ENTER_EXTRA_TICKS_MAX] = Integer.valueOf(startRegionId);
        objArr[4] = Integer.valueOf(targetRegionId);
        objArr[5] = Integer.valueOf(regionCount);
        objArr[BLOCKED_POS_GIVE_UP_MIN_TICKS] = Integer.valueOf(outgoingFromStart);
        objArr[7] = Integer.valueOf(startPos != null ? startPos.x : -1);
        objArr[8] = Integer.valueOf(startPos != null ? startPos.y : -1);
        objArr[9] = Integer.valueOf(targetPos != null ? targetPos.x : -1);
        objArr[JUMP_READY_X_TOLERANCE] = Integer.valueOf(targetPos != null ? targetPos.y : -1);
        objArr[11] = Integer.valueOf(profile.expandedNodes());
        objArr[12] = Integer.valueOf(profile.staleNodes());
        objArr[13] = Integer.valueOf(profile.edgeChecks());
        objArr[EDGE_READY_X_TOLERANCE] = Integer.valueOf(profile.usableEdges());
        objArr[15] = Integer.valueOf(profile.relaxations());
        objArr[16] = Integer.valueOf(profile.openPeak());
        objArr[17] = Integer.valueOf(bestGoalCost);
        objArr[18] = Integer.valueOf(profile.resultEdges());
        logger.warn(str, objArr);
    }

    private static List<BotNavigationGraph.Edge> reconstructPath(SearchState startState, SearchState goalState, Map<SearchState, SearchState> cameFrom, Map<SearchState, BotNavigationGraph.Edge> cameByEdge) {
        if (goalState == null || !cameByEdge.containsKey(goalState)) {
            return List.of();
        }
        List<BotNavigationGraph.Edge> path = new ArrayList<>();
        SearchState searchState = goalState;
        while (true) {
            SearchState cursor = searchState;
            if (!cursor.equals(startState)) {
                BotNavigationGraph.Edge edge = cameByEdge.get(cursor);
                if (edge == null) {
                    return List.of();
                }
                path.add(0, edge);
                SearchState previousState = cameFrom.get(cursor);
                if (previousState == null) {
                    return List.of();
                }
                searchState = previousState;
            } else {
                return path;
            }
        }
    }

    static BotNavigationGraph.Edge collapseLeadingWalkEdges(List<BotNavigationGraph.Edge> path) {
        BotNavigationGraph.Edge first = path.get(0);
        if (first.type != BotNavigationGraph.EdgeType.WALK) {
            return first;
        }
        if (!isNoMovementWalk(first.startPoint, first.endPoint)) {
            return first;
        }
        int totalCost = 0;
        int walkCount = 0;
        while (walkCount < path.size()) {
            BotNavigationGraph.Edge edge = path.get(walkCount);
            if (edge.type != BotNavigationGraph.EdgeType.WALK || !isNoMovementWalk(edge.startPoint, edge.endPoint)) {
                break;
            }
            totalCost += edge.cost;
            walkCount++;
        }
        if (walkCount >= path.size()) {
            return null;
        }
        BotNavigationGraph.Edge next = path.get(walkCount);
        return new BotNavigationGraph.Edge(first.fromRegionId, next.toRegionId, next.type, next.startPoint, next.endPoint, next.launchMinX, next.launchMaxX, next.launchStepX, next.portalId, next.ropeX, next.ropeTopY, next.ropeBottomY, totalCost + next.cost);
    }

    private static boolean isEdgeUsable(BotNavigationGraph graph, Character bot, BotNavigationGraph.Edge edge) {
        return isEdgeUsable(graph, bot.getMap(), edge);
    }

    private static boolean sameEdge(BotNavigationGraph.Edge left, BotNavigationGraph.Edge right) {
        return left == right || (left != null && right != null && left.fromRegionId == right.fromRegionId && left.toRegionId == right.toRegionId && left.type == right.type && left.launchMinX == right.launchMinX && left.launchMaxX == right.launchMaxX && left.launchStepX == right.launchStepX && left.portalId == right.portalId && left.ropeX == right.ropeX && left.ropeTopY == right.ropeTopY && left.ropeBottomY == right.ropeBottomY && left.startPoint.equals(right.startPoint) && left.endPoint.equals(right.endPoint));
    }

    static boolean shouldRetainCommittedGroundEdge(BotNavigationGraph.Edge current, BotNavigationGraph.Edge replacement) {
        return (current == null || replacement == null || current.fromRegionId != replacement.fromRegionId || current.toRegionId != replacement.toRegionId || current.type == BotNavigationGraph.EdgeType.WALK || replacement.type == BotNavigationGraph.EdgeType.WALK) ? false : true;
    }

    /* JADX INFO: Thrown type has an unknown type hierarchy: java.lang.MatchException */
    private static boolean isEdgeUsable(BotNavigationGraph graph, MapleMap map, BotNavigationGraph.Edge edge) throws MatchException {
        switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[edge.type.ordinal()]) {
            case 1:
            case 2:
            case PORTAL_ENTER_EXTRA_TICKS_MAX /* 3 */:
            case 5:
                return true;
            case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                Portal portal = map.getPortal(edge.portalId);
                return portal != null && portal.getPortalStatus();
            default:
                throw new MatchException((String) null, (Throwable) null);
        }
    }

    private static boolean usePortal(Character bot, int portalId) {
        Portal portal = bot.getMap().getPortal(portalId);
        if (portal == null || !portal.getPortalStatus()) {
            return false;
        }
        int oldMapId = bot.getMapId();
        Point oldPos = bot.getPosition();
        GCPortals.enter(bot, portal);
        return (bot.getMapId() == oldMapId && bot.getPosition().equals(oldPos)) ? false : true;
    }

    private static boolean isReadyForEdge(Point botPos, BotNavigationGraph.Edge edge) {
        int dx = Math.abs(botPos.x - edge.startPoint.x);
        int dy = Math.abs(botPos.y - edge.startPoint.y);
        switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$GCMoveSystem$BotNavigationGraph$EdgeType[edge.type.ordinal()]) {
            case 1:
                return dx <= JUMP_READY_X_TOLERANCE && dy <= BotMovementManager.cfg.JUMP_Y_THRESH;
            case 2:
            case PORTAL_ENTER_EXTRA_TICKS_MAX /* 3 */:
            case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                return dx <= EDGE_READY_X_TOLERANCE && dy <= BotMovementManager.cfg.JUMP_Y_THRESH * 2;
            default:
                return dx <= BotMovementManager.cfg.STOP_DIST + 8 && dy <= BotMovementManager.cfg.JUMP_Y_THRESH * 2;
        }
    }

    static boolean canExecuteJumpFromCurrentPosition(BotNavigationGraph graph, MapleMap map, Point botPos, BotNavigationGraph.Edge edge) {
        if (edge.type != BotNavigationGraph.EdgeType.JUMP) {
            return false;
        }
        return isWithinJumpLaunchWindow(graph, botPos, edge);
    }

    private static boolean canExecuteSelectedJumpFromCurrentPosition(BotNavigationGraph graph, BotMovementState entry, MapleMap map, Point botPos, BotNavigationGraph.Edge edge) {
        if (!canExecuteJumpFromCurrentPosition(graph, map, botPos, edge)) {
            return false;
        }
        int launchX = selectedJumpLaunchX(entry, graph, edge);
        int tolerance = Math.max(1, BotPhysicsEngine.walkStep(map, entry != null ? entry.movementProfile : null));
        return Math.abs(botPos.x - launchX) <= tolerance;
    }

    private static boolean isReachableWithinRegion(BotNavigationGraph graph, MapleMap map, int regionId, Point fromPos, Point toPos) {
        BotNavigationGraph.Region region = graph.getRegion(regionId);
        if (region == null || fromPos == null || toPos == null) {
            return false;
        }
        if (region.isRopeRegion) {
            return fromPos.x == toPos.x;
        }
        int dir = Integer.compare(toPos.x, fromPos.x);
        Point previous = region.pointAt(fromPos.x);
        if (graph.findRegionId(map, previous) != regionId) {
            return false;
        }
        if (dir == 0) {
            return Math.abs(toPos.y - previous.y) <= BotMovementManager.cfg.JUMP_Y_THRESH;
        }
        int i = fromPos.x;
        while (true) {
            int x = i + dir;
            if (x != toPos.x + dir) {
                Point current = region.pointAt(x);
                if (graph.findRegionId(map, current) != regionId || !BotPhysicsEngine.isWalkableEndpointStep(Math.abs(current.x - previous.x), current.y - previous.y)) {
                    return false;
                }
                previous = current;
                i = x;
            } else {
                return true;
            }
        }
    }

    static boolean isWithinJumpLaunchWindow(BotNavigationGraph graph, Point botPos, BotNavigationGraph.Edge edge) {
        BotNavigationGraph.Region fromRegion;
        if (botPos == null || edge.type != BotNavigationGraph.EdgeType.JUMP || !edge.containsLaunchX(botPos.x) || (fromRegion = graph.getRegion(edge.fromRegionId)) == null) {
            return false;
        }
        Point expectedLaunchPoint = fromRegion.pointAt(botPos.x);
        return Math.abs(botPos.y - expectedLaunchPoint.y) <= BotMovementManager.cfg.JUMP_Y_THRESH;
    }

    static boolean isWithinDropLaunchWindow(BotNavigationGraph graph, Point botPos, BotNavigationGraph.Edge edge) {
        if (botPos == null || edge.type != BotNavigationGraph.EdgeType.DROP || edge.launchStepX != 0 || !edge.containsLaunchX(botPos.x)) {
            return false;
        }
        if (graph == null) {
            return Math.abs(botPos.y - edge.startPoint.y) <= BotMovementManager.cfg.JUMP_Y_THRESH;
        }
        BotNavigationGraph.Region fromRegion = graph.getRegion(edge.fromRegionId);
        if (fromRegion == null || fromRegion.isRopeRegion) {
            return false;
        }
        Point expectedLaunchPoint = fromRegion.pointAt(botPos.x);
        return Math.abs(botPos.y - expectedLaunchPoint.y) <= BotMovementManager.cfg.JUMP_Y_THRESH;
    }

    private static int selectedJumpLaunchX(BotMovementState entry, BotNavigationGraph graph, BotNavigationGraph.Edge edge) {
        int iNextInt;
        if (entry == null || graph == null || edge == null || edge.type != BotNavigationGraph.EdgeType.JUMP) {
            if (edge != null) {
                return edge.startPoint.x;
            }
            return 0;
        }
        BotNavigationGraph.Region fromRegion = graph.getRegion(edge.fromRegionId);
        if (fromRegion == null || fromRegion.isRopeRegion) {
            return edge.startPoint.x;
        }
        if (sameEdge(entry.navJumpLaunchEdge, edge) && entry.navJumpLaunchX >= edge.launchMinX && entry.navJumpLaunchX <= edge.launchMaxX) {
            return entry.navJumpLaunchX;
        }
        int minX = Math.max(edge.launchMinX, fromRegion.minX);
        int maxX = Math.min(edge.launchMaxX, fromRegion.maxX);
        if (minX > maxX) {
            minX = edge.launchMinX;
            maxX = edge.launchMaxX;
        }
        int width = Math.max(0, maxX - minX);
        int margin = Math.min(width / 2, Math.max(1, BotPhysicsEngine.walkStep(entry.bot.getMap(), entry.movementProfile) * 2));
        int randomMinX = minX + margin;
        int randomMaxX = maxX - margin;
        if (randomMinX > randomMaxX) {
            randomMinX = minX;
            randomMaxX = maxX;
        }
        if (randomMinX >= randomMaxX) {
            iNextInt = randomMinX;
        } else {
            iNextInt = ThreadLocalRandom.current().nextInt(randomMinX, randomMaxX + 1);
        }
        int selectedX = iNextInt;
        entry.navJumpLaunchEdge = edge;
        entry.navJumpLaunchX = selectedX;
        return selectedX;
    }

    private static int intraRegionTravelCost(BotNavigationGraph graph, Point from, Point to) {
        int dx = Math.abs(to.x - from.x);
        return Math.max(0, (int) Math.round((dx * 1000.0d) / Math.max(1.0d, graph.movementProfile.walkVelocityPxs())));
    }

    private static int intraRegionTravelCost(BotNavigationGraph graph, int regionId, Point from, Point to) {
        BotNavigationGraph.Region region = graph.getRegion(regionId);
        if (region != null && region.isRopeRegion) {
            int travel = Math.abs(to.y - from.y);
            return Math.max(0, (int) Math.round((travel * 1000.0d) / Math.max(1.0f, BotMovementManager.cfg.CLIMB_SPEED_PXS)));
        }
        return intraRegionTravelCost(graph, from, to);
    }

    private static int heuristic(BotNavigationGraph graph, Point from, Point targetPos) {
        return intraRegionTravelCost(graph, from, targetPos);
    }

    private static int hValue(BotNavigationGraph graph, Point from, Point targetPos, boolean zeroHeuristic, boolean randomized, double epsilon) {
        if (randomized) {
            return (int) Math.round(epsilon * heuristic(graph, from, targetPos));
        }
        if (zeroHeuristic) {
            return 0;
        }
        return heuristic(graph, from, targetPos);
    }

    private static long routeSeed(Character bot) {
        return mix64(bot.getId()) | 1;
    }

    private static long edgeKey(BotNavigationGraph.Edge edge) {
        long k = edge.toRegionId;
        return (((((k * 31) + edge.startPoint.x) * 31) + edge.startPoint.y) * 31) + edge.type.ordinal();
    }

    private static double hashFrac(long seed, long key) {
        long h = mix64(seed ^ (key * (-7046029254386353131L)));
        return (h >>> 11) * 1.1102230246251565E-16d;
    }

    private static long mix64(long z) {
        long z2 = (z ^ (z >>> 30)) * (-4658895280553007687L);
        long z3 = (z2 ^ (z2 >>> 27)) * (-7723592293110705685L);
        return z3 ^ (z3 >>> 31);
    }

    static boolean shouldUsePreciseWalkTarget(BotNavigationGraph.Edge edge) {
        return (edge == null || edge.type != BotNavigationGraph.EdgeType.WALK || isNoMovementWalk(edge.startPoint, edge.endPoint)) ? false : true;
    }

    private static boolean isNoMovementWalk(Point start, Point end) {
        return Math.abs(end.x - start.x) <= 4 && Math.abs(end.y - start.y) <= 4;
    }

    private static boolean canGrabRopeAtCurrentPosition(Point botPos, Rope rope) {
        return Math.abs(botPos.x - rope.x()) <= BotMovementManager.cfg.ROPE_GRAB_X && botPos.y >= BotPhysicsEngine.firstClimbableY(rope) && botPos.y <= rope.bottomY();
    }

    private static boolean canAttachToRopeFromTopPlatform(BotNavigationGraph.Edge edge, Point botPos, Rope rope) {
        return Math.abs(botPos.x - rope.x()) <= BotMovementManager.cfg.ROPE_GRAB_X && edge.endPoint.y == BotPhysicsEngine.firstClimbableY(rope) && botPos.y < rope.topY() && rope.topY() - botPos.y <= BotPhysicsEngine.cfg.MAX_SNAP_DROP;
    }

    private static boolean canGrabRopeFromTopPlatform(BotNavigationGraph.Edge edge, Point botPos, Rope rope) {
        return edge.startPoint.y <= rope.topY() + BotMovementManager.cfg.JUMP_Y_THRESH && Math.abs(botPos.x - rope.x()) <= BotMovementManager.cfg.ROPE_GRAB_X;
    }

    private static boolean canExecuteClimbEntryFromCurrentPosition(MapleMap map, Point botPos, BotNavigationGraph.Edge edge, Rope rope) {
        return rope != null && (canGrabRopeAtCurrentPosition(botPos, rope) || canAttachToRopeFromTopPlatform(edge, botPos, rope) || canGrabRopeFromTopPlatform(edge, botPos, rope) || canExecuteGroundRopeJumpEntryFromCurrentPosition(botPos, edge));
    }

    private static boolean canExecuteGroundRopeJumpEntryFromCurrentPosition(Point botPos, BotNavigationGraph.Edge edge) {
        return botPos != null && edge != null && edge.type == BotNavigationGraph.EdgeType.CLIMB && edge.containsLaunchX(botPos.x) && Math.abs(botPos.y - edge.startPoint.y) <= BotMovementManager.cfg.JUMP_Y_THRESH * 2;
    }

    private static boolean canExecuteClimbExitFromCurrentPosition(BotNavigationGraph graph, MapleMap map, Point botPos, BotNavigationGraph.Edge edge) {
        if (edge.type != BotNavigationGraph.EdgeType.CLIMB) {
            return false;
        }
        if (edge.launchStepX != 0 && botPos.y != edge.startPoint.y && !isTopRopeJumpExitReady(findRopeForRegion(map, graph.getRegion(edge.fromRegionId)), botPos, edge)) {
            return false;
        }
        BotNavigationGraph.Region toRegion = graph.getRegion(edge.toRegionId);
        if (toRegion != null && toRegion.isRopeRegion) {
            return Math.abs(botPos.y - edge.startPoint.y) <= BotMovementManager.cfg.JUMP_Y_THRESH * 2;
        }
        if (edge.launchStepX != 0) {
            return Math.abs(botPos.y - edge.startPoint.y) <= BotMovementManager.cfg.JUMP_Y_THRESH * 2;
        }
        Rope rope = findRopeForRegion(map, graph.getRegion(edge.fromRegionId));
        return rope != null && isTopStepOffExit(rope, botPos, edge);
    }

    private static boolean isTopRopeJumpExitReady(Rope rope, Point botPos, BotNavigationGraph.Edge edge) {
        if (rope == null || botPos == null || edge == null || edge.launchStepX == 0) {
            return false;
        }
        int firstClimbableY = BotPhysicsEngine.firstClimbableY(rope);
        return edge.startPoint.x == rope.x() && edge.startPoint.y == firstClimbableY && botPos.x == rope.x() && botPos.y >= firstClimbableY && botPos.y <= (firstClimbableY + BotPhysicsEngine.climbStepPerTick()) + 2;
    }

    private static void startClimbing(BotMovementState entry, Character bot, Rope rope, int climbY) {
        BotPhysicsEngine.attachToRope(entry, bot, rope, climbY);
        BotMovementManager.broadcastMovement(entry);
    }

    private static void setEdgeExecutionTarget(BotMovementState entry, BotNavigationGraph.Edge edge) {
        entry.navPreciseTarget = false;
        entry.navTargetPos = new Point(edge.endPoint);
    }

    private static Point adjustPathTarget(BotMovementState entry, BotNavigationGraph graph, int targetRegionId, Point rawTargetPos) {
        if (rawTargetPos == null || !entry.grinding || targetRegionId < 0) {
            return rawTargetPos;
        }
        BotNavigationGraph.Region targetRegion = graph.getRegion(targetRegionId);
        if (targetRegion == null || targetRegion.isRopeRegion) {
            return rawTargetPos;
        }
        int safeLeft = targetRegion.minX + BotMovementManager.cfg.GRIND_EDGE_MARGIN;
        int safeRight = targetRegion.maxX - BotMovementManager.cfg.GRIND_EDGE_MARGIN;
        if (safeLeft >= safeRight) {
            return rawTargetPos;
        }
        int clampedX = Math.max(safeLeft, Math.min(safeRight, rawTargetPos.x));
        return targetRegion.pointAt(clampedX);
    }

    private static int landingRegionId(BotNavigationGraph graph, BotPhysicsEngine.JumpLanding landing) {
        if (landing == null) {
            return -1;
        }
        return graph.regionIdByFootholdId.getOrDefault(Integer.valueOf(landing.foothold().getId()), -1).intValue();
    }

    static int resolveCurrentRegionId(BotNavigationGraph graph, BotMovementState entry, MapleMap map, Point botPos) {
        if (entry.climbing || (entry.bot != null && CharacterStance.isClimbing(entry.bot.getStance()))) {
            int ropeX = entry.climbRope != null ? entry.climbRope.x() : botPos.x;
            int ropeRegionId = graph.findRopeRegionId(new Point(ropeX, botPos.y));
            if (ropeRegionId >= 0) {
                return ropeRegionId;
            }
        }
        if (entry.inAir) {
            return -1;
        }
        return graph.findRegionId(map, botPos);
    }

    static int resolveTargetRegionId(BotNavigationGraph graph, BotMovementState entry, MapleMap map, Point targetPos) {
        if (targetPos == null) {
            return -1;
        }
        Character followAnchor = entry.owner;
        if (entry.following && entry.moveTarget == null && entry.farmAnchor == null && !entry.shopVisitPending && !entry.grinding && followAnchor != null && followAnchor.getMap() == map) {
            if (CharacterStance.isClimbing(followAnchor.getStance())) {
                int ropeRegionId = graph.findRopeRegionId(targetPos);
                if (ropeRegionId >= 0) {
                    return ropeRegionId;
                }
                return resolveCharacterRegionId(graph, map, followAnchor);
            }
            if (targetPos.equals(followAnchor.getPosition())) {
                return resolveCharacterRegionId(graph, map, followAnchor);
            }
        }
        return resolvePointTargetRegionId(graph, map, targetPos);
    }

    static int resolveCharacterRegionId(BotNavigationGraph graph, MapleMap map, Character character) {
        Point position;
        int ropeRegionId;
        if (character == null || (position = character.getPosition()) == null) {
            return -1;
        }
        if (CharacterStance.isClimbing(character.getStance()) && (ropeRegionId = graph.findRopeRegionId(position)) >= 0) {
            return ropeRegionId;
        }
        return resolvePointTargetRegionId(graph, map, position);
    }

    static int resolvePointTargetRegionId(BotNavigationGraph graph, MapleMap map, Point position) {
        int ropeRegionId = graph.findRopeRegionId(position);
        if (ropeRegionId >= 0 && shouldPreferRopeRegion(map, position)) {
            return ropeRegionId;
        }
        return graph.findRegionId(map, position);
    }

    private static boolean shouldPreferRopeRegion(MapleMap map, Point position) {
        return BotPhysicsEngine.isGroundFarBelow(map, position);
    }

    private static boolean isRopeEntryEdge(BotNavigationGraph graph, BotNavigationGraph.Edge edge) {
        if (edge.type != BotNavigationGraph.EdgeType.CLIMB) {
            return false;
        }
        BotNavigationGraph.Region from = graph.getRegion(edge.fromRegionId);
        BotNavigationGraph.Region to = graph.getRegion(edge.toRegionId);
        return (from == null || to == null || from.isRopeRegion || !to.isRopeRegion) ? false : true;
    }

    static boolean isTopStepOffExit(Rope rope, Point botPos, BotNavigationGraph.Edge edge) {
        return rope != null && botPos != null && edge != null && edge.launchStepX == 0 && edge.startPoint.y == rope.topY() && Math.abs(edge.endPoint.y - rope.topY()) <= BotMovementManager.cfg.JUMP_Y_THRESH * 2 && botPos.y <= rope.topY() + (BotMovementManager.cfg.JUMP_Y_THRESH * 2);
    }

    private static Rope findRopeForRegion(MapleMap map, BotNavigationGraph.Region region) {
        return BotNavigationGraphProvider.findRopeFromRegion(map, region);
    }
}
