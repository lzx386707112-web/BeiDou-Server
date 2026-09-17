package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import org.gms.client.Character;
import soloMapling.ArtificialPlayer.BotAttackSystem.BotAttackData;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCFidget.class */
final class GCFidget {
    private static final long POLL_MS = 1500;
    private static final long MIN_REST_MS = 5000;
    private static final long MAX_REST_MS = 14000;
    private static final int WANDER_PX = 45;
    private static final int RETURN_DIST = 70;
    private static final int DUCK_MIN_MS = 900;
    private static final int DUCK_MAX_MS = 1900;
    private static final ScheduledExecutorService POOL = Executors.newScheduledThreadPool(1, r -> {
        Thread t = new Thread(r, "gcfidget-poll");
        t.setDaemon(true);
        return t;
    });
    private static final Map<Integer, Session> SESSIONS = new ConcurrentHashMap();

    private GCFidget() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCFidget$Session.class */
    private static final class Session {
        final Character bot;
        ScheduledFuture<?> task;
        Point base;
        long nextActionAtMs;
        boolean fidgetMoveActive;

        Session(Character bot) {
            this.bot = bot;
        }
    }

    static void start(Character bot) {
        if (bot == null) {
            return;
        }
        cancel(bot);
        Session s = new Session(bot);
        s.task = POOL.scheduleAtFixedRate(() -> {
            try {
                tick(s);
            } catch (Throwable th) {
            }
        }, POLL_MS, POLL_MS, TimeUnit.MILLISECONDS);
        SESSIONS.put(Integer.valueOf(bot.getId()), s);
    }

    static void cancel(Character bot) {
        Session s;
        if (bot != null && (s = SESSIONS.remove(Integer.valueOf(bot.getId()))) != null && s.task != null) {
            s.task.cancel(false);
        }
    }

    static boolean isActive(Character bot) {
        return bot != null && SESSIONS.containsKey(Integer.valueOf(bot.getId()));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void tick(Session s) {
        Character bot = s.bot;
        if (bot == null || bot.getMap() == null || !GCMovement.isEnabled(bot)) {
            cancel(bot);
            return;
        }
        boolean busy = GCMovement.isMoving(bot) || GCMovement.isTraveling(bot) || GCMovement.isFollowing(bot);
        if (busy && !s.fidgetMoveActive) {
            s.base = null;
        }
        if (busy) {
            return;
        }
        s.fidgetMoveActive = false;
        Point pos = bot.getPosition();
        if (s.base == null) {
            s.base = new Point(pos);
        }
        long now = System.currentTimeMillis();
        if (now < s.nextActionAtMs) {
            return;
        }
        s.nextActionAtMs = now + ThreadLocalRandom.current().nextLong(MIN_REST_MS, MAX_REST_MS);
        if (Math.abs(pos.x - s.base.x) + Math.abs(pos.y - s.base.y) > RETURN_DIST) {
            GCMovement.nudgeTo(bot, s.base.x, s.base.y);
            s.fidgetMoveActive = true;
            return;
        }
        switch (ThreadLocalRandom.current().nextInt(4)) {
            case BotAttackData.FACING_RIGHT_MASK /* 0 */:
                GCMovement.turnAround(bot);
                break;
            case 1:
                GCMovement.duck(bot, ThreadLocalRandom.current().nextInt(DUCK_MIN_MS, DUCK_MAX_MS));
                break;
            case 2:
                GCMovement.jumpInPlace(bot);
                break;
            default:
                int dx = ThreadLocalRandom.current().nextInt(-45, 46);
                GCMovement.nudgeTo(bot, s.base.x + dx, s.base.y);
                s.fidgetMoveActive = true;
                break;
        }
    }
}
