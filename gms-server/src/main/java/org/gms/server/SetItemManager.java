package org.gms.server;

import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.server.life.Monster;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Server-authoritative set catalog used by the equipment evolution path. */
public final class SetItemManager {
    private static final int[] FINAL_DAMAGE_BY_STAGE = {
            2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 22, 25, 30, 34, 39, 44, 50
    };

    public static final String[] STAT_KEYS = {
            "STR", "DEX", "INT", "LUK", "PAD", "MAD", "PDD", "MDD",
            "ACC", "EVA", "SPD", "JMP", "HP", "MP", "FinalDamage",
            "BossDamage", "ExpRate", "AllStatPct", "HPpct", "MPpct",
            "DropRate", "MesoRate", "StatusRes", "BuffDuration"
    };
    public static final Set<String> SUPPORTED_STAT_KEYS = Set.of(
            "STR", "DEX", "INT", "LUK", "PAD", "MAD", "HP", "MP",
            "FinalDamage", "BossDamage", "ExpRate", "DropRate", "MesoRate");

    public record Tier(int requiredCount, Map<String, Integer> stats) {
    }

    public record Definition(int id, int jobIndex, String name,
                             List<List<Integer>> slots, List<Tier> tiers, String story) {
        public int completeCount() {
            return slots.size();
        }
    }

    public static final class Bonus {
        public static final Bonus NONE = new Bonus();
        private final Map<String, Integer> values = new LinkedHashMap<>();

        private void add(Map<String, Integer> stats) {
            stats.forEach((key, value) -> values.merge(key, value, Integer::sum));
        }

        public int get(String key) {
            return values.getOrDefault(key, 0);
        }
    }

    public record Panel(Definition definition, Set<Integer> equippedIds, int equippedCount, boolean jobEligible) {
        public int activeTier() {
            if (!jobEligible) {
                return -1;
            }
            int active = -1;
            for (int i = 0; i < definition.tiers().size(); i++) {
                if (equippedCount >= definition.tiers().get(i).requiredCount()) {
                    active = i;
                }
            }
            return active;
        }
    }

    public record Result(Bonus bonus, List<Panel> panels) {
    }

    private static final List<Definition> DEFINITIONS = buildDefinitions();

    private SetItemManager() {
    }

    public static Result compute(Character chr) {
        if (chr == null) {
            return new Result(Bonus.NONE, Collections.emptyList());
        }
        Set<Integer> equipped = new LinkedHashSet<>();
        for (Item item : chr.getInventory(InventoryType.EQUIPPED)) {
            if (item.getPosition() < 0 && item.getPosition() > -100) {
                equipped.add(item.getItemId());
            }
        }

        int jobIndex = getJobIndex(chr);
        Bonus total = new Bonus();
        List<Panel> panels = new ArrayList<>();
        List<Definition> definitions = definitions();
        List<Definition> orderedDefinitions = new ArrayList<>(definitions.size());
        for (Definition definition : definitions) {
            if (definition.jobIndex() < 0 || definition.jobIndex() == jobIndex) {
                orderedDefinitions.add(definition);
            }
        }
        for (Definition definition : definitions) {
            if (definition.jobIndex() >= 0 && definition.jobIndex() != jobIndex) {
                orderedDefinitions.add(definition);
            }
        }
        for (Definition definition : orderedDefinitions) {
            int count = 0;
            Set<Integer> matched = new LinkedHashSet<>();
            for (List<Integer> slot : definition.slots()) {
                for (Integer itemId : slot) {
                    if (equipped.contains(itemId)) {
                        count++;
                        matched.add(itemId);
                        break;
                    }
                }
            }
            boolean jobEligible = definition.jobIndex() < 0 || definition.jobIndex() == jobIndex;
            Panel panel = new Panel(definition, matched, count, jobEligible);
            panels.add(panel);
            if (jobEligible) {
                for (Tier tier : definition.tiers()) {
                    if (count >= tier.requiredCount()) {
                        total.add(tier.stats());
                    }
                }
            }
        }
        return new Result(total, Collections.unmodifiableList(panels));
    }

    public static List<Definition> definitions() {
        Map<String, Map<String, Integer>> overrides = SetItemBonusOverrides.snapshot();
        Set<Integer> disabled = SetItemBonusOverrides.disabledBuiltInIds();
        return defaultDefinitions().stream()
                .filter(definition -> !disabled.contains(definition.id()))
                .map(definition -> withOverrides(definition, overrides))
                .toList();
    }

