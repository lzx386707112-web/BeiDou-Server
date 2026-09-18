package org.gms.model.dto;

import java.util.List;

/**
 * 技能目录分页 DTO
 */
public record SkillCatalogPageDTO(
    List<SkillCatalogItemDTO> records,
    List<SkillJobCategoryDTO> jobs,
    int pageNo,
    int pageSize,
    int total,
    boolean loaded,
    String message
) {}
