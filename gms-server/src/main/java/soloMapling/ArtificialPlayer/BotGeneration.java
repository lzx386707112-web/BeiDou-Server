package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.client.Job;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.server.SoloMaplingConstants;
import soloMapling.server.SoloMaplingUtilities;

import java.awt.*;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicInteger;

import static soloMapling.ArtificialPlayer.BotClientHandler.getBotClient;
import static soloMapling.ArtificialPlayer.BotCommandsPack.WarpCommands.botEnterPortalDropDown;
import static soloMapling.ArtificialPlayer.BotDecoratorSystem.BotDecorate.setBotVariables;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.microTurnAroundToLeft;
import static soloMapling.DebugUtilities.debugprint;
import static soloMapling.server.ExecutorServiceManager.runAsync;
import static soloMapling.server.SoloMaplingUtilities.getChr;
import static soloMapling.server.SoloMaplingUtilities.channel;
import static soloMapling.server.SoloMaplingUtilities.getMapleMapById;
import static soloMapling.server.SoloMaplingUtilities.world;

public class BotGeneration {

    // Bot generation - handles anything related to putting the bots in the server

    // Atomic because bots spawn in parallel - a plain int would let two threads
    // grab the same id, silently overwriting one bot with another in storage.
    private static final AtomicInteger currentBotCount = new AtomicInteger(100);
    private static final String[] CHINESE_NAME_PREFIXES = {
            "小", "阿", "云", "星", "枫", "南", "北", "青", "白", "洛",
            "夏", "秋", "雨", "风", "月", "川", "竹", "桃", "一", "七"
    };
    private static final String[] CHINESE_NAME_SUFFIXES = {
            "枫", "糖", "鱼", "鹿", "橙", "眠", "茶", "雪", "竹", "舟",
            "安", "宁", "澈", "遥", "然", "梨", "月", "星", "豆", "夏"
    };

    /**
     * Worst-case duration of the spawn choreography (pre-drop delay 0.5-1.2s
     * + portal lag 1.5s + drop-down playback + optional turn-around delay
     * 1.0-1.5s + turn playback). Anything that must visually wait for a freshly
     * spawned bot to finish arriving (FSM first tick, shop opening, chair sits,
     * facing adjustments) should delay by at least this much.
     */
    public static final long SPAWN_CHOREOGRAPHY_MAX_MS = 7000;

    /** Total number of bots created since server start (for startup logging). */
    public static int getBotsCreatedCount() {
        return currentBotCount.get() - 100;
    }


    public static Character getConsoleBot() {
        Character consoleBot = getChr(999);
        if (consoleBot != null) {
            return consoleBot;
        }

        int botId = 999;

        consoleBot = loadBotTemplate();

        consoleBot = setConsoleBot(consoleBot, botId); // Bot onDemandBot
        addBotToServer(consoleBot);
        return consoleBot;
    }

    public static int createBot(Point pos, MapleMap map) {
        Character bot = loadBotTemplate();
        int botId = SoloMaplingConstants.GameConstants.BOT_BASE_ID + currentBotCount.getAndIncrement();
        bot = setBotStats(bot, botId); // Bot onDemandBot
        addBotToServer(bot);
        placeBotOnMap(bot, pos, map);
        // Decorate before the drop-down plays so the bot arrives fully dressed
        // (decoration is an in-memory cache lookup, takes microseconds).
        setBotVariables(bot);
        // Choreography sleeps ~2.5-6s in total; play it on a virtual thread so
        // mass spawning isn't gated on each bot's arrival animation. Drop-down ->
        // turn-around ordering is preserved because it's one sequential task.
        Character finalBot = bot;
        runAsync(() -> playSpawnChoreography(finalBot));
        return botId;
    }

    private static Character loadBotTemplate() {
        Client client = getBotClient();
        if (client == null || client.getPlayer() == null) {
            throw new IllegalStateException("Bot client is not initialized. Run a SoloMapling command from an online character first.");
        }

        int templateCid = client.getPlayer().getId();
        return Character.loadCharFromDB(templateCid, client, false);
    }


    /**
     * Places the bot on a map + position and plays the portal drop-down animation
     * so the spawn looks like a real player arriving. Sequence runs inline so the
     * caller waits for the full spawn choreography to finish before continuing —
     * use this (not createBot's async path) when downstream actions must not race
     * the drop-down / turn-around (e.g. OPQ map transitions).
     *
     * This method blocks the calling thread for roughly 2.5-6s total. Callers
     * should already be running on a pooled executor (not the client thread).
     */
    public static void warpBotToLocation(Character fakechar, Point pos, MapleMap map) {
        placeBotOnMap(fakechar, pos, map);
        playSpawnChoreography(fakechar);
    }

