package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import org.gms.client.Client;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.MethodScheduler;

import java.util.concurrent.atomic.AtomicLong;


public class BotClientHandler {

    final static String clientIp = "127.0.0.1";
    static final AtomicLong sessionId = new AtomicLong(6969);
    static Client botClient = null;


    public static void createBotClient(Client c) {
        boolean firstCapture = botClient == null;
        botClient = c;
        if (firstCapture && SoloMaplingConfig.autoEnvironmentEnabled()) {
            MethodScheduler.runAfterDelay(soloMapling.Environment.EnvironmentManager::environmentLoadStartup, 1000);
        }
    }

    public static Client getBotClient() {
        return botClient;
    }

    public static void disconnectFirstClient(Client c) {
        Character player = c.getPlayer();
        for (int i = 0; i < 10; i++) {
            player.yellowMessage("SoloMapling no longer disconnects the first player on BeiDou.");
        }
    }

}
