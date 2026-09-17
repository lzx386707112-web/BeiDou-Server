package soloMapling.ArtificialPlayer.BotPartySystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

/** Clusters walkable ledges into vertical floors for party-grind stationing. */
public final class PartyGrindFloors {
    public static final int BAND = 80;

    private PartyGrindFloors() {
    }

    public record Sample(int centerY, int minX, int maxX) {
    }

    public record Floor(int centerY, int minX, int maxX) {
        public boolean containsY(int y) {
            return Math.abs(y - centerY) <= BAND;
        }

        public int clampX(int x) {
            if (x < minX) {
                return minX;
            }
            if (x > maxX) {
                return maxX;
            }
            return x;
        }
    }

    public static int indexFor(int botSlot, int floorCount) {
        return org.gms.server.life.PartyGrindCompat.floorIndex(botSlot, floorCount);
    }

    public static List<Floor> cluster(List<Sample> samples) {
        if (samples == null || samples.isEmpty()) {
            return List.of();
        }
        List<Sample> ordered = new ArrayList<>(samples);
        ordered.sort(Comparator.comparingInt(Sample::centerY));
        List<Floor> floors = new ArrayList<>();
        int ySum = ordered.get(0).centerY();
        int n = 1;
        int minX = ordered.get(0).minX();
        int maxX = ordered.get(0).maxX();
        for (int i = 1; i < ordered.size(); i++) {
            Sample s = ordered.get(i);
            if (Math.abs(s.centerY() - Math.round(ySum / (float) n)) <= BAND) {
                ySum += s.centerY();
                n++;
                minX = Math.min(minX, s.minX());
                maxX = Math.max(maxX, s.maxX());
            } else {
                floors.add(new Floor(Math.round(ySum / (float) n), minX, maxX));
                ySum = s.centerY();
                n = 1;
                minX = s.minX();
                maxX = s.maxX();
            }
        }
        floors.add(new Floor(Math.round(ySum / (float) n), minX, maxX));
        return floors;
    }

    public static List<Floor> fromMap(MapleMap map, Point fallback) {
        List<Sample> samples = new ArrayList<>();
        if (map != null) {
            for (GCMovement.Ledge ledge : GCMovement.walkableLedges(map)) {
                if (ledge.maxX() - ledge.minX() < 40) {
                    continue;
                }
                samples.add(new Sample(ledge.centerY(), ledge.minX(), ledge.maxX()));
            }
        }
        List<Floor> floors = cluster(samples);
        if (!floors.isEmpty()) {
            return floors;
        }
        int y = fallback != null ? fallback.y : 0;
        int x = fallback != null ? fallback.x : 0;
        return List.of(new Floor(y, x - 400, x + 400));
    }

    public static Point station(MapleMap map, Floor floor, int desiredX) {
        int x = floor.clampX(desiredX);
        if (map != null) {
            Point ground = GCMovement.groundPointBelow(map, x, floor.centerY());
            if (ground != null) {
                return ground;
            }
        }
        return new Point(x, floor.centerY());
    }
}
