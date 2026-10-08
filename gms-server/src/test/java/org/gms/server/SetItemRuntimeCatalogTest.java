package org.gms.server;

import com.alibaba.fastjson2.JSON;
import org.gms.client.BuffStat;
import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SetItemRuntimeCatalogTest {
    @AfterEach
    void reset() {
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(), Map.of());
    }

    private SetItemManager.Definition definition(String name, int job) {
        return SetItemManager.builtInDefinitions().stream()
                .filter(set -> set.name().equals(name) && (set.jobIndex() == job || set.jobIndex() < 0))
                .findFirst().orElseThrow();
    }

    private SetItemManager.Result equipped(Job job, List<Integer> items) {
        Character character = mock(Character.class);
        Inventory inventory = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        for (int i = 0; i < items.size(); i++) {
            inventory.addItemFromDB(new Item(items.get(i), (short) (-i - 1), (short) 1));
        }
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(inventory);
        when(character.getJob()).thenReturn(job);
        return SetItemManager.compute(character);
    }

    @Test
    void everyReviewedSeriesIsRegisteredAndOriginalIdsAreRetained() throws Exception {
        try (var input = getClass().getResourceAsStream("/set-item/catalog.json")) {
            var source = JSON.parseArray(new String(input.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8));
            assertEquals(55, source.size());
            for (var series : source) {
                String name = ((com.alibaba.fastjson2.JSONObject) series).getString("name");
                assertTrue(SetItemManager.builtInDefinitions().stream().anyMatch(set -> set.name().equals(name)), name);
            }
        }
        for (int id = 10000; id <= 10090; id++) assertTrue(SetItemManager.isBuiltIn(id), "original ID " + id);
        assertEquals(SetItemManager.builtInDefinitions().size(), SetItemManager.builtInDefinitions().stream()
                .map(SetItemManager.Definition::id).distinct().count());
    }

    @Test
    void blackGateThreeAndFivePiecesAreCumulativeAndDoNotStackTwice() {
        var blackGate = definition("黑门", -1);
        List<Integer> ids = blackGate.slots().stream().map(List::getFirst).toList();
        var three = equipped(Job.BISHOP, ids.subList(0, 3));
        assertEquals(5, three.bonus().get("PAD"));
        assertEquals(5, three.bonus().get("MAD"));
        assertEquals(10, three.bonus().get("STR"));
        assertEquals(0, three.bonus().get("HPPct"));
        var five = equipped(Job.BISHOP, ids.subList(0, 5));
        assertEquals(15, five.bonus().get("PAD"));
        assertEquals(15, five.bonus().get("MAD"));
        for (String key : List.of("STR", "DEX", "INT", "LUK")) assertEquals(20, five.bonus().get(key));
        assertEquals(50, five.bonus().get("PDD"));
        assertEquals(50, five.bonus().get("MDD"));
        assertEquals(2, five.bonus().get("HPPct"));
        assertEquals(2, five.bonus().get("MPPct"));
        assertEquals(10200, five.bonus().apply("HP", 10000));
        assertEquals(20400, five.bonus().apply("MP", 20000));
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(blackGate.id()), Map.of());
        assertEquals(0, equipped(Job.BISHOP, ids).bonus().get("PAD"));
    }

    @Test
    void treasureTwelfthTierIsReachableAndNeverDowngraded() {
        var treasure = definition("冒险岛寻宝", -1);
        assertEquals(12, treasure.slots().size());
        assertTrue(treasure.slots().stream().anyMatch(slot -> slot.contains(1012524)));
        var result = equipped(Job.HERO, treasure.slots().stream().map(List::getFirst).toList());
        var panel = result.panels().stream().filter(p -> p.definition().id() == treasure.id()).findFirst().orElseThrow();
        assertEquals(12, panel.equippedCount());
        assertEquals(5, panel.activeTier());
        assertEquals(30, result.bonus().get("BossDamage"));
        assertEquals(50, result.bonus().get("PAD"));
        assertEquals(0, result.bonus().get("FinalDamage"));
        assertEquals(9, result.bonus().get("Damage"));
    }

    @Test
    void weaponVersionsCountOnceAndSharedArmorAppliesOnlyOneJobDefinition() {
        var gem = definition("冒险岛宝石", 1);
        var result = equipped(Job.BISHOP, gem.slots().stream().map(List::getFirst).toList());
        assertEquals(6, result.bonus().get("PAD"));
        assertEquals(8, result.bonus().get("STR"));
        assertEquals(5, result.bonus().get("SPD"));
        assertEquals(5, result.bonus().get("JMP"));
        assertEquals(25, SetItemNativeStats.mergedValue(result.bonus(), BuffStat.SPEED, 10, 20));
        assertEquals(15, SetItemNativeStats.mergedValue(result.bonus(), BuffStat.JUMP, 10, 10));
        var fafnir = definition("高贵游侠", 2);
        List<Integer> weapon = fafnir.slots().getLast();
        assertTrue(weapon.size() > 1);
        var bowResult = equipped(Job.BOWMASTER, weapon.subList(0, 2));
        var panel = bowResult.panels().stream().filter(p -> p.definition().id() == fafnir.id()).findFirst().orElseThrow();
        assertEquals(1, panel.equippedCount());
        assertEquals(-1, panel.activeTier());
    }

    @Test
    void normalDamageAccumulatesAndNeverAppliesToBossesOrUnknownTargets() {
        var pensalir = definition("芬撒里尔战斗", 0);
        var full = equipped(Job.HERO, pensalir.slots().stream().map(List::getFirst).toList());
        assertEquals(20, full.bonus().get("NormalDamage"));
        Character character = mock(Character.class);
        when(character.getSetItemBonus("NormalDamage")).thenReturn(full.bonus().get("NormalDamage"));
        var normal = mock(org.gms.server.life.Monster.class);
        var boss = mock(org.gms.server.life.Monster.class);
        when(boss.isBoss()).thenReturn(true);
        assertEquals(120, SetItemManager.applyDamage(character, normal, 100));
        assertEquals(100, SetItemManager.applyDamage(character, boss, 100));
        assertEquals(100, SetItemManager.applyDamage(character, null, 100));
        assertEquals(0, SetItemManager.applyDamage(character, normal, 0));
    }

    @Test
    void ordinaryAndTargetDamageAddBeforeFinalDamageMultiplies() {
        Character character = mock(Character.class);
        when(character.getSetItemBonus("Damage")).thenReturn(9);
        when(character.getSetItemBonus("BossDamage")).thenReturn(30);
        when(character.getSetItemBonus("NormalDamage")).thenReturn(20);
        when(character.getSetItemBonus("FinalDamage")).thenReturn(20);
        var normal = mock(org.gms.server.life.Monster.class);
        var boss = mock(org.gms.server.life.Monster.class);
        when(boss.isBoss()).thenReturn(true);
        assertEquals(167, SetItemManager.applyDamage(character, boss, 100));
        assertEquals(155, SetItemManager.applyDamage(character, normal, 100));
        assertEquals(131, SetItemManager.applyDamage(character, null, 100));
        assertEquals(Integer.MAX_VALUE, SetItemManager.applyDamage(character, boss, Integer.MAX_VALUE - 1));
        assertEquals(Integer.MAX_VALUE, SetItemManager.applyDamage(character, boss, Integer.MAX_VALUE));
        assertEquals(0, SetItemManager.applyDamage(character, boss, 0));
        assertEquals(-1, SetItemManager.applyDamage(character, boss, -1));
        assertEquals(100, SetItemManager.applyDamage(null, boss, 100));
    }
}
