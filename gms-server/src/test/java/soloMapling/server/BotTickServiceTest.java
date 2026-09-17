package soloMapling.server;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BotTickServiceTest {
    @AfterEach
    void tearDown() {
        BotTickService.unregister(424242);
    }

    @Test
    void registerTracksBotUntilUnregister() {
        AtomicInteger ticks = new AtomicInteger();
        BotTickService.register(424242, ticks::incrementAndGet, 60_000, 60_000);
        assertTrue(BotTickService.isRegistered(424242));
        assertTrue(BotTickService.size() >= 1);
        BotTickService.unregister(424242);
        assertFalse(BotTickService.isRegistered(424242));
        assertEquals(0, ticks.get());
    }
}
