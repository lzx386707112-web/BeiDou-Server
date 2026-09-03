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
import org.gms.config.GameConfig;
import org.gms.constants.id.MapId;
import org.gms.constants.skills.BlazeWizard;
import org.gms.constants.skills.Bishop;
import org.gms.constants.skills.Evan;
import org.gms.constants.skills.ExplorerOtherSkillCompat;
import org.gms.constants.skills.FPArchMage;
import org.gms.constants.skills.FPMage;
import org.gms.constants.skills.ILArchMage;
import org.gms.net.packet.InPacket;
import org.gms.net.packet.Packet;
import org.gms.server.DamageCapService;
import org.gms.server.StatEffect;
import org.gms.server.TimerManager;
import org.gms.server.life.Monster;
import org.gms.server.maps.MapObject;
import org.gms.server.maps.MapObjectType;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Mist;
import org.gms.server.maps.Summon;
import org.gms.util.PacketCreator;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static java.util.concurrent.TimeUnit.SECONDS;

public final class MagicDamageHandler extends AbstractDealDamageHandler {
    private static final int[] FOUNTAIN_FOR_ANGEL_VI_ATTACK_TIMES_MS =
            intervalTimes(2000, 2000, 60000);
    private static final Rectangle FOUNTAIN_FOR_ANGEL_VI_LOCAL_BOUNDS =
            new Rectangle(-290, -300, 580, 410);
    private static final String ETERNAL_PHOENIX_VIDEO_LAYER =
            "customSkill/blazeWizard/eternalPhoenixVideoLayer";
    private static final String FLAME_CONCERTO_VIDEO_LAYER =
            "customSkill/blazeWizard/flameConcertoVideoLayer";
    private static final int[] FLAME_DISCHARGE_LION_MAIN_TIMES_MS = {1530};
    private static final int[] FLAME_DISCHARGE_LION_EMBER_TIMES_MS = {3450};
    private static final int[] FLAME_DISCHARGE_LION_FINISH_TIMES_MS = {
        5000, 8250, 11500, 14750, 18000
    };
    private static final int[] INFERNO_SPHERE_ATTACK_TIMES_MS = intervalTimes(120, 120, 4920);
    private static final int[] PHOENIX_DRIVE_VI_ATTACK_TIMES_MS = intervalTimes(480, 480, 19680);
    private static final int[] ETERNAL_PHOENIX_MAIN_TIMES_MS = {
        120, 150, 180, 210, 240, 270, 300, 2400, 3960, 4080,
        4230, 4260, 4290, 4320, 4350, 4380, 4410, 4440, 4470, 4500,
        4530, 4560, 4590, 4620, 4650, 4680, 4710, 4740, 4770, 4800,
        4830, 4860, 4890, 4920, 4950, 4980, 5010, 5040
    };
    private static final int[] ETERNAL_PHOENIX_CYCLE_TIMES_MS = intervalTimes(6300, 1200, 29100);
    private static final int[] FLAME_CONCERTO_MAIN_TIMES_MS = {
        360, 420, 480, 540, 600, 1440, 1500, 1560, 1620, 1680, 1740, 1800, 1860
    };
    private static final int[] FLAME_CONCERTO_FINISH_TIMES_MS = {
        2160, 2190, 2220, 2250, 2280, 2310, 2340, 2370,
        2400, 2430, 2460, 2490, 2520, 2550, 2580
    };
    private static final int[] BLIZZARD_VI_FINAL_ATTACK_TIMES_MS = {990};
    private static final int[] SPIRIT_OF_SNOW_TICK_TIMES_MS = intervalTimes(3000, 3000, 27000);
    private static final int[] CHAIN_LIGHTNING_VI_FIELD_TICK_TIMES_MS = {
        1960, 2960, 3960, 4960
    };
    private static final int FLAME_HAZE_VI_MIST_DELAY_MS = 1200;
    private static final int FLAME_HAZE_VI_MIST_DURATION_MS = 15000;
    private static final int[] FLAME_HAZE_VI_MIST_TICK_TIMES_MS =
            intervalTimes(1200, 1000, 15200);

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

