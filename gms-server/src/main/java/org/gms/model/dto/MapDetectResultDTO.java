package org.gms.model.dto;

import lombok.Data;

import java.util.List;

/**
 * 地图功能检测总结果
 */
@Data
public class MapDetectResultDTO {
    /** 地图 ID */
    private String mapId;
    /** 地图文件是否存在 */
    private boolean mapExists;
    /** 节点总数 */
    private int total;
    private int ok;
    private int warn;
    private int error;
    private int info;
    /** 各分类检测结果 */
    private List<MapDetectCategoryDTO> categories;
    /** 聚合后的地图基础信息（名字 / 地区 / 怪物 / NPC） */
    private MapInfoDTO mapInfo;
    /** 备注（如地图不存在 / 解析失败原因） */
    private String note;
    /** 崩溃风险总数（crashRisk=CRASH 的节点数） */
    private int crashRiskCount;
}
