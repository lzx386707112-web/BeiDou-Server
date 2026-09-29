package org.gms.model.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.Map;
import java.util.LinkedHashMap;

@Data
public class SetItemCatalogStorageDTO {
    private Set<Integer> disabledBuiltInIds = new LinkedHashSet<>();
    private List<SetItemDefinitionCreateDTO> customDefinitions = new ArrayList<>();
    private Map<Integer, List<List<Integer>>> slotOverrides = new LinkedHashMap<>();
}
