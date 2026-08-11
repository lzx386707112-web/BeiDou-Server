package org.gms.server;

import org.gms.net.packet.Packet;
import org.gms.util.PacketCreator;
import org.junit.jupiter.api.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DamageSkinPacketTest {
    @Test
    void selectionPacketMatchesClientDecoderContract() {
        Packet packet = PacketCreator.damageSkinUpdate(1630);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(6, data.remaining());
        assertEquals(0x17B, Short.toUnsignedInt(data.getShort()));
        assertEquals(1630, data.getInt());
        assertEquals(0, data.remaining());
    }

    @Test
    void generatedCatalogIsSortedAndContainsDefaultSkin() {
        int[] ids = DamageSkinCatalog.ids();
        assertTrue(ids.length > 800);
        assertEquals(0, ids[0]);
        for (int index = 1; index < ids.length; index++) {
            assertTrue(ids[index - 1] < ids[index]);
        }
        assertTrue(DamageSkinCatalog.contains(0));
        assertTrue(DamageSkinCatalog.contains(1630));
    }
}
