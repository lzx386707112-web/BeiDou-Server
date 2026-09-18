package org.gms.server.skill;

import org.gms.net.packet.Packet;
import org.junit.jupiter.api.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class SkillBackdropPacketsTest {
    @Test
    void showPacketIsAsciiPathAfterOpcode() {
        Packet packet = SkillBackdropPackets.show("Effect/SkillBack.img/plane/0", 1500);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(0x373F, Short.toUnsignedInt(data.getShort()));
        assertEquals(1, Byte.toUnsignedInt(data.get()));
        int len = Short.toUnsignedInt(data.getShort());
        byte[] path = new byte[len];
        data.get(path);
        assertEquals("Effect/SkillBack.img/plane/0", new String(path, StandardCharsets.US_ASCII));
        assertEquals(1500, data.getInt());
        assertEquals(0, data.remaining());
    }

    @Test
    void clearPacketIsModeZero() {
        Packet packet = SkillBackdropPackets.clear();
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(0x373F, Short.toUnsignedInt(data.getShort()));
        assertEquals(0, Byte.toUnsignedInt(data.get()));
        assertEquals(0, data.remaining());
    }

    @Test
    void rejectsTraversalAndNonAscii() {
        assertNull(SkillBackdropPackets.normalizePath("../Etc.img/x"));
        assertNull(SkillBackdropPackets.normalizePath("Effect/Foo.img"));
        assertNull(SkillBackdropPackets.normalizePath("Effect/Foo.img/平面"));
        assertEquals("Map/Back/grassySoil.img/back/0",
                SkillBackdropPackets.normalizePath("Map/Back/grassySoil.img/back/0"));
        assertEquals("Video/spirit-caliber.mcv",
                SkillBackdropPackets.normalizePath("spirit-caliber.mcv"));
        assertEquals("Video/spirit-caliber.mcv",
                SkillBackdropPackets.normalizePath("Video/spirit-caliber.mcv"));
        assertNull(SkillBackdropPackets.normalizePath("Etc/spirit-caliber.mcv"));
    }

    @Test
    void mcvPacketKeepsVideoStem() {
        Packet packet = SkillBackdropPackets.show("Video/spirit-caliber.mcv", 7020);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(0x373F, Short.toUnsignedInt(data.getShort()));
        assertEquals(1, Byte.toUnsignedInt(data.get()));
        int len = Short.toUnsignedInt(data.getShort());
        byte[] path = new byte[len];
        data.get(path);
        assertEquals("Video/spirit-caliber.mcv", new String(path, StandardCharsets.US_ASCII));
        assertEquals(7020, data.getInt());
    }
}
