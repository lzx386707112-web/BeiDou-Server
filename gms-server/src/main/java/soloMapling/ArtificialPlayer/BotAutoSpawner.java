package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import soloMapling.Environment.EnvironmentManager;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.ExecutorServiceManager;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;


public final class BotAutoSpawner {
    private static final int FM_ENTRANCE = 910000000;
    private static final long MARKET_STARTUP_DELAY_MS = 2_500L;
    private static final AtomicBoolean marketStartupQueued = new AtomicBoolean(false);

    private BotAutoSpawner() {
    }

    public static void onPlayerEnterMap(Character player) {
        if (player == null || player.getClient() == null || player.getMap() == null || BotHelpers.isBot(player)) {
            return;
        }
        EnvironmentManager.ensureMarketServiceNpcs(player.getMap());
        BotClientHandler.createBotClient(player.getClient());

        if (player.getMapId() != FM_ENTRANCE
                || !SoloMaplingConfig.autoEnvironmentEnabled()
                || !SoloMaplingConfig.autoMapBotsEnabled()) {
            return;
        }
        if (!marketStartupQueued.compareAndSet(false, true)) {
            return;
        }
        ExecutorServiceManager.getScheduledExecutorService().schedule(
                EnvironmentManager::marketEnvironmentStartup,
                MARKET_STARTUP_DELAY_MS,
                TimeUnit.MILLISECONDS
        );
    }
}
