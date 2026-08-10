package org.gms.util;

import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.net.packet.Packet;
import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.gms.server.SetItemManager;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Locale;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SetItemPacketTest {
    @BeforeAll
    static void configureApplicationContext() {
        ApplicationContext context = mock(ApplicationContext.class);
        ServiceProperty serviceProperty = new ServiceProperty();
        serviceProperty.setLanguage("zh-CN");
        MessageSource messageSource = mock(MessageSource.class);
        when(messageSource.getMessage(anyString(), any(Object[].class), any(Locale.class)))
                .thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(serviceProperty);
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messageSource);
        new ServerManager().setApplicationContext(context);
    }

    @Test
    void destinyStaffPacketMatchesClientDecoderContract() {
        Job bishop = Job.BISHOP;
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        equipped.addItemFromDB(new Item(1382289, (short) -11, (short) 1));
        when(character.getJob()).thenReturn(bishop);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        Packet packet = PacketCreator.setItemUpdate(SetItemManager.compute(character), Integer::toString);
        assertTrue(packet.getBytes().length <= 0xFFFF);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(0x17A, read2(data));
        int setCount = read2(data);
        assertEquals(90, setCount);

        for (int set = 0; set < setCount; set++) {
            int setId = data.getInt();
            if (set == 0) {
                assertEquals(10001, setId);
            }
            readString(data);
            read2(data);
            int slotCount = read2(data);
            for (int slot = 0; slot < slotCount; slot++) {
                int altCount = read2(data);
                for (int alt = 0; alt < altCount; alt++) {
                    data.getInt();
                    data.get();
                    readString(data);
                    readString(data);
                    data.getInt();
                }
            }
            int tierCount = read2(data);
            for (int tier = 0; tier < tierCount; tier++) {
                read2(data);
                int statCount = read2(data);
                assertTrue(statCount > 0 && statCount <= SetItemManager.STAT_KEYS.length);
                for (int stat = 0; stat < statCount; stat++) {
                    readString(data);
                    assertNotEquals(0, data.getInt());
                }
            }
            read2(data);
            readString(data);
            data.getInt();
            data.getInt();
        }
        assertEquals(0, read2(data));
        assertEquals(0, data.remaining());
    }

    private static int read2(ByteBuffer data) {
        return Short.toUnsignedInt(data.getShort());
    }

    private static void readString(ByteBuffer data) {
        int length = read2(data);
        data.position(data.position() + length);
    }
}
