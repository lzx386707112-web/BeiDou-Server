package org.gms.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.List;

@Data
@Schema(description = "怪物攻城请求参数")
public class MonsterSiegeDTO {

    @Schema(name = "mapId", example = "100000000",
            requiredMode = Schema.RequiredMode.AUTO,
            description = "召唤怪物的主城地图ID，默认自由市场入口")
    private Integer mapId;

    @Schema(name = "monsterIds", example = "[9600318, 9400590]",
            requiredMode = Schema.RequiredMode.REQUIRED,
            description = "召唤的怪物ID列表")
    private List<Integer> monsterIds;

    @Schema(name = "count", example = "1",
            requiredMode = Schema.RequiredMode.AUTO,
            description = "每个怪物ID在每个频道召唤的数量")
    private Integer count;

    @Schema(name = "message", example = "怪物攻城开始！请前往指定主城迎战！",
            requiredMode = Schema.RequiredMode.AUTO,
            description = "召唤后发送的全服中央广播")
    private String message;

    @Schema(name = "broadcast", example = "true",
            requiredMode = Schema.RequiredMode.AUTO,
            description = "是否发送全服中央广播")
    private Boolean broadcast = true;

    @Schema(name = "rewards", description = "伤害排行前三名的奖励配置")
    private List<MonsterSiegeRewardDTO> rewards;
}
