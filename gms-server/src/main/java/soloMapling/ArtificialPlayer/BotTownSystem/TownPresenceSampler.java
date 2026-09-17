package soloMapling.ArtificialPlayer.BotTownSystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import org.gms.server.maps.MapObject;
import org.gms.server.maps.MapObjectType;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownPresenceSampler.class */
public final class TownPresenceSampler {
    private static final Random RANDOM = new Random();
    private static final double NPC_STRENGTH = 1.0d;
    private static final double PORTAL_STRENGTH = 0.45d;
    private static final double SIGMA_X = 260.0d;
    private static final double SIGMA_Y = 130.0d;
    private static final double HEIGHT_DECAY = 320.0d;
    private static final double BASE_WEIGHT = 0.15d;
    private static final double TAIL_FRACTION = 0.09d;
    private static final int MIN_SPACING = 30;
    private static final int X_CANDIDATES = 7;

    private TownPresenceSampler() {
    }

    public static List<Point> sample(MapleMap map, Point anchor, int count) {
        return sample(map, anchor, count, TownOverrides.EMPTY);
    }

    public static List<Point> sample(MapleMap map, Point anchor, int count, TownOverrides overrides) {
        GCMovement.Ledge ledgeWeightedPick;
        List<Point> out = new ArrayList<>();
        if (map == null || anchor == null || count <= 0) {
            return out;
        }
        TownOverrides ov = overrides != null ? overrides : TownOverrides.EMPTY;
        for (Point pin : ov.pins()) {
            if (out.size() >= count) {
                return out;
            }
            Point ground = GCMovement.groundPointBelow(map, pin.x, pin.y);
            out.add(ground != null ? ground : new Point(pin));
        }
        int remaining = count - out.size();
        if (remaining <= 0) {
            return out;
        }
        List<GCMovement.Ledge> ledges = reachableLedges(map, anchor);
        if (ledges.isEmpty()) {
            return out;
        }
        List<Anchor> anchors = collectAnchors(map);
        double groundBandY = groundBandY(ledges);
        double[] weights = new double[ledges.size()];
        for (int i = 0; i < ledges.size(); i++) {
            weights[i] = ledgeWeight(ledges.get(i), anchors, groundBandY, ov);
        }
        Map<Integer, List<Integer>> occupiedByLedge = new HashMap<>();
        for (int i2 = 0; i2 < remaining; i2++) {
            if (RANDOM.nextDouble() < TAIL_FRACTION) {
                ledgeWeightedPick = ledges.get(RANDOM.nextInt(ledges.size()));
            } else {
                ledgeWeightedPick = weightedPick(ledges, weights);
            }
            GCMovement.Ledge l = ledgeWeightedPick;
            List<Integer> taken = occupiedByLedge.computeIfAbsent(Integer.valueOf(l.regionId()), k -> {
                return new ArrayList();
            });
            int x = pickX(l, anchors, taken, ov);
            taken.add(Integer.valueOf(x));
            Point ground2 = GCMovement.groundPointInRegion(map, l.regionId(), x);
            out.add(ground2 != null ? ground2 : new Point(x, l.centerY()));
        }
        return out;
    }

    private static List<GCMovement.Ledge> reachableLedges(MapleMap map, Point anchor) {
        List<GCMovement.Ledge> all = GCMovement.walkableLedges(map);
        if (all.isEmpty()) {
            return all;
        }
        Set<Integer> reachable = GCMovement.reachableRegions(map, anchor.x, anchor.y);
        if (reachable.isEmpty()) {
            return all;
        }
        List<GCMovement.Ledge> out = new ArrayList<>();
        for (GCMovement.Ledge l : all) {
            if (reachable.contains(Integer.valueOf(l.regionId()))) {
                out.add(l);
            }
        }
        return out.isEmpty() ? all : out;
    }

    private static List<Anchor> collectAnchors(MapleMap map) {
        List<Anchor> anchors = new ArrayList<>();
        for (MapObject npc : map.getMapObjectsInRange(new Point(0, 0), Double.POSITIVE_INFINITY, Arrays.asList(MapObjectType.NPC))) {
            Point p = npc.getPosition();
            if (p != null) {
                anchors.add(new Anchor(p.x, p.y, NPC_STRENGTH));
            }
        }
        for (Portal portal : map.getPortals()) {
            Point p2 = portal.getPosition();
            if (p2 != null) {
                anchors.add(new Anchor(p2.x, p2.y, PORTAL_STRENGTH));
            }
        }
        return anchors;
    }

    private static double groundBandY(List<GCMovement.Ledge> ledges) {
        int maxSpan = 1;
        for (GCMovement.Ledge l : ledges) {
            maxSpan = Math.max(maxSpan, l.maxX() - l.minX());
        }
        int band = Integer.MIN_VALUE;
        for (GCMovement.Ledge l2 : ledges) {
            if (l2.maxX() - l2.minX() >= maxSpan / 2) {
                band = Math.max(band, l2.centerY());
            }
        }
        return band == Integer.MIN_VALUE ? ledges.get(0).centerY() : band;
    }

