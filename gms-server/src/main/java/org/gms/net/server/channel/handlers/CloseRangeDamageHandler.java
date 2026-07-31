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
import org.gms.client.Job;
import org.gms.client.Skill;
import org.gms.client.SkillFactory;
import org.gms.config.GameConfig;
import org.gms.constants.game.GameConstants;
import org.gms.constants.id.MapId;
import org.gms.constants.skills.Crusader;
import org.gms.constants.skills.DawnWarrior;
import org.gms.constants.skills.DragonKnight;
import org.gms.constants.skills.Hero;
import org.gms.constants.skills.NightWalker;
import org.gms.constants.skills.Rogue;
import org.gms.constants.skills.ThunderBreaker;
import org.gms.constants.skills.WindArcher;
import org.gms.net.packet.InPacket;
import org.gms.net.packet.Packet;
import org.gms.server.StatEffect;
import org.gms.server.TimerManager;
import org.gms.server.life.Monster;
import org.gms.server.maps.MapObject;
import org.gms.server.maps.MapObjectType;
import org.gms.server.maps.MapleMap;
import org.gms.util.PacketCreator;
import org.gms.util.Pair;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static java.util.concurrent.TimeUnit.SECONDS;

public final class CloseRangeDamageHandler extends AbstractDealDamageHandler {
    private static final Logger log = LoggerFactory.getLogger(CloseRangeDamageHandler.class);
    private static final String ANIMATED_ATTACK_LOG_VERSION = "DW_ANIM v3";
    private static final int SWORD_ILLUSION_HIT_DELAY_MS = 1000;
    private static final int DEATH_FAULT_HIT_DELAY_MS = 1000;
    private static final String DEATH_FAULT_FIELD_EFFECT = "customSkill/deathFault/full";
    private static final String GALAXY_STAR_BURST_VIDEO_LAYER =
            "customSkill/dawnWarrior/galaxyStarBurstVideoLayer";
    private static final String ECLIPSE_FORCE_VIDEO_LAYER =
            "customSkill/dawnWarrior/eclipseForceVideoLayer";
    private static final String SOUL_ECLIPSE_VIDEO_LAYER =
            "customSkill/dawnWarrior/soulEclipseVideoLayer";
    private static final String GOD_OF_THE_SEA_VI_VIDEO_LAYER =
            "customSkill/thunderBreaker/godOfSeaViVideoLayer";
    private static final String WAVE_RIDING_THUNDER_VIDEO_LAYER =
            "customSkill/thunderBreaker/waveRidingThunderVideoLayer";
    private static final String SWIFT_ANNIHILATION_VIDEO_LAYER =
            "customSkill/thunderBreaker/swiftAnnihilationVideoLayer";
    private static final int[] GALAXY_STAR_BURST_ATTACK_TIMES_MS = {
        1200, 1380, 1560, 1740, 3180, 3360, 3540, 3720, 4560, 4740, 6240, 6420, 6600, 6780
    };
    private static final int[] ECLIPSE_FORCE_ATTACK_TIMES_MS = {
        1200, 1380, 1560, 1740, 1920, 2100, 2280, 2340,
        3120, 3300, 3480, 3660, 3840, 4020, 4200, 4260
    };
    private static final int[] SOUL_ECLIPSE_ATTACK_TIMES_MS = {
        1200, 1800, 2400, 3000, 3600, 4200, 4800, 5400, 6000, 6600,
        7200, 7800, 8400, 9000, 9600, 10200, 10800, 11400, 12000, 12600,
        13200, 13800, 14400, 15000, 15600, 16200, 16800, 17400, 18000, 18600,
        19200, 19800
    };
    private static final int[] COSMOS_ATTACK_TIMES_MS = {
        450, 900, 1350, 1800, 2250, 2700, 3150, 3600, 4050, 4500, 4950,
        5400, 5850, 6300, 6750, 7200, 7650, 8100, 8550, 9000, 9450, 9900,
        10350, 10800, 11250, 11700, 12150, 12600, 13050, 13500, 13950, 14400,
        14850
    };
    private static final int[] SEA_DRAGON_SPIRAL_TIMES_MS = intervalTimes(0, 240, 23760);
    private static final int[] LIGHTNING_SPEAR_STRIKE_1_TIMES_MS = {0, 1080};
    private static final int[] LIGHTNING_SPEAR_STRIKE_2_TIMES_MS = {180, 1260};
    private static final int[] LIGHTNING_SPEAR_STRIKE_3_TIMES_MS = {360, 1440};
    private static final int[] LIGHTNING_SPEAR_STRIKE_4_TIMES_MS = {540, 1620};
    private static final int[] LIGHTNING_SPEAR_STRIKE_5_TIMES_MS = {720, 1800};
    private static final int[] LIGHTNING_SPEAR_STRIKE_6_TIMES_MS = {900, 1980};
    private static final int[] LIGHTNING_SPEAR_THUNDER_TIMES_MS = {360, 900, 1440, 1980};
    private static final int[] WAVE_RIDING_THUNDER_OPENING_TIMES_MS = {
        300, 360, 420, 480, 540, 600, 660, 720, 780, 840, 900, 960,
        1020, 1080, 1140, 1200, 1260, 1320, 1380, 1440, 1500, 2940, 3060, 3180,
        3300, 3840, 3900, 3960, 4020, 4080, 4140, 4200
    };
    private static final int[] WAVE_RIDING_THUNDER_SHOCK_TIMES_MS = {
        4680, 4740, 4800, 4860, 4920, 4980, 5040, 5100, 5160, 5220, 5460, 5490,
        5520, 5550, 5580, 5610, 5640, 5670, 5700, 5730, 5910, 5940, 5970, 6000,
        6030, 6060, 6090, 6120, 6150, 6180, 6210, 6240, 6270, 6300, 6330, 6360,
        6390, 6420, 6450, 6480, 6510, 6540, 6570, 6600, 6630, 6660, 6690, 6720,
        6750, 6780, 6810, 6840, 6870, 6900, 6930, 6960, 6990, 7020, 7050, 7080,
        7110, 7140
    };
    private static final int[] SWIFT_ANNIHILATION_OPENING_TIMES_MS = {
        180, 240, 300, 360, 420, 480, 540, 600, 660, 720, 780
    };
    private static final int[] SWIFT_ANNIHILATION_SURGE_TIMES_MS = {
        1620, 1680, 1740, 1800, 1860, 1920, 1980, 2010, 2040,
        2070, 2100, 2130, 2160, 2190, 2220, 2250, 2280, 2310
    };

