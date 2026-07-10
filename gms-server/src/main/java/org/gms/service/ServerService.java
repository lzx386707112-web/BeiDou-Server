package org.gms.service;

import org.gms.client.Character;
import org.gms.constants.id.MapId;
import org.gms.model.dto.ChannelListRtnDTO;
import org.gms.model.dto.MonsterSiegeDTO;
import org.gms.model.dto.ServerBroadcastDTO;
import org.gms.model.dto.WorldListRtnDTO;
import org.gms.net.server.Server;
import org.gms.net.server.channel.Channel;
import org.gms.net.server.world.World;
import org.gms.server.life.LifeFactory;
import org.gms.server.life.Monster;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import org.gms.util.RequireUtil;
import org.springframework.stereotype.Service;

import java.awt.Point;
import java.util.List;

@Service
public class ServerService {
    private static final int MAP_EFFECT_ITEM_ID = 5121009;
    private static final int SPAWN_GAP_X = 80;
    private static final int DEFAULT_SIEGE_COUNT = 1;
    private static final String DEFAULT_SIEGE_MESSAGE = "怪物攻城开始！请前往自由市场入口迎战！";

    public List<WorldListRtnDTO> worldList() {
        List<World> worlds = Server.getInstance().getWorlds();
        return worlds.stream()
                .map(w -> WorldListRtnDTO.builder()
                        .id(w.getId())
                        .expRate(w.getExpRate())
                        .dropRate(w.getDropRate())
                        .mesoRate(w.getMesoRate())
                        .bossDropRate(w.getBossDropRate())
                        .questRate(w.getQuestRate())
                        .travelRate(w.getTravelRate())
                        .fishingRate(w.getFishingRate())
                        .build())
                .toList();
    }

    public List<ChannelListRtnDTO> channelList(int worldId) {
        List<Channel> channels = Server.getInstance().getWorld(worldId).getChannels();
        return channels.stream()
                .map(c -> ChannelListRtnDTO.builder().id(c.getId()).worldId(c.getWorld()).build())
                .toList();
    }

    public void broadcastMapEffect(ServerBroadcastDTO request) {
        RequireUtil.requireNotNull(request, "广播参数不能为空");
        RequireUtil.requireNotEmpty(request.getMessage(), "广播内容不能为空");
        broadcastMapEffect(request.getMessage().trim());
    }

    public int summonMonsterSiege(MonsterSiegeDTO request) {
        RequireUtil.requireNotNull(request, "怪物攻城参数不能为空");
        RequireUtil.requireNotEmpty(request.getMonsterIds(), "怪物ID不能为空");

        int count = request.getCount() == null ? DEFAULT_SIEGE_COUNT : request.getCount();
        RequireUtil.requireTrue(count > 0, "召唤数量必须大于0");

        for (Integer monsterId : request.getMonsterIds()) {
            RequireUtil.requireNotNull(monsterId, "怪物ID不能为空");
            RequireUtil.requireNotNull(LifeFactory.getMonster(monsterId), "未知怪物ID：" + monsterId);
        }

        int spawned = 0;
        for (Channel channel : Server.getInstance().getAllChannels()) {
            MapleMap map = channel.getMapFactory().getMap(MapId.FM_ENTRANCE);
            if (map == null) {
                continue;
            }

            Point basePoint = getFreeMarketSpawnPoint(map);
            int totalIndex = 0;
            for (Integer monsterId : request.getMonsterIds()) {
                for (int i = 0; i < count; i++) {
                    Monster monster = LifeFactory.getMonster(monsterId);
                    Point spawnPoint = new Point(basePoint.x + (totalIndex * SPAWN_GAP_X), basePoint.y);
                    map.spawnMonsterOnGroundBelow(monster, spawnPoint);
                    spawned++;
                    totalIndex++;
                }
            }
        }

        if (Boolean.TRUE.equals(request.getBroadcast())) {
            String message = RequireUtil.isEmpty(request.getMessage()) ? DEFAULT_SIEGE_MESSAGE : request.getMessage().trim();
            broadcastMapEffect(message);
        }

        return spawned;
    }

    private void broadcastMapEffect(String message) {
        for (World world : Server.getInstance().getWorlds()) {
            for (Character chr : world.getPlayerStorage().getAllCharacters()) {
                if (chr != null) {
                    chr.startMapEffect(message, MAP_EFFECT_ITEM_ID);
                }
            }
        }
    }

    private Point getFreeMarketSpawnPoint(MapleMap map) {
        Portal portal = map.getPortal(0);
        if (portal == null) {
            portal = map.findClosestPlayerSpawnpoint(new Point(0, 0));
        }
        return portal == null ? new Point(0, 0) : portal.getPosition();
    }
}
