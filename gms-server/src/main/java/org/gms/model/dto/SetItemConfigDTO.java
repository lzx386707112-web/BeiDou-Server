package org.gms.model.dto;

import java.util.List;
import java.util.Map;

public record SetItemConfigDTO(int id, int jobIndex, String name, int completeCount,
                               boolean builtIn, boolean enabled,
                               List<List<SetItemEquipmentDTO>> slots, List<Tier> tiers) {
    public record Tier(int requiredCount, Map<String, Integer> stats,
                       Map<String, Integer> defaultStats, boolean customized) {
    }
}
