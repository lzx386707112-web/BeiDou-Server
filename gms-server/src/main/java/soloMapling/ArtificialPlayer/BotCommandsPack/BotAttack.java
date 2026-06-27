package soloMapling.ArtificialPlayer.BotCommandsPack;

import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Item;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.WeaponType;
import org.gms.constants.skills.*;
import org.gms.server.ItemInformationProvider;
import org.gms.server.life.Monster;
import soloMapling.ArtificialPlayer.BotAttackSystem.BotAttackData;
import soloMapling.server.ExecutorServiceManager;
import org.gms.util.PacketCreator;

import java.util.Collections;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.facingLeft;

/**
 * Server-side attack animation helper for bots. 
 * Credit to NuTNNuT for attack animation values and code reference
 *
 * Bots have no real client, so they don't generate close-range-damage packets
 * the way players do. This helper synthesizes the broadcast packet directly so
 * other clients see the swing animation. We do NOT couple this to any actual
 * damage application — when the swing should also hit a reactor or monster,
 * the caller invokes the relevant logic separately (e.g. CustomReactor.hitReactor).
 *
 * Packet byte semantics in this Cosmic build (verified against AbstractDealDamageHandler.parseDamage):
 *   direction byte = body action id from Character/00002000.img (e.g. swingO1 = 5, swingP1 = 13)
 *   stance    byte = facing mask (0x80 = facing left, 0x00 = facing right)
 *   display   byte = 0 for a basic (non-skill) attack
 *   speed     byte = weapon attackSpeed (2..9; lower is faster). 4 is a safe default.
 *
 * The body-action id MUST match the equipped weapon class — a 1H swingO1 on a polearm
 * renders nothing. {@link BotAttackData#randomActionFor} picks the right variant.
 */
public final class BotAttack {

    /** Equip slot id for the main-hand weapon in v83. */
    private static final short EQUIP_SLOT_WEAPON = -11;

    private BotAttack() {}

    /**
     * Broadcast a basic Ctrl-attack swing animation. Pure visual; no damage,
     * no targets, no skill. Caller is responsible for any follow-up damage
     * application (e.g. reactor hit). The animation is selected based on the
     * bot's currently equipped weapon class.
     */
    public static void basicSwing(Character chr) {
        if (chr == null) return;

        broadcastCloseRangeAttack(chr, 0, 0, Collections.emptyMap());
    }

    /**
     * Broadcasts a real-looking one-target attack packet against a boss. Unlike
     * the social skill visuals, this packet carries the monster oid and damage,
     * so support/buff effects are not presented as damaging attacks.
     */
    public static boolean bossAttack(Character chr, Monster boss, int damage) {
        if (chr == null || boss == null || damage <= 0) return false;

        BossAttackSkill skill = resolveBossAttackSkill(chr.getJob());
        if (skill.skillId() <= 0 || skill.hitCount() <= 0) {
            return false;
        }
        Map<Integer, List<Integer>> targetDamage = Collections.singletonMap(
                boss.getObjectId(),
                splitDamage(damage, skill.hitCount())
        );
        broadcastAttack(chr, skill, targetDamage);
        broadcastSkillDamageNumbers(chr, boss, targetDamage.get(boss.getObjectId()));
        return true;
    }

    private static void broadcastAttack(Character chr, BossAttackSkill skill, Map<Integer, List<Integer>> targets) {
        showSkillVisual(chr, skill);
        switch (skill.packetKind()) {
            case MAGIC -> broadcastMagicAttack(chr, skill, targets);
            case RANGED -> broadcastRangedAttack(chr, skill, targets);
            default -> broadcastCloseRangeAttack(chr, skill.skillId(), skill.skillLevel(), targets);
        }
    }

    private static void showSkillVisual(Character chr, BossAttackSkill skill) {
        if (skill.skillId() <= 0 || chr == null || chr.getMap() == null) {
            return;
        }
        byte direction = (byte) (facingLeft(chr) ? 0 : 1);
        chr.getMap().broadcastMessage(chr,
                PacketCreator.showBuffEffect(chr.getId(), skill.skillId(), skill.skillLevel(), 1, direction), false);
    }

