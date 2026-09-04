package org.gms.model.dto.weather;

public record WeatherStateDTO(boolean enabled, int minuteOfDay, float nightLevel,
                              boolean weatherOverridden, String overrideProfile,
                              boolean timeFrozen, long overrideRemainingSec,
                              long nextRollInSec, int onlinePlayers) {
}
