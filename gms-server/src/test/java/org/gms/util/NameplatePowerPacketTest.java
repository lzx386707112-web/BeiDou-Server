package org.gms.util;

import org.gms.net.packet.Packet;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

import javax.xml.parsers.DocumentBuilderFactory;
import java.nio.file.Path;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class NameplatePowerPacketTest {
    @Test
    void nameTagRingContractComesFromCharacterData() throws Exception {
        assertTrue(hasInfoProperty(1115173, "nameTag"));
        assertTrue(hasInfoProperty(1115108, "nameTag"));
        assertFalse(hasInfoProperty(1112238, "nameTag"));
        assertTrue(hasInfoProperty(1112238, "chatBalloon"));
        assertFalse(hasInfoProperty(1112400, "nameTag"));
    }

    @Test
    void enabledPacketMatchesClientDecoderContract() {
        Packet packet = PacketCreator.nameplatePowerUpdate(1234, true, 567890);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);

        assertEquals(11, data.remaining());
        assertEquals(0x17C, Short.toUnsignedInt(data.getShort()));
        assertEquals(1234, data.getInt());
        assertEquals(1, Byte.toUnsignedInt(data.get()));
        assertEquals(567890, data.getInt());
        assertEquals(0, data.remaining());
    }

    @Test
    void disabledPacketClearsPower() {
        Packet packet = PacketCreator.nameplatePowerUpdate(1234, false, 567890);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);

        data.position(7);
        assertEquals(0, data.getInt());
    }

    @Test
    void powerUsesPrimaryStatsAndTheStrongerAttackType() {
        assertEquals(11100, PacketCreator.calculateNameplatePower(100, 80, 20, 10, 30, 50, 5000, 2000));
    }

    private static boolean hasInfoProperty(int itemId, String propertyName) throws Exception {
        Path path = Path.of("wz/Character.wz/Ring", String.format("0%d.img.xml", itemId));
        Element root = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(path.toFile()).getDocumentElement();
        Element info = directChild(root, "imgdir", "info");
        return info != null && directChild(info, null, propertyName) != null;
    }

    private static Element directChild(Element parent, String tagName, String name) {
        for (Node child = parent.getFirstChild(); child != null; child = child.getNextSibling()) {
            if (child instanceof Element element
                    && (tagName == null || element.getTagName().equals(tagName))
                    && element.getAttribute("name").equals(name)) {
                return element;
            }
        }
        return null;
    }
}
