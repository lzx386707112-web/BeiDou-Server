package soloMapling.FreeMarket;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Market dummy / shop diagnostics. Uses SLF4J so lines land in the server log
 * file instead of only System.err / printStackTrace.
 */
public final class MarketBotLog {
    private static final Logger LOG = LoggerFactory.getLogger("MarketBot");

    private MarketBotLog() {
    }

    public static void debug(String message, Object... args) {
        // BOTLOG-MUTE: soloMapling 日志已关闭，不打印
    }

    public static void info(String message, Object... args) {
        // BOTLOG-MUTE: soloMapling 日志已关闭，不打印
    }

    public static void warn(String message, Object... args) {
        // BOTLOG-MUTE: soloMapling 日志已关闭，不打印
    }

    public static void error(String message, Throwable error) {
        // BOTLOG-MUTE: soloMapling 日志已关闭，不打印
    }

    public static void error(String message, Object... args) {
        // BOTLOG-MUTE: soloMapling 日志已关闭，不打印
    }
}
