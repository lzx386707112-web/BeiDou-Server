package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/TierDwell.class */
final class TierDwell {
    private final long dwellMs;
    private final Map<Integer, Long> stickyUntil = new HashMap();
    private volatile Set<Integer> active = Set.of();

    TierDwell(long dwellMs) {
        this.dwellMs = dwellMs;
    }

    void observe(Set<Integer> observed, long nowMs) {
        long deadline = nowMs + this.dwellMs;
        Iterator<Integer> it = observed.iterator();
        while (it.hasNext()) {
            int mapId = it.next().intValue();
            this.stickyUntil.put(Integer.valueOf(mapId), Long.valueOf(deadline));
        }
        this.stickyUntil.entrySet().removeIf(e -> {
            return ((Long) e.getValue()).longValue() <= nowMs;
        });
        this.active = this.stickyUntil.isEmpty() ? Set.of() : Set.copyOf(this.stickyUntil.keySet());
    }

    boolean isActive(int mapId) {
        return this.active.contains(Integer.valueOf(mapId));
    }

    Set<Integer> active() {
        return this.active;
    }

    int size() {
        return this.active.size();
    }
}
