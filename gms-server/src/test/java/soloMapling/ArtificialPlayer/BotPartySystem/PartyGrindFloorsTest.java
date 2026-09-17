package soloMapling.ArtificialPlayer.BotPartySystem;

import java.util.List;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PartyGrindFloorsTest {
    @Test
    void nearbyLedgesMergeIntoOneFloor() {
        List<PartyGrindFloors.Floor> floors = PartyGrindFloors.cluster(List.of(
                new PartyGrindFloors.Sample(100, 0, 200),
                new PartyGrindFloors.Sample(140, 50, 250),
                new PartyGrindFloors.Sample(400, -100, 100)
        ));
        assertEquals(2, floors.size());
        assertTrue(floors.get(0).containsY(120));
        assertFalse(floors.get(0).containsY(400));
        assertTrue(floors.get(1).containsY(400));
        assertEquals(0, floors.get(0).minX());
        assertEquals(250, floors.get(0).maxX());
    }

    @Test
    void emptySamplesStayEmpty() {
        assertTrue(PartyGrindFloors.cluster(List.of()).isEmpty());
    }
}
