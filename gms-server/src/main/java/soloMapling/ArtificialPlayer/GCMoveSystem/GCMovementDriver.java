package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotPartySystem.BotRecruitManager;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationManager;
import soloMapling.ArtificialPlayer.GCMoveSystem.CoarseExecutor;
import soloMapling.server.BotPerfStats;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCMovementDriver.class */
final class GCMovementDriver {
    private static final int AI_TICK_MS = 100;
    private static final int UNOBSERVED_TICK_MS = 250;
    private static final int UNOBSERVED_IDLE_TICK_MS = 1000;
    private static final int COARSE_ARRIVE_PX = 12;
    private static final int ENABLE_UNSTUCK = 1;
    private static final int AIR_STUCK_RECOVER_TICKS = 30;
    private static final int FALL_RECOVER_SLACK_PX = 400;
    private static final long PORTAL_DROP_DELAY_MS = 1500;
    private static final int PORTAL_DROP_DELAY_JITTER_MS = 600;
    private static final long MOVE_NO_PROGRESS_MS = 8000;
    private static final int MOVE_PROGRESS_EPS_PX = 16;
    private static final long PROFILE_REFRESH_INTERVAL_MS = 20000;
    private static final AtomicInteger THREAD_SEQ = new AtomicInteger();
    private static final ScheduledExecutorService POOL = Executors.newScheduledThreadPool(2, r -> {
        Thread t = new Thread(r, "gcmove-tick-" + THREAD_SEQ.getAndIncrement());
        t.setDaemon(true);
        return t;
    });
    private static final int PORTAL_FLOAT_HEIGHT_PX = 60;

    private GCMovementDriver() {
    }

    static void start(BotMovementState entry) {
        stop(entry);
        entry.tickStopped = false;
        scheduleNext(entry, 0L);
    }

    static void stop(BotMovementState entry) {
        entry.tickStopped = true;
        if (entry.task != null) {
            entry.task.cancel(false);
            entry.task = null;
        }
    }

    private static void scheduleNext(BotMovementState entry, long delayMs) {
        if (entry.tickStopped) {
            return;
        }
        entry.task = POOL.schedule(() -> {
            safeTick(entry);
            scheduleNext(entry, nextDelayMs(entry));
        }, delayMs, TimeUnit.MILLISECONDS);
    }

    private static long nextDelayMs(BotMovementState entry) {
        Character bot = entry.bot;
        boolean active = bot != null && bot.getMap() != null && ObserverTracker.isActiveMap(bot.getMapId());
        if (active) {
            return BotPhysicsEngine.cfg.TICK_MS;
        }
        if (bot != null && (GCMovement.isMoving(bot) || GCMovement.isTraveling(bot) || GCMovement.isFollowing(bot) || entry.inAir)) {
            return 500L;
        }
        return 2500L;
    }

    private static void maybeRefreshProfile(BotMovementState entry) {
        long now = System.currentTimeMillis();
        if (now - entry.lastProfileRefreshMs < PROFILE_REFRESH_INTERVAL_MS) {
            return;
        }
        entry.lastProfileRefreshMs = now;
        BotMovementManager.refreshMovementProfile(entry);
    }

    private static void safeTick(BotMovementState entry) {
        try {
            BotPerfStats.MOVEMENT_TICKS.increment();
            tick(entry);
        } catch (Throwable th) {
        }
    }

