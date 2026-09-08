package org.gms.model.dto;

import java.util.List;

public record ItemCatalogPageDTO(
        List<ItemCatalogItemDTO> records,
        List<EquipmentCatalogCategoryDTO> categories,
        int pageNo,
        int pageSize,
        int total) {
}
