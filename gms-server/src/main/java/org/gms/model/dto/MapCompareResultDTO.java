package org.gms.model.dto;

import lombok.Data;

import java.util.List;

/**
 * 地图对比结果：两张地图的结构差异。
 */
@Data
public class MapCompareResultDTO {
    private String mapIdA;
    private String mapIdB;
    /** 两图的基础信息对比 */
    private MapCompareInfoDTO infoA;
    private MapCompareInfoDTO infoB;
    /** 差异列表 */
    private List<MapCompareDiffDTO> diffs;
    /** 崩溃风险评估摘要 */
    private String crashSummary;

    @Data
    public static class MapCompareInfoDTO {
        private String mapId;
        private boolean mapExists;
        private int lifeCount;
        private int mobCount;
        private int npcCount;
        private int fhCount;
        private int portalCount;
        private int objCount;
        private int backCount;
        private int crashRiskCount;
        private int fileSize;
    }

    @Data
    public static class MapCompareDiffDTO {
        /** 分类：life / foothold / portal / obj / back / info */
        private String category;
        /** 描述 */
        private String description;
        /** 地图A的值 */
        private String valueA;
        /** 地图B的值 */
        private String valueB;
        /** 是否可能与崩溃相关 */
        private String crashRisk;
    }
}