    private static void tick(BotMovementState entry) {
        Character bot = entry.bot;
        if (bot == null || bot.getMap() == null) {
            stop(entry);
            return;
        }
        maybeRefreshProfile(entry);
        if (entry.lastMapId != bot.getMapId()) {
            onMapChange(entry, bot);
            return;
        }
        if (bot.getChair() > 0) {
            return;
        }
        boolean active = ObserverTracker.isActiveMap(bot.getMapId());
        if (!active && !entry.inAir && !entry.climbing && entry.moveTarget == null
                && !entry.following && !GCMovement.isTraveling(bot)) {
            return;
        }
        if (entry.resting) {
            if (entry.climbing) {
                BotPhysicsEngine.holdClimb(entry, bot);
            } else {
                BotPhysicsEngine.idleOnGround(entry, bot);
            }
            broadcastIfObserved(entry);
            return;
        }
        BotContactDamage.tickMobDamage(entry, bot);
        if (active && entry.coarseActive) {
            reconstructPhysicsFromCoarse(entry, bot);
        }
        boolean runAiTick = consumeAiTick(entry);
        if (active && runAiTick && !entry.inAir && !entry.climbing) {
            BotPlayerReaction.maybeReact(entry, bot);
        }
        if (entry.reactingUntilMs > System.currentTimeMillis()) {
            entry.moveProgressAtMs = System.currentTimeMillis();
            BotPhysicsEngine.idleOnGround(entry, bot);
            broadcastIfObserved(entry);
            return;
        }
        if (entry.portalDropAtMs > 0) {
            if (System.currentTimeMillis() < entry.portalDropAtMs) {
                BotPhysicsEngine.idleOnGround(entry, bot);
                entry.inAir = true;
                broadcastIfObserved(entry);
                return;
            } else {
                entry.portalDropAtMs = 0L;
                BotPhysicsEngine.beginPortalDrop(entry, bot, bot.getPosition());
                broadcastIfObserved(entry);
                return;
            }
        }
        if (giveUpStalledMove(entry)) {
            BotPhysicsEngine.idleOnGround(entry, bot);
            broadcastIfObserved(entry);
            return;
        }
        Point target = resolveTarget(entry, bot);
        boolean hasGoal = target != null || entry.inAir || entry.climbing || entry.navEdge != null;
        if (!hasGoal) {
            if (entry.duckUntilMs > System.currentTimeMillis()) {
                BotPhysicsEngine.proneOnGround(entry, bot);
            } else {
                BotPhysicsEngine.idleOnGround(entry, bot);
            }
            broadcastIfObserved(entry);
            return;
        }
        if (!active && tryCoarseAdvance(entry, bot, target)) {
            return;
        }
        stepMovementCore(entry, target != null ? target : bot.getPosition(), runAiTick);
    }

    private static boolean tryCoarseAdvance(BotMovementState entry, Character bot, Point target) {
        if (target == null || entry.inAir || entry.climbing) {
            return false;
        }
        if (entry.coarsePlan == null && Math.abs(bot.getPosition().x - target.x) <= COARSE_ARRIVE_PX && Math.abs(bot.getPosition().y - target.y) <= COARSE_ARRIVE_PX) {
            arriveCoarse(entry, bot, target);
            return true;
        }
        BotNavigationGraph graph = BotNavigationGraphProvider.peekBestGraph(bot.getMap(), entry.movementProfile);
        if (graph == null) {
            return false;
        }
        long now = System.currentTimeMillis();
        boolean needPlan = (entry.coarsePlan != null && entry.coarsePlanMapId == bot.getMapId() && target.equals(entry.coarsePlanTarget)) ? false : true;
        if (needPlan) {
            MovementPlan plan = MovementPlan.inMap(graph, bot.getMap(), bot.getPosition(), target);
            if (plan == null) {
                arriveCoarse(entry, bot, target);
                return true;
            }
            entry.coarsePlan = plan;
            entry.coarsePlanStartMs = now;
            entry.coarsePlanTarget = new Point(target);
            entry.coarsePlanMapId = bot.getMapId();
        }
        entry.coarseActive = true;
        CoarseExecutor.Step step = CoarseExecutor.advance(entry.coarsePlan, entry.coarsePlanStartMs, now);
        if (step.position() != null) {
            bot.setPosition(step.position());
        }
        if (step.complete()) {
            arriveCoarse(entry, bot, entry.coarsePlanTarget);
            return true;
        }
        return true;
    }

    private static void arriveCoarse(BotMovementState entry, Character bot, Point target) {
        if (target != null) {
            bot.setPosition(new Point(target));
        }
        entry.coarsePlan = null;
        entry.coarsePlanTarget = null;
        entry.moveTarget = null;
        entry.moveTargetPrecise = false;
        entry.moveBestDist = Integer.MAX_VALUE;
        BotMovementManager.clearNavigationState(entry);
        GCMovement.fireArrival(entry);
    }

    private static void reconstructPhysicsFromCoarse(BotMovementState entry, Character bot) {
        entry.coarseActive = false;
        entry.coarsePlan = null;
        entry.coarsePlanTarget = null;
        Point pos = bot.getPosition();
        Point ground = BotPhysicsEngine.findGroundPoint(bot.getMap(), new Point(pos.x, pos.y - ENABLE_UNSTUCK));
        BotPhysicsEngine.teleportTo(entry, bot, ground != null ? ground : pos);
        BotMovementManager.resetEntryStateAfterTeleport(entry);
    }

