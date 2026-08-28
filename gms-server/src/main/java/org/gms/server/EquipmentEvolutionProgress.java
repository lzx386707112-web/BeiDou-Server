package org.gms.server;

import org.gms.client.Character;

import java.util.Set;

/**
 * Tracks progress for the equipment upgrade system (套装进化).
 * - Boss-clear qualifications (permanent).
 * - Kill counts per upgrade stage (reset on failure).
 */
public final class EquipmentEvolutionProgress {
    public static final String BOSS_KEY_PREFIX = "equipment_evolution_boss_";
    public static final String STAGE_KEY_PREFIX = "equip_upgrade_stage_";
    public static final String KILL_KEY_PREFIX = "equip_upgrade_kill_";

    /**
     * Min-level requirement per stage index (0-19).
     * Matches the killCount.minLevel in the NPC script's ARMOR_STAGES config.
     */
    private static final int[] STAGE_MIN_LEVEL = {
            10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
            110, 120, 130, 135, 140, 150, 160, 170, 185, 200
    };

    private static final Set<Integer> QUALIFICATION_BOSSES = Set.of(
            2220000, 9400610, 9400609, 9400613, 9400612, 9400611, 9400633,
            3220000, 3220001, 4220001, 5220002, 5220004, 5220001, 5220003,
            6220000, 6220001, 6090002, 7220001, 7220000, 7220002,
            8220000, 8220002, 8220009, 8220003,
            8860000, 8850011,
            8910100, 8900100, 8920101, 8930100,
            8870000, 8870200, 8880400, 8880200, 8645009, 8880700, 8880803
    );

    private EquipmentEvolutionProgress() {
    }

    public static void recordBossClear(Character chr, int mobId) {
        if (chr == null || !QUALIFICATION_BOSSES.contains(mobId)) {
            return;
        }
        chr.getAbstractPlayerInteraction().saveOrUpdateCharacterExtendValue(
                BOSS_KEY_PREFIX + mobId, "1"
        );
    }

    /**
     * Increment kill count for the equipment upgrade system when a monster is killed.
     * Only counts if the monster's level meets the minimum for the player's next upgrade stage.
     * Armor and weapon share the same kill count (same stage index → same key).
     *
     * @param chr    the attacking player
     * @param mobLevel the killed monster's level
     */
    public static void recordKill(Character chr, int mobLevel) {
        if (chr == null) return;

        // Get current armor and weapon stages
        int armorStage = getInt(chr, STAGE_KEY_PREFIX + "armor", -1);
        int weaponStage = getInt(chr, STAGE_KEY_PREFIX + "weapon", -1);

        // Use the lower stage (the one that still needs upgrading)
        // If both are at the same stage, use that stage
        // If one is behind, use the behind one
        int currentStage = Math.min(
                armorStage < 0 ? Integer.MAX_VALUE : armorStage,
                weaponStage < 0 ? Integer.MAX_VALUE : weaponStage
        );

        // Both stages not started yet - count from stage 0
        if (currentStage == Integer.MAX_VALUE) {
            currentStage = -1;
        }

        int nextStage = currentStage + 1;

        // Already at max stage
        if (nextStage >= STAGE_MIN_LEVEL.length) return;

        // Check if monster level meets the minimum for next stage
        if (mobLevel < STAGE_MIN_LEVEL[nextStage]) return;

        incrementKillCount(chr, nextStage);
    }

    private static void incrementKillCount(Character chr, int stageIndex) {
        String key = KILL_KEY_PREFIX + stageIndex;
        int current = getInt(chr, key, 0);
        chr.getAbstractPlayerInteraction().saveOrUpdateCharacterExtendValue(
                key, String.valueOf(current + 1)
        );
    }

    private static int getInt(Character chr, String key, int defaultValue) {
        String val = chr.getAbstractPlayerInteraction().getCharacterExtendValue(key);
        if (val == null || val.isEmpty()) return defaultValue;
        try {
            return Integer.parseInt(val);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
}
