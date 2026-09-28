package soloMapling.ArtificialPlayer;

import org.gms.client.Character;
import org.gms.net.server.Server;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.ArtificialPlayer.BotPartySystem.PartyGrindService;

import java.awt.Point;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 孤儿假人（有角色、没大脑）审计与清理。
 *
 * <p>背景：{@link BotGeneration#createBot} 只负责"建角色 + 放上地图"，
 * 赋 BotSM 类型并启动 FSM 是调用方的事（{@link BotTypeManager#setAndStartBots}）。
 * 一旦调用方漏了这一步，就会留下一个"有角色、没行为"的假人：
 * <ul>
 *   <li>没有任何 tick —— 永远站桩，不表情、不说话、不移动；</li>
 *   <li>不在 {@link CharacterStorage} 里 —— 后台"活跃假人"统计看不到它；</li>
 *   <li>不在任何系统的清理名单里 —— 只能靠重启服务器消失。</li>
 * </ul>
 * 已知会漏掉这一步的调用方：GM 指令 {@code !bot create} / {@code !bot masscreate}
 * （{@code BotTypeManager.createBots} / {@code massCreateBots} 只调 createBot），
 * 以及 {@code setAndStartBots} 中 {@code createAndSetBot} 抛异常的单只假人。
 *
 * <p>本类只做只读审计和显式清理，不参与任何自动生成/自动删除流程。
 */
public final class BotOrphanAudit {

    private static final int NAME_COLUMN = 14;

    private BotOrphanAudit() {
    }

    /**
     * 孤儿判定：是假人角色、挂着 mock client、在图上，但没有注册 BotSM。
     * 与 {@link BotHelpers#isBot} 保持同一套"假人"定义，避免误伤真玩家。
     */
    public static boolean isOrphan(Character chr) {
        return chr != null
                && BotHelpers.isBot(chr)
                && chr.getClient() != null
                && chr.getMap() != null
                && CharacterStorage.getBotById(chr.getId()) == null;
    }

    /** 当前地图上的全部假人角色。 */
    public static List<Character> botsOnMap(MapleMap map) {
        List<Character> out = new ArrayList<>();
        if (map == null) {
            return out;
        }
        try {
            for (Character chr : map.getAllPlayers()) {
                if (chr != null && BotHelpers.isBot(chr)) {
                    out.add(chr);
                }
            }
        } catch (Throwable ignored) {
        }
        out.sort(Comparator.comparingInt(Character::getId));
        return out;
    }

    /** 全服（所有世界/频道）的假人角色。 */
    public static List<Character> allBots() {
        List<Character> out = new ArrayList<>();
        try {
            for (var world : Server.getInstance().getWorlds()) {
                if (world == null || world.getPlayerStorage() == null) {
                    continue;
                }
                for (Character chr : world.getPlayerStorage().getAllCharacters()) {
                    if (chr != null && BotHelpers.isBot(chr)) {
                        out.add(chr);
                    }
                }
            }
        } catch (Throwable ignored) {
        }
        out.sort(Comparator.comparingInt(Character::getId));
        return out;
    }

    // ------------------------------------------------------------------
    // 审计报告
    // ------------------------------------------------------------------

    public static void report(Character player) {
        if (player == null) {
            return;
        }
        MapleMap map = player.getMap();

        List<Character> onMap = botsOnMap(map);
        List<Character> mapOrphans = new ArrayList<>();
        for (Character chr : onMap) {
            if (isOrphan(chr)) {
                mapOrphans.add(chr);
            }
        }

        player.yellowMessage("---- 假人孤儿审计 ----");
        player.yellowMessage(String.format("当前地图 %d：假人 %d，其中孤儿 %d",
                map == null ? -1 : map.getId(), onMap.size(), mapOrphans.size()));
        for (Character chr : onMap) {
            player.yellowMessage(describe(chr, isOrphan(chr)));
        }

        List<Character> world = allBots();
        List<Character> worldOrphans = new ArrayList<>();
        Map<String, Integer> typeCount = new LinkedHashMap<>();
        Map<Integer, Integer> orphanMaps = new LinkedHashMap<>();
        for (Character chr : world) {
            BotSM sm = CharacterStorage.getBotById(chr.getId());
            if (sm == null) {
                worldOrphans.add(chr);
                orphanMaps.merge(chr.getMapId(), 1, Integer::sum);
                continue;
            }
            String type = sm.getBotType() == null ? sm.getClass().getSimpleName() : sm.getBotType();
            if (PartyGrindService.isCompanion(chr.getId())) {
                type = type + "(组队基友)";
            }
            typeCount.merge(type, 1, Integer::sum);
        }

        player.yellowMessage(String.format("全服：有行为假人 %d，孤儿 %d", world.size() - worldOrphans.size(), worldOrphans.size()));

        StringBuilder types = new StringBuilder();
        for (Map.Entry<String, Integer> e : typeCount.entrySet()) {
            types.append(e.getKey()).append('x').append(e.getValue()).append("  ");
        }
        player.yellowMessage("类型分布：" + (types.length() == 0 ? "（无）" : types.toString().trim()));

        if (!orphanMaps.isEmpty()) {
            StringBuilder maps = new StringBuilder();
            for (Map.Entry<Integer, Integer> e : orphanMaps.entrySet()) {
                maps.append(e.getKey()).append('x').append(e.getValue()).append("  ");
            }
            player.yellowMessage("孤儿所在地图：" + maps.toString().trim());
            player.yellowMessage("清理：站在目标地图执行 !bot orphanpurge（只清当前地图的孤儿）。");
        }
    }

    private static String describe(Character chr, boolean orphan) {
        String name = pad(chr.getName(), NAME_COLUMN);
        Point pos = chr.getPosition();
        String where = pos == null ? "(?, ?)" : "(" + pos.x + ", " + pos.y + ")";
        if (orphan) {
            return String.format(" ★ %d %s【孤儿-无行为】 %s", chr.getId(), name, where);
        }
        BotSM sm = CharacterStorage.getBotById(chr.getId());
        if (sm == null) {
            return String.format("   %d %s【已停止?】 %s", chr.getId(), name, where);
        }
        String type = sm.getBotType() == null ? sm.getClass().getSimpleName() : sm.getBotType();
        return String.format("   %d %s[%s] run=%s state=%s %s",
                chr.getId(), name, type, sm.getRunning(), sm.getState(), where);
    }

    private static String pad(String value, int width) {
        String text = value == null ? "" : value;
        StringBuilder sb = new StringBuilder(text);
        while (sb.length() < width) {
            sb.append(' ');
        }
        return sb.toString();
    }

    // ------------------------------------------------------------------
    // 清理
    // ------------------------------------------------------------------

    /**
     * 清掉当前地图上的孤儿假人。
     *
     * @return 实际移除的假人数量
     */
    public static int purgeCurrentMap(Character player) {
        if (player == null || player.getMap() == null) {
            return 0;
        }
        return purge(player.getMap(), player);
    }

    /**
     * 清掉指定地图上的孤儿假人。执行者自身不会被移除，注册过 BotSM 的假人也不会。
     *
     * @return 实际移除的假人数量
     */
    public static int purge(MapleMap map, Character executor) {
        if (map == null) {
            return 0;
        }
        int removed = 0;
        for (Character chr : botsOnMap(map)) {
            if (executor != null && chr.getId() == executor.getId()) {
                continue;
            }
            if (!isOrphan(chr)) {
                continue;
            }
            String label = String.format("  - %d %s (%d, %d)",
                    chr.getId(), chr.getName(),
                    chr.getPosition() == null ? 0 : chr.getPosition().x,
                    chr.getPosition() == null ? 0 : chr.getPosition().y);
            try {
                BotGeneration.removeBotFromServer(chr);
                removed++;
                if (executor != null) {
                    executor.yellowMessage(label);
                }
            } catch (Throwable t) {
                if (executor != null) {
                    executor.yellowMessage(label + "  清理失败：" + t.getClass().getSimpleName());
                }
            }
        }
        return removed;
    }

    public static int countOrphans(MapleMap map) {
        int count = 0;
        for (Character chr : botsOnMap(map)) {
            if (isOrphan(chr)) {
                count++;
            }
        }
        return count;
    }
}
