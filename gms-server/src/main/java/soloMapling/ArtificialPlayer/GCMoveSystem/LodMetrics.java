package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import org.gms.client.Character;
import org.gms.net.server.Server;
import org.gms.net.server.world.World;
import soloMapling.ArtificialPlayer.BotHelpers;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/LodMetrics.class */
final class LodMetrics {
    private static final int DEFAULT_LOAD = 50;
    private static final int TOP_MAPS = 6;
    private static final Set<Integer> LOADED = ConcurrentHashMap.newKeySet();

    private LodMetrics() {
    }

    static List<String> stats() {
        Collection<BotMovementState> states = GCMovement.enabledStates();
        int total = states.size();
        int moving = 0;
        int traveling = 0;
        int following = 0;
        int idle = 0;
        int tierFull = 0;
        int tierHalo = 0;
        int tierDwell = 0;
        int tierCoarse = 0;
        Map<Integer, Integer> botsByMap = new HashMap<>();
        for (BotMovementState st : states) {
            Character bot = st.bot;
            if (bot != null) {
                int mapId = bot.getMapId();
                botsByMap.merge(Integer.valueOf(mapId), 1, (v0, v1) -> {
                    return Integer.sum(v0, v1);
                });
                boolean t = GCMovement.isTraveling(bot);
                boolean f = GCMovement.isFollowing(bot);
                boolean m = GCMovement.isMoving(bot);
                if (t) {
                    traveling++;
                } else if (m) {
                    moving++;
                } else if (f) {
                    following++;
                } else {
                    idle++;
                }
                if (ObserverTracker.isFull(mapId)) {
                    tierFull++;
                } else if (ObserverTracker.isHalo(mapId)) {
                    tierHalo++;
                } else if (ObserverTracker.isActiveMap(mapId)) {
                    tierDwell++;
                } else {
                    tierCoarse++;
                }
            }
        }
        List<String> out = new ArrayList<>();
        out.add("=== GCMove LOD load ===");
        out.add(String.format("dynamic bots: %d  (moving=%d traveling=%d following=%d idle=%d)", Integer.valueOf(total), Integer.valueOf(moving), Integer.valueOf(traveling), Integer.valueOf(following), Integer.valueOf(idle)));
        out.add(String.format("tiers: FULL=%d HALO=%d dwell=%d coarse=%d   (maps: full=%d halo=%d active=%d)", Integer.valueOf(tierFull), Integer.valueOf(tierHalo), Integer.valueOf(tierDwell), Integer.valueOf(tierCoarse), Integer.valueOf(ObserverTracker.fullCount()), Integer.valueOf(ObserverTracker.haloCount()), Integer.valueOf(ObserverTracker.activeCount())));
        out.add(String.format("occupied maps: %d   load-test bots: %d", Integer.valueOf(botsByMap.size()), Integer.valueOf(LOADED.size())));
        botsByMap.entrySet().stream().sorted(Map.Entry.<Integer, Integer>comparingByValue().reversed()).limit(6L).forEach(e -> {
            out.add(String.format("  map %d : %d bot(s)", e.getKey(), e.getValue()));
        });
        out.add("(watch the JVM/host CPU at this bot count — that is the M0 measurement)");
        return out;
    }

    static int load(int n) {
        if (n <= 0) {
            n = DEFAULT_LOAD;
        }
        int enabled = 0;
        for (World world : Server.getInstance().getWorlds()) {
            for (Character chr : world.getPlayerStorage().getAllCharacters()) {
                if (enabled >= n) {
                    return enabled;
                }
                if (chr != null && BotHelpers.isBot(chr) && !GCMovement.isEnabled(chr)) {
                    GCMovement.enable(chr);
                    GCMovement.setFidget(chr, true);
                    LOADED.add(Integer.valueOf(chr.getId()));
                    enabled++;
                }
            }
        }
        return enabled;
    }

    static int unload() {
        int released = 0;
        Iterator<Integer> it = LOADED.iterator();
        while (it.hasNext()) {
            int id = it.next().intValue();
            Character bot = BotHelpers.getCharFromChannelStorage(id);
            if (bot != null) {
                GCMovement.setFidget(bot, false);
                GCMovement.disable(bot);
            }
            released++;
        }
        LOADED.clear();
        return released;
    }
}
