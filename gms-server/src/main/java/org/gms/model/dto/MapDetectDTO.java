package org.gms.model.dto;

import lombok.Data;

import java.util.List;

/**
 * 地图功能检测请求
 */
@Data
public class MapDetectDTO {
    /** 地图 ID，如 271000000 */
    private String mapId;
    /** 第二个地图 ID（对比接口用） */
    private String mapId2;
}
