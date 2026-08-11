package org.gms.server;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import org.gms.client.inventory.Equip;
import org.gms.constants.inventory.ItemConstants;
import org.gms.util.Randomizer;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Server-authoritative flat-stat cube bonuses stored in Equip.expandAttribute4. */
public final class EquipmentCubeManager {
    private static final int DATA_VERSION = 2;
    private static final int MAX_STORED_BONUS = 10_000;

    private static final Map<Integer, CubeSpec> CUBES = buildCubes();
    private static final List<Stat> WEAPON_STATS = List.of(
            Stat.STR, Stat.DEX, Stat.INT, Stat.LUK, Stat.WATK, Stat.MATK,
            Stat.HP, Stat.MP, Stat.ACC
    );
    private static final List<Stat> ARMOR_STATS = List.of(
            Stat.STR, Stat.DEX, Stat.INT, Stat.LUK, Stat.HP, Stat.MP,
            Stat.WDEF, Stat.MDEF, Stat.ACC, Stat.AVOID, Stat.SPEED, Stat.JUMP
    );
    private static final List<Stat> HIGH_ARMOR_STATS = List.of(
            Stat.STR, Stat.DEX, Stat.INT, Stat.LUK, Stat.WATK, Stat.MATK,
            Stat.HP, Stat.MP, Stat.WDEF, Stat.MDEF, Stat.ACC, Stat.AVOID,
            Stat.SPEED, Stat.JUMP
    );

    public record Roll(int itemId, int cubeItemId, String data, String description,
                       int grade, boolean rankedUp, boolean canKeepOld) {
    }

    private record CubeSpec(int itemId, String name, PotentialGrade maxGrade,
                            int rareRate, int uniqueRate, int legendaryRate,
                            boolean canKeepOld) {
        int upgradeRate(PotentialGrade grade) {
            return switch (grade) {
                case SPECIAL -> rareRate;
                case RARE -> uniqueRate;
                case UNIQUE -> legendaryRate;
                case LEGENDARY -> 0;
            };
        }
    }

    private record Line(Stat stat, int value) {
    }

    private record CubeData(int cubeItemId, PotentialGrade grade, List<Line> lines) {
    }

    private enum PotentialGrade {
        SPECIAL(1, "特殊", 1, 1),
        RARE(2, "稀有", 2, 2),
        UNIQUE(3, "罕见", 3, 4),
        LEGENDARY(4, "传说", 3, 8);

        private final int level;
        private final String label;
        private final int lineCount;
        private final int power;

        PotentialGrade(int level, String label, int lineCount, int power) {
            this.level = level;
            this.label = label;
            this.lineCount = lineCount;
            this.power = power;
        }

        PotentialGrade next() {
            return switch (this) {
                case SPECIAL -> RARE;
                case RARE -> UNIQUE;
                case UNIQUE, LEGENDARY -> LEGENDARY;
            };
        }

        static PotentialGrade fromLevel(int level) {
            for (PotentialGrade grade : values()) {
                if (grade.level == level) {
                    return grade;
                }
            }
            throw new IllegalArgumentException("未知潜能强度：" + level);
        }
    }

    private enum Stat {
        STR("力量") {
            int get(Equip equip) { return equip.getStr(); }
            void set(Equip equip, short value) { equip.setStr(value); }
        },
        DEX("敏捷") {
            int get(Equip equip) { return equip.getDex(); }
            void set(Equip equip, short value) { equip.setDex(value); }
        },
        INT("智力") {
            int get(Equip equip) { return equip.getInt(); }
            void set(Equip equip, short value) { equip.setInt(value); }
        },
        LUK("运气") {
            int get(Equip equip) { return equip.getLuk(); }
            void set(Equip equip, short value) { equip.setLuk(value); }
        },
        WATK("攻击力") {
            int get(Equip equip) { return equip.getWatk(); }
            void set(Equip equip, short value) { equip.setWatk(value); }
        },
        MATK("魔法力") {
            int get(Equip equip) { return equip.getMatk(); }
            void set(Equip equip, short value) { equip.setMatk(value); }
        },
        HP("生命值") {
            int get(Equip equip) { return equip.getHp(); }
            void set(Equip equip, short value) { equip.setHp(value); }
        },
        MP("魔法值") {
            int get(Equip equip) { return equip.getMp(); }
            void set(Equip equip, short value) { equip.setMp(value); }
        },
        WDEF("物理防御") {
            int get(Equip equip) { return equip.getWdef(); }
            void set(Equip equip, short value) { equip.setWdef(value); }
        },
        MDEF("魔法防御") {
            int get(Equip equip) { return equip.getMdef(); }
            void set(Equip equip, short value) { equip.setMdef(value); }
        },
        ACC("命中") {
            int get(Equip equip) { return equip.getAcc(); }
            void set(Equip equip, short value) { equip.setAcc(value); }
        },
        AVOID("回避") {
            int get(Equip equip) { return equip.getAvoid(); }
            void set(Equip equip, short value) { equip.setAvoid(value); }
        },
        SPEED("移动速度") {
            int get(Equip equip) { return equip.getSpeed(); }
            void set(Equip equip, short value) { equip.setSpeed(value); }
        },
        JUMP("跳跃力") {
            int get(Equip equip) { return equip.getJump(); }
            void set(Equip equip, short value) { equip.setJump(value); }
        };

