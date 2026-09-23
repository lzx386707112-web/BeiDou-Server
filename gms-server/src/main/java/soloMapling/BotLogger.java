package soloMapling;

import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;


/*
Shift rightclick in NostalgiaStory direction
Copy below into powershell

powershell -Command "Get-Content -Path 'BotLog.txt' -Wait"

 */

public class BotLogger {
    static final boolean log = false; // BOTLOG-MUTE: soloMapling 日志已关闭，不再写 BotLog.txt/控制台
    private static final String LOG_FILE = "BotLog.txt";
    private static final DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public static void log(String message) {
        if (!log) {
            return;
        }
        LocalDateTime now = LocalDateTime.now();
        String timestamp = now.format(formatter);
        String logMessage = String.format("[%s]: %s", timestamp, message);

        try (PrintWriter out = new PrintWriter(new FileWriter(LOG_FILE, true))) {
            out.println(logMessage);
        } catch (IOException e) {
            // BOTLOG-MUTE: soloMapling 日志已关闭，不打印
        }
    }
}