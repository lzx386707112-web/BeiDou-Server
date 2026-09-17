package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.gms.server.life.NPC;
import org.gms.server.maps.MapleMap;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCTaxi.class */
final class GCTaxi {
    private static final int[][] VICTORIA_CABS = {new int[]{104000000, 1002007}, new int[]{100000000, 1012000}, new int[]{102000000, 1022001}, new int[]{101000000, 1032000}, new int[]{103000000, 1052016}, new int[]{120000000, 1092014}};
    private static final Map<Integer, List<TaxiEdge>> BY_FROM = buildEdges();

    private GCTaxi() {
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCTaxi$TaxiEdge.class */
    static final class TaxiEdge {
        private final int fromMapId;
        private final int npcId;
        private final int toMapId;

        TaxiEdge(int fromMapId, int npcId, int toMapId) {
            this.fromMapId = fromMapId;
            this.npcId = npcId;
            this.toMapId = toMapId;
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

        public int fromMapId() {
            return this.fromMapId;
        }

        public int npcId() {
            return this.npcId;
        }

        public int toMapId() {
            return this.toMapId;
        }
    }

    private static Map<Integer, List<TaxiEdge>> buildEdges() {
        Map<Integer, List<TaxiEdge>> byFrom = new HashMap<>();
        for (int[] from : VICTORIA_CABS) {
            if (true) {
                List<TaxiEdge> edges = new ArrayList<>();
                for (int[] to : VICTORIA_CABS) {
                    if (from[0] != to[0] && true) {
                        edges.add(new TaxiEdge(from[0], from[1], to[0]));
                    }
                }
                byFrom.put(Integer.valueOf(from[0]), List.copyOf(edges));
            }
        }
        return Map.copyOf(byFrom);
    }

    static List<TaxiEdge> from(int mapId) {
        return BY_FROM.getOrDefault(Integer.valueOf(mapId), List.of());
    }

    static TaxiEdge edge(int fromMapId, int toMapId) {
        for (TaxiEdge e : from(fromMapId)) {
            if (e.toMapId() == toMapId) {
                return e;
            }
        }
        return null;
    }

    static int[] destinations(int mapId) {
        List<TaxiEdge> edges = from(mapId);
        int[] dests = new int[edges.size()];
        for (int i = 0; i < edges.size(); i++) {
            dests[i] = edges.get(i).toMapId();
        }
        return dests;
    }

    static Point npcPos(MapleMap map, int npcId) {
        NPC npc;
        if (map == null || (npc = map.getNPCById(npcId)) == null) {
            return null;
        }
        return npc.getPosition();
    }
}
