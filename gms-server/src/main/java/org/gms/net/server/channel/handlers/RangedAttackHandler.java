/*
This file is part of the OdinMS Maple Story Server
Copyright (C) 2008 Patrick Huy <patrick.huy@frz.cc>
Matthias Butz <matze@odinms.de>
Jan Christian Meyer <vimes@odinms.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation version 3 as published by
the Free Software Foundation. You may not use, modify or distribute
this program under any other version of the GNU Affero General Public
License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
package org.gms.net.server.channel.handlers;

import org.gms.client.BuffStat;
import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.client.Skill;
import org.gms.client.SkillFactory;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.client.inventory.WeaponType;
import org.gms.client.inventory.manipulator.InventoryManipulator;
import org.gms.config.GameConfig;
import org.gms.constants.id.ItemId;
import org.gms.constants.id.MapId;
import org.gms.constants.inventory.ItemConstants;
import org.gms.constants.skills.Aran;
import org.gms.constants.skills.Buccaneer;
import org.gms.constants.skills.Bowmaster;
import org.gms.constants.skills.ExplorerOtherSkillCompat;
import org.gms.constants.skills.Marksman;
import org.gms.constants.skills.NightLord;
import org.gms.constants.skills.NightWalker;
import org.gms.constants.skills.Shadower;
import org.gms.constants.skills.ThunderBreaker;
import org.gms.constants.skills.WindArcher;
import org.gms.net.packet.InPacket;
import org.gms.net.packet.Packet;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.gms.server.ItemInformationProvider;
import org.gms.server.StatEffect;
import org.gms.server.TimerManager;
import org.gms.server.life.Monster;
import org.gms.server.maps.MapleMap;
import org.gms.util.PacketCreator;
import org.gms.util.Randomizer;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

import static java.util.concurrent.TimeUnit.SECONDS;


public final class RangedAttackHandler extends AbstractDealDamageHandler {
    private static final Logger log = LoggerFactory.getLogger(RangedAttackHandler.class);
    private static final String DOMINION_VIDEO_LAYER =
            "customSkill/nightWalker/dominionVideoLayer";
    private static final String SILENT_NIGHT_VIDEO_LAYER =
            "customSkill/nightWalker/silentNightVideoLayer";
    private static final String STYGIAN_COMMAND_VIDEO_LAYER =
            "customSkill/nightWalker/stygianCommandVideoLayer";
    private static final String MONSOON_VIDEO_LAYER =
            "customSkill/windArcher/monsoonVideoLayer";
    private static final String MISTRAL_SPRING_VIDEO_LAYER =
            "customSkill/windArcher/mistralSpringVideoLayer";
    private static final String ELEMENTAL_TEMPEST_VIDEO_LAYER =
            "customSkill/windArcher/elementalTempestVideoLayer";
    private static final int[] RAPID_THROW_UPPER_TIMES_MS = intervalTimes(240, 360, 2400);
    private static final int[] RAPID_THROW_MIDDLE_TIMES_MS = intervalTimes(360, 360, 2520);
    private static final int[] RAPID_THROW_LOWER_TIMES_MS = intervalTimes(480, 360, 2280);
    private static final int RAPID_THROW_FINISH_TIME_MS = 2640;
    private static final int SHADOW_BITE_PASSIVE_PERCENT = 120;
    private static final int SHADOW_BITE_NORMAL_PERCENT = 990;
    private static final int SHADOW_BITE_BOSS_PERCENT = 2673;
    private static final int SHADOW_BITE_ATTACK_COUNT = 8;
    private static final int SHADOW_BITE_TARGET_COUNT = 10;
    private static final int SHADOW_BITE_BAT_DELAY_MS = 720;
    private static final int[] DOMINION_VI_ATTACK_TIMES_MS = intervalTimes(120, 540, 2820);
    private static final int[] DARK_OMEN_VI_TIMES_MS = intervalTimes(270, 270, 6750);
    private static final int[] SILENT_NIGHT_OPENING_TIMES_MS = intervalTimes(3180, 30, 3420);
    private static final int[] SILENT_NIGHT_DART_TIMES_MS = intervalTimes(4020, 30, 4740);
    private static final int[] STYGIAN_COMMAND_TIMES_MS = intervalTimes(900, 30, 1200);
    private static final int[] STYGIAN_COMMAND_FINISH_TIMES_MS = intervalTimes(1890, 30, 2280);
    private static final int[] MERCILESS_WINDS_TIMES_MS = intervalTimes(0, 100, 900);
    private static final int MERCILESS_WINDS_TRACKING_DURATION_MS = 8000;
    private static final int MERCILESS_WINDS_SEARCH_INTERVAL_MS = 100;
    private static final int MERCILESS_WINDS_REPEATED_TARGET_PERCENT = 85;
    private static final int MERCILESS_WINDS_DOT_PERCENT = 1100;
    private static final int MERCILESS_WINDS_DOT_TICKS = 9;
    private static final int MERCILESS_WINDS_DOT_INTERVAL_MS = 1000;
    private static final Map<Character, Map<Monster, Long>> MERCILESS_WINDS_DOT_GENERATIONS =
            new WeakHashMap<>();
    private static final int[] GALE_BARRIER_TIMES_MS = {0};
    private static final int[] ANEMOI_TIMES_MS = {1200};
    private static final int[] MISTRAL_WIND_BLADE_TIMES_MS = {
        2400, 3600, 3720, 3840, 3900, 3930, 3960,
        3990, 4020, 4050, 4080, 4110, 4140
    };
    private static final int MISTRAL_SPIRIT_START_TIME_MS = 4080;
    private static final int MISTRAL_SPIRIT_INTERVAL_MS = 2100;
    private static final int MISTRAL_SPIRIT_DURATION_MS = 20000;
    private static final int MISTRAL_SPIRIT_TOTAL_END_TIME_MS = 25000;
    private static final int MISTRAL_SPIRIT_SEARCH_INTERVAL_MS = 100;
    private static final int[] MISTRAL_SPIRIT_SKILL_IDS = {
        WindArcher.MISTRAL_SPIRIT,
        WindArcher.MISTRAL_HAPPY_SPIRIT,
        WindArcher.MISTRAL_FIERCE_SPIRIT
    };
    private static final int[] MISTRAL_SPIRIT_COUNTS = {13, 5, 3};
    private static final int[] MISTRAL_SPIRIT_LIFETIMES_MS = {3000, 4000, 2400};
    private static final int[] MISTRAL_SPIRIT_ENABLE_DELAYS_MS = {270, 120, 120};
    private static final int[] ELEMENTAL_TEMPEST_WAVE_TIMES_MS = intervalTimes(960, 30, 1260);
    private static final int[] ELEMENTAL_TEMPEST_ARROW_TIMES_MS = intervalTimes(2040, 30, 2340);
    private static final int ARROW_RAIN_DURATION_MS = 70000;
    private static final int ARROW_RAIN_FIELD_COOLDOWN_MS = 5000;
    private static final int[] ARROW_RAIN_FIELD_TIMES_MS = intervalTimes(0, 240, 2400);
    private static final Map<Character, ArrowRainState> ARROW_RAIN_STATES =
            new WeakHashMap<>();
    private static final Map<Character, Boolean> FOUR_SEASONS_RAIN_FRENZY =
            new WeakHashMap<>();
    private static final class ArrowRainState {
        private final long expiresAt;
        private long nextFieldAt;

        private ArrowRainState(long expiresAt, long nextFieldAt) {
            this.expiresAt = expiresAt;
            this.nextFieldAt = nextFieldAt;
        }
    }
    private static int[] intervalTimes(int first, int interval, int last) {
        int[] result = new int[((last - first) / interval) + 1];
        for (int index = 0; index < result.length; index++) {
            result[index] = first + (index * interval);
        }
        return result;
    }

    private static boolean isNightWalkerVViSkill(int skillId) {
        return (skillId >= NightWalker.SHADOW_BITE && skillId <= NightWalker.RAPID_THROW_LOWER_DART)
                || (skillId >= NightWalker.SHADOW_BITE_NORMAL_HIT
                    && skillId <= NightWalker.DOMINION_VI_TICK)
                || (skillId >= NightWalker.DARK_OMEN_VI && skillId <= NightWalker.DARK_OMEN_VI_TICK)
                || (skillId >= NightWalker.DOMINION_VI && skillId <= NightWalker.STYGIAN_COMMAND_FINISH);
    }

    private static boolean isWindArcherVViSkill(int skillId) {
        return (skillId >= WindArcher.MERCILESS_WINDS
                    && skillId <= WindArcher.GALE_BARRIER_TORNADO)
                || (skillId >= WindArcher.FAIRY_SPIRAL_VI
                    && skillId <= WindArcher.MERCILESS_WINDS_SPIRIT)
                || skillId == WindArcher.ELEMENTAL_TEMPEST
                || skillId == WindArcher.ELEMENTAL_TEMPEST_ARROW_RAIN
                || skillId == WindArcher.ELEMENTAL_TEMPEST_WAVE;
    }

    private static boolean isMarksmanVViRangedSkill(int skillId) {
        return skillId == Marksman.TRUE_SNIPING
                || skillId == Marksman.CHARGED_ARROW
                || skillId == Marksman.SWIFT_SHOT_VI
                || skillId == Marksman.LONG_RANGE_TRUE_SHOT_VI
                || skillId == Marksman.SPLIT_SPACE
                || skillId == Marksman.FATAL_TRIGGER;
    }

    private static void scaleDamageLines(List<Integer> damage, int numerator, int denominator) {
        if (damage == null || denominator <= 0) {
            return;
        }
        for (int index = 0; index < damage.size(); index++) {
            int original = damage.get(index);
            long scaled = Math.round((double) decodeRepeatedDamage(original) * numerator / denominator);
            damage.set(index, encodeRepeatedDamage(
                    (int) Math.min(Integer.MAX_VALUE, scaled), original < 0
            ));
        }
    }

    private static void applyShadowBitePassive(AttackInfo attack, Character chr) {
        if (chr.getSkillLevel(NightWalker.SHADOW_BITE) <= 0) {
            return;
        }
        for (List<Integer> damage : attack.allDamage.values()) {
            scaleDamageLines(damage, SHADOW_BITE_PASSIVE_PERCENT, 100);
        }
    }

    private static void applyShadowBiteBossDamage(AttackInfo attack, MapleMap map) {
        if (attack.skill != NightWalker.SHADOW_BITE) {
            return;
        }
        for (Map.Entry<Integer, List<Integer>> entry : attack.allDamage.entrySet()) {
            Monster monster = map.getMonsterByOid(entry.getKey());
            if (monster != null && monster.isBoss()) {
                scaleDamageLines(
                        entry.getValue(), SHADOW_BITE_BOSS_PERCENT, SHADOW_BITE_NORMAL_PERCENT
                );
            }
        }
    }

    private static boolean usesScheduledDamageOnly(int skillId) {
        return ExplorerOtherSkillCompat.multiAttacks(skillId) != null
                || skillId == Bowmaster.ARROW_RAIN
                || skillId == NightWalker.RAPID_THROW
                || skillId == NightWalker.DARK_OMEN_VI
                || skillId == NightWalker.DOMINION_VI
                || skillId == NightWalker.SILENT_NIGHT
                || skillId == NightWalker.STYGIAN_COMMAND
                || skillId == WindArcher.MERCILESS_WINDS
                || skillId == WindArcher.GALE_BARRIER
                || skillId == WindArcher.MISTRAL_SPRING
                || skillId == WindArcher.ELEMENTAL_TEMPEST;
    }

    private static boolean usesFixedAttackOrigin(int skillId) {
        return skillId == Bowmaster.ARROW_RAIN
                || skillId == 4121011
                || skillId == 4121023
                || skillId == Marksman.TRUE_SNIPING
                || skillId == Marksman.CHARGED_ARROW
                || skillId == Marksman.LONG_RANGE_TRUE_SHOT_VI
                || skillId == Marksman.SPLIT_SPACE
                || skillId == Marksman.FATAL_TRIGGER
                || skillId == NightWalker.DARK_OMEN_VI
                || skillId == NightWalker.DOMINION_VI
                || skillId == NightWalker.SILENT_NIGHT
                || skillId == NightWalker.STYGIAN_COMMAND
                || skillId == WindArcher.MERCILESS_WINDS
                || skillId == WindArcher.ANEMOI
                || skillId == WindArcher.MISTRAL_SPRING
                || skillId == WindArcher.ELEMENTAL_TEMPEST;
    }

    private static boolean hasFourSeasonsRainFrenzy(Character chr, AttackInfo attack) {
        if (attack.skill != 4121023) {
            return false;
        }
        synchronized (FOUR_SEASONS_RAIN_FRENZY) {
            return FOUR_SEASONS_RAIN_FRENZY.containsKey(chr);
        }
    }

    private static void consumeFourSeasonsRainFrenzy(Character chr, AttackInfo attack) {
        if (attack.skill != 4121023) {
            return;
        }
        synchronized (FOUR_SEASONS_RAIN_FRENZY) {
            FOUR_SEASONS_RAIN_FRENZY.remove(chr);
        }
    }

    private static void markFourSeasonsRainHit(Character chr, AttackInfo attack) {
        if (attack.skill != 4121023 || attack.numAttacked <= 0) {
            return;
        }
        synchronized (FOUR_SEASONS_RAIN_FRENZY) {
            FOUR_SEASONS_RAIN_FRENZY.put(chr, Boolean.TRUE);
        }
    }

    private void applyAttackCostOnly(AttackInfo attack, Character chr, int bulletCount) {
        Map<Integer, List<Integer>> originalDamage = attack.allDamage;
        int originalNumAttacked = attack.numAttacked;
        int originalPackedCount = attack.numAttackedAndDamage;
        try {
            attack.allDamage = Collections.emptyMap();
            attack.numAttacked = 0;
            attack.numAttackedAndDamage = attack.numDamage & 0xF;
            applyAttack(attack, chr, bulletCount);
        } finally {
            attack.allDamage = originalDamage;
            attack.numAttacked = originalNumAttacked;
            attack.numAttackedAndDamage = originalPackedCount;
        }
    }

    private static boolean canContinueTrackingAttack(Character chr, MapleMap expectedMap) {
        return chr.isLoggedIn() && chr.isAlive() && chr.getMap() == expectedMap;
    }

    private static int decodeRepeatedDamage(int damage) {
        if (damage >= 0) {
            return damage;
        }
        return (int) Math.min(Integer.MAX_VALUE, (long) damage + (long) Integer.MAX_VALUE + 1L);
    }

    private static int encodeRepeatedDamage(int damage, boolean critical) {
        int clamped = Math.max(0, damage);
        return critical ? clamped | Integer.MIN_VALUE : clamped;
    }

    private static List<Integer> copyDamageTemplate(AttackInfo attack) {
        for (List<Integer> damage : attack.allDamage.values()) {
            if (damage != null && !damage.isEmpty()) {
                return new ArrayList<>(damage);
            }
        }
        return Collections.emptyList();
    }

    private static boolean hasPositiveDamageTemplate(List<Integer> damageTemplate) {
        for (int damage : damageTemplate) {
            if (decodeRepeatedDamage(damage) > 0) {
                return true;
            }
        }
        return false;
    }

    private static int calculateFallbackRangedDamage(Character chr, StatEffect effect) {
        long baseDamage = chr.calculateMaxBaseDamage(Math.max(14, chr.getTotalWatk()));
        long skillDamage = Math.round((double) baseDamage * effect.getDamage() / 100.0);
        return (int) Math.max(1, Math.min(Integer.MAX_VALUE, skillDamage));
    }

    private static List<Integer> adaptDamageTemplate(
            List<Integer> source,
            int attackCount,
            int sourcePercent,
            int targetPercent
    ) {
        if (source.isEmpty()) {
            return Collections.emptyList();
        }
        List<Integer> result = new ArrayList<>(attackCount);
        for (int index = 0; index < attackCount; index++) {
            int original = source.get(index % source.size());
            int decoded = decodeRepeatedDamage(original);
            long scaled = sourcePercent > 0
                    ? Math.round((double) decoded * targetPercent / sourcePercent)
                    : decoded;
            result.add(encodeRepeatedDamage((int) Math.min(Integer.MAX_VALUE, scaled), original < 0));
        }
        return result;
    }

    private static Map<Integer, List<Integer>> collectTrackingTargets(
            MapleMap expectedMap,
            Point attackOrigin,
            Rectangle attackBounds,
            int mobCount,
            List<Integer> damageTemplate
    ) {
        Map<Integer, List<Integer>> result = new LinkedHashMap<>();
        if (damageTemplate.isEmpty()) {
            return result;
        }
        List<Monster> monsters = new ArrayList<>(expectedMap.getAllMonsters());
        monsters.removeIf(monster -> !monster.isAlive()
                || (attackBounds != null && !attackBounds.contains(monster.getPosition())));
        monsters.sort(Comparator
                .comparing((Monster monster) -> !monster.isBoss())
                .thenComparingDouble(monster -> monster.getPosition().distanceSq(attackOrigin))
                .thenComparingInt(Monster::getObjectId));
        for (Monster monster : monsters) {
            result.put(monster.getObjectId(), new ArrayList<>(damageTemplate));
            if (result.size() >= Math.min(15, mobCount)) {
                break;
            }
        }
        return result;
    }

    private static void repeatTrackingAttack(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            int replaySkillId,
            int replayLevel,
            int replayAttackCount,
            int mobCount,
            List<Integer> damageTemplate,
            StatEffect replayEffect,
            Point fixedAttackOrigin
    ) {
        if (!canContinueTrackingAttack(chr, expectedMap)) {
            return;
        }
        Point attackOrigin = fixedAttackOrigin != null
                ? fixedAttackOrigin
                : new Point(chr.getPosition());
        Rectangle attackBounds = replayEffect.hasBoundingBox()
                ? replayEffect.calculateBoundingBox(attackOrigin, attack.direction == 0)
                : null;
        Map<Integer, List<Integer>> damage = collectTrackingTargets(
                expectedMap, attackOrigin, attackBounds, mobCount, damageTemplate
        );
        if (damage.isEmpty()) {
            return;
        }
        int actualAttackCount = replayAttackCount;
        if (replaySkillId == Bowmaster.ARROW_RAIN_FIELD_ATTACK) {
            actualAttackCount = Math.min(
                    15, replayAttackCount + Math.min(8, (damage.size() - 1) * 2)
            );
            if (actualAttackCount != replayAttackCount) {
                for (Map.Entry<Integer, List<Integer>> entry : damage.entrySet()) {
                    entry.setValue(adaptDamageTemplate(
                            entry.getValue(), actualAttackCount, 1, 1
                    ));
                }
            }
        }
        int packedCount = (damage.size() << 4) | (actualAttackCount & 0xF);
        Packet packet = PacketCreator.rangedAttack(
                chr,
                replaySkillId,
                replayLevel,
                attack.stance,
                packedCount,
                0,
                damage,
                attack.speed,
                attack.direction,
                attack.display
        );
        chr.sendPacket(packet);
        expectedMap.broadcastMessage(chr, packet, false, true);
        for (Map.Entry<Integer, List<Integer>> entry : damage.entrySet()) {
            Monster monster = expectedMap.getMonsterByOid(entry.getKey());
            if (monster == null || !monster.isAlive()) {
                continue;
            }
            int total = 0;
            for (Integer hit : entry.getValue()) {
                total = (int) Math.min(Integer.MAX_VALUE, (long) total + decodeRepeatedDamage(hit));
            }
            chr.sendPacket(PacketCreator.damageMonster(monster.getObjectId(), total));
            monster.aggroMonsterDamage(chr, total);
            expectedMap.damageMonster(chr, monster, total);
        }
    }

    private static boolean replayTargetedAttack(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            int replaySkillId,
            int replayAttackCount,
            Map<Integer, List<Integer>> damage
    ) {
        if (!canContinueTrackingAttack(chr, expectedMap) || damage.isEmpty()) {
            return false;
        }
        int packedCount = (Math.min(15, damage.size()) << 4) | (replayAttackCount & 0xF);
        Packet packet = PacketCreator.rangedAttack(
                chr,
                replaySkillId,
                attack.skilllevel,
                attack.stance,
                packedCount,
                0,
                damage,
                attack.speed,
                attack.direction,
                attack.display
        );
        chr.sendPacket(packet);
        expectedMap.broadcastMessage(chr, packet, false, true);
        boolean damaged = false;
        for (Map.Entry<Integer, List<Integer>> entry : damage.entrySet()) {
            Monster monster = expectedMap.getMonsterByOid(entry.getKey());
            if (monster == null || !monster.isAlive()) {
                continue;
            }
            int total = 0;
            for (Integer hit : entry.getValue()) {
                total = (int) Math.min(Integer.MAX_VALUE, (long) total + decodeRepeatedDamage(hit));
            }
            chr.sendPacket(PacketCreator.damageMonster(monster.getObjectId(), total));
            monster.aggroMonsterDamage(chr, total);
            expectedMap.damageMonster(chr, monster, total);
            damaged = true;
        }
        return damaged;
    }

    private static boolean replayTargetedAttacksIndividually(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            int replaySkillId,
            int replayAttackCount,
            List<Monster> targets,
            List<Integer> damageTemplate
    ) {
        boolean damaged = false;
        for (Monster monster : targets) {
            if (monster.isAlive()) {
                Map<Integer, List<Integer>> damage = new LinkedHashMap<>();
                damage.put(monster.getObjectId(), new ArrayList<>(damageTemplate));
                damaged |= replayTargetedAttack(
                        attack,
                        chr,
                        expectedMap,
                        replaySkillId,
                        replayAttackCount,
                        damage
                );
            }
        }
        return damaged;
    }

    private static List<Monster> collectShadowBiteTargets(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            Rectangle attackBounds
    ) {
        Point casterPosition = new Point(chr.getPosition());
        List<Monster> candidates = new ArrayList<>(expectedMap.getAllMonsters());
        candidates.removeIf(monster -> !monster.isAlive()
                || !attackBounds.contains(monster.getPosition()));
        candidates.sort(Comparator
                .comparingDouble((Monster monster) ->
                        monster.getPosition().distanceSq(casterPosition))
                .thenComparingInt(Monster::getObjectId));

        List<Monster> result = new ArrayList<>(SHADOW_BITE_TARGET_COUNT);
        Set<Integer> selectedIds = new HashSet<>();
        for (Integer objectId : attack.allDamage.keySet()) {
            if (result.size() >= SHADOW_BITE_TARGET_COUNT) {
                break;
            }
            Monster monster = expectedMap.getMonsterByOid(objectId);
            if (monster != null && monster.isAlive()
                    && attackBounds.contains(monster.getPosition())
                    && selectedIds.add(objectId)) {
                result.add(monster);
            }
        }
        for (Monster monster : candidates) {
            if (result.size() >= SHADOW_BITE_TARGET_COUNT) {
                break;
            }
            if (selectedIds.add(monster.getObjectId())) {
                result.add(monster);
            }
        }
        return result;
    }

    private static void scheduleShadowBiteAttack(
            AttackInfo attack,
            Character chr,
            List<Integer> baseDamageTemplate
    ) {
        if (baseDamageTemplate.isEmpty()) {
            return;
        }
        MapleMap expectedMap = chr.getMap();
        Skill skill = SkillFactory.getSkill(NightWalker.SHADOW_BITE);
        StatEffect effect = skill.getEffect(chr.getSkillLevel(skill));
        Point castPosition = new Point(chr.getPosition());
        Rectangle attackBounds = effect.hasBoundingBox()
                ? effect.calculateBoundingBox(castPosition, attack.direction == 0)
                : new Rectangle(castPosition.x - 450, castPosition.y - 450, 900, 600);
        List<Monster> targets = collectShadowBiteTargets(
                attack, chr, expectedMap, attackBounds
        );
        if (targets.isEmpty()) {
            return;
        }

        Set<Integer> originalTargetIds = attack.allDamage.keySet();
        List<Monster> additionalNormalTargets = new ArrayList<>();
        List<Monster> additionalBossTargets = new ArrayList<>();
        for (Monster monster : targets) {
            if (originalTargetIds.contains(monster.getObjectId())) {
                continue;
            }
            (monster.isBoss() ? additionalBossTargets : additionalNormalTargets).add(monster);
        }
        List<Integer> normalDamage = adaptDamageTemplate(
                baseDamageTemplate, SHADOW_BITE_ATTACK_COUNT,
                SHADOW_BITE_NORMAL_PERCENT, SHADOW_BITE_NORMAL_PERCENT
        );
        List<Integer> bossDamage = adaptDamageTemplate(
                baseDamageTemplate, SHADOW_BITE_ATTACK_COUNT,
                SHADOW_BITE_NORMAL_PERCENT, SHADOW_BITE_BOSS_PERCENT
        );
        replayTargetedAttacksIndividually(
                attack,
                chr,
                expectedMap,
                NightWalker.SHADOW_BITE_NORMAL_HIT,
                SHADOW_BITE_ATTACK_COUNT,
                additionalNormalTargets,
                normalDamage
        );
        replayTargetedAttacksIndividually(
                attack,
                chr,
                expectedMap,
                NightWalker.SHADOW_BITE_BOSS_HIT,
                SHADOW_BITE_ATTACK_COUNT,
                additionalBossTargets,
                bossDamage
        );

        List<Monster> batTargets = new ArrayList<>(targets.subList(0, Math.min(3, targets.size())));
        Monster ravenousTarget = targets.stream()
                .min(Comparator
                        .comparing((Monster monster) -> !monster.isBoss())
                        .thenComparing(Comparator.comparingLong(Monster::getMaxHp).reversed())
                        .thenComparingDouble(monster ->
                                monster.getPosition().distanceSq(castPosition)))
                .orElse(null);
        List<Integer> shadowBatDamage = adaptDamageTemplate(
                baseDamageTemplate, 1, SHADOW_BITE_NORMAL_PERCENT, 150
        );
        List<Integer> ravenousBatDamage = adaptDamageTemplate(
                baseDamageTemplate, 2, SHADOW_BITE_NORMAL_PERCENT, 480
        );
        TimerManager.getInstance().schedule(() -> {
            if (replayTargetedAttacksIndividually(
                    attack,
                    chr,
                    expectedMap,
                    NightWalker.SHADOW_BITE_SHADOW_BAT,
                    1,
                    batTargets,
                    shadowBatDamage
            )) {
                chr.addHP(Math.max(1, chr.getCurrentMaxHp() / 100));
            }
            if (ravenousTarget != null && replayTargetedAttacksIndividually(
                    attack,
                    chr,
                    expectedMap,
                    NightWalker.SHADOW_BITE_RAVENOUS_BAT,
                    2,
                    Collections.singletonList(ravenousTarget),
                    ravenousBatDamage
            )) {
                chr.addHP(Math.max(1, chr.getCurrentMaxHp() / 100));
            }
        }, SHADOW_BITE_BAT_DELAY_MS);
    }

    private static void scheduleTrackingAttacks(
            AttackInfo attack,
            Character chr,
            int[] attackTimesMs,
            int replaySkillId
    ) {
        MapleMap expectedMap = chr.getMap();
        Skill originalSkill = SkillFactory.getSkill(attack.skill);
        StatEffect originalEffect = originalSkill.getEffect(chr.getSkillLevel(originalSkill));
        Skill replaySkill = SkillFactory.getSkill(replaySkillId);
        int requestedLevel = replaySkillId == Bowmaster.ARROW_RAIN_FIELD_ATTACK
                ? chr.getSkillLevel(Bowmaster.ARROW_RAIN)
                : attack.skilllevel;
        int replayLevel = Math.max(1, Math.min(requestedLevel, replaySkill.getMaxLevel()));
        StatEffect replayEffect = replaySkill.getEffect(replayLevel);
        int replayAttackCount = Math.max(1, Math.min(15, replayEffect.getAttackCount()));
        int mobCount = Math.max(1, Math.min(15, replayEffect.getMobCount()));
        List<Integer> sourceDamageTemplate = copyDamageTemplate(attack);
        if (!hasPositiveDamageTemplate(sourceDamageTemplate)) {
            sourceDamageTemplate = Collections.singletonList(
                    calculateFallbackRangedDamage(chr, originalEffect)
            );
        }
        List<Integer> damageTemplate = adaptDamageTemplate(
                sourceDamageTemplate,
                replayAttackCount,
                originalEffect.getDamage(),
                replayEffect.getDamage()
        );
        Point fixedAttackOrigin = (
                replaySkillId == Bowmaster.ARROW_RAIN_FIELD_ATTACK
                        || usesFixedAttackOrigin(attack.skill)
        )
                ? new Point(chr.getPosition())
                : null;
        for (int attackTimeMs : attackTimesMs) {
            TimerManager.getInstance().schedule(() -> repeatTrackingAttack(
                    attack,
                    chr,
                    expectedMap,
                    replaySkillId,
                    replayLevel,
                    replayAttackCount,
                    mobCount,
                    damageTemplate,
                    replayEffect,
                    fixedAttackOrigin
            ), attackTimeMs);
        }
    }

    private static boolean consumeArrowRainField(AttackInfo attack, Character chr) {
        long now = currentServerTime();
        synchronized (ARROW_RAIN_STATES) {
            ArrowRainState state = ARROW_RAIN_STATES.get(chr);
            if (attack.skill == Bowmaster.ARROW_RAIN) {
                state = new ArrowRainState(now + ARROW_RAIN_DURATION_MS, now);
                ARROW_RAIN_STATES.put(chr, state);
            }
            if (state == null || now >= state.expiresAt) {
                ARROW_RAIN_STATES.remove(chr);
                return false;
            }
            if (attack.skill != Bowmaster.ARROW_RAIN && attack.numAttacked <= 0) {
                return false;
            }
            if (now < state.nextFieldAt) {
                return false;
            }
            state.nextFieldAt = now + ARROW_RAIN_FIELD_COOLDOWN_MS;
            return true;
        }
    }

    private static void triggerArrowRainField(AttackInfo attack, Character chr) {
        if (attack.skill == Bowmaster.ARROW_RAIN_FIELD_ATTACK
                || !consumeArrowRainField(attack, chr)) {
            return;
        }
        scheduleTrackingAttacks(
                attack,
                chr,
                ARROW_RAIN_FIELD_TIMES_MS,
                Bowmaster.ARROW_RAIN_FIELD_ATTACK
        );
    }

    private static List<Monster> collectMercilessWindsTargets(
            MapleMap expectedMap,
            Point castPosition,
            Rectangle attackBounds
    ) {
        List<Monster> monsters = new ArrayList<>(expectedMap.getAllMonsters());
        monsters.removeIf(monster -> !monster.isAlive()
                || (attackBounds != null && !attackBounds.contains(monster.getPosition())));
        monsters.sort(Comparator
                .comparing((Monster monster) -> !monster.isBoss())
                .thenComparing(Comparator.comparingLong(
                        (Monster monster) -> monster.isBoss() ? monster.getMaxHp() : 0L
                ).reversed())
                .thenComparingDouble(monster -> monster.getPosition().distanceSq(castPosition))
                .thenComparingInt(Monster::getObjectId));
        return monsters;
    }

    private static long refreshMercilessWindsDot(Character chr, Monster monster) {
        synchronized (MERCILESS_WINDS_DOT_GENERATIONS) {
            Map<Monster, Long> generations = MERCILESS_WINDS_DOT_GENERATIONS.computeIfAbsent(
                    chr, ignored -> new WeakHashMap<>()
            );
            long generation = generations.getOrDefault(monster, 0L) + 1L;
            generations.put(monster, generation);
            return generation;
        }
    }

    private static boolean isCurrentMercilessWindsDot(
            Character chr,
            Monster monster,
            long generation
    ) {
        synchronized (MERCILESS_WINDS_DOT_GENERATIONS) {
            Map<Monster, Long> generations = MERCILESS_WINDS_DOT_GENERATIONS.get(chr);
            return generations != null && generations.get(monster) != null
                    && generations.get(monster) == generation;
        }
    }

    private static void clearMercilessWindsDot(
            Character chr,
            Monster monster,
            long generation
    ) {
        synchronized (MERCILESS_WINDS_DOT_GENERATIONS) {
            Map<Monster, Long> generations = MERCILESS_WINDS_DOT_GENERATIONS.get(chr);
            if (generations == null || generations.get(monster) == null
                    || generations.get(monster) != generation) {
                return;
            }
            generations.remove(monster);
            if (generations.isEmpty()) {
                MERCILESS_WINDS_DOT_GENERATIONS.remove(chr);
            }
        }
    }

    private static void scheduleMercilessWindsDot(
            Character chr,
            MapleMap expectedMap,
            Monster monster,
            List<Integer> damageTemplate
    ) {
        long generation = refreshMercilessWindsDot(chr, monster);
        int totalDamage = 0;
        for (Integer hit : damageTemplate) {
            totalDamage = (int) Math.min(
                    Integer.MAX_VALUE, (long) totalDamage + decodeRepeatedDamage(hit)
            );
        }
        final int tickDamage = totalDamage;
        for (int tick = 1; tick <= MERCILESS_WINDS_DOT_TICKS; tick++) {
            final boolean finalTick = tick == MERCILESS_WINDS_DOT_TICKS;
            TimerManager.getInstance().schedule(() -> {
                if (!isCurrentMercilessWindsDot(chr, monster, generation)) {
                    return;
                }
                if (!canContinueTrackingAttack(chr, expectedMap) || !monster.isAlive()) {
                    clearMercilessWindsDot(chr, monster, generation);
                    return;
                }
                expectedMap.broadcastMessage(
                        PacketCreator.damageMonster(monster.getObjectId(), tickDamage),
                        monster.getPosition()
                );
                monster.aggroMonsterDamage(chr, tickDamage);
                expectedMap.damageMonster(chr, monster, tickDamage);
                if (finalTick || !monster.isAlive()) {
                    clearMercilessWindsDot(chr, monster, generation);
                }
            }, (long) tick * MERCILESS_WINDS_DOT_INTERVAL_MS);
        }
    }

    private static void tryMercilessWindsProjectile(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            Point castPosition,
            Rectangle attackBounds,
            int projectileIndex,
            long trackingDeadline,
            int replayAttackCount,
            List<Integer> damageTemplate,
            List<Integer> dotDamageTemplate,
            Map<Integer, Integer> targetHitCounts
    ) {
        if (!canContinueTrackingAttack(chr, expectedMap)
                || currentServerTime() >= trackingDeadline) {
            return;
        }
        List<Monster> targets = collectMercilessWindsTargets(
                expectedMap, castPosition, attackBounds
        );
        if (targets.isEmpty()) {
            TimerManager.getInstance().schedule(() -> tryMercilessWindsProjectile(
                    attack, chr, expectedMap, castPosition, attackBounds,
                    projectileIndex, trackingDeadline, replayAttackCount,
                    damageTemplate, dotDamageTemplate, targetHitCounts
            ), MERCILESS_WINDS_SEARCH_INTERVAL_MS);
            return;
        }

        Monster target = targets.get(projectileIndex % targets.size());
        List<Integer> projectileDamage = new ArrayList<>(damageTemplate);
        synchronized (targetHitCounts) {
            int previousHits = targetHitCounts.getOrDefault(target.getObjectId(), 0);
            if (previousHits > 0) {
                scaleDamageLines(
                        projectileDamage, MERCILESS_WINDS_REPEATED_TARGET_PERCENT, 100
                );
            }
            targetHitCounts.put(target.getObjectId(), previousHits + 1);
        }
        Map<Integer, List<Integer>> damage = new LinkedHashMap<>();
        damage.put(target.getObjectId(), projectileDamage);
        if (replayTargetedAttack(
                attack,
                chr,
                expectedMap,
                WindArcher.MERCILESS_WINDS_SPIRIT,
                replayAttackCount,
                damage
        )) {
            scheduleMercilessWindsDot(chr, expectedMap, target, dotDamageTemplate);
            return;
        }
        synchronized (targetHitCounts) {
            int recordedHits = targetHitCounts.getOrDefault(target.getObjectId(), 0);
            if (recordedHits <= 1) {
                targetHitCounts.remove(target.getObjectId());
            } else {
                targetHitCounts.put(target.getObjectId(), recordedHits - 1);
            }
        }
        TimerManager.getInstance().schedule(() -> tryMercilessWindsProjectile(
                attack, chr, expectedMap, castPosition, attackBounds,
                projectileIndex, trackingDeadline, replayAttackCount,
                damageTemplate, dotDamageTemplate, targetHitCounts
        ), MERCILESS_WINDS_SEARCH_INTERVAL_MS);
    }

    private static void scheduleMercilessWinds(AttackInfo attack, Character chr) {
        MapleMap expectedMap = chr.getMap();
        Skill originalSkill = SkillFactory.getSkill(attack.skill);
        StatEffect originalEffect = originalSkill.getEffect(chr.getSkillLevel(originalSkill));
        Skill replaySkill = SkillFactory.getSkill(WindArcher.MERCILESS_WINDS_SPIRIT);
        int replayLevel = Math.max(1, Math.min(attack.skilllevel, replaySkill.getMaxLevel()));
        StatEffect replayEffect = replaySkill.getEffect(replayLevel);
        int replayAttackCount = Math.max(1, Math.min(15, replayEffect.getAttackCount()));
        Point castPosition = new Point(chr.getPosition());
        Rectangle attackBounds = originalEffect.hasBoundingBox()
                ? originalEffect.calculateBoundingBox(castPosition, attack.direction == 0)
                : null;
        List<Integer> sourceDamageTemplate = copyDamageTemplate(attack);
        if (sourceDamageTemplate.isEmpty()) {
            sourceDamageTemplate = Collections.singletonList(
                    calculateFallbackRangedDamage(chr, originalEffect)
            );
        }
        List<Integer> damageTemplate = adaptDamageTemplate(
                sourceDamageTemplate,
                replayAttackCount,
                originalEffect.getDamage(),
                replayEffect.getDamage()
        );
        List<Integer> dotDamageTemplate = adaptDamageTemplate(
                sourceDamageTemplate,
                1,
                originalEffect.getDamage(),
                MERCILESS_WINDS_DOT_PERCENT
        );
        Map<Integer, Integer> targetHitCounts = new LinkedHashMap<>();
        long trackingDeadline = currentServerTime() + MERCILESS_WINDS_TRACKING_DURATION_MS;
        for (int projectileIndex = 0;
                projectileIndex < MERCILESS_WINDS_TIMES_MS.length;
                projectileIndex++) {
            final int currentProjectileIndex = projectileIndex;
            TimerManager.getInstance().schedule(() -> tryMercilessWindsProjectile(
                    attack,
                    chr,
                    expectedMap,
                    castPosition,
                    attackBounds,
                    currentProjectileIndex,
                    trackingDeadline,
                    replayAttackCount,
                    damageTemplate,
                    dotDamageTemplate,
                    targetHitCounts
            ), MERCILESS_WINDS_TIMES_MS[projectileIndex]);
        }
    }

    private static void tryMistralSpiritProjectile(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            Point castPosition,
            Rectangle attackBounds,
            int projectileIndex,
            long trackingDeadline,
            int replaySkillId,
            int replayAttackCount,
            List<Integer> damageTemplate
    ) {
        if (!canContinueTrackingAttack(chr, expectedMap)
                || currentServerTime() >= trackingDeadline) {
            return;
        }
        List<Monster> targets = collectMercilessWindsTargets(
                expectedMap, castPosition, attackBounds
        );
        if (!targets.isEmpty()) {
            Monster target = targets.get(projectileIndex % targets.size());
            Map<Integer, List<Integer>> damage = new LinkedHashMap<>();
            damage.put(target.getObjectId(), new ArrayList<>(damageTemplate));
            if (replayTargetedAttack(
                    attack,
                    chr,
                    expectedMap,
                    replaySkillId,
                    replayAttackCount,
                    damage
            )) {
                return;
            }
        }
        TimerManager.getInstance().schedule(() -> tryMistralSpiritProjectile(
                attack,
                chr,
                expectedMap,
                castPosition,
                attackBounds,
                projectileIndex,
                trackingDeadline,
                replaySkillId,
                replayAttackCount,
                damageTemplate
        ), MISTRAL_SPIRIT_SEARCH_INTERVAL_MS);
    }

    private static void launchMistralSpiritWave(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            Point castPosition,
            Rectangle attackBounds,
            int spiritType,
            long trackingDeadline,
            int replayAttackCount,
            List<Integer> damageTemplate
    ) {
        if (!canContinueTrackingAttack(chr, expectedMap)) {
            return;
        }
        for (int projectileIndex = 0;
                projectileIndex < MISTRAL_SPIRIT_COUNTS[spiritType];
                projectileIndex++) {
            tryMistralSpiritProjectile(
                    attack,
                    chr,
                    expectedMap,
                    castPosition,
                    attackBounds,
                    projectileIndex,
                    trackingDeadline,
                    MISTRAL_SPIRIT_SKILL_IDS[spiritType],
                    replayAttackCount,
                    damageTemplate
            );
        }
    }

    private static void scheduleMistralSpirits(AttackInfo attack, Character chr) {
        MapleMap expectedMap = chr.getMap();
        Skill originalSkill = SkillFactory.getSkill(attack.skill);
        StatEffect originalEffect = originalSkill.getEffect(chr.getSkillLevel(originalSkill));
        Point castPosition = new Point(chr.getPosition());
        Rectangle attackBounds = originalEffect.hasBoundingBox()
                ? originalEffect.calculateBoundingBox(castPosition, attack.direction == 0)
                : new Rectangle(castPosition.x - 1200, castPosition.y - 800, 2400, 1600);
        List<Integer> sourceDamageTemplate = copyDamageTemplate(attack);
        if (sourceDamageTemplate.isEmpty()) {
            sourceDamageTemplate = Collections.singletonList(
                    calculateFallbackRangedDamage(chr, originalEffect)
            );
        }
        List<List<Integer>> damageTemplates = new ArrayList<>(
                MISTRAL_SPIRIT_SKILL_IDS.length
        );
        int[] replayAttackCounts = new int[MISTRAL_SPIRIT_SKILL_IDS.length];
        for (int spiritType = 0;
                spiritType < MISTRAL_SPIRIT_SKILL_IDS.length;
                spiritType++) {
            Skill replaySkill = SkillFactory.getSkill(MISTRAL_SPIRIT_SKILL_IDS[spiritType]);
            int replayLevel = Math.max(
                    1, Math.min(attack.skilllevel, replaySkill.getMaxLevel())
            );
            StatEffect replayEffect = replaySkill.getEffect(replayLevel);
            replayAttackCounts[spiritType] = Math.max(
                    1, Math.min(15, replayEffect.getAttackCount())
            );
            damageTemplates.add(adaptDamageTemplate(
                    sourceDamageTemplate,
                    replayAttackCounts[spiritType],
                    originalEffect.getDamage(),
                    replayEffect.getDamage()
            ));
        }
        long castTime = currentServerTime();
        int waveIndex = 0;
        for (int waveOffset = 0;
                waveOffset < MISTRAL_SPIRIT_DURATION_MS;
                waveOffset += MISTRAL_SPIRIT_INTERVAL_MS) {
            final int spiritType = waveIndex % MISTRAL_SPIRIT_SKILL_IDS.length;
            final long trackingDeadline = Math.min(
                    castTime + MISTRAL_SPIRIT_START_TIME_MS + waveOffset
                            + MISTRAL_SPIRIT_LIFETIMES_MS[spiritType],
                    castTime + MISTRAL_SPIRIT_TOTAL_END_TIME_MS
            );
            TimerManager.getInstance().schedule(() -> launchMistralSpiritWave(
                    attack,
                    chr,
                    expectedMap,
                    castPosition,
                    attackBounds,
                    spiritType,
                    trackingDeadline,
                    replayAttackCounts[spiritType],
                    damageTemplates.get(spiritType)
            ), MISTRAL_SPIRIT_START_TIME_MS + waveOffset
                    + MISTRAL_SPIRIT_ENABLE_DELAYS_MS[spiritType]);
            waveIndex++;
        }
    }

    private static void scheduleNightWalkerSkill(
            AttackInfo attack,
            Character chr,
            List<Integer> shadowBiteDamageTemplate
    ) {
        switch (attack.skill) {
            case NightWalker.SHADOW_BITE:
                scheduleShadowBiteAttack(attack, chr, shadowBiteDamageTemplate);
                break;
            case NightWalker.RAPID_THROW:
                scheduleTrackingAttacks(attack, chr, RAPID_THROW_UPPER_TIMES_MS,
                        NightWalker.RAPID_THROW_UPPER_DART);
                scheduleTrackingAttacks(attack, chr, RAPID_THROW_MIDDLE_TIMES_MS,
                        NightWalker.RAPID_THROW_MIDDLE_DART);
                scheduleTrackingAttacks(attack, chr, RAPID_THROW_LOWER_TIMES_MS,
                        NightWalker.RAPID_THROW_LOWER_DART);
                scheduleTrackingAttacks(attack, chr, new int[]{RAPID_THROW_FINISH_TIME_MS},
                        NightWalker.RAPID_THROW_FINISH);
                break;
            case NightWalker.DARK_OMEN_VI:
                scheduleTrackingAttacks(attack, chr, DARK_OMEN_VI_TIMES_MS,
                        NightWalker.DARK_OMEN_VI_TICK);
                break;
            case NightWalker.DOMINION_VI:
                chr.sendPacket(PacketCreator.showEffect(DOMINION_VIDEO_LAYER));
                scheduleTrackingAttacks(attack, chr, DOMINION_VI_ATTACK_TIMES_MS,
                        NightWalker.DOMINION_VI_TICK);
                break;
            case NightWalker.SILENT_NIGHT:
                chr.sendPacket(PacketCreator.showEffect(SILENT_NIGHT_VIDEO_LAYER));
                scheduleTrackingAttacks(attack, chr, SILENT_NIGHT_OPENING_TIMES_MS,
                        NightWalker.SILENT_NIGHT_DART);
                scheduleTrackingAttacks(attack, chr, SILENT_NIGHT_DART_TIMES_MS,
                        NightWalker.SILENT_NIGHT_PROJECTILE);
                break;
            case NightWalker.STYGIAN_COMMAND:
                chr.sendPacket(PacketCreator.showEffect(STYGIAN_COMMAND_VIDEO_LAYER));
                scheduleTrackingAttacks(attack, chr, STYGIAN_COMMAND_TIMES_MS,
                        NightWalker.STYGIAN_COMMAND_MAIN);
                scheduleTrackingAttacks(attack, chr, STYGIAN_COMMAND_FINISH_TIMES_MS,
                        NightWalker.STYGIAN_COMMAND_FINISH);
                break;
            default:
                break;
        }
    }

    private static void scheduleWindArcherSkill(AttackInfo attack, Character chr) {
        switch (attack.skill) {
            case WindArcher.MERCILESS_WINDS:
                scheduleMercilessWinds(attack, chr);
                break;
            case WindArcher.GALE_BARRIER:
                scheduleTrackingAttacks(attack, chr, GALE_BARRIER_TIMES_MS,
                        WindArcher.GALE_BARRIER_TORNADO);
                break;
            case WindArcher.MONSOON_VI:
                chr.sendPacket(PacketCreator.showEffect(MONSOON_VIDEO_LAYER));
                break;
            case WindArcher.ANEMOI:
                scheduleTrackingAttacks(attack, chr, ANEMOI_TIMES_MS,
                        WindArcher.ANEMOI_GALE);
                break;
            case WindArcher.MISTRAL_SPRING:
                chr.sendPacket(PacketCreator.showEffect(MISTRAL_SPRING_VIDEO_LAYER));
                scheduleTrackingAttacks(attack, chr, MISTRAL_WIND_BLADE_TIMES_MS,
                        WindArcher.MISTRAL_WIND_BLADE);
                scheduleMistralSpirits(attack, chr);
                break;
            case WindArcher.ELEMENTAL_TEMPEST:
                chr.sendPacket(PacketCreator.showEffect(ELEMENTAL_TEMPEST_VIDEO_LAYER));
                scheduleTrackingAttacks(attack, chr, ELEMENTAL_TEMPEST_WAVE_TIMES_MS,
                        WindArcher.ELEMENTAL_TEMPEST_WAVE);
                scheduleTrackingAttacks(attack, chr, ELEMENTAL_TEMPEST_ARROW_TIMES_MS,
                        WindArcher.ELEMENTAL_TEMPEST_ARROW_RAIN);
                break;
            default:
                break;
        }
    }

    @Override
    public void handlePacket(InPacket p, Client c) {
        Character chr = c.getPlayer();
        
        /*long timeElapsed = currentServerTime() - chr.getAutobanManager().getLastSpam(8);
        if(timeElapsed < 300) {
            AutobanFactory.FAST_ATTACK.alert(chr, "Time: " + timeElapsed);
        }
        chr.getAutobanManager().spam(8);*/

        AttackInfo attack = parseDamage(p, chr, true, false);
        boolean fourSeasonsRainFrenzy = hasFourSeasonsRainFrenzy(chr, attack);
        applyShadowBitePassive(attack, chr);
        List<Integer> shadowBiteDamageTemplate = attack.skill == NightWalker.SHADOW_BITE
                ? copyDamageTemplate(attack)
                : Collections.emptyList();
        applyShadowBiteBossDamage(attack, chr.getMap());

        if (chr.getBuffEffect(BuffStat.MORPH) != null) {
            if (chr.getBuffEffect(BuffStat.MORPH).isMorphWithoutAttack()) {
                // How are they attacking when the client won't let them?
                chr.getClient().disconnect(false, false);
                return;
            }
        }

        if (MapId.isDojo(chr.getMap().getId()) && attack.numAttacked > 0) {
            chr.setDojoEnergy(chr.getDojoEnergy() + GameConfig.getServerInt("dojo_energy_atk"));
            c.sendPacket(PacketCreator.getEnergy("energy", chr.getDojoEnergy()));
        }

        if (attack.skill == Buccaneer.ENERGY_ORB || attack.skill == ThunderBreaker.SPARK || attack.skill == Shadower.TAUNT || attack.skill == NightLord.TAUNT) {
            chr.getMap().broadcastMessage(chr, PacketCreator.rangedAttack(chr, attack.skill, attack.skilllevel, attack.stance, attack.numAttackedAndDamage, 0, attack.allDamage, attack.speed, attack.direction, attack.display), false);
            applyAttack(attack, chr, 1);
        } else if (attack.skill == ThunderBreaker.SHARK_WAVE && chr.getSkillLevel(ThunderBreaker.SHARK_WAVE) > 0) {
            chr.getMap().broadcastMessage(chr, PacketCreator.rangedAttack(chr, attack.skill, attack.skilllevel, attack.stance, attack.numAttackedAndDamage, 0, attack.allDamage, attack.speed, attack.direction, attack.display), false);
            applyAttack(attack, chr, 1);

            for (int i = 0; i < attack.numAttacked; i++) {
                chr.handleEnergyChargeGain();
            }
        } else if (attack.skill == Aran.COMBO_SMASH || attack.skill == Aran.COMBO_FENRIR || attack.skill == Aran.COMBO_TEMPEST) {
            chr.getMap().broadcastMessage(chr, PacketCreator.rangedAttack(chr, attack.skill, attack.skilllevel, attack.stance, attack.numAttackedAndDamage, 0, attack.allDamage, attack.speed, attack.direction, attack.display), false);
            if (attack.skill == Aran.COMBO_SMASH && chr.getCombo() >= 30) {
                chr.setCombo((short) 0);
                applyAttack(attack, chr, 1);
            } else if (attack.skill == Aran.COMBO_FENRIR && chr.getCombo() >= 100) {
                chr.setCombo((short) 0);
                applyAttack(attack, chr, 2);
            } else if (attack.skill == Aran.COMBO_TEMPEST && chr.getCombo() >= 200) {
                chr.setCombo((short) 0);
                applyAttack(attack, chr, 4);
            }
        } else {
            Item weapon = chr.getInventory(InventoryType.EQUIPPED).getItem((short) -11);
            WeaponType type = ItemInformationProvider.getInstance().getWeaponType(weapon.getItemId());
            if (type == WeaponType.NOT_A_WEAPON) {
                return;
            }
            short slot = -1;
            int projectile = 0;
            short bulletCount = 1;
            short supplement = 0;   //用于补充平衡之怒的变量
            StatEffect effect = null;
            if (attack.skill != 0) {
                effect = attack.getAttackEffect(chr, null);
                bulletCount = effect.getBulletCount();
                if (effect.getCooldown() > 0) {
                    c.sendPacket(PacketCreator.skillCooldown(attack.skill, effect.getCooldown()));
                }

                if (attack.skill == 4111004) {   // shadow meso
                    bulletCount = 0;

                    int money = effect.getMoneyCon();
                    if (money != 0) {
                        int moneyMod = money / 2;
                        money += Randomizer.nextInt(moneyMod);
                        if (money > chr.getMeso()) {
                            money = chr.getMeso();
                        }
                        chr.gainMeso(-money, false);
                    }
                }
            }
            boolean hasShadowPartner = chr.getBuffedValue(BuffStat.SHADOWPARTNER) != null;
            if (hasShadowPartner && !isNightWalkerVViSkill(attack.skill)
                    && !isWindArcherVViSkill(attack.skill)) {
                bulletCount *= 2;
            }
            Inventory inv = chr.getInventory(InventoryType.USE);
            for (short i = 1; i <= inv.getSlotLimit(); i++) {
                Item item = inv.getItem(i);
                if (item != null) {
                    int id = item.getItemId();
                    slot = item.getPosition();

                    boolean bow = ItemConstants.isArrowForBow(id);
                    boolean cbow = ItemConstants.isArrowForCrossBow(id);

                    if (id == ItemId.BALANCED_FURY && (item.getQuantity() - bulletCount) <= 10) {   //平衡之怒低于10，则自动补充，如果设置数值过低时，会造成出拳平A
                        supplement = (short) -ItemInformationProvider.getInstance().getSlotMax(c,id);  //设定补充到限制的最高数值
                    }

                    if (item.getQuantity() >= bulletCount) { //Fixes the bug where you can't use your last arrow.
                        if (type == WeaponType.CLAW && ItemConstants.isThrowingStar(id) && weapon.getItemId() != ItemId.MAGICAL_MITTEN) {
                            //这段判断不知道干啥用的，里面又没有内容，看样子是判定 物品ID = 月牙镖 或 平衡之怒 且 等级小于70，或 月牙镖 且 等级小于50
                            if (((id == ItemId.HWABI_THROWING_STARS || id == ItemId.BALANCED_FURY) && chr.getLevel() < 70) || (id == ItemId.CRYSTAL_ILBI_THROWING_STARS && chr.getLevel() < 50)) {
                            } else {
                                projectile = id;
                                break;
                            }
                        } else if ((type == WeaponType.GUN && ItemConstants.isBullet(id))) {
                            if (id == ItemId.BLAZE_CAPSULE || id == ItemId.GLAZE_CAPSULE) {
                                if (chr.getLevel() >= 70) {
                                    projectile = id;
                                    break;
                                }
                            } else if (chr.getLevel() > (id % 10) * 20 + 9) {
                                projectile = id;
                                break;
                            }
                        } else if ((type == WeaponType.BOW && bow) || (type == WeaponType.CROSSBOW && cbow) || (weapon.getItemId() == ItemId.MAGICAL_MITTEN && (bow || cbow))) {
                            projectile = id;
                            break;
                        }
                    }
                }
            }
            boolean soulArrow = chr.getBuffedValue(BuffStat.SOULARROW) != null;
            boolean shadowClaw = chr.getBuffedValue(BuffStat.SHADOW_CLAW) != null;
            if (projectile != 0) {
                if (!soulArrow && !shadowClaw
                        && attack.skill != NightWalker.SHADOW_BITE
                        && attack.skill != 11101004
                        && attack.skill != 15111007
                        && attack.skill != 14101006) {
                    short bulletConsume = (isNightWalkerVViSkill(attack.skill)
                            || isWindArcherVViSkill(attack.skill)
                            || isMarksmanVViRangedSkill(attack.skill)) ? 1 : bulletCount;

                    if (effect != null && effect.getBulletConsume() != 0) {
                        bulletConsume = (byte) (effect.getBulletConsume() * (hasShadowPartner ? 2 : 1));
                    }
                    if (supplement < 0 ) {
                        bulletConsume = supplement;     //将消耗飞镖设为补充飞镖
                    }
                    if (slot < 0) {
                        log.warn("<ERROR> Projectile to use was unable to be found.");
                    } else {
                        InventoryManipulator.removeFromSlot(c, InventoryType.USE, slot, bulletConsume, false, true);    //减去消耗品指定栏位物品数量
                    }
                }
            }

            if (projectile != 0 || soulArrow || isMarksmanVViRangedSkill(attack.skill)
                    || attack.skill == 11101004 || attack.skill == 15111007
                    || attack.skill == 14101006 || attack.skill == 4111004
                    || attack.skill == 13101005) {
                int visProjectile = projectile; //visible projectile sent to players
                if (ItemConstants.isThrowingStar(projectile)) {
                    Inventory cash = chr.getInventory(InventoryType.CASH);
                    for (int i = 1; i <= cash.getSlotLimit(); i++) { // impose order...
                        Item item = cash.getItem((short) i);
                        if (item != null) {
                            if (item.getItemId() / 1000 == 5021) {
                                visProjectile = item.getItemId();
                                break;
                            }
                        }
                    }
                } else if (soulArrow || isWindArcherVViSkill(attack.skill)
                        || isMarksmanVViRangedSkill(attack.skill)
                        || attack.skill == 3111004 || attack.skill == 3211004
                        || attack.skill == 11101004 || attack.skill == 15111007
                        || attack.skill == 14101006 || attack.skill == 13101005) {
                    visProjectile = 0;
                }
                if (ExplorerOtherSkillCompat.hidesNativeProjectile(attack.skill)) {
                    visProjectile = 0;
                }

                final Packet packet;
                switch (attack.skill) {
                    case 3121004: // Hurricane
                    case 3221001: // Pierce
                    case 5221004: // Rapid Fire
                    case 13111002: // KoC Hurricane
                        packet = PacketCreator.rangedAttack(chr, attack.skill, attack.skilllevel, attack.rangedirection, attack.numAttackedAndDamage, visProjectile, attack.allDamage, attack.speed, attack.direction, attack.display);
                        break;
                    default:
                        packet = PacketCreator.rangedAttack(chr, attack.skill, attack.skilllevel, attack.stance, attack.numAttackedAndDamage, visProjectile, attack.allDamage, attack.speed, attack.direction, attack.display);
                        break;
                }
                if (!fourSeasonsRainFrenzy) {
                    chr.getMap().broadcastMessage(chr, packet, false, true);
                }
                String explorerVideoLayer = ExplorerOtherSkillCompat.videoLayer(attack.skill);
                if (explorerVideoLayer != null) {
                    chr.sendPacket(PacketCreator.showEffect(explorerVideoLayer));
                }

                if (attack.skill != 0) {
                    Skill skill = SkillFactory.getSkill(attack.skill);
                    StatEffect effect_ = skill.getEffect(chr.getSkillLevel(skill));
                    if (effect_.getCooldown() > 0) {
                        if (chr.skillIsCooling(attack.skill)) {
                            return;
                        } else {
                            c.sendPacket(PacketCreator.skillCooldown(attack.skill, effect_.getCooldown()));
                            chr.addCooldown(attack.skill, currentServerTime(), SECONDS.toMillis(effect_.getCooldown()));
                        }
                    }
                }

                if (chr.getSkillLevel(SkillFactory.getSkill(NightWalker.VANISH)) > 0 && chr.getBuffedValue(BuffStat.DARKSIGHT) != null && attack.numAttacked > 0 && chr.getBuffSource(BuffStat.DARKSIGHT) != 9101004) {
                    chr.cancelEffectFromBuffStat(BuffStat.DARKSIGHT);
                    chr.cancelBuffStats(BuffStat.DARKSIGHT);
                } else if (chr.getSkillLevel(SkillFactory.getSkill(WindArcher.WIND_WALK)) > 0 && chr.getBuffedValue(BuffStat.WIND_WALK) != null && attack.numAttacked > 0) {
                    chr.cancelEffectFromBuffStat(BuffStat.WIND_WALK);
                    chr.cancelBuffStats(BuffStat.WIND_WALK);
                }

                if (fourSeasonsRainFrenzy || usesScheduledDamageOnly(attack.skill)) {
                    if (fourSeasonsRainFrenzy) {
                        consumeFourSeasonsRainFrenzy(chr, attack);
                    }
                    applyAttackCostOnly(attack, chr, bulletCount);
                } else {
                    applyAttack(attack, chr, bulletCount);
                }
                if (isNightWalkerVViSkill(attack.skill)) {
                    scheduleNightWalkerSkill(attack, chr, shadowBiteDamageTemplate);
                }
                if (isWindArcherVViSkill(attack.skill)) {
                    scheduleWindArcherSkill(attack, chr);
                }
                triggerArrowRainField(attack, chr);
                ExplorerOtherSkillCompat.Replay[] explorerReplays =
                        fourSeasonsRainFrenzy
                                ? ExplorerOtherSkillCompat.multiAttacks(4121024)
                                : ExplorerOtherSkillCompat.multiAttacks(attack.skill);
                if (explorerReplays != null) {
                    for (ExplorerOtherSkillCompat.Replay replay : explorerReplays) {
                        scheduleTrackingAttacks(
                                attack, chr, replay.timesMs(), replay.skillId()
                        );
                    }
                }
                if (!fourSeasonsRainFrenzy) {
                    markFourSeasonsRainHit(chr, attack);
                }
            }
        }
    }
}