    private static void broadcastSkillDamageNumbers(Character chr, Monster boss, List<Integer> damageLines) {
        if (chr == null || chr.getMap() == null || boss == null || damageLines == null || damageLines.isEmpty()) {
            return;
        }
        for (int i = 0; i < damageLines.size(); i++) {
            Integer damageLine = damageLines.get(i);
            if (damageLine != null && damageLine > 0) {
                if (i == 0) {
                    chr.getMap().broadcastMessage(PacketCreator.damageMonster(boss.getObjectId(), damageLine));
                } else {
                    int delayedDamage = damageLine;
                    ExecutorServiceManager.getScheduledExecutorService().schedule(
                            () -> {
                                if (chr.getMap() != null && boss.isAlive()) {
                                    chr.getMap().broadcastMessage(PacketCreator.damageMonster(boss.getObjectId(), delayedDamage));
                                }
                            },
                            i * 80L,
                            TimeUnit.MILLISECONDS
                    );
                }
            }
        }
    }

    private static void broadcastCloseRangeAttack(Character chr, int skill, int skillLevel, Map<Integer, List<Integer>> targets) {
        int facingMask = facingLeft(chr) ? BotAttackData.FACING_LEFT_MASK : BotAttackData.FACING_RIGHT_MASK;
        int direction = facingLeft(chr) ? 0 : 1;
        WeaponType weaponType = resolveEquippedWeaponType(chr);
        int bodyActionId = BotAttackData.randomActionFor(weaponType);
        int targetCount = targets.size();
        int hitCount = targetCount == 0 ? 0 : targets.values().iterator().next().size();
        int numAttackedAndDamage = (targetCount << 4) + hitCount;

        chr.getMap().broadcastMessage(
                chr,
                PacketCreator.closeRangeAttack(
                        chr,
                        skill,
                        skillLevel,
                        /* stance       */ facingMask,
                        numAttackedAndDamage,
                        targets,
                        /* speed        */ BotAttackData.DEFAULT_ATTACK_SPEED,
                        /* direction    */ direction,
                        /* display      */ bodyActionId
                ),
                /* repeatToSource */ false
        );
    }

    private static void broadcastRangedAttack(Character chr, BossAttackSkill skill, Map<Integer, List<Integer>> targets) {
        int facingMask = facingLeft(chr) ? BotAttackData.FACING_LEFT_MASK : BotAttackData.FACING_RIGHT_MASK;
        int direction = facingLeft(chr) ? 0 : 1;
        int targetCount = targets.size();
        int hitCount = targetCount == 0 ? 0 : targets.values().iterator().next().size();
        int numAttackedAndDamage = (targetCount << 4) + hitCount;

        chr.getMap().broadcastMessage(
                chr,
                PacketCreator.rangedAttack(
                        chr,
                        skill.skillId(),
                        skill.skillLevel(),
                        facingMask,
                        numAttackedAndDamage,
                        0,
                        targets,
                        BotAttackData.DEFAULT_ATTACK_SPEED,
                        direction,
                        0
                ),
                /* repeatToSource */ false
        );
    }

    private static void broadcastMagicAttack(Character chr, BossAttackSkill skill, Map<Integer, List<Integer>> targets) {
        int facingMask = facingLeft(chr) ? BotAttackData.FACING_LEFT_MASK : BotAttackData.FACING_RIGHT_MASK;
        int direction = facingLeft(chr) ? 0 : 1;
        int targetCount = targets.size();
        int hitCount = targetCount == 0 ? 0 : targets.values().iterator().next().size();
        int numAttackedAndDamage = (targetCount << 4) + hitCount;

        chr.getMap().broadcastMessage(
                chr,
                PacketCreator.magicAttack(
                        chr,
                        skill.skillId(),
                        skill.skillLevel(),
                        facingMask,
                        numAttackedAndDamage,
                        targets,
                        -1,
                        BotAttackData.DEFAULT_ATTACK_SPEED,
                        direction,
                        0
                ),
                /* repeatToSource */ false
        );
    }

    private static WeaponType resolveEquippedWeaponType(Character chr) {
        Item weapon = chr.getInventory(InventoryType.EQUIPPED).getItem(EQUIP_SLOT_WEAPON);
        if (weapon == null) return null;
        return ItemInformationProvider.getInstance().getWeaponType(weapon.getItemId());
    }

    private static BossAttackSkill resolveBossAttackSkill(Job job) {
        if (job == null) {
            return new BossAttackSkill(0, 0, 1, PacketKind.CLOSE);
        }
        if (job == Job.WARRIOR || job == Job.FIGHTER || job == Job.PAGE || job == Job.SPEARMAN) {
            return new BossAttackSkill(Warrior.SLASH_BLAST, 20, 1, PacketKind.CLOSE);
        }
        if (job == Job.CRUSADER) {
            return new BossAttackSkill(Crusader.SWORD_COMA, 30, 1, PacketKind.CLOSE);
        }
        if (job.isA(Job.FIGHTER) || job.isA(Job.DAWNWARRIOR1)) {
            return new BossAttackSkill(job.isA(Job.DAWNWARRIOR1) ? DawnWarrior.BRANDISH : Hero.BRANDISH, 30, 2, PacketKind.CLOSE);
        }
        if (job == Job.WHITEKNIGHT) {
            return new BossAttackSkill(WhiteKnight.CHARGE_BLOW, 30, 1, PacketKind.CLOSE);
        }
        if (job.isA(Job.PAGE)) {
            return new BossAttackSkill(Paladin.BLAST, 30, 1, PacketKind.CLOSE);
        }
        if (job == Job.DRAGONKNIGHT) {
            return new BossAttackSkill(DragonKnight.SPEAR_CRUSHER, 30, 3, PacketKind.CLOSE);
        }
        if (job.isA(Job.SPEARMAN)) {
            return new BossAttackSkill(DragonKnight.SPEAR_CRUSHER, 30, 3, PacketKind.CLOSE);
        }
        if (job == Job.MAGICIAN) {
            return new BossAttackSkill(Magician.MAGIC_CLAW, 20, 2, PacketKind.MAGIC);
        }
        if (job == Job.FP_WIZARD || job == Job.BLAZEWIZARD2) {
            return new BossAttackSkill(FPWizard.FIRE_ARROW, 30, 1, PacketKind.MAGIC);
        }
        if (job == Job.FP_MAGE || job == Job.BLAZEWIZARD3) {
            return new BossAttackSkill(job == Job.BLAZEWIZARD3 ? BlazeWizard.FIRE_STRIKE : FPMage.EXPLOSION, 30, 1, PacketKind.MAGIC);
        }
        if (job.isA(Job.FP_WIZARD) || job.isA(Job.BLAZEWIZARD1)) {
            return new BossAttackSkill(job.isA(Job.BLAZEWIZARD1) ? BlazeWizard.METEOR_SHOWER : FPArchMage.METEOR_SHOWER, 30, 1, PacketKind.MAGIC);
        }
        if (job == Job.IL_WIZARD) {
            return new BossAttackSkill(ILWizard.COLD_BEAM, 30, 1, PacketKind.MAGIC);
        }
        if (job == Job.IL_MAGE) {
            return new BossAttackSkill(ILMage.ICE_STRIKE, 30, 1, PacketKind.MAGIC);
        }
        if (job.isA(Job.IL_WIZARD)) {
            return new BossAttackSkill(ILArchMage.CHAIN_LIGHTNING, 30, 1, PacketKind.MAGIC);
        }
        if (job == Job.CLERIC) {
            return new BossAttackSkill(Cleric.HOLY_ARROW, 30, 1, PacketKind.MAGIC);
        }
        if (job == Job.PRIEST) {
            return new BossAttackSkill(Priest.SHINING_RAY, 30, 1, PacketKind.MAGIC);
        }
        if (job.isA(Job.CLERIC)) {
            return new BossAttackSkill(Bishop.ANGEL_RAY, 30, 1, PacketKind.MAGIC);
        }
        if (job == Job.BOWMAN) {
            return new BossAttackSkill(3001004, 20, 2, PacketKind.RANGED);
        }
        if (job == Job.HUNTER || job == Job.CROSSBOWMAN) {
            return new BossAttackSkill(job == Job.HUNTER ? Hunter.ARROW_BOMB : Crossbowman.IRON_ARROW, 30, 1, PacketKind.RANGED);
        }
        if (job == Job.RANGER) {
            return new BossAttackSkill(Ranger.STRAFE, 30, 4, PacketKind.RANGED);
        }
        if (job.isA(Job.HUNTER) || job.isA(Job.WINDARCHER1)) {
            return new BossAttackSkill(job.isA(Job.WINDARCHER1) ? WindArcher.STRAFE : Ranger.STRAFE, 30, 4, PacketKind.RANGED);
        }
        if (job == Job.SNIPER) {
            return new BossAttackSkill(Sniper.STRAFE, 30, 4, PacketKind.RANGED);
        }
        if (job.isA(Job.CROSSBOWMAN)) {
            return new BossAttackSkill(Sniper.STRAFE, 30, 4, PacketKind.RANGED);
        }
        if (job == Job.THIEF) {
            return new BossAttackSkill(Rogue.DOUBLE_STAB, 20, 2, PacketKind.CLOSE);
        }
        if (job == Job.ASSASSIN) {
            return new BossAttackSkill(Rogue.LUCKY_SEVEN, 20, 2, PacketKind.RANGED);
        }
        if (job == Job.HERMIT) {
            return new BossAttackSkill(Hermit.AVENGER, 30, 1, PacketKind.RANGED);
        }
        if (job.isA(Job.ASSASSIN) || job.isA(Job.NIGHTWALKER1)) {
            return new BossAttackSkill(job.isA(Job.NIGHTWALKER1) ? NightWalker.TRIPLE_THROW : NightLord.TRIPLE_THROW, 30, 3, PacketKind.RANGED);
        }
        if (job == Job.BANDIT) {
            return new BossAttackSkill(Bandit.SAVAGE_BLOW, 30, 6, PacketKind.CLOSE);
        }
        if (job == Job.CHIEFBANDIT) {
            return new BossAttackSkill(ChiefBandit.BAND_OF_THIEVES, 30, 1, PacketKind.CLOSE);
        }
        if (job.isA(Job.BANDIT)) {
            return new BossAttackSkill(Shadower.BOOMERANG_STEP, 30, 2, PacketKind.CLOSE);
        }
        if (job == Job.PIRATE) {
            return new BossAttackSkill(Pirate.SOMERSAULT_KICK, 20, 1, PacketKind.CLOSE);
        }
        if (job == Job.BRAWLER || job == Job.THUNDERBREAKER2) {
            return new BossAttackSkill(job == Job.THUNDERBREAKER2 ? ThunderBreaker.ENERGY_BLAST : Brawler.DOUBLE_UPPERCUT, 30, 1, PacketKind.CLOSE);
        }
        if (job == Job.MARAUDER || job == Job.THUNDERBREAKER3) {
            return new BossAttackSkill(job == Job.THUNDERBREAKER3 ? ThunderBreaker.BARRAGE : Marauder.ENERGY_BLAST, 30, job == Job.THUNDERBREAKER3 ? 6 : 1, PacketKind.CLOSE);
        }
        if (job.isA(Job.BRAWLER) || job.isA(Job.THUNDERBREAKER1)) {
            return new BossAttackSkill(job.isA(Job.THUNDERBREAKER1) ? ThunderBreaker.BARRAGE : Buccaneer.BARRAGE, 30, 6, PacketKind.CLOSE);
        }
        if (job == Job.GUNSLINGER) {
            return new BossAttackSkill(Pirate.DOUBLE_SHOT, 20, 2, PacketKind.RANGED);
        }
        if (job == Job.OUTLAW) {
            return new BossAttackSkill(Outlaw.BURST_FIRE, 30, 3, PacketKind.RANGED);
        }
        if (job.isA(Job.GUNSLINGER)) {
            return new BossAttackSkill(Corsair.BATTLESHIP_CANNON, 30, 4, PacketKind.RANGED);
        }
        return new BossAttackSkill(0, 0, 1, PacketKind.CLOSE);
    }

    private static List<Integer> splitDamage(int totalDamage, int hitCount) {
        int hits = Math.max(1, hitCount);
        List<Integer> values = new ArrayList<>(hits);
        int base = Math.max(1, totalDamage / hits);
        int remaining = totalDamage;
        for (int i = 0; i < hits; i++) {
            int hit = (i == hits - 1) ? remaining : Math.min(base, remaining);
            values.add(Math.max(1, hit));
            remaining -= hit;
        }
        return values;
    }

    private enum PacketKind {
        CLOSE,
        RANGED,
        MAGIC
    }

    private record BossAttackSkill(int skillId, int skillLevel, int hitCount, PacketKind packetKind) {
    }
}
