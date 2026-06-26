package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import org.gms.server.life.Monster;
import org.gms.server.maps.MapleMap;
import org.gms.util.PacketCreator;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.server.ExecutorServiceManager;

import java.awt.Point;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

import static soloMapling.ArtificialPlayer.BotCommandsPack.BotAttack.bossAttack;
import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotChatbubble;
import static soloMapling.ArtificialPlayer.BotHelpers.isBot;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.BotMoveSmallDistanceX;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botCancelChair;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botFaceTowardsPoint;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.isBotMoving;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.pathFinderBeta;

public final class BotBossCombatManager {
    private static final int FM_ENTRANCE = 910000000;
    private static final int MAX_ATTACKERS = 10;
    private static final long ATTACK_INTERVAL_MS = 1200L;
    private static final long MOVE_REFRESH_MS = 900L;
    private static final int FORMATION_TOLERANCE = 45;
    private static final int ATTACK_RANGE_X = 170;
    private static final int ATTACK_RANGE_Y = 70;
    private static final ConcurrentHashMap<Integer, ScheduledFuture<?>> ACTIVE_BY_MAP = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<Integer, Long> NEXT_MOVE_AT_BY_BOT = new ConcurrentHashMap<>();
    private static final String[] START_LINES = {
            "来了，集火Boss！",
            "开打开打，注意躲技能！",
            "老板出现了，兄弟们上！"
    };

    private BotBossCombatManager() {
    }

    public static boolean handleChatTrigger(Character player, String message) {
        if (player == null || message == null || player.getMapId() != FM_ENTRANCE || isBot(player)) {
            return false;
        }
        if (!isTriggerPhrase(message)) {
            return false;
        }

        MapleMap map = player.getMap();
        Monster boss = findBoss(map, player.getPosition());
        if (boss == null) {
            player.yellowMessage("当前市场没有可攻击的Boss。");
            return true;
        }

        List<Character> attackers = findAttackers(map, boss.getPosition());
        if (attackers.isEmpty()) {
            player.yellowMessage("当前市场没有可用假人。");
            return true;
        }

        ScheduledFuture<?> previous = ACTIVE_BY_MAP.remove(map.getId());
        if (previous != null) {
            previous.cancel(false);
        }

        moveAttackersNearBoss(attackers, boss);
        BotChatbubble(attackers.get(ThreadLocalRandom.current().nextInt(attackers.size())), randomStartLine());
        ScheduledFuture<?> future = ExecutorServiceManager.getScheduledExecutorService().scheduleWithFixedDelay(
                () -> attackTick(player, map, boss),
                800L,
                ATTACK_INTERVAL_MS,
                TimeUnit.MILLISECONDS);
        ACTIVE_BY_MAP.put(map.getId(), future);
        player.yellowMessage("假人已开始集火Boss。");
        return true;
    }

    private static boolean isTriggerPhrase(String message) {
        String normalized = message.trim().toLowerCase(Locale.ROOT).replace(" ", "");
        return normalized.equals("假人打boss")
                || normalized.equals("假人攻击")
                || normalized.equals("攻击boss")
                || normalized.equals("打boss")
                || normalized.equals("botattack");
    }

    private static Monster findBoss(MapleMap map, Point origin) {
        if (map == null || origin == null) {
            return null;
        }
        return map.getAllMonsters().stream()
                .filter(monster -> monster != null && monster.isBoss() && monster.isAlive())
                .min(Comparator.comparingDouble(monster -> monster.getPosition().distanceSq(origin)))
                .orElse(null);
    }

    private static List<Character> findAttackers(MapleMap map, Point bossPosition) {
        Map<Integer, Character> candidates = new LinkedHashMap<>();
        CharacterStorage.getAllBots().values().stream()
                .map(BotSM::getChr)
                .filter(chr -> chr != null)
                .forEach(chr -> candidates.put(chr.getId(), chr));
        map.getAllPlayers().stream()
                .filter(chr -> chr != null && isBot(chr))
                .forEach(chr -> candidates.putIfAbsent(chr.getId(), chr));

        return candidates.values().stream()
                .filter(chr -> isReadyAttacker(chr, map))
                .sorted(Comparator.comparingDouble(chr -> chr.getPosition().distanceSq(bossPosition)))
                .limit(MAX_ATTACKERS)
                .collect(Collectors.toList());
    }

    private static void moveAttackersNearBoss(List<Character> attackers, Monster boss) {
        for (int i = 0; i < attackers.size(); i++) {
            Character bot = attackers.get(i);
            if (bot.getChair() > 0) {
                botCancelChair(bot);
            }
            moveBotToBossFormation(bot, boss, i);
        }
    }

