package soloMapling.FreeMarket;

import org.gms.client.inventory.Equip;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.server.ItemInformationProvider;
import org.gms.server.maps.PlayerShopItem;
import soloMapling.itemPool.ScrolledItemComparator;

import java.io.BufferedReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public class FMShopDescGen {

    static String filePath_FMNameDesc = "soloMapling/FreeMarket/FMNameDesc/";
    static List<String> topFMClans = new ArrayList<>();
    private static final List<String> FALLBACK_IGNS = List.of(
            "小枫", "阿糖", "云鹿", "星橙", "枫眠", "南茶", "北雪", "青竹",
            "白舟", "洛安", "夏宁", "秋澈", "雨遥", "风然", "月梨", "川豆",
            "阿禾", "晚晴", "疏影", "清欢", "拾光", "半夏", "听雨", "折柳",
            "顾南", "沈夜", "林深", "江晚", "苏晚", "陈舟", "陆青", "叶安"
    );

    protected static final Map<String, String> typeToFilePath;

    static {
        typeToFilePath = new HashMap<>();
        typeToFilePath.put("ign", "randomRealMaplestoryIGNs.txt");
        typeToFilePath.put("thief", "thiefDesc.txt");
        typeToFilePath.put("warrior", "warriorDesc.txt");
        typeToFilePath.put("mage", "mageDesc.txt");
        typeToFilePath.put("bowman", "bowmanDesc.txt");
        typeToFilePath.put("chair", "chairDesc.txt");
        typeToFilePath.put("scrolls", "scrollsDesc.txt");
        typeToFilePath.put("useable", "useableDesc.txt");
        typeToFilePath.put("etc", "etcDesc.txt");
        typeToFilePath.put("common", "commonDesc.txt");
        typeToFilePath.put("fmclan", "FMClans.txt");
        typeToFilePath.put("shortword", "shortWordDesc.txt");
        typeToFilePath.put("emojis", "emojiFaces.txt");
    }

    protected static final Map<String, String> ITEM_ACRONYM_MAP = Map.ofEntries(
            // Gloves
            Map.entry("Brown Work Glove", "bwg"),
            Map.entry("Stormcaster Gloves", "scg"),

            // Accessories
            Map.entry("Pink Adventurer Cape", "pac"),
            Map.entry("Facestompers", "fs"),

            // Consumables
            Map.entry("Onyx Apple", "Apples")

            // Armor
    );

    protected static String modifyShopTypeSeperatorText(String currentStr) {
//        trimTertiaryShopDescription(merchant);
//        String currentDesc = merchant.getDescription();
        String replaceString = replaceSeperatorText(currentStr);
        return replaceString;
    }

    protected static String replaceSeperatorText(String str) {
        //        Equips&Stuff
//        White Scrolls
//        Apples&Scrolls
        boolean replaceText = Math.random() < 0.33;
        if (!replaceText) {
            return str;
        }

        // Randomly decide whether to replace with ' ' or '&'
        char replacementChar = new Random().nextBoolean() ? ' ' : '&';

        // Replace all '|' characters with the chosen character
        String replacedString = str.replace('|', replacementChar);
        return replacedString;
    }

    protected static String getRandomQuote() {
//        - meme/quote
//                - video game quotes / reference ("Trinkets, Odds and ends, that sort of thing" - Skyrim)
//                - anime quotes/reference ("Nah I'd Win")

        return null;
    }

    protected static String FMClanAdvertisement() {
        return "【" + getRandomTopFMClan() + "】";
    }

    protected static String randomShortWordsPhrases() {
        String shortWord = getRandomStoreDescription("shortword");
        return shortWord;
    }

    protected static String emojiFaces() {
        String emoji = getRandomStoreDescription("emojis");
        return emoji;
    }

    protected static String cringeDescriptions() {
//        <3
//        I love him/Ilove her/I miss her
        return null;
    }

    protected static String guildRecruitment() {
        // R> Guild
        return null;
    }

    protected static String transformTwoLetterString(String input) {
        if (input == null || input.length() != 2) {
            throw new IllegalArgumentException("Input must be a two-letter string.");
        }

        if (Math.random() < 0.5) { // 50% chance
            return input.substring(0, 1).toUpperCase() + input.substring(1, 2).toLowerCase();
        }
        return input; // Return the original string if the condition is not met
    }

    protected static String advertiseRWTWebsites() {
        return null;
    }

    protected static String advertiseRWTCurrencies() {
        return MarketShopTitles.randomCurrency();
    }

    protected static String getOfferableDescription() {
        return MarketShopTitles.randomOffer();
    }

    protected static String convertToLowerCaseWithChance(String input) {
        if (Math.random() < 0.5) { // 50% chance
            return input.toLowerCase();
        }
        return input; // Return the original string if the chance condition is not met
    }


    protected static String itemNameAcronymConverter(String str) {
        if (str == null || MarketShopTitles.hasLatin(str)) {
            return "";
        }
        return str;
    }


    protected static String trimColorsFromEquipNames(String str) {
        // Define a list of common color names to remove
        List<String> colors = List.of(
                "Dark", "Red", "Blue", "Green", "White", "Black",
                "Purple", "Yellow", "Orange", "Pink", "Silver", "Gold", "Brown"
        );

        // Iterate through the list of colors and remove them from the string
        for (String color : colors) {
            if (str.startsWith(color + " ")) {
                return str.substring(color.length() + 1); // Remove the color and the following space
            }
        }

        return str;
    }


    protected static String trimTextFromItemNames(String str) {
        if (str == null || str.isEmpty()) {
            return str; // Return as is for null or empty input
        }

        // Define the list of words/phrases to remove
        List<String> substringsToRemove = List.of("Dark Scroll ", "Dark scroll ", "Scroll ", "for ", "[Mastery Book] ",
                "Throwing-Knives", "Throwing-Stars");

        // Define the list of special cases to preserve
        List<String> omitList = List.of("White Scroll", "Chaos Scroll");

        // Check if the string contains any omit list item
        for (String omit : omitList) {
            if (str.contains(omit)) {
                return str; // Return original string if it matches any omit condition
            }
        }
        // Iterate over each substring and remove it from the input string
        for (String substring : substringsToRemove) {
            str = str.replace(substring, "").trim();
        }

        return str.trim();
    }

    protected static String advertiseBestEquip(Item bestItem, boolean writeStat) {
        ItemInformationProvider ii = ItemInformationProvider.getInstance();
        int itemId = bestItem.getItemId();
        String itemName = ii.getName(itemId);
        itemName = itemNameAcronymConverter(itemName);
        itemName = trimColorsFromEquipNames(itemName);

        ScrolledItemComparator bestEq = new ScrolledItemComparator((Equip) bestItem);
        int numSuccessfulScrolls = ((Equip) bestItem).getLevel();
        String bestStatName = bestEq.getHighestStatType();
        int highestStatValue = bestEq.getHighestStatValue();

        if (itemName == null || itemName.isBlank()) {
            return MarketShopTitles.randomTitle("common");
        }
        if (numSuccessfulScrolls != 0) {
            if (writeStat) {
                return itemName + MarketShopTitles.statLabel(bestStatName) + highestStatValue;
            }
            return "神砸" + itemName;
        }
        return "未砸" + itemName;
    }

    protected static String getMostExpensiveItemName(HiredMerchantArtificial merchant) {
        String itemName = "";
        int maxValue = 0;
        int mostExpensiveItemId = 0;
        ItemInformationProvider ii = ItemInformationProvider.getInstance();
        for (PlayerShopItem psItem : merchant.getItems()) {
            if (psItem.getItem().getInventoryType() != InventoryType.EQUIP) {
                if (psItem.getPrice() > maxValue) {
                    maxValue = psItem.getPrice();
                    mostExpensiveItemId = psItem.getItem().getItemId();
                }
            }
        }
        itemName = ii.getName(mostExpensiveItemId);
        return trimTextFromItemNames(itemName);
    }

    protected static String advertiseBestEquip(Item bestItem) {
        boolean displayStat = Math.random() < 0.5;
        return advertiseBestEquip(bestItem, displayStat);
    }

    protected static Item getMostExpensiveEquipFromShop(HiredMerchantArtificial merchant) {
        String itemName = "";
        int maxValue = 0;
        ItemInformationProvider ii = ItemInformationProvider.getInstance();
        Item mostExpensiveItem = null;
        for (PlayerShopItem psItem : merchant.getItems()) {
            if (psItem.getItem().getInventoryType() == InventoryType.EQUIP) {
                if (psItem.getPrice() > maxValue) {
                    maxValue = psItem.getPrice();
                    mostExpensiveItem = psItem.getItem();
                }
            }
        }
        return mostExpensiveItem;
    }


    protected static String getRandomTopFMClan() {
        if (topFMClans.isEmpty()) {
            for (int i = 0; i < 7; i++) {
                topFMClans.add(getRandomStoreDescription("fmclan"));
            }
        }
        Random random = new Random();
        int randomIndex = random.nextInt(topFMClans.size());
        return topFMClans.get(randomIndex);
    }

    private static List<String> namePool;
    private static int namePoolIndex = 0;
    private static final List<String> assignedCharacterNames = new ArrayList<>();

    /**
     * Draws a unique name from the pool and registers it as a bot character name.
     * Use this when spawning bot characters.
     */
    public static synchronized String getRandomCharacterIGN() {
        String name = getRandomIGN();
        assignedCharacterNames.add(name);
        return name;
    }

    /**
     * Gets a name for a shop owner. ~35% chance to pick from existing bot character
     * names (simulates an online player's shop), otherwise draws a fresh unique name
     * (simulates an offline player's shop).
     */
    public static synchronized String getRandomShopOwnerIGN() {
        Random rand = new Random();
        if (!assignedCharacterNames.isEmpty() && rand.nextInt(100) < 35) {
            return assignedCharacterNames.get(rand.nextInt(assignedCharacterNames.size()));
        }
        return getRandomIGN();
    }

    /**
     * Core pool draw — hands out one unique name per call. Reloads and reshuffles
     * only when the entire pool is exhausted.
     */
    public static synchronized String getRandomIGN() {
        if (namePool == null || namePool.isEmpty() || namePoolIndex >= namePool.size()) {
            namePool = loadAndShuffleNames();
            namePoolIndex = 0;
        }
        if (namePool.isEmpty()) {
            return FALLBACK_IGNS.get(new Random().nextInt(FALLBACK_IGNS.size()))
                    + (new Random().nextInt(90) + 10);
        }
        return namePool.get(namePoolIndex++);
    }

    private static List<String> loadAndShuffleNames() {
        List<String> names = readLines("ign");
        names.removeIf(line -> line.isEmpty() || line.length() > 12 || MarketShopTitles.hasLatin(line));
        if (names.isEmpty()) {
            names.addAll(FALLBACK_IGNS);
            // BOTLOG-MUTE: MarketBotLog.warn("IGN name file missing or empty; using {} fallback names", names.size());
        } else {
            // BOTLOG-MUTE: MarketBotLog.info("Loaded {} shop/bot IGNs", names.size());
        }
        Collections.shuffle(names);
        return names;
    }

    protected static String resolveFilePath(String type) {
        return filePath_FMNameDesc + typeToFilePath.getOrDefault(type, "");
    }

    protected static String getRandomStoreDescription(String type) {
        List<String> lines = readLines(type);
        lines.removeIf(line -> line.isEmpty() || MarketShopTitles.hasLatin(line));
        if (lines.isEmpty()) {
            return MarketShopTitles.randomTitle(type);
        }
        return lines.get(new Random().nextInt(lines.size()));
    }

    private static List<String> readLines(String type) {
        String fileName = typeToFilePath.getOrDefault(type, "");
        if (fileName.isBlank()) {
            return List.of();
        }
        String classpath = filePath_FMNameDesc + fileName;
        List<String> lines = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(soloMapling.server.SoloMaplingResource.openReader(classpath))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (!line.isEmpty()) {
                    lines.add(line);
                }
            }
        } catch (IOException e) {
            // BOTLOG-MUTE: MarketBotLog.error("Failed to read " + classpath, e);
        }
        return lines;
    }

    protected static String emblemizeFirstLetter(String str) {
        if (str == null || str.isEmpty()) {
            return str; // Return as is if the string is null or empty
        }
        // Surround the first letter with brackets and append the rest of the string
        return "[" + str.charAt(0) + "]" + str.substring(1);
    }

    protected static String asciiBorderString(String str, int maxLineLength) {
        int maxBorderStyleLength = (maxLineLength - str.length()) / 2;

        String borderStyle = selectRandomAsciiBorderCharacters(maxBorderStyleLength);
        if (str == null || str.length() > maxLineLength - 2) {
            throw new IllegalArgumentException("String must be non-null and fit within the max line length with borders.");
        }

        // Calculate the number of border characters needed on each side
        int totalSpaces = maxLineLength - str.length();
        int borderLength = totalSpaces / 2;

        return borderStyle + str + reverseString(borderStyle);
    }

    protected static String selectRandomAsciiBorderCharacters(int maxBorderStyleLength) {
        List<String> borderStyles = new ArrayList<>(List.of("-", "~", "~~", ".:", "*"));
        borderStyles.add("--");
//        borderStyles.add("==");
        borderStyles.add("++");
        borderStyles.add("'~.");

        // Filter the list to only include styles within the length constraint
        List<String> filteredStyles = new ArrayList<>();
        for (String style : borderStyles) {
            if (style.length() <= maxBorderStyleLength) {
                filteredStyles.add(style);
            }
        }

        // If no styles meet the length condition, return an empty string or a default value
        if (filteredStyles.isEmpty()) {
            return ""; // Or a default style like "-" or "N/A"
        }

        // Select a random border style from the filtered list
        Random random = new Random();
        int randomIndex = random.nextInt(filteredStyles.size());
        return filteredStyles.get(randomIndex);
    }

    protected static String reverseString(String str) {
        if (str == null) {
            return null; // Handle null input gracefully
        }
        return new StringBuilder(str).reverse().toString();
    }

    protected static String addSpacesInbetweenLetters(String str) {
        if (str == null || str.length() > 6) {
            return str;
        }

        StringBuilder spacedString = new StringBuilder();
        for (int i = 0; i < str.length(); i++) {
            spacedString.append(str.charAt(i));
            if (i < str.length() - 1) {
                spacedString.append(" "); // Add a space between characters
            }
        }

        return spacedString.toString().toUpperCase();
    }

}
