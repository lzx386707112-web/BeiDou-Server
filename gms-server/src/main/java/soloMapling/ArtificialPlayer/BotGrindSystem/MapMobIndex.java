package soloMapling.ArtificialPlayer.BotGrindSystem;

import org.gms.net.server.Server;
import org.gms.server.maps.MapleMap;

public final class MapMobIndex {
    private MapMobIndex() {
    }

    public static int level(int mapId) {
        try {
            MapleMap map = Server.getInstance().getChannel(0, 1).getMapFactory().getMap(mapId);
            if (map == null || map.getAllMonsters().isEmpty()) {
                return -1;
            }
            return 1;
        } catch (Exception e) {
            return -1;
        }
    }
}
