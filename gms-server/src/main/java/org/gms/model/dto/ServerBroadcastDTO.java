package org.gms.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "全服广播请求参数")
public class ServerBroadcastDTO {

    @Schema(name = "message", example = "自由市场出现了异常能量！",
            requiredMode = Schema.RequiredMode.REQUIRED,
            description = "广播内容")
    private String message;
}
