package org.gms.server.life;

import java.util.Set;

/**
 * Cooldown projection only. Skill/attack hits go through MobSkill.applyEffect
 * and the client TakeDamage path, same as other bosses.
 */
public final class DamienBossCompat {
    private static final int PHASE_ONE = 8880110;
    private static final int PHASE_TWO = 8880111;
    private static final Set<Integer> PROJECTED_SKILL_IDS = Set.of(
            120, 122, 123, 124, 125, 126, 128, 133, 176, 185);
    private static final int ATTACK_COOLDOWN_MS = 2000;
    private static final int SKILL_COOLDOWN_MS = 4000;

    private DamienBossCompat() {
    }

    public static boolean isDamien(int mobId) {
        return mobId == PHASE_ONE || mobId == PHASE_TWO;
    }

    public static boolean ignoresMobSkillHpGate(int mobId) {
        return isDamien(mobId);
    }

    public static int attackCooldownMillis(int mobId, int attackPosition, int fallback) {
        if (!isDamien(mobId) || attackPosition < 0) {
            return fallback;
        }
        return ATTACK_COOLDOWN_MS;
    }

    public static long skillCooldownMillis(int mobId, int skillId, int level, long fallback) {
        if (!isDamien(mobId)) {
            return fallback;
        }
        if (PROJECTED_SKILL_IDS.contains(skillId)) {
            return SKILL_COOLDOWN_MS;
        }
        return fallback;
    }
}
