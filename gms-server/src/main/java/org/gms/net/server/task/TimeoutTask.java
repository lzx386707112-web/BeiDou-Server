package org.gms.net.server.task;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.config.GameConfig;
import org.gms.net.server.channel.Channel;
import org.gms.net.server.world.World;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Collection;

/**
 * @author Shavit
 */
public class TimeoutTask extends BaseTask implements Runnable {
    private static final Logger log = LoggerFactory.getLogger(TimeoutTask.class);

    @Override
    public void run() {
        long time = System.currentTimeMillis();
        Collection<Character> chars = wserv.getPlayerStorage().getAllCharacters();
        for (Character chr : chars) {
            Client client = chr.getClient();
            if (client == null || client.getPlayer() != chr) {
                boolean removed = false;
                if (client != null) {
                    Channel channel = client.getChannelServer();
                    if (channel != null) {
                        removed = channel.getPlayerStorage().removePlayer(chr);
                    }
                }
                if (wserv.getPlayerStorage().removePlayer(chr)) {
                    removed = true;
                }
                if (removed) {
                    log.warn("Removed stale character {} from player storage", chr.getName());
                }
                continue;
            }

            if (time - client.getLastPacket() > GameConfig.getServerLong("timeout_duration")) {
                // 默认1h还没有发过任何包，那就是异常连接，直接断开
                if (client.timeoutDisconnect()) {
                    log.info("Chr {} auto-disconnected due to inactivity", chr.getName());
                }
            }
        }
    }

    public TimeoutTask(World world) {
        super(world);
    }
}
