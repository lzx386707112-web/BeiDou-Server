package soloMapling.ArtificialPlayer.BotTownSystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotGrindSystem.BotSpotPicker;
import soloMapling.ArtificialPlayer.BotSpotClaims;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownLoiter.class */
public final class TownLoiter {
    private static final int CAPACITY_PER_LEDGE = 3;
    private static final int PICK_ATTEMPTS = 4;
    private static final Map<Integer, Claim> ACTIVE = new ConcurrentHashMap();
    private static final Object CLAIM_LOCK = new Object();

    private TownLoiter() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownLoiter$Claim.class */
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

    public static void settle(Character bot) {
        if (bot == null || bot.getMap() == null) {
            return;
        }
        Point p = bot.getPosition();
        settle(bot, p.x, p.y, 0, true);
    }

    public static void settle(Character bot, int anchorX, int anchorY, int radius, boolean fidget) {
        Point pointPickGroundSpot;
        if (bot == null || bot.getMap() == null) {
            return;
        }
        MapleMap map = bot.getMap();
        int mapId = bot.getMapId();
        int botId = bot.getId();
        List<int[]> candidateLedges = new ArrayList<>();
        List<Point> candidateSpots = new ArrayList<>();
        for (int i = 0; i < 4; i++) {
            if (radius > 0) {
                pointPickGroundSpot = BotSpotPicker.pickGroundSpot(map, anchorX, anchorY, anchorX - radius, anchorX + radius);
            } else {
                pointPickGroundSpot = BotSpotPicker.pickGroundSpot(map, anchorX, anchorY);
            }
            Point spot = pointPickGroundSpot;
            if (spot == null) {
                break;
            }
            candidateSpots.add(spot);
            candidateLedges.add(new int[]{GCMovement.regionIdAt(map, spot.x, spot.y)});
        }
        Point chosen = null;
        synchronized (CLAIM_LOCK) {
            releaseLocked(botId);
            int i2 = 0;
            while (true) {
                if (i2 >= candidateSpots.size()) {
                    break;
                }
                Point spot2 = candidateSpots.get(i2);
                int ledgeId = candidateLedges.get(i2)[0];
                if (ledgeId < 0) {
                    chosen = spot2;
                    break;
                } else if (BotSpotClaims.claim(mapId, ledgeId, CAPACITY_PER_LEDGE, botId) < 0) {
                    i2++;
                } else {
                    ACTIVE.put(Integer.valueOf(botId), new Claim(mapId, ledgeId));
                    chosen = spot2;
                    break;
                }
            }
        }
        if (chosen == null) {
            return;
        }
        GCMovement.move(bot, chosen.x, chosen.y);
        GCMovement.setFidget(bot, fidget);
    }

    public static void stop(Character bot) {
        if (bot == null) {
            return;
        }
        GCMovement.setFidget(bot, false);
        synchronized (CLAIM_LOCK) {
            releaseLocked(bot.getId());
        }
    }

    private static void releaseLocked(int botId) {
        Claim c = ACTIVE.remove(Integer.valueOf(botId));
        if (c != null) {
            BotSpotClaims.release(c.mapId, c.ledgeId, botId);
        }
    }

    public static boolean isLoitering(Character bot) {
        return bot != null && ACTIVE.containsKey(Integer.valueOf(bot.getId()));
    }
}
