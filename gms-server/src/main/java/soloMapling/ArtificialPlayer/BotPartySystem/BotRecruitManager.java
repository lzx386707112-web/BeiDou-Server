package soloMapling.ArtificialPlayer.BotPartySystem;

public final class BotRecruitManager {
    private BotRecruitManager() {
    }

    public static boolean isCompanion(int botId) {
        return PartyGrindService.isCompanion(botId);
    }
}
