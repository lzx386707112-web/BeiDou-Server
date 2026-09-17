package soloMapling.itemPool;
import java.io.IOException;
import java.util.Map;
import com.esotericsoftware.yamlbeans.YamlReader;
import soloMapling.server.SoloMaplingResource;


public class ItemQuantityConfig {
    public static class TierRange {
        public int min;
        public int max;
    }

    public static class ItemType {
        public Map<String, TierRange> tiers;
    }

    public Map<String, ItemType> itemQuantities;


    public static ItemQuantityConfig readYaml(String filePath) {
        try (java.io.Reader source = SoloMaplingResource.openReader(toClasspath(filePath))) {
            YamlReader reader = new YamlReader(source);
            return reader.read(ItemQuantityConfig.class);
        } catch (IOException e) {
            System.err.println("[ItemQuantityConfig] " + e.getMessage());
            return null;
        }
    }

    private static String toClasspath(String filePath) {
        String marker = "soloMapling/";
        int idx = filePath.replace('\\', '/').indexOf(marker);
        return idx >= 0 ? filePath.substring(idx) : "soloMapling/itemPool/itemConfig/itemQuantities.yaml";
    }
}

