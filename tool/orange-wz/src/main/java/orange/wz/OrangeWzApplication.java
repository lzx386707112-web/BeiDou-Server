package orange.wz;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

@SpringBootApplication
public class OrangeWzApplication {

    public static void main(String[] args) {
        boolean guiEnabled = readGuiEnabled(args);
        new SpringApplicationBuilder(OrangeWzApplication.class)
                .headless(!guiEnabled)
                .run(args);
    }

    private static boolean readGuiEnabled(String[] args) {
        String value = null;
        for (String arg : args) {
            if (arg != null && arg.startsWith("--orange.gui.enabled=")) {
                value = arg.substring("--orange.gui.enabled=".length());
            }
        }
        if (value == null) {
            value = System.getProperty("orange.gui.enabled", "true");
        }
        return Boolean.parseBoolean(value);
    }
}
