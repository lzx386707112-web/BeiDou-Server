package org.gms.server.weather;

import org.gms.net.packet.Packet;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.EnumMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WeatherRuntimeTest {
    @AfterEach
    void reset() {
        WeatherRuntime.clearOverride();
        WeatherRuntime.replaceConfig(WeatherConfigSnapshot.defaults());
    }

    @Test
    void packetMatchesTwentyEightByteClientContract() {
        Packet packet = WeatherPackets.weatherSync(211000000, true);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);

        assertEquals(28, data.remaining());
        assertEquals(0x373D, Short.toUnsignedInt(data.getShort()));
        assertTrue(Short.toUnsignedInt(data.getShort()) < 1440);
        assertTrue(data.getInt() > 0);
        assertEquals(WeatherProfile.SNOW.id(), data.get());
        assertEquals(WeatherRuntime.FLAG_SNAP, data.get() & WeatherRuntime.FLAG_SNAP);
        data.getInt();
        assertEquals(0x41, Byte.toUnsignedInt(data.get()));
        assertEquals(0x50, Byte.toUnsignedInt(data.get()));
        assertEquals(0x8E, Byte.toUnsignedInt(data.get()));
        data.getShort();
        assertEquals(WeatherRegion.EL_NATH.paletteId(), Byte.toUnsignedInt(data.get()));
        data.getInt();
        data.getInt();
        assertEquals(0, data.remaining());
    }

    @Test
    void disabledConfigSendsFrozenNoonAndClearSky() {
        WeatherConfigSnapshot defaults = WeatherConfigSnapshot.defaults();
        WeatherRuntime.replaceConfig(new WeatherConfigSnapshot(false, defaults.dayLengthMs(),
                defaults.changeIntervalMs(), defaults.overrideHoldMs(),
                defaults.rainbowDurationSec(), defaults.regions()));
        ByteBuffer data = ByteBuffer.wrap(WeatherPackets.weatherSync(211000000, false).getBytes())
                .order(ByteOrder.LITTLE_ENDIAN);
        data.getShort();
        assertEquals(720, Short.toUnsignedInt(data.getShort()));
        data.getInt();
        assertEquals(WeatherProfile.CLEAR.id(), data.get());
        int flags = Byte.toUnsignedInt(data.get());
        assertTrue((flags & WeatherRuntime.FLAG_FROZEN) != 0);
        assertTrue((flags & WeatherRuntime.FLAG_DISABLED) != 0);
    }

    @Test
    void regionalWeightsSelectOnlyEnabledProfile() {
        WeatherConfigSnapshot defaults = WeatherConfigSnapshot.defaults();
        Map<WeatherRegion, WeatherConfigSnapshot.RegionConfig> regions =
                new EnumMap<>(defaults.regions());
        regions.put(WeatherRegion.HENESYS, new WeatherConfigSnapshot.RegionConfig(
                null, new double[]{0, 0, 0, 0, 0, 0, 0, 0, 1}, 0x123456, 19));
        WeatherRuntime.replaceConfig(new WeatherConfigSnapshot(true, defaults.dayLengthMs(),
                defaults.changeIntervalMs(), defaults.overrideHoldMs(),
                defaults.rainbowDurationSec(), regions));

        assertTrue(WeatherRuntime.rollIfDue());
        assertEquals(WeatherProfile.SANDSTORM,
                WeatherRuntime.skyForRegion(WeatherRegion.HENESYS));
    }

    @Test
    void mapPrefixesResolveToStableRegions() {
        assertEquals(WeatherRegion.HENESYS, WeatherRegion.forMap(100000000));
        assertEquals(WeatherRegion.MUSHROOM_SHRINE, WeatherRegion.forMap(800000000));
        assertEquals(WeatherRegion.ZIPANGU, WeatherRegion.forMap(800010000));
        assertEquals(WeatherRegion.DEFAULT, WeatherRegion.forMap(910000000));
    }

    @Test
    void weatherOverrideRestampsVisualTimelineAndRestoresRegionalSky() {
        WeatherConfigSnapshot defaults = WeatherConfigSnapshot.defaults();
        Map<WeatherRegion, WeatherConfigSnapshot.RegionConfig> regions =
                new EnumMap<>(defaults.regions());
        regions.put(WeatherRegion.HENESYS, new WeatherConfigSnapshot.RegionConfig(
                WeatherProfile.RAIN, new double[]{1, 0, 0, 0, 0, 0, 0, 0, 0},
                0x123456, 19));
        WeatherRuntime.replaceConfig(new WeatherConfigSnapshot(true, defaults.dayLengthMs(),
                defaults.changeIntervalMs(), defaults.overrideHoldMs(),
                defaults.rainbowDurationSec(), regions));

        WeatherRuntime.override(WeatherProfile.CLEAR, null, 60_000L);
        assertEquals(WeatherProfile.CLEAR, WeatherRuntime.skyForRegion(WeatherRegion.HENESYS));
        assertTrue(WeatherRuntime.skyElapsedMs(WeatherRegion.HENESYS) < 5_000L);
        assertTrue(WeatherRuntime.rainbowSecsLeft(WeatherRegion.HENESYS) > 0);

        WeatherRuntime.clearOverride();
        assertEquals(WeatherProfile.RAIN, WeatherRuntime.skyForRegion(WeatherRegion.HENESYS));
        assertTrue(WeatherRuntime.skyElapsedMs(WeatherRegion.HENESYS) < 5_000L);
        assertEquals(0, WeatherRuntime.rainbowSecsLeft(WeatherRegion.HENESYS));
    }
}
