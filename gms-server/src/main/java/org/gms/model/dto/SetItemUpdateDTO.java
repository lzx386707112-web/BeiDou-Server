package org.gms.model.dto;

import lombok.Data;

import java.util.Map;
import java.util.List;

@Data
public class SetItemUpdateDTO {
    private Map<Integer, Map<String, Integer>> tiers;
    private List<List<Integer>> slots;
}
