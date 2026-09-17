package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import org.gms.client.Character;
import org.gms.server.maps.Foothold;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Rope;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotPhysicsEngine;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotFallbackMovementManager.class */
final class BotFallbackMovementManager {
    private BotFallbackMovementManager() {
    }

    static Point resolveSteeringTarget(BotMovementState entry, Point botPos, Point targetPos) {
        Rope rope = selectNearbyRope(entry, botPos, targetPos);
        Point ledgeTarget = resolveFallbackLedgeTarget(entry, botPos, targetPos, rope);
        if (ledgeTarget != null) {
            return ledgeTarget;
        }
        if (rope == null) {
            return targetPos;
        }
        return new Point(rope.x(), botPos.y);
    }

    static boolean tryImmediateAction(BotMovementState entry, Point botPos, Point targetPos) {
        Character bot = entry.bot;
        MapleMap map = bot.getMap();
        Rope rope = selectNearbyRope(entry, botPos, targetPos);
        if (rope != null) {
            if (canDirectlyAttachToRope(botPos, rope)) {
                int attachY = Math.max(rope.topY(), Math.min(botPos.y, rope.bottomY()));
                BotPhysicsEngine.attachToRope(entry, bot, rope, attachY);
                BotMovementManager.broadcastMovement(entry);
                return true;
            }
            int ropeDx = rope.x() - botPos.x;
            int ropeJumpRange = Math.max(BotPhysicsEngine.cfg.ROPE_GRAB_X * 2, BotPhysicsEngine.walkStep(map, entry.movementProfile) * 2);
            if (Math.abs(ropeDx) <= ropeJumpRange && BotPhysicsEngine.canReachRopeFromGround(map, botPos, rope, entry.movementProfile)) {
                BotMovementManager.initiateRopeJump(entry, bot, ropeDx);
                return true;
            }
        }
        if (shouldJumpUpIntoSwim(entry, botPos, targetPos)) {
            BotMovementManager.initiateJump(entry, bot, 0);
            return true;
        }
        if (shouldUseDownJump(entry, botPos, targetPos, rope)) {
            BotPhysicsEngine.queueDownJump(entry, bot);
            BotMovementManager.broadcastMovement(entry);
            return true;
        }
        Point steeringTarget = rope == null ? targetPos : new Point(rope.x(), targetPos.y);
        int stepX = BotMovementManager.resolveGroundStepX(entry, botPos, steeringTarget, BotMovementManager.cfg.STOP_DIST, BotMovementManager.cfg.FOLLOW_DIST);
        if (stepX != 0 && !BotPhysicsEngine.canWalkGroundStep(map, botPos, stepX) && shouldUseJump(entry, botPos, steeringTarget, stepX)) {
            BotMovementManager.initiateJump(entry, bot, steeringTarget.x - botPos.x);
            return true;
        }
        return false;
    }

    private static boolean shouldJumpUpIntoSwim(BotMovementState entry, Point botPos, Point targetPos) {
        MapleMap map;
        if (entry == null || entry.bot == null || botPos == null || targetPos == null || entry.inAir || entry.climbing || entry.jumpCooldownMs > 0 || entry.downJumpPending || (map = entry.bot.getMap()) == null || !map.isSwim()) {
            return false;
        }
        int dy = targetPos.y - botPos.y;
        return dy < (-Math.max(BotMovementManager.cfg.JUMP_Y_THRESH * 2, 60));
    }

    static boolean shouldWalkOffLedge(BotMovementState entry, Point botPos, Point targetPos, int stepX) {
        if (entry == null || !entry.graphWarmupFallback || botPos == null || targetPos == null || stepX == 0 || targetPos.y <= botPos.y + BotPhysicsEngine.cfg.MAX_SNAP_DROP) {
            return false;
        }
        Point ahead = new Point(botPos.x + stepX, botPos.y);
        return BotPhysicsEngine.isGroundFarBelow(entry.bot.getMap(), ahead);
    }

