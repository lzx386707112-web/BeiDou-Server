package org.gms.net.server.task;

import org.gms.net.server.world.World;
import org.gms.server.weather.WeatherPackets;
import org.gms.server.weather.WeatherRuntime;

public class WeatherTask extends BaseTask implements Runnable {
    public static final long INTERVAL_MS = 60_000L;

    public WeatherTask(World world) {
        super(world);
    }

    @Override
    public void run() {
        if (wserv == null || wserv.getPlayerStorage() == null) return;
        WeatherRuntime.rollIfDue();
        WeatherPackets.broadcast(wserv, false);
    }
}