    public static List<Definition> defaultDefinitions() {
        List<Definition> customDefinitions = SetItemBonusOverrides.customDefinitions();
        if (customDefinitions.isEmpty()) {
            return DEFINITIONS;
        }
        List<Definition> result = new ArrayList<>(DEFINITIONS.size() + customDefinitions.size());
        result.addAll(DEFINITIONS);
        result.addAll(customDefinitions);
        return Collections.unmodifiableList(result);
    }

    public static List<Definition> builtInDefinitions() {
        return DEFINITIONS;
    }

    public static List<Definition> catalogDefinitions() {
        Map<String, Map<String, Integer>> overrides = SetItemBonusOverrides.snapshot();
        return defaultDefinitions().stream()
                .map(definition -> withOverrides(definition, overrides))
                .toList();
    }

    public static boolean isBuiltIn(int definitionId) {
        return DEFINITIONS.stream().anyMatch(definition -> definition.id() == definitionId);
    }

    public static boolean isEnabled(int definitionId) {
        return !SetItemBonusOverrides.disabledBuiltInIds().contains(definitionId);
    }

    private static Definition withOverrides(Definition definition,
                                            Map<String, Map<String, Integer>> overrides) {
        List<Tier> tiers = new ArrayList<>(definition.tiers().size());
        boolean changed = false;
        for (Tier tier : definition.tiers()) {
            Map<String, Integer> replacement = overrides.get(
                    SetItemBonusOverrides.key(definition.id(), tier.requiredCount()));
            if (replacement == null) {
                tiers.add(tier);
                continue;
            }
            Map<String, Integer> effective = new LinkedHashMap<>(tier.stats());
            for (Map.Entry<String, Integer> entry : replacement.entrySet()) {
                if (!SUPPORTED_STAT_KEYS.contains(entry.getKey())) {
                    continue;
                }
                if (entry.getValue() == SetItemBonusOverrides.REMOVED_VALUE) {
                    effective.remove(entry.getKey());
                } else {
                    effective.put(entry.getKey(), entry.getValue());
                }
                changed = true;
            }
            tiers.add(new Tier(tier.requiredCount(), Collections.unmodifiableMap(effective)));
        }
        if (!changed) {
            return definition;
        }
        return new Definition(definition.id(), definition.jobIndex(), definition.name(),
                definition.slots(), Collections.unmodifiableList(tiers), definition.story());
    }

    public static int applyDamage(Character chr, Monster monster, int damage) {
        if (chr == null || damage <= 0 || damage == Integer.MAX_VALUE) {
            return damage;
        }
        int percent = chr.getSetItemBonus("FinalDamage");
        if (monster != null && monster.isBoss()) {
            percent += chr.getSetItemBonus("BossDamage");
        }
        long result = Math.round(damage * (100.0 + percent) / 100.0);
        return (int) Math.min(Integer.MAX_VALUE, Math.max(1L, result));
    }

    private static int getJobIndex(Character chr) {
        int niche = Job.getJobStyleInternal(chr.getJob().getId(), (byte) 0).getJobNiche();
        return niche >= 1 && niche <= 5 ? niche - 1 : -1;
    }