    private static void placeBotOnMap(Character fakechar, Point pos, MapleMap map) {
        if (fakechar.getMap() == map) {
            fakechar.getMap().removePlayer(fakechar);
        }
        fakechar.setMap(map);
        fakechar.setPosition(pos);
        fakechar.setStance(5);
        map.addPlayer(fakechar);
    }

    /**
     * The spawn arrival choreography. Blocks the calling thread while it plays:
     *   - drop-down fires 500-1200ms after the bot is added to the map
     *     (plus ~1.5s portal lag inside botEnterPortalDropDown)
     *   - a random-direction micro turn-around fires 1000-1500ms after the
     *     drop-down playback completes - the strict ordering matters, the turn
     *     must never overlap the drop-down packets
     * Worst case is bounded by {@link #SPAWN_CHOREOGRAPHY_MAX_MS}.
     */
    private static void playSpawnChoreography(Character fakechar) {
        long dropDelayMs = ThreadLocalRandom.current().nextLong(500, 1201);
        if (!BotHelpers.sleepAmountSeconds(dropDelayMs)) return;
        botEnterPortalDropDown(fakechar);

        // Bots spawn facing right by default, so a 50% roll to flip to left gives
        // roughly even left/right distribution without a no-op right-turn.
        if (ThreadLocalRandom.current().nextBoolean()) {
            long turnDelayMs = ThreadLocalRandom.current().nextLong(1000, 1501);
            if (!BotHelpers.sleepAmountSeconds(turnDelayMs)) return;
            microTurnAroundToLeft(fakechar);
        }
    }

    private static Character setConsoleBot(Character baseChr, int botId) {
        Character onDemandBot = baseChr; // Character.getDefault(c)
        onDemandBot.setClient(getBotClient());
        onDemandBot.setName("Console");

        onDemandBot.setID(botId);
        onDemandBot.setFame(botId); // debug purposes
        onDemandBot.setLevel(69);
        onDemandBot.setJob(Job.getById(420));

        return onDemandBot;
    }

    private static Character setBotStats(Character baseChr, int botId) {
        Character onDemandBot = baseChr; // Character.getDefault(c)
        onDemandBot.setClient(getBotClient());
        onDemandBot.setName(getRandomChineseBotName());
        onDemandBot.setID(botId);
        onDemandBot.setFame(botId); // debug purposes
        return onDemandBot;
    }

    private static String getRandomChineseBotName() {
        String prefix = CHINESE_NAME_PREFIXES[ThreadLocalRandom.current().nextInt(CHINESE_NAME_PREFIXES.length)];
        String suffix = CHINESE_NAME_SUFFIXES[ThreadLocalRandom.current().nextInt(CHINESE_NAME_SUFFIXES.length)];
        if (ThreadLocalRandom.current().nextInt(100) < 35) {
            String suffix2 = CHINESE_NAME_SUFFIXES[ThreadLocalRandom.current().nextInt(CHINESE_NAME_SUFFIXES.length)];
            return prefix + suffix + suffix2;
        }
        return prefix + suffix;
    }

    public static void removeBotFromServer(Character fakechar) {
        fakechar.getMap().removePlayer(fakechar);
        channel.removePlayer(fakechar);
        world.getPlayerStorage().removePlayer(fakechar.getId());
        CharacterStorage.removeActiveBot(fakechar.getId());//
    }

    private static void addBotToServer(Character fakechar) {
//        final Channel channel = Server.getInstance().getChannel(BotSM.GameConstants.WORLD_SCANIA, BotSM.GameConstants.CHANNEL_1);
        channel.addPlayer(fakechar);
//        World world = Server.getInstance().getWorld(BotSM.GameConstants.WORLD_SCANIA);
        world.getPlayerStorage().addPlayer(fakechar);
    }

    public static void spawnBotFm(Character fakechar, Point pt) {
        int fmMap = 910000000;
        MapleMap spawnMap = getBotClient().getChannelServer().getMapFactory().getMap(fmMap);
        fakechar.setMap(spawnMap);
        fakechar.setPosition(pt);
        fakechar.setStance(5);
        spawnMap.addPlayer(fakechar);
    }

    /*
    Creates a bot on demand. The bot is registered in channel storage synchronously
    inside createBot, so it's normally ready on the first check - the 100ms poll
    loop only kicks in as a fallback. If the bot isn't ready after 3000ms, returns null.
     */
    public static Character createBotPollReadiness(Point position, int mapId) {
        int botId = BotGeneration.createBot(position, getMapleMapById(mapId));

        for (int i = 0; i < 30; i++) { // 30 * 100ms = 3000ms max
            Character fakechar = BotHelpers.getCharFromChannelStorage(botId);
            if (fakechar != null) {
                if (i > 0) {
                    debugprint("Bot " + botId + " ready after " + (i * 100) + "ms");
                }
                return fakechar;
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return null;
            }
        }

        System.err.println("Bot " + botId + " not ready after 3 seconds, skipping store");
        return null;
    }

}
