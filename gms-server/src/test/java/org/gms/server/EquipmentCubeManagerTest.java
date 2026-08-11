package org.gms.server;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EquipmentCubeManagerTest {
    @Test
    void potentialGradeControlsLineCountAndStrength() {
        assertEquals(1, EquipmentCubeManager.lineCountForGrade(1));
        assertEquals(2, EquipmentCubeManager.lineCountForGrade(2));
        assertEquals(3, EquipmentCubeManager.lineCountForGrade(3));
        assertEquals(3, EquipmentCubeManager.lineCountForGrade(4));
        assertEquals(1, EquipmentCubeManager.powerForGrade(1));
        assertEquals(2, EquipmentCubeManager.powerForGrade(2));
        assertEquals(4, EquipmentCubeManager.powerForGrade(3));
        assertEquals(8, EquipmentCubeManager.powerForGrade(4));
    }

    @Test
    void cubeRollAlwaysProducesLinesAndOnlyTheRankCanFail() {
        EquipmentCubeManager.Roll failedUpgrade = EquipmentCubeManager.roll(
                1302000, "", 4007000, 99);
        assertEquals(1, failedUpgrade.grade());
        assertFalse(failedUpgrade.rankedUp());
        assertEquals(1, EquipmentCubeManager.lineCountForGrade(failedUpgrade.grade()));

        EquipmentCubeManager.Roll upgraded = EquipmentCubeManager.roll(
                1302000, "", 4007000, 0);
        assertEquals(2, upgraded.grade());
        assertTrue(upgraded.rankedUp());
        assertEquals(2, EquipmentCubeManager.lineCountForGrade(upgraded.grade()));
    }

    @Test
    void cubeCapsAndUpgradeRatesMatchTheConfiguredPotentialSystem() {
        assertEquals(3, EquipmentCubeManager.maxGrade(4007000));
        assertEquals(4, EquipmentCubeManager.maxGrade(4007007));
        assertEquals(20, EquipmentCubeManager.upgradeRate(4007007, 1));
        assertEquals(8, EquipmentCubeManager.upgradeRate(4007007, 2));
        assertEquals(2, EquipmentCubeManager.upgradeRate(4007007, 3));
        assertEquals(0, EquipmentCubeManager.upgradeRate(4007007, 4));
        assertFalse(EquipmentCubeManager.canKeepOld(4007006));
        assertTrue(EquipmentCubeManager.canKeepOld(4007007));
    }

    @Test
    void rerollReplacesOnlyThePreviousCubeContribution() {
        EquipmentCubeManager.Roll first = EquipmentCubeManager.roll(1302000, "", 4007006, 99);
        int firstBonus = EquipmentCubeManager.bonus(first.data(), "STR");
        int current = 100 + firstBonus + 5;

        EquipmentCubeManager.Roll second = EquipmentCubeManager.roll(
                1302000, first.data(), 4007007, 99);
        int secondBonus = EquipmentCubeManager.bonus(second.data(), "STR");
        int replaced = EquipmentCubeManager.replaceValue(current, firstBonus, secondBonus);

        assertEquals(105 + secondBonus, replaced);
        assertTrue(second.data().contains("\"v\":2"));
    }

    @Test
    void inheritanceAppliesTheStoredBonusExactlyOnce() {
        EquipmentCubeManager.Roll source = EquipmentCubeManager.roll(
                1302000, "", 4007005, 99);
        int sourceBonus = EquipmentCubeManager.bonus(source.data(), "STR");
        int inherited = EquipmentCubeManager.replaceValue(80, 0, sourceBonus);
        int inheritedAgain = EquipmentCubeManager.replaceValue(
                inherited, sourceBonus, sourceBonus);

        assertEquals(inherited, inheritedAgain);
    }

    @Test
    void inheritingEmptyCubeDataRemovesTheOldCubeContribution() {
        assertEquals(80, EquipmentCubeManager.replaceValue(86, 6, 0));
    }

    @Test
    void corruptDataCannotBeOverwrittenOrApplied() {
        assertFalse(EquipmentCubeManager.isValidData("not-json"));
        assertThrows(IllegalArgumentException.class,
                () -> EquipmentCubeManager.roll(1302000, "not-json", 4007007));
        assertTrue(EquipmentCubeManager.isValidData(""));
    }

    @Test
    void legacyVersionOneDataKeepsItsBonusAndInfersItsGrade() {
        String legacy = "{\"v\":1,\"cube\":4007006,\"lines\":["
                + "{\"stat\":\"STR\",\"value\":6},"
                + "{\"stat\":\"DEX\",\"value\":5},"
                + "{\"stat\":\"WATK\",\"value\":3}]}";

        assertTrue(EquipmentCubeManager.isValidData(legacy));
        assertEquals(3, EquipmentCubeManager.grade(legacy));
        assertEquals(6, EquipmentCubeManager.bonus(legacy, "STR"));
    }
}
