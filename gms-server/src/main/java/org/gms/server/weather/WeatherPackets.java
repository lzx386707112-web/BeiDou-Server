package org.gms.server.weather;

import org.gms.client.Character;
import org.gms.net.opcodes.SendOpcode;
import org.gms.net.packet.OutPacket;
import org.gms.net.packet.Packet;
import org.gms.net.server.world.World;

import java.util.EnumMap;
import java.util.Map;

public final class WeatherPackets {
    private WeatherPackets() {
    }

    public static Packet weatherSync(int mapId, boolean snap) {
        WeatherRegion region = WeatherRegion.forMap(mapId);
        WeatherConfigSnapshot snapshot = WeatherRuntime.config();
        WeatherConfigSnapshot.RegionConfig regionConfig = snapshot.region(region);
        int flags = snap ? WeatherRuntime.FLAG_SNAP : 0;
        if (WeatherRuntime.isTimeFrozen() || !snapshot.enabled()) flags |= WeatherRuntime.FLAG_FROZEN;
        if (!snapshot.enabled()) flags |= WeatherRuntime.FLAG_DISABLED;
        long elapsedMs = WeatherRuntime.skyElapsedMs(region);

        OutPacket packet = OutPacket.create(SendOpcode.WEATHER_SYNC);
        packet.writeShort(snapshot.enabled() ? WeatherRuntime.minuteOfDay() : 720);
        packet.writeInt(WeatherRuntime.msPerGameMinute());
        packet.writeByte(WeatherRuntime.skyForRegion(region).id());
        packet.writeByte(flags);
        packet.writeInt((int) Math.min(Integer.MAX_VALUE, elapsedMs / 1000L));
        packet.writeByte((regionConfig.nightTint() >> 16) & 0xFF);
        packet.writeByte((regionConfig.nightTint() >> 8) & 0xFF);
        packet.writeByte(regionConfig.nightTint() & 0xFF);
        packet.writeShort(WeatherRuntime.rainbowSecsLeft(region));
        packet.writeByte(regionConfig.paletteId());
        packet.writeInt((int) Math.min(Integer.MAX_VALUE, elapsedMs));
        packet.writeInt(WeatherRuntime.skyToken(region));
        return packet;
    }

    public static void sendTo(Character character) {
        if (character != null && character.getClient() != null) {
            character.sendPacket(weatherSync(character.getMapId(), true));
        }
    }

    public static int broadcastAll(boolean snap) {
        int sent = 0;
        for (World world : org.gms.net.server.Server.getInstance().getWorlds()) {
            sent += broadcast(world, snap);
        }
        return sent;
    }

    public static int broadcast(World world, boolean snap) {
        if (world == null || world.getPlayerStorage() == null) return 0;
        Map<WeatherRegion, Packet> packets = new EnumMap<>(WeatherRegion.class);
        int sent = 0;
        for (Character character : world.getPlayerStorage().getAllCharacters()) {
            try {
                if (character == null || !character.isLoggedinWorld()) continue;
                WeatherRegion region = WeatherRegion.forMap(character.getMapId());
                Packet packet = packets.computeIfAbsent(region,
                        ignored -> weatherSync(character.getMapId(), snap));
                character.sendPacket(packet);
                sent++;
            } catch (RuntimeException ignored) {
                // Keep one disconnected client from aborting the world broadcast.
            }
        }
        return sent;
    }
}
