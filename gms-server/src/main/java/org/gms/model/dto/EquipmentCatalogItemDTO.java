package org.gms.model.dto;

import java.util.Map;

public record EquipmentCatalogItemDTO(
        int id,
        String name,
        String description,
        String category,
        Map<String, Integer> stats,
        boolean iconAvailable) {
}
