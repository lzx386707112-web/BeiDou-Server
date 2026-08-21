package org.gms.model.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

@Data
public class SetItemCatalogStorageDTO {
    private Set<Integer> disabledBuiltInIds = new LinkedHashSet<>();
    private List<SetItemDefinitionCreateDTO> customDefinitions = new ArrayList<>();
}
