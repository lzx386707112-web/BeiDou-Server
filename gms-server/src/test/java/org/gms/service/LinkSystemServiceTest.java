package org.gms.service;

import org.junit.jupiter.api.Test;

import java.sql.Timestamp;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LinkSystemServiceTest {
    @Test
    void stageBonusesUseRequestedLevelBoundaries() {
        assertEquals(0, LinkSystemService.stagePercent(149));
        assertEquals(3, LinkSystemService.stagePercent(150));
        assertEquals(3, LinkSystemService.stagePercent(199));
        assertEquals(7, LinkSystemService.stagePercent(200));
        assertEquals(7, LinkSystemService.stagePercent(254));
        assertEquals(10, LinkSystemService.stagePercent(255));

        assertEquals(0, LinkSystemService.stageHpMp(149));
        assertEquals(800, LinkSystemService.stageHpMp(150));
        assertEquals(1500, LinkSystemService.stageHpMp(200));
        assertEquals(2000, LinkSystemService.stageHpMp(255));
    }

    @Test
    void linkedCharacterBonusesAccumulateAcrossAllRequestedStats() {
        LinkSystemService.Bonus bonus = LinkSystemService.calculateBonus(List.of(149, 150, 200, 255));

        assertEquals(3, bonus.activeLinks());
        assertEquals(20, bonus.allStatPercent());
        assertEquals(20, bonus.finalDamagePercent());
        assertEquals(20, bonus.bossDamagePercent());
        assertEquals(20, bonus.expPercent());
        assertEquals(4300, bonus.hp());
        assertEquals(4300, bonus.mp());
        assertEquals(1.2f, bonus.expMultiplier());
    }

    @Test
    void creationTimeUsesCharacterIdAsStableTieBreaker() {
        Timestamp timestamp = Timestamp.valueOf("2026-09-03 12:00:00");

        assertTrue(LinkSystemService.isEarlier(timestamp, 10, timestamp, 11));
        assertFalse(LinkSystemService.isEarlier(timestamp, 11, timestamp, 10));
        assertFalse(LinkSystemService.isEarlier(timestamp, 10, timestamp, 10));
    }

    @Test
    void finalAndBossDamageBonusesApplyAtTheSharedDamageBoundary() {
        LinkSystemService.Bonus bonus = LinkSystemService.calculateBonus(List.of(150, 200, 255));

        assertEquals(1200, LinkSystemService.calculateDamage(bonus, false, 1000));
        assertEquals(1400, LinkSystemService.calculateDamage(bonus, true, 1000));
        assertEquals(Integer.MAX_VALUE,
                LinkSystemService.calculateDamage(bonus, true, Integer.MAX_VALUE));
    }
}
