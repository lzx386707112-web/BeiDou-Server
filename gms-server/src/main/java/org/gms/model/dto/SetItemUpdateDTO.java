package org.gms.model.dto;

import lombok.Data;

import java.util.Map;

@Data
public class SetItemUpdateDTO {
    private Map<Integer, Map<String, Integer>> tiers;
}
