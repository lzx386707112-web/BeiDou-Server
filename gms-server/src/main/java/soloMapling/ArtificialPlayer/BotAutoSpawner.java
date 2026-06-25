package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import org.gms.config.GameConfig;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.ArtificialPlayer.BotTypes.AmbientMapBot;
import soloMapling.server.ExecutorServiceManager;

import java.awt.Point;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ThreadLocalRandom;

public final class BotAutoSpawner {
    private static final String ENABLED_KEY = "solo_mapling_auto_map_bots_enabled";
    private static final String MIN_KEY = "solo_mapling_auto_map_bots_min";
    private static final String MAX_KEY = "solo_mapling_auto_map_bots_max";
    private static final String RADIUS_KEY = "solo_mapling_auto_map_bots_radius";

    private static final ConcurrentMap<Integer, Integer> mapTargets = new ConcurrentHashMap<>();
    private static final Set<Integer> spawningMaps = ConcurrentHashMap.newKeySet();

    private BotAutoSpawner() {
    }

    public static void onPlayerEnterMap(Character player) {
        if (player == null || player.getClient() == null || player.getMap() == null || BotHelpers.isBot(player)) {
            return;
        }
        if (!isEnabled()) {
            return;
        }

        BotClientHandler.createBotClient(player.getClient());

        MapleMap map = player.getMap();
        int target = mapTargets.computeIfAbsent(map.getId(), ignored -> randomTargetCount());
        int existingBots = countBots(map);
        int missing = target - existingBots;
        if (missing <= 0) {
            return;
        }
        if (!spawningMaps.add(map.getId())) {
            return;
        }

        ExecutorServiceManager.runAsync(() -> {
            try {
                for (int i = 0; i < missing; i++) {
                    if (countBots(map) >= target) {
                        break;
                    }
                    int botId = BotGeneration.createBot(randomNearbyPosition(player, map), map);
                    startAmbientBehavior(botId);
                }
            } finally {
                spawningMaps.remove(map.getId());
            }
        });
    }

    private static boolean isEnabled() {
        String configured = GameConfig.getServerString(ENABLED_KEY);
        return configured.isEmpty() || Boolean.parseBoolean(configured);
    }

    private static int randomTargetCount() {
        int min = readPositiveInt(MIN_KEY, 2);
        int max = readPositiveInt(MAX_KEY, 4);
        if (max < min) {
            max = min;
        }
        return ThreadLocalRandom.current().nextInt(min, max + 1);
    }

    private static int readPositiveInt(String key, int defaultValue) {
        int value = GameConfig.getServerInt(key);
        return value > 0 ? value : defaultValue;
    }

    private static int countBots(MapleMap map) {
        int count = 0;
        for (Character chr : map.getAllPlayers()) {
            if (BotHelpers.isBot(chr)) {
                count++;
            }
        }
        return count;
    }

    private static void startAmbientBehavior(int botId) {
        Character bot = BotHelpers.getCharFromChannelStorage(botId);
        if (bot == null || CharacterStorage.botLoggedIn(botId)) {
            return;
        }

        AmbientMapBot ambientBot = new AmbientMapBot(bot);
        CharacterStorage.addActiveBot(botId, ambientBot);
        ambientBot.setRunning(true);
        ambientBot.startScheduledTask(BotGeneration.SPAWN_CHOREOGRAPHY_MAX_MS + ThreadLocalRandom.current().nextLong(1000, 4001));
    }

    private static Point randomNearbyPosition(Character player, MapleMap map) {
        Point base = player.getPosition();
        int radius = readPositiveInt(RADIUS_KEY, 350);
        int offset = ThreadLocalRandom.current().nextInt(-radius, radius + 1);
        if (Math.abs(offset) < 60) {
            offset = offset < 0 ? -60 : 60;
        }

        Point candidate = new Point(base.x + offset, base.y);
        try {
            Point ground = map.getGroundBelow(candidate);
            if (ground != null) {
                return ground;
            }
        } catch (Exception ignored) {
        }
        return candidate;
    }
}