        private final String label;

        Stat(String label) {
            this.label = label;
        }

        abstract int get(Equip equip);

        abstract void set(Equip equip, short value);
    }

    private EquipmentCubeManager() {
    }

    public static boolean isCube(int itemId) {
        return CUBES.containsKey(itemId);
    }

    public static String cubeName(int itemId) {
        CubeSpec spec = CUBES.get(itemId);
        return spec == null ? "未知魔方" : spec.name();
    }

    public static String cubeSummary(int itemId) {
        CubeSpec spec = requireCube(itemId);
        return "最高" + spec.maxGrade().label + "，升阶率 "
                + spec.rareRate() + "%/" + spec.uniqueRate() + "%/"
                + spec.legendaryRate() + "%"
                + (spec.canKeepOld() ? "，可保留原词条" : "");
    }

    public static String cubeSummary(Equip equip, int itemId) {
        CubeSpec spec = requireCube(itemId);
        PotentialGrade grade = currentGrade(equip);
        if (grade.level > spec.maxGrade().level) {
            return "最高" + spec.maxGrade().label + "，当前强度不可使用";
        }
        int rate = grade.level >= spec.maxGrade().level ? 0 : spec.upgradeRate(grade);
        String chance = rate == 0 ? "已达该魔方上限" : "当前升阶率 " + rate + "%";
        return "最高" + spec.maxGrade().label + "，" + chance
                + (spec.canKeepOld() ? "，可保留原词条" : "");
    }

    public static boolean canRoll(Equip equip) {
        return equip != null && isValidData(equip.getExpandAttribute4());
    }

    public static boolean canUseCube(Equip equip, int cubeItemId) {
        if (equip == null || !isValidData(equip.getExpandAttribute4())) {
            return false;
        }
        return currentGrade(equip).level <= requireCube(cubeItemId).maxGrade().level;
    }

    public static Roll roll(Equip equip, int cubeItemId) {
        if (equip == null) {
            throw new IllegalArgumentException("装备不存在");
        }
        return roll(equip.getItemId(), equip.getExpandAttribute4(), cubeItemId,
                Randomizer.nextInt(100));
    }

    static Roll roll(int itemId, String currentData, int cubeItemId) {
        return roll(itemId, currentData, cubeItemId, Randomizer.nextInt(100));
    }

    static Roll roll(int itemId, String currentData, int cubeItemId, int upgradeValue) {
        if (upgradeValue < 0 || upgradeValue >= 100) {
            throw new IllegalArgumentException("魔方升阶判定值超出范围");
        }
        CubeData current = readData(currentData);
        CubeSpec spec = requireCube(cubeItemId);
        PotentialGrade oldGrade = current == null ? PotentialGrade.SPECIAL : current.grade();
        if (oldGrade.level > spec.maxGrade().level) {
            throw new IllegalArgumentException(spec.name() + "最高只能洗练"
                    + spec.maxGrade().label + "强度的装备");
        }
        int upgradeRate = oldGrade.level >= spec.maxGrade().level
                ? 0 : spec.upgradeRate(oldGrade);
        boolean rankedUp = upgradeValue < upgradeRate;
        PotentialGrade nextGrade = rankedUp ? oldGrade.next() : oldGrade;
        List<Stat> pool = statPool(itemId, spec);
        List<Stat> available = new ArrayList<>(pool);
        List<Line> lines = new ArrayList<>(nextGrade.lineCount);
        for (int index = 0; index < nextGrade.lineCount; index++) {
            Stat stat = available.remove(Randomizer.nextInt(available.size()));
            lines.add(new Line(stat, randomValue(stat, nextGrade.power)));
        }
        CubeData data = new CubeData(cubeItemId, nextGrade, List.copyOf(lines));
        String result = describe(data) + (rankedUp ? "（升阶成功）" : "（强度未提升）");
        return new Roll(itemId, cubeItemId, writeData(data), result,
                nextGrade.level, rankedUp, spec.canKeepOld());
    }

