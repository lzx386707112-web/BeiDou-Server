package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import org.gms.client.Character;
import org.gms.server.life.Monster;
import org.gms.server.maps.MapObject;
import org.gms.server.maps.MapObjectType;
import soloMapling.server.MethodScheduler;
import org.gms.util.PacketCreator;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotContactDamage.class */
final class BotContactDamage {
    private static final float KNOCKBACK_HSPEED = 1.5f;
    private static final float KNOCKBACK_VFORCE = 3.5f;
    private static final int MOB_TOUCH_SWEEP_HEIGHT = 50;
    private static final int MOB_HIT_COOLDOWN_MS = 2500;
    private static final int MOB_QUERY_MARGIN = 150;
    private static final double DMG_FACTOR = 0.5d;
    private static final double DMG_SPREAD = 0.2d;
    private static final int NICHE_WARRIOR = 1;
    private static final int NICHE_THIEF = 4;
    private static final double BASE_MISS_CHANCE = 0.1d;
    private static final double THIEF_MISS_CHANCE = 0.4d;
    private static final double WARRIOR_KB_RESIST = 0.75d;
    private static final float WARRIOR_KB_DAMPEN = 0.45f;
    private static final long ALERT_DURATION_MS = 5000;
    private static final float FALL_DIST_THRESHOLD_PX = 890.0f;
    private static final float FALL_DMG_SAT = 28.0f;
    private static final float FALL_KNEE_SHARPNESS = 0.013f;
    private static final float FALL_DMG_PER_PX_TAIL = 0.0024f;

    private BotContactDamage() {
    }

    static void tickMobDamage(BotMovementState entry, Character bot) {
        if (!GCMovement.isMapObserved(bot.getMapId())) {
            entry.mobHitCooldownMs = 0;
            return;
        }
        Point botPos = bot.getPosition();
        try {
            if (entry.mobHitCooldownMs > 0) {
                entry.mobHitCooldownMs = BotMovementManager.tickDown(entry.mobHitCooldownMs);
                rememberMobTouchCheck(entry, bot, botPos);
                return;
            }
            Rectangle query = new Rectangle(getBotTouchBounds(entry, bot));
            query.grow(MOB_QUERY_MARGIN, MOB_QUERY_MARGIN);
            for (MapObject obj : bot.getMap().getMapObjectsInRect(query, List.of(MapObjectType.MONSTER))) {
                if (!(obj instanceof Monster mob)) {
                    continue;
                }
                if (isHostileLivingMonster(mob) && isMobTouchingBot(entry, bot, mob)) {
                    applyMobHit(entry, bot, mob);
                    rememberMobTouchCheck(entry, bot, botPos);
                    return;
                }
            }
        } finally {
            rememberMobTouchCheck(entry, bot, botPos);
        }
    }

    private static void applyMobHit(BotMovementState entry, Character bot, Monster mob) {
        double missChance = isThief(bot) ? THIEF_MISS_CHANCE : BASE_MISS_CHANCE;
        int dmg = ThreadLocalRandom.current().nextDouble() < missChance ? 0 : rollMobDamage(mob);
        MobHitKnockback kb = resolveMobHitKnockback(bot.getPosition(), mob.getPosition());
        applyDamage(entry, bot, dmg, -1, mob.getId(), kb.direction(), kb.airVelX());
    }

    private static int rollMobDamage(Monster mob) {
        double base = Math.max(NICHE_WARRIOR, mob.getPADamage()) * 0.5d;
        double spread = 1.0d + ThreadLocalRandom.current().nextDouble(-0.2d, DMG_SPREAD);
        return (int) Math.max(1L, Math.round(base * spread));
    }

    static void applyFallDamage(BotMovementState entry, Character bot, float fallDistancePx) {
        int dmg;
        if (!GCMovement.isMapObserved(bot.getMapId()) || entry.mobHitCooldownMs > 0 || (dmg = fallDamageFromDistance(fallDistancePx)) <= 0) {
            return;
        }
        int dirSign = entry.facingDir >= 0 ? NICHE_WARRIOR : -1;
        int airVelX = Math.round((-dirSign) * scaledOpenStoryStep(KNOCKBACK_HSPEED));
        applyDamage(entry, bot, dmg, -3, 0, 0, airVelX);
    }

    static int fallDamageFromDistance(float distancePx) {
        if (distancePx <= FALL_DIST_THRESHOLD_PX) {
            return 0;
        }
        double u = distancePx - FALL_DIST_THRESHOLD_PX;
        double dmg = (28.0d * (1.0d - Math.exp((-0.013000000268220901d) * u))) + (0.002400000113993883d * u);
        return (int) Math.max(1L, Math.round(dmg));
    }

    private static void applyDamage(BotMovementState entry, Character bot, int dmg, int damageFrom, int monsterId, int broadcastDirection, int knockbackAirVelX) {
        Point botPos = bot.getPosition();
        bot.getMap().broadcastMessage(bot, PacketCreator.damagePlayer(damageFrom, monsterId, bot.getId(), Math.max(0, dmg), 0, broadcastDirection, false, 0, false, 0, 0, 0), false);
        entry.mobHitCooldownMs = BotMovementManager.delayAfterCurrentTick(MOB_HIT_COOLDOWN_MS);
        markAlerted(entry);
        if (dmg <= 0 || !shouldApplyMobKnockback(entry, bot)) {
            return;
        }
        clearActionState(entry);
        float dampen = isWarrior(bot) ? WARRIOR_KB_DAMPEN : 1.0f;
        int hVel = Math.round(knockbackAirVelX * dampen);
        if (entry.inAir) {
            BotPhysicsEngine.applyAirKnockback(entry, bot, hVel);
        } else {
            BotPhysicsEngine.beginKnockback(entry, bot, botPos, (-scaledOpenStoryStep(KNOCKBACK_VFORCE)) * dampen, hVel);
        }
        BotMovementManager.broadcastMovement(entry);
    }

