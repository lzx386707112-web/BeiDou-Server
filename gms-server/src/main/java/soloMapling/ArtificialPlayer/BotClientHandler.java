package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import org.gms.client.Client;
import soloMapling.server.SoloMaplingConstants;

import java.util.concurrent.atomic.AtomicLong;


public class BotClientHandler {

    final static String clientIp = "127.0.0.1";
    static final AtomicLong sessionId = new AtomicLong(6969);
    static Client botClient = null;


    public static synchronized Client ensureStandaloneClient() {
        if (botClient != null && botClient.getWorldServer() != null) {
            return botClient;
        }
        Client mock = Client.createMock();
        mock.setWorld(SoloMaplingConstants.GameConstants.WORLD_SCANIA);
        mock.setChannel(SoloMaplingConstants.GameConstants.CHANNEL_1);
        Character host = Character.getDefault(mock);
        host.setID(0);
        mock.setPlayer(host);
        botClient = mock;
        return botClient;
    }

    public static void createBotClient(Client c) {
        ensureStandaloneClient();
    }

    public static Client getBotClient() {
        return ensureStandaloneClient();
    }

    public static void disconnectFirstClient(Client c) {
        Character player = c.getPlayer();
        for (int i = 0; i < 10; i++) {
            player.yellowMessage("SoloMapling no longer disconnects the first player on BeiDou.");
        }
    }

}
