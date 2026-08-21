package org.gms.model.dto;

import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
public class SetItemDefinitionCreateDTO {
    private Integer id;
    private String name;
    private Integer jobIndex;
    private List<List<Integer>> slots;
    private Map<Integer, Map<String, Integer>> tiers;
}
