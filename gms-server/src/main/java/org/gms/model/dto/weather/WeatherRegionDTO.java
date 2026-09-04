package org.gms.model.dto.weather;

import java.util.List;

public record WeatherRegionDTO(String region, String currentProfile,
                               String forcedProfile, List<Double> weights,
                               int nightTint, int paletteId) {
}
