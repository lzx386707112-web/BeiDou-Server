package soloMapling.ArtificialPlayer.BotTownSystem;

import java.awt.Point;
import java.util.List;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownOverrides.class */
public final class TownOverrides {
    public static final TownOverrides EMPTY = new TownOverrides(List.of(), List.of(), List.of());
    private final List<Zone> ban;
    private final List<Zone> boost;
    private final List<Point> pins;

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownOverrides$Zone.class */
    public static final class Zone {
        private final int x1;
        private final int y1;
        private final int x2;
        private final int y2;
        private final double mult;

        public Zone(int x1, int y1, int x2, int y2, double mult) {
            this.x1 = x1;
            this.y1 = y1;
            this.x2 = x2;
            this.y2 = y2;
            this.mult = mult;
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

        public int x1() {
            return this.x1;
        }

        public int y1() {
            return this.y1;
        }

        public int x2() {
            return this.x2;
        }

        public int y2() {
            return this.y2;
        }

        public double mult() {
            return this.mult;
        }

        public boolean contains(int x, int y) {
            return x >= Math.min(this.x1, this.x2) && x <= Math.max(this.x1, this.x2) && y >= Math.min(this.y1, this.y2) && y <= Math.max(this.y1, this.y2);
        }
    }

    public TownOverrides(List<Zone> ban, List<Zone> boost, List<Point> pins) {
        this.ban = ban;
        this.boost = boost;
        this.pins = pins;
    }

    public List<Point> pins() {
        return this.pins;
    }

    public boolean isEmpty() {
        return this.ban.isEmpty() && this.boost.isEmpty() && this.pins.isEmpty();
    }

    public boolean isBanned(int x, int y) {
        for (Zone z : this.ban) {
            if (z.contains(x, y)) {
                return true;
            }
        }
        return false;
    }

    public double boostMultiplier(int x, int y) {
        double m = 1.0d;
        for (Zone z : this.boost) {
            if (z.contains(x, y)) {
                m *= z.mult();
            }
        }
        return m;
    }
}
