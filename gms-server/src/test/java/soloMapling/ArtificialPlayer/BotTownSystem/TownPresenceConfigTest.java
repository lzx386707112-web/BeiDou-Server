package soloMapling.ArtificialPlayer.BotTownSystem;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TownPresenceConfigTest {
    @Test
    void townPresenceYamlLoadsWandererTowns() {
        var towns = TownPresenceConfig.reload();
        assertFalse(towns.isEmpty(), "TownPresence.yaml must load so town wanderers can spawn");
        int wanderers = 0;
        for (TownPresenceConfig.TownEntry town : towns) {
            assertTrue(town.mainMapId() > 0, town.name());
            wanderers += town.wanderers();
        }
        assertTrue(wanderers > 0);
    }
}
