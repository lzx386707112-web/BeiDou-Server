package soloMapling.server;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

public final class BotTiming {
    private BotTiming() {
    }

    public static void afterRandom(long minMs, long maxMs, Runnable task) {
        long span = Math.max(0L, maxMs - minMs);
        long delay = minMs + (span == 0 ? 0 : ThreadLocalRandom.current().nextLong(span + 1));
        ExecutorServiceManager.getScheduledExecutorService().schedule(task, delay, TimeUnit.MILLISECONDS);
    }

    public static Chain chain() {
        return new Chain();
    }

    public static final class Chain {
        private final List<Runnable> steps = new ArrayList<>();
        private BooleanSupplier keepGoing = () -> true;

        public Chain stopUnless(BooleanSupplier keepGoing) {
            if (keepGoing != null) {
                this.keepGoing = keepGoing;
            }
            return this;
        }

        public Chain pause(long ms) {
            steps.add(() -> {
                try {
                    Thread.sleep(Math.max(0L, ms));
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                }
            });
            return this;
        }

        public Chain pauseRandom(long minMs, long maxMs) {
            long span = Math.max(0L, maxMs - minMs);
            long delay = minMs + (span == 0 ? 0 : ThreadLocalRandom.current().nextLong(span + 1));
            return pause(delay);
        }

        public Chain run(Runnable task) {
            if (task != null) {
                steps.add(task);
            }
            return this;
        }

        public void start() {
            ExecutorServiceManager.runAsync(() -> {
                for (Runnable step : steps) {
                    if (!keepGoing.getAsBoolean()) {
                        return;
                    }
                    step.run();
                }
            });
        }
    }
}
