package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import soloMapling.ArtificialPlayer.BotTravelSystem.BotScriptedWarp;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCTaxi;
import soloMapling.BotLogger;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCTravel.class */
final class GCTravel {
    private static final int MAX_HOPS = 20;
    private static final int POLL_MS = 300;
    private static final int ENTER_X = 35;
    private static final int ENTER_Y = 100;
    private static final long HOP_STUCK_MS = 12000;
    private static final int HOP_PROGRESS_EPS_PX = 16;
    private static final int HOP_MOVE_EPS_PX = 16;
    private static final long PORTAL_ENTER_DWELL_MS = 350;
    private static final int SNAP_ENTER_RADIUS_PX = 100;
    private static final long SNAP_ENTER_MS = 1200;
    private static final long SNAP_NEAR_GRACE_MS = 1500;
    private static final int SOFT_LOCK_SPAN_PX = 400;
    private static final long SOFT_LOCK_MS = 20000;
    private static final long HOP_MAX_MS = 90000;
    private static final ScheduledExecutorService POOL = Executors.newScheduledThreadPool(2, r -> {
        Thread t = new Thread(r, "gctravel-poll");
        t.setDaemon(true);
        return t;
    });
    private static final Map<Integer, Trip> TRIPS = new ConcurrentHashMap();

    private GCTravel() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCTravel$Trip.class */
    private static final class Trip {
        final Character bot;
        final int destMapId;
        final Consumer<Boolean> callback;
        ScheduledFuture<?> task;
        long settledAtMs;
        long hopProgressAtMs;
        long nearTargetSinceMs;
        long lastNearTargetAtMs;
        int softMinX;
        int softMaxX;
        int softMinY;
        int softMaxY;
        long softLockSinceMs;
        long hopStartAtMs;
        int hopBestDist = Integer.MAX_VALUE;
        int lastPosX = Integer.MIN_VALUE;
        int lastPosY = Integer.MIN_VALUE;
        int lastMapId = -1;

        Trip(Character bot, int destMapId, Consumer<Boolean> callback) {
            this.bot = bot;
            this.destMapId = destMapId;
            this.callback = callback;
        }
    }

    static void travel(Character bot, int destMapId, Consumer<Boolean> callback) {
        if (bot == null) {
            return;
        }
        cancel(bot);
        if (bot.getMap() != null && bot.getMapId() == destMapId) {
            fire(callback, true);
            return;
        }
        GCMovement.enable(bot);
        Trip trip = new Trip(bot, destMapId, callback);
        trip.hopProgressAtMs = nowMs();
        trip.hopStartAtMs = nowMs();
        trip.task = POOL.scheduleAtFixedRate(() -> {
            try {
                tick(trip);
            } catch (Throwable th) {
            }
        }, 0L, 300L, TimeUnit.MILLISECONDS);
        TRIPS.put(Integer.valueOf(bot.getId()), trip);
    }

    static void cancel(Character bot) {
        Trip t;
        if (bot != null && (t = TRIPS.remove(Integer.valueOf(bot.getId()))) != null && t.task != null) {
            t.task.cancel(false);
        }
    }

