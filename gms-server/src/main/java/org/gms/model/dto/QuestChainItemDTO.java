package org.gms.model.dto;

import lombok.Data;

/**
 * 任务浏览 —— 任务链成员。
 */
@Data
public class QuestChainItemDTO {
    private String questId;
    private String name;
    private Integer levelMin;
    /** 是否为当前查看的任务 */
    private Boolean current;
}
