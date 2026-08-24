package org.gms.model.dto;

import lombok.Data;

import java.util.List;

/**
 * 任务浏览 —— 任务详情（含三段任务内容与任务链）。
 */
@Data
public class QuestDetailDTO {
    private String questId;
    private String name;
    private Integer levelMin;
    private Integer levelMax;
    private String startNpcId;
    private String startNpcName;
    private String endNpcId;
    private String endNpcName;
    /** 任务内容（开始时） */
    private String contentStart;
    /** 任务内容（进行中） */
    private String contentProgress;
    /** 任务内容（完成时） */
    private String contentComplete;
    /** 链组名（QuestInfo/parent，如"莎丽的镜子"） */
    private String parentName;
    /** 链内序号（QuestInfo/order） */
    private Integer order;
    /** 任务链（有序；单任务无链时仅含自身） */
    private List<QuestChainItemDTO> chain;
    private String region;
    private String town;
}