    static boolean isTraveling(Character bot) {
        return bot != null && TRIPS.containsKey(Integer.valueOf(bot.getId()));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void tick(Trip trip) {
        Character bot = trip.bot;
        if (bot == null || bot.getMap() == null) {
            finish(trip, false);
            return;
        }
        int cur = bot.getMapId();
        if (cur == trip.destMapId) {
            finish(trip, true);
            return;
        }
        if (cur != trip.lastMapId) {
            trip.lastMapId = cur;
            trip.settledAtMs = 0L;
            trip.hopBestDist = Integer.MAX_VALUE;
            trip.lastPosX = Integer.MIN_VALUE;
            trip.lastPosY = Integer.MIN_VALUE;
            trip.hopProgressAtMs = nowMs();
            trip.nearTargetSinceMs = 0L;
            trip.softLockSinceMs = 0L;
            trip.hopStartAtMs = nowMs();
            GCMovement.clearMoveIntent(bot);
        }
        List<Integer> route = GCWorldGraph.route(cur, trip.destMapId, MAX_HOPS);
        if (route == null) {
            warp(bot, trip.destMapId, "no walkable portal route to " + trip.destMapId);
            return;
        }
        if (route.isEmpty()) {
            finish(trip, true);
            return;
        }
        int nextHop = route.get(0).intValue();
        Portal portal = findPortalTo(bot.getMap(), nextHop);
        if (portal != null) {
            approachAndAct(trip, bot, portal.getPosition(), nextHop, "portal " + portal.getId() + " -> map " + nextHop, () -> {
                GCPortals.enter(bot, portal);
            });
            return;
        }
        GCTaxi.TaxiEdge taxi = GCTaxi.edge(cur, nextHop);
        if (taxi != null) {
            Point npcPos = GCTaxi.npcPos(bot.getMap(), taxi.npcId());
            if (npcPos == null) {
                warp(bot, nextHop, "taxi npc " + taxi.npcId() + " not on map " + cur);
                return;
            } else {
                approachAndAct(trip, bot, npcPos, nextHop, "taxi npc " + taxi.npcId() + " -> map " + nextHop, () -> {
                    warp(bot, nextHop, "taxi ride " + cur + " -> " + nextHop);
                });
                return;
            }
        }
        BotScriptedWarp.WarpEdge sw = BotScriptedWarp.edge(cur, nextHop);
        if (sw != null) {
            Point trigger = BotScriptedWarp.portalPos(bot.getMap(), sw.portalName());
            if (trigger == null) {
                warp(bot, nextHop, "scripted portal '" + sw.portalName() + "' not on map " + cur);
                return;
            } else {
                approachAndAct(trip, bot, trigger, nextHop, "scripted portal '" + sw.portalName() + "' -> map " + nextHop, () -> {
                    warpToPortal(bot, sw.toMapId(), sw.toPortalId(), "scripted warp " + cur + " -> " + nextHop);
                });
                return;
            }
        }
        warp(bot, nextHop, "no walkable portal/taxi/scripted-warp on map " + cur + " to " + nextHop);
    }

    private static void approachAndAct(Trip trip, Character bot, Point dest, int nextHop, String intent, Runnable action) {
        Point bp = bot.getPosition();
        long now = nowMs();
        if (now - trip.hopStartAtMs >= HOP_MAX_MS) {
            warp(bot, nextHop, "HOP-CEILING: hop 90s old on map " + bot.getMapId() + " at (" + bp.x + "," + bp.y + "), intent: " + intent);
            return;
        }
        long sdx = bp.x - dest.x;
        long sdy = bp.y - dest.y;
        boolean nearTarget = (sdx * sdx) + (sdy * sdy) <= 10000;
        if (nearTarget) {
            trip.lastNearTargetAtMs = now;
            if (trip.nearTargetSinceMs == 0) {
                trip.nearTargetSinceMs = now;
            }
        } else if (trip.nearTargetSinceMs != 0 && now - trip.lastNearTargetAtMs > SNAP_NEAR_GRACE_MS) {
            trip.nearTargetSinceMs = 0L;
        }
        boolean atDest = Math.abs(bp.x - dest.x) <= ENTER_X && Math.abs(bp.y - dest.y) <= 100;
        boolean settled = atDest && !GCMovement.isMoving(bot);
        if (settled) {
            if (trip.settledAtMs == 0) {
                trip.settledAtMs = now;
                return;
            } else {
                if (now - trip.settledAtMs >= PORTAL_ENTER_DWELL_MS) {
                    action.run();
                    return;
                }
                return;
            }
        }
        trip.settledAtMs = 0L;
        if (nearTarget && now - trip.nearTargetSinceMs >= SNAP_ENTER_MS) {
            action.run();
            return;
        }
        if (trip.softLockSinceMs == 0) {
            trip.softLockSinceMs = now;
            trip.softMinX = bp.x;
            trip.softMaxX = bp.x;
            trip.softMinY = bp.y;
            trip.softMaxY = bp.y;
        } else {
            trip.softMinX = Math.min(trip.softMinX, bp.x);
            trip.softMaxX = Math.max(trip.softMaxX, bp.x);
            trip.softMinY = Math.min(trip.softMinY, bp.y);
            trip.softMaxY = Math.max(trip.softMaxY, bp.y);
            if (trip.softMaxX - trip.softMinX > SOFT_LOCK_SPAN_PX || trip.softMaxY - trip.softMinY > SOFT_LOCK_SPAN_PX) {
                trip.softLockSinceMs = now;
                trip.softMinX = bp.x;
                trip.softMaxX = bp.x;
                trip.softMinY = bp.y;
                trip.softMaxY = bp.y;
            } else if (now - trip.softLockSinceMs >= SOFT_LOCK_MS) {
                warp(bot, nextHop, "SOFT-LOCK: confined to " + (trip.softMaxX - trip.softMinX) + "x" + (trip.softMaxY - trip.softMinY) + "px for 20s on map " + bot.getMapId() + " at (" + bp.x + "," + bp.y + "), intent: " + intent);
                return;
            }
        }
        int dist = Math.abs(bp.x - dest.x) + Math.abs(bp.y - dest.y);
        boolean closingIn = dist < trip.hopBestDist - 16;
        boolean moved = trip.lastPosX == Integer.MIN_VALUE || Math.abs(bp.x - trip.lastPosX) + Math.abs(bp.y - trip.lastPosY) > 16;
        if (closingIn || moved) {
            if (closingIn) {
                trip.hopBestDist = dist;
            }
            trip.lastPosX = bp.x;
            trip.lastPosY = bp.y;
            trip.hopProgressAtMs = now;
        } else if (now - trip.hopProgressAtMs > HOP_STUCK_MS) {
            warp(bot, nextHop, "stuck 12s — not moving toward hop target on map " + bot.getMapId());
            return;
        }
        if (!GCMovement.isMoving(bot)) {
            GCMovement.move(bot, dest.x, dest.y);
        }
    }

    private static Portal findPortalTo(MapleMap map, int targetMapId) {
        for (Portal p : map.getPortals()) {
            if (p.getTargetMapId() == targetMapId) {
                return p;
            }
        }
        return null;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void warp(Character bot, int mapId, String reason) {
        BotLogger.log("[GCTravel] " + bot.getName() + " warped to map " + mapId + " — " + reason);
        try {
            bot.changeMap(mapId);
        } catch (Throwable th) {
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void warpToPortal(Character bot, int mapId, int portalId, String reason) {
        BotLogger.log("[GCTravel] " + bot.getName() + " warped to map " + mapId + " portal " + portalId + " — " + reason);
        try {
            bot.changeMap(mapId, Integer.valueOf(portalId));
        } catch (Throwable th) {
        }
    }

    private static void finish(Trip trip, boolean ok) {
        TRIPS.remove(Integer.valueOf(trip.bot.getId()));
        if (trip.task != null) {
            trip.task.cancel(false);
        }
        GCMovement.clearMoveIntent(trip.bot);
        fire(trip.callback, ok);
    }

    private static void fire(Consumer<Boolean> cb, boolean ok) {
        if (cb != null) {
            try {
                cb.accept(Boolean.valueOf(ok));
            } catch (Throwable th) {
            }
        }
    }

    private static long nowMs() {
        return System.nanoTime() / 1000000;
    }
}
