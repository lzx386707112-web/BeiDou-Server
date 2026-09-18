package org.gms.model.dto;

/**
 * 技能职业分类 DTO
 */
public record SkillJobCategoryDTO(
    int jobId,
    String jobName,
    int count
) {}
