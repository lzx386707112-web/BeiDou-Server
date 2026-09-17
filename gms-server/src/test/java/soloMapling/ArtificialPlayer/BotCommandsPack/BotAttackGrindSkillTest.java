package soloMapling.ArtificialPlayer.BotCommandsPack;

import org.gms.client.Job;
import org.gms.client.inventory.WeaponType;
import org.gms.constants.skills.Magician;
import org.gms.constants.skills.Pirate;
import org.gms.constants.skills.Rogue;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class BotAttackGrindSkillTest {
    @Test
    void magicianWithSwordDoesNotSendMagic() {
        assertEquals(0, BotAttack.grindSkillId(Job.MAGICIAN, WeaponType.SWORD1H));
    }

    @Test
    void magicianWithWandSendsMagicClaw() {
        assertEquals(Magician.MAGIC_CLAW, BotAttack.grindSkillId(Job.MAGICIAN, WeaponType.WAND));
    }

    @Test
    void beginnerThiefMatchesClawOrDagger() {
        assertEquals(Rogue.LUCKY_SEVEN, BotAttack.grindSkillId(Job.THIEF, WeaponType.CLAW));
        assertEquals(Rogue.DOUBLE_STAB, BotAttack.grindSkillId(Job.THIEF, WeaponType.DAGGER_THIEVES));
    }

    @Test
    void pirateMatchesGunOrKnuckle() {
        assertEquals(Pirate.DOUBLE_SHOT, BotAttack.grindSkillId(Job.PIRATE, WeaponType.GUN));
        assertEquals(Pirate.SOMERSAULT_KICK, BotAttack.grindSkillId(Job.PIRATE, WeaponType.KNUCKLE));
    }
}
