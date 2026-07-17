package org.gms.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "清除怪物攻城请求参数")
public class MonsterSiegeClearDTO {

    @Schema(name = "mapId", example = "100000000",
            requiredMode = Schema.RequiredMode.REQUIRED,
            description = "需要清除攻城Boss的主城地图ID")
    private Integer mapId;
}
