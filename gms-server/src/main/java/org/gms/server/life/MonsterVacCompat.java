package org.gms.server.life;

import org.gms.config.GameConfig;

import java.awt.Point;
import java.util.concurrent.TimeUnit;

/** 消耗品 2431158「怪物吸星大法」：10 分钟固定吸怪点，不可叠加。 */
public final class MonsterVacCompat {
    public static final int ITEM_ID = 2431158;
    public static final String DURATION_CONFIG = "monster_vac_duration_minutes";
    public static final String STUN_ENABLED_CONFIG = "monster_vac_stun_enabled";
    public static final long DURATION_MS = TimeUnit.MINUTES.toMillis(10);
    public static final long PULL_INTERVAL_MS = 100L;
    public static final int PULL_STEP_PX = 150;
    public static final int MOVE_DURATION_MS = 130;
    public static final int SNAP_DISTANCE_SQ = 8 * 8;
    public static final long STUN_DURATION_MS = 2500L;
    /** 十字军虎咆哮：客户端用这个技能 ID 画怪物头顶眩晕星。 */
    public static final int STUN_SKILL_ID = 1111008;

    private MonsterVacCompat() {
    }

    public static boolean canStart(boolean alreadyActive) {
        return !alreadyActive;
    }

    public static long durationMillis() {
        int minutes;
        try {
            minutes = GameConfig.getServerInt(DURATION_CONFIG);
        } catch (Throwable ignored) {
            return DURATION_MS;
        }
        if (minutes <= 0) {
            return DURATION_MS;
        }
        return TimeUnit.MINUTES.toMillis(minutes);
    }

    public static int durationMinutes() {
        return (int) TimeUnit.MILLISECONDS.toMinutes(durationMillis());
    }

    public static boolean stunEnabled() {
        try {
            return GameConfig.getServerBoolean(STUN_ENABLED_CONFIG);
        } catch (Throwable ignored) {
            return true;
        }
    }

    public static boolean isActive(long nowMillis, long expireAtMillis) {
        return expireAtMillis > nowMillis;
    }

    public static boolean isPullable(boolean alive, boolean fake, boolean boss) {
        return alive && !fake && !boss;
    }

    public static Point stepToward(Point from, Point to, int maxStepPx) {
        int dx = to.x - from.x;
        int dy = to.y - from.y;
        double dist = Math.hypot(dx, dy);
        if (dist <= maxStepPx) {
            return new Point(to);
        }
        double scale = maxStepPx / dist;
        return new Point(
                from.x + (int) Math.round(dx * scale),
                from.y + (int) Math.round(dy * scale));
    }

    public static int facingStance(int fromX, int toX) {
        return toX < fromX ? 3 : 2;
    }
}
