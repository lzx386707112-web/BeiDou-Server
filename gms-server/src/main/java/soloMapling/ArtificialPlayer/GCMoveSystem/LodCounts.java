package soloMapling.ArtificialPlayer.GCMoveSystem;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/LodCounts.class */
public final class LodCounts {
    private LodCounts() {
    }

    public static int fullMaps() {
        return ObserverTracker.fullCount();
    }

    public static int haloMaps() {
        return ObserverTracker.haloCount();
    }

    public static int activeMaps() {
        return ObserverTracker.activeCount();
    }

    public static int dynamicBots() {
        return GCMovement.enabledStates().size();
    }

    public static boolean trackerRunning() {
        return ObserverTracker.started();
    }

    public static boolean isMapFull(int mapId) {
        return ObserverTracker.isFull(mapId);
    }

    public static boolean isMapActive(int mapId) {
        return ObserverTracker.isActiveMap(mapId);
    }
}
