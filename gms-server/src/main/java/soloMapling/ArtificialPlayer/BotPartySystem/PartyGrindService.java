package soloMapling.ArtificialPlayer.BotPartySystem;

import java.awt.Point;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.net.server.world.Party;
import org.gms.server.life.Monster;
import org.gms.server.life.PartyGrindCompat;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotDecoratorSystem.BotDecorate;
import soloMapling.ArtificialPlayer.BotDecoratorSystem.BotDecorateEquips;
import soloMapling.ArtificialPlayer.BotGeneration;
import soloMapling.ArtificialPlayer.BotHelpers;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.BotTypeManager;
import soloMapling.ArtificialPlayer.BotTypes.CompanionGrindBot;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

public final class PartyGrindService {
    private static final Map<Integer, Integer> BOT_TO_LEADER = new ConcurrentHashMap<>();
    private static final Map<Integer, List<Integer>> LEADER_TO_BOTS = new ConcurrentHashMap<>();
    private static final Map<Integer, Integer> BOT_CLAIM = new ConcurrentHashMap<>();
    private static final Map<Integer, PartyGrindFloors.Floor> BOT_FLOOR = new ConcurrentHashMap<>();
    private static final Map<Integer, Integer> LEADER_FLOOR_MAP = new ConcurrentHashMap<>();
    private static final Map<Integer, Integer> LEADER_FLOOR_COUNT = new ConcurrentHashMap<>();
    private static final Map<Integer, Long> NEXT_FLOOR_REFRESH_MS = new ConcurrentHashMap<>();
    private static final int LEADER_LEASH_X = 560;
    private static List<Monster> cachedMobs = List.of();
    private static int cachedMapId = -1;
    private static long cachedMobsAtMs = 0L;

    private PartyGrindService() {
    }

    public static boolean isCompanion(int botId) {
        return BOT_TO_LEADER.containsKey(botId);
    }

    public static int leaderIdFor(int botId) {
        return BOT_TO_LEADER.getOrDefault(botId, -1);
    }

    public static PartyGrindFloors.Floor floorFor(int botId) {
        return BOT_FLOOR.get(botId);
    }

    public static Point stationFor(Character bot, Character leader) {
        if (bot == null || leader == null || leader.getMap() == null) {
            return null;
        }
        bindFloors(leader);
        PartyGrindFloors.Floor floor = BOT_FLOOR.get(bot.getId());
        if (floor == null) {
            Point lead = leader.getPosition();
            return lead == null ? null : new Point(lead);
        }
        int slot = slotOf(leader.getId(), bot.getId());
        int xOffset = ((slot % 3) - 1) * 48;
        return PartyGrindFloors.station(leader.getMap(), floor, leader.getPosition().x + xOffset);
    }

    public static boolean onAssignedFloor(Character bot) {
        if (bot == null || bot.getPosition() == null) {
            return false;
        }
        PartyGrindFloors.Floor floor = BOT_FLOOR.get(bot.getId());
        if (floor == null) {
            return true;
        }
        return floor.containsY(bot.getPosition().y);
    }

    public static Monster huntMobFor(Character bot, Character leader) {
        if (bot == null || leader == null || bot.getMap() == null || leader.getMap() == null
                || bot.getMapId() != leader.getMapId()) {
            return null;
        }
        bindFloors(leader);
        PartyGrindFloors.Floor floor = BOT_FLOOR.get(bot.getId());
        synchronized (BOT_CLAIM) {
            MapleMap map = bot.getMap();
            Point origin = bot.getPosition();
            Point leadPos = leader.getPosition();
            Integer heldOid = BOT_CLAIM.get(bot.getId());
            if (heldOid != null) {
                Monster held = map.getMonsterByOid(heldOid);
                if (isHuntTarget(held, floor, origin, leadPos)) {
                    return held;
                }
                BOT_CLAIM.remove(bot.getId(), heldOid);
            }
            Set<Integer> taken = claimedBySiblings(bot.getId(), leader.getId());
            Monster target = closestMob(mobsOnMap(map), origin, leadPos, floor, taken);
            if (target != null) {
                BOT_CLAIM.put(bot.getId(), target.getObjectId());
            }
            return target;
        }
    }

