package org.gms.server;

import org.gms.client.Character;
import org.gms.scripting.AbstractPlayerInteraction;
import org.gms.server.life.Monster;

import java.util.Collections;
import java.util.Locale;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;

public final class BossDamageGrowth {
    public static final int QUEST_REQUIREMENT = 1000;
    public static final int BOSS_KILL_REQUIREMENT = 10;
    public static final int MONSTER_CARD_REQUIREMENT = 300;
    public static final double QUEST_MAX_BONUS_PERCENT = 30.0;
    public static final double BOSS_MAX_BONUS_PERCENT = 40.0;
    public static final double MONSTER_CARD_MAX_BONUS_PERCENT = 30.0;
    public static final double MAX_BONUS_PERCENT = 100.0;
    public static final double MAX_MULTIPLIER = 2.0;

    private static final long CACHE_DURATION_MS = 5 * 60 * 1000L;
    private static final String BOSS_KILL_KEY_PREFIX = "boss_growth_kill_";
    private static final int KREXEL_ID = 9420522;
    private static final Map<Integer, BossBonusCache> BOSS_BONUS_CACHE = new ConcurrentHashMap<>();
    private static final Map<Monster, Boolean> STANDALONE_RECORDED =
            Collections.synchronizedMap(new WeakHashMap<>());

    private static final Map<Integer, BossGrowthEntry> BOSS_ENTRIES = Map.ofEntries(
            Map.entry(8500002, new BossGrowthEntry("papulatus", "帕普拉图斯", 1.0)),
            Map.entry(9420544, new BossGrowthEntry("scarga", "狮熊双王", 1.2)),
            Map.entry(9600025, new BossGrowthEntry("yaoseng", "武林妖僧", 1.4)),
            Map.entry(KREXEL_ID, new BossGrowthEntry("krexel", "克雷塞尔", 1.6)),
            Map.entry(8800002, new BossGrowthEntry("zakum", "扎昆", 1.8)),
            Map.entry(9400300, new BossGrowthEntry("showa", "昭和大头老板", 2.4)),
            Map.entry(8810018, new BossGrowthEntry("horntail", "暗黑龙王", 2.6)),
            Map.entry(8820001, new BossGrowthEntry("pinkbean", "品克缤", 2.8)),
            Map.entry(9400265, new BossGrowthEntry("tokyo_vergamot", "贝尔加莫特", 3.0)),
            Map.entry(9400270, new BossGrowthEntry("tokyo_dunas", "都纳斯", 3.2)),
            Map.entry(9400273, new BossGrowthEntry("tokyo_nibergen", "尼贝隆", 3.4)),
            Map.entry(9400266, new BossGrowthEntry("tokyo_nux", "努克斯", 3.6)),
            Map.entry(9400294, new BossGrowthEntry("tokyo_dunas2", "再生都纳斯", 3.8)),
            Map.entry(9400289, new BossGrowthEntry("tokyo_aufheben", "欧碧拉", 4.0)),
            Map.entry(8840000, new BossGrowthEntry("vonleon", "狮子王", 4.2))
    );

    private BossDamageGrowth() {
    }

    public static int apply(Character chr, Monster monster, int damage) {
        if (chr == null || monster == null || damage <= 0 || !monster.isBoss()) {
            return damage;
        }
        if (damage == Integer.MAX_VALUE) {
            return damage;
        }

        long boosted = Math.round(damage * getMultiplier(chr));
        int actualDamage = boosted >= Integer.MAX_VALUE
                ? Integer.MAX_VALUE
                : (int) Math.max(1L, boosted);
        long bonusDamage = (long) actualDamage - damage;
        if (bonusDamage > 0L) {
            chr.dropMessage(5, "[BOSS伤害] 本次额外造成 +"
                    + String.format(Locale.US, "%,d", bonusDamage) + " 伤害。");
        }

        recordStandaloneBossOnLethalHit(monster, actualDamage);
        return actualDamage;
    }

    public static int getQuestCount(Character chr) {
        return chr == null ? 0 : chr.getCompletedQuests().size();
    }

    public static int getMonsterCardCount(Character chr) {
        return chr == null || chr.getMonsterBook() == null ? 0 : chr.getMonsterBook().getTotalCards();
    }

    public static double getMultiplier(Character chr) {
        return 1.0 + getBonusPercent(chr) / 100.0;
    }

    public static double getBonusPercent(Character chr) {
        double total = getQuestBonusPercent(chr)
                + getBossBonusPercent(chr)
                + getMonsterCardBonusPercent(chr);
        return Math.min(total, MAX_BONUS_PERCENT);
    }

    public static double calculateMultiplier(int questCount, int bossBonusPercent, int monsterCardCount) {
        return 1.0 + calculateBonusPercent(questCount, bossBonusPercent, monsterCardCount) / 100.0;
    }

    public static double calculateBonusPercent(int questCount, int bossBonusPercent, int monsterCardCount) {
        double total = calculateQuestBonusPercent(questCount)
                + clampBossBonusPercent(bossBonusPercent)
                + calculateMonsterCardBonusPercent(monsterCardCount);
        return Math.min(total, MAX_BONUS_PERCENT);
    }

    public static double getQuestBonusPercent(Character chr) {
        return calculateQuestBonusPercent(getQuestCount(chr));
    }

