package soloMapling.FreeMarket;

import java.util.concurrent.ThreadLocalRandom;
import java.util.regex.Pattern;

final class MarketShopTitles {
    private static final Pattern LATIN = Pattern.compile("[A-Za-z]");

    private static final String[] COMMON = {
            "杂货小店", "路过看看", "低价出货", "随便逛逛", "清仓处理",
            "今日特价", "便宜好货", "来看看货", "小本买卖", "急出一批",
            "友情价出", "打包处理", "走过路过", "别错过", "好货便宜"
    };
    private static final String[] THIEF = {
            "飞镖专卖", "飞镖手套", "盗贼用品", "标类好货", "飞镖便宜出",
            "暗影装备", "飞镖手套店", "盗贼杂货"
    };
    private static final String[] WARRIOR = {
            "战士装备", "力量装专卖", "战士杂货", "近战装备", "力量装便宜"
    };
    private static final String[] MAGE = {
            "法师装备", "智力装专卖", "魔法用品", "法师杂货", "智力装便宜"
    };
    private static final String[] BOWMAN = {
            "弓手装备", "敏捷装专卖", "弓矢专卖", "弓手杂货", "敏捷装便宜"
    };
    private static final String[] CHAIR = {
            "椅子专卖", "好看椅子", "休息椅子", "椅子便宜出", "稀有椅子"
    };
    private static final String[] SCROLLS = {
            "卷轴专卖", "祝福卷便宜", "白卷混沌", "砸卷处理", "卷轴清仓",
            "黑暗卷轴", "成功卷便宜"
    };
    private static final String[] USEABLE = {
            "药水专卖", "消耗品店", "药水便宜", "苹果白卷", "补给小店"
    };
    private static final String[] ETC = {
            "材料处理", "杂物便宜", "其他材料", "材料清仓", "路过出材料"
    };
    private static final String[] CLAN = {
            "枫之商会", "金币联盟", "自由市集", "夜市商行", "红叶商会",
            "南风货栈", "北雪商行", "青竹铺子", "月梨商会", "白舟货行"
    };
    private static final String[] SHORT = {
            "看看", "便宜", "可刀", "秒出", "清仓", "好货", "急出",
            "来看", "别错过", "走过路过"
    };
    private static final String[] EMOJI = {
            "★☆", "※※", "～～", "嘿嘿", "呵呵", "哦豁", "来来"
    };
    private static final String[] OFFER = {
            "可议", "可刀", "留价", "给价", "可小刀", "价好说"
    };
    private static final String[] CURRENCY = {
            "收点券", "收抵用", "收金币", "点券可换", "抵用可议"
    };

    private MarketShopTitles() {
    }

    static boolean hasLatin(String text) {
        return text != null && LATIN.matcher(text).find();
    }

    static String chineseOrFallback(String text) {
        if (text == null || text.isBlank() || hasLatin(text)) {
            return randomTitle("common");
        }
        return text.trim();
    }

    static String randomTitle(String type) {
        String[] pool = switch (type == null ? "common" : type) {
            case "thief" -> THIEF;
            case "warrior" -> WARRIOR;
            case "mage" -> MAGE;
            case "bowman" -> BOWMAN;
            case "chair" -> CHAIR;
            case "scrolls" -> SCROLLS;
            case "useable" -> USEABLE;
            case "etc" -> ETC;
            case "fmclan" -> CLAN;
            case "shortword" -> SHORT;
            case "emojis" -> EMOJI;
            default -> COMMON;
        };
        return pool[ThreadLocalRandom.current().nextInt(pool.length)];
    }

    static String randomOffer() {
        return OFFER[ThreadLocalRandom.current().nextInt(OFFER.length)];
    }

    static String randomCurrency() {
        return CURRENCY[ThreadLocalRandom.current().nextInt(CURRENCY.length)];
    }

    static String welcome(String owner) {
        if (owner != null && !owner.isBlank() && !hasLatin(owner) && owner.length() <= 6) {
            return owner + "的小店";
        }
        return "欢迎光临";
    }

    static String statLabel(String statType) {
        if (statType == null) {
            return "属性";
        }
        return switch (statType) {
            case "watt" -> "物攻";
            case "matt" -> "魔攻";
            case "str" -> "力量";
            case "dex" -> "敏捷";
            case "int" -> "智力";
            case "luk" -> "幸运";
            default -> "属性";
        };
    }
}
