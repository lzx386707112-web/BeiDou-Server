package org.gms.server.life;

import org.junit.jupiter.api.Test;

import java.awt.Point;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LucidBossCompatTest {
    @Test
    void butterflyScheduleMatchesTmsHpBands() {
        assertEquals(5000, LucidBossCompat.butterflyIntervalMillis(100));
        assertEquals(5000, LucidBossCompat.butterflyIntervalMillis(90));
        assertEquals(4500, LucidBossCompat.butterflyIntervalMillis(89));
        assertEquals(4000, LucidBossCompat.butterflyIntervalMillis(69));
        assertEquals(3000, LucidBossCompat.butterflyIntervalMillis(49));
        assertEquals(2000, LucidBossCompat.butterflyIntervalMillis(19));

        assertEquals(5, LucidBossCompat.butterflyCreateCount(100));
        assertEquals(7, LucidBossCompat.butterflyCreateCount(89));
        assertEquals(10, LucidBossCompat.butterflyCreateCount(69));
        assertEquals(15, LucidBossCompat.butterflyCreateCount(49));
        assertEquals(20, LucidBossCompat.butterflyCreateCount(19));
    }

    @Test
    void onlyTheThreeEncounterBossesAreClassifiedAsLucid() {
        assertTrue(LucidBossCompat.isLucidBoss(8880140));
        assertTrue(LucidBossCompat.isLucidBoss(8880141));
        assertTrue(LucidBossCompat.isLucidBoss(8880142));
        assertFalse(LucidBossCompat.isLucidBoss(8880164));
    }

    @Test
    void rushPathKeepsTheTmsStartAndEndCoordinates() {
        assertEquals(new Point(685, -510), LucidBossCompat.rushPositionAt(0));
        assertEquals(new Point(978, -742), LucidBossCompat.rushPositionAt(3000));
        assertEquals(new Point(685, -510), LucidBossCompat.rushPositionAt(-1));
        assertEquals(new Point(978, -742), LucidBossCompat.rushPositionAt(4000));
    }
}