    private static Set<Integer> claimedBySiblings(int botId, int leaderId) {
        Set<Integer> taken = new HashSet<>();
        List<Integer> siblings = LEADER_TO_BOTS.get(leaderId);
        if (siblings == null) {
            return taken;
        }
        for (Integer siblingId : siblings) {
            if (siblingId == null || siblingId == botId) {
                continue;
            }
            Integer oid = BOT_CLAIM.get(siblingId);
            if (oid != null) {
                taken.add(oid);
            }
        }
        return taken;
    }

    private static List<Monster> mobsOnMap(MapleMap map) {
        long now = System.currentTimeMillis();
        if (cachedMapId == map.getId() && now - cachedMobsAtMs < 50 && cachedMobs != null) {
            return cachedMobs;
        }
        cachedMobs = map.getAllMonsters();
        cachedMapId = map.getId();
        cachedMobsAtMs = now;
        return cachedMobs;
    }

    private static Monster closestMob(List<Monster> mobs, Point origin, Point leadPos, PartyGrindFloors.Floor floor,
            Set<Integer> skip) {
        Monster best = null;
        int bestDist = Integer.MAX_VALUE;
        int originX = origin != null ? origin.x : leadPos.x;
        for (Monster mob : mobs) {
            if (!isHuntTarget(mob, floor, origin, leadPos) || skip.contains(mob.getObjectId())) {
                continue;
            }
            int dist = Math.abs(mob.getPosition().x - originX);
            if (dist < bestDist) {
                bestDist = dist;
                best = mob;
            }
        }
        return best;
    }

    private static boolean isHuntTarget(Monster mob, PartyGrindFloors.Floor floor, Point origin, Point leadPos) {
        if (mob == null || !mob.isAlive() || mob.isFake() || mob.isBoss() || leadPos == null) {
            return false;
        }
        Point pos = mob.getPosition();
        if (pos == null) {
            return false;
        }
        boolean onFloor = floor == null || floor.containsY(pos.y);
        boolean besideBot = origin != null && Math.abs(pos.y - origin.y) <= PartyGrindFloors.BAND;
        if (!onFloor && !besideBot) {
            return false;
        }
        return Math.abs(pos.x - leadPos.x) <= LEADER_LEASH_X;
    }

    public static boolean spawnFor(Character leader) {
        if (leader == null || leader.getMap() == null || leader.getParty() == null) {
            return false;
        }
        dismiss(leader.getId());
        MapleMap map = leader.getMap();
        List<PartyGrindFloors.Floor> floors = PartyGrindFloors.fromMap(map, leader.getPosition());
        List<Integer> ids = new ArrayList<>();
        int partyId = leader.getParty().getId();
        for (int i = 0; i < PartyGrindCompat.BOT_COUNT; i++) {
            PartyGrindFloors.Floor floor = floors.get(PartyGrindCompat.floorIndex(i, floors.size()));
            int xOffset = ((i % 3) - 1) * 48;
            Point spawnAt = PartyGrindFloors.station(map, floor, leader.getPosition().x + xOffset);
            floor = new PartyGrindFloors.Floor(spawnAt.y, floor.minX(), floor.maxX());
            Character bot = BotGeneration.createBotPollReadiness(spawnAt, map.getId(), true, false);
            if (bot == null) {
                cleanup(ids);
                return false;
            }
            tuneCompanion(bot, leader);
            BOT_TO_LEADER.put(bot.getId(), leader.getId());
            BOT_FLOOR.put(bot.getId(), floor);
            BotTypeManager.BotType.COMPANION_GRIND_BOT.createAndSetBot(bot);
            if (!Party.joinParty(bot, partyId, true)) {
                cleanup(ids);
                dismissOne(bot);
                return false;
            }
            try {
                leader.receivePartyMemberHP();
                bot.updatePartyMemberHP();
            } catch (Exception ignored) {
            }
            GCMovement.setGrinding(bot, true);
            GCMovement.teleportTo(bot, spawnAt.x, spawnAt.y);
            BotSM sm = CharacterStorage.getBotById(bot.getId());
            if (sm instanceof CompanionGrindBot companion) {
                companion.setRunning(true);
                companion.startScheduledTask(180 + i * 80);
            }
            ids.add(bot.getId());
        }
        LEADER_TO_BOTS.put(leader.getId(), ids);
        LEADER_FLOOR_MAP.put(leader.getId(), map.getId());
        LEADER_FLOOR_COUNT.put(leader.getId(), floors.size());
        return ids.size() == PartyGrindCompat.BOT_COUNT;
    }

