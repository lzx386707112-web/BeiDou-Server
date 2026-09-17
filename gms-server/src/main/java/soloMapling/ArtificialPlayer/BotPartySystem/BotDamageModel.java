package soloMapling.ArtificialPlayer.BotPartySystem;

import java.util.concurrent.ThreadLocalRandom;

/** Companion grind damage: job-tier bands scaled by level, floored by a share of mob HP. */
public final class BotDamageModel {
    private static final int[][] BANDS = {
            {80, 160},
            {150, 360},
            {320, 800},
            {700, 1800},
            {1200, 3200}
    };

    private BotDamageModel() {}

    public static int lineDamage(int jobTier, int level, long monsterMaxHp) {
        int tier = Math.max(0, Math.min(BANDS.length - 1, jobTier));
        int lo = BANDS[tier][0];
        int hi = BANDS[tier][1];
        int raw = lo + ThreadLocalRandom.current().nextInt(Math.max(1, hi - lo + 1));
        int scaled = (int) Math.round(raw * (1.0 + Math.max(0, level) / 80.0));
        int fromHp = monsterMaxHp > 0 ? (int) Math.min(99_999L, Math.max(1L, monsterMaxHp / 18L)) : 1;
        return Math.min(99_999, Math.max(scaled, fromHp));
    }
}
