package org.gms.server.weather;

import java.util.EnumMap;
import java.util.Map;

public record WeatherConfigSnapshot(boolean enabled, long dayLengthMs,
                                    long changeIntervalMs, long overrideHoldMs,
                                    int rainbowDurationSec,
                                    Map<WeatherRegion, RegionConfig> regions) {
    public WeatherConfigSnapshot {
        regions = Map.copyOf(regions);
    }

    public RegionConfig region(WeatherRegion region) {
        return regions.getOrDefault(region, regions.get(WeatherRegion.DEFAULT));
    }

    public static WeatherConfigSnapshot defaults() {
        Map<WeatherRegion, RegionConfig> regions = new EnumMap<>(WeatherRegion.class);
        for (WeatherRegion region : WeatherRegion.values()) {
            regions.put(region, new RegionConfig(region.forcedProfile(), region.weights(),
                    region.tint(), region.paletteId()));
        }
        return new WeatherConfigSnapshot(true, 14_400_000L, 900_000L,
                3_600_000L, 180, regions);
    }

    public record RegionConfig(WeatherProfile forcedProfile, double[] weights,
                               int nightTint, int paletteId) {
        public RegionConfig {
            weights = weights.clone();
        }

        @Override
        public double[] weights() { return weights.clone(); }
    }
}
