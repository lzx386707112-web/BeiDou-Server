package org.gms.server.life;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashSet;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RootAbyssBossCompatTest {
    @Test
    void vellumVisualSlotsDoNotApplySummonsOrBuffs() {
        for (int level = 251; level <= 255; level++) {
            assertTrue(RootAbyssBossCompat.isVellumVisualSkill(
                    8930000, new MobSkillId(MobSkillType.SUMMON, level)));
            assertFalse(RootAbyssBossCompat.isVellumVisualSkill(
                    8930001, new MobSkillId(MobSkillType.SUMMON, level)));
        }
        assertTrue(RootAbyssBossCompat.isVellumVisualSkill(
                8930000, new MobSkillId(MobSkillType.ATTACK_UP, 30)));
        assertFalse(RootAbyssBossCompat.isVellumVisualSkill(
                8930000, new MobSkillId(MobSkillType.SUMMON, 239)));
    }

    @Test
    void originalVellumSkillRetainsItsClientProjection() {
        MobSkillId projected = RootAbyssBossCompat.projectSkillForClient(
                8930000, new MobSkillId(MobSkillType.SUMMON_170, 13));
        assertEquals(MobSkillType.SUMMON, projected.type());
        assertEquals(239, projected.level());
    }

    @Test
    void vellumUsesActionSlotWhenPacketContainsAnotherValidSkillId() {
        MonsterStats stats = new MonsterStats();
        MobSkillId original = new MobSkillId(MobSkillType.SUMMON_170, 13);
        MobSkillId video = new MobSkillId(MobSkillType.SUMMON, 251);
        MobSkillId alias = new MobSkillId(MobSkillType.ATTACK_UP, 30);
        stats.setSkills(new LinkedHashSet<>(List.of(original, video, alias)));
        Monster vellum = new Monster(8930000, stats);

        assertEquals(video, vellum.resolveCastSkill(170, 13, 1));
        assertEquals(alias, vellum.resolveCastSkill(200, 251, 2));
        assertEquals(original, vellum.resolveCastSkill(0, 0, 0));
    }
}
