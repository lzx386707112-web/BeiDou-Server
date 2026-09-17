package soloMapling.ArtificialPlayer.GCMoveSystem;

import io.netty.buffer.Unpooled;
import java.awt.Point;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import org.gms.client.Character;
import org.gms.net.packet.ByteBufInPacket;
import org.gms.net.packet.Packet;
import org.gms.server.maps.Foothold;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Rope;
import soloMapling.ArtificialPlayer.BotAttackSystem.BotAttackData;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationGraph;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotPhysicsEngine;
import org.gms.util.PacketCreator;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotMovementManager.class */
class BotMovementManager {
    static Config cfg = bindConfig(new Config());

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotMovementManager$ActionType.class */
    enum ActionType {
        IDLE,
        WALK,
        CROUCH,
        JUMP,
        CLIMB_UP,
        CLIMB_DOWN
    }

    BotMovementManager() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotMovementManager$MoveAction.class */
    static final class MoveAction {
        private final ActionType type;
        private final int stepX;
        private static final MoveAction IDLE = new MoveAction(ActionType.IDLE, 0);
        private static final MoveAction CROUCH = new MoveAction(ActionType.CROUCH, 0);
        private static final MoveAction CLIMB_UP = new MoveAction(ActionType.CLIMB_UP, 0);
        private static final MoveAction CLIMB_DOWN = new MoveAction(ActionType.CLIMB_DOWN, 0);

