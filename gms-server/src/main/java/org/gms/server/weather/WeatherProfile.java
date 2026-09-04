package org.gms.server.weather;

import java.util.Locale;

public enum WeatherProfile {
    CLEAR(0), RAIN(1), SNOW(2), OVERCAST(3), STORM(4), BLIZZARD(5),
    LEAVES(6), BLOSSOM(7), SANDSTORM(8);

    private final byte id;

    WeatherProfile(int id) {
        this.id = (byte) id;
    }

    public byte id() {
        return id;
    }

    public String profileName() {
        return name().toLowerCase(Locale.ROOT);
    }

    public static WeatherProfile parse(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return valueOf(value.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }
}