    private static boolean shouldApplyMobKnockback(BotMovementState entry, Character bot) {
        if (entry.climbing) {
            return false;
        }
        if (isWarrior(bot) && ThreadLocalRandom.current().nextDouble() < WARRIOR_KB_RESIST) {
            return false;
        }
        return true;
    }

    private static boolean isWarrior(Character bot) {
        return (bot == null || bot.getJob() == null || bot.getJob().getJobNiche() != NICHE_WARRIOR) ? false : true;
    }

    private static boolean isThief(Character bot) {
        return (bot == null || bot.getJob() == null || bot.getJob().getJobNiche() != 4) ? false : true;
    }

    private static MobHitKnockback resolveMobHitKnockback(Point botPos, Point attackOrigin) {
        boolean attackFromRight = attackOrigin.x > botPos.x;
        int direction = attackFromRight ? 0 : NICHE_WARRIOR;
        int airVelX = Math.round((attackFromRight ? -1.0f : 1.0f) * scaledOpenStoryStep(KNOCKBACK_HSPEED));
        return new MobHitKnockback(direction, airVelX);
    }

    private static float scaledOpenStoryStep(float openStoryStepValue) {
        return openStoryStepValue * (BotPhysicsEngine.cfg.TICK_MS / 8.0f);
    }

    private static void clearActionState(BotMovementState entry) {
        entry.attackCooldownMs = 0;
        BotMovementManager.clearNavigationState(entry);
        entry.movementBroadcastValid = false;
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotContactDamage$MobHitKnockback.class */
    private static final class MobHitKnockback {
        private final int direction;
        private final int airVelX;

        private MobHitKnockback(int direction, int airVelX) {
            this.direction = direction;
            this.airVelX = airVelX;
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

        public int direction() {
            return this.direction;
        }

        public int airVelX() {
            return this.airVelX;
        }
    }

    private static boolean isMobTouchingBot(BotMovementState entry, Character bot, Monster mob) {
        Rectangle botBounds = getBotTouchBounds(entry, bot);
        Rectangle mobBounds = BotMobHitboxProvider.getMobBounds(mob);
        if (mobBounds == null) {
            return false;
        }
        int lowerHeight = Math.max(NICHE_WARRIOR, mobBounds.height / 2);
        Rectangle mobLowerHalf = new Rectangle(mobBounds.x, (mobBounds.y + mobBounds.height) - lowerHeight, mobBounds.width, lowerHeight);
        return mobLowerHalf.intersects(botBounds);
    }

    private static Rectangle getBotTouchBounds(BotMovementState entry, Character bot) {
        Point currentPos = bot.getPosition();
        Point previousPos = currentPos;
        if (entry != null && entry.lastMobTouchCheckPos != null && entry.lastMobTouchMapId == bot.getMapId()) {
            previousPos = entry.lastMobTouchCheckPos;
        }
        int left = Math.min(previousPos.x, currentPos.x);
        int right = Math.max(previousPos.x, currentPos.x);
        int top = Math.min(previousPos.y, currentPos.y) - MOB_TOUCH_SWEEP_HEIGHT;
        int bottom = Math.max(previousPos.y, currentPos.y);
        return inclusiveRectangle(left, top, right, bottom);
    }

    private static Rectangle inclusiveRectangle(int left, int top, int right, int bottom) {
        return new Rectangle(left, top, Math.max(NICHE_WARRIOR, (right - left) + NICHE_WARRIOR), Math.max(NICHE_WARRIOR, (bottom - top) + NICHE_WARRIOR));
    }

    private static void rememberMobTouchCheck(BotMovementState entry, Character bot, Point position) {
        if (entry == null || bot == null || position == null) {
            return;
        }
        entry.lastMobTouchCheckPos = new Point(position);
        entry.lastMobTouchMapId = bot.getMapId();
    }

    private static boolean isHostileLivingMonster(Monster monster) {
        return monster != null && monster.isAlive() && (monster.getStats() == null || !monster.getStats().isFriendly());
    }

    static void markAlerted(BotMovementState entry) {
        entry.alertedUntilMs = System.currentTimeMillis() + ALERT_DURATION_MS;
        scheduleAlertReset(entry);
    }

    private static void scheduleAlertReset(BotMovementState entry) {
        if (entry.alertResetScheduled) {
            return;
        }
        entry.alertResetScheduled = true;
        long delay = Math.max(50L, (entry.alertedUntilMs - System.currentTimeMillis()) + 100);
        MethodScheduler.runAfterDelay(() -> {
            long now = System.currentTimeMillis();
            if (now < entry.alertedUntilMs) {
                entry.alertResetScheduled = false;
                scheduleAlertReset(entry);
            } else {
                entry.alertResetScheduled = false;
                try {
                    if (entry.bot != null) {
                        entry.bot.broadcastStance();
                    }
                } catch (Throwable th) {
                }
            }
        }, delay);
    }
}