    private static int[] intervalTimes(int first, int interval, int last) {
        int[] result = new int[((last - first) / interval) + 1];
        for (int index = 0; index < result.length; index++) {
            result[index] = first + (index * interval);
        }
        return result;
    }

    private static boolean canContinueAnimatedAttack(Character chr, MapleMap expectedMap) {
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

    private static int calculateFallbackCloseDamage(Character chr, StatEffect effect) {
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
            result.add(encodeRepeatedDamage(
                    (int) Math.min(Integer.MAX_VALUE, scaled), original < 0
            ));
        }
        return result;
    }

    private static List<Integer> copyCapturedDamageTemplate(AttackInfo attack) {
        for (List<Integer> damage : attack.allDamage.values()) {
            if (damage != null && !damage.isEmpty()) {
                return new ArrayList<>(damage);
            }
        }
        return Collections.emptyList();
    }

    private static Map<Integer, List<Integer>> collectAnimatedAttackTargets(
            AttackInfo attack,
            MapleMap expectedMap,
            Rectangle attackBounds,
            int mobCount,
            List<Integer> damageTemplate
    ) {
        Map<Integer, List<Integer>> liveDamage = new LinkedHashMap<>();
        if (attackBounds != null && !damageTemplate.isEmpty()) {
            List<MapObject> targets = expectedMap.getMapObjectsInBox(
                    attackBounds,
                    Collections.singletonList(MapObjectType.MONSTER)
            );
            for (MapObject target : targets) {
                Monster monster = (Monster) target;
                if (monster.isAlive()) {
                    liveDamage.put(monster.getObjectId(), new ArrayList<>(damageTemplate));
                    if (liveDamage.size() >= mobCount) {
                        break;
                    }
                }
            }
            return liveDamage;
        }

        for (Map.Entry<Integer, List<Integer>> entry : attack.allDamage.entrySet()) {
            Monster monster = expectedMap.getMonsterByOid(entry.getKey());
            if (monster != null && monster.isAlive() && entry.getValue() != null) {
                liveDamage.put(entry.getKey(), entry.getValue());
            }
        }
        return liveDamage;
    }

