package org.gms.server.life;

import org.junit.jupiter.api.Test;

import java.awt.Point;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MonsterVacCompatTest {
    @Test
    void durationIsTenMinutesAndRejectsSecondUse() {
        assertEquals(2431158, MonsterVacCompat.ITEM_ID);
        assertEquals(10 * 60 * 1000L, MonsterVacCompat.DURATION_MS);
        assertTrue(MonsterVacCompat.canStart(false));
        assertFalse(MonsterVacCompat.canStart(true));
    }

    @Test
    void expiresAtDeadlineAndSkipsBossOrFake() {
        long expireAt = 1_000_000L;
        assertTrue(MonsterVacCompat.isActive(expireAt - 1, expireAt));
        assertFalse(MonsterVacCompat.isActive(expireAt, expireAt));
        assertTrue(MonsterVacCompat.isPullable(true, false, false));
        assertFalse(MonsterVacCompat.isPullable(false, false, false));
        assertFalse(MonsterVacCompat.isPullable(true, true, false));
        assertFalse(MonsterVacCompat.isPullable(true, false, true));
        assertEquals(2500L, MonsterVacCompat.STUN_DURATION_MS);
        assertEquals(1111008, MonsterVacCompat.STUN_SKILL_ID);
        assertEquals("monster_vac_stun_enabled", MonsterVacCompat.STUN_ENABLED_CONFIG);
    }

    @Test
    void pullStepsFromSpawnInsteadOfSnappingToVacPoint() {
        Point spawn = new Point(0, 200);
        Point vac = new Point(800, 200);
        Point first = MonsterVacCompat.stepToward(spawn, vac, MonsterVacCompat.PULL_STEP_PX);
        assertNotEquals(vac, first);
        assertEquals(spawn.x + MonsterVacCompat.PULL_STEP_PX, first.x);
        assertEquals(spawn.y, first.y);
        Point arrived = MonsterVacCompat.stepToward(new Point(790, 200), vac, MonsterVacCompat.PULL_STEP_PX);
        assertEquals(vac, arrived);
        assertEquals(3, MonsterVacCompat.facingStance(800, 0));
        assertEquals(2, MonsterVacCompat.facingStance(0, 800));
    }
}
