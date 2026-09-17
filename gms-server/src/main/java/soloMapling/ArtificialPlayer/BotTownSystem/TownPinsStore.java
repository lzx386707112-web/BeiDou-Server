package soloMapling.ArtificialPlayer.BotTownSystem;

import java.awt.Point;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class TownPinsStore {
    private TownPinsStore() {
    }

    public static synchronized void addPin(int mapId, int x, int y) {
    }

    public static synchronized Map<Integer, List<Point>> load() {
        return new HashMap<>();
    }

    public static List<Point> forMap(int mapId) {
        return List.of();
    }
}
