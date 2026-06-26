package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import soloMapling.Environment.EnvironmentManager;
import soloMapling.SoloMaplingConfig;


public final class BotAutoSpawner {
    private BotAutoSpawner() {
    }

    public static void onPlayerEnterMap(Character player) {
        if (player == null || player.getClient() == null || player.getMap() == null || BotHelpers.isBot(player)) {
            return;
        }
        EnvironmentManager.ensureMarketServiceNpcs(player.getMap());
        if (!SoloMaplingConfig.autoMapBotsEnabled()) {
            return;
        }

        BotClientHandler.createBotClient(player.getClient());
        EnvironmentManager.marketEnvironmentStartup();
    }
}
