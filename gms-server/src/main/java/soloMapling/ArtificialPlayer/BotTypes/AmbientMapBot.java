package soloMapling.ArtificialPlayer.BotTypes;

import org.gms.client.Character;
import org.gms.server.maps.FootholdTree;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.BotFlavorSystem.BotFlavor;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;
import soloMapling.FreeMarket.MarketBotFlavor;
import soloMapling.SoloMaplingConfig;

import java.awt.Point;
import java.util.concurrent.ThreadLocalRandom;

import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotEmote;
import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotSpeak;
import static soloMapling.ArtificialPlayer.BotHelpers.sleepAmountSeconds;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.BotMoveSmallDistanceX;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botFaceTowardsPoint;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.microTurnAround;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.pathFinderBeta;

public class AmbientMapBot extends BotSM {
    private static final int RANDOM_WALK_TARGET_ATTEMPTS = 24;
    private static final int MIN_RANDOM_WALK_DISTANCE_X = 180;
    private static final int SMALL_STEP_MIN_DISTANCE = 140;
    private static final int SMALL_STEP_MAX_DISTANCE = 280;
    private static final int MAX_SMALL_STEP_Y_DELTA = 240;

    private long nextActionAt = 0;

    public AmbientMapBot(Character chr) {
        super(chr);
        dialoguePath = "";
        botType = "AmbientMapBot";
        scheduleNextAction();
    }

    @Override
    public boolean isAvailableForAmbientActions() {
        return getState() != BotState.TRADING;
    }

    @Override
    public void updateState() {
        super.updateState();
        if (!SoloMaplingConfig.ambientBehaviorEnabled() || !SoloMaplingConfig.ambientHasAnyActionEnabled()) {
            stopScheduledTask();
            return;
        }
        if (checkIfNotRunningOrPaused()) {
            return;
        }
        if (System.currentTimeMillis() < nextActionAt) {
            return;
        }

        BotFlavor.maybeExpress(this);
        runAmbientAction();
        scheduleNextAction();
    }

    @Override
    public void checkPrioritySpeed() {
        if (checkMainPlayersOnMap()) {
            updateScheduleDelay(SoloMaplingConfig.ambientActionMinMs());
            return;
        }
        updateScheduleDelay(2500);
    }

    private void runAmbientAction() {
        int moveWeight = SoloMaplingConfig.ambientMoveEnabled() ? 85 : 0;
        int faceWeight = SoloMaplingConfig.ambientFacePlayerEnabled() ? 5 : 0;
        int emoteWeight = SoloMaplingConfig.ambientEmoteEnabled() ? 5 : 0;
        int chatWeight = SoloMaplingConfig.ambientChatEnabled() ? 5 : 0;
        int totalWeight = moveWeight + faceWeight + emoteWeight + chatWeight;
        if (totalWeight <= 0) {
            return;
        }

        int roll = ThreadLocalRandom.current().nextInt(totalWeight);
        if (roll < moveWeight) {
            stroll();
        } else if (roll < moveWeight + faceWeight) {
            faceNearbyPlayerOrTurn();
        } else if (roll < moveWeight + faceWeight + emoteWeight) {
            BotEmote(getChr());
        } else {
            BotSpeak(getChr(), MarketBotFlavor.chat());
        }
    }

    private void stroll() {
        Character chr = getChr();
        Point target = randomWalkTarget();
        if (chr == null || target == null) {
            return;
        }
        if (!GCMovement.isMapObserved(chr.getMapId())) {
            return;
        }
        GCMovement.enable(chr);
        GCMovement.move(chr, target.x, target.y);
    }

    private void walkToward(Point target) {
        if (target == null) {
            walkSmallSteps(null);
            return;
        }
        int steps = ThreadLocalRandom.current().nextInt(6, 12);
        for (int i = 0; i < steps; i++) {
            Point pos = getChr().getPosition();
            if (Math.abs(target.x - pos.x) < 40) {
                return;
            }
            int direction = Integer.compare(target.x, pos.x);
            int distance = ThreadLocalRandom.current().nextInt(SMALL_STEP_MIN_DISTANCE, SMALL_STEP_MAX_DISTANCE + 1);
            Point next = pointBelow(new Point(pos.x + direction * distance, pos.y - 24));
            if (next == null) {
                next = pointBelow(new Point(pos.x + direction * distance, target.y - 12));
            }
            if (next == null) {
                walkSmallSteps(target);
                return;
            }
            BotMoveSmallDistanceX(getChr(), next);
            if (i + 1 < steps && !sleepAmountSeconds(180 + ThreadLocalRandom.current().nextInt(220))) {
                return;
            }
        }
    }

