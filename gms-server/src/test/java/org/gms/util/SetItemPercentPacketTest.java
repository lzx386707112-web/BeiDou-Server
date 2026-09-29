package org.gms.util;

import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.gms.server.SetItemManager;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
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
                "EVA", 10, "PDDPct", 20, "HPPct", 20);
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
        for (int itemId : List.of(1002000, 1002001)) {
            assertEquals(itemId, data.getInt());
            assertEquals(itemId == 1002001 ? 1 : 0, data.get());
            assertEquals(Integer.toString(itemId), string(data));
            string(data);
            assertEquals(0, data.getInt());
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

    private static int unsignedShort(ByteBuffer data) {
        return Short.toUnsignedInt(data.getShort());
    }

    private static String string(ByteBuffer data) {
        byte[] bytes = new byte[unsignedShort(data)];
        data.get(bytes);
        return new String(bytes, StandardCharsets.UTF_8);
    }
}
