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
    private static final int[] RAPID_THROW_UPPER_TIMES_MS = intervalTimes(0, 360, 2160);
    private static final int[] RAPID_THROW_MIDDLE_TIMES_MS = intervalTimes(120, 360, 2280);
    private static final int[] RAPID_THROW_LOWER_TIMES_MS = intervalTimes(240, 360, 2040);
    private static final int[] QUINTUPLE_THROW_VI_TIMES_MS = {450};
    private static final int SHADOW_BITE_PASSIVE_PERCENT = 120;
    private static final int SHADOW_BITE_NORMAL_PERCENT = 990;
    private static final int SHADOW_BITE_BOSS_PERCENT = 2673;
    private static final int SHADOW_BITE_BAT_DELAY_MS = 720;
    private static final long QUINTUPLE_THROW_VI_ALTERNATE_INTERVAL_MS = SECONDS.toMillis(6);
    private static final Map<Character, Long> QUINTUPLE_THROW_VI_ALTERNATE_READY_AT =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final int[] DARK_OMEN_VI_TIMES_MS = intervalTimes(270, 270, 7020);
    private static final int[] SILENT_NIGHT_OPENING_TIMES_MS = intervalTimes(3180, 30, 3420);
    private static final int[] SILENT_NIGHT_DART_TIMES_MS = intervalTimes(4020, 30, 4740);
    private static final int[] STYGIAN_COMMAND_TIMES_MS = intervalTimes(900, 30, 1200);
    private static final int[] STYGIAN_COMMAND_FINISH_TIMES_MS = intervalTimes(1890, 30, 2280);

    private static int[] intervalTimes(int first, int interval, int last) {
        int[] result = new int[((last - first) / interval) + 1];
        for (int index = 0; index < result.length; index++) {
            result[index] = first + (index * interval);
        }
        return result;
    }

    private static boolean isNightWalkerVViSkill(int skillId) {
        return (skillId >= NightWalker.SHADOW_BITE && skillId <= NightWalker.SHADOW_BITE_RAVENOUS_BAT)
                || (skillId >= NightWalker.DARK_OMEN_VI && skillId <= NightWalker.DARK_OMEN_VI_TICK)
                || (skillId >= NightWalker.DOMINION_VI && skillId <= NightWalker.STYGIAN_COMMAND_FINISH);
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
        return skillId == NightWalker.RAPID_THROW
                || skillId == NightWalker.QUINTUPLE_THROW_VI
                || skillId == NightWalker.SILENT_NIGHT
                || skillId == NightWalker.STYGIAN_COMMAND;
    }

    private static boolean useQuintupleThrowAlternate(Character chr) {
        long now = currentServerTime();
        synchronized (QUINTUPLE_THROW_VI_ALTERNATE_READY_AT) {
            Long readyAt = QUINTUPLE_THROW_VI_ALTERNATE_READY_AT.get(chr);
            if (readyAt != null && readyAt > now) {
                return false;
            }
            QUINTUPLE_THROW_VI_ALTERNATE_READY_AT.put(
                    chr,
                    now + QUINTUPLE_THROW_VI_ALTERNATE_INTERVAL_MS
            );
            return true;
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
            Character chr,
            MapleMap expectedMap,
            int mobCount,
            List<Integer> damageTemplate
    ) {
        Map<Integer, List<Integer>> result = new LinkedHashMap<>();
        if (damageTemplate.isEmpty()) {
            return result;
        }
        Point casterPosition = new Point(chr.getPosition());
        List<Monster> monsters = new ArrayList<>(expectedMap.getAllMonsters());
        monsters.removeIf(monster -> !monster.isAlive());
        monsters.sort(Comparator
                .comparing((Monster monster) -> !monster.isBoss())
                .thenComparingDouble(monster -> monster.getPosition().distanceSq(casterPosition))
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
            int replayAttackCount,
            int mobCount,
            List<Integer> damageTemplate
    ) {
        if (!canContinueTrackingAttack(chr, expectedMap)) {
            return;
        }
        Map<Integer, List<Integer>> damage = collectTrackingTargets(
                chr, expectedMap, mobCount, damageTemplate
        );
        if (damage.isEmpty()) {
            return;
        }
        int packedCount = (damage.size() << 4) | (replayAttackCount & 0xF);
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

        List<Monster> result = new ArrayList<>(15);
        Set<Integer> selectedIds = new HashSet<>();
        for (Integer objectId : attack.allDamage.keySet()) {
            Monster monster = expectedMap.getMonsterByOid(objectId);
            if (monster != null && monster.isAlive()
                    && attackBounds.contains(monster.getPosition())
                    && selectedIds.add(objectId)) {
                result.add(monster);
            }
        }
        for (Monster monster : candidates) {
            if (result.size() >= 15) {
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
                baseDamageTemplate, 14, SHADOW_BITE_NORMAL_PERCENT, SHADOW_BITE_NORMAL_PERCENT
        );
        List<Integer> bossDamage = adaptDamageTemplate(
                baseDamageTemplate, 14, SHADOW_BITE_NORMAL_PERCENT, SHADOW_BITE_BOSS_PERCENT
        );
        replayTargetedAttacksIndividually(
                attack,
                chr,
                expectedMap,
                NightWalker.SHADOW_BITE_NORMAL_HIT,
                14,
                additionalNormalTargets,
                normalDamage
        );
        replayTargetedAttacksIndividually(
                attack,
                chr,
                expectedMap,
                NightWalker.SHADOW_BITE_BOSS_HIT,
                14,
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
        int replayLevel = Math.max(1, Math.min(attack.skilllevel, replaySkill.getMaxLevel()));
        StatEffect replayEffect = replaySkill.getEffect(replayLevel);
        int replayAttackCount = Math.max(1, Math.min(15, replayEffect.getAttackCount()));
        int mobCount = Math.max(1, Math.min(15, replayEffect.getMobCount()));
        List<Integer> damageTemplate = adaptDamageTemplate(
                copyDamageTemplate(attack),
                replayAttackCount,
                originalEffect.getDamage(),
                replayEffect.getDamage()
        );
        for (int attackTimeMs : attackTimesMs) {
            TimerManager.getInstance().schedule(() -> repeatTrackingAttack(
                    attack,
                    chr,
                    expectedMap,
                    replaySkillId,
                    replayAttackCount,
                    mobCount,
                    damageTemplate
            ), attackTimeMs);
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
                scheduleTrackingAttacks(attack, chr, new int[]{2400}, NightWalker.RAPID_THROW_FINISH);
                break;
            case NightWalker.QUINTUPLE_THROW_VI:
                if (useQuintupleThrowAlternate(chr)) {
                    scheduleTrackingAttacks(attack, chr, new int[]{0},
                            NightWalker.QUINTUPLE_THROW_VI_ALTERNATE);
                    scheduleTrackingAttacks(attack, chr, QUINTUPLE_THROW_VI_TIMES_MS,
                            NightWalker.QUINTUPLE_THROW_VI_TRACKING);
                } else {
                    scheduleTrackingAttacks(attack, chr, new int[]{0},
                            NightWalker.QUINTUPLE_THROW_VI_NORMAL);
                    scheduleTrackingAttacks(attack, chr, QUINTUPLE_THROW_VI_TIMES_MS,
                            NightWalker.QUINTUPLE_THROW_VI_ENHANCED);
                }
                break;
            case NightWalker.DARK_OMEN_VI:
                scheduleTrackingAttacks(attack, chr, DARK_OMEN_VI_TIMES_MS,
                        NightWalker.DARK_OMEN_VI_TICK);
                break;
            case NightWalker.DOMINION_VI:
                chr.sendPacket(PacketCreator.showEffect(DOMINION_VIDEO_LAYER));
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

    @Override
    public void handlePacket(InPacket p, Client c) {
        Character chr = c.getPlayer();
        
        /*long timeElapsed = currentServerTime() - chr.getAutobanManager().getLastSpam(8);
        if(timeElapsed < 300) {
            AutobanFactory.FAST_ATTACK.alert(chr, "Time: " + timeElapsed);
        }
        chr.getAutobanManager().spam(8);*/

        AttackInfo attack = parseDamage(p, chr, true, false);
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
            if (hasShadowPartner && !isNightWalkerVViSkill(attack.skill)) {
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
                    short bulletConsume = isNightWalkerVViSkill(attack.skill) ? 1 : bulletCount;

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

            if (projectile != 0 || soulArrow || attack.skill == 11101004 || attack.skill == 15111007 || attack.skill == 14101006 || attack.skill == 4111004 || attack.skill == 13101005) {
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
                } else if (soulArrow || attack.skill == 3111004 || attack.skill == 3211004 || attack.skill == 11101004 || attack.skill == 15111007 || attack.skill == 14101006 || attack.skill == 13101005) {
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
                chr.getMap().broadcastMessage(chr, packet, false, true);

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

                if (usesScheduledDamageOnly(attack.skill)) {
                    applyAttackCostOnly(attack, chr, bulletCount);
                } else {
                    applyAttack(attack, chr, bulletCount);
                }
                if (isNightWalkerVViSkill(attack.skill)) {
                    scheduleNightWalkerSkill(attack, chr, shadowBiteDamageTemplate);
                }
            }
        }
    }
}
