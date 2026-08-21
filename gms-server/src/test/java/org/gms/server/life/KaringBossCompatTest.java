package org.gms.server.life;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class KaringBossCompatTest {
    @Test
    void regenProtectionUsesFullTmsAnimationDurations() {
        assertEquals(3240, KaringBossCompat.regenDurationMillis(8880830));
        assertEquals(2520, KaringBossCompat.regenDurationMillis(8880831));
        assertEquals(2340, KaringBossCompat.regenDurationMillis(8880832));
        assertEquals(6660, KaringBossCompat.regenDurationMillis(8880837));
        assertEquals(8100, KaringBossCompat.regenDurationMillis(8880842));
    }

    @Test
    void regularAttackCooldownsUseTmsCooltimeNotImpactDelay() {
        assertEquals(15000, KaringBossCompat.attackCooldownMillis(8880830, 0, 780));
        assertEquals(25000, KaringBossCompat.attackCooldownMillis(8880830, 2, 1080));
        assertEquals(60000, KaringBossCompat.attackCooldownMillis(8880831, 0, 2040));
        assertEquals(5400, KaringBossCompat.attackCooldownMillis(8880832, 2, 990));
        assertEquals(30000, KaringBossCompat.attackCooldownMillis(8880837, 4, 990));
        assertEquals(18000, KaringBossCompat.attackCooldownMillis(8880842, 2, 1440));
    }

    @Test
    void onlyFsmCompatibilityAttacksUseTheirMappedSkillForbid() {
        assertEquals(60000, KaringBossCompat.attackCooldownMillis(8880830, 3, 0));
        assertEquals(20000, KaringBossCompat.attackCooldownMillis(8880830, 4, 0));
        assertEquals(18000, KaringBossCompat.attackCooldownMillis(8880837, 2, 0));
        assertEquals(7000, KaringBossCompat.attackCooldownMillis(8880837, 5, 0));
        assertTrue(KaringBossCompat.isKaringBoss(8880842));
    }

    @Test
    void p2DarkPulseUsesTmsSkillForbid() {
        assertEquals(18000, KaringBossCompat.skillCooldownMillis(8880837, 128, 2, 0));
    }
}
