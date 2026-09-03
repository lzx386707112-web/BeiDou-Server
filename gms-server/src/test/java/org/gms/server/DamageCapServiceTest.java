package org.gms.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DamageCapServiceTest {
    @ParameterizedTest
    @CsvSource({
            "2431152, 300000",
            "2431153, 500000",
            "2431154, 2000000",
            "2431155, 10000000",
            "2431156, 100000000",
            "2431157, 500000000"
    })
    void stoneIdsMapToTheirNamedIncrements(int itemId, int increment) {
        assertTrue(DamageCapService.isBreakthroughStone(itemId));
        assertEquals(increment, DamageCapService.incrementForStone(itemId));
    }

    @Test
    void unknownItemsAreNotBreakthroughStones() {
        assertFalse(DamageCapService.isBreakthroughStone(2431151));
        assertEquals(0, DamageCapService.incrementForStone(2431151));
    }

    @Test
    void successfulRollRaisesTheCurrentCap() {
        DamageCapService.BreakthroughResult result = DamageCapService.resolve(
                DamageCapService.INITIAL_CAP, 300_000, true
        );

        assertTrue(result.success());
        assertTrue(result.changed());
        assertEquals(19_999_999, result.previousCap());
        assertEquals(20_299_999, result.currentCap());
    }

    @Test
    void failedRollLeavesTheCurrentCapUnchanged() {
        DamageCapService.BreakthroughResult result = DamageCapService.resolve(
                500_000_000, 100_000_000, false
        );

        assertFalse(result.success());
        assertFalse(result.changed());
        assertEquals(500_000_000, result.currentCap());
    }

    @Test
    void successfulRollCanReachTheTechnicalMaximumExactly() {
        DamageCapService.BreakthroughResult result = DamageCapService.resolve(
                Integer.MAX_VALUE - 500_000_000, 500_000_000, true
        );

        assertTrue(result.success());
        assertTrue(result.changed());
        assertEquals(Integer.MAX_VALUE, result.currentCap());
    }

    @Test
    void successfulRollBeyondTheTechnicalMaximumDoesNotChangeTheCap() {
        DamageCapService.BreakthroughResult result = DamageCapService.resolve(
                Integer.MAX_VALUE - 499_999_999, 500_000_000, true
        );

        assertTrue(result.success());
        assertFalse(result.changed());
        assertEquals(Integer.MAX_VALUE - 499_999_999, result.currentCap());
    }

    @Test
    void missingAndLegacyCapsNormalizeToTheInitialLimit() {
        assertEquals(DamageCapService.INITIAL_CAP, DamageCapService.normalizeCap(null));
        assertEquals(DamageCapService.INITIAL_CAP, DamageCapService.normalizeCap(0));
        assertEquals(25_000_000, DamageCapService.normalizeCap(25_000_000));
    }

    @Test
    void positiveAndCriticalEncodedDamageAreCappedPerLine() {
        int damageCap = 25_000_000;
        assertEquals(24_000_000, DamageCapService.capEncodedClientDamage(damageCap, 24_000_000));
        assertEquals(25_000_000, DamageCapService.capEncodedClientDamage(damageCap, 30_000_000));

        int criticalDamage = 30_000_000 | Integer.MIN_VALUE;
        int cappedCriticalDamage = 25_000_000 | Integer.MIN_VALUE;
        assertEquals(30_000_000, DamageCapService.decodeClientDamage(criticalDamage));
        assertEquals(cappedCriticalDamage,
                DamageCapService.capEncodedClientDamage(damageCap, criticalDamage));
        assertEquals(25_000_000,
                DamageCapService.decodeClientDamage(cappedCriticalDamage));
    }
}
