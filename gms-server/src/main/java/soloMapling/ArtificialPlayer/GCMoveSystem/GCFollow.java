package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import org.gms.client.Character;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCFollow.class */
final class GCFollow {
    private static final long POLL_MS = 400;
    private static final ScheduledExecutorService POOL = Executors.newScheduledThreadPool(1, r -> {
        Thread t = new Thread(r, "gcfollow-poll");
        t.setDaemon(true);
        return t;
    });
    private static final Map<Integer, Session> SESSIONS = new ConcurrentHashMap();

    private GCFollow() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCFollow$Session.class */
    private static final class Session {
        final Character bot;
        final Character target;
        ScheduledFuture<?> task;
        int travelDest = -1;

        Session(Character bot, Character target) {
            this.bot = bot;
            this.target = target;
        }
    }

    static void start(Character bot, Character target) {
        if (bot == null || target == null) {
            return;
        }
        cancel(bot);
        GCMovement.enable(bot);
        Session s = new Session(bot, target);
        s.task = POOL.scheduleAtFixedRate(() -> {
            try {
                tick(s);
            } catch (Throwable th) {
            }
        }, 0L, POLL_MS, TimeUnit.MILLISECONDS);
        SESSIONS.put(Integer.valueOf(bot.getId()), s);
    }

    static void cancel(Character bot) {
        Session s;
        if (bot != null && (s = SESSIONS.remove(Integer.valueOf(bot.getId()))) != null && s.task != null) {
            s.task.cancel(false);
        }
    }

    static boolean isFollowing(Character bot) {
        return bot != null && SESSIONS.containsKey(Integer.valueOf(bot.getId()));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void tick(Session s) {
        Character bot = s.bot;
        Character target = s.target;
        if (bot == null || bot.getMap() == null || target == null || target.getMap() == null) {
            GCMovement.endFollowState(bot);
            cancel(bot);
            return;
        }
        if (bot.getMapId() == target.getMapId()) {
            if (GCMovement.isTraveling(bot)) {
                GCTravel.cancel(bot);
            }
            s.travelDest = -1;
            GCMovement.armSameMapFollow(bot, target);
            return;
        }
        GCMovement.pauseFollowForTravel(bot);
        int destMap = target.getMapId();
        if (s.travelDest == destMap) {
            return;
        }
        GCTravel.cancel(bot);
        s.travelDest = destMap;
        GCTravel.warp(bot, destMap, "follow leader without world-graph scan");
    }
}
