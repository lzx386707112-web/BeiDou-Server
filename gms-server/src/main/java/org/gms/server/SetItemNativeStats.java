package org.gms.server;

import org.gms.client.BuffStat;
import org.gms.client.inventory.Equip;

/** Native v83 temporary stats; percentages use equipment contributions, not guessed client formulas. */
public final class SetItemNativeStats {
    public static final BuffStat[] STATS = {BuffStat.WDEF, BuffStat.MDEF, BuffStat.ACC, BuffStat.AVOID};

    private SetItemNativeStats() {
    }

    public static String key(BuffStat stat) {
        return switch (stat) {
            case WDEF -> "PDD";
            case MDEF -> "MDD";
            case ACC -> "ACC";
            case AVOID -> "EVA";
            default -> null;
        };
    }

    public static int equipmentValue(Equip equip, BuffStat stat) {
        return switch (stat) {
            case WDEF -> equip.getWdef();
            case MDEF -> equip.getMdef();
            case ACC -> equip.getAcc();
            case AVOID -> equip.getAvoid();
            default -> 0;
        };
    }

    public static int mergedValue(SetItemManager.Bonus bonus, BuffStat stat, int equipment, int skillBuff) {
        String key = key(stat);
        if (key == null || (bonus.get(key) == 0 && bonus.get(key + "Pct") == 0)) return skillBuff;
        long value = (long) bonus.apply(key, equipment + skillBuff) - equipment;
        return (int) Math.max(Short.MIN_VALUE, Math.min(Short.MAX_VALUE, value));
    }
}
