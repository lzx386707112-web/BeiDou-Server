package org.gms.model.dto;

import java.util.List;

public record MobCatalogPageDTO(
        List<MobCatalogItemDTO> records,
        int pageNo,
        int pageSize,
        int total) {
}