    private static boolean giveUpStalledMove(BotMovementState entry) {
        if (entry.moveTarget == null || entry.inAir || entry.climbing) {
            return false;
        }
        Point bp = entry.bot.getPosition();
        int dist = Math.abs(bp.x - entry.moveTarget.x) + Math.abs(bp.y - entry.moveTarget.y);
        long now = System.currentTimeMillis();
        if (entry.moveProgressAtMs == 0) {
            entry.moveProgressAtMs = now;
        }
        if (dist < entry.moveBestDist - MOVE_PROGRESS_EPS_PX) {
            entry.moveBestDist = dist;
            entry.moveProgressAtMs = now;
            return false;
        }
        if (now - entry.moveProgressAtMs <= MOVE_NO_PROGRESS_MS) {
            return false;
        }
        entry.moveTarget = null;
        entry.moveTargetPrecise = false;
        entry.moveBestDist = Integer.MAX_VALUE;
        BotMovementManager.clearNavigationState(entry);
        GCMovement.abandonMove(entry);
        return true;
    }

    private static Point resolveTarget(BotMovementState entry, Character bot) {
        if (entry.moveTarget != null) {
            return entry.moveTarget;
        }
        if (entry.following && entry.owner != null && entry.owner.getMap() == bot.getMap()) {
            return entry.owner.getPosition();
        }
        if (entry.farmAnchor != null) {
            return entry.farmAnchor;
        }
        return null;
    }

    private static void stepMovementCore(BotMovementState entry, Point target, boolean runAiTick) {
        BotNavigationManager.NavigationDirective nav = BotNavigationManager.resolveTarget(entry, target, runAiTick);
        if (nav.consumedTick) {
            return;
        }
        Point steering = nav.targetPos;
        if (entry.moveTargetPrecise && entry.navEdge == null) {
            entry.navPreciseTarget = true;
        }
        tickMovementPhase(entry, steering, runAiTick);
        if (runAiTick && !entry.inAir && !entry.climbing) {
            BotNavigationManager.tryExecuteCommittedEdgeAfterGroundMovement(entry, target);
        }
        tickStuckDetection(entry);
        clearReachedMoveTarget(entry);
    }

    private static void tickMovementPhase(BotMovementState entry, Point target, boolean runAiTick) {
        if (entry.climbing) {
            BotMovementManager.tickClimbing(entry, target, runAiTick);
            return;
        }
        if (isSwimMap(entry) && entry.inAir) {
            BotMovementManager.tickSwimming(entry, target);
        } else if (entry.inAir) {
            BotMovementManager.tickAirborne(entry, target);
        } else {
            BotMovementManager.tickGrounded(entry, target);
        }
    }

    private static boolean isSwimMap(BotMovementState entry) {
        return (entry.bot == null || entry.bot.getMap() == null || !entry.bot.getMap().isSwim()) ? false : true;
    }

    private static void clearReachedMoveTarget(BotMovementState entry) {
        if (entry.moveTarget == null) {
            return;
        }
        Point botPos = entry.bot.getPosition();
        int arrivalDist = entry.moveTargetPrecise ? 8 : BotMovementManager.cfg.STOP_DIST;
        if (Math.abs(botPos.x - entry.moveTarget.x) <= arrivalDist && Math.abs(botPos.y - entry.moveTarget.y) <= arrivalDist) {
            entry.moveTarget = null;
            entry.moveTargetPrecise = false;
            GCMovement.fireArrival(entry);
        }
    }

    private static boolean consumeAiTick(BotMovementState entry) {
        entry.aiTickAccumulatorMs += BotPhysicsEngine.cfg.TICK_MS;
        if (entry.aiTickAccumulatorMs < AI_TICK_MS) {
            return false;
        }
        entry.aiTickAccumulatorMs -= AI_TICK_MS;
        return true;
    }

    static void onMapChange(BotMovementState entry, Character bot) {
        entry.lastMapId = bot.getMapId();
        entry.reactingUntilMs = 0L;
        entry.coarsePlan = null;
        entry.coarsePlanTarget = null;
        entry.coarseActive = false;
        MapleMap map = bot.getMap();
        entry.fhIndex = BotMovementManager.buildFhIndex(map);
        Point spawn = bot.getPosition();
        Point ground = BotPhysicsEngine.findGroundPoint(map, new Point(spawn.x, spawn.y - ENABLE_UNSTUCK));
        BotMovementManager.resetEntryStateAfterTeleport(entry);
        boolean isCompanion = BotRecruitManager.isCompanion(bot.getId());
        if (ground != null && ObserverTracker.isActiveMap(bot.getMapId()) && !isCompanion) {
            int floatY = Math.min(spawn.y, ground.y - PORTAL_FLOAT_HEIGHT_PX);
            BotPhysicsEngine.teleportTo(entry, bot, new Point(spawn.x, floatY));
            entry.portalDropAtMs = System.currentTimeMillis() + PORTAL_DROP_DELAY_MS + ThreadLocalRandom.current().nextInt(601);
        } else {
            BotPhysicsEngine.teleportTo(entry, bot, ground != null ? ground : spawn);
            entry.portalDropAtMs = 0L;
        }
        if (ObserverTracker.isActiveMap(bot.getMapId())) {
            BotNavigationGraphProvider.warmGraphAsync(map, entry.movementProfile);
        }
        broadcastIfObserved(entry);
    }

