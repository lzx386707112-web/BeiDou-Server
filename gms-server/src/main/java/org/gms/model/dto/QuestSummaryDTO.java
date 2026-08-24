package org.gms.model.dto;

import lombok.Data;

/**
 * 任务浏览 —— 任务列表项（列表页按等级排序展示）。
 */
@Data
public class QuestSummaryDTO {
    /** 任务 id */
    private String questId;
    /** 任务名 */
    private String name;
    /** 最低等级（Check/0/lvmin，无限制为 null） */
    private Integer levelMin;
    /** 最高等级（Check/0/lvmax，无限制为 null） */
    private Integer levelMax;
    /** 起始 NPC id */
    private String startNpcId;
    /** 起始 NPC 名 */
    private String startNpcName;
    /** 结束 NPC id */
    private String endNpcId;
    /** 结束 NPC 名 */
    private String endNpcName;
    /** 是否属于任务链（有前置/后继或链组名） */
    private Boolean inChain;
    /** 所属大地区（key） */
    private String region;
    /** 所属城镇/街道 */
    private String town;
}