        MoveAction(ActionType type, int stepX) {
            this.type = type;
            this.stepX = stepX;
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

        public ActionType type() {
            return this.type;
        }

        public int stepX() {
            return this.stepX;
        }

        static MoveAction idle() {
            return IDLE;
        }

        static MoveAction walk(int stepX) {
            return new MoveAction(ActionType.WALK, stepX);
        }

        static MoveAction crouch() {
            return CROUCH;
        }

        static MoveAction jump(int stepX) {
            return new MoveAction(ActionType.JUMP, stepX);
        }

        static MoveAction climbUp() {
            return CLIMB_UP;
        }

        static MoveAction climbDown() {
            return CLIMB_DOWN;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotMovementManager$JumpLanding.class */
    static final class JumpLanding {
        private final Point point;
        private final Foothold foothold;

        JumpLanding(Point point, Foothold foothold) {
            this.point = point;
            this.foothold = foothold;
        }

        Point point() {
            return this.point;
        }

        Foothold foothold() {
            return this.foothold;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotMovementManager$Config.class */
    static class Config extends BotPhysicsEngine.Config {
        public int STOP_DIST = 30;
        public int FOLLOW_DIST = 80;
        public int GRIND_EDGE_MARGIN = 40;
        public int MOB_AVOID_LOOKAHEAD_STEPS = 3;
        public double MOB_AVOID_REACTION_CHANCE = 0.6d;
        public int JUMP_Y_THRESH = 30;
        public int TELEPORT_DIST = 8000;
        public int OOB_TELEPORT_DIST = 600;
        public int FOLLOW_Y_CAP = 200;

        Config() {
        }
    }

    private static Config bindConfig(Config config) {
        BotPhysicsEngine.cfg = config;
        return config;
    }

    static int tickDown(int remainingMs) {
        if (remainingMs <= 0) {
            return 0;
        }
        return Math.max(0, remainingMs - BotPhysicsEngine.cfg.TICK_MS);
    }

    static int delayAfterCurrentTick(int durationMs) {
        if (durationMs <= 0) {
            return 0;
        }
        return Math.max(0, durationMs - BotPhysicsEngine.cfg.TICK_MS);
    }

    static int walkStep(MapleMap map) {
        return BotPhysicsEngine.walkStep(map);
    }

    static int walkStep(MapleMap map, BotMovementProfile profile) {
        return BotPhysicsEngine.walkStep(map, profile);
    }

    static int velocityFromDeltaX(double deltaX) {
        return BotPhysicsEngine.velocityFromDeltaX(deltaX);
    }

    static void stopGroundMotion(BotMovementState entry) {
        BotPhysicsEngine.stopGroundMotion(entry);
    }

    static JumpLanding simulateJumpLanding(MapleMap map, Point from, int stepX) {
        return wrapLanding(BotPhysicsEngine.simulateJumpLanding(map, from, stepX));
    }

    static JumpLanding simulateJumpLanding(MapleMap map, Point from, int stepX, BotMovementProfile profile) {
        return wrapLanding(BotPhysicsEngine.simulateJumpLanding(map, from, stepX, profile));
    }

    static JumpLanding simulateRopeJumpLanding(MapleMap map, Point from, int stepX) {
        return wrapLanding(BotPhysicsEngine.simulateRopeJumpLanding(map, from, stepX));
    }

    static JumpLanding simulateRopeJumpLanding(MapleMap map, Point from, int stepX, BotMovementProfile profile) {
        return wrapLanding(BotPhysicsEngine.simulateRopeJumpLanding(map, from, stepX, profile));
    }

    static boolean canReachRopeFromGround(MapleMap map, Point from, Rope rope) {
        return BotPhysicsEngine.canReachRopeFromGround(map, from, rope);
    }

    static boolean canReachRopeFromGround(MapleMap map, Point from, Rope rope, BotMovementProfile profile) {
        return BotPhysicsEngine.canReachRopeFromGround(map, from, rope, profile);
    }

    static boolean refreshMovementProfile(BotMovementState entry) {
        BotMovementProfile updated = BotMovementProfile.fromCharacter(entry.bot);
        if (updated.equals(entry.movementProfile)) {
            return false;
        }
        MapleMap map = entry.bot != null ? entry.bot.getMap() : null;
        if (map != null && map.getFootholds() != null && BotNavigationGraphProvider.peekGraph(map, updated) == null) {
            BotNavigationGraphProvider.warmGraphAsync(map, updated);
        }
        entry.movementProfile = updated;
        clearNavigationState(entry);
        return true;
    }

    static void resetEntryState(BotMovementState entry) {
        BotPhysicsEngine.resetMotion(entry, entry.bot.getPosition());
        clearTransientState(entry);
    }

    static void resetEntryStateAfterTeleport(BotMovementState entry) {
        clearTransientState(entry);
    }

    private static void clearTransientState(BotMovementState entry) {
        entry.attackCooldownMs = 0;
        entry.graphWarmupFallback = false;
        entry.observedOwnerStepX = 0;
        entry.observedOwnerStepY = 0;
        clearNavigationState(entry);
        entry.movementBroadcastValid = false;
    }

    static void clearNavigationState(BotMovementState entry) {
        entry.navTargetPos = null;
        entry.navEdge = null;
        entry.navJumpLaunchEdge = null;
        entry.navJumpLaunchX = Integer.MIN_VALUE;
        entry.navJumpLaunchDelaySteps = Integer.MIN_VALUE;
        entry.navTargetRegionId = -1;
        entry.navPreciseTarget = false;
        entry.navBlockedPosTicks = 0;
    }

    static void tickClimbing(BotMovementState entry, Point targetPos, boolean runAiTick) {
        long startedAt = System.nanoTime();
        try {
            Character bot = entry.bot;
            BotPhysicsEngine.tickMotionTimers(entry);
            Point botPos = bot.getPosition();
            int dy = targetPos.y - botPos.y;
            int dxOwner = targetPos.x - entry.climbRope.x();
            if (runAiTick && entry.navEdge == null && Math.abs(dxOwner) > cfg.FOLLOW_DIST && entry.climbRope.bottomY() < targetPos.y) {
                jumpOffRope(entry, bot, dxOwner);
                BotPerformanceMonitor.record("move-climb", System.nanoTime() - startedAt);
                return;
            }
            boolean climbIdle = shouldHoldClimbIdle(entry, dy, dxOwner);
            if (climbIdle) {
                BotPhysicsEngine.holdClimb(entry, bot);
                broadcastMovement(entry);
                BotPerformanceMonitor.record("move-climb", System.nanoTime() - startedAt);
                return;
            }
            if (shouldSnapToClimbTarget(entry, targetPos, dy)) {
                BotPhysicsEngine.attachToRope(entry, bot, entry.climbRope, targetPos.y);
                broadcastMovement(entry);
                BotPerformanceMonitor.record("move-climb", System.nanoTime() - startedAt);
            } else if (runAiTick || entry.navEdge != null) {
                MoveAction action = dy < 0 ? MoveAction.climbUp() : dy > 0 ? MoveAction.climbDown() : MoveAction.idle();
                applyClimbAction(entry, bot, action);
                BotPerformanceMonitor.record("move-climb", System.nanoTime() - startedAt);
            } else {
                if (entry.climbVerticalDir == 0) {
                    BotPhysicsEngine.holdClimb(entry, bot);
                } else {
                    BotPhysicsEngine.advanceClimb(entry, bot);
                }
                broadcastMovement(entry);
                BotPerformanceMonitor.record("move-climb", System.nanoTime() - startedAt);
            }
        } catch (Throwable th) {
            BotPerformanceMonitor.record("move-climb", System.nanoTime() - startedAt);
            throw th;
        }
    }

    static void jumpOffRope(BotMovementState entry, Character bot, int dx) {
        int airVelX = resolveAirVelocityX(entry, bot.getMap(), entry.movementProfile, dx);
        BotPhysicsEngine.beginJumpOffRope(entry, bot, airVelX);
        broadcastMovement(entry);
    }

    static void jumpToRope(BotMovementState entry, Character bot, int dx) {
        Rope sourceRope = entry.climbRope;
        int airVelX = resolveAirVelocityX(entry, bot.getMap(), entry.movementProfile, dx);
        BotPhysicsEngine.beginRopeTransferJump(entry, bot, sourceRope, airVelX);
        broadcastMovement(entry);
    }

    private static void applyClimbAction(BotMovementState entry, Character bot, MoveAction action) {
        int i;
        switch (action.type().ordinal()) {
            case BotAttackData.DEFAULT_ATTACK_SPEED /* 4 */:
                i = -1;
                break;
            case 5:
                i = 1;
                break;
            default:
                i = 0;
                break;
        }
        entry.climbVerticalDir = i;
        if (entry.climbVerticalDir == 0) {
            BotPhysicsEngine.holdClimb(entry, bot);
        } else {
            BotPhysicsEngine.advanceClimb(entry, bot);
        }
        broadcastMovement(entry);
    }

    static boolean shouldHoldClimbIdle(BotMovementState entry, int dy, int dxOwner) {
        if (entry.navEdge != null) {
            return false;
        }
        if (entry.resting) {
            return true;
        }
        return !entry.grinding && Math.abs(dy) < cfg.STOP_DIST && Math.abs(dxOwner) < cfg.FOLLOW_DIST * 2;
    }

    static boolean shouldSnapToClimbTarget(BotMovementState entry, Point targetPos, int dy) {
        return entry != null && entry.climbing && entry.climbRope != null && targetPos != null && dy != 0 && entry.navPreciseTarget && targetPos.x == entry.climbRope.x() && targetPos.y > entry.climbRope.topY() && targetPos.y <= entry.climbRope.bottomY() && Math.abs(dy) < BotPhysicsEngine.climbStepPerTick();
    }

    static void tickAirborne(BotMovementState entry, Point targetPos) {
        long startedAt = System.nanoTime();
        try {
            entry.swimming = false;
            BotPhysicsEngine.tickMotionTimers(entry);
            Character bot = entry.bot;
            Point botPos = bot.getPosition();
            if (successfullyGrabbedRope(entry, bot, botPos)) {
                return;
            }
            if (entry.moveDir == 0) {
                if (!shouldApplyAirSteering(entry)) {
                    entry.moveDir = Integer.signum(entry.airVelX);
                } else if (targetPos != null) {
                    int dx = targetPos.x - botPos.x;
                    entry.moveDir = Math.abs(dx) > BotPhysicsEngine.cfg.SWIM_ARRIVAL_RADIUS_PX ? Integer.signum(dx) : 0;
                }
            }
            BotPhysicsEngine.AirborneStepResult result = BotPhysicsEngine.stepAirborne(entry, bot);
            if (result == BotPhysicsEngine.AirborneStepResult.WALL) {
                if (successfullyGrabbedRope(entry, bot, bot.getPosition())) {
                    BotPerformanceMonitor.record("move-air", System.nanoTime() - startedAt);
                    return;
                } else {
                    broadcastMovement(entry);
                    BotPerformanceMonitor.record("move-air", System.nanoTime() - startedAt);
                    return;
                }
            }
            if (result == BotPhysicsEngine.AirborneStepResult.CEILING) {
                broadcastMovement(entry);
                BotPerformanceMonitor.record("move-air", System.nanoTime() - startedAt);
                return;
            }
            if (result == BotPhysicsEngine.AirborneStepResult.LANDED) {
                entry.jumpCooldownMs = 0;
                broadcastMovement(entry);
                BotPerformanceMonitor.record("move-air", System.nanoTime() - startedAt);
            } else {
                if (successfullyGrabbedRope(entry, bot, bot.getPosition())) {
                    BotPerformanceMonitor.record("move-air", System.nanoTime() - startedAt);
                    return;
                }
                if (entry.flashJumpFired) {
                    Point now = bot.getPosition();
                    broadcastFlashJump(entry, now.x - botPos.x, now.y - botPos.y);
                    entry.flashJumpFired = false;
                } else {
                    broadcastMovement(entry);
                }
                BotPerformanceMonitor.record("move-air", System.nanoTime() - startedAt);
            }
        } finally {
            BotPerformanceMonitor.record("move-air", System.nanoTime() - startedAt);
        }
    }

    private static boolean successfullyGrabbedRope(BotMovementState entry, Character bot, Point botPos) {
        if (!entry.climbUpIntent) {
            return false;
        }
        for (Rope rope : bot.getMap().getRopes()) {
            if (!sameRope(entry.blockedRopeGrab, rope) && Math.abs(rope.x() - botPos.x) <= BotPhysicsEngine.cfg.ROPE_GRAB_X && botPos.y >= rope.topY() && botPos.y <= rope.bottomY() + 2) {
                BotPhysicsEngine.attachToRope(entry, bot, rope, botPos.y);
                broadcastMovement(entry);
                return true;
            }
        }
        return false;
    }

    static boolean sameRope(Rope left, Rope right) {
        return left != null && right != null && left.x() == right.x() && left.topY() == right.topY() && left.bottomY() == right.bottomY() && left.isLadder() == right.isLadder();
    }

    private static boolean shouldApplyAirSteering(BotMovementState entry) {
        if (entry.fixedAirArc || entry.downJumpGracePeriodMS != 0) {
            return false;
        }
        if (entry.navEdge == null) {
            return true;
        }
        return (entry.navEdge.type == BotNavigationGraph.EdgeType.JUMP || entry.navEdge.type == BotNavigationGraph.EdgeType.DROP || (entry.navEdge.type == BotNavigationGraph.EdgeType.CLIMB && entry.navEdge.launchStepX != 0)) ? false : true;
    }

    static void tickSwimming(BotMovementState entry, Point targetPos) {
        long startedAt = System.nanoTime();
        try {
            BotPhysicsEngine.tickMotionTimers(entry);
            computeSwimIntents(entry, targetPos);
            BotPhysicsEngine.applySwimMotion(entry);
            broadcastMovement(entry);
            BotPerformanceMonitor.record("move-swim", System.nanoTime() - startedAt);
        } catch (Throwable th) {
            BotPerformanceMonitor.record("move-swim", System.nanoTime() - startedAt);
            throw th;
        }
    }

    private static void computeSwimIntents(BotMovementState entry, Point targetPos) {
        int prevVerticalHold = entry.swimVerticalHold;
        entry.swimMoveDir = 0;
        entry.swimVerticalHold = 0;
        entry.swimJumpRequested = false;
        if (entry.attackCooldownMs > 0) {
            return;
        }
        if (targetPos == null) {
            entry.swimVerticalHold = -1;
            return;
        }
        Point pos = entry.bot.getPosition();
        int dx = targetPos.x - pos.x;
        int dy = targetPos.y - pos.y;
        int hRadius = BotPhysicsEngine.cfg.SWIM_ARRIVAL_RADIUS_PX;
        if (dx > hRadius) {
            entry.swimMoveDir = 1;
        } else if (dx < (-hRadius)) {
            entry.swimMoveDir = -1;
        }
        int levelBand = BotPhysicsEngine.cfg.SWIM_LEVEL_BAND_PX;
        if (Math.abs(dx) <= hRadius && Math.abs(dy) <= levelBand) {
            entry.swimMoveDir = 0;
            entry.swimVerticalHold = -1;
            return;
        }
        long now = System.currentTimeMillis();
        int jumpTrigger = BotPhysicsEngine.cfg.SWIM_JUMP_TRIGGER_DY_PX;
        int downBand = BotPhysicsEngine.cfg.SWIM_DOWN_BAND_PX;
        if (dy <= (-jumpTrigger) && now >= entry.swimNextJumpAtMs) {
            entry.swimJumpRequested = true;
            entry.swimNextJumpAtMs = now + BotPhysicsEngine.cfg.SWIM_JUMP_COOLDOWN_MS;
            entry.swimVerticalHold = -1;
        } else if (dy <= levelBand) {
            entry.swimVerticalHold = -1;
        } else if (dy > downBand) {
            entry.swimVerticalHold = 1;
        } else {
            entry.swimVerticalHold = prevVerticalHold > 0 ? 1 : 0;
        }
    }

    static void tickGrounded(BotMovementState entry, Point targetPos) {
        long startedAt = System.nanoTime();
        try {
            entry.swimming = false;
            Character bot = entry.bot;
            BotPhysicsEngine.tickMotionTimers(entry);
            Foothold currentFh = BotPhysicsEngine.syncAndDetectGround(entry, bot);
            if (currentFh == null) {
                broadcastMovement(entry);
                BotPerformanceMonitor.record("move-ground", System.nanoTime() - startedAt);
                return;
            }
            Point botPos = bot.getPosition();
            if (entry.ropeEntryPending) {
                performTopRopeEntry(entry);
                BotPerformanceMonitor.record("move-ground", System.nanoTime() - startedAt);
                return;
            }
            if (entry.downJumpPending) {
                performDownJump(entry);
                BotPerformanceMonitor.record("move-ground", System.nanoTime() - startedAt);
                return;
            }
            Point targetPos2 = adjustGrindingTargetPosition(entry, currentFh, targetPos);
            if (entry.graphWarmupFallback && targetPos2 != null) {
                if (BotFallbackMovementManager.tryImmediateAction(entry, botPos, targetPos2)) {
                    return;
                } else {
                    targetPos2 = BotFallbackMovementManager.resolveSteeringTarget(entry, botPos, targetPos2);
                }
            }
            MoveAction action = planGroundAction(entry, currentFh, botPos, targetPos2);
            applyGroundAction(entry, currentFh, action);
            BotPerformanceMonitor.record("move-ground", System.nanoTime() - startedAt);
        } finally {
            BotPerformanceMonitor.record("move-ground", System.nanoTime() - startedAt);
        }
    }

    static int preciseNavStopDist(BotNavigationGraph.Edge navEdge) {
        if (navEdge != null) {
            if (navEdge.type == BotNavigationGraph.EdgeType.JUMP) {
                return 0;
            }
            if (navEdge.type == BotNavigationGraph.EdgeType.DROP && navEdge.launchStepX == 0) {
                return 0;
            }
        }
        if (navEdge != null && navEdge.type != BotNavigationGraph.EdgeType.WALK) {
            return 1;
        }
        return 4;
    }

    static Point adjustGrindingTargetPosition(BotMovementState entry, Foothold currentFh, Point targetPos) {
        if (!entry.grinding || entry.navEdge != null || currentFh == null || targetPos == null) {
            return targetPos;
        }
        MapleMap map = entry.bot.getMap();
        BotNavigationGraph graph = BotNavigationGraphProvider.peekGraph(map, entry.movementProfile);
        if (graph == null) {
            BotNavigationGraphProvider.warmGraphAsync(map, entry.movementProfile);
            return targetPos;
        }
        Point botPos = entry.bot.getPosition();
        int currentRegionId = BotNavigationManager.resolveCurrentRegionId(graph, entry, map, botPos);
        int targetRegionId = BotNavigationManager.resolveTargetRegionId(graph, entry, map, targetPos);
        if (currentRegionId < 0 || currentRegionId != targetRegionId) {
            return targetPos;
        }
        BotNavigationGraph.Region currentRegion = graph.getRegion(currentRegionId);
        if (currentRegion == null || currentRegion.isRopeRegion) {
            return targetPos;
        }
        int safeLeft = currentRegion.minX + cfg.GRIND_EDGE_MARGIN;
        int safeRight = currentRegion.maxX - cfg.GRIND_EDGE_MARGIN;
        if (safeLeft >= safeRight) {
            return targetPos;
        }
        int clampedX = Math.max(safeLeft, Math.min(safeRight, targetPos.x));
        return currentRegion.pointAt(clampedX);
    }

    private static MoveAction planGroundAction(BotMovementState entry, Foothold currentFh, Point botPos, Point targetPos) {
        int i;
        boolean directionalDrop = isDirectionalDropEdge(entry.navEdge);
        int stopDist = directionalDrop ? 0 : entry.navPreciseTarget ? preciseNavStopDist(entry.navEdge) : cfg.STOP_DIST;
        if (directionalDrop) {
            i = 0;
        } else {
            i = (entry.navEdge != null || entry.navPreciseTarget) ? stopDist : cfg.FOLLOW_DIST;
        }
        int followDist = i;
        int stepX = resolveGroundStepX(entry, botPos, targetPos, stopDist, followDist);
        if (stepX == 0) {
            return MoveAction.idle();
        }
        boolean canWalkStep = BotPhysicsEngine.canWalkGroundStep(entry.bot.getMap(), botPos, stepX);
        if (!canWalkStep) {
            boolean blockedByWall = BotPhysicsEngine.isGroundStepBlockedByWall(entry.bot.getMap(), botPos, stepX);
            if (!blockedByWall && ((directionalDrop && Integer.signum(stepX) == Integer.signum(entry.navEdge.launchStepX)) || BotFallbackMovementManager.shouldWalkOffLedge(entry, botPos, targetPos, stepX))) {
                return MoveAction.walk(stepX);
            }
            if (blockedByWall && entry.navEdge != null) {
                clearNavigationState(entry);
            } else if (entry.navEdge != null && entry.navEdge.type == BotNavigationGraph.EdgeType.WALK) {
                clearNavigationState(entry);
            }
            return MoveAction.idle();
        }
        return MoveAction.walk(stepX);
    }

    private static boolean isDirectionalDropEdge(BotNavigationGraph.Edge navEdge) {
        return (navEdge == null || navEdge.type != BotNavigationGraph.EdgeType.DROP || navEdge.launchStepX == 0) ? false : true;
    }

    static int resolveGroundStepX(BotMovementState entry, Point botPos, Point targetPos, int stopDist, int followDist) {
        if (entry == null || entry.bot == null || botPos == null || targetPos == null) {
            return 0;
        }
        if (entry.graphWarmupFallback) {
            int localStopDist = Math.min(stopDist, 12);
            return updateStepX(entry, entry.bot.getMap(), botPos.x, targetPos.x, localStopDist, localStopDist);
        }
        return updateStepX(entry, entry.bot.getMap(), botPos.x, targetPos.x, stopDist, followDist);
    }

    private static void applyGroundAction(BotMovementState entry, Foothold currentFh, MoveAction action) {
        int iCompare;
        Character bot = entry.bot;
        switch (action.type().ordinal()) {
            case 1:
            case 3:
                iCompare = Integer.compare(action.stepX(), 0);
                break;
            default:
                iCompare = 0;
                break;
        }
        entry.moveDir = iCompare;
        if (action.type() == ActionType.CROUCH) {
            BotPhysicsEngine.queueDownJump(entry, bot);
            broadcastMovement(entry);
            return;
        }
        if (action.type() == ActionType.JUMP) {
            initiateFixedArcJump(entry, bot, action.stepX());
            return;
        }
        BotPhysicsEngine.GroundMotion motion = BotPhysicsEngine.applyGroundMotion(entry, bot, currentFh);
        if (motion.lostGround()) {
            broadcastMovement(entry);
        } else if (motion.stepX() == 0) {
            applyIdleOrInPlaceMotion(entry, action);
        } else {
            broadcastMovement(entry);
        }
    }

    private static void applyIdleOrInPlaceMotion(BotMovementState entry, MoveAction action) {
        if (entry.movementVelX == 0 && action.type() == ActionType.IDLE) {
            BotPhysicsEngine.idleOnGround(entry, entry.bot);
        }
        broadcastMovement(entry);
    }

    private static void performDownJump(BotMovementState entry) {
        BotPhysicsEngine.beginDownJump(entry, entry.bot);
        broadcastMovement(entry);
    }

    private static void performTopRopeEntry(BotMovementState entry) {
        BotPhysicsEngine.beginTopRopeEntry(entry, entry.bot);
        broadcastMovement(entry);
    }

    static int calcStepX(MapleMap map, int botX, int targetX, boolean wasMovingX) {
        return calcStepX(map, BotMovementProfile.base(), botX, targetX, wasMovingX, cfg.STOP_DIST, cfg.FOLLOW_DIST);
    }

    static int calcStepX(MapleMap map, int botX, int targetX, boolean wasMovingX, int stopDist, int followDist) {
        return calcStepX(map, BotMovementProfile.base(), botX, targetX, wasMovingX, stopDist, followDist);
    }

    static int calcStepX(MapleMap map, BotMovementProfile profile, int botX, int targetX, boolean wasMovingX, int stopDist, int followDist) {
        int dx = targetX - botX;
        int absDx = Math.abs(dx);
        if (absDx <= stopDist) {
            return 0;
        }
        if (wasMovingX || absDx > followDist) {
            return Math.min(absDx, BotPhysicsEngine.walkStep(map, profile)) * (dx >= 0 ? 1 : -1);
        }
        return 0;
    }

    static int updateStepX(BotMovementState entry, MapleMap map, int botX, int targetX) {
        return updateStepX(entry, map, botX, targetX, cfg.STOP_DIST, cfg.FOLLOW_DIST);
    }

    static int updateStepX(BotMovementState entry, MapleMap map, int botX, int targetX, int stopDist, int followDist) {
        int stepX = calcStepX(map, entry.movementProfile, botX, targetX, entry.wasMovingX, stopDist, followDist);
        if (stepX == 0) {
            entry.wasMovingX = false;
            return 0;
        }
        entry.wasMovingX = true;
        if (isDirectionalDropEdge(entry.navEdge)) {
            return stepX;
        }
        int approachDir = BotPhysicsEngine.slipperyApproachDir(map, entry.movementProfile, entry.hspeed, targetX - botX, launchWindowOvershootSlackPx(entry, botX, targetX));
        return approachDir == Integer.signum(stepX) ? stepX : approachDir;
    }

    private static int launchWindowOvershootSlackPx(BotMovementState entry, int botX, int targetX) {
        int dir;
        BotNavigationGraph.Edge edge = entry.navEdge;
        if (edge == null) {
            return 0;
        }
        boolean windowed = edge.type == BotNavigationGraph.EdgeType.JUMP || (edge.type == BotNavigationGraph.EdgeType.DROP && edge.launchStepX == 0);
        if (!windowed || !edge.containsLaunchX(targetX) || (dir = Integer.signum(targetX - botX)) == 0) {
            return 0;
        }
        int slack = dir > 0 ? edge.launchMaxX - targetX : targetX - edge.launchMinX;
        return Math.clamp(slack, 0, BotPhysicsEngine.walkStep(entry.bot.getMap(), entry.movementProfile));
    }

    static void initiateJump(BotMovementState entry, Character bot, int dx) {
        BotPhysicsEngine.beginGroundJump(entry, bot, resolveAirVelocityX(entry, bot.getMap(), entry.movementProfile, dx));
        broadcastMovement(entry);
    }

    private static void initiateFixedArcJump(BotMovementState entry, Character bot, int dx) {
        initiateJump(entry, bot, dx);
        entry.fixedAirArc = true;
    }

    static void tickUnstuck(BotMovementState entry) {
        Character bot = entry.bot;
        int walkStep = BotPhysicsEngine.walkStep(bot.getMap(), entry.movementProfile);
        switch (ThreadLocalRandom.current().nextInt(2)) {
            case BotAttackData.FACING_RIGHT_MASK /* 0 */:
                BotPhysicsEngine.beginGroundJump(entry, bot, -walkStep);
                break;
            default:
                BotPhysicsEngine.beginGroundJump(entry, bot, walkStep);
                break;
        }
        clearNavigationState(entry);
        entry.unstuckCooldownMs = delayAfterCurrentTick(5000);
        broadcastMovement(entry);
    }

    static void initiateRopeJump(BotMovementState entry, Character bot, int dx) {
        BotPhysicsEngine.beginClimbUpJump(entry, bot, resolveAirVelocityX(entry, bot.getMap(), entry.movementProfile, dx));
        broadcastMovement(entry);
    }

    private static int resolveAirVelocityX(BotMovementState entry, MapleMap map, BotMovementProfile profile, int dx) {
        if (dx == 0) {
            if (entry != null && BotPhysicsEngine.slipperyGround(map) && !entry.climbing) {
                return BotPhysicsEngine.carriedAirVelX(map, entry);
            }
            return 0;
        }
        int walkStep = BotPhysicsEngine.walkStep(map, profile);
        return dx > 0 ? walkStep : -walkStep;
    }

    static void broadcastMovement(BotMovementState entry) {
        if (!BotPerformanceMonitor.enabled()) {
            doBroadcastMovement(entry);
            return;
        }
        long startedAt = System.nanoTime();
        try {
            doBroadcastMovement(entry);
            BotPerformanceMonitor.record("broadcast-move", System.nanoTime() - startedAt);
        } catch (Throwable th) {
            BotPerformanceMonitor.record("broadcast-move", System.nanoTime() - startedAt);
            throw th;
        }
    }

    private static void doBroadcastMovement(BotMovementState entry) {
        Character bot = entry.bot;
        if (!ObserverTracker.isActiveMap(bot.getMapId())) {
            entry.movementBroadcastValid = false;
            return;
        }
        int x = bot.getPosition().x;
        int y = bot.getPosition().y;
        BotPhysicsEngine.MovementSnapshot snapshot = BotPhysicsEngine.movementSnapshot(entry);
        int fhId = resolveBroadcastFhId(entry, bot);
        if (entry.movementBroadcastValid && entry.lastBroadcastX == x && entry.lastBroadcastY == y && entry.lastBroadcastVelX == snapshot.velX() && entry.lastBroadcastVelY == snapshot.velY() && entry.lastBroadcastStance == snapshot.stance() && entry.lastBroadcastFh == fhId) {
            return;
        }
        entry.movementBroadcastValid = true;
        entry.lastBroadcastX = x;
        entry.lastBroadcastY = y;
        entry.lastBroadcastVelX = snapshot.velX();
        entry.lastBroadcastVelY = snapshot.velY();
        entry.lastBroadcastStance = snapshot.stance();
        entry.lastBroadcastFh = fhId;
        sendMovementPacket(bot, snapshot, fhId);
    }

    private static int resolveBroadcastFhId(BotMovementState entry, Character bot) {
        Foothold fh = BotPhysicsEngine.findGroundFoothold(bot.getMap(), bot.getPosition());
        if (fh != null) {
            entry.lastGroundFhId = fh.getId();
        }
        return entry.lastGroundFhId;
    }

    private static void sendMovementPacket(Character bot, BotPhysicsEngine.MovementSnapshot snapshot, int fhId) {
        int x = bot.getPosition().x;
        int y = bot.getPosition().y;
        byte[] data = {1, 0, (byte) (x & 255), (byte) (x >> 8), (byte) (y & 255), (byte) (y >> 8), (byte) (snapshot.velX() & 255), (byte) (snapshot.velX() >> 8), (byte) (snapshot.velY() & 255), (byte) (snapshot.velY() >> 8), (byte) (fhId & 255), (byte) (fhId >> 8), (byte) snapshot.stance(), (byte) (BotPhysicsEngine.cfg.TICK_MS & 255), (byte) (BotPhysicsEngine.cfg.TICK_MS >> 8)};
        Packet movePacket = PacketCreator.movePlayer(bot.getId(), new ByteBufInPacket(Unpooled.wrappedBuffer(data)), data.length);
        bot.getMap().broadcastMessage(bot, movePacket, false);
    }

    static void broadcastRawMovement(Character bot, byte[] data) {
        if (bot == null || bot.getMap() == null) {
            return;
        }
        Packet movePacket = PacketCreator.movePlayer(bot.getId(), new ByteBufInPacket(Unpooled.wrappedBuffer(data)), data.length);
        bot.getMap().broadcastMessage(bot, movePacket, false);
    }

    static void broadcastFlashJump(BotMovementState entry, int relDx, int relDy) {
        Character bot = entry.bot;
        if (bot == null || bot.getMap() == null) {
            return;
        }
        if (!ObserverTracker.isActiveMap(bot.getMapId())) {
            broadcastMovement(entry);
            return;
        }
        BotPhysicsEngine.MovementSnapshot snapshot = BotPhysicsEngine.movementSnapshot(entry);
        int stance = snapshot.stance();
        int fhId = resolveBroadcastFhId(entry, bot);
        int x = bot.getPosition().x;
        int y = bot.getPosition().y;
        int dur = BotPhysicsEngine.cfg.TICK_MS;
        byte[] data = new byte[23];
        int i = 0 + 1;
        data[0] = 2;
        int i2 = i + 1;
        data[i] = 0;
        int i3 = i2 + 1;
        data[i2] = (byte) (x & 255);
        int i4 = i3 + 1;
        data[i3] = (byte) (x >> 8);
        int i5 = i4 + 1;
        data[i4] = (byte) (y & 255);
        int i6 = i5 + 1;
        data[i5] = (byte) (y >> 8);
        int i7 = i6 + 1;
        data[i6] = (byte) (snapshot.velX() & 255);
        int i8 = i7 + 1;
        data[i7] = (byte) (snapshot.velX() >> 8);
        int i9 = i8 + 1;
        data[i8] = (byte) (snapshot.velY() & 255);
        int i10 = i9 + 1;
        data[i9] = (byte) (snapshot.velY() >> 8);
        int i11 = i10 + 1;
        data[i10] = (byte) (fhId & 255);
        int i12 = i11 + 1;
        data[i11] = (byte) (fhId >> 8);
        int i13 = i12 + 1;
        data[i12] = (byte) stance;
        int i14 = i13 + 1;
        data[i13] = (byte) (dur & 255);
        int i15 = i14 + 1;
        data[i14] = (byte) (dur >> 8);
        int i16 = i15 + 1;
        data[i15] = 6;
        int i17 = i16 + 1;
        data[i16] = (byte) (relDx & 255);
        int i18 = i17 + 1;
        data[i17] = (byte) (relDx >> 8);
        int i19 = i18 + 1;
        data[i18] = (byte) (relDy & 255);
        int i20 = i19 + 1;
        data[i19] = (byte) (relDy >> 8);
        int i21 = i20 + 1;
        data[i20] = (byte) stance;
        data[i21] = 0;
        data[i21 + 1] = 0;
        Packet movePacket = PacketCreator.movePlayer(bot.getId(), new ByteBufInPacket(Unpooled.wrappedBuffer(data)), data.length);
        bot.getMap().broadcastMessage(bot, movePacket, false);
        entry.movementBroadcastValid = true;
        entry.lastBroadcastX = x;
        entry.lastBroadcastY = y;
        entry.lastBroadcastVelX = snapshot.velX();
        entry.lastBroadcastVelY = snapshot.velY();
        entry.lastBroadcastStance = stance;
        entry.lastBroadcastFh = fhId;
    }

    static Map<Integer, Foothold> buildFhIndex(MapleMap map) {
        Map<Integer, Foothold> index = new HashMap<>();
        for (Foothold foothold : map.getFootholds().getAllFootholds()) {
            index.put(Integer.valueOf(foothold.getId()), foothold);
        }
        return index;
    }

    private static JumpLanding wrapLanding(BotPhysicsEngine.JumpLanding landing) {
        if (landing == null) {
            return null;
        }
        return new JumpLanding(landing.point(), landing.foothold());
    }
}
