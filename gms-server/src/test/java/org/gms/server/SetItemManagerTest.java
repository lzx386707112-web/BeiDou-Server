package org.gms.server;

import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SetItemManagerTest {
    @Test
    void finalDamageCurveIsMonotonicAndCappedAtFiftyPercent() {
        int previous = 0;
        for (int stage = 0; stage <= 16; stage++) {
            int current = SetItemManager.finalDamageForStage(stage);
            assertTrue(current > previous, "stage " + stage + " must improve final damage");
            assertTrue(current <= 50, "final damage must not exceed 50%");
            previous = current;
        }
        assertEquals(50, SetItemManager.finalDamageForStage(16));
        assertEquals(50, SetItemManager.finalDamageForStage(Integer.MAX_VALUE));
    }

    @Test
    void catalogIncludesAllJobsWithoutApplyingForeignSetBonuses() {
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        int[] warriorDestiny = {1432242, 1005980, 1042433, 1062285, 1082760, 1073629, 1103433, 1152212};
        for (int index = 0; index < warriorDestiny.length; index++) {
            equipped.addItemFromDB(new Item(warriorDestiny[index], (short) (-index - 1), (short) 1));
        }
        when(character.getJob()).thenReturn(Job.BISHOP);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        SetItemManager.Result result = SetItemManager.compute(character);
        SetItemManager.Panel warriorPanel = result.panels().stream()
                .filter(panel -> panel.definition().slots().stream().anyMatch(slot -> slot.contains(1432242)))
                .findFirst()
                .orElseThrow();

        assertEquals(91, result.panels().size());
        assertFalse(warriorPanel.jobEligible());
        assertEquals(8, warriorPanel.equippedCount());
        assertEquals(-1, warriorPanel.activeTier());
        assertEquals(0, result.bonus().get("FinalDamage"));
    }

    @Test
    void currentJobSetStillActivatesNormally() {
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        int[] bishopDestiny = {1382289, 1005981, 1042434, 1062286, 1082761, 1073630, 1103434, 1152213};
        for (int index = 0; index < bishopDestiny.length; index++) {
            equipped.addItemFromDB(new Item(bishopDestiny[index], (short) (-index - 1), (short) 1));
        }
        when(character.getJob()).thenReturn(Job.BISHOP);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        SetItemManager.Result result = SetItemManager.compute(character);
        SetItemManager.Panel bishopPanel = result.panels().stream()
                .filter(panel -> panel.definition().slots().stream().anyMatch(slot -> slot.contains(1382289)))
                .findFirst()
                .orElseThrow();

        assertTrue(bishopPanel.jobEligible());
        assertEquals(8, bishopPanel.equippedCount());
        assertEquals(2, bishopPanel.activeTier());
        assertEquals(50, result.bonus().get("FinalDamage"));
    }

    @Test
    void genesisWeaponActivatesItsEternalJobSet() {
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        int[] bishopEternal = {1382274, 1005981, 1042434, 1062286, 1082761, 1073630, 1103434, 1152213};
        for (int index = 0; index < bishopEternal.length; index++) {
            equipped.addItemFromDB(new Item(bishopEternal[index], (short) (-index - 1), (short) 1));
        }
        when(character.getJob()).thenReturn(Job.BISHOP);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        SetItemManager.Result result = SetItemManager.compute(character);
        SetItemManager.Panel bishopPanel = result.panels().stream()
                .filter(panel -> panel.definition().slots().stream().anyMatch(slot -> slot.contains(1382274)))
                .findFirst()
                .orElseThrow();

        assertTrue(bishopPanel.jobEligible());
        assertEquals(8, bishopPanel.equippedCount());
        assertEquals(2, bishopPanel.activeTier());
        assertEquals(50, result.bonus().get("FinalDamage"));
    }

    @Test
    void runtimeOverrideChangesOnlyTheSupportedTierStats() {
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        equipped.addItemFromDB(new Item(1382274, (short) -1, (short) 1));
        equipped.addItemFromDB(new Item(1005981, (short) -2, (short) 1));
        when(character.getJob()).thenReturn(Job.BISHOP);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        SetItemManager.Definition bishop = SetItemManager.defaultDefinitions().stream()
                .filter(definition -> definition.slots().stream().anyMatch(slot -> slot.contains(1382274)))
                .findFirst()
                .orElseThrow();
        String key = SetItemBonusOverrides.key(bishop.id(), 2);
        try {
            SetItemBonusOverrides.replace(Map.of(key, Map.of("HP", 4321, "Unsupported", 999)));
            SetItemManager.Result result = SetItemManager.compute(character);

            assertEquals(4321, result.bonus().get("HP"));
            assertEquals(0, result.bonus().get("Unsupported"));
        } finally {
            SetItemBonusOverrides.replace(Map.of());
        }
    }

    @Test
    void runtimeOverrideCanAddAndRemoveSupportedTierStats() {
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        equipped.addItemFromDB(new Item(1382274, (short) -1, (short) 1));
        equipped.addItemFromDB(new Item(1005981, (short) -2, (short) 1));
        when(character.getJob()).thenReturn(Job.BISHOP);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        SetItemManager.Definition bishop = SetItemManager.defaultDefinitions().stream()
                .filter(definition -> definition.slots().stream()
                        .anyMatch(slot -> slot.contains(1382274)))
                .findFirst()
                .orElseThrow();
        String key = SetItemBonusOverrides.key(bishop.id(), 2);
        try {
            SetItemBonusOverrides.replace(Map.of(key, Map.of(
                    "HP", SetItemBonusOverrides.REMOVED_VALUE,
                    "STR", 99)));
            SetItemManager.Result result = SetItemManager.compute(character);

            assertEquals(0, result.bonus().get("HP"));
            assertEquals(99, result.bonus().get("STR"));
        } finally {
            SetItemBonusOverrides.replace(Map.of());
        }
    }

    @Test
    void dynamicCatalogAddsCustomSetsAndCanDisableBuiltInSets() {
        SetItemManager.Definition builtIn = SetItemManager.builtInDefinitions().getFirst();
        SetItemManager.Definition custom = new SetItemManager.Definition(
                20000, -1, "动态测试套装", List.of(List.of(1122447)),
                List.of(new SetItemManager.Tier(1, Map.of("BossDamage", 7))),
                "test");
        try {
            SetItemBonusOverrides.replaceAll(Map.of(), List.of(custom), Set.of(builtIn.id()));

            assertFalse(SetItemManager.definitions().stream()
                    .anyMatch(definition -> definition.id() == builtIn.id()));
            assertTrue(SetItemManager.definitions().stream()
                    .anyMatch(definition -> definition.id() == custom.id()));
            assertTrue(SetItemManager.catalogDefinitions().stream()
                    .anyMatch(definition -> definition.id() == builtIn.id()));
        } finally {
            SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of());
        }
    }

    @Test
    void endlessRadianceSetAppliesToEveryJobWithTmsCompatibleStats() {
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        int[] radiance = {1113341, 1122447, 1143471, 1113360, 1012911};
        for (int index = 0; index < radiance.length; index++) {
            equipped.addItemFromDB(new Item(radiance[index], (short) (-index - 1), (short) 1));
        }
        when(character.getJob()).thenReturn(Job.BISHOP);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        SetItemManager.Result result = SetItemManager.compute(character);
        SetItemManager.Panel panel = result.panels().stream()
                .filter(candidate -> candidate.definition().name().equals("无尽辉耀"))
                .findFirst()
                .orElseThrow();

        assertTrue(panel.jobEligible());
        assertEquals(5, panel.equippedCount());
        assertEquals(3, panel.activeTier());
        assertEquals(80, result.bonus().get("STR"));
        assertEquals(80, result.bonus().get("PAD"));
        assertEquals(80, result.bonus().get("MAD"));
        assertEquals(2000, result.bonus().get("HP"));
        assertEquals(30, result.bonus().get("BossDamage"));
    }
}
