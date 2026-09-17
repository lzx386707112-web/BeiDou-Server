package soloMapling.ArtificialPlayer.BotTownSystem;

import java.awt.Point;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands;
import soloMapling.ArtificialPlayer.BotSpotClaims;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownStation.class */
public final class TownStation {
    private static final int CAPACITY = 3;
    private static final Map<Integer, Claim> ACTIVE = new ConcurrentHashMap();
    private static final Object CLAIM_LOCK = new Object();

    private TownStation() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownStation$Claim.class */
    private static final class Claim {
        private final int mapId;
        private final int ledgeId;

        private Claim(int mapId, int ledgeId) {
            this.mapId = mapId;
            this.ledgeId = ledgeId;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public int mapId() {
            return this.mapId;
        }

        public int ledgeId() {
            return this.ledgeId;
        }
    }

    public static boolean claimSpot(Character bot) {
        if (bot == null || bot.getMap() == null) {
            return false;
        }
        MapleMap map = bot.getMap();
        int mapId = bot.getMapId();
        int botId = bot.getId();
        Point p = bot.getPosition();
        int ledgeId = GCMovement.regionIdAt(map, p.x, p.y);
        synchronized (CLAIM_LOCK) {
            releaseLocked(botId);
            if (ledgeId < 0) {
                return false;
            }
            if (BotSpotClaims.claim(mapId, ledgeId, CAPACITY, botId) >= 0) {
                ACTIVE.put(Integer.valueOf(botId), new Claim(mapId, ledgeId));
                return true;
            }
            return false;
        }
    }

    public static void releaseSpot(Character bot) {
        if (bot == null) {
            return;
        }
        synchronized (CLAIM_LOCK) {
            releaseLocked(bot.getId());
        }
    }

    public static boolean relocate(Character bot, Point townAnchor) {
        if (bot == null || bot.getMap() == null) {
            return false;
        }
        MapleMap map = bot.getMap();
        int mapId = bot.getMapId();
        Point anchor = townAnchor != null ? townAnchor : bot.getPosition();
        List<Point> spots = TownPresenceSampler.sample(map, anchor, 1, TownPresenceConfig.overridesFor(mapId));
        if (spots.isEmpty()) {
            return false;
        }
        Point dest = spots.get(0);
        releaseSpot(bot);
        try {
            MovementCommands.pathFinderAware(bot, dest);
        } catch (Exception e) {
        }
        claimSpot(bot);
        return true;
    }

    public static boolean isStationed(Character bot) {
        return bot != null && ACTIVE.containsKey(Integer.valueOf(bot.getId()));
    }

    private static void releaseLocked(int botId) {
        Claim c = ACTIVE.remove(Integer.valueOf(botId));
        if (c != null) {
            BotSpotClaims.release(c.mapId(), c.ledgeId(), botId);
        }
    }
}
