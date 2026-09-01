package org.gms.util;

import org.gms.net.packet.Packet;
import org.junit.jupiter.api.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

import static org.junit.jupiter.api.Assertions.assertEquals;

class BossHpBarPacketTest {
    private static final long BAR_SIZE = Integer.MAX_VALUE;

    @Test
    void ordinaryBossKeepsItsConfiguredColorsAndHp() {
        BossHpBarPacket bar = decode(PacketCreator.showBossHP(8880000, 50, 100, (byte) 3, (byte) 5));

        assertEquals(8880000, bar.mobId());
        assertEquals(50, bar.hp());
        assertEquals(100, bar.maxHp());
        assertEquals(3, bar.color());
        assertEquals(5, bar.backgroundColor());
    }

    @Test
    void currentPipeOverlaysTheNextFullPipe() {
        BossHpBarPacket bar = decode(PacketCreator.showBossHP(
                8880000, BAR_SIZE * 2 + BAR_SIZE / 2, BAR_SIZE * 3, (byte) 1, (byte) 5));

        assertEquals(BAR_SIZE / 2, bar.hp());
        assertEquals(BAR_SIZE, bar.maxHp());
        assertEquals(3, bar.color());
        assertEquals(2, bar.backgroundColor());
    }

    @Test
    void pipeTransitionReplacesTheEmptyPipeWithAFullPipe() {
        BossHpBarPacket bar = decode(PacketCreator.showBossHP(
                8880000, BAR_SIZE * 2, BAR_SIZE * 3, (byte) 1, (byte) 5));

        assertEquals(Integer.MAX_VALUE, bar.hp());
        assertEquals(Integer.MAX_VALUE, bar.maxHp());
        assertEquals(2, bar.color());
        assertEquals(1, bar.backgroundColor());
    }

    @Test
    void finalPipeUsesTheConfiguredEmptyBackground() {
        BossHpBarPacket bar = decode(PacketCreator.showBossHP(
                8880000, BAR_SIZE / 2, BAR_SIZE * 3, (byte) 1, (byte) 5));

        assertEquals(BAR_SIZE / 2, bar.hp());
        assertEquals(BAR_SIZE, bar.maxHp());
        assertEquals(1, bar.color());
        assertEquals(5, bar.backgroundColor());
    }

    @Test
    void eighthPipeCyclesBackToTheFirstColor() {
        BossHpBarPacket bar = decode(PacketCreator.showBossHP(
                8880000, BAR_SIZE * 7 + 100, BAR_SIZE * 7 + 100, (byte) 1, (byte) 5));

        assertEquals(100, bar.hp());
        assertEquals(100, bar.maxHp());
        assertEquals(1, bar.color());
        assertEquals(7, bar.backgroundColor());
    }

    private static BossHpBarPacket decode(Packet packet) {
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(17, data.remaining());
        assertEquals(0x8A, Short.toUnsignedInt(data.getShort()));
        assertEquals(5, Byte.toUnsignedInt(data.get()));
        BossHpBarPacket result = new BossHpBarPacket(
                data.getInt(),
                data.getInt(),
                data.getInt(),
                Byte.toUnsignedInt(data.get()),
                Byte.toUnsignedInt(data.get()));
        assertEquals(0, data.remaining());
        return result;
    }

    private record BossHpBarPacket(int mobId, int hp, int maxHp, int color, int backgroundColor) {
    }
}