    public static void apply(Equip equip, Roll roll) {
        if (equip == null || roll == null || roll.itemId() != equip.getItemId()) {
            throw new IllegalArgumentException("装备已变化，不能应用该魔方结果");
        }
        CubeData next = readData(roll.data());
        if (next == null || next.cubeItemId() != roll.cubeItemId()
                || next.grade().level != roll.grade()) {
            throw new IllegalArgumentException("魔方结果无效");
        }
        applyData(equip, next);
    }

    public static void inherit(Equip source, Equip target) {
        if (source == null || target == null) {
            return;
        }
        CubeData sourceData = readData(source.getExpandAttribute4());
        if (sourceData == null) {
            applyData(target, null);
            return;
        }
        applyData(target, sourceData);
    }

    public static String describe(Equip equip) {
        if (equip == null) {
            return "无装备";
        }
        try {
            CubeData data = readData(equip.getExpandAttribute4());
            return data == null ? "潜能强度：特殊；尚未拥有魔方词条" : describe(data);
        } catch (RuntimeException exception) {
            return "魔方数据异常，请联系管理员";
        }
    }

    static int bonus(Equip equip, String statName) {
        return bonus(equip.getExpandAttribute4(), statName);
    }

    static int bonus(String dataValue, String statName) {
        CubeData data = readData(dataValue);
        if (data == null) {
            return 0;
        }
        Stat expected = Stat.valueOf(statName);
        return data.lines().stream()
                .filter(line -> line.stat() == expected)
                .mapToInt(Line::value)
                .sum();
    }

    static int lineCountForGrade(int grade) {
        return PotentialGrade.fromLevel(grade).lineCount;
    }

    static int powerForGrade(int grade) {
        return PotentialGrade.fromLevel(grade).power;
    }

    static int maxGrade(int cubeItemId) {
        return requireCube(cubeItemId).maxGrade().level;
    }

    static boolean canKeepOld(int cubeItemId) {
        return requireCube(cubeItemId).canKeepOld();
    }

    static int grade(String dataValue) {
        CubeData data = readData(dataValue);
        return data == null ? PotentialGrade.SPECIAL.level : data.grade().level;
    }

    static int upgradeRate(int cubeItemId, int grade) {
        CubeSpec spec = requireCube(cubeItemId);
        PotentialGrade current = PotentialGrade.fromLevel(grade);
        if (current.level >= spec.maxGrade().level) {
            return 0;
        }
        return spec.upgradeRate(current);
    }

    private static void applyData(Equip equip, CubeData next) {
        CubeData current = readData(equip.getExpandAttribute4());
        EnumMap<Stat, Integer> oldValues = totals(current);
        EnumMap<Stat, Integer> newValues = totals(next);
        EnumMap<Stat, Short> replacements = new EnumMap<>(Stat.class);
        for (Stat stat : Stat.values()) {
            int value = replaceValue(stat.get(equip),
                    oldValues.getOrDefault(stat, 0), newValues.getOrDefault(stat, 0));
            replacements.put(stat, (short) value);
        }
        replacements.forEach((stat, value) -> stat.set(equip, value));
        equip.setExpandAttribute4(next == null ? "" : writeData(next));
    }

    private static EnumMap<Stat, Integer> totals(CubeData data) {
        EnumMap<Stat, Integer> result = new EnumMap<>(Stat.class);
        if (data != null) {
            for (Line line : data.lines()) {
                result.merge(line.stat(), line.value(), Integer::sum);
            }
        }
        return result;
    }

    private static List<Stat> statPool(int itemId, CubeSpec spec) {
        if (ItemConstants.isWeapon(itemId)) {
            return WEAPON_STATS;
        }
        return spec.maxGrade() == PotentialGrade.LEGENDARY ? HIGH_ARMOR_STATS : ARMOR_STATS;
    }

    private static PotentialGrade currentGrade(Equip equip) {
        CubeData data = readData(equip.getExpandAttribute4());
        return data == null ? PotentialGrade.SPECIAL : data.grade();
    }

    private static int randomValue(Stat stat, int power) {
        return switch (stat) {
            case HP, MP -> Randomizer.rand(power * 10, power * 20);
            case WDEF, MDEF -> Randomizer.rand(power * 4, power * 8);
            case WATK, MATK -> Randomizer.rand(Math.max(1, (power + 1) / 2), power);
            case ACC, AVOID, SPEED, JUMP -> Randomizer.rand(Math.max(1, power / 2), power);
            default -> Randomizer.rand(power, power * 2);
        };
    }

    static int replaceValue(int current, int oldBonus, int newBonus) {
        int value = current - oldBonus + newBonus;
        if (value < 0 || value > Short.MAX_VALUE) {
            throw new IllegalStateException("魔方属性超出装备属性范围");
        }
        return value;
    }

    static boolean isValidData(String raw) {
        try {
            readData(raw);
            return true;
        } catch (RuntimeException exception) {
            return false;
        }
    }

