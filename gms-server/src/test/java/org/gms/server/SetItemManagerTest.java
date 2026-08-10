package org.gms.server;

import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.junit.jupiter.api.Test;

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
        int[] warriorDestiny = {1432242, 1005980, 1042433, 1062285, 1082760, 1073629, 1103433};
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

        assertEquals(90, result.panels().size());
        assertFalse(warriorPanel.jobEligible());
        assertEquals(7, warriorPanel.equippedCount());
        assertEquals(-1, warriorPanel.activeTier());
        assertEquals(0, result.bonus().get("FinalDamage"));
    }

    @Test
    void currentJobSetStillActivatesNormally() {
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        int[] bishopDestiny = {1382289, 1005981, 1042434, 1062286, 1082761, 1073630, 1103434};
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
        assertEquals(7, bishopPanel.equippedCount());
        assertEquals(2, bishopPanel.activeTier());
        assertEquals(50, result.bonus().get("FinalDamage"));
    }
}
