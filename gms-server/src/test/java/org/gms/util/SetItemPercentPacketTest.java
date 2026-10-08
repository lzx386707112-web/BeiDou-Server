package org.gms.util;

import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.gms.server.SetItemManager;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.Charset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SetItemPercentPacketTest {
    @BeforeAll
    static void context() {
        ApplicationContext context = mock(ApplicationContext.class);
        ServiceProperty property = new ServiceProperty();
        property.setLanguage("zh-CN");
        when(context.getBean(ServiceProperty.class)).thenReturn(property);
        new ServerManager().setApplicationContext(context);
    }

    @Test
    void percentageKeysAndEditedSlotsRoundTripInNativePacketLayout() {
        Map<String, Integer> expected = Map.of("PDD", 30, "MDD", 40, "ACC", 15,
                "EVA", 10, "PDDPct", 20, "HPPct", 20, "SPD", 5, "JMP", 5,
                "Damage", 9, "NormalDamage", 20);
        var definition = new SetItemManager.Definition(20000, -1, "test",
                List.of(List.of(1002000, 1002001)),
                List.of(new SetItemManager.Tier(1, expected)), "test");
        var result = new SetItemManager.Result(SetItemManager.Bonus.NONE,
                List.of(new SetItemManager.Panel(definition, Set.of(1002001), 1, true)));
        ByteBuffer data = ByteBuffer.wrap(PacketCreator.setItemUpdate(result, Integer::toString).getBytes())
                .order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(0x17A, unsignedShort(data));
        assertEquals(1, unsignedShort(data));
        assertEquals(20000, data.getInt());
        assertEquals("test", string(data));
        assertEquals(1, unsignedShort(data));
        assertEquals(1, unsignedShort(data));
        assertEquals(2, unsignedShort(data));
        for (int itemId : List.of(1002001, 1002000)) {
            assertEquals(itemId, data.getInt());
            assertEquals(itemId == 1002001 ? 1 : 0, data.get());
            assertEquals(org.gms.server.SetItemCatalog.itemName(itemId, null), string(data));
            string(data);
            assertEquals(1, data.getInt());
        }
        assertEquals(1, unsignedShort(data));
        assertEquals(1, unsignedShort(data));
        int count = unsignedShort(data);
        assertEquals(expected.size(), count);
        Map<String, Integer> actual = new LinkedHashMap<>();
        for (int index = 0; index < count; index++) actual.put(string(data), data.getInt());
        assertEquals(expected, actual);
        assertEquals(0, unsignedShort(data));
        assertEquals("test", string(data));
        assertEquals(1, data.getInt());
        assertEquals(1, data.getInt());
        assertEquals(0, unsignedShort(data));
        assertFalse(data.hasRemaining());
    }

    @Test
    void legacyPanelIsBoundedWhileServerCountAndTwelfthTierRemainComplete() {
        List<List<Integer>> slots = java.util.stream.IntStream.range(0, 20)
                .mapToObj(slot -> java.util.stream.IntStream.range(0, 50)
                        .mapToObj(item -> 1000000 + slot * 50 + item).toList()).toList();
        var definition = new SetItemManager.Definition(20000, -1, "test", slots,
                List.of(new SetItemManager.Tier(12, Map.of("PAD", 30))), "test");
        var result = new SetItemManager.Result(SetItemManager.Bonus.NONE,
                List.of(new SetItemManager.Panel(definition, Set.of(1000999), 12, true)));
        ByteBuffer data = ByteBuffer.wrap(PacketCreator.setItemUpdate(result, Integer::toString).getBytes())
                .order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(0x17A, unsignedShort(data));
        int views = unsignedShort(data);
        assertEquals(15, views);
        Set<Integer> visible = new java.util.HashSet<>();
        for (int view = 0; view < views; view++) {
            assertEquals(20000, data.getInt());
            string(data);
            assertEquals(20, unsignedShort(data));
            int slotCount = unsignedShort(data);
            assertTrue(slotCount <= 8);
            for (int slot = 0; slot < slotCount; slot++) {
                assertEquals(10, unsignedShort(data));
                for (int item = 0; item < 10; item++) {
                    int id = data.getInt();
                    assertTrue(visible.add(id));
                    int equipped = data.get();
                    assertEquals(id == 1000999 ? 1 : 0, equipped);
                    if (view == 0 && slot == 0 && item == 0) {
                        assertEquals(1000999, id);
                    }
                    string(data);
                    string(data);
                    data.getInt();
                }
            }
            assertEquals(1, unsignedShort(data));
            assertEquals(12, unsignedShort(data));
            assertEquals(1, unsignedShort(data));
            assertEquals("PAD", string(data));
            assertEquals(30, data.getInt());
            assertEquals(0, unsignedShort(data));
            string(data);
            assertEquals(12, data.getInt());
            assertEquals(12, data.getInt());
        }
        assertEquals(1000, visible.size());
        assertEquals(0, unsignedShort(data));
        assertFalse(data.hasRemaining());
        assertEquals(20, definition.slots().size());
        assertEquals(50, definition.slots().getLast().size());
    }

    private static int unsignedShort(ByteBuffer data) {
        return Short.toUnsignedInt(data.getShort());
    }

    private static String string(ByteBuffer data) {
        byte[] bytes = new byte[unsignedShort(data)];
        data.get(bytes);
        return new String(bytes, Charset.forName("GBK"));
    }
}
