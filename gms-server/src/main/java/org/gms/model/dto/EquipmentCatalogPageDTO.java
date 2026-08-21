package org.gms.model.dto;

import java.util.List;

public record EquipmentCatalogPageDTO(
        List<EquipmentCatalogItemDTO> records,
        List<EquipmentCatalogCategoryDTO> categories,
        int pageNo,
        int pageSize,
        int total,
        List<EquipmentCatalogCategoryDTO> weaponTypes,
        int cashCount,
        int nonCashCount) {
}
