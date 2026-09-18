package org.gms.model.dto.weather;

public record WeatherStateDTO(boolean enabled, int minuteOfDay, float nightLevel,
                              String phase, boolean weatherOverridden, String overrideProfile,
                              boolean timeFrozen, long overrideRemainingSec,
                              long nextRollInSec, int onlinePlayers, int msPerGameMinute) {
}
