package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/CoarseExecutor.class */
final class CoarseExecutor {
    private CoarseExecutor() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/CoarseExecutor$Step.class */
    static final class Step {
        private final Point position;
        private final boolean complete;

        Step(Point position, boolean complete) {
            this.position = position;
            this.complete = complete;
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

        public Point position() {
            return this.position;
        }

        public boolean complete() {
            return this.complete;
        }
    }

    static Step advance(MovementPlan plan, long planStartedAtMs, long nowMs) {
        long elapsed = Math.max(0L, nowMs - planStartedAtMs);
        return new Step(plan.positionAt(elapsed), plan.isComplete(elapsed));
    }
}