    private static void broadcastIfObserved(BotMovementState entry) {
        if (entry.bot != null && ObserverTracker.isActiveMap(entry.bot.getMapId())) {
            BotMovementManager.broadcastMovement(entry);
        }
    }

    private static void tickStuckDetection(BotMovementState entry) {
        entry.unstuckCooldownMs = BotMovementManager.tickDown(entry.unstuckCooldownMs);
        tickFrozenAirborneWatchdog(entry);
        tickFallOffMapRecovery(entry);
        if (entry.inAir || entry.climbing || entry.graphWarmupFallback || (entry.navEdge == null && entry.moveTarget == null)) {
            entry.stuckMs = 0;
            entry.stuckCheckX = Integer.MIN_VALUE;
            return;
        }
        Point botPos = entry.bot.getPosition();
        if (entry.stuckCheckX == Integer.MIN_VALUE) {
            entry.stuckCheckX = botPos.x;
            entry.stuckCheckY = botPos.y;
            return;
        }
        boolean moved = Math.abs(botPos.x - entry.stuckCheckX) > 8 || Math.abs(botPos.y - entry.stuckCheckY) > 8;
        if (moved) {
            entry.stuckMs = 0;
            entry.stuckCheckX = botPos.x;
            entry.stuckCheckY = botPos.y;
        } else {
            entry.stuckMs += BotPhysicsEngine.cfg.TICK_MS;
        }
        if (entry.stuckMs >= 500 && entry.unstuckCooldownMs == 0) {
            entry.stuckMs = 0;
            entry.stuckCheckX = Integer.MIN_VALUE;
            BotMovementManager.tickUnstuck(entry);
        }
    }

    private static void tickFrozenAirborneWatchdog(BotMovementState entry) {
        if (!entry.inAir || entry.climbing) {
            entry.airStuckTicks = 0;
            entry.airStuckX = Integer.MIN_VALUE;
            return;
        }
        Point pos = entry.bot.getPosition();
        if (pos.x != entry.airStuckX || pos.y != entry.airStuckY) {
            entry.airStuckTicks = 0;
            entry.airStuckX = pos.x;
            entry.airStuckY = pos.y;
            return;
        }
        int i = entry.airStuckTicks + ENABLE_UNSTUCK;
        entry.airStuckTicks = i;
        if (i < AIR_STUCK_RECOVER_TICKS) {
            return;
        }
        entry.airStuckTicks = 0;
        entry.airStuckX = Integer.MIN_VALUE;
        MapleMap map = entry.bot.getMap();
        Point goal = entry.moveTarget != null ? entry.moveTarget : entry.navTargetPos;
        Point base = goal != null ? goal : pos;
        Point ground = BotPhysicsEngine.findGroundPoint(map, new Point(base.x, base.y - ENABLE_UNSTUCK));
        BotPhysicsEngine.teleportTo(entry, entry.bot, ground != null ? ground : pos);
        BotMovementManager.resetEntryStateAfterTeleport(entry);
        broadcastIfObserved(entry);
    }

    private static void tickFallOffMapRecovery(BotMovementState entry) {
        Rectangle vr;
        Point pos;
        Point point;
        Character bot = entry.bot;
        MapleMap map = bot != null ? bot.getMap() : null;
        if (map == null || (vr = map.getMapArea()) == null || vr.width <= 0 || vr.height <= 0 || (pos = bot.getPosition()) == null) {
            return;
        }
        boolean belowFloor = pos.y > (vr.y + vr.height) + FALL_RECOVER_SLACK_PX;
        boolean offSides = pos.x < vr.x - FALL_RECOVER_SLACK_PX || pos.x > (vr.x + vr.width) + FALL_RECOVER_SLACK_PX;
        if (!belowFloor && !offSides) {
            return;
        }
        Point goal = entry.moveTarget != null ? entry.moveTarget : entry.navTargetPos;
        if (goal != null) {
            point = new Point(goal.x, goal.y);
        } else {
            point = new Point(Math.max(vr.x, Math.min(vr.x + vr.width, pos.x)), vr.y);
        }
        Point base = point;
        Point ground = BotPhysicsEngine.findGroundPoint(map, new Point(base.x, base.y - ENABLE_UNSTUCK));
        BotPhysicsEngine.teleportTo(entry, bot, ground != null ? ground : base);
        BotMovementManager.resetEntryStateAfterTeleport(entry);
        entry.moveTarget = null;
        broadcastIfObserved(entry);
    }
}
