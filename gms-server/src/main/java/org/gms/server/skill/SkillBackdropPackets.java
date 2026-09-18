package org.gms.server.skill;

import org.gms.net.opcodes.SendOpcode;
import org.gms.net.packet.OutPacket;
import org.gms.net.packet.Packet;

import java.nio.charset.StandardCharsets;

/**
 * LP 0x373F — independent skill backdrop plane in BeiDouWeatherCompat.
 * Large FX use {@code Video/name.mcv} (BeiDouVideo + 7x5 marker at backdrop z).
 * Tiny IMG canvases remain {@code Map/Effect.img/...} UOLs. Not stock FIELD_EFFECT z.
 */
public final class SkillBackdropPackets {
    public static final int OPCODE = 0x373F;
    public static final int MAX_PATH = 192;
    public static final int MAX_DURATION_MS = 86_400_000;

    private SkillBackdropPackets() {
    }

    public static String normalizePath(String wzPath) {
        if (wzPath == null) {
            return null;
        }
        String path = wzPath.trim();
        if (path.isEmpty() || path.length() > MAX_PATH || path.contains("..")) {
            return null;
        }
        for (int i = 0; i < path.length(); i++) {
            char c = path.charAt(i);
            boolean ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
                    || c == '_' || c == '.' || c == '/' || c == '-';
            if (!ok) {
                return null;
            }
        }
        boolean mcv = path.endsWith(".mcv");
        if (mcv) {
            if (!path.contains("/")) {
                path = "Video/" + path;
            }
            if (!path.startsWith("Video/") || path.indexOf('/') != path.lastIndexOf('/')) {
                return null;
            }
            String file = path.substring("Video/".length());
            if (file.length() <= 4 || file.contains("/") || file.contains("\\")) {
                return null;
            }
            return path;
        }
        if (!path.contains(".img/") || path.indexOf('/') < 0) {
            return null;
        }
        return path;
    }

    public static Packet show(String wzPath, int durationMs) {
        String path = normalizePath(wzPath);
        if (path == null) {
            return clear();
        }
        int duration = durationMs;
        if (duration < 0) {
            duration = 0;
        } else if (duration > MAX_DURATION_MS) {
            duration = MAX_DURATION_MS;
        }
        byte[] bytes = path.getBytes(StandardCharsets.US_ASCII);
        OutPacket packet = OutPacket.create(SendOpcode.SKILL_BACKDROP);
        packet.writeByte(1);
        packet.writeShort(bytes.length);
        packet.writeBytes(bytes);
        packet.writeInt(duration);
        return packet;
    }

    public static Packet clear() {
        OutPacket packet = OutPacket.create(SendOpcode.SKILL_BACKDROP);
        packet.writeByte(0);
        return packet;
    }
}