    private static List<Definition> buildDefinitions() {
        List<Definition> result = new ArrayList<>();
        int id = 10000;

        String[] sharedNames = {"冒险岛宝石", "冒险岛铂金", "斯泰拉", "传说冒险岛", "专属紫金枫叶", "风暴", "终极", "革命"};
        int[][] sharedArmor = {
                {1003242, 1052357, 1082314, 1072521, 1102294},
                {1003243, 1052358, 1082315, 1072522, 1102295},
                {1003723, 1052553, 1082494, 1072761, 1102502},
                {1003364, 1052405, 1082391, 1072610, 1102322},
                {1003552, 1052461, 1082433, 1072666, 1102441},
                {1003561, 1052467, 1082438, 1072672, 1102467},
                {1003740, 1052569, 1082498, 1072768, 1102506},
                {1003946, 1052647, 1082540, 1072853, 1102612}
        };
        int[][] sharedWeapons = {
                {1302169, 1372096, 1452125, 1332144, 1482098},
                {1302170, 1372097, 1452126, 1332145, 1482099},
                {1302257, 1372169, 1452197, 1332215, 1482160},
                {1302192, 1372117, 1452147, 1332168, 1482120},
                {1302227, 1372139, 1452170, 1332193, 1482140},
                {1302249, 1372162, 1452190, 1332207, 1482152},
                {1302258, 1372170, 1452198, 1332216, 1482161},
                {1302289, 1372188, 1452216, 1332238, 1482179}
        };
        for (int stage = 0; stage < sharedNames.length; stage++) {
            for (int job = 0; job < 5; job++) {
                result.add(definition(id++, job, sharedNames[stage],
                        singleton(sharedWeapons[stage][job]), sharedArmor[stage], stage));
            }
        }

        String[] branchNames = {"120级班·雷昂", "125级班·雷昂", "皇家班·雷昂", "芬撒里尔", "女皇", "战国", "埃苏莱布斯", "神秘之影"};
        int[][] advancedWeapons = {{1302275,1302333,1302297,1302343,1302376,1312153,1312199,1312173,1312203,1312227,1322203,1322250,1322223,1322255,1322283,1402196,1402251,1402220,1402259,1402295,1412135,1412177,1412152,1412181,1412198,1422140,1422184,1422158,1422189,1422210,1432167,1432214,1432187,1432218,1432242,1442223,1442268,1442242,1442274,1442301},{1372177,1372222,1372195,1372228,1372252,1382272,1382259,1382231,1382265,1382289},{1452205,1452252,1452226,1452257,1452287,1462193,1462239,1462213,1462243,1462270},{1332225,1332274,1332247,1332279,1332305,1472214,1472261,1472235,1472265,1472290},{1482168,1482216,1482189,1482221,1482247,1492179,1492231,1492199,1492235,1492261}};
        int[][][] branchItems = {
                {{1302193,1003154,1052299,1082285,1072471,1102262},{1372119,1003155,1052300,1082286,1072472,1102263},{1452149,1003156,1052301,1082287,1072473,1102264},{1332170,1003157,1052302,1082288,1072474,1102265},{1482122,1003158,1052303,1082289,1072475,1102266}},
                {{1302175,1003290,1052384,1082338,1072554,1102312},{1372102,1003291,1052385,1082339,1072555,1102313},{1452131,1003292,1052386,1082340,1072556,1102314},{1332152,1003293,1052387,1082341,1072557,1102315},{1482104,1003294,1052388,1082342,1072558,1102316}},
                {{1302316,1004234,1052804,1082613,1072972,1102713},{1372208,1004235,1052805,1082614,1072973,1102714},{1452239,1004236,1052806,1082615,1072974,1102715},{1332261,1004237,1052807,1082616,1072975,1102716},{1482203,1004238,1052808,1082617,1072976,1102717}},
                {{1302315,1004229,1052799,1082608,1072967,1102718},{1372207,1004230,1052800,1082609,1072968,1102719},{1452238,1004231,1052801,1082610,1072969,1102720},{1332260,1004232,1052802,1082611,1072970,1102721},{1482202,1004233,1052803,1082612,1072971,1102722}},
                {{1302152,1003172,1052314,1082295,1072485,1102275},{1372084,1003173,1052315,1082296,1072486,1102276},{1452111,1003174,1052316,1082297,1072487,1102277},{1332130,1003175,1052317,1082298,1072488,1102278},{1482084,1003176,1052318,1082299,1072489,1102279}},
                {{1302229,1003601,1052509,1082472,1072711,1102456},{1372141,1003603,1052511,1082474,1072713,1102458},{1452172,1003602,1052510,1082473,1072712,1102457},{1332195,1003604,1052512,1082475,1072714,1102459},{1482142,1003605,1052513,1082476,1072715,1102460}},
                {{1302333,1004422,1052882,1082636,1073030,1102775},{1372222,1004423,1052887,1082637,1073032,1102794},{1452252,1004424,1052888,1082638,1073033,1102795},{1332274,1004425,1052889,1082639,1073034,1102796},{1482216,1004426,1052890,1082640,1073035,1102797}},
                {{1302343,1004808,1053063,1082695,1073158,1102940},{1372228,1004809,1053064,1082696,1073159,1102941},{1452257,1004810,1053065,1082697,1073160,1102942},{1332279,1004811,1053066,1082698,1073161,1102943},{1482221,1004812,1053067,1082699,1073162,1102944}}
        };
        for (int stage = 0; stage < branchNames.length; stage++) {
            for (int job = 0; job < 5; job++) {
                int[] items = branchItems[stage][job];
                int[] weapons = switch (stage) {
                    case 3, 4 -> stageWeapons(advancedWeapons[job], 0);
                    case 5, 6 -> stageWeapons(advancedWeapons[job], 1);
                    case 7 -> stageWeapons(advancedWeapons[job], 3);
                    default -> singleton(items[0]);
                };
                result.add(definition(id++, job, branchNames[stage], weapons, Arrays.copyOfRange(items, 1, items.length), stage + 8));
            }
        }

        int[][] visitorWeapons = {{1302147,1312062,1322090,1402090,1412062,1422063,1432081,1442111},{1372078,1382099},{1452106,1462091},{1332120,1472117},{1482079,1492079}};
        int[] visitorArmor = {1003540,1052460,1082432,1072664,1132040};
        for (int job = 0; job < 5; job++) {
            result.add(definition(id++, job, "至尊不速之客·外星人", visitorWeapons[job], visitorArmor, 10));
        }

        int[][] destinyArmor = {{1005980,1042433,1062285,1082760,1073629,1103433,1152212},{1005981,1042434,1062286,1082761,1073630,1103434,1152213},{1005982,1042435,1062287,1082762,1073631,1103435,1152214},{1005983,1042436,1062288,1082763,1073632,1103436,1152215},{1005984,1042437,1062289,1082764,1073633,1103437,1152216}};
        int[][] genesisWeapons = {{1302355,1312213,1322264,1402268,1412189,1422197,1432227,1442285},{1372237,1382274},{1452266,1462252},{1332289,1472275},{1482232,1492245}};
        for (int job = 0; job < 5; job++) {
            int[] finalWeapons = stageWeapons(advancedWeapons[job], 4);
            result.add(definition(id++, job, "天命/创世/永恒", mergeWeapons(finalWeapons, genesisWeapons[job]), destinyArmor[job], 16));
        }

        List<List<Integer>> radianceSlots = Arrays.stream(
                new int[]{1113341,1122447,1143471,1113360,1012911})
                .mapToObj(itemId -> List.of(itemId))
                .toList();
        List<Tier> radianceTiers = List.of(
                new Tier(2, stats("STR", 20, "DEX", 20, "INT", 20, "LUK", 20, "PAD", 20, "MAD", 20, "HP", 500, "BossDamage", 15)),
                new Tier(3, stats("STR", 20, "DEX", 20, "INT", 20, "LUK", 20, "PAD", 20, "MAD", 20, "HP", 500)),
                new Tier(4, stats("STR", 20, "DEX", 20, "INT", 20, "LUK", 20, "PAD", 20, "MAD", 20, "HP", 500)),
                new Tier(5, stats("STR", 20, "DEX", 20, "INT", 20, "LUK", 20, "PAD", 20, "MAD", 20, "HP", 500, "BossDamage", 15))
        );
        result.add(new Definition(id, -1, "无尽辉耀", radianceSlots, radianceTiers,
                "TMS光辉Boss套装的旧端兼容投影。"));
        return Collections.unmodifiableList(result);
    }

