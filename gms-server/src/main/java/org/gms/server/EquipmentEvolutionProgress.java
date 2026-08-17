package org.gms.server;

import org.gms.client.Character;

import java.util.Set;

/** Permanent boss-clear qualifications consumed by the equipment evolution NPC. */
public final class EquipmentEvolutionProgress {
    public static final String BOSS_KEY_PREFIX = "equipment_evolution_boss_";

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
}
