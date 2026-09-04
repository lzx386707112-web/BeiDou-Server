package org.gms.dao.entity;

import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.util.Date;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("weather_region_config")
public class WeatherRegionConfigDO {
    @Id(keyType = KeyType.None)
    private String region;
    private String forcedProfile;
    private BigDecimal clearWeight;
    private BigDecimal rainWeight;
    private BigDecimal snowWeight;
    private BigDecimal overcastWeight;
    private BigDecimal stormWeight;
    private BigDecimal blizzardWeight;
    private BigDecimal leavesWeight;
    private BigDecimal blossomWeight;
    private BigDecimal sandstormWeight;
    private Integer nightTint;
    private Integer paletteId;
    private Date updateTime;
}
