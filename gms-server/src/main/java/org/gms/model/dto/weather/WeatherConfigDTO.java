package org.gms.model.dto.weather;

public record WeatherConfigDTO(boolean enabled, long dayLengthMs,
                               long changeIntervalMs, long overrideHoldMs,
                               int rainbowDurationSec) {
}
