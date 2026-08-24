package org.gms.model.dto;

import lombok.Data;

import java.util.List;

/**
 * 地图检测：某一类资源的检测结果（聚合统计 + 节点列表）
 */
@Data
public class MapDetectCategoryDTO {
    /** 分类 key */
    private String category;
    /** 分类展示名（如 "NPC" / "传送点"） */
    private String label;
    /** 该分类节点总数 */
    private int total;
    private int ok;
    private int warn;
    private int error;
    private int info;
    /** true 表示 nodes 仅包含代表性/问题节点（如瓦片、foothold），总数见 total */
    private boolean summaryOnly;
    /** 节点列表（小分类为完整结构；大分类为问题/代表节点） */
    private List<MapDetectNodeDTO> nodes;
}