    private static double ledgeWeight(GCMovement.Ledge l, List<Anchor> anchors, double groundBandY, TownOverrides ov) {
        if (ov.isBanned(l.centerX(), l.centerY())) {
            return 0.0d;
        }
        double span = Math.max(1, l.maxX() - l.minX());
        double heightAbove = Math.max(0.0d, groundBandY - l.centerY());
        double shape = Math.exp((-heightAbove) / HEIGHT_DECAY);
        double pull = 0.0d;
        for (Anchor a : anchors) {
            pull += anchorPull(a, nearestX(l, a.x), l.centerY());
        }
        return span * shape * (BASE_WEIGHT + pull) * ov.boostMultiplier(l.centerX(), l.centerY());
    }

    private static double anchorPull(Anchor a, int x, int y) {
        double dx = a.x - x;
        double dy = a.y - y;
        return a.strength * Math.exp((-(dx * dx)) / 135200.0d) * Math.exp((-(dy * dy)) / 33800.0d);
    }

    private static int nearestX(GCMovement.Ledge l, int x) {
        return Math.max(l.minX(), Math.min(l.maxX(), x));
    }

    private static int pickX(GCMovement.Ledge l, List<Anchor> anchors, List<Integer> taken, TownOverrides ov) {
        if (l.maxX() <= l.minX()) {
            return l.minX();
        }
        int best = l.minX();
        double bestScore = -1.7976931348623157E308d;
        for (int i = 0; i < X_CANDIDATES; i++) {
            int x = l.minX() + RANDOM.nextInt((l.maxX() - l.minX()) + 1);
            if (!ov.isBanned(x, l.centerY())) {
                double pull = 0.0d;
                for (Anchor a : anchors) {
                    pull += anchorPull(a, x, l.centerY());
                }
                double score = (pull * ov.boostMultiplier(x, l.centerY())) - crowding(x, taken);
                if (score > bestScore) {
                    bestScore = score;
                    best = x;
                }
            }
        }
        return best;
    }

    private static double crowding(int x, List<Integer> taken) {
        double penalty = 0.0d;
        Iterator<Integer> it = taken.iterator();
        while (it.hasNext()) {
            int t = it.next().intValue();
            int d = Math.abs(t - x);
            if (d < MIN_SPACING) {
                penalty += MIN_SPACING - d;
            }
        }
        return penalty;
    }

    private static GCMovement.Ledge weightedPick(List<GCMovement.Ledge> ledges, double[] weights) {
        double total = 0.0d;
        for (double w : weights) {
            total += w;
        }
        if (total <= 0.0d) {
            return ledges.get(RANDOM.nextInt(ledges.size()));
        }
        double r = RANDOM.nextDouble() * total;
        double cumulative = 0.0d;
        for (int i = 0; i < ledges.size(); i++) {
            cumulative += weights[i];
            if (r < cumulative) {
                return ledges.get(i);
            }
        }
        return ledges.get(ledges.size() - 1);
    }

    public static String describe(MapleMap map, Point anchor, int topN) {
        return describe(map, anchor, topN, TownOverrides.EMPTY);
    }

    public static String describe(MapleMap map, Point anchor, int topN, TownOverrides overrides) {
        if (map == null || anchor == null) {
            return "town weights: no map/anchor";
        }
        TownOverrides ov = overrides != null ? overrides : TownOverrides.EMPTY;
        List<GCMovement.Ledge> ledges = reachableLedges(map, anchor);
        if (ledges.isEmpty()) {
            return "town weights: no baked ledges (nav graph not built yet)";
        }
        List<Anchor> anchors = collectAnchors(map);
        double groundBandY = groundBandY(ledges);
        double total = 0.0d;
        List<double[]> rows = new ArrayList<>();
        for (GCMovement.Ledge l : ledges) {
            double w = ledgeWeight(l, anchors, groundBandY, ov);
            total += w;
            rows.add(new double[]{l.regionId(), l.minX(), l.maxX(), l.centerY(), w});
        }
        rows.sort((a, b) -> {
            return Double.compare(b[4], a[4]);
        });
        StringBuilder sb = new StringBuilder();
        sb.append(String.format("town weights map=%d: %d ledges, %d anchors, groundBandY=%.0f, %d pins%n", Integer.valueOf(map.getId()), Integer.valueOf(ledges.size()), Integer.valueOf(anchors.size()), Double.valueOf(groundBandY), Integer.valueOf(ov.pins().size())));
        int limit = Math.min(topN, rows.size());
        for (int i = 0; i < limit; i++) {
            double[] r = rows.get(i);
            double pct = total > 0.0d ? (100.0d * r[4]) / total : 0.0d;
            sb.append(String.format("  #%d region=%d x=[%.0f..%.0f] y=%.0f  %.1f%%%n", Integer.valueOf(i + 1), Integer.valueOf((int) r[0]), Double.valueOf(r[1]), Double.valueOf(r[2]), Double.valueOf(r[3]), Double.valueOf(pct)));
        }
        return sb.toString();
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotTownSystem/TownPresenceSampler$Anchor.class */
    private static final class Anchor {
        private final int x;
        private final int y;
        private final double strength;

        private Anchor(int x, int y, double strength) {
            this.x = x;
            this.y = y;
            this.strength = strength;
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

        public int x() {
            return this.x;
        }

        public int y() {
            return this.y;
        }

        public double strength() {
            return this.strength;
        }
    }
}
