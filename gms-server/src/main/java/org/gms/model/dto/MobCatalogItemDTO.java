package org.gms.model.dto;

import java.util.Map;

public record MobCatalogItemDTO(
        int id,
        String name,
        Map<String, Integer> stats,
        boolean iconAvailable) {
}
