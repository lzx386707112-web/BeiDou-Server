package org.gms.server.life;

import org.gms.client.Character;
import org.gms.server.TimerManager;
import org.gms.server.maps.MapleMap;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Point;
import java.awt.Rectangle;

/** TMS timing projected onto contracts supported by the legacy client. */
public final class KaringBossCompat {
    private static final Logger log = LoggerFactory.getLogger(KaringBossCompat.class);
    private static final String GOONGI_SCREEN_EFFECT =
            "customSkill/karing/goongiScreenVideoLayer";
    private static final String DARK_PULSE_EFFECT =
            "customSkill/karing/darkPulseVideoLayer";

    private KaringBossCompat() {
    }

    public static boolean isKaringBoss(int mobId) {
        return mobId == 8880830 || mobId == 8880831 || mobId == 8880832
                || mobId == 8880837 || mobId == 8880842;
    }

    public static int regenDurationMillis(int mobId) {
        return switch (mobId) {
            case 8880830 -> 3240;
            case 8880831 -> 2520;
            case 8880832 -> 2340;
            case 8880837 -> 6660;
            case 8880842 -> 8100;
            default -> 0;
        };
    }

    public static int attackCooldownMillis(int mobId, int attackPosition, int fallback) {
        int[] cooldowns = switch (mobId) {
            case 8880830 -> new int[]{15000, 15000, 25000, 60000, 20000};
            case 8880831 -> new int[]{60000, 15000, 15000, 25000};
            case 8880832 -> new int[]{15000, 12000, 5400, 8000, 12000, 0};
            case 8880837 -> new int[]{12000, 12000, 18000, 15000, 30000, 7000};
            case 8880842 -> new int[]{12000, 12000, 18000, 15000};
            default -> null;
        };
        if (cooldowns == null || attackPosition < 0 || attackPosition >= cooldowns.length) {
            return fallback;
        }
        int cooldown = cooldowns[attackPosition];
        return cooldown > 0 ? cooldown : fallback;
    }

    public static long skillCooldownMillis(Monster monster, MobSkill skill) {
        return skillCooldownMillis(
                monster.getId(), skill.getId().type().getId(),
                skill.getId().level(), skill.getCoolTime());
    }

    static long skillCooldownMillis(int mobId, int skillId, int level, long fallback) {
        if (mobId == 8880830 && skillId == 128 && level == 1) {
            return 60000;
        }
        if (mobId == 8880830 && skillId == 126 && level == 7) {
            return 20000;
        }
        if (mobId == 8880831 && skillId == 123 && level == 3) {
            return 10000;
        }
        if (mobId == 8880831 && skillId == 120 && level == 5) {
            return 45000;
        }
        if (mobId == 8880837 && skillId == 128 && level == 2) {
            return 18000;
        }
        return fallback;
    }

    public static void protectDuringRegen(Monster monster) {
        int duration = regenDurationMillis(monster.getId());
        if (duration > 0) {
            monster.setDamageBlockedUntil(System.currentTimeMillis() + duration);
        }
    }

    /**
     * Handles modern skills that were assigned legacy IDs solely so v83 can
     * request and animate them. Returning true suppresses the unrelated legacy
     * disease represented by that compatibility ID.
     */
    public static boolean handleProjectedSkillCast(Monster monster, int skillId, int level) {
        if (monster.getId() == 8880830 && skillId == 128 && level == 1) {
            castFixedDamageSkill(
                    monster,
                    GOONGI_SCREEN_EFFECT,
                    1560,
                    100,
                    new Rectangle(-600, -1000, 1201, 1001));
            return true;
        }
        if (monster.getId() == 8880830 && skillId == 126 && level == 7) {
            castFixedDamageSkill(
                    monster,
                    null,
                    780,
                    30,
                    new Rectangle(-215, -325, 554, 333));
            return true;
        }
        if (monster.getId() == 8880837 && skillId == 128 && level == 2) {
            castFixedDamageSkill(
                    monster,
                    DARK_PULSE_EFFECT,
                    2370,
                    25,
                    new Rectangle(-800, -800, 1601, 1601));
            return true;
        }
        return monster.getId() == 8880831
                && ((skillId == 123 && level == 3) || (skillId == 120 && level == 5));
    }

    private static void castFixedDamageSkill(
            Monster monster,
            String effect,
            int impactDelay,
            int damagePercent,
            Rectangle relativeRange) {
        MapleMap map = monster.getMap();
        if (effect != null) {
            map.broadcastMessage(PacketCreator.showEffect(effect));
        }
        int objectId = monster.getObjectId();
        TimerManager.getInstance().schedule(() -> {
            if (!monster.isAlive() || monster.getMap() != map
                    || map.getMonsterByOid(objectId) != monster) {
                return;
            }
            Point mobPosition = monster.getPosition();
            Rectangle impactRange = new Rectangle(
                    mobPosition.x + relativeRange.x,
                    mobPosition.y + relativeRange.y,
                    relativeRange.width,
                    relativeRange.height);
            for (Character character : map.getAllPlayers()) {
                if (character.isAlive() && impactRange.contains(character.getPosition())) {
                    damageCharacter(monster, character, damagePercent);
                }
            }
        }, impactDelay);
    }

    private static void damageCharacter(Monster monster, Character character, int percent) {
        int damage = Math.max(1, (int) ((long) character.getMaxHp() * percent / 100));
        character.addHP(-damage);
        monster.getMap().broadcastMessage(
                character,
                PacketCreator.damagePlayer(
                        0, monster.getId(), character.getId(), damage, 0, 0,
                        false, 0, true, monster.getObjectId(), 0, 0),
                false);
        log.info("[KaringSkillTrace] map={} mob={} oid={} chr={} damagePercent={} damage={} hpAfter={}",
                monster.getMap().getId(), monster.getId(), monster.getObjectId(),
                character.getName(), percent, damage, character.getHp());
    }
}