    private static List<Integer> copyDamageTemplate(AttackInfo attack) {
        for (List<Integer> damage : attack.allDamage.values()) {
            if (damage != null && !damage.isEmpty()) {
                return new ArrayList<>(damage);
            }
        }
        return Collections.emptyList();
    }

    private static int calculateFallbackMagicDamage(Character chr, StatEffect effect) {
        double totalMagic = chr.getTotalMagic();
        long damage = (long) (
                Math.ceil((totalMagic * Math.ceil(totalMagic / 1000.0) + totalMagic) / 30.0)
                        + Math.ceil(chr.getTotalInt() / 200.0)
        );
        int amplificationLevel = chr.getSkillLevel(BlazeWizard.ELEMENT_AMPLIFICATION);
        if (amplificationLevel > 0) {
            StatEffect amplification = SkillFactory.getSkill(BlazeWizard.ELEMENT_AMPLIFICATION)
                    .getEffect(amplificationLevel);
            damage = damage * amplification.getY() / 100;
        }
        damage *= effect.getMatk();
        return (int) Math.max(1, Math.min(Integer.MAX_VALUE, damage));
    }

    private static int encodeRepeatedDamage(int damage, boolean critical) {
        int clamped = Math.max(0, damage);
        return critical ? clamped | Integer.MIN_VALUE : clamped;
    }

