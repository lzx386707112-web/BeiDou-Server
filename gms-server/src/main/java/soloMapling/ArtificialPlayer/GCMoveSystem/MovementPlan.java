package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.List;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationGraph;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/MovementPlan.class */
final class MovementPlan {
    final Kind kind;
    final int mapId;
    final List<BotNavigationGraph.Edge> edges;
    private final long[] cumStartMs;
    final long totalTimeMs;

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/MovementPlan$Kind.class */
    enum Kind {
        IN_MAP,
        CROSS_MAP
    }

    private MovementPlan(Kind kind, int mapId, List<BotNavigationGraph.Edge> edges, long[] cumStartMs, long totalTimeMs) {
        this.kind = kind;
        this.mapId = mapId;
        this.edges = edges;
        this.cumStartMs = cumStartMs;
        this.totalTimeMs = totalTimeMs;
    }

    static MovementPlan inMap(int mapId, List<BotNavigationGraph.Edge> edges) {
        if (edges == null || edges.isEmpty()) {
            return null;
        }
        long[] cumStart = new long[edges.size()];
        long acc = 0;
        for (int i = 0; i < edges.size(); i++) {
            cumStart[i] = acc;
            acc += Math.max(0, edges.get(i).cost);
        }
        return new MovementPlan(Kind.IN_MAP, mapId, List.copyOf(edges), cumStart, acc);
    }

    static MovementPlan inMap(BotNavigationGraph graph, MapleMap map, Point startPos, Point targetPos) {
        if (graph == null || map == null || startPos == null || targetPos == null) {
            return null;
        }
        int startRegion = graph.findRegionId(map, startPos);
        int targetRegion = graph.findRegionId(map, targetPos);
        if (startRegion < 0 || targetRegion < 0) {
            return null;
        }
        List<BotNavigationGraph.Edge> edges = BotNavigationManager.findPath(graph, map, startPos, startRegion, targetRegion, targetPos);
        return inMap(map.getId(), edges);
    }

    boolean isComplete(long elapsedMs) {
        return elapsedMs >= this.totalTimeMs;
    }

    Point positionAt(long elapsedMs) {
        if (this.edges.isEmpty()) {
            return null;
        }
        if (elapsedMs <= 0) {
            return new Point(this.edges.get(0).startPoint);
        }
        if (elapsedMs >= this.totalTimeMs) {
            return new Point(this.edges.get(this.edges.size() - 1).endPoint);
        }
        int i = edgeIndexAt(elapsedMs);
        BotNavigationGraph.Edge e = this.edges.get(i);
        long into = elapsedMs - this.cumStartMs[i];
        long dur = Math.max(1, e.cost);
        double t = Math.min(1.0d, into / dur);
        int x = (int) Math.round(e.startPoint.x + ((e.endPoint.x - e.startPoint.x) * t));
        int y = (int) Math.round(e.startPoint.y + ((e.endPoint.y - e.startPoint.y) * t));
        return new Point(x, y);
    }

    int edgeIndexAt(long elapsedMs) {
        int idx = 0;
        for (int i = 0; i < this.edges.size() && elapsedMs >= this.cumStartMs[i]; i++) {
            idx = i;
        }
        return idx;
    }
}
