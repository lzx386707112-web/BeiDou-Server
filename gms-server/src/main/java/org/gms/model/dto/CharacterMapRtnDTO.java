package org.gms.model.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CharacterMapRtnDTO {
    private int characterId;
    private String characterName;
    private int mapId;
    private String mapName;
}
