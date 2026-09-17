package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.io.Serializable;
import java.util.Map;
import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.net.server.world.Party;
import org.gms.net.server.world.PartyCharacter;
import org.gms.server.ItemInformationProvider;
import org.gms.server.maps.FieldLimit;
import org.gms.server.maps.MapleMap;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotMovementProfile.class */
final class BotMovementProfile implements Serializable {
    private final int totalSpeedStat;
    private final int totalJumpStat;
    private final boolean snowShoes;
    private static final long serialVersionUID = 1;
    static final int STAT_BUCKET_SIZE = 5;
    static final int MAX_EFFECTIVE_SPEED_STAT = 200;
    static final int MAX_EFFECTIVE_JUMP_STAT = 123;
    static final int HASTE_MAX_SPEED = 155;
    static final int HASTE_MAX_JUMP = 123;
    static final int YOUNG_THIEF_SPEED = 150;
    static final int YOUNG_THIEF_JUMP = 115;
    static final int HASTE_SELF_MAX_LEVEL = 55;
    static final int PARTY_HASTE_THIEF_LEVEL = 60;
    static final int BASE_TOTAL_STAT = 100;
    static final BotMovementProfile BASE = new BotMovementProfile(BASE_TOTAL_STAT, BASE_TOTAL_STAT);

    public final String toString() {
        return getClass().getSimpleName();
    }

    public final int hashCode() {
        return System.identityHashCode(this);
    }

    public final boolean equals(Object o) {
        return this == o;
    }

    public int totalSpeedStat() {
        return this.totalSpeedStat;
    }

    public int totalJumpStat() {
        return this.totalJumpStat;
    }

    public boolean snowShoes() {
        return this.snowShoes;
    }

    BotMovementProfile(int totalSpeedStat, int totalJumpStat, boolean snowShoes) {
        int totalSpeedStat2 = bucketStat(totalSpeedStat);
        int totalJumpStat2 = bucketStat(totalJumpStat);
        int totalSpeedStat3 = Math.min(totalSpeedStat2, MAX_EFFECTIVE_SPEED_STAT);
        int totalJumpStat3 = Math.min(totalJumpStat2, 123);
        this.totalSpeedStat = totalSpeedStat3;
        this.totalJumpStat = totalJumpStat3;
        this.snowShoes = snowShoes;
    }

    BotMovementProfile(int totalSpeedStat, int totalJumpStat) {
        this(totalSpeedStat, totalJumpStat, false);
    }

    static BotMovementProfile base() {
        return BASE;
    }

    static BotMovementProfile fromCharacter(Character character) {
        int speedBaseline;
        int jumpBaseline;
        if (character == null) {
            return BASE;
        }
        if (hasForcedBaseMovementStats(character)) {
            return BASE;
        }
        int level = character.getLevel();
        boolean hasteThief = hasHasteSkill(character.getJob());
        if (hasteThief && level >= HASTE_SELF_MAX_LEVEL) {
            speedBaseline = HASTE_MAX_SPEED;
            jumpBaseline = 123;
        } else if (hasteThief) {
            speedBaseline = YOUNG_THIEF_SPEED;
            jumpBaseline = YOUNG_THIEF_JUMP;
        } else {
            speedBaseline = levelSpeedStat(level);
            jumpBaseline = levelJumpStat(level);
        }
        if (partyGrantsHaste(character)) {
            speedBaseline = Math.max(speedBaseline, HASTE_MAX_SPEED);
        }
        int totalSpeed = speedBaseline;
        int totalJump = jumpBaseline;
        return new BotMovementProfile(totalSpeed, totalJump, wearsSnowShoes(character));
    }

    private static boolean hasHasteSkill(Job job) {
        return job != null && (job.isA(Job.ASSASSIN) || job.isA(Job.BANDIT));
    }

    private static boolean partyGrantsHaste(Character character) {
        Party party = character.getParty();
        if (party == null) {
            return false;
        }
        for (PartyCharacter member : party.getMembers()) {
            if (member != null && member.getId() != character.getId() && member.isOnline() && member.getLevel() >= PARTY_HASTE_THIEF_LEVEL && hasHasteSkill(member.getJob())) {
                return true;
            }
        }
        return false;
    }

    private static int levelSpeedStat(int level) {
        if (level <= 9) {
            return YOUNG_THIEF_JUMP;
        }
        if (level <= 29) {
            return 125;
        }
        if (level <= 50) {
            return 130;
        }
        if (level <= 69) {
            return 135;
        }
        if (level <= BASE_TOTAL_STAT) {
            return 145;
        }
        return HASTE_MAX_SPEED;
    }

    private static int levelJumpStat(int level) {
        if (level <= 9) {
            return BASE_TOTAL_STAT;
        }
        if (level <= 29) {
            return 105;
        }
        if (level <= 50) {
            return 110;
        }
        if (level <= 69) {
            return YOUNG_THIEF_JUMP;
        }
        if (level <= BASE_TOTAL_STAT) {
            return 120;
        }
        return 123;
    }

    private static boolean wearsSnowShoes(Character character) {
        Map<String, Integer> stats;
        try {
            Item shoe = character.getInventory(InventoryType.EQUIPPED).getItem((short) -7);
            if (shoe != null && (stats = ItemInformationProvider.getInstance().getEquipStats(shoe.getItemId())) != null) {
                if (stats.getOrDefault("fs", 0).intValue() >= 1) {
                    return true;
                }
            }
            return false;
        } catch (Throwable th) {
            return false;
        }
    }

    private static boolean hasForcedBaseMovementStats(Character character) {
        MapleMap map = character.getMap();
        return map != null && FieldLimit.MOVEMENTSKILLS.check(map.getFieldLimit());
    }

    private static int bucketStat(int stat) {
        int clamped = Math.max(1, stat);
        if (clamped < STAT_BUCKET_SIZE) {
            return clamped;
        }
        return (int) (Math.round(clamped / 5.0d) * 5);
    }

    double speedMultiplier() {
        return this.totalSpeedStat / 100.0d;
    }

    double jumpMultiplier() {
        return this.totalJumpStat / 100.0d;
    }

    double walkVelocityPxs() {
        return BotMovementManager.cfg.WALK_VEL * speedMultiplier();
    }

    double hForcePxs() {
        return BotPhysicsEngine.cfg.HFORCE_PXS * speedMultiplier();
    }

    float jumpSpeedPxs() {
        return (float) (BotPhysicsEngine.cfg.JUMP_SPEED_PXS * jumpMultiplier());
    }

    float ropeJumpSpeedPxs() {
        return (float) (BotPhysicsEngine.cfg.JUMP_ROPE_PXS * jumpMultiplier());
    }
}
