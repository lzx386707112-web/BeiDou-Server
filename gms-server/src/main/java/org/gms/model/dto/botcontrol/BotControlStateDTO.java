package org.gms.model.dto.botcontrol;

public record BotControlStateDTO(int activeBots, int marketDirectorBots, int marketEntranceBots,
                                 int onlinePlayers, boolean marketReady, boolean marketStarting) {
}
