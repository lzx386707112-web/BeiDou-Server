package org.gms.service;

import org.gms.client.Character;
import org.gms.client.inventory.manipulator.InventoryManipulator;
import org.gms.constants.id.MapId;
import org.gms.constants.id.MobId;
import org.gms.model.dto.ChannelListRtnDTO;
import org.gms.model.dto.MonsterSiegeDTO;
import org.gms.model.dto.MonsterSiegeRewardDTO;
import org.gms.model.dto.ServerBroadcastDTO;
import org.gms.model.dto.WorldListRtnDTO;
import org.gms.net.server.Server;
import org.gms.net.server.channel.Channel;
import org.gms.net.server.world.World;
import org.gms.server.ItemInformationProvider;
import org.gms.server.TimerManager;
import org.gms.server.life.LifeFactory;
import org.gms.server.life.Monster;
import org.gms.server.life.MonsterListener;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import org.gms.util.RequireUtil;
import org.springframework.stereotype.Service;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.LongAdder;

@Service
public class ServerService {
    private static final int MAP_EFFECT_ITEM_ID = 5121009;
    private static final int DEFAULT_SIEGE_COUNT = 1;
    private static final String DEFAULT_SIEGE_MESSAGE = "怪物攻城开始！请前往指定主城迎战！";
    private final Set<Monster> siegeMonsters = ConcurrentHashMap.newKeySet();
    private final Set<SiegeSession> siegeSessions = ConcurrentHashMap.newKeySet();

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
        int mapId = requireSiegeMapId(request.getMapId());

        for (Integer monsterId : request.getMonsterIds()) {
            RequireUtil.requireNotNull(monsterId, "怪物ID不能为空");
            RequireUtil.requireNotNull(LifeFactory.getMonster(monsterId), "未知怪物ID：" + monsterId);
        }
        List<MonsterSiegeRewardDTO> rewards = validateRewards(request.getRewards());

        int spawned = 0;
        SiegeSession session = rewards.isEmpty() ? null : new SiegeSession(mapId, rewards);
        if (session != null) {
            siegeSessions.add(session);
        }
        for (Channel channel : getSiegeChannels()) {
            MapleMap map = channel.getMapFactory().getMap(mapId);
            if (map == null) {
                continue;
            }

            Point basePoint = getSiegeSpawnPoint(map);
            List<Point> spawnAnchors = getSiegeSpawnAnchors(map, basePoint);
            for (Integer monsterId : request.getMonsterIds()) {
                for (int i = 0; i < count; i++) {
                    Point spawnPoint = getRandomGroundSpawnPoint(map, spawnAnchors, basePoint);
                    List<Monster> monsters = spawnSiegeMonsters(map, monsterId, spawnPoint);
                    for (Monster monster : monsters) {
                        if (session != null) {
                            session.addMonster(monster);
                        }
                        siegeMonsters.add(monster);
                    }
                    spawned++;
                }
            }
        }
        if (session != null) {
            session.ready();
            if (spawned == 0) {
                session.cancel();
            }
        }

        if (Boolean.TRUE.equals(request.getBroadcast())) {
            String message = RequireUtil.isEmpty(request.getMessage()) ? DEFAULT_SIEGE_MESSAGE : request.getMessage().trim();
            broadcastMapEffect(message);
        }

