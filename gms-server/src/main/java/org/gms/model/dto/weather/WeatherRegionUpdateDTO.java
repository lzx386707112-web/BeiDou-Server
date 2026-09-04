package org.gms.model.dto.weather;

import lombok.Data;

import java.util.List;

@Data
public class WeatherRegionUpdateDTO {
    private String forcedProfile;
    private List<Double> weights;
    private Integer nightTint;
    private Integer paletteId;
}
