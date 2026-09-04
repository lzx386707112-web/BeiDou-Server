package org.gms.model.dto.weather;

import lombok.Data;

@Data
public class WeatherOverrideDTO {
    private String profile;
    private Integer minuteOfDay;
    private Integer durationMinutes;
}
