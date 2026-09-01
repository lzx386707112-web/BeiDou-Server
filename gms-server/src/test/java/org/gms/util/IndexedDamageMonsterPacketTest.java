package org.gms.util;

import org.gms.net.packet.Packet;
import org.junit.jupiter.api.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class IndexedDamageMonsterPacketTest {
    @Test
    void ordinaryDamageMonsterPacketKeepsNativeDirectionByte() {
        DamageMonsterPacket packet = decode(PacketCreator.damageMonster(1234, 5678));

        assertEquals(1234, packet.objectId());
        assertEquals(0, packet.marker());
        assertEquals(5678, packet.damage());
    }

    @Test
    void indexedPacketsEncodeFirstAndLastNativeHitIndex() {
        assertEquals(0x80, decode(
                PacketCreator.indexedDamageMonsterNumber(1, 100, 0)
        ).marker());
        assertEquals(0x8E, decode(
                PacketCreator.indexedDamageMonsterNumber(1, 200, 14)
        ).marker());
    }

    @Test
    void indexedPacketPreservesCriticalDamageBitPattern() {
        int encodedCriticalDamage = Integer.MIN_VALUE + 321;

        assertEquals(encodedCriticalDamage, decode(
                PacketCreator.indexedDamageMonsterNumber(1, encodedCriticalDamage, 3)
        ).damage());
    }

    @Test
    void indexedPacketRejectsValuesOutsideNativeFourBitHitRange() {
        assertThrows(
                IllegalArgumentException.class,
                () -> PacketCreator.indexedDamageMonsterNumber(1, 1, -1)
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> PacketCreator.indexedDamageMonsterNumber(1, 1, 15)
        );
    }

    private static DamageMonsterPacket decode(Packet packet) {
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(19, data.remaining());
        assertEquals(0xF6, Short.toUnsignedInt(data.getShort()));
        DamageMonsterPacket result = new DamageMonsterPacket(
                data.getInt(),
                Byte.toUnsignedInt(data.get()),
                data.getInt(),
                data.getInt(),
                data.getInt()
        );
        assertEquals(0, data.remaining());
        return result;
    }

    private record DamageMonsterPacket(
            int objectId,
            int marker,
            int damage,
            int currentHp,
            int maxHp
    ) {
    }
}
