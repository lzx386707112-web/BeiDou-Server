package org.gms.model.dto;

import lombok.Data;

/**
 * 地图检测：带名称的引用项（如 怪物 / NPC，含 id 与中文名）
 */
@Data
public class MapDetectRefDTO {
    /** 资源 ID（怪物 / NPC 的 7 位编号） */
    private String id;
    /** 中文名称（来自 String.wz 名称表，缺失时为 null） */
    private String name;
}
