package org.gms.server.life;

import org.gms.client.Character;
import org.gms.client.status.MonsterStatus;
import org.gms.net.server.channel.handlers.AbstractDealDamageHandler.AttackInfo;
import org.gms.scripting.event.EventInstanceManager;
import org.gms.server.maps.AbstractAnimatedMapObject;
import org.gms.server.maps.Reactor;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Point;
import java.util.List;
import java.util.Map;

/** Legacy input and authoritative movement adapters, restricted to Seed instances. */
public final class SeedTowerCompat {
    private static final Logger log = LoggerFactory.getLogger(SeedTowerCompat.class);

    private SeedTowerCompat() {}

    private static EventInstanceManager instance(Character player) {
        EventInstanceManager eim = player.getEventInstance();
        return eim != null && "1".equals(eim.getProperty("seedTower")) ? eim : null;
    }

    public static boolean handleAttack(Character player, AttackInfo attack) {
        EventInstanceManager eim = instance(player);
        if (player.getMapId() != 992014000 || eim == null) {
            return false;
        }
        int target = 0;
        if (attack.skill == 0 && attack.allDamage != null) {
            for (int oid : attack.allDamage.keySet()) {
                Monster mob = player.getMap().getMonsterByOid(oid);
                if (mob == null || !mob.isAlive() || (mob.getId() != 9309116 && mob.getId() != 9309117)) {
                    continue;
                }
                Point pos = mob.getPosition();
                Point from = player.getPosition();
                int reach = attack.ranged ? 800 : 250;
                if (Math.abs(pos.x - from.x) <= reach && Math.abs(pos.y - from.y) <= 200) {
                    target = oid;
                    break;
                }
            }
        }
        try {
            eim.invokeScriptFunction("seedAttack", eim, player, attack.skill, target);
        } catch (Exception ex) {
            log.error("Seed shot failed instance={}", eim.getName(), ex);
        } finally {
            player.sendPacket(PacketCreator.enableActions());
        }
        return true;
    }

    public static boolean protectsTarget(Character player, Monster mob) {
        if (player == null || instance(player) == null) {
            return false;
        }
        return (player.getMapId() == 992014000 && (mob.getId() == 9309116 || mob.getId() == 9309117))
                || ((player.getMapId() == 992008000 || player.getMapId() == 992013000)
                && mob.getId() >= 9309400 && mob.getId() <= 9309402);
    }

    public static boolean controls(Character player, Monster mob) {
        EventInstanceManager eim = instance(player);
        return eim != null && "1".equals(eim.getProperty("seedControlled."
                + mob.getMap().getId() + "." + mob.getObjectId()));
    }

    public static boolean allowReactorHit(Character player, Reactor reactor) {
        EventInstanceManager eim = instance(player);
        if (eim != null && player.getMapId() == 992002000
                && reactor.getId() >= 9260004 && reactor.getId() <= 9260007) {
            return false;
        }
        if (eim == null || player.getMapId() != 992018000) {
            return true;
        }
        try {
            return Boolean.TRUE.equals(eim.invokeScriptFunction("seedReactorHit", eim, player, reactor));
        } catch (Exception ex) {
            log.error("Seed reactor failed instance={}", eim.getName(), ex);
            return false;
        }
    }

    public static void move(Monster mob, int x, int y, int duration, boolean flying) {
        Point from = new Point(mob.getPosition());
        Point next = new Point(x, y);
        int stance = (flying ? 0 : 2) + (x >= from.x ? 1 : 0);
        mob.setStance(stance);
        mob.getMap().moveMonster(mob, next);
        mob.getMap().broadcastMessage(PacketCreator.moveMonster(mob.getObjectId(), false, -1, 0, 0, 0,
                from, mob.getAbsoluteMovement(x, y, mob.getFh(), stance, duration,
                        (x - from.x) * 1000 / duration, (y - from.y) * 1000 / duration),
                AbstractAnimatedMapObject.IDLE_MOVEMENT_PACKET_LENGTH));
    }

    public static void spiderWeb(Monster mob) {
        MobSkill skill = MobSkillFactory.getMobSkillOrThrow(MobSkillType.PHYSICAL_AND_MAGIC_COUNTER, 1);
        mob.applyMonsterBuff(Map.of(MonsterStatus.WEAPON_REFLECT, 1, MonsterStatus.MAGIC_REFLECT, 1,
                MonsterStatus.WEAPON_IMMUNITY, 1, MonsterStatus.MAGIC_IMMUNITY, 1),
                4000, 6000, skill, List.of(4000));
    }
}
