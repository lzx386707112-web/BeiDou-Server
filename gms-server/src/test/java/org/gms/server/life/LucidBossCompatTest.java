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
    void seduceCooldownIsOneMinuteForAllThreePhases() {
        assertEquals(60_000, LucidBossCompat.skillCooldownMillis(8880140, 128, 16, 20_000));
        assertEquals(60_000, LucidBossCompat.skillCooldownMillis(8880141, 128, 16, 20_000));
        assertEquals(60_000, LucidBossCompat.skillCooldownMillis(8880142, 128, 10, 50_000));
        assertEquals(20_000, LucidBossCompat.skillCooldownMillis(8880140, 128, 15, 20_000));
        assertEquals(20_000, LucidBossCompat.skillCooldownMillis(8880140, 127, 16, 20_000));
    }

    @Test
    void stunAttackCooldownIsLimitedToTheTwoDiseaseAttacks() {
        assertTrue(LucidBossCompat.usesAttackCooldown(8880140, 1));
        assertTrue(LucidBossCompat.usesAttackCooldown(8880141, 2));
        assertFalse(LucidBossCompat.usesAttackCooldown(8880140, 0));
        assertFalse(LucidBossCompat.usesAttackCooldown(8880141, 1));
        assertFalse(LucidBossCompat.usesAttackCooldown(8880142, 1));

        assertEquals(60_000, LucidBossCompat.attackCooldownMillis(8880140, 1, 1200));
        assertEquals(60_000, LucidBossCompat.attackCooldownMillis(8880141, 2, 1200));
        assertEquals(1200, LucidBossCompat.attackCooldownMillis(8880140, 0, 1200));
    }

    @Test
    void rushPathKeepsTheTmsStartAndEndCoordinates() {
        assertEquals(new Point(685, -510), LucidBossCompat.rushPositionAt(0));
        assertEquals(new Point(978, -742), LucidBossCompat.rushPositionAt(3000));
        assertEquals(new Point(685, -510), LucidBossCompat.rushPositionAt(-1));
        assertEquals(new Point(978, -742), LucidBossCompat.rushPositionAt(4000));
    }
}
