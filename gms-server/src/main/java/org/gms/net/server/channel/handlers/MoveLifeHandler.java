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

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.config.GameConfig;
import org.gms.net.packet.InPacket;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.gms.server.life.MobSkill;
import org.gms.server.life.MobSkillFactory;
import org.gms.server.life.MobSkillId;
import org.gms.server.life.MobSkillType;
import org.gms.server.life.KaringBossCompat;
import org.gms.server.life.Monster;
import org.gms.server.life.MonsterInformationProvider;
import org.gms.server.maps.MapObject;
import org.gms.server.maps.MapObjectType;
import org.gms.server.maps.MapleMap;
import org.gms.util.PacketCreator;
import org.gms.exception.EmptyMovementException;

import java.awt.*;
import java.util.LinkedList;
import java.util.List;
import java.util.Set;

/**
 * @author Danny (Leifde)
 * @author ExtremeDevilz
 * @author Ronan (HeavenMS)
 */
public final class MoveLifeHandler extends AbstractMovementPacketHandler {
    private static final Logger log = LoggerFactory.getLogger(MoveLifeHandler.class);
    private static final Set<Integer> KARING_BOSS_IDS = Set.of(
            8880830, 8880831, 8880832, 8880837, 8880842);

    @Override
    public void handlePacket(InPacket p, Client c) {
        Character player = c.getPlayer();
        MapleMap map = player.getMap();

        if (player.isChangingMaps()) {  // thanks Lame for noticing mob movement shuffle (mob OID on different maps) happening on map transitions
            return;
        }

        int objectid = p.readInt();
        short moveid = p.readShort();
        MapObject mmo = map.getMapObject(objectid);
        if (mmo == null || mmo.getType() != MapObjectType.MONSTER) {
            return;
        }

        Monster monster = (Monster) mmo;
        boolean traceKaringBoss = KARING_BOSS_IDS.contains(monster.getId());
        boolean traceArcanaMob = monster.getId() == 8644001
                && (map.getId() == 450005120 || map.getId() == 450005131);
        List<Character> banishPlayers = null;

        byte pNibbles = p.readByte();
        byte rawActivity = p.readByte();
        byte packetActivity = rawActivity;
        int skillId = p.readByte() & 0xff;
        int skillLv = p.readByte() & 0xff;
        short pOption = p.readShort();
        p.skip(8);

        if (traceArcanaMob) {
            log.info("[Mob8644001Trace] header map={} chr={} oid={} moveId={} activityByte={} nibbles={} skillId={} skillLv={} option={} mobPos={} remaining={}",
                    map.getId(), player.getName(), objectid, moveid, packetActivity, pNibbles,
                    skillId, skillLv, pOption, monster.getPosition(), p.available());
        }

        if (rawActivity >= 0) {
            rawActivity = (byte) (rawActivity & 0xFF >> 1);
        }

        boolean isAttack = inRangeInclusive(rawActivity, 24, 41);
        boolean isSkill = inRangeInclusive(rawActivity, 42, 59);

        if (traceArcanaMob) {
            log.info("[Mob8644001Trace] classified map={} oid={} activity={} attack={} skill={} castPos={}",
                    map.getId(), objectid, rawActivity, isAttack, isSkill,
                    isAttack ? (rawActivity - 24) / 2 : -1);
        }

        int useSkillId = 0;
        int useSkillLevel = 0;
        int requestedCastPos = isAttack ? (rawActivity - 24) / 2 : -1;
        int attackStatus = 0;
        boolean skillAccepted = false;

        if (isSkill) {
            useSkillId = skillId;
            useSkillLevel = skillLv;

            if (monster.hasSkill(useSkillId, useSkillLevel)) {
                MobSkillType mobSkillType = MobSkillType.from(useSkillId).orElseThrow();
                MobSkill toUse = MobSkillFactory.getMobSkillOrThrow(mobSkillType, useSkillLevel);

                if (monster.canUseSkill(toUse, true)) {
                    skillAccepted = true;
                    boolean handled = KaringBossCompat.handleProjectedSkillCast(
                            monster, useSkillId, useSkillLevel);
                    if (!handled) {
                        int animationTime = MonsterInformationProvider.getInstance().getMobSkillAnimationTime(toUse);
                        if (animationTime > 0 && toUse.getType() != MobSkillType.BANISH) {
                            toUse.applyDelayedEffect(player, monster, true, animationTime);
                        } else {
                            banishPlayers = new LinkedList<>();
                            toUse.applyEffect(player, monster, true, banishPlayers);
                        }
                    }
                }
            }
            if (traceKaringBoss && !skillAccepted) {
                rawActivity = -1;
                pOption = 0;
                useSkillId = 0;
                useSkillLevel = 0;
            }
        } else {
            attackStatus = monster.canUseAttack(requestedCastPos, isSkill);
            if (attackStatus < 1) {
                rawActivity = -1;
                pOption = 0;
            }
        }

        if (traceKaringBoss && (isAttack || isSkill)) {
            log.info("[KaringMoveTrace] map={} mob={} oid={} moveId={} packetActivity={} decodedActivity={} attack={} skill={} castPos={} attackStatus={} skillId={} skillLv={} option={}",
                    map.getId(), monster.getId(), objectid, moveid, packetActivity, rawActivity,
                    isAttack, isSkill, requestedCastPos, attackStatus, skillId, skillLv, pOption);
        }

        boolean nextMovementCouldBeSkill = !(isSkill || (pNibbles != 0));
        MobSkill nextUse = null;
        int nextSkillId = 0;
        int nextSkillLevel = 0;
        int mobMp = monster.getMp();
        if (nextMovementCouldBeSkill && monster.hasAnySkill()) {
            int hpPercent = (int) (((float) monster.getHp() / monster.getMaxHp()) * 100);
            for (MobSkillId skillToUse : monster.getSkillsInRandomOrder()) {
                MobSkill candidate = MobSkillFactory.getMobSkillOrThrow(skillToUse.type(), skillToUse.level());
                if (monster.canUseSkill(candidate, false)
                        && candidate.getHP() >= hpPercent
                        && mobMp >= candidate.getMpCon()) {
                    nextSkillId = skillToUse.type().getId();
                    nextSkillLevel = skillToUse.level();
                    nextUse = candidate;
                    break;
                }
            }
        }

        p.readByte();
        p.readInt(); // whatever
        short start_x = p.readShort(); // hmm.. startpos?
        short start_y = p.readShort(); // hmm...
        Point startPos = new Point(start_x, start_y - 2);
        Point serverStartPos = new Point(monster.getPosition());

        Boolean aggro = monster.aggroMoveLifeUpdate(player);
        if (aggro == null) {
            return;
        }

        if (nextUse != null) {
            c.sendPacket(PacketCreator.moveMonsterResponse(objectid, moveid, mobMp, aggro, nextSkillId, nextSkillLevel));
        } else {
            c.sendPacket(PacketCreator.moveMonsterResponse(objectid, moveid, mobMp, aggro));
        }


        try {
            int movementDataStart = p.getPosition();
            updatePosition(p, monster, -2);  // Thanks Doodle & ZERO傑洛 for noticing sponge-based bosses moving out of stage in case of no-offset applied
            long movementDataLength = p.getPosition() - movementDataStart; //how many bytes were read by updatePosition
            p.seek(movementDataStart);

            if (traceArcanaMob) {
                log.info("[Mob8644001Trace] parsed map={} oid={} activity={} movementBytes={} startPos={} serverStartPos={} resultingPos={}",
                        map.getId(), objectid, rawActivity, movementDataLength, startPos,
                        serverStartPos, monster.getPosition());
            }

            if (GameConfig.getServerBoolean("use_debug_show_life_move")) {
                log.info("{} rawAct: {}, opt: {}, skillId: {}, skillLv: {}, allowSkill: {}, mobMp: {}",
                        isSkill ? "SKILL" : (isAttack ? "ATTCK" : ""), rawActivity, pOption, useSkillId,
                        useSkillLevel, nextMovementCouldBeSkill, mobMp);
            }

            map.broadcastMessage(player, PacketCreator.moveMonster(objectid, nextMovementCouldBeSkill, rawActivity, useSkillId, useSkillLevel, pOption, startPos, p, movementDataLength), serverStartPos);
            if (traceArcanaMob) {
                log.info("[Mob8644001Trace] broadcast map={} oid={} activity={} nextSkill={}:{}",
                        map.getId(), objectid, rawActivity, nextSkillId, nextSkillLevel);
            }
            //updatePosition(res, monster, -2); //does this need to be done after the packet is broadcast?
            map.moveMonster(monster, monster.getPosition());
        } catch (EmptyMovementException e) {
            if (traceArcanaMob) {
                log.warn("[Mob8644001Trace] empty movement map={} oid={} activity={} remaining={}",
                        map.getId(), objectid, rawActivity, p.available());
            }
        }

        if (banishPlayers != null) {
            for (Character chr : banishPlayers) {
                chr.changeMapBanish(monster.getBanish().getMap(), monster.getBanish().getPortal(), monster.getBanish().getMsg());
            }
        }
    }

    private static boolean inRangeInclusive(Byte pVal, Integer pMin, Integer pMax) {
        return pVal >= pMin && pVal <= pMax;
    }
}