    private static void attackTick(Character owner, MapleMap map, Monster boss) {
        if (shouldStop(map, boss)) {
            stop(map.getId());
            return;
        }

        Character damageOwner = findDamageOwner(owner, map);
        if (damageOwner == null) {
            stop(map.getId());
            return;
        }

        List<Character> attackers = findAttackers(map, boss.getPosition());
        int damage = calculateDamage(boss);
        int index = 0;
        for (Character bot : attackers) {
            if (bot.getChair() > 0) {
                botCancelChair(bot);
            }
            keepBotNearBoss(bot, boss, index++);
            if (!isInAttackRange(bot, boss)) {
                continue;
            }
            botFaceTowardsPoint(bot, boss.getPosition());
            applyBotAttack(damageOwner, bot, boss, damage);
            if (!boss.isAlive()) {
                break;
            }
        }

        if (!boss.isAlive()) {
            stop(map.getId());
        }
    }

    private static void keepBotNearBoss(Character bot, Monster boss, int index) {
        Point target = getFormationTarget(bot, boss, index);
        if (bot.getPosition().distanceSq(target) <= FORMATION_TOLERANCE * FORMATION_TOLERANCE
                && Math.abs(bot.getPosition().y - target.y) <= 25) {
            return;
        }

        long now = System.currentTimeMillis();
        long nextMoveAt = NEXT_MOVE_AT_BY_BOT.getOrDefault(bot.getId(), 0L);
        if (now < nextMoveAt) {
            return;
        }
        NEXT_MOVE_AT_BY_BOT.put(bot.getId(), now + MOVE_REFRESH_MS);

        moveBotToBossFormation(bot, boss, index);
    }

    private static void moveBotToBossFormation(Character bot, Monster boss, int index) {
        if (isBotMoving(bot)) {
            return;
        }
        ExecutorServiceManager.runAsync(() -> {
            Point bossPosition = boss.getPosition();
            Point target = getFormationTarget(bot, boss, index);
            try {
                if (Math.abs(bot.getPosition().y - target.y) <= 80) {
                    BotMoveSmallDistanceX(bot, target);
                } else {
                    pathFinderBeta(bot, target);
                }
            } catch (Exception ignored) {
                // Facing below is enough to keep the visual attack active if pathing fails.
            }
            botFaceTowardsPoint(bot, bossPosition);
        });
    }

    private static Point getFormationTarget(Character bot, Monster boss, int index) {
        Point bossPosition = boss.getPosition();
        int side = (index % 2 == 0) ? -1 : 1;
        int distance = 60 + (index / 2) * 25;
        return findGroundPoint(bot, new Point(bossPosition.x + side * distance, bossPosition.y));
    }

    private static boolean isInAttackRange(Character bot, Monster boss) {
        Point botPosition = bot.getPosition();
        Point bossPosition = boss.getPosition();
        return Math.abs(botPosition.x - bossPosition.x) <= ATTACK_RANGE_X
                && Math.abs(botPosition.y - bossPosition.y) <= ATTACK_RANGE_Y;
    }

    private static void applyBotAttack(Character damageOwner, Character bot, Monster boss, int damage) {
        int visibleDamage = (int) Math.max(1L, Math.min((long) damage, boss.getHp()));
        boolean skillPacketSent = false;
        try {
            skillPacketSent = bossAttack(bot, boss, visibleDamage);
        } catch (Exception ignored) {
            // Keep the boss fight progressing even if a client-side skill packet is not accepted.
        }
        if (!skillPacketSent) {
            damageOwner.getMap().broadcastMessage(PacketCreator.damageMonster(boss.getObjectId(), visibleDamage));
        }
        damageOwner.getMap().damageMonster(damageOwner, boss, damage);
    }

    private static Point findGroundPoint(Character bot, Point target) {
        if (bot == null || bot.getMap() == null || target == null) {
            return target;
        }
        return bot.getMap().calcDropPos(new Point(target.x, target.y), target);
    }

    private static boolean shouldStop(MapleMap map, Monster boss) {
        return map == null
                || boss == null
                || boss.getMap() != map
                || !boss.isBoss()
                || !boss.isAlive();
    }

    private static boolean isReadyAttacker(Character bot, MapleMap map) {
        if (bot == null || !isBot(bot) || bot.getMap() != map || bot.getMapId() != FM_ENTRANCE) {
            return false;
        }
        if (!bot.isAlive()) {
            bot.healHpMp();
        }
        return bot.isAlive();
    }

    private static Character findDamageOwner(Character preferred, MapleMap map) {
        if (isUsableDamageOwner(preferred, map)) {
            return preferred;
        }
        return map.getAllPlayers().stream()
                .filter(chr -> isUsableDamageOwner(chr, map))
                .findFirst()
                .orElse(null);
    }

    private static boolean isUsableDamageOwner(Character chr, MapleMap map) {
        return chr != null
                && !isBot(chr)
                && chr.getMap() == map
                && chr.getMapId() == FM_ENTRANCE;
    }

    private static int calculateDamage(Monster boss) {
        long scaled = Math.max(50_000L, boss.getMaxHp() / 180L);
        return (int) Math.min(2_000_000L, scaled);
    }

    private static void stop(int mapId) {
        ScheduledFuture<?> future = ACTIVE_BY_MAP.remove(mapId);
        if (future != null) {
            future.cancel(false);
        }
        NEXT_MOVE_AT_BY_BOT.clear();
    }

    private static String randomStartLine() {
        return START_LINES[ThreadLocalRandom.current().nextInt(START_LINES.length)];
    }
}
