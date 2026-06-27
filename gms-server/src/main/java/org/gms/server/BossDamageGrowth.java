package org.gms.server;

import org.gms.client.Character;
import org.gms.constants.string.ExtendType;
import org.gms.dao.entity.ExtendValueDO;
import org.gms.util.ExtendUtil;

import java.util.Map;

public final class BossDamageGrowth {
    public static final int QUEST_REQUIREMENT = 300;
    public static final double QUEST_MAX_BONUS_PERCENT = 300.0;
    public static final int MONSTER_CARD_REQUIREMENT = 300;
    public static final double MONSTER_CARD_MAX_BONUS_PERCENT = 300.0;
    public static final double BOSS_MAX_BONUS_PERCENT = 400.0;

    private static final int BOSS_KILL_LIMIT = 10;
    private static final String BOSS_KILL_KEY_PREFIX = "boss_growth_kill_";

    private static final Map<Integer, BossGrowthEntry> BOSS_ENTRIES = Map.ofEntries(
            Map.entry(8500002, new BossGrowthEntry("papulatus", 10.0)),
            Map.entry(9420544, new BossGrowthEntry("scarga", 12.0)),
            Map.entry(9600025, new BossGrowthEntry("yaoseng", 14.0)),
            Map.entry(9420522, new BossGrowthEntry("krexel", 16.0)),
            Map.entry(8800002, new BossGrowthEntry("zakum", 18.0)),
            Map.entry(9400300, new BossGrowthEntry("showa", 24.0)),
            Map.entry(8810018, new BossGrowthEntry("horntail", 26.0)),
            Map.entry(8820001, new BossGrowthEntry("pinkbean", 28.0)),
            Map.entry(9400265, new BossGrowthEntry("tokyo_vergamot", 30.0)),
            Map.entry(9400270, new BossGrowthEntry("tokyo_dunas", 32.0)),
            Map.entry(9400273, new BossGrowthEntry("tokyo_nibergen", 34.0)),
            Map.entry(9400266, new BossGrowthEntry("tokyo_nux", 36.0)),
            Map.entry(9400294, new BossGrowthEntry("tokyo_dunas2", 38.0)),
            Map.entry(9400289, new BossGrowthEntry("tokyo_aufheben", 40.0)),
            Map.entry(8840000, new BossGrowthEntry("vonleon", 42.0))
    );

    private BossDamageGrowth() {
    }

    public static int getQuestCount(Character chr) {
        return chr == null ? 0 : chr.getCompletedQuests().size();
    }

    public static int getMonsterCardCount(Character chr) {
        return chr == null || chr.getMonsterBook() == null ? 0 : chr.getMonsterBook().getTotalCards();
    }

    public static double getQuestBonusPercent(Character chr) {
        return getCappedProgressBonus(getQuestCount(chr), QUEST_REQUIREMENT, QUEST_MAX_BONUS_PERCENT);
    }

    public static double getMonsterCardBonusPercent(Character chr) {
        return getCappedProgressBonus(getMonsterCardCount(chr), MONSTER_CARD_REQUIREMENT, MONSTER_CARD_MAX_BONUS_PERCENT);
    }

    public static double getBossBonusPercent(Character chr) {
        if (chr == null) {
            return 0.0;
        }

        double total = 0.0;
        for (BossGrowthEntry entry : BOSS_ENTRIES.values()) {
            int kills = Math.min(getBossKillCount(chr, entry.key()), BOSS_KILL_LIMIT);
            total += kills * entry.maxBonusPercent() / BOSS_KILL_LIMIT;
        }
        return Math.min(total, BOSS_MAX_BONUS_PERCENT);
    }

    public static double getBonusPercent(Character chr) {
        return getQuestBonusPercent(chr) + getMonsterCardBonusPercent(chr) + getBossBonusPercent(chr);
    }

    public static int applyBossDamageBonus(Character chr, int monsterId, int damage) {
        if (damage <= 0 || chr == null || !BOSS_ENTRIES.containsKey(monsterId)) {
            return damage;
        }

        double bonusPercent = getBonusPercent(chr);
        if (bonusPercent <= 0.0) {
            return damage;
        }

        long boosted = Math.round(damage * (100.0 + bonusPercent) / 100.0);
        return (int) Math.min(Integer.MAX_VALUE, Math.max(1L, boosted));
    }

    public static void recordBossKill(Character chr, int monsterId) {
        BossGrowthEntry entry = BOSS_ENTRIES.get(monsterId);
        if (chr == null || entry == null) {
            return;
        }

        String key = BOSS_KILL_KEY_PREFIX + entry.key();
        int current = getBossKillCount(chr, entry.key());
        if (current >= BOSS_KILL_LIMIT) {
            return;
        }

        ExtendUtil.saveOrUpdateExtendValue(
                String.valueOf(chr.getId()),
                ExtendType.CHARACTER_EXTEND.getType(),
                key,
                String.valueOf(current + 1)
        );
    }

    private static double getCappedProgressBonus(int count, int requirement, double maxBonus) {
        if (requirement <= 0 || count <= 0) {
            return 0.0;
        }
        int progress = Math.min(count, requirement);
        return progress * maxBonus / requirement;
    }

    private static int getBossKillCount(Character chr, String key) {
        ExtendValueDO value = ExtendUtil.getExtendValue(
                String.valueOf(chr.getId()),
                ExtendType.CHARACTER_EXTEND.getType(),
                BOSS_KILL_KEY_PREFIX + key
        );
        if (value == null || value.getExtendValue() == null) {
            return 0;
        }

        try {
            return Math.max(0, Integer.parseInt(value.getExtendValue()));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private record BossGrowthEntry(String key, double maxBonusPercent) {
    }
}
