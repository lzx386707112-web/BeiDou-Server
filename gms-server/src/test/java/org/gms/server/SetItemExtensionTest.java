package org.gms.server;

import org.gms.client.BuffStat;
import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.Locale;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SetItemExtensionTest {
    @BeforeAll
    static void context() {
        ApplicationContext context = mock(ApplicationContext.class, RETURNS_MOCKS);
        ServiceProperty property = new ServiceProperty();
        property.setLanguage("zh-CN");
        when(context.getBean(ServiceProperty.class)).thenReturn(property);
        MessageSource messages = mock(MessageSource.class);
        when(messages.getMessage(anyString(), any(Object[].class), any(Locale.class))).thenReturn("");
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messages);
        new ServerManager().setApplicationContext(context);
    }

    @AfterEach
    void clear() {
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(), Map.of());
    }

    private SetItemManager.Bonus bonus(Map<String, Integer> first, Map<String, Integer> second) {
        var definition = new SetItemManager.Definition(20000, -1, "test",
                List.of(List.of(1002000), List.of(1040000)),
                List.of(new SetItemManager.Tier(1, first), new SetItemManager.Tier(2, second)), "test");
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(definition), Set.of(), Map.of());
        Character character = mock(Character.class);
        Job beginner = Job.BEGINNER;
        Inventory inventory = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        inventory.addItemFromDB(new Item(1002000, (short) -1, (short) 1));
        inventory.addItemFromDB(new Item(1040000, (short) -5, (short) 1));
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(inventory);
        when(character.getJob()).thenReturn(beginner);
        return SetItemManager.compute(character).bonus();
    }

    @Test
    void percentagesAddAcrossTiersAndDoNotCompoundOnRefresh() {
        var bonus = bonus(Map.of("HP", 100, "HPPct", 10), Map.of("HPPct", 10));
        assertEquals(1320, bonus.apply("HP", 1000));
        assertEquals(1320, bonus.apply("HP", 1000));
        assertEquals(20, bonus.get("HPPct"));
    }

    @Test
    void nativeStatsMergeSkillBuffsAndClampSignedShorts() {
        var bonus = bonus(Map.of("PDD", 30, "PDDPct", 20, "MDD", 40,
                "ACC", 15, "EVA", 10), Map.of("MDDPct", 10));
        assertEquals(88, SetItemNativeStats.mergedValue(bonus, BuffStat.WDEF, 200, 10));
        assertEquals(69, SetItemNativeStats.mergedValue(bonus, BuffStat.MDEF, 200, 5));
        assertEquals(35, SetItemNativeStats.mergedValue(bonus, BuffStat.ACC, 200, 20));
        assertEquals(17, SetItemNativeStats.mergedValue(bonus, BuffStat.AVOID, 200, 7));
        assertEquals(Short.MAX_VALUE, SetItemNativeStats.mergedValue(bonus, BuffStat.WDEF, 1000000, 10));
        assertEquals(9, SetItemNativeStats.mergedValue(SetItemManager.Bonus.NONE, BuffStat.WDEF, 200, 9));
        assertEquals(9, SetItemNativeStats.mergedValue(bonus, BuffStat.SPEED, 200, 9));
    }

    @Test
    void slotOverridesPreserveDefaultsAndSurviveOtherCatalogChanges() {
        var definition = SetItemManager.builtInDefinitions().getFirst();
        List<List<Integer>> slots = List.of(List.of(1002000), List.of(1040000));
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(), Map.of(definition.id(), slots));
        SetItemBonusOverrides.replace(Map.of());
        assertEquals(slots, SetItemManager.catalogDefinitions().getFirst().slots());
        assertEquals(definition.slots(), SetItemManager.defaultDefinitions().getFirst().slots());
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(definition.id()));
        assertEquals(slots, SetItemBonusOverrides.slotOverrides().get(definition.id()));
    }

    @Test
    void allEditableStatsAreIncludedInPacketKeyList() {
        assertTrue(Set.of(SetItemManager.STAT_KEYS).containsAll(SetItemManager.SUPPORTED_STAT_KEYS));
        assertEquals(Integer.MAX_VALUE, bonus(Map.of("PAD", 1000000, "PADPct", 10000),
                Map.of()).apply("PAD", Integer.MAX_VALUE));
    }
}
