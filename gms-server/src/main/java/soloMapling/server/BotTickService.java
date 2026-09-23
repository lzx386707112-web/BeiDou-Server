package soloMapling.server;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.gms.net.server.Server;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/server/BotTickService.class */
public final class BotTickService {
    private static final long DRIVER_PERIOD_MS = 250;
    private static final long GOVERNOR_WINDOW_MS = 5000;
    private static final long LAG_HI_MS = 1000;
    private static final long LAG_LO_MS = 300;
    private static final double FACTOR_MAX = 4.0d;
    private static final double FACTOR_STEP = 1.5d;
    private static final Map<Integer, Entry> ENTRIES = new ConcurrentHashMap();
    private static final AtomicBoolean DRIVER_STARTED = new AtomicBoolean(false);
    private static volatile double throttleFactor = 1.0d;
    private static long governorWindowStartMs = 0;
    private static long windowLagSumMs = 0;
    private static long windowDispatches = 0;
    private static volatile ScheduledFuture<?> driverTask = null;

    private BotTickService() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/server/BotTickService$Entry.class */
    private static final class Entry {
        final Runnable tick;
        volatile long periodMs;
        volatile long nextDueMs;
        volatile long pendingDueMs;
        volatile boolean noThrottle;
        final AtomicBoolean ticking = new AtomicBoolean(false);

        Entry(Runnable tick, long periodMs, long nextDueMs) {
            this.tick = tick;
            this.periodMs = periodMs;
            this.nextDueMs = nextDueMs;
        }
    }

    public static double throttleFactor() {
        return throttleFactor;
    }

    public static void register(int botId, Runnable tick, long initialDelayMs, long periodMs) {
        ensureDriver();
        ENTRIES.putIfAbsent(Integer.valueOf(botId), new Entry(tick, periodMs, System.currentTimeMillis() + initialDelayMs));
    }

    public static void unregister(int botId) {
        ENTRIES.remove(Integer.valueOf(botId));
    }

    public static boolean isRegistered(int botId) {
        return ENTRIES.containsKey(Integer.valueOf(botId));
    }

    public static void setNoThrottle(int botId, boolean on) {
        Entry e = ENTRIES.get(Integer.valueOf(botId));
        if (e != null) {
            e.noThrottle = on;
        }
    }

    public static int size() {
        return ENTRIES.size();
    }

    public static void reschedule(int botId, long periodMs) {
        Entry e = ENTRIES.get(Integer.valueOf(botId));
        if (e == null) {
            return;
        }
        e.periodMs = periodMs;
        requestFireAt(e, System.currentTimeMillis() + periodMs);
    }

    public static void nudge(int botId, long initialDelayMs, long periodMs) {
        Entry e = ENTRIES.get(Integer.valueOf(botId));
        if (e == null) {
            return;
        }
        e.periodMs = periodMs;
        requestFireAt(e, System.currentTimeMillis() + initialDelayMs);
    }

    private static void requestFireAt(Entry e, long at) {
        e.pendingDueMs = at;
        if (e.nextDueMs != Long.MAX_VALUE) {
            e.nextDueMs = at;
        }
    }

    private static void ensureDriver() {
        if (!DRIVER_STARTED.compareAndSet(false, true)) {
            return;
        }
        driverTask = ExecutorServiceManager.getScheduledExecutorService().scheduleWithFixedDelay(BotTickService::safeDrive, DRIVER_PERIOD_MS, DRIVER_PERIOD_MS, TimeUnit.MILLISECONDS);
    }

    public static void stop() {
        ENTRIES.clear();
        ScheduledFuture<?> task = driverTask;
        if (task != null) {
            task.cancel(false);
            driverTask = null;
        }
        DRIVER_STARTED.set(false);
    }

    private static void safeDrive() {
        try {
            drive();
        } catch (Throwable th) {
        }
    }

    private static void drive() {
        if (!isServerOperating()) {
            return;
        }
        long now = System.currentTimeMillis();
        long lagSum = 0;
        int dispatched = 0;
        for (Entry e : ENTRIES.values()) {
            if (now >= e.nextDueMs && e.ticking.compareAndSet(false, true)) {
                long lag = now - e.nextDueMs;
                e.nextDueMs = Long.MAX_VALUE;
                if (e.pendingDueMs > 0 && now >= e.pendingDueMs) {
                    e.pendingDueMs = 0L;
                }
                BotPerfStats.MOVEMENT_TICKS.increment();
                lagSum += Math.max(0L, lag);
                dispatched++;
                ExecutorServiceManager.runAsync(() -> {
                    runTick(e);
                });
            }
        }
        governorTick(now, lagSum, dispatched);
    }

    private static void governorTick(long now, long lagSumMs, int dispatches) {
        windowLagSumMs += lagSumMs;
        windowDispatches += dispatches;
        if (governorWindowStartMs == 0) {
            governorWindowStartMs = now;
            return;
        }
        if (now - governorWindowStartMs < GOVERNOR_WINDOW_MS) {
            return;
        }
        long avg = windowDispatches > 0 ? windowLagSumMs / windowDispatches : 0L;
        windowLagSumMs = 0L;
        windowDispatches = 0L;
        governorWindowStartMs = now;
        if (avg > LAG_HI_MS && throttleFactor < FACTOR_MAX) {
            throttleFactor = Math.min(FACTOR_MAX, throttleFactor * 1.5d);
            // BOTLOG-MUTE: System.out.println(String.format("[BotTickService] wheel lag avg %dms - stretching cadences x%.2f", Long.valueOf(avg), Double.valueOf(throttleFactor)));
        } else if (avg < LAG_LO_MS && throttleFactor > 1.0d) {
            throttleFactor = Math.max(1.0d, throttleFactor / 1.5d);
            // BOTLOG-MUTE: System.out.println(String.format("[BotTickService] wheel recovered (avg %dms) - cadence factor x%.2f", Long.valueOf(avg), Double.valueOf(throttleFactor)));
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void runTick(Entry e) {
        if (!isServerOperating()) {
            e.ticking.set(false);
            return;
        }
        try {
            e.tick.run();
            if (!isServerOperating()) {
                e.ticking.set(false);
                return;
            }
            long now = System.currentTimeMillis();
            long due = now + (e.noThrottle ? e.periodMs : (long) (e.periodMs * throttleFactor));
            long pending = e.pendingDueMs;
            if (pending > 0) {
                e.pendingDueMs = 0L;
                due = Math.min(due, Math.max(pending, now));
            }
            e.nextDueMs = due;
            e.ticking.set(false);
        } catch (Throwable th) {
            if (!isServerOperating()) {
                e.ticking.set(false);
                return;
            }
            long now2 = System.currentTimeMillis();
            long due2 = now2 + (e.noThrottle ? e.periodMs : (long) (e.periodMs * throttleFactor));
            long pending2 = e.pendingDueMs;
            if (pending2 > 0) {
                e.pendingDueMs = 0L;
                due2 = Math.min(due2, Math.max(pending2, now2));
            }
            e.nextDueMs = due2;
            e.ticking.set(false);
            throw th;
        }
    }

    private static boolean isServerOperating() {
        Server server;
        return DRIVER_STARTED.get() && (server = Server.getInstance()) != null && server.isOnline() && !server.isShuttingDown();
    }
}