    private static Rope selectNearbyRope(BotMovementState entry, Point botPos, Point targetPos) {
        if (entry == null || entry.bot == null || botPos == null || targetPos == null) {
            return null;
        }
        int dy = targetPos.y - botPos.y;
        if (Math.abs(dy) < Math.max(BotMovementManager.cfg.JUMP_Y_THRESH * 2, 60)) {
            return null;
        }
        MapleMap map = entry.bot.getMap();
        int walkStep = BotPhysicsEngine.walkStep(map, entry.movementProfile);
        int searchX = Math.max(walkStep * 4, 90);
        Rope best = null;
        int bestScore = Integer.MAX_VALUE;
        for (Rope rope : map.getRopes()) {
            int dx = Math.abs(rope.x() - botPos.x);
            if (dx > searchX) {
                continue;
            }
            boolean usable = dy < 0
                    ? rope.topY() < botPos.y - BotPhysicsEngine.cfg.MAX_SNAP_DROP
                    && rope.bottomY() >= botPos.y - BotPhysicsEngine.cfg.MAX_SNAP_DROP
                    && rope.topY() <= targetPos.y + BotMovementManager.cfg.FOLLOW_Y_CAP
                    : rope.bottomY() > botPos.y + BotPhysicsEngine.cfg.MAX_SNAP_DROP
                    && rope.topY() <= botPos.y + BotPhysicsEngine.cfg.MAX_SLOPE_UP
                    && rope.bottomY() >= targetPos.y - BotMovementManager.cfg.FOLLOW_Y_CAP;
            if (!usable) {
                continue;
            }
            int verticalPenalty = dy >= 0
                    ? Math.max(0, rope.topY() - targetPos.y)
                    : Math.max(0, targetPos.y - rope.bottomY());
            int score = (dx * 4) + verticalPenalty;
            if (score < bestScore) {
                best = rope;
                bestScore = score;
            }
        }
        return best;
    }

    private static boolean canDirectlyAttachToRope(Point botPos, Rope rope) {
        return botPos != null && rope != null && Math.abs(botPos.x - rope.x()) <= BotPhysicsEngine.cfg.ROPE_GRAB_X && botPos.y >= rope.topY() - BotPhysicsEngine.cfg.MAX_SNAP_DROP && botPos.y <= rope.bottomY() + BotPhysicsEngine.cfg.MAX_SNAP_DROP;
    }

    private static Point resolveFallbackLedgeTarget(BotMovementState entry, Point botPos, Point targetPos, Rope rope) {
        Foothold foothold;
        if (entry == null || entry.bot == null || botPos == null || targetPos == null || rope != null) {
            return null;
        }
        MapleMap map = entry.bot.getMap();
        if (!shouldConsiderFallbackDrop(entry, map, botPos, targetPos) || (foothold = BotPhysicsEngine.findGroundFoothold(map, botPos)) == null) {
            return null;
        }
        Point left = walkOffTarget(map, foothold, entry.movementProfile, -1);
        Point right = walkOffTarget(map, foothold, entry.movementProfile, 1);
        Point best = chooseBetterLedgeTarget(botPos, targetPos, left, right);
        if (best == null) {
            return null;
        }
        return new Point(best.x, targetPos.y);
    }

    private static boolean shouldUseDownJump(BotMovementState entry, Point botPos, Point targetPos, Rope rope) {
        boolean zCanStartDownJump;
        if (entry == null || botPos == null || targetPos == null || rope != null) {
            return false;
        }
        MapleMap map = entry.bot.getMap();
        if (!shouldConsiderFallbackDrop(entry, map, botPos, targetPos)) {
            return false;
        }
        if (map != null && map.isSwim()) {
            zCanStartDownJump = BotPhysicsEngine.canStartDownJump(map, botPos);
        } else {
            zCanStartDownJump = BotPhysicsEngine.simulateDownJumpLanding(map, botPos) != null;
        }
        boolean canDrop = zCanStartDownJump;
        return canDrop && Math.abs(targetPos.x - botPos.x) <= Math.max(BotMovementManager.cfg.FOLLOW_DIST, BotPhysicsEngine.walkStep(map, entry.movementProfile) * 4);
    }

