package soloMapling.ArtificialPlayer.BotDecoratorSystem;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class NXItemPoolShowcaseRingsTest {
    private static final int SHOWCASE_RING_COUNT = 167 + 183 + 43 + 16;

    @Test
    void mergeAddsSoulBiwangNameTagAndChatRingsWithoutDroppingExisting() {
        Map<String, List<NXItemPool.PoolItem>> pools = new HashMap<>();
        pools.put("rings", new ArrayList<>(List.of(new NXItemPool.PoolItem(1112001, NXItemPool.GENDER_UNISEX))));

        int added = NXItemPool.mergeShowcaseRings(pools);
        assertEquals(SHOWCASE_RING_COUNT, added);

        Set<Integer> ids = new HashSet<>();
        for (NXItemPool.PoolItem item : pools.get("rings")) {
            ids.add(item.id);
        }
        assertTrue(ids.contains(1112001));
        assertTrue(ids.contains(1112100));
        assertTrue(ids.contains(1112138));
        assertTrue(ids.contains(1112200));
        assertTrue(ids.contains(1112245));
        assertTrue(ids.contains(1112724));
        assertTrue(ids.contains(1112808));
        assertTrue(ids.contains(1115003));
        assertTrue(ids.contains(1115100));
        assertTrue(ids.contains(1115198));
        assertTrue(ids.contains(1118000));
        assertTrue(ids.contains(1118042));
        assertTrue(ids.contains(1118063));
        assertTrue(ids.contains(1118078));
        assertFalse(ids.contains(1112128));
        assertFalse(ids.contains(1112240));
        assertFalse(ids.contains(1118043));
        assertFalse(ids.contains(1118062));
    }

    @Test
    void mergeIsIdempotent() {
        Map<String, List<NXItemPool.PoolItem>> pools = new HashMap<>();
        assertEquals(SHOWCASE_RING_COUNT, NXItemPool.mergeShowcaseRings(pools));
        assertEquals(0, NXItemPool.mergeShowcaseRings(pools));
        assertEquals(SHOWCASE_RING_COUNT, pools.get("rings").size());
    }
}
