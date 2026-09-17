package soloMapling.ArtificialPlayer.BotPartySystem;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

class BotDamageModelTest {
    @Test
    void highHpMobsTakeAShareEachHit() {
        int damage = BotDamageModel.lineDamage(1, 40, 18_000);
        assertTrue(damage >= 1000, "expected at least 1/18 of 18000, got " + damage);
    }

    @Test
    void lowHpMobsUseJobBand() {
        int damage = BotDamageModel.lineDamage(1, 40, 100);
        assertTrue(damage >= 150, "job band should exceed tiny HP share, got " + damage);
    }
}
