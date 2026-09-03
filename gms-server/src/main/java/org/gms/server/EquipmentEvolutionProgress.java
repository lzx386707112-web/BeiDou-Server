package org.gms.server;

import org.gms.client.Character;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Tracks stage-bound monster kills for the equipment evolution system. */
public final class EquipmentEvolutionProgress {
    public static final String STAGE_KEY_PREFIX = "equip_upgrade_v2_stage_";
    public static final String KILL_KEY_PREFIX = "equip_upgrade_v2_kill_";

    private static final List<Map<Integer, Integer>> STAGE_KILL_REQUIREMENTS = List.of(
            requirements(1140100, 100, 2130103, 100, 3230300, 100),
            requirements(4230125, 100, 4230102, 100, 4130100, 100, 3230100, 100),
            requirements(6230601, 100, 6230100, 100, 6130208, 100, 7130104, 100, 6130209, 100),
            requirements(2230103, 100, 3230103, 100, 3230304, 100, 3230400, 100, 6230300, 100),
            requirements(8140600, 100, 8140701, 100, 8140702, 100, 8141100, 100,
                    8141300, 100, 9400013, 100, 8140101, 100, 8140111, 100, 9400205, 10),
            requirements(9420530, 100, 9420533, 100, 9420538, 100, 9420540, 100,
                    9400542, 100, 9400562, 100),
            requirements(8190004, 100, 8200008, 100, 8200010, 100, 8220003, 3,
                    8500002, 3, 9400014, 3, 9400121, 3, 8220004, 3, 8220005, 3, 8220006, 3),
            requirements(8800002, 10, 9400300, 10, 8510000, 10,
                    9400549, 20, 9400575, 20, 8150000, 20),
            requirements(8810018, 10, 8600000, 100, 8600001, 100, 8600002, 100,
                    8600003, 100, 8600004, 100, 8600005, 100, 8600006, 100,
                    8610005, 100, 8610006, 100, 8610007, 100, 8610008, 100, 8610009, 100,
                    8610010, 100, 8610011, 100, 8610012, 100, 8610013, 100, 8610014, 100),
            requirements(8880142, 1)
    );

    private EquipmentEvolutionProgress() {
    }

    /** Records only kills required by the character's immediate next armor stage. */
    public static void recordKill(Character chr, int mobId) {
        if (chr == null) {
            return;
        }

        int completedStage = getInt(chr, STAGE_KEY_PREFIX + "armor", -1);
        int targetStage = completedStage + 1;
        if (targetStage < 0 || targetStage >= STAGE_KILL_REQUIREMENTS.size()) {
            return;
        }

        Integer requiredCount = STAGE_KILL_REQUIREMENTS.get(targetStage).get(mobId);
        if (requiredCount == null) {
            return;
        }

        String key = KILL_KEY_PREFIX + targetStage + "_" + mobId;
        int current = getInt(chr, key, 0);
        if (current >= requiredCount) {
            return;
        }
        chr.getAbstractPlayerInteraction().saveOrUpdateCharacterExtendValue(
                key, String.valueOf(current + 1)
        );
    }

    private static Map<Integer, Integer> requirements(int... mobIdAndCountPairs) {
        if (mobIdAndCountPairs.length % 2 != 0) {
            throw new IllegalArgumentException("mob requirements must use id/count pairs");
        }
        Map<Integer, Integer> result = new LinkedHashMap<>();
        for (int i = 0; i < mobIdAndCountPairs.length; i += 2) {
            Integer previous = result.put(mobIdAndCountPairs[i], mobIdAndCountPairs[i + 1]);
            if (previous != null) {
                throw new IllegalArgumentException("duplicate mob id " + mobIdAndCountPairs[i]);
            }
        }
        return Map.copyOf(result);
    }

    private static int getInt(Character chr, String key, int defaultValue) {
        String value = chr.getAbstractPlayerInteraction().getCharacterExtendValue(key);
        if (value == null || value.isEmpty()) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
}
