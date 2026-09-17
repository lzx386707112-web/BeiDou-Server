package soloMapling.ArtificialPlayer.BotWanderSystem;

import java.awt.Point;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotGrindSystem.BotSpotPicker;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

public final class BotWanderSystem {
    private static final int POLL_MS = 400;
    private static final int MIN_STROLL = 60;
    private static final int STROLL_ATTEMPTS = 6;
    private static final int ARRIVE_X = 25;
    private static final int ARRIVE_Y = 60;
    private static final int PROGRESS_EPS = 12;
    private static final long STUCK_MS = 6000;
    private static final long DWELL_MIN_MS = 2500;
    private static final long DWELL_MAX_MS = 6000;
    private static final int START_JITTER_MS = 1500;
    private static final double EDGE_MARGIN_PCT = 0.075d;
    private static final int EDGE_MARGIN_MIN_PX = 30;
    private static final byte WALKING = 0;
    private static final byte DWELLING = 1;
    private static final Random RANDOM = new Random();
    private static final AtomicInteger THREAD_SEQ = new AtomicInteger();
    private static final ScheduledExecutorService POOL = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "bot-wander-" + THREAD_SEQ.getAndIncrement());
        t.setDaemon(true);
        return t;
    });
    private static final Map<Integer, Wander> WANDERS = new ConcurrentHashMap<>();

    private BotWanderSystem() {
    }

    private static final class Wander {
        final Character bot;
        final int mapId;
        final boolean banded;
        final int bandLo;
        final int bandHi;
        ScheduledFuture<?> task;
        long dwellUntilMs;
        Point target;
        long progressAtMs;
        byte state = DWELLING;
        int bestDist = Integer.MAX_VALUE;

        Wander(Character bot, int mapId, boolean banded, int bandLo, int bandHi) {
            this.bot = bot;
            this.mapId = mapId;
            this.banded = banded;
            this.bandLo = bandLo;
            this.bandHi = bandHi;
        }
    }

    public static void start(Character bot) {
        startWholeMap(bot);
    }

    public static void start(Character bot, int anchorX, int radius) {
        if (radius <= 0) {
            startWholeMap(bot);
        } else {
            startInternal(bot, true, anchorX - radius, anchorX + radius);
        }
    }

    private static void startWholeMap(Character bot) {
        if (bot == null || bot.getMap() == null) {
            startInternal(bot, false, 0, 0);
            return;
        }
        int[] band = trimmedBand(bot.getMap(), bot.getPosition());
        if (band == null) {
            startInternal(bot, false, 0, 0);
        } else {
            startInternal(bot, true, band[0], band[1]);
        }
    }

    private static int[] trimmedBand(MapleMap map, Point from) {
        List<GCMovement.Ledge> ledges = GCMovement.walkableLedges(map);
        if (ledges.isEmpty()) {
            return null;
        }
        Set<Integer> reachable = from != null ? GCMovement.reachableRegions(map, from.x, from.y) : Set.of();
        boolean filter = !reachable.isEmpty();
        int min = Integer.MAX_VALUE;
        int max = Integer.MIN_VALUE;
        for (GCMovement.Ledge l : ledges) {
            if (!filter || reachable.contains(l.regionId())) {
                min = Math.min(min, l.minX());
                max = Math.max(max, l.maxX());
            }
        }
        if (max <= min) {
            return null;
        }
        int inset = Math.max(EDGE_MARGIN_MIN_PX, (int) (EDGE_MARGIN_PCT * (max - min)));
        int lo = min + inset;
        int hi = max - inset;
        if (hi > lo) {
            return new int[]{lo, hi};
        }
        return null;
    }

    public static void stop(Character bot) {
        if (bot == null) {
            return;
        }
        Wander w = WANDERS.remove(bot.getId());
        if (w != null && w.task != null) {
            w.task.cancel(false);
        }
    }

    public static boolean isWandering(Character bot) {
        return bot != null && WANDERS.containsKey(bot.getId());
    }

    private static void startInternal(Character bot, boolean banded, int bandLo, int bandHi) {
        if (bot == null || bot.getMap() == null) {
            return;
        }
        stop(bot);
        GCMovement.enable(bot);
        Wander w = new Wander(bot, bot.getMapId(), banded, bandLo, bandHi);
        w.progressAtMs = System.currentTimeMillis();
        long initialDelay = RANDOM.nextInt(START_JITTER_MS);
        w.task = POOL.scheduleAtFixedRate(() -> {
            try {
                tick(w);
            } catch (Throwable ignored) {
            }
        }, initialDelay, POLL_MS, TimeUnit.MILLISECONDS);
        WANDERS.put(bot.getId(), w);
    }

    private static void tick(Wander w) {
        Character bot = w.bot;
        if (bot == null || WANDERS.get(bot.getId()) != w) {
            return;
        }
        if (bot.getMap() == null || bot.getMapId() != w.mapId) {
            stop(bot);
            return;
        }
        if (!GCMovement.isMapObserved(bot.getMapId())) {
            return;
        }
        MapleMap map = bot.getMap();
        Point bp = bot.getPosition();
        long now = System.currentTimeMillis();
        if (w.state == DWELLING) {
            if (now < w.dwellUntilMs) {
                return;
            }
            Point spot = pickStroll(map, bp, w);
            if (spot == null) {
                w.dwellUntilMs = now + DWELL_MIN_MS;
                return;
            }
            issueMove(w, spot, now);
            return;
        }
        if (w.target == null) {
            w.state = DWELLING;
            w.dwellUntilMs = now + DWELL_MIN_MS;
            return;
        }
        int dx = Math.abs(bp.x - w.target.x);
        int dy = Math.abs(bp.y - w.target.y);
        if (dx <= ARRIVE_X && dy <= ARRIVE_Y && !GCMovement.isMoving(bot)) {
            w.state = DWELLING;
            w.dwellUntilMs = now + DWELL_MIN_MS + (long) (RANDOM.nextDouble() * (DWELL_MAX_MS - DWELL_MIN_MS));
            return;
        }
        int dist = dx + dy;
        if (dist < w.bestDist - PROGRESS_EPS) {
            w.bestDist = dist;
            w.progressAtMs = now;
        } else if (now - w.progressAtMs > STUCK_MS) {
            Point spot2 = pickStroll(map, bp, w);
            if (spot2 != null) {
                issueMove(w, spot2, now);
                return;
            }
            w.state = DWELLING;
            w.dwellUntilMs = now + DWELL_MIN_MS;
            return;
        }
        if (!GCMovement.isMoving(bot)) {
            GCMovement.move(bot, w.target.x, w.target.y);
        }
    }

    private static Point pickStroll(MapleMap map, Point from, Wander w) {
        Point last = null;
        for (int i = 0; i < STROLL_ATTEMPTS; i++) {
            Point p = w.banded
                    ? BotSpotPicker.pickGroundSpot(map, from.x, from.y, w.bandLo, w.bandHi)
                    : BotSpotPicker.pickGroundSpot(map, from.x, from.y);
            if (p == null) {
                return last;
            }
            last = p;
            if (Math.abs(p.x - from.x) >= MIN_STROLL) {
                return p;
            }
        }
        return last;
    }

    private static void issueMove(Wander w, Point spot, long now) {
        w.target = spot;
        w.state = WALKING;
        w.bestDist = Integer.MAX_VALUE;
        w.progressAtMs = now;
        GCMovement.move(w.bot, spot.x, spot.y);
    }
}