    private Point randomWalkTarget() {
        MapleMap map = getChr().getMap();
        if (map == null || map.getFootholds() == null) {
            return null;
        }

        FootholdTree footholds = map.getFootholds();
        int minX = footholds.getMinDropX();
        int maxX = footholds.getMaxDropX();
        if (maxX <= minX) {
            return null;
        }

        Point current = getChr().getPosition();
        Point fallback = null;
        ThreadLocalRandom rng = ThreadLocalRandom.current();
        for (int i = 0; i < RANDOM_WALK_TARGET_ATTEMPTS; i++) {
            int x = rng.nextInt(minX, maxX + 1);
            Point ground = map.getPointBelow(new Point(x, footholds.getY1()));
            if (ground == null) {
                continue;
            }
            fallback = ground;
            if (Math.abs(ground.x - current.x) >= MIN_RANDOM_WALK_DISTANCE_X) {
                return ground;
            }
        }
        return fallback;
    }

    private boolean walkToTarget(Point target) {
        Point before = getChr().getPosition();
        if (before == null || Math.abs(target.x - before.x) < MIN_RANDOM_WALK_DISTANCE_X) {
            return false;
        }

        try {
            pathFinderBeta(getChr(), target);
            Point after = getChr().getPosition();
            return after != null && Math.abs(after.x - before.x) >= 80;
        } catch (Exception ignored) {
            return false;
        }
    }

    private void walkSmallSteps(Point preferredTarget) {
        int steps = ThreadLocalRandom.current().nextInt(4, 9);
        int direction = preferredTarget != null && preferredTarget.x != getChr().getPosition().x
                ? Integer.compare(preferredTarget.x, getChr().getPosition().x)
                : (ThreadLocalRandom.current().nextBoolean() ? 1 : -1);
        for (int i = 0; i < steps; i++) {
            Point target = samePlatformStepTarget(direction);
            if (target == null) {
                target = samePlatformStepTarget(-direction);
                if (target == null) {
                    microTurnAround(getChr());
                    return;
                }
                direction = -direction;
            }
            BotMoveSmallDistanceX(getChr(), target);
            if (i + 1 < steps && !sleepAmountSeconds(250 + ThreadLocalRandom.current().nextInt(450))) {
                return;
            }
        }
    }

    private Point samePlatformStepTarget(int direction) {
        Point pos = getChr().getPosition();
        int distance = ThreadLocalRandom.current().nextInt(SMALL_STEP_MIN_DISTANCE, SMALL_STEP_MAX_DISTANCE + 1) * direction;
        Point target = pointBelow(new Point(pos.x + distance, pos.y - 8));
        if (target == null) {
            return null;
        }
        return Math.abs(target.y - pos.y) <= MAX_SMALL_STEP_Y_DELTA ? target : null;
    }

    private Point pointBelow(Point point) {
        try {
            MapleMap map = getChr().getMap();
            return map != null ? map.getPointBelow(point) : null;
        } catch (Exception ignored) {
            return null;
        }
    }

    private void faceNearbyPlayerOrTurn() {
        Character target = null;
        int bestDistance = Integer.MAX_VALUE;
        for (Character other : getChr().getMap().getAllPlayers()) {
            if (other.getId() == getChr().getId() || other.getId() > 20000 || other.getId() == 999) {
                continue;
            }
            int distance = Math.abs(other.getPosition().x - getChr().getPosition().x);
            if (distance < bestDistance) {
                bestDistance = distance;
                target = other;
            }
        }
        if (target != null && bestDistance < 500) {
            botFaceTowardsPoint(getChr(), target.getPosition());
        } else {
            microTurnAround(getChr());
        }
    }

    private void scheduleNextAction() {
        long minMs = Math.min(SoloMaplingConfig.ambientActionMinMs(), 800);
        long maxMs = Math.min(SoloMaplingConfig.ambientActionMaxMs(), 1600);
        if (maxMs < minMs) {
            maxMs = minMs;
        }
        nextActionAt = System.currentTimeMillis() + ThreadLocalRandom.current().nextLong(minMs, maxMs + 1);
    }
}
