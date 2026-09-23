package org.gms.server.life;

import org.gms.client.Character;
import org.gms.util.PacketCreator;

import java.util.Map;

/** Compatibility projection for the TMS Root Abyss boss skill tables. */
public final class RootAbyssBossCompat {
    private static final int PIERRE_RED = 8900001;
    private static final int PIERRE_BLUE = 8900002;
    private static final int VELLUM = 8930000;
    private static final String VELLUM_ATTACK10_SCREEN =
            "customSkill/rootAbyss/vellumAttack10VideoLayer";
    private static final String VELLUM_ATTACK11_SCREEN =
            "customSkill/rootAbyss/vellumAttack11VideoLayer";

    private static final Map<MobSkillId, Integer> PROJECTED_LEVELS = Map.ofEntries(
            Map.entry(new MobSkillId(MobSkillType.SUMMON_170, 10), 237),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_170, 11), 238),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_170, 13), 239),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_170, 14), 240),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_191, 1), 241),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_191, 2), 242),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_201, 40), 243),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_201, 47), 244),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_201, 48), 245),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_201, 51), 246),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_201, 52), 247),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_201, 53), 248),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_203, 1), 249),
            Map.entry(new MobSkillId(MobSkillType.SUMMON_188, 1), 250)
    );

    private RootAbyssBossCompat() {
    }

    /**
     * The v83 client cannot load modern MobSkill roots 188/191/201/203 or
     * modern 170 levels. Send reserved 200/* levels while the server keeps
     * and executes the real TMS skill IDs.
     */
    public static MobSkillId projectSkillForClient(int mobId, MobSkillId skill) {
        if (!isRootAbyssMob(mobId)) {
            return skill;
        }
        Integer level = PROJECTED_LEVELS.get(skill);
        return level == null ? skill : new MobSkillId(MobSkillType.SUMMON, level);
    }

    /** Mirror damage between Pierre's red/blue pair (TMS linkHP=1). */
    public static void mirrorPierreDamage(Character attacker, Monster damaged, int damage) {
        int peerId = switch (damaged.getId()) {
            case PIERRE_RED -> PIERRE_BLUE;
            case PIERRE_BLUE -> PIERRE_RED;
            default -> 0;
        };
        if (peerId == 0 || damage <= 0 || damaged.getMap() == null) {
            return;
        }
        Monster peer = damaged.getMap().getMonsterById(peerId);
        if (peer == null || !peer.isAlive()) {
            return;
        }
        boolean killed = peer.damage(attacker, damage, false);
        if (killed) {
            // The struck twin owns the real kill/drop. The linked peer is a
            // visual half of the same HP pool and must not award a duplicate.
            damaged.getMap().killMonster(peer, null, false);
        }
    }

    public static boolean isPierreBoss(int mobId) {
        return mobId >= 8900000 && mobId <= 8900002;
    }

    public static boolean isQueenBoss(int mobId) {
        return mobId >= 8920000 && mobId <= 8920002;
    }

    public static boolean isVellumVisualSkill(int mobId, MobSkillId skill) {
        return mobId == VELLUM && ((skill.type() == MobSkillType.SUMMON
                && skill.level() >= 251 && skill.level() <= 255)
                || (skill.type() == MobSkillType.ATTACK_UP && skill.level() == 30));
    }

    public static void playVellumScreen(Monster monster, int skillActionIndex) {
        String screen = switch (skillActionIndex) {
            case 1 -> VELLUM_ATTACK10_SCREEN;
            case 2 -> VELLUM_ATTACK11_SCREEN;
            default -> null;
        };
        if (screen != null) {
            monster.getMap().broadcastMessage(PacketCreator.showEffect(screen));
        }
    }

    private static boolean isRootAbyssMob(int mobId) {
        return (mobId >= 8900000 && mobId <= 8930001);
    }
}