    private static List<Integer> adaptDamageTemplate(
            Character chr,
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
                    DamageCapService.capDamage(
                            chr, (int) Math.min(Integer.MAX_VALUE, scaled)
                    ), original < 0
            ));
        }
        return result;
    }

    private static Map<Integer, List<Integer>> collectAnimatedTargets(
            AttackInfo attack,
            MapleMap expectedMap,
            Rectangle attackBounds,
            int mobCount,
            List<Integer> damageTemplate
    ) {
        Map<Integer, List<Integer>> result = new LinkedHashMap<>();
        if (attackBounds != null && !damageTemplate.isEmpty()) {
            Point attackOrigin = new Point(
                    (int) attackBounds.getCenterX(),
                    (int) attackBounds.getCenterY()
            );
            List<Monster> targets = new ArrayList<>(expectedMap.getAllMonsters());
            targets.removeIf(monster -> !monster.isAlive()
                    || !attackBounds.contains(monster.getPosition()));
            targets.sort(Comparator
                    .comparing((Monster monster) -> !monster.isBoss())
                    .thenComparingDouble(monster -> monster.getPosition().distanceSq(attackOrigin))
                    .thenComparingInt(Monster::getObjectId));
            for (Monster monster : targets) {
                result.put(monster.getObjectId(), new ArrayList<>(damageTemplate));
                if (result.size() >= mobCount) {
                    break;
                }
            }
            return result;
        }
        for (Map.Entry<Integer, List<Integer>> entry : attack.allDamage.entrySet()) {
            Monster monster = expectedMap.getMonsterByOid(entry.getKey());
            if (monster != null && monster.isAlive() && entry.getValue() != null) {
                result.put(entry.getKey(), entry.getValue());
                if (result.size() >= mobCount) {
                    break;
                }
            }
        }
        return result;
    }

    private static void scheduleFountainForAngelViAttacks(
            Character chr,
            Summon summon,
            StatEffect effect
    ) {
        MapleMap expectedMap = chr.getMap();
        int mobCount = Math.max(1, Math.min(8, effect.getMobCount()));
        long oneLineDamage = (long) SummonDamageHandler.calcMaxDamage(effect, chr, true)
                * Math.max(1, Math.min(15, effect.getAttackCount()));
        int damage = DamageCapService.capDamage(
                chr, (int) Math.min(Integer.MAX_VALUE, oneLineDamage)
        );
        for (int attackTimeMs : FOUNTAIN_FOR_ANGEL_VI_ATTACK_TIMES_MS) {
            TimerManager.getInstance().schedule(() -> {
                if (!canContinueAnimatedAttack(chr, expectedMap)
                        || chr.getSummonByKey(Bishop.FOUNTAIN_FOR_ANGEL_VI) != summon
                        || expectedMap.isOwnershipRestricted(chr)) {
                    return;
                }
                Point summonPosition = summon.getPosition();
                Rectangle bounds = new Rectangle(
                        summonPosition.x + FOUNTAIN_FOR_ANGEL_VI_LOCAL_BOUNDS.x,
                        summonPosition.y + FOUNTAIN_FOR_ANGEL_VI_LOCAL_BOUNDS.y,
                        FOUNTAIN_FOR_ANGEL_VI_LOCAL_BOUNDS.width,
                        FOUNTAIN_FOR_ANGEL_VI_LOCAL_BOUNDS.height
                );
                List<SummonDamageHandler.SummonAttackEntry> attacks = new ArrayList<>();
                for (MapObject target : expectedMap.getMapObjectsInBox(
                        bounds, Collections.singletonList(MapObjectType.MONSTER)
                )) {
                    Monster monster = (Monster) target;
                    if (monster.isAlive()) {
                        attacks.add(new SummonDamageHandler.SummonAttackEntry(
                                monster.getObjectId(), damage
                        ));
                        if (attacks.size() >= mobCount) {
                            break;
                        }
                    }
                }
                if (attacks.isEmpty()) {
                    return;
                }
                byte direction = chr.isFacingLeft() ? (byte) 1 : (byte) 0;
                Packet packet = PacketCreator.summonAttack(
                        chr.getId(), summon.getObjectId(), direction, attacks
                );
                chr.sendPacket(packet);
                expectedMap.broadcastMessage(chr, packet, summonPosition);
                for (SummonDamageHandler.SummonAttackEntry attack : attacks) {
                    Monster monster = expectedMap.getMonsterByOid(attack.getMonsterOid());
                    if (monster != null && monster.isAlive()) {
                        monster.aggroMonsterDamage(chr, attack.getDamage());
                        expectedMap.damageMonster(chr, monster, attack.getDamage());
                    }
                }
            }, attackTimeMs);
        }
    }

    private static Rectangle captureAnimatedAttackBounds(
            AttackInfo attack,
            MapleMap map,
            StatEffect replayEffect,
            boolean facingLeft
    ) {
        if (!replayEffect.hasBoundingBox()) {
            return null;
        }
        Rectangle result = null;
        for (Integer objectId : attack.allDamage.keySet()) {
            Monster monster = map.getMonsterByOid(objectId);
            if (monster == null || !monster.isAlive()) {
                continue;
            }
            Rectangle targetBounds = replayEffect.calculateBoundingBox(
                    new Point(monster.getPosition()), facingLeft
            );
            if (result == null) {
                result = new Rectangle(targetBounds);
            } else {
                result.add(targetBounds);
            }
        }
        return result;
    }

    private void scheduleFlameHazeViMist(AttackInfo attack, Character chr) {
        MapleMap expectedMap = chr.getMap();
        Point impactPosition = new Point(chr.getPosition());
        for (Integer objectId : attack.allDamage.keySet()) {
            Monster monster = expectedMap.getMonsterByOid(objectId);
            if (monster != null) {
                impactPosition = new Point(monster.getPosition());
                break;
            }
        }

        Skill mistSkill = SkillFactory.getSkill(FPArchMage.FATAL_POISON_MIST);
        int mistLevel = Math.max(1, Math.min(attack.skilllevel, mistSkill.getMaxLevel()));
        StatEffect mistEffect = mistSkill.getEffect(mistLevel);
        Rectangle mistBounds = mistEffect.calculateBoundingBox(impactPosition, false);
        TimerManager.getInstance().schedule(() -> {
            if (!canContinueAnimatedAttack(chr, expectedMap)) {
                return;
            }
            Skill visualMistSkill = SkillFactory.getSkill(FPMage.POISON_MIST);
            int visualMistLevel = Math.max(
                    1, Math.min(attack.skilllevel, visualMistSkill.getMaxLevel())
            );
            StatEffect visualMistEffect = visualMistSkill.getEffect(visualMistLevel);
            Mist mist = new Mist(new Rectangle(mistBounds), chr, visualMistEffect);
            expectedMap.spawnMist(
                    mist, FLAME_HAZE_VI_MIST_DURATION_MS, false, true, false
            );
        }, FLAME_HAZE_VI_MIST_DELAY_MS);

        Skill originalSkill = SkillFactory.getSkill(attack.skill);
        int originalLevel = Math.max(
                1, Math.min(attack.skilllevel, originalSkill.getMaxLevel())
        );
        StatEffect originalEffect = originalSkill.getEffect(originalLevel);
        List<Integer> sourceDamageTemplate = copyDamageTemplate(attack);
        if (sourceDamageTemplate.isEmpty()) {
            sourceDamageTemplate = Collections.singletonList(
                    calculateFallbackMagicDamage(chr, originalEffect)
            );
        }
        List<Integer> mistDamageTemplate = adaptDamageTemplate(
                chr,
                sourceDamageTemplate,
                Math.max(1, Math.min(15, mistEffect.getAttackCount())),
                originalEffect.getDamage(),
                mistEffect.getDamage()
        );
        int mistMobCount = Math.max(1, Math.min(15, mistEffect.getMobCount()));
        for (int tickTimeMs : FLAME_HAZE_VI_MIST_TICK_TIMES_MS) {
            TimerManager.getInstance().schedule(() -> {
                if (!canContinueAnimatedAttack(chr, expectedMap)) {
                    return;
                }
                Map<Integer, List<Integer>> damage = collectAnimatedTargets(
                        attack, expectedMap, mistBounds, mistMobCount, mistDamageTemplate
                );
                for (Map.Entry<Integer, List<Integer>> entry : damage.entrySet()) {
                    Monster monster = expectedMap.getMonsterByOid(entry.getKey());
                    if (monster == null || !monster.isAlive()) {
                        continue;
                    }
                    int total = 0;
                    for (Integer hit : entry.getValue()) {
                        total = (int) Math.min(
                                Integer.MAX_VALUE,
                                (long) total + decodeRepeatedDamage(hit)
                        );
                    }
                    expectedMap.broadcastMessage(
                            PacketCreator.damageMonster(monster.getObjectId(), total),
                            monster.getPosition()
                    );
                    monster.aggroMonsterDamage(chr, total);
                    expectedMap.damageMonster(chr, monster, total);
                }
            }, tickTimeMs);
        }
    }

    private static void applyAnimatedDamage(
            Character chr,
            MapleMap expectedMap,
            Map<Integer, List<Integer>> damage
    ) {
        if (!canContinueAnimatedAttack(chr, expectedMap)) {
            return;
        }
        for (Map.Entry<Integer, List<Integer>> entry : damage.entrySet()) {
            Monster monster = expectedMap.getMonsterByOid(entry.getKey());
            if (monster == null || !monster.isAlive()) {
                continue;
            }
            int total = 0;
            for (Integer hit : entry.getValue()) {
                total = (int) Math.min(Integer.MAX_VALUE, (long) total + decodeRepeatedDamage(hit));
            }
            monster.aggroMonsterDamage(chr, total);
            expectedMap.damageMonster(chr, monster, total);
        }
    }

    private static void showDamageNumbers(
            Character chr,
            MapleMap expectedMap,
            Map<Integer, List<Integer>> damage
    ) {
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
        }
    }

    private static Packet animatedAttackPacket(
            AttackInfo attack,
            Character chr,
            Map<Integer, List<Integer>> damage,
            int replaySkillId,
            int replayAttackCount
    ) {
        int packedCount = (Math.min(15, damage.size()) << 4) | (replayAttackCount & 0xF);
        return PacketCreator.magicAttack(
                chr,
                replaySkillId,
                attack.skilllevel,
                attack.stance,
                packedCount,
                damage,
                -1,
                attack.speed,
                attack.direction,
                attack.display
        );
    }

    private static void broadcastAnimatedAttack(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            Map<Integer, List<Integer>> damage,
            int replaySkillId,
            int replayAttackCount
    ) {
        Packet packet = animatedAttackPacket(
                attack, chr, damage, replaySkillId, replayAttackCount
        );
        chr.sendPacket(packet);
        expectedMap.broadcastMessage(chr, packet, false, true);
    }

    private static void repeatAnimatedAttack(
            AttackInfo attack,
            Character chr,
            MapleMap expectedMap,
            Rectangle attackBounds,
            int mobCount,
            List<Integer> damageTemplate,
            int replaySkillId,
            int replayAttackCount,
            boolean applyDamage
    ) {
        if (!canContinueAnimatedAttack(chr, expectedMap)) {
            return;
        }
        Map<Integer, List<Integer>> damage = collectAnimatedTargets(
                attack, expectedMap, attackBounds, mobCount, damageTemplate
        );
        if (damage.isEmpty()) {
            return;
        }
        broadcastAnimatedAttack(
                attack, chr, expectedMap, damage, replaySkillId, replayAttackCount
        );
        if (applyDamage) {
            showDamageNumbers(chr, expectedMap, damage);
            applyAnimatedDamage(chr, expectedMap, damage);
        }
    }

    private void scheduleAnimatedAttacks(
            AttackInfo attack,
            Character chr,
            int[] attackTimesMs,
            int replaySkillId,
            boolean applyInitialAttack
    ) {
        scheduleAnimatedAttacks(
                attack, chr, attackTimesMs, replaySkillId, applyInitialAttack, null
        );
    }

    private void scheduleAnimatedAttacks(
            AttackInfo attack,
            Character chr,
            int[] attackTimesMs,
            int replaySkillId,
            boolean applyInitialAttack,
            Rectangle fixedBounds
    ) {
        MapleMap expectedMap = chr.getMap();
        Skill originalSkill = SkillFactory.getSkill(attack.skill);
        StatEffect originalEffect = originalSkill.getEffect(chr.getSkillLevel(originalSkill));
        Skill replaySkill = SkillFactory.getSkill(replaySkillId);
        int replayLevel = Math.max(1, Math.min(attack.skilllevel, replaySkill.getMaxLevel()));
        StatEffect replayEffect = replaySkill.getEffect(replayLevel);
        Point castPosition = new Point(chr.getPosition());
        boolean usesCapturedTargets = replaySkillId == ILArchMage.BLIZZARD_VI_FINAL_ATTACK
                || replaySkillId == ILArchMage.CHAIN_LIGHTNING_VI_FIELD;
        Rectangle attackBounds;
        if (fixedBounds != null) {
            attackBounds = new Rectangle(fixedBounds);
        } else if (replaySkillId == ILArchMage.CHAIN_LIGHTNING_VI_FIELD_TICK
                && originalEffect.hasBoundingBox()) {
            attackBounds = originalEffect.calculateBoundingBox(
                    castPosition, attack.direction == 0
            );
        } else {
            attackBounds = !usesCapturedTargets && replayEffect.hasBoundingBox()
                    ? replayEffect.calculateBoundingBox(castPosition, attack.direction == 0)
                    : null;
        }
        boolean followsCaster = attack.skill == BlazeWizard.PHOENIX_DRIVE_VI;
        int mobCount = Math.max(1, Math.min(15, replayEffect.getMobCount()));
        int replayAttackCount = Math.max(1, Math.min(15, replayEffect.getAttackCount()));
        List<Integer> sourceDamageTemplate = copyDamageTemplate(attack);
        boolean hasCapturedDamage = !sourceDamageTemplate.isEmpty();
        if (sourceDamageTemplate.isEmpty()) {
            sourceDamageTemplate = Collections.singletonList(
                    calculateFallbackMagicDamage(chr, originalEffect)
            );
        }
        List<Integer> damageTemplate = adaptDamageTemplate(
                chr,
                sourceDamageTemplate,
                replayAttackCount,
                originalEffect.getDamage(),
                replayEffect.getDamage()
        );
        for (int index = 0; index < attackTimesMs.length; index++) {
            final int tickIndex = index;
            TimerManager.getInstance().schedule(() -> {
                if (!canContinueAnimatedAttack(chr, expectedMap)) {
                    return;
                }
                Rectangle currentAttackBounds = followsCaster && replayEffect.hasBoundingBox()
                        ? replayEffect.calculateBoundingBox(
                                new Point(chr.getPosition()), chr.isFacingLeft()
                        )
                        : attackBounds;
                if (tickIndex == 0 && applyInitialAttack) {
                    if (followsCaster || !hasCapturedDamage) {
                        repeatAnimatedAttack(
                                attack,
                                chr,
                                expectedMap,
                                currentAttackBounds,
                                mobCount,
                                damageTemplate,
                                replaySkillId,
                                replayAttackCount,
                                true
                        );
                    } else {
                        if (replaySkillId != attack.skill) {
                            repeatAnimatedAttack(
                                    attack,
                                    chr,
                                    expectedMap,
                                    currentAttackBounds,
                                    mobCount,
                                    damageTemplate,
                                    replaySkillId,
                                    replayAttackCount,
                                    false
                            );
                        } else {
                            chr.sendPacket(animatedAttackPacket(
                                    attack,
                                    chr,
                                    attack.allDamage,
                                    replaySkillId,
                                    replayAttackCount
                            ));
                        }
                        showDamageNumbers(chr, expectedMap, attack.allDamage);
                        applyAttack(attack, chr, originalEffect.getAttackCount());
                    }
                } else {
                    repeatAnimatedAttack(
                            attack,
                            chr,
                            expectedMap,
                            currentAttackBounds,
                            mobCount,
                            damageTemplate,
                            replaySkillId,
                            replayAttackCount,
                            true
                    );
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

        AttackInfo attack = parseDamage(p, chr, false, true);
        if (chr.getBuffEffect(BuffStat.MORPH) != null) {
            if (chr.getBuffEffect(BuffStat.MORPH).isMorphWithoutAttack()) {
                // How are they attacking when the client won't let them?
                chr.getClient().disconnect(false, false);
                return;
            }
        }

        if (MapId.isDojo(chr.getMap().getId()) && attack.numAttacked > 0) {
            chr.setDojoEnergy(chr.getDojoEnergy() + +GameConfig.getServerInt("dojo_energy_atk"));
            c.sendPacket(PacketCreator.getEnergy("energy", chr.getDojoEnergy()));
        }

        StatEffect effect = attack.getAttackEffect(chr, null);
        Skill skill = SkillFactory.getSkill(attack.skill);
        StatEffect effect_ = skill.getEffect(chr.getSkillLevel(skill));
        int charge = (attack.skill == Evan.FIRE_BREATH || attack.skill == Evan.ICE_BREATH || attack.skill == FPArchMage.BIG_BANG || attack.skill == ILArchMage.BIG_BANG || attack.skill == Bishop.BIG_BANG) ? attack.charge : -1;
        Packet packet = PacketCreator.magicAttack(chr, attack.skill, attack.skilllevel, attack.stance, attack.numAttackedAndDamage, attack.allDamage, charge, attack.speed, attack.direction, attack.display);

        if (attack.skill == Bishop.HEAVENS_DOOR_VI) {
            chr.sendPacket(PacketCreator.showOwnBuffEffect(attack.skill, 2));
            chr.getMap().broadcastMessage(
                    chr,
                    PacketCreator.showBuffEffect(chr.getId(), attack.skill, 2),
                    false
            );
        }
        chr.getMap().broadcastMessage(chr, packet, false, true);
        String explorerVideoLayer = ExplorerOtherSkillCompat.videoLayer(attack.skill);
        if (explorerVideoLayer != null) {
            chr.sendPacket(PacketCreator.showEffect(explorerVideoLayer));
        }
        if (effect_.getCooldown() > 0) {
            if (chr.skillIsCooling(attack.skill)) {
                return;
            } else {
                c.sendPacket(PacketCreator.skillCooldown(attack.skill, effect_.getCooldown()));
                chr.addCooldown(attack.skill, currentServerTime(), SECONDS.toMillis(effect_.getCooldown()));
            }
        }
        if (Bishop.isVViSummonSkill(attack.skill)) {
            effect_.applyTo(chr, new Point(chr.getPosition()));
            if (attack.skill == Bishop.FOUNTAIN_FOR_ANGEL_VI) {
                Summon summon = chr.getSummonByKey(Bishop.FOUNTAIN_FOR_ANGEL_VI);
                if (summon != null) {
                    scheduleFountainForAngelViAttacks(chr, summon, effect_);
                }
            }
            return;
        }
        ExplorerOtherSkillCompat.Replay[] explorerReplays =
                ExplorerOtherSkillCompat.multiAttacks(attack.skill);
        if (explorerReplays != null) {
            for (int index = 0; index < explorerReplays.length; index++) {
                ExplorerOtherSkillCompat.Replay replay = explorerReplays[index];
                scheduleAnimatedAttacks(
                        attack, chr, replay.timesMs(), replay.skillId(), index == 0
                );
            }
            if (attack.skill == FPArchMage.INFERNAL_ERUPTION_VI
                    && attack.numAttacked > 0) {
                chr.removeCooldown(FPArchMage.FLAME_HAZE_VI);
                chr.sendPacket(PacketCreator.skillCooldown(FPArchMage.FLAME_HAZE_VI, 0));
            }
        } else if (attack.skill == BlazeWizard.FLAME_DISCHARGE_LION) {
            scheduleAnimatedAttacks(
                    attack, chr, FLAME_DISCHARGE_LION_MAIN_TIMES_MS,
                    BlazeWizard.FLAME_DISCHARGE_LION_BURST, true
            );
            scheduleAnimatedAttacks(
                    attack, chr, FLAME_DISCHARGE_LION_EMBER_TIMES_MS,
                    BlazeWizard.FLAME_DISCHARGE_LION_EMBER, false
            );
            scheduleAnimatedAttacks(
                    attack, chr, FLAME_DISCHARGE_LION_FINISH_TIMES_MS,
                    BlazeWizard.FLAME_DISCHARGE_LION_FINISH, false
            );
        } else if (attack.skill == BlazeWizard.INFERNO_SPHERE) {
            scheduleAnimatedAttacks(
                    attack, chr, INFERNO_SPHERE_ATTACK_TIMES_MS,
                    BlazeWizard.INFERNO_SPHERE_TICK, true
            );
        } else if (attack.skill == BlazeWizard.PHOENIX_DRIVE_VI) {
            scheduleAnimatedAttacks(
                    attack, chr, PHOENIX_DRIVE_VI_ATTACK_TIMES_MS,
                    BlazeWizard.PHOENIX_DRIVE_VI_TICK, true
            );
        } else if (attack.skill == BlazeWizard.ETERNAL_PHOENIX) {
            chr.sendPacket(PacketCreator.showEffect(ETERNAL_PHOENIX_VIDEO_LAYER));
            scheduleAnimatedAttacks(
                    attack, chr, ETERNAL_PHOENIX_MAIN_TIMES_MS,
                    BlazeWizard.ETERNAL_PHOENIX_BURST, true
            );
            scheduleAnimatedAttacks(
                    attack, chr, ETERNAL_PHOENIX_CYCLE_TIMES_MS,
                    BlazeWizard.ETERNAL_PHOENIX_CYCLE, false
            );
        } else if (attack.skill == BlazeWizard.FLAME_CONCERTO) {
            chr.sendPacket(PacketCreator.showEffect(FLAME_CONCERTO_VIDEO_LAYER));
            scheduleAnimatedAttacks(
                    attack, chr, FLAME_CONCERTO_MAIN_TIMES_MS,
                    BlazeWizard.FLAME_CONCERTO_MAIN, true
            );
            scheduleAnimatedAttacks(
                    attack, chr, FLAME_CONCERTO_FINISH_TIMES_MS,
                    BlazeWizard.FLAME_CONCERTO_FINISH, false
            );
        } else if (attack.skill == ILArchMage.SPIRIT_OF_SNOW) {
            Skill tickSkill = SkillFactory.getSkill(ILArchMage.SPIRIT_OF_SNOW_TICK);
            int tickLevel = Math.max(1, Math.min(attack.skilllevel, tickSkill.getMaxLevel()));
            Rectangle fieldBounds = tickSkill.getEffect(tickLevel).calculateBoundingBox(
                    new Point(chr.getPosition()), attack.direction == 0
            );
            applyAttack(attack, chr, effect.getAttackCount());
            scheduleAnimatedAttacks(
                    attack, chr, SPIRIT_OF_SNOW_TICK_TIMES_MS,
                    ILArchMage.SPIRIT_OF_SNOW_TICK, false, fieldBounds
            );
        } else if (attack.skill == ILArchMage.BLIZZARD_VI) {
            applyAttack(attack, chr, effect.getAttackCount());
            Skill finalAttack = SkillFactory.getSkill(ILArchMage.BLIZZARD_VI_FINAL_ATTACK);
            int finalAttackLevel = Math.max(
                    1, Math.min(attack.skilllevel, finalAttack.getMaxLevel())
            );
            if (finalAttack.getEffect(finalAttackLevel).makeChanceResult()) {
                scheduleAnimatedAttacks(
                        attack, chr, BLIZZARD_VI_FINAL_ATTACK_TIMES_MS,
                        ILArchMage.BLIZZARD_VI_FINAL_ATTACK, false
                );
            }
        } else if (attack.skill == ILArchMage.CHAIN_LIGHTNING_VI) {
            Skill fieldTickSkill = SkillFactory.getSkill(ILArchMage.CHAIN_LIGHTNING_VI_FIELD_TICK);
            int fieldTickLevel = Math.max(
                    1, Math.min(attack.skilllevel, fieldTickSkill.getMaxLevel())
            );
            Rectangle fieldBounds = captureAnimatedAttackBounds(
                    attack,
                    chr.getMap(),
                    fieldTickSkill.getEffect(fieldTickLevel),
                    attack.direction == 0
            );
            applyAttack(attack, chr, effect.getAttackCount());
            scheduleAnimatedAttacks(
                    attack, chr, CHAIN_LIGHTNING_VI_FIELD_TICK_TIMES_MS,
                    ILArchMage.CHAIN_LIGHTNING_VI_FIELD_TICK, false, fieldBounds
            );
        } else if (attack.skill == FPArchMage.FLAME_HAZE_VI) {
            scheduleFlameHazeViMist(attack, chr);
            applyAttack(attack, chr, effect.getAttackCount());
        } else {
            applyAttack(attack, chr, effect.getAttackCount());
        }
        Skill eaterSkill = SkillFactory.getSkill((chr.getJob().getId() - (chr.getJob().getId() % 10)) * 10000);// MP Eater, works with right job
        int eaterLevel = chr.getSkillLevel(eaterSkill);
        if (eaterLevel > 0) {
            for (Integer singleDamage : attack.allDamage.keySet()) {
                eaterSkill.getEffect(eaterLevel).applyPassive(chr, chr.getMap().getMapObject(singleDamage), 0);
            }
        }
    }
}
