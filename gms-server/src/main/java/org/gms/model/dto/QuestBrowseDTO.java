package org.gms.model.dto;

import lombok.Data;

/**
 * 任务浏览 —— 请求 DTO。
 */
@Data
public class QuestBrowseDTO {
    /** 大地区 key（如 victoria；树接口返回的 region value） */
    private String region;
    /** 城镇/街道名（如 射手村；空表示该地区全部） */
    private String town;
    /** 任务 id（详情接口用） */
    private String questId;
}