    public static double getBossBonusPercent(Character chr) {
        if (chr == null) {
            return 0.0;
        }

        int characterId = chr.getId();
        long now = System.currentTimeMillis();
        BossBonusCache cached = BOSS_BONUS_CACHE.get(characterId);
        if (cached != null && cached.expireAt > now) {
            return cached.bonusPercent;
        }

        double bonusPercent = loadBossBonusPercent(chr);
        BOSS_BONUS_CACHE.put(characterId, new BossBonusCache(bonusPercent, now + CACHE_DURATION_MS));
        return bonusPercent;
    }

    public static double getMonsterCardBonusPercent(Character chr) {
        return calculateMonsterCardBonusPercent(getMonsterCardCount(chr));
    }

    public static double calculateQuestBonusPercent(int questCount) {
        return getProgress(questCount, QUEST_REQUIREMENT) * QUEST_MAX_BONUS_PERCENT;
    }

    public static double calculateMonsterCardBonusPercent(int monsterCardCount) {
        return getProgress(monsterCardCount, MONSTER_CARD_REQUIREMENT) * MONSTER_CARD_MAX_BONUS_PERCENT;
    }

    public static void recordBossKill(Monster monster) {
        if (monster == null) {
            return;
        }

        BossGrowthEntry entry = BOSS_ENTRIES.get(monster.getId());
        if (entry == null) {
            return;
        }
        if (monster.getId() == KREXEL_ID && !markStandaloneRecorded(monster)) {
            return;
        }

        recordBossKill(monster, entry.key(), entry.name(), entry.maxBonusPercent());
    }

    public static void recordBossKill(Monster monster, String key, String name, double maxBonusPercent) {
        if (monster == null || monster.getMap() == null || key == null || key.isBlank()) {
            return;
        }

        for (Character chr : monster.getMap().getAllPlayers()) {
            if (chr == null || !chr.isAlive()) {
                continue;
            }

            AbstractPlayerInteraction api = chr.getAbstractPlayerInteraction();
            String extendKey = BOSS_KILL_KEY_PREFIX + key;
            int current = parseNonNegativeInt(api.getCharacterExtendValue(extendKey));
            int updated = current == Integer.MAX_VALUE ? Integer.MAX_VALUE : current + 1;
            api.saveOrUpdateCharacterExtendValue(extendKey, String.valueOf(updated));
            invalidate(chr.getId());

            int effectiveKills = Math.min(updated, BOSS_KILL_REQUIREMENT);
            double currentBonus = getProgress(effectiveKills, BOSS_KILL_REQUIREMENT) * maxBonusPercent;
            chr.dropMessage(5, "[BOSS记录] 击败" + name
                    + "，进度 " + effectiveKills + "/" + BOSS_KILL_REQUIREMENT
                    + "，BOSS伤害 +" + formatPercent(currentBonus)
                    + "% / +" + formatPercent(maxBonusPercent) + "%。");
        }
    }

    public static void invalidate(int characterId) {
        BOSS_BONUS_CACHE.remove(characterId);
    }

    private static void recordStandaloneBossOnLethalHit(Monster monster, int damage) {
        if (monster.getId() != KREXEL_ID || damage < monster.getHp() || !markStandaloneRecorded(monster)) {
            return;
        }

        BossGrowthEntry entry = BOSS_ENTRIES.get(KREXEL_ID);
        recordBossKill(monster, entry.key(), entry.name(), entry.maxBonusPercent());
    }

    private static boolean markStandaloneRecorded(Monster monster) {
        synchronized (STANDALONE_RECORDED) {
            return STANDALONE_RECORDED.put(monster, Boolean.TRUE) == null;
        }
    }

    private static double getProgress(int count, int requirement) {
        if (requirement <= 0) {
            return 1.0;
        }
        return Math.min(Math.max((double) count / requirement, 0.0), 1.0);
    }

    private static double clampBossBonusPercent(double bonusPercent) {
        return Math.min(Math.max(bonusPercent, 0.0), BOSS_MAX_BONUS_PERCENT);
    }

    private static double loadBossBonusPercent(Character chr) {
        double total = 0.0;
        for (BossGrowthEntry entry : BOSS_ENTRIES.values()) {
            int kills = getBossKillCount(chr, entry.key());
            total += getProgress(kills, BOSS_KILL_REQUIREMENT) * entry.maxBonusPercent();
        }
        return clampBossBonusPercent(total);
    }

    private static int getBossKillCount(Character chr, String key) {
        String value = chr.getAbstractPlayerInteraction()
                .getCharacterExtendValue(BOSS_KILL_KEY_PREFIX + key);
        return parseNonNegativeInt(value);
    }

    private static String formatPercent(double value) {
        return String.format(Locale.US, "%.1f", value);
    }

    private static int parseNonNegativeInt(String value) {
        if (value == null || value.isBlank()) {
            return 0;
        }
        try {
            return Math.max(Integer.parseInt(value), 0);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private record BossGrowthEntry(String key, String name, double maxBonusPercent) {
    }

    private static final class BossBonusCache {
        private final double bonusPercent;
        private final long expireAt;

        private BossBonusCache(double bonusPercent, long expireAt) {
            this.bonusPercent = bonusPercent;
            this.expireAt = expireAt;
        }
    }
}