    private static Definition definition(int id, int job, String name, int[] weapons, int[] armor, int stage) {
        List<List<Integer>> slots = new ArrayList<>();
        slots.add(Arrays.stream(weapons).boxed().toList());
        for (int itemId : armor) {
            slots.add(List.of(itemId));
        }
        return new Definition(id, job, name, Collections.unmodifiableList(slots), tiers(stage, slots.size()), "随整套进化路线逐步觉醒的装备。套装档位效果可累计。" );
    }

    private static int[] singleton(int value) {
        return new int[]{value};
    }

    private static int[] mergeWeapons(int[] first, int[] second) {
        int[] result = Arrays.copyOf(first, first.length + second.length);
        System.arraycopy(second, 0, result, first.length, second.length);
        return result;
    }

    private static int[] stageWeapons(int[] paths, int stage) {
        int[] result = new int[paths.length / 5];
        for (int path = 0; path < result.length; path++) {
            result[path] = paths[path * 5 + stage];
        }
        return result;
    }

    private static List<Tier> tiers(int stage, int completeCount) {
        int hp = 100 + stage * 75;
        int attack = 2 + stage;
        Map<String, Integer> two = stats("HP", hp, "MP", hp, "ExpRate", stage < 5 ? 5 : 0);
        Map<String, Integer> four = stats("PAD", attack, "MAD", attack, "DropRate", stage >= 5 ? Math.min(15, stage) : 0);
        Map<String, Integer> full = stats("FinalDamage", finalDamageForStage(stage), "BossDamage", stage >= 8 ? (stage - 6) * 2 : 0, "MesoRate", stage >= 5 ? Math.min(12, stage - 2) : 0);
        return List.of(new Tier(2, two), new Tier(4, four), new Tier(completeCount, full));
    }

    static int finalDamageForStage(int stage) {
        int index = Math.max(0, Math.min(stage, FINAL_DAMAGE_BY_STAGE.length - 1));
        return FINAL_DAMAGE_BY_STAGE[index];
    }

    private static Map<String, Integer> stats(Object... values) {
        Map<String, Integer> result = new LinkedHashMap<>();
        for (int i = 0; i < values.length; i += 2) {
            int value = (Integer) values[i + 1];
            if (value != 0) {
                result.put((String) values[i], value);
            }
        }
        return Collections.unmodifiableMap(result);
    }
}
