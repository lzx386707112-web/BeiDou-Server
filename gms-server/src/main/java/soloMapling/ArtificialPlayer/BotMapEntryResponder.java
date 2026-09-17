package soloMapling.ArtificialPlayer;

import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicBoolean;
import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.server.EventMessageSystem.EventBus;
import soloMapling.server.EventMessageSystem.EventSubscriber;
import soloMapling.server.EventMessageSystem.EventType;
import soloMapling.server.EventMessageSystem.GameEvent;
import soloMapling.server.ExecutorServiceManager;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotMapEntryResponder.class */
public final class BotMapEntryResponder implements EventSubscriber {
    private static final BotMapEntryResponder INSTANCE = new BotMapEntryResponder();
    private static final AtomicBoolean REGISTERED = new AtomicBoolean(false);
    private static final long NUDGE_MIN_MS = 150;
    private static final long NUDGE_MAX_MS = 700;

    private BotMapEntryResponder() {
    }

    public static void register() {
        if (REGISTERED.compareAndSet(false, true)) {
            EventBus.getInstance().subscribe(EventType.MAP_ENTERED, INSTANCE);
        }
    }

    public boolean matchesFilter(GameEvent event) {
        return event != null && event.getType() == EventType.MAP_ENTERED;
    }

    public void onEvent(GameEvent event) {
        try {
            MapleMap map = event.getMap();
            if (map == null) {
                return;
            }
            ExecutorServiceManager.runAsync(() -> {
                nudgeBotsOnMap(map);
            });
        } catch (Throwable th) {
        }
    }

    private void nudgeBotsOnMap(MapleMap map) {
        try {
            for (Character chr : map.getAllPlayers()) {
                if (chr != null && BotHelpers.isBot(chr)) {
                    nudge(chr);
                }
            }
        } catch (Throwable th) {
        }
    }

    public static void onBotArrivedObserved(Character bot) {
        if (bot != null) {
            try {
                INSTANCE.nudge(bot);
            } catch (Throwable th) {
            }
        }
    }

    private void nudge(Character botChr) {
        BotSM bot = (BotSM) CharacterStorage.getAllBots().get(Integer.valueOf(botChr.getId()));
        if (bot == null || !bot.getRunning()) {
            return;
        }
        long jitter = ThreadLocalRandom.current().nextLong(NUDGE_MIN_MS, 701L);
        bot.nudgeSoon(jitter);
    }
}