    private static int repeatCapturedAttack(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            Rectangle attackBounds,
            int mobCount,
            List<Integer> damageTemplate
    ) {
        if (!canContinueAnimatedAttack(chr, expectedMap)) {
            return -1;
        }
        Map<Integer, List<Integer>> liveDamage = collectAnimatedAttackTargets(
                attack,
                expectedMap,
                attackBounds,
                mobCount,
                damageTemplate
        );
        if (liveDamage.isEmpty()) {
            return 0;
        }

        int packedCount = (Math.min(15, liveDamage.size()) << 4) | (attack.numDamage & 0xF);
        Packet repeatedAttack = PacketCreator.closeRangeAttack(
                chr,
                attack.skill,
                attack.skilllevel,
                attack.stance,
                packedCount,
                liveDamage,
                attack.speed,
                attack.direction,
                attack.display
        );
        chr.sendPacket(repeatedAttack);
        expectedMap.broadcastMessage(chr, repeatedAttack, false, true);

        for (Map.Entry<Integer, List<Integer>> entry : liveDamage.entrySet()) {
            Monster monster = expectedMap.getMonsterByOid(entry.getKey());
            if (monster == null || !monster.isAlive()) {
                continue;
            }
            int damage = 0;
            for (Integer hit : entry.getValue()) {
                damage = (int) Math.min(Integer.MAX_VALUE, (long) damage + decodeRepeatedDamage(hit));
            }
            chr.sendPacket(PacketCreator.damageMonster(monster.getObjectId(), damage));
            monster.aggroMonsterDamage(chr, damage);
            expectedMap.damageMonster(chr, monster, damage);
        }
        return liveDamage.size();
    }

    private static void showCapturedDamageNumbers(AttackInfo attack, Character chr, MapleMap expectedMap) {
        for (Map.Entry<Integer, List<Integer>> entry : attack.allDamage.entrySet()) {
            Monster monster = expectedMap.getMonsterByOid(entry.getKey());
            if (monster == null || !monster.isAlive() || entry.getValue() == null) {
                continue;
            }
            int damage = 0;
            for (Integer hit : entry.getValue()) {
                damage = (int) Math.min(Integer.MAX_VALUE, (long) damage + decodeRepeatedDamage(hit));
            }
            chr.sendPacket(PacketCreator.damageMonster(monster.getObjectId(), damage));
        }
    }

    private static boolean usesFixedThunderBreakerOrigin(int skillId) {
        return skillId == ThunderBreaker.LIGHTNING_SPEAR_MULTISTRIKE
                || skillId == ThunderBreaker.WAVE_RIDING_THUNDER
                || skillId == ThunderBreaker.SWIFT_ANNIHILATION;
    }