        return spawned;
    }

    private List<Monster> spawnSiegeMonsters(MapleMap map, int monsterId, Point spawnPoint) {
        if (monsterId == MobId.ZAKUM_3) {
            return map.spawnZakumOnGroundBelow(spawnPoint);
        }
        if (monsterId == MobId.HORNTAIL) {
            return map.spawnHorntailOnGroundBelow(spawnPoint);
        }

        Monster monster = LifeFactory.getMonster(monsterId);
        map.spawnMonsterOnGroundBelow(monster, spawnPoint);
        return List.of(monster);
    }

    public int clearMonsterSiege(Integer requestedMapId) {
        int mapId = requireSiegeMapId(requestedMapId);
        siegeSessions.stream().filter(session -> session.mapId == mapId).forEach(SiegeSession::cancel);
        int cleared = 0;
        for (Channel channel : getSiegeChannels()) {
            MapleMap map = channel.getMapFactory().getMap(mapId);
            if (map == null) {
                continue;
            }

            for (Monster monster : map.getAllMonsters()) {
                if (siegeMonsters.contains(monster) || monster.isBoss()) {
                    map.killMonster(monster, null, false);
                    siegeMonsters.remove(monster);
                    cleared++;
                }
            }
        }
        siegeMonsters.removeIf(monster -> monster.getMap() == null || monster.getMap().getMonsterByOid(monster.getObjectId()) == null);
        return cleared;
    }

    private List<MonsterSiegeRewardDTO> validateRewards(List<MonsterSiegeRewardDTO> rewards) {
        if (rewards == null) {
            return List.of();
        }
        Set<Integer> ranks = ConcurrentHashMap.newKeySet();
        for (MonsterSiegeRewardDTO reward : rewards) {
            RequireUtil.requireNotNull(reward, "奖励配置不能为空");
            RequireUtil.requireTrue(reward.getRank() != null && reward.getRank() >= 1 && reward.getRank() <= 3,
                    "奖励名次只能是1至3");
            RequireUtil.requireTrue(ranks.add(reward.getRank()), "奖励名次不能重复");
            RequireUtil.requireTrue(reward.getItemId() != null
                    && ItemInformationProvider.getInstance().getName(reward.getItemId()) != null,
                    "未知奖励物品ID：" + reward.getItemId());
            RequireUtil.requireTrue(reward.getQuantity() != null && reward.getQuantity() > 0
                    && reward.getQuantity() <= Short.MAX_VALUE, "奖励数量必须在1至32767之间");
        }
        return List.copyOf(rewards);
    }

    private Character findOnlineCharacter(int characterId) {
        return Server.getInstance().getWorlds().stream()
                .map(world -> world.getPlayerStorage().getCharacterById(characterId))
                .filter(character -> character != null)
                .findFirst()
                .orElse(null);
    }

    private final class SiegeSession {
        private final int mapId;
        private final List<MonsterSiegeRewardDTO> rewards;
        private final AtomicInteger remaining = new AtomicInteger();
        private final AtomicBoolean settled = new AtomicBoolean();
        private final AtomicBoolean ready = new AtomicBoolean();
        private final AtomicInteger emptyChecks = new AtomicInteger();
        private final ConcurrentHashMap<Integer, LongAdder> damages = new ConcurrentHashMap<>();
        private final ConcurrentHashMap<Integer, String> characterNames = new ConcurrentHashMap<>();
        private final Set<Monster> trackedMonsters = ConcurrentHashMap.newKeySet();
        private volatile ScheduledFuture<?> completionTask;

        private SiegeSession(int mapId, List<MonsterSiegeRewardDTO> rewards) {
            this.mapId = mapId;
            this.rewards = rewards;
        }

        private void addMonster(Monster monster) {
            if (!trackedMonsters.add(monster)) {
                return;
            }
            remaining.incrementAndGet();
            AtomicBoolean killed = new AtomicBoolean();
            monster.addListener(new MonsterListener() {
                @Override
                public void monsterKilled(int aniTime) {
                    siegeMonsters.remove(monster);
                    if (killed.compareAndSet(false, true)) {
                        remaining.decrementAndGet();
                    }
                }

                @Override
                public void monsterDamaged(Character from, int trueDmg) {
                    if (!settled.get() && from != null && trueDmg > 0) {
                        damages.computeIfAbsent(from.getId(), ignored -> new LongAdder()).add(trueDmg);
                        characterNames.putIfAbsent(from.getId(), from.getName());
                    }
                }

                @Override
                public void monsterHealed(int trueHeal) {
                }
            });
            if (!monster.isAlive() && killed.compareAndSet(false, true)) {
                remaining.decrementAndGet();
            }
        }

        private void cancel() {
            settled.set(true);
            cancelCompletionTask();
            siegeSessions.remove(this);
        }

        private void ready() {
            ready.set(true);
            completionTask = TimerManager.getInstance().register(this::checkCompletion, 200, 200);
        }

        private void checkCompletion() {
            if (settled.get() || !ready.get()) {
                return;
            }
            boolean hasBoss = false;
            for (Channel channel : getSiegeChannels()) {
                MapleMap map = channel.getMapFactory().getMap(mapId);
                if (map == null) {
                    continue;
                }
                for (Monster monster : map.getAllMonsters()) {
                    if (monster.isBoss()) {
                        hasBoss = true;
                        addMonster(monster);
                    }
                }
            }
            if (hasBoss || remaining.get() > 0) {
                emptyChecks.set(0);
            } else if (emptyChecks.incrementAndGet() >= 25) {
                settle();
            }
        }

        private void cancelCompletionTask() {
            ScheduledFuture<?> task = completionTask;
            if (task != null) {
                task.cancel(false);
            }
        }

        private void settle() {
            if (!settled.compareAndSet(false, true)) {
                return;
            }
            cancelCompletionTask();
            siegeSessions.remove(this);
            List<Integer> winners = damages.entrySet().stream()
                    .sorted((left, right) -> Long.compare(right.getValue().sum(), left.getValue().sum()))
                    .limit(3)
                    .map(java.util.Map.Entry::getKey)
                    .toList();
            if (!winners.isEmpty()) {
                StringBuilder ranking = new StringBuilder("怪物攻城结束！伤害前三名：");
                for (int i = 0; i < winners.size(); i++) {
                    int characterId = winners.get(i);
                    ranking.append(i == 0 ? "" : "，")
                            .append(i + 1).append(".")
                            .append(characterNames.getOrDefault(characterId, String.valueOf(characterId)))
                            .append("(").append(damages.get(characterId).sum()).append(")");
                }
                broadcastMapEffect(ranking.toString());
            }
            for (MonsterSiegeRewardDTO reward : rewards) {
                if (reward.getRank() > winners.size()) {
                    continue;
                }
                Character winner = findOnlineCharacter(winners.get(reward.getRank() - 1));
                if (winner != null) {
                    boolean added = InventoryManipulator.addById(winner.getClient(), reward.getItemId(),
                            reward.getQuantity().shortValue());
                    winner.dropMessage(5, added
                            ? "怪物攻城伤害第" + reward.getRank() + "名奖励已发放到背包。"
                            : "怪物攻城奖励发放失败，请清理背包后联系管理员。");
                }
            }
        }
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

    private int requireSiegeMapId(Integer mapId) {
        int resolvedMapId = mapId == null ? MapId.FM_ENTRANCE : mapId;
        RequireUtil.requireTrue(resolvedMapId > 0, "攻城地图ID必须大于0");
        boolean exists = getSiegeChannels().stream()
                .anyMatch(channel -> channel.getMapFactory().getMap(resolvedMapId) != null);
        RequireUtil.requireTrue(exists, "攻城地图不存在：" + resolvedMapId);
        return resolvedMapId;
    }

    private Point getSiegeSpawnPoint(MapleMap map) {
        Portal portal = map.getPortal(0);
        if (portal == null) {
            portal = map.findClosestPlayerSpawnpoint(new Point(0, 0));
        }
        return portal == null ? new Point(0, 0) : portal.getPosition();
    }

    private List<Point> getSiegeSpawnAnchors(MapleMap map, Point fallback) {
        List<Point> anchors = new ArrayList<>();
        for (int portalId = 0; portalId < 200; portalId++) {
            Portal portal = map.getPortal(portalId);
            if (portal == null) {
                continue;
            }
            String name = portal.getName();
            if (name != null && (name.startsWith("in") || name.startsWith("pt_floor") || name.startsWith("sp"))) {
                anchors.add(portal.getPosition());
            }
        }
        if (anchors.isEmpty()) {
            anchors.add(fallback);
        }
        return anchors;
    }

    private List<Channel> getSiegeChannels() {
        return Server.getInstance().getWorlds().stream()
                .map(world -> world.getChannel(1))
                .filter(channel -> channel != null)
                .toList();
    }

    private Point getRandomGroundSpawnPoint(MapleMap map, List<Point> anchors, Point fallback) {
        Rectangle mapArea = map.getMapArea();
        if (mapArea == null || mapArea.width <= 0 || anchors.isEmpty()) {
            return fallback;
        }

        ThreadLocalRandom random = ThreadLocalRandom.current();
        Point anchor = anchors.get(random.nextInt(anchors.size()));
        int randomX = anchor.x + random.nextInt(-30, 31);
        randomX = Math.max(mapArea.x, Math.min(mapArea.x + mapArea.width, randomX));
        Point randomPoint = new Point(randomX, anchor.y);
        Point groundPoint = map.calcDropPos(randomPoint, fallback);
        return groundPoint == null ? fallback : groundPoint;
    }
}
