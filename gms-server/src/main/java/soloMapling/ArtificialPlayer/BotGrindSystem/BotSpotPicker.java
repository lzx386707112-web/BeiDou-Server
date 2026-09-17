package soloMapling.ArtificialPlayer.BotGrindSystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

public final class BotSpotPicker {
    private static final Random RANDOM = new Random();
    private static final int MIN_SPACING = 30;
    private static final int SPACING_ATTEMPTS = 8;

    private BotSpotPicker() {
    }

    public static Point pickGroundSpot(MapleMap map, int fromX, int fromY) {
        return pickGroundSpot(map, fromX, fromY, Integer.MIN_VALUE, Integer.MAX_VALUE);
    }

    public static Point pickGroundSpot(MapleMap map, int fromX, int fromY, int x1, int x2) {
        List<Candidate> candidates = eligibleLedges(map, fromX, fromY, x1, x2);
        if (candidates.isEmpty()) {
            return null;
        }
        Candidate c = pickWeightedByWidth(candidates);
        int x = randomInSpan(c.lo, c.hi);
        return groundAt(map, c, x);
    }

    public static List<Point> pickGroundSpots(MapleMap map, int fromX, int fromY, int count) {
        return pickGroundSpots(map, fromX, fromY, Integer.MIN_VALUE, Integer.MAX_VALUE, count);
    }

    public static List<Point> pickGroundSpots(MapleMap map, int fromX, int fromY, int x1, int x2, int count) {
        List<Point> out = new ArrayList<>();
        List<Candidate> candidates = eligibleLedges(map, fromX, fromY, x1, x2);
        if (candidates.isEmpty() || count <= 0) {
            return out;
        }
        Map<Integer, List<Integer>> occupiedByLedge = new HashMap<>();
        for (int i = 0; i < count; i++) {
            Candidate c = pickWeightedByWidth(candidates);
            List<Integer> taken = occupiedByLedge.computeIfAbsent(c.ledge.regionId(), k -> new ArrayList<>());
            int x = pickSpacedX(c.lo, c.hi, taken);
            taken.add(x);
            out.add(groundAt(map, c, x));
        }
        return out;
    }

    private static List<Candidate> eligibleLedges(MapleMap map, int fromX, int fromY, int x1, int x2) {
        List<Candidate> out = new ArrayList<>();
        if (map == null) {
            return out;
        }
        List<GCMovement.Ledge> ledges = GCMovement.walkableLedges(map);
        if (ledges.isEmpty()) {
            return out;
        }
        int bandLo = Math.min(x1, x2);
        int bandHi = Math.max(x1, x2);
        Set<Integer> reachable = GCMovement.reachableRegions(map, fromX, fromY);
        boolean filter = !reachable.isEmpty();
        for (GCMovement.Ledge l : ledges) {
            if (!filter || reachable.contains(l.regionId())) {
                int lo = Math.max(l.minX(), bandLo);
                int hi = Math.min(l.maxX(), bandHi);
                if (hi >= lo) {
                    out.add(new Candidate(l, lo, hi));
                }
            }
        }
        return out;
    }

    private static Point groundAt(MapleMap map, Candidate c, int x) {
        Point ground = GCMovement.groundPointInRegion(map, c.ledge.regionId(), x);
        return ground != null ? ground : new Point(x, c.ledge.centerY());
    }

    private static Candidate pickWeightedByWidth(List<Candidate> candidates) {
        if (candidates.size() == 1) {
            return candidates.get(0);
        }
        long total = 0;
        for (Candidate c : candidates) {
            total += c.weight();
        }
        long r = (long) (RANDOM.nextDouble() * total);
        long cumulative = 0;
        for (Candidate c : candidates) {
            cumulative += c.weight();
            if (r < cumulative) {
                return c;
            }
        }
        return candidates.get(candidates.size() - 1);
    }

    private static int randomInSpan(int lo, int hi) {
        return hi <= lo ? lo : lo + RANDOM.nextInt((hi - lo) + 1);
    }

    private static int pickSpacedX(int lo, int hi, List<Integer> taken) {
        if (hi <= lo) {
            return lo;
        }
        int candidate = lo;
        for (int attempt = 0; attempt < SPACING_ATTEMPTS; attempt++) {
            candidate = lo + RANDOM.nextInt((hi - lo) + 1);
            boolean clear = true;
            for (int t : taken) {
                if (Math.abs(t - candidate) < MIN_SPACING) {
                    clear = false;
                    break;
                }
            }
            if (clear) {
                return candidate;
            }
        }
        return candidate;
    }

    private static final class Candidate {
        final GCMovement.Ledge ledge;
        final int lo;
        final int hi;

        Candidate(GCMovement.Ledge ledge, int lo, int hi) {
            this.ledge = ledge;
            this.lo = lo;
            this.hi = hi;
        }

        int weight() {
            return Math.max(1, (this.hi - this.lo) + 1);
        }
    }
}
