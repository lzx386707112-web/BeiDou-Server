package org.gms.dao.entity;

import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("weather_config")
public class WeatherConfigDO {
    @Id(keyType = KeyType.None)
    private Integer id;
    private Boolean enabled;
    private Long dayLengthMs;
    private Long changeIntervalMs;
    private Long overrideHoldMs;
    private Integer rainbowDurationSec;
    private Date updateTime;
}