    private static Map<Integer, List<Integer>> collectTrackingCloseTargets(
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

    private static void repeatTrackingCloseAttack(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            int replaySkillId,
            int replayAttackCount,
            int mobCount,
            List<Integer> damageTemplate,
            StatEffect replayEffect,
            Point fixedAttackOrigin
    ) {
        if (!canContinueAnimatedAttack(chr, expectedMap)) {
            return;
        }
        Point attackOrigin = fixedAttackOrigin != null
                ? fixedAttackOrigin
                : new Point(chr.getPosition());
        Rectangle attackBounds = replayEffect.hasBoundingBox()
                ? replayEffect.calculateBoundingBox(attackOrigin, attack.direction == 0)
                : null;
        Map<Integer, List<Integer>> damage = collectTrackingCloseTargets(
                expectedMap, attackOrigin, attackBounds, mobCount, damageTemplate
        );
        if (damage.isEmpty()) {
            return;
        }
        int packedCount = (damage.size() << 4) | (replayAttackCount & 0xF);
        Packet packet = PacketCreator.closeRangeAttack(
                chr,
                replaySkillId,
                attack.skilllevel,
                attack.stance,
                packedCount,
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

    private void scheduleTrackingCloseAttacks(
            AttackInfo attack,
            Character chr,
            int[] attackTimesMs,
            int replaySkillId,
            boolean applyOriginalFirst
    ) {
        MapleMap expectedMap = chr.getMap();
        Skill originalSkill = SkillFactory.getSkill(attack.skill);
        StatEffect originalEffect = originalSkill.getEffect(chr.getSkillLevel(originalSkill));
        Skill replaySkill = SkillFactory.getSkill(replaySkillId);
        int replayLevel = Math.max(1, Math.min(attack.skilllevel, replaySkill.getMaxLevel()));
        StatEffect replayEffect = replaySkill.getEffect(replayLevel);
        int replayAttackCount = Math.max(1, Math.min(15, replayEffect.getAttackCount()));
        int mobCount = Math.max(1, Math.min(15, replayEffect.getMobCount()));
        List<Integer> sourceDamageTemplate = copyCapturedDamageTemplate(attack);
        if (sourceDamageTemplate.isEmpty()) {
            sourceDamageTemplate = Collections.singletonList(
                    calculateFallbackCloseDamage(chr, originalEffect)
            );
        }
        List<Integer> damageTemplate = adaptDamageTemplate(
                sourceDamageTemplate,
                replayAttackCount,
                originalEffect.getDamage(),
                replayEffect.getDamage()
        );
        Point fixedAttackOrigin = usesFixedThunderBreakerOrigin(attack.skill)
                ? new Point(chr.getPosition())
                : null;
        for (int index = 0; index < attackTimesMs.length; index++) {
            final boolean originalTick = applyOriginalFirst && index == 0;
            TimerManager.getInstance().schedule(() -> {
                if (!canContinueAnimatedAttack(chr, expectedMap)) {
                    return;
                }
                if (originalTick) {
                    showCapturedDamageNumbers(attack, chr, expectedMap);
                    applyAttack(attack, chr, originalEffect.getAttackCount());
                    return;
                }
                repeatTrackingCloseAttack(
                        attack,
                        chr,
                        expectedMap,
                        replaySkillId,
                        replayAttackCount,
                        mobCount,
                        damageTemplate,
                        replayEffect,
                        fixedAttackOrigin
                );
            }, attackTimesMs[index]);
        }
    }

    private void scheduleLightningSpearMultistrike(AttackInfo attack, Character chr) {
        scheduleTrackingCloseAttacks(
                attack, chr, new int[]{LIGHTNING_SPEAR_STRIKE_1_TIMES_MS[0]},
                ThunderBreaker.LIGHTNING_SPEAR_MULTISTRIKE, true
        );
        scheduleTrackingCloseAttacks(
                attack, chr, new int[]{LIGHTNING_SPEAR_STRIKE_1_TIMES_MS[1]},
                ThunderBreaker.LIGHTNING_SPEAR_STRIKE_1, false
        );
        scheduleTrackingCloseAttacks(attack, chr, LIGHTNING_SPEAR_STRIKE_2_TIMES_MS,
                ThunderBreaker.LIGHTNING_SPEAR_STRIKE_2, false);
        scheduleTrackingCloseAttacks(attack, chr, LIGHTNING_SPEAR_STRIKE_3_TIMES_MS,
                ThunderBreaker.LIGHTNING_SPEAR_STRIKE_3, false);
        scheduleTrackingCloseAttacks(attack, chr, LIGHTNING_SPEAR_STRIKE_4_TIMES_MS,
                ThunderBreaker.LIGHTNING_SPEAR_STRIKE_4, false);
        scheduleTrackingCloseAttacks(attack, chr, LIGHTNING_SPEAR_STRIKE_5_TIMES_MS,
                ThunderBreaker.LIGHTNING_SPEAR_STRIKE_5, false);
        scheduleTrackingCloseAttacks(attack, chr, LIGHTNING_SPEAR_STRIKE_6_TIMES_MS,
                ThunderBreaker.LIGHTNING_SPEAR_STRIKE_6, false);
        scheduleTrackingCloseAttacks(attack, chr, LIGHTNING_SPEAR_THUNDER_TIMES_MS,
                ThunderBreaker.LIGHTNING_SPEAR_THUNDER, false);
        scheduleTrackingCloseAttacks(attack, chr, new int[]{2490},
                ThunderBreaker.LIGHTNING_SPEAR_FINISH, false);
        scheduleTrackingCloseAttacks(attack, chr, new int[]{2820},
                ThunderBreaker.LIGHTNING_SPEAR_GIANT_THUNDER, false);
    }

    private void scheduleAnimatedAttacks(
            AttackInfo attack,
            Character chr,
            int attackCount,
            int[] attackTimesMs
    ) {
        MapleMap expectedMap = chr.getMap();
        Skill skill = SkillFactory.getSkill(attack.skill);
        StatEffect effect = skill.getEffect(chr.getSkillLevel(skill));
        Point castPosition = new Point(chr.getPosition());
        Rectangle attackBounds = effect.hasBoundingBox()
                ? effect.calculateBoundingBox(castPosition, attack.direction == 0)
                : null;
        int mobCount = Math.max(1, Math.min(15, effect.getMobCount()));
        List<Integer> damageTemplate = copyCapturedDamageTemplate(attack);
        log.info(
                "{} schedule skill={} ticks={} initialTargets={} templateHits={} bounds={}",
                ANIMATED_ATTACK_LOG_VERSION,
                attack.skill,
                attackTimesMs.length,
                attack.allDamage.size(),
                damageTemplate.size(),
                attackBounds
        );
        for (int index = 0; index < attackTimesMs.length; index++) {
            final int tickIndex = index;
            TimerManager.getInstance().schedule(() -> {
                if (!canContinueAnimatedAttack(chr, expectedMap)) {
                    if (tickIndex == 0 || tickIndex == 1 || tickIndex == attackTimesMs.length - 1) {
                        log.info(
                                "{} stop skill={} tick={}/{} reason=character-state-or-map",
                                ANIMATED_ATTACK_LOG_VERSION,
                                attack.skill,
                                tickIndex + 1,
                                attackTimesMs.length
                        );
                    }
                    return;
                }
                if (tickIndex == 0) {
                    showCapturedDamageNumbers(attack, chr, expectedMap);
                    applyAttack(attack, chr, attackCount);
                    log.info(
                            "{} first skill={} tick=1/{} targets={}",
                            ANIMATED_ATTACK_LOG_VERSION,
                            attack.skill,
                            attackTimesMs.length,
                            attack.allDamage.size()
                    );
                } else {
                    int targets = repeatCapturedAttack(
                            attack,
                            chr,
                            expectedMap,
                            attackBounds,
                            mobCount,
                            damageTemplate
                    );
                    if (tickIndex == 1 || tickIndex == attackTimesMs.length - 1) {
                        log.info(
                                "{} repeat skill={} tick={}/{} targets={}",
                                ANIMATED_ATTACK_LOG_VERSION,
                                attack.skill,
                                tickIndex + 1,
                                attackTimesMs.length,
                                targets
                        );
                    }
                }
            }, attackTimesMs[index]);
        }
    }

    @Override
    public final void handlePacket(InPacket p, Client c) {
        Character chr = c.getPlayer();
        
        /*long timeElapsed = currentServerTime() - chr.getAutobanManager().getLastSpam(8);
        if(timeElapsed < 300) {
                AutobanFactory.FAST_ATTACK.alert(chr, "Time: " + timeElapsed);
        }
        chr.getAutobanManager().spam(8);*/

        AttackInfo attack = parseDamage(p, chr, false, false);
        if (chr.getBuffEffect(BuffStat.MORPH) != null) {
            if (chr.getBuffEffect(BuffStat.MORPH).isMorphWithoutAttack()) {
                // How are they attacking when the client won't let them?
                chr.getClient().disconnect(false, false);
                return;
            }
        }

        if (chr.getDojoEnergy() < 10000 && (attack.skill == 1009 || attack.skill == 10001009 || attack.skill == 20001009)) // PE hacking or maybe just lagging
        {
            return;
        }
        if (MapId.isDojo(chr.getMap().getId()) && attack.numAttacked > 0) {
            chr.setDojoEnergy(chr.getDojoEnergy() + GameConfig.getServerInt("dojo_energy_atk"));
            c.sendPacket(PacketCreator.getEnergy("energy", chr.getDojoEnergy()));
        }

        chr.getMap().broadcastMessage(chr, PacketCreator.closeRangeAttack(chr, attack.skill, attack.skilllevel, attack.stance, attack.numAttackedAndDamage, attack.allDamage, attack.speed, attack.direction, attack.display), false, true);
        int numFinisherOrbs = 0;
        Integer comboBuff = chr.getBuffedValue(BuffStat.COMBO);
        if (GameConstants.isFinisherSkill(attack.skill)) {
            if (comboBuff != null) {
                numFinisherOrbs = comboBuff - 1;
            }
            chr.handleOrbconsume();
        } else if (attack.numAttacked > 0) {
            if (attack.skill != 1111008 && comboBuff != null) {
                int orbcount = chr.getBuffedValue(BuffStat.COMBO);
                int oid = chr.isCygnus() ? DawnWarrior.COMBO : Crusader.COMBO;
                int advcomboid = chr.isCygnus() ? DawnWarrior.ADVANCED_COMBO : Hero.ADVANCED_COMBO;
                Skill combo = SkillFactory.getSkill(oid);
                Skill advcombo = SkillFactory.getSkill(advcomboid);
                StatEffect ceffect;
                int advComboSkillLevel = chr.getSkillLevel(advcombo);
                if (advComboSkillLevel > 0) {
                    ceffect = advcombo.getEffect(advComboSkillLevel);
                } else {
                    int comboLv = chr.getSkillLevel(combo);
                    if (comboLv <= 0 || chr.isGM()) {
                        comboLv = SkillFactory.getSkill(oid).getMaxLevel();
                    }

                    if (comboLv > 0) {
                        ceffect = combo.getEffect(comboLv);
                    } else {
                        ceffect = null;
                    }
                }
                if (ceffect != null) {
                    if (orbcount < ceffect.getX() + 1) {
                        int neworbcount = orbcount + 1;
                        if (advComboSkillLevel > 0 && ceffect.makeChanceResult()) {
                            if (neworbcount <= ceffect.getX()) {
                                neworbcount++;
                            }
                        }

                        int olv = chr.getSkillLevel(oid);
                        if (olv <= 0) {
                            olv = SkillFactory.getSkill(oid).getMaxLevel();
                        }

                        int duration = combo.getEffect(olv).getDuration();
                        List<Pair<BuffStat, Integer>> stat = Collections.singletonList(new Pair<>(BuffStat.COMBO, neworbcount));
                        chr.setBuffedValue(BuffStat.COMBO, neworbcount);
                        duration -= (int) (currentServerTime() - chr.getBuffedStarttime(BuffStat.COMBO));
                        c.sendPacket(PacketCreator.giveBuff(oid, duration, stat));
                        chr.getMap().broadcastMessage(chr, PacketCreator.giveForeignBuff(chr.getId(), stat), false);
                    }
                }
            } else if (chr.getSkillLevel(chr.isCygnus() ? SkillFactory.getSkill(15100004) : SkillFactory.getSkill(5110001)) > 0 && (chr.getJob().isA(Job.MARAUDER) || chr.getJob().isA(Job.THUNDERBREAKER2))) {
                for (int i = 0; i < attack.numAttacked; i++) {
                    chr.handleEnergyChargeGain();
                }
            }
        }
        if (attack.numAttacked > 0 && attack.skill == DragonKnight.SACRIFICE) {
            int totDamageToOneMonster = 0; // sacrifice attacks only 1 mob with 1 attack
            final Iterator<List<Integer>> dmgIt = attack.allDamage.values().iterator();
            if (dmgIt.hasNext()) {
                totDamageToOneMonster = dmgIt.next().get(0);
            }

            chr.safeAddHP(-1 * totDamageToOneMonster * attack.getAttackEffect(chr, null).getX() / 100);
        }
        if (attack.numAttacked > 0 && attack.skill == 1211002) {
            boolean advcharge_prob = false;
            int advcharge_level = chr.getSkillLevel(SkillFactory.getSkill(1220010));
            if (advcharge_level > 0) {
                advcharge_prob = SkillFactory.getSkill(1220010).getEffect(advcharge_level).makeChanceResult();
            }
            if (!advcharge_prob) {
                chr.cancelEffectFromBuffStat(BuffStat.WK_CHARGE);
            }
        }
        int attackCount = 1;
        if (attack.skill != 0) {
            attackCount = attack.getAttackEffect(chr, null).getAttackCount();
        }
        if (numFinisherOrbs == 0 && GameConstants.isFinisherSkill(attack.skill)) {
            return;
        }
        if (attack.skill % 10000000 == 1009) { // bamboo
            if (chr.getDojoEnergy() < 10000) { // PE hacking or maybe just lagging
                return;
            }

            chr.setDojoEnergy(0);
            c.sendPacket(PacketCreator.getEnergy("energy", chr.getDojoEnergy()));
            c.sendPacket(PacketCreator.serverNotice(5, "As you used the secret skill, your energy bar has been reset."));
        } else if (attack.skill > 0) {
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
        if ((chr.getSkillLevel(SkillFactory.getSkill(NightWalker.VANISH)) > 0 || chr.getSkillLevel(SkillFactory.getSkill(Rogue.DARK_SIGHT)) > 0) && chr.getBuffedValue(BuffStat.DARKSIGHT) != null) {// && chr.getBuffSource(BuffStat.DARKSIGHT) != 9101004
            chr.cancelEffectFromBuffStat(BuffStat.DARKSIGHT);
            chr.cancelBuffStats(BuffStat.DARKSIGHT);
        } else if (chr.getSkillLevel(SkillFactory.getSkill(WindArcher.WIND_WALK)) > 0 && chr.getBuffedValue(BuffStat.WIND_WALK) != null) {
            chr.cancelEffectFromBuffStat(BuffStat.WIND_WALK);
            chr.cancelBuffStats(BuffStat.WIND_WALK);
        }

        if (attack.skill == Hero.MONSTER_MAGNET) {
            final int delayedAttackCount = attackCount;
            TimerManager.getInstance().schedule(() -> applyAttack(attack, chr, delayedAttackCount), SWORD_ILLUSION_HIT_DELAY_MS);
        } else if (attack.skill == Hero.DEATH_FAULT) {
            chr.getMap().broadcastMessage(PacketCreator.showEffect(DEATH_FAULT_FIELD_EFFECT));
            final int delayedAttackCount = attackCount;
            TimerManager.getInstance().schedule(() -> applyAttack(attack, chr, delayedAttackCount), DEATH_FAULT_HIT_DELAY_MS);
        } else if (attack.skill == DawnWarrior.GALAXY_STAR_BURST) {
            chr.sendPacket(PacketCreator.showEffect(GALAXY_STAR_BURST_VIDEO_LAYER));
            scheduleAnimatedAttacks(attack, chr, attackCount, GALAXY_STAR_BURST_ATTACK_TIMES_MS);
        } else if (attack.skill == DawnWarrior.ECLIPSE_FORCE) {
            chr.sendPacket(PacketCreator.showEffect(ECLIPSE_FORCE_VIDEO_LAYER));
            scheduleAnimatedAttacks(attack, chr, attackCount, ECLIPSE_FORCE_ATTACK_TIMES_MS);
        } else if (attack.skill == DawnWarrior.SOUL_ECLIPSE) {
            chr.sendPacket(PacketCreator.showEffect(SOUL_ECLIPSE_VIDEO_LAYER));
            scheduleAnimatedAttacks(attack, chr, attackCount, SOUL_ECLIPSE_ATTACK_TIMES_MS);
        } else if (attack.skill == DawnWarrior.COSMOS) {
            scheduleAnimatedAttacks(attack, chr, attackCount, COSMOS_ATTACK_TIMES_MS);
        } else if (attack.skill == ThunderBreaker.SEA_DRAGON_SPIRAL) {
            scheduleTrackingCloseAttacks(
                    attack, chr, SEA_DRAGON_SPIRAL_TIMES_MS,
                    ThunderBreaker.SEA_DRAGON_SPIRAL, true
            );
        } else if (attack.skill == ThunderBreaker.LIGHTNING_SPEAR_MULTISTRIKE) {
            scheduleLightningSpearMultistrike(attack, chr);
        } else if (attack.skill == ThunderBreaker.THUNDERBOLT_VI) {
            applyAttack(attack, chr, attackCount);
            if (!chr.skillIsCooling(ThunderBreaker.THUNDERBOLT_FLASH)) {
                chr.addCooldown(
                        ThunderBreaker.THUNDERBOLT_FLASH,
                        currentServerTime(),
                        SECONDS.toMillis(6)
                );
                scheduleTrackingCloseAttacks(
                        attack, chr, new int[]{0}, ThunderBreaker.THUNDERBOLT_FLASH, false
                );
            }
        } else if (attack.skill == ThunderBreaker.GOD_OF_THE_SEA_VI) {
            chr.sendPacket(PacketCreator.showEffect(GOD_OF_THE_SEA_VI_VIDEO_LAYER));
            applyAttack(attack, chr, attackCount);
        } else if (attack.skill == ThunderBreaker.WAVE_RIDING_THUNDER) {
            chr.sendPacket(PacketCreator.showEffect(WAVE_RIDING_THUNDER_VIDEO_LAYER));
            scheduleTrackingCloseAttacks(
                    attack, chr, WAVE_RIDING_THUNDER_OPENING_TIMES_MS,
                    ThunderBreaker.WAVE_RIDING_THUNDER, true
            );
            scheduleTrackingCloseAttacks(
                    attack, chr, WAVE_RIDING_THUNDER_SHOCK_TIMES_MS,
                    ThunderBreaker.WAVE_RIDING_THUNDER_SHOCK, false
            );
        } else if (attack.skill == ThunderBreaker.SWIFT_ANNIHILATION) {
            chr.sendPacket(PacketCreator.showEffect(SWIFT_ANNIHILATION_VIDEO_LAYER));
            scheduleTrackingCloseAttacks(
                    attack, chr, SWIFT_ANNIHILATION_OPENING_TIMES_MS,
                    ThunderBreaker.SWIFT_ANNIHILATION, true
            );
            scheduleTrackingCloseAttacks(
                    attack, chr, SWIFT_ANNIHILATION_SURGE_TIMES_MS,
                    ThunderBreaker.SWIFT_ANNIHILATION_SURGE, false
            );
        } else {
            applyAttack(attack, chr, attackCount);
        }
    }
}
