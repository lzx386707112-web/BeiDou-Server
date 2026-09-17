package org.gms.server.life;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** skill2 光球轨迹纯函数；地图与发包需实机验证。 */
class DamienBossCompatTest {
    @Test
    void skill2PlansTwoFanThenStaggeredSinglesFromSky() {
        List<DamienBossCompat.Skill2OrbPlan> plans = DamienBossCompat.planSkill2Orbs(
                new java.awt.Point(100, -300), new java.awt.Point(400, 240), new java.util.Random(7));
        assertEquals(6, plans.size());
        assertEquals(2, plans.stream().filter(plan -> "fan".equals(plan.wave())).count());
        assertEquals(4, plans.stream().filter(plan -> "single".equals(plan.wave())).count());
        List<Integer> fanXs = plans.stream()
                .filter(plan -> "fan".equals(plan.wave()))
                .map(plan -> plan.end().x)
                .toList();
        assertTrue(fanXs.get(0) < fanXs.get(1));
        for (DamienBossCompat.Skill2OrbPlan fan : plans.stream().filter(plan -> "fan".equals(plan.wave())).toList()) {
            assertEquals(0, fan.delayMs());
            assertEquals(-300, fan.start().y);
            assertTrue(fan.end().y >= fan.start().y);
            assertEquals(240, fan.end().y);
        }
        long previous = -1;
        for (DamienBossCompat.Skill2OrbPlan single : plans.stream().filter(plan -> "single".equals(plan.wave())).toList()) {
            assertTrue(single.delayMs() >= previous);
            previous = single.delayMs();
            assertTrue(single.start().y < single.end().y);
            assertEquals(240, single.end().y);
            assertTrue(single.start().y < 0);
        }
        java.awt.Point mid = DamienBossCompat.bezier(
                new java.awt.Point(0, 0), new java.awt.Point(0, 100), new java.awt.Point(0, 200), 0.5);
        assertEquals(0, mid.x);
        assertEquals(100, mid.y);
        assertEquals(8880112, DamienBossCompat.SKILL2_ORB_MOB);
        assertEquals(2, DamienBossCompat.SKILL2_FAN_COUNT);
        assertEquals(4, DamienBossCompat.SKILL2_SINGLE_COUNT);
        assertEquals(8880102, DamienBossCompat.SKILL2_BANNED_MOB);
        assertEquals(2790, DamienBossCompat.SKILL2_AIRBORNE_MS);
        assertEquals("customBossDemian/groundBurst", DamienBossCompat.SKILL2_GROUND_EFFECT);
        assertTrue(DamienBossCompat.isDamien(8880110));
        assertTrue(DamienBossCompat.isDamien(8880111));
        assertTrue(DamienBossCompat.allowClientAttack(8880110, 0));
        assertTrue(DamienBossCompat.allowClientAttack(8880110, 2));
        assertFalse(DamienBossCompat.allowClientAttack(8880110, 1));
        assertTrue(DamienBossCompat.allowClientAttack(8880111, 0));
        assertFalse(DamienBossCompat.allowClientAttack(8880111, 1));
        assertEquals(3240, DamienBossCompat.skillEffectDelayMs(8880110, 2, 3960));
        assertEquals(2610, DamienBossCompat.skillEffectDelayMs(8880110, 3, 3600));
        assertEquals(3060, DamienBossCompat.skillEffectDelayMs(8880111, 2, 3960));
        List<DamienBossCompat.Attack3BallPlan> balls = DamienBossCompat.planAttack3Balls(
                new java.awt.Point(800, -40), new java.awt.Point(800, 17));
        assertEquals(16, balls.size());
        int hover = DamienBossCompat.HOVER_OFFSET_Y;
        long upper = balls.stream().filter(plan -> plan.start().y == -40 - hover - 40).count();
        long lower = balls.stream().filter(plan -> plan.start().y == -40 - hover + 40).count();
        assertEquals(8, upper);
        assertEquals(8, lower);
        assertEquals(8, balls.stream().map(plan -> plan.start().x).distinct().count());
        assertTrue(balls.get(0).delayMs() == 0);
        assertTrue(balls.get(balls.size() - 1).delayMs() > balls.get(0).delayMs());
        assertEquals(8880113, DamienBossCompat.SHADOW_ORB_MOB);
        assertEquals(8880114, DamienBossCompat.FLYING_SWORD_MOB);
        assertEquals(2, DamienBossCompat.PHASE2_ORB_COUNT);
        assertEquals(2, DamienBossCompat.SWORD_COUNT);
        assertFalse(DamienBossCompat.SPAWN_FLYING_SWORDS);
        assertEquals(2000, DamienBossCompat.SWORD_SPAWN_DELAY_MS);
        assertEquals(8880102, DamienBossCompat.SKILL2_BANNED_MOB);
        java.awt.Point c = new java.awt.Point(800, 100);
        java.awt.Point eight0 = DamienBossCompat.swordPathPoint(0, 0, c, 200, 80);
        java.awt.Point eightRight = DamienBossCompat.swordPathPoint(0, Math.PI / 2, c, 200, 80);
        java.awt.Point eightMid = DamienBossCompat.swordPathPoint(0, Math.PI / 4, c, 200, 80);
        java.awt.Point reverseLeft = DamienBossCompat.swordPathPoint(1, Math.PI / 2, c, 200, 80);
        assertEquals(800, eight0.x);
        assertEquals(100, eight0.y);
        assertEquals(1000, eightRight.x);
        assertEquals(100, eightRight.y);
        assertTrue(eightMid.x > 800 && eightMid.y > 100);
        assertEquals(600, reverseLeft.x);
        assertEquals(100, reverseLeft.y);
        java.awt.Point ellipse = DamienBossCompat.swordPathPoint(2, 0, c, 200, 80);
        assertEquals(1000, ellipse.x);
        assertEquals(100, ellipse.y);
        assertEquals(4, DamienBossCompat.swordFacingStance(40, 0, false));
        assertEquals(5, DamienBossCompat.swordFacingStance(-40, 0, false));
        assertEquals(6, DamienBossCompat.swordFacingStance(40, -40, false));
        assertEquals(7, DamienBossCompat.swordFacingStance(-40, -40, false));
        assertEquals(240, DamienBossCompat.SWORD_AMP_Y);
    }
}