    private static boolean shouldConsiderFallbackDrop(BotMovementState entry, MapleMap map, Point botPos, Point targetPos) {
        if (entry == null || map == null || botPos == null || targetPos == null) {
            return false;
        }
        int dy = targetPos.y - botPos.y;
        if (dy < Math.max(BotPhysicsEngine.cfg.MAX_SNAP_DROP * 3, 90)) {
            return false;
        }
        Foothold currentFoothold = BotPhysicsEngine.findGroundFoothold(map, botPos);
        Foothold targetFoothold = BotPhysicsEngine.findGroundFoothold(map, targetPos);
        return currentFoothold == null || targetFoothold == null || currentFoothold.getId() != targetFoothold.getId();
    }

    private static Point walkOffTarget(MapleMap map, Foothold foothold, BotMovementProfile profile, int direction) {
        Point point;
        if (map == null || foothold == null || direction == 0) {
            return null;
        }
        if (direction < 0) {
            point = new Point(foothold.getX1(), foothold.getY1());
        } else {
            point = new Point(foothold.getX2(), foothold.getY2());
        }
        Point endpoint = point;
        int step = direction * Math.max(1, BotPhysicsEngine.walkStep(map, profile));
        Point ahead = new Point(endpoint.x + step, endpoint.y);
        if (BotPhysicsEngine.isGroundFarBelow(map, ahead)) {
            return ahead;
        }
        return null;
    }

    private static Point chooseBetterLedgeTarget(Point botPos, Point targetPos, Point left, Point right) {
        if (left == null) {
            return right;
        }
        if (right == null) {
            return left;
        }
        int desiredDirection = Integer.compare(targetPos.x, botPos.x);
        if (desiredDirection < 0 && left.x <= botPos.x) {
            return left;
        }
        if (desiredDirection > 0 && right.x >= botPos.x) {
            return right;
        }
        int leftScore = Math.abs(targetPos.x - left.x) + Math.abs(botPos.x - left.x);
        int rightScore = Math.abs(targetPos.x - right.x) + Math.abs(botPos.x - right.x);
        return leftScore <= rightScore ? left : right;
    }

    private static boolean shouldUseJump(BotMovementState entry, Point botPos, Point steeringTarget, int stepX) {
        if (entry == null || botPos == null || steeringTarget == null || stepX == 0 || shouldWalkOffLedge(entry, botPos, steeringTarget, stepX)) {
            return false;
        }
        MapleMap map = entry.bot.getMap();
        int direction = Integer.signum(stepX);
        int jumpStep = direction * BotPhysicsEngine.walkStep(map, entry.movementProfile);
        BotPhysicsEngine.JumpLanding landing = BotPhysicsEngine.simulateJumpLanding(map, botPos, jumpStep, entry.movementProfile);
        return isUsefulJumpProbeLanding(botPos, steeringTarget, direction, landing);
    }

    private static boolean isUsefulJumpProbeLanding(Point botPos, Point steeringTarget, int direction, BotPhysicsEngine.JumpLanding landing) {
        if (landing == null || landing.point() == null || direction == 0) {
            return false;
        }
        Point landingPoint = landing.point();
        int landingDx = landingPoint.x - botPos.x;
        if (Integer.signum(landingDx) != direction) {
            return false;
        }
        int distanceBefore = Math.abs(steeringTarget.x - botPos.x);
        int distanceAfter = Math.abs(steeringTarget.x - landingPoint.x);
        if (distanceAfter >= distanceBefore) {
            return false;
        }
        boolean targetIsAboveOrLevel = steeringTarget.y <= botPos.y + BotPhysicsEngine.cfg.MAX_SNAP_DROP;
        boolean landingIsAboveOrLevel = landingPoint.y <= botPos.y + BotPhysicsEngine.cfg.MAX_SNAP_DROP;
        return targetIsAboveOrLevel && landingIsAboveOrLevel;
    }
}
