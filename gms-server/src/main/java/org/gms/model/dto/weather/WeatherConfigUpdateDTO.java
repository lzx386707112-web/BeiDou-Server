package org.gms.model.dto.weather;

import lombok.Data;

@Data
public class WeatherConfigUpdateDTO {
    private Boolean enabled;
    private Long dayLengthMs;
    private Long changeIntervalMs;
    private Long overrideHoldMs;
    private Integer rainbowDurationSec;
}
