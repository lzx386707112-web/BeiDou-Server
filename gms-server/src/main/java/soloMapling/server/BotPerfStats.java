package soloMapling.server;

public final class BotPerfStats {
    public static final Counter MOVEMENT_TICKS = new Counter();

    private BotPerfStats() {
    }

    public static final class Counter {
        public void increment() {
        }
    }
}
