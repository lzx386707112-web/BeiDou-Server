package org.gms.model.dto;

import java.util.Map;

public record ItemCatalogItemDTO(
        int id,
        String name,
        String description,
        String category,
        Map<String, Object> specs,
        boolean iconAvailable) {
}
