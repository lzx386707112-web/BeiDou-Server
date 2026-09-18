package org.gms.model.dto;

import java.util.List;
import java.util.Map;

/**
 * 技能目录项 DTO
 */
public record SkillCatalogItemDTO(
    int id,
    String name,
    String desc,
    String jobName,
    int jobId,
    int maxLevel,
    boolean iconAvailable,
    Map<String, Object> attributes,
    List<String> levelDescs
) {}