    private static CubeData readData(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }
        try {
            JSONObject root = JSON.parseObject(raw);
            int version = root.getIntValue("v");
            if (version != 1 && version != DATA_VERSION) {
                throw new IllegalArgumentException("不支持的魔方数据版本");
            }
            int cubeItemId = root.getIntValue("cube");
            requireCube(cubeItemId);
            JSONArray array = root.getJSONArray("lines");
            if (array == null) {
                throw new IllegalArgumentException("魔方词条不存在");
            }
            PotentialGrade grade = version == 1
                    ? legacyGrade(cubeItemId, array.size())
                    : PotentialGrade.fromLevel(root.getIntValue("grade"));
            if (array.size() != grade.lineCount) {
                throw new IllegalArgumentException("魔方词条数量错误");
            }
            List<Line> lines = new ArrayList<>(array.size());
            for (int index = 0; index < array.size(); index++) {
                JSONObject entry = array.getJSONObject(index);
                Stat stat = Stat.valueOf(entry.getString("stat"));
                int value = entry.getIntValue("value");
                if (value <= 0 || value > MAX_STORED_BONUS) {
                    throw new IllegalArgumentException("魔方词条数值错误");
                }
                lines.add(new Line(stat, value));
            }
            return new CubeData(cubeItemId, grade, List.copyOf(lines));
        } catch (RuntimeException exception) {
            throw new IllegalArgumentException("无法解析装备魔方数据", exception);
        }
    }

    private static String writeData(CubeData data) {
        JSONObject root = new JSONObject();
        root.put("v", DATA_VERSION);
        root.put("cube", data.cubeItemId());
        root.put("grade", data.grade().level);
        JSONArray lines = new JSONArray();
        for (Line line : data.lines()) {
            JSONObject entry = new JSONObject();
            entry.put("stat", line.stat().name());
            entry.put("value", line.value());
            lines.add(entry);
        }
        root.put("lines", lines);
        return root.toJSONString();
    }

    private static String describe(CubeData data) {
        StringBuilder result = new StringBuilder();
        CubeSpec spec = requireCube(data.cubeItemId());
        result.append("潜能强度：").append(data.grade().label).append("；")
                .append(spec.name()).append("：");
        for (int index = 0; index < data.lines().size(); index++) {
            if (index > 0) {
                result.append("；");
            }
            Line line = data.lines().get(index);
            result.append(line.stat().label).append("+").append(line.value());
        }
        return result.toString();
    }

    private static PotentialGrade legacyGrade(int cubeItemId, int lineCount) {
        int expected = switch (cubeItemId) {
            case 4007000, 4007001 -> 1;
            case 4007002, 4007003, 4007004 -> 2;
            case 4007005, 4007006, 4007007 -> 3;
            default -> throw new IllegalArgumentException("未知旧版魔方道具：" + cubeItemId);
        };
        if (lineCount != expected) {
            throw new IllegalArgumentException("旧版魔方词条数量错误");
        }
        return PotentialGrade.fromLevel(expected);
    }

    private static CubeSpec requireCube(int itemId) {
        CubeSpec spec = CUBES.get(itemId);
        if (spec == null) {
            throw new IllegalArgumentException("未知魔方道具：" + itemId);
        }
        return spec;
    }

    private static Map<Integer, CubeSpec> buildCubes() {
        Map<Integer, CubeSpec> result = new LinkedHashMap<>();
        addCube(result, 4007000, "奇幻魔方", PotentialGrade.UNIQUE, 12, 6, 0, false);
        addCube(result, 4007001, "白金奇幻魔方", PotentialGrade.LEGENDARY, 20, 10, 3, false);
        addCube(result, 4007002, "超级奇幻魔方", PotentialGrade.UNIQUE, 18, 8, 0, false);
        addCube(result, 4007003, "星星魔方", PotentialGrade.UNIQUE, 20, 10, 0, false);
        addCube(result, 4007004, "太阳魔方", PotentialGrade.LEGENDARY, 25, 12, 4, false);
        addCube(result, 4007005, "传说魔方", PotentialGrade.LEGENDARY, 18, 8, 2, false);
        addCube(result, 4007006, "红色魔方", PotentialGrade.LEGENDARY, 15, 6, 1, false);
        addCube(result, 4007007, "黑色魔方", PotentialGrade.LEGENDARY, 20, 8, 2, true);
        return Map.copyOf(result);
    }

    private static void addCube(Map<Integer, CubeSpec> cubes, int itemId, String name,
                                PotentialGrade maxGrade, int rareRate, int uniqueRate,
                                int legendaryRate, boolean canKeepOld) {
        cubes.put(itemId, new CubeSpec(itemId, name, maxGrade,
                rareRate, uniqueRate, legendaryRate, canKeepOld));
    }
}