    static void bindFloors(Character leader) {
        if (leader == null || leader.getMap() == null) {
            return;
        }
        List<Integer> ids = LEADER_TO_BOTS.get(leader.getId());
        if (ids == null || ids.isEmpty()) {
            return;
        }
        int mapId = leader.getMapId();
        Integer bound = LEADER_FLOOR_MAP.get(leader.getId());
        if (bound != null && bound == mapId && allFloorsBound(ids)) {
            return;
        }
        List<PartyGrindFloors.Floor> floors = PartyGrindFloors.fromMap(leader.getMap(), leader.getPosition());
        for (int i = 0; i < ids.size(); i++) {
            Integer botId = ids.get(i);
            if (botId == null) {
                continue;
            }
            PartyGrindFloors.Floor floor = floors.get(PartyGrindCompat.floorIndex(i, floors.size()));
            Point parked = PartyGrindFloors.station(leader.getMap(), floor, leader.getPosition().x);
            BOT_FLOOR.put(botId, new PartyGrindFloors.Floor(parked.y, floor.minX(), floor.maxX()));
        }
        LEADER_FLOOR_MAP.put(leader.getId(), mapId);
        LEADER_FLOOR_COUNT.put(leader.getId(), floors.size());
    }

    private static boolean allFloorsBound(List<Integer> ids) {
        for (Integer id : ids) {
            if (id != null && !BOT_FLOOR.containsKey(id)) {
                return false;
            }
        }
        return true;
    }

    private static int slotOf(int leaderId, int botId) {
        List<Integer> ids = LEADER_TO_BOTS.get(leaderId);
        if (ids == null) {
            return 0;
        }
        int idx = ids.indexOf(botId);
        return Math.max(0, idx);
    }

    private static void tuneCompanion(Character bot, Character leader) {
        int offset = ThreadLocalRandom.current().nextInt(-PartyGrindCompat.LEVEL_JITTER, PartyGrindCompat.LEVEL_JITTER + 1);
        int level = PartyGrindCompat.companionLevel(leader.getLevel(), offset);
        bot.setLevel(level);
        bot.setJob(Job.getById(BotDecorate.selectJobByLevel(level)));
        int primary = Math.min(999, 4 + Math.max(0, level - 1) * 5);
        bot.updateStrDexIntLuk(primary);
        BotDecorateEquips.equipWeapon(bot);
        BotDecorate.applyVisibleHpMp(bot);
    }

    public static void dismiss(int leaderId) {
        List<Integer> ids = LEADER_TO_BOTS.remove(leaderId);
        LEADER_FLOOR_MAP.remove(leaderId);
        LEADER_FLOOR_COUNT.remove(leaderId);
        if (ids == null) {
            return;
        }
        cleanup(ids);
    }

    private static void cleanup(List<Integer> ids) {
        for (Integer id : ids) {
            Character bot = null;
            try {
                bot = BotHelpers.getCharFromChannelStorage(id);
            } catch (Exception ignored) {
            }
            dismissOne(bot);
            BOT_TO_LEADER.remove(id);
            BOT_CLAIM.remove(id);
            BOT_FLOOR.remove(id);
        }
    }

    private static void dismissOne(Character bot) {
        if (bot == null) {
            return;
        }
        try {
            BotPartyCommands.botLeaveParty(bot);
        } catch (Exception ignored) {
        }
        try {
            GCMovement.stop(bot);
            GCMovement.disable(bot);
        } catch (Exception ignored) {
        }
        try {
            BotTypeManager.manuallyStopBot(bot);
        } catch (Exception ignored) {
        }
        try {
            if (bot.getMap() != null) {
                BotGeneration.removeBotFromServer(bot);
            }
        } catch (Exception ignored) {
        }
        BOT_TO_LEADER.remove(bot.getId());
        BOT_CLAIM.remove(bot.getId());
        BOT_FLOOR.remove(bot.getId());
    }
}
