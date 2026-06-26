package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import org.gms.server.maps.FootholdTree;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.ArtificialPlayer.BotTypes.AmbientMapBot;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.ExecutorServiceManager;

import java.awt.Point;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ThreadLocalRandom;

public final class BotAutoSpawner {
    private static final int RANDOM_MAP_POSITION_ATTEMPTS = 40;
    private static final int MIN_SPAWN_DISTANCE_FROM_PLAYER = 250;

    private static final ConcurrentMap<Integer, Integer> mapTargets = new ConcurrentHashMap<>();
    private static final Set<Integer> spawningMaps = ConcurrentHashMap.newKeySet();

    private BotAutoSpawner() {
    }

    public static void onPlayerEnterMap(Character player) {
        if (player == null || player.getClient() == null || player.getMap() == null || BotHelpers.isBot(player)) {
            return;
        }
        if (!SoloMaplingConfig.autoMapBotsEnabled()) {
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
                    int botId = BotGeneration.createBot(randomSpawnPosition(player, map), map);
                    if (botId > 0) {
                        startAmbientBehavior(botId);
                    }
                }
            } finally {
                spawningMaps.remove(map.getId());
            }
        });
    }

    private static int randomTargetCount() {
        int min = SoloMaplingConfig.autoMapBotsMin();
        int max = SoloMaplingConfig.autoMapBotsMax();
        if (max < min) {
            max = min;
        }
        return ThreadLocalRandom.current().nextInt(min, max + 1);
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
        if (!SoloMaplingConfig.ambientBehaviorEnabled() || !SoloMaplingConfig.ambientHasAnyActionEnabled()) {
            return;
        }
        Character bot = BotHelpers.getCharFromChannelStorage(botId);
        if (bot == null || CharacterStorage.botLoggedIn(botId)) {
            return;
        }

        AmbientMapBot ambientBot = new AmbientMapBot(bot);
        CharacterStorage.addActiveBot(botId, ambientBot);
        ambientBot.setRunning(true);
        ambientBot.startScheduledTask(BotGeneration.SPAWN_CHOREOGRAPHY_MAX_MS + ThreadLocalRandom.current().nextLong(1000, 4001));
    }

    private static Point randomSpawnPosition(Character player, MapleMap map) {
        if (SoloMaplingConfig.autoMapBotsRandomPositionEnabled()) {
            return randomMapPosition(player, map);
        }
        return randomNearbyPosition(player, map);
    }

    private static Point randomMapPosition(Character player, MapleMap map) {
        FootholdTree footholds = map.getFootholds();
        int minX = footholds.getMinDropX();
        int maxX = footholds.getMaxDropX();
        if (maxX <= minX) {
            return randomNearbyPosition(player, map);
        }

        Point best = null;
        ThreadLocalRandom rng = ThreadLocalRandom.current();
        for (int i = 0; i < RANDOM_MAP_POSITION_ATTEMPTS; i++) {
            int x = rng.nextInt(minX, maxX + 1);
            Point ground = map.getPointBelow(new Point(x, footholds.getY1()));
            if (ground == null) {
                continue;
            }
            best = ground;
            if (player == null || player.getPosition().distanceSq(ground) >= MIN_SPAWN_DISTANCE_FROM_PLAYER * MIN_SPAWN_DISTANCE_FROM_PLAYER) {
                return ground;
            }
        }

        return best != null ? best : randomNearbyPosition(player, map);
    }

    private static Point randomNearbyPosition(Character player, MapleMap map) {
        Point base = player.getPosition();
        int radius = SoloMaplingConfig.autoMapBotsRadius();
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
