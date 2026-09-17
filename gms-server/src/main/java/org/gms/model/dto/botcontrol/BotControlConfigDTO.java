package org.gms.model.dto.botcontrol;

import java.util.List;

public record BotControlConfigDTO(
        List<BotControlFieldDTO> market,
        List<BotControlFieldDTO> appearance,
        List<BotControlFieldDTO> environment,
        List<BotControlFieldDTO> party) {
}
