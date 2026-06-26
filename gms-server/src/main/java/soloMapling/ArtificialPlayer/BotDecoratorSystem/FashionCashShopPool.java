package soloMapling.ArtificialPlayer.BotDecoratorSystem;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class FashionCashShopPool {
    private static final String SCRIPT_PATH = "gms-server/scripts-zh-CN/BeiDouSpecial/时尚点装.js";
    private static final String SCRIPT_RESOURCE = "scripts-zh-CN/BeiDouSpecial/时尚点装.js";
    private static final Pattern ARRAY_BLOCK = Pattern.compile("var\\s+(\\w+)\\s*=\\s*Array\\((.*?)\\);", Pattern.DOTALL);
    private static final Pattern ITEM_ID = Pattern.compile("Array\\s*\\(\\s*(\\d{7})\\s*,");
    private static final Map<String, String[]> SCRIPT_ARRAY_TO_CATEGORIES = Map.of(
            "wq", new String[]{"weapons"},
            "yf", new String[]{"tops"},
            "kz", new String[]{"bottoms"},
            "tz", new String[]{"overalls"},
            "st", new String[]{"gloves"},
            "xz", new String[]{"shoes"},
            "sp", new String[]{"rings"},
            "mz", new String[]{"caps"},
            "dm", new String[]{"caps"}
    );

    private FashionCashShopPool() {
    }

    static int applyTo(Map<String, List<NXItemPool.PoolItem>> pools) {
        String script = readScript();
        if (script == null || script.isEmpty()) {
            return 0;
        }

        Map<String, List<NXItemPool.PoolItem>> parsed = parse(script);
        int count = 0;
        for (Map.Entry<String, List<NXItemPool.PoolItem>> entry : parsed.entrySet()) {
            if (entry.getValue().isEmpty()) {
                continue;
            }
            pools.put(entry.getKey(), entry.getValue());
            count += entry.getValue().size();
        }
        if (count > 0) {
            System.out.println("[FashionCashShopPool] Loaded " + count + " items from 时尚点装.js");
        }
        return count;
    }

    private static Map<String, List<NXItemPool.PoolItem>> parse(String script) {
        Map<String, List<NXItemPool.PoolItem>> result = new HashMap<>();
        Matcher blockMatcher = ARRAY_BLOCK.matcher(stripLineComments(script));
        while (blockMatcher.find()) {
            String arrayName = blockMatcher.group(1);
            String[] categories = SCRIPT_ARRAY_TO_CATEGORIES.get(arrayName);
            if (categories == null) {
                continue;
            }

            Matcher itemMatcher = ITEM_ID.matcher(blockMatcher.group(2));
            while (itemMatcher.find()) {
                int itemId = Integer.parseInt(itemMatcher.group(1));
                for (String category : categories) {
                    result.computeIfAbsent(category, ignored -> new ArrayList<>())
                            .add(new NXItemPool.PoolItem(itemId, NXItemPool.GENDER_UNISEX));
                }
            }
        }
        return result;
    }

    private static String stripLineComments(String script) {
        StringBuilder out = new StringBuilder(script.length());
        for (String line : script.split("\\R")) {
            int commentStart = line.indexOf("//");
            out.append(commentStart >= 0 ? line.substring(0, commentStart) : line).append('\n');
        }
        return out.toString();
    }

    private static String readScript() {
        try {
            Path path = Path.of(SCRIPT_PATH);
            if (Files.exists(path)) {
                return Files.readString(path, StandardCharsets.UTF_8);
            }
        } catch (Exception e) {
            System.err.println("[FashionCashShopPool] Failed to read external script: " + e.getMessage());
        }

        try (InputStream input = FashionCashShopPool.class.getClassLoader().getResourceAsStream(SCRIPT_RESOURCE)) {
            if (input != null) {
                return new String(input.readAllBytes(), StandardCharsets.UTF_8);
            }
        } catch (Exception e) {
            System.err.println("[FashionCashShopPool] Failed to read classpath script: " + e.getMessage());
        }
        return null;
    }
}
