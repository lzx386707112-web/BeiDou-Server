package soloMapling.Environment;

import java.awt.Point;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * Parses movement packet CSV files and constructs Platform objects.
 *
 * CSV format:
 * - Lines with timestamps (long numbers) are ignored
 * - Lines with single digit numbers (packet counts) are ignored
 * - Movement packets: "0,x,y,..." where x and y are the 2nd and 3rd values
 *
 * Automatically detects whether a platform is FLAT or SLOPED based on Y variance.
 */
public class PlatformParser {

    private static final String BASE_PATH = "src/main/java/soloMapling/ArtificialPlayer/BotMovementSystem/movementDataPackets";
    private static final String RESOURCE_PATH = "soloMapling/ArtificialPlayer/BotMovementSystem/movementDataPackets";
    private static final Map<String, Platform> CACHE = new ConcurrentHashMap<>();
    private static final int FM_ENTRANCE = 910000000;

    /** Y variance threshold to determine if platform is sloped (in pixels) */
    private static final int SLOPE_THRESHOLD = 50;

    /**
     * Parses a movement CSV file and returns the raw list of (x, y) coordinates.
     *
     * @param mapId    The map ID (e.g., 910000000)
     * @param fileName The file name without extension (e.g., "m1")
     * @return List of Point objects representing all recorded coordinates
     */
    public static List<Point> parseCoordinates(int mapId, String fileName) {
        List<Point> coordinates = readCoordinates(mapId, fileName);
        if (coordinates.isEmpty()) {
            coordinates = fallbackCoordinates(mapId, fileName);
        }
        return coordinates;
    }

    /**
     * Parses coordinates and organizes them into a Platform object.
     * Automatically detects if platform is FLAT or SLOPED based on Y variance.
     *
     * @param mapId    The map ID (e.g., 910000000)
     * @param fileName The file name without extension (e.g., "m1")
     * @return Platform object with bounds, type, and sorted reference points
     */
    public static Platform parsePlatform(int mapId, String fileName) {
        String key = mapId + ":" + fileName;
        return CACHE.computeIfAbsent(key, ignored -> organizePlatform(parseCoordinates(mapId, fileName)));
    }

    public static List<String> listPlatformIds(int mapId) {
        String dir = RESOURCE_PATH + "/map" + mapId;
        List<String> ids = new ArrayList<>(soloMapling.server.SoloMaplingResource.listFileStems(dir, ".csv"));
        ids.removeIf(name -> name.contains("/") || "depreciated".equals(name));
        if (ids.isEmpty() && mapId == FM_ENTRANCE) {
            ids.addAll(List.of(
                    "m1", "m2", "m3", "m4", "m5",
                    "c1-2a", "c1-2b", "c1-5a", "c2-1b", "c2-3a",
                    "c3-2a", "c3-4a", "c3-4b", "c4-3b", "c5-1a"
            ));
        }
        return ids;
    }

    /**
     * Parses coordinates into a Platform with explicit type override.
     * Use this if you know the platform type ahead of time.
     *
     * @param mapId    The map ID
     * @param fileName The file name without extension
     * @param type     Explicit platform type (FLAT or SLOPED)
     * @return Platform object
     */
    public static Platform parsePlatform(int mapId, String fileName, Platform.Type type) {
        List<Point> rawCoordinates = parseCoordinates(mapId, fileName);
        return organizePlatform(rawCoordinates, type);
    }

    /**
     * Organizes a raw list of coordinates into a Platform.
     * Automatically detects if platform is FLAT or SLOPED.
     *
     * @param coordinates Raw list of recorded coordinates
     * @return Platform object
     */
    public static Platform organizePlatform(List<Point> coordinates) {
        Platform.Type detectedType = detectPlatformType(coordinates);
        return organizePlatform(coordinates, detectedType);
    }

    /**
     * Organizes a raw list of coordinates into a Platform with explicit type.
     *
     * @param coordinates Raw list of recorded coordinates
     * @param type        Platform type (FLAT or SLOPED)
     * @return Platform object
     */
    public static Platform organizePlatform(List<Point> coordinates, Platform.Type type) {
        if (coordinates == null || coordinates.isEmpty()) {
            return new Platform(0, 0, 0, new ArrayList<>(), type);
        }

        // Deduplicate and sort by X
        List<Point> sortedPoints = coordinates.stream()
                .distinct()
                .sorted(Comparator.comparingInt(p -> p.x))
                .collect(Collectors.toList());

        // Find bounds
        int minX = sortedPoints.get(0).x;
        int maxX = sortedPoints.get(sortedPoints.size() - 1).x;

        // Calculate base Y
        int baseY;
        if (type == Platform.Type.FLAT) {
            // For flat platforms, use the mode (most common Y)
            baseY = calculateModeY(coordinates);
        } else {
            // For sloped platforms, use average Y (informational only)
            baseY = (int) coordinates.stream().mapToInt(p -> p.y).average().orElse(0);
        }

        return new Platform(minX, maxX, baseY, sortedPoints, type);
    }

    /**
     * Detects whether the platform is FLAT or SLOPED based on Y variance.
     */
    private static Platform.Type detectPlatformType(List<Point> coordinates) {
        if (coordinates == null || coordinates.isEmpty()) {
            return Platform.Type.FLAT;
        }

        int minY = coordinates.stream().mapToInt(p -> p.y).min().orElse(0);
        int maxY = coordinates.stream().mapToInt(p -> p.y).max().orElse(0);
        int yRange = maxY - minY;

        return yRange > SLOPE_THRESHOLD ? Platform.Type.SLOPED : Platform.Type.FLAT;
    }

    /**
     * Checks if a line is a timestamp (long number) or packet count (single digit).
     */
    private static boolean isTimestampOrPacketCount(String line) {
        // Single digit = packet count
        if (line.length() == 1 && Character.isDigit(line.charAt(0))) {
            return true;
        }

        // Two digits can also be packet count (e.g., "10", "12")
        if (line.length() == 2 && Character.isDigit(line.charAt(0)) && Character.isDigit(line.charAt(1))) {
            return true;
        }

        // No commas and all digits = timestamp
        if (!line.contains(",")) {
            try {
                Long.parseLong(line);
                return true;
            } catch (NumberFormatException e) {
                return false;
            }
        }

        return false;
    }

    /**
     * Parses a movement packet line and extracts the (x, y) coordinate.
     * Format: "0,x,y,..."
     */
    private static Point parseMovementPacket(String line) {
        String[] parts = line.split(",");
        if (parts.length < 3) {
            return null;
        }

        try {
            int x = Integer.parseInt(parts[1].trim());
            int y = Integer.parseInt(parts[2].trim());
            return new Point(x, y);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /**
     * Calculates the mode (most frequent value) of Y coordinates.
     */
    private static int calculateModeY(List<Point> coordinates) {
        Map<Integer, Integer> frequencyMap = new HashMap<>();

        for (Point p : coordinates) {
            frequencyMap.merge(p.y, 1, Integer::sum);
        }

        return frequencyMap.entrySet().stream()
                .max(Map.Entry.comparingByValue())
                .map(Map.Entry::getKey)
                .orElse(0);
    }

    private static List<Point> readCoordinates(int mapId, String fileName) {
        List<Point> fromDisk = readCoordinateStream(openDiskCsv(mapId, fileName));
        if (!fromDisk.isEmpty()) {
            return fromDisk;
        }
        return readCoordinateStream(openClasspathCsv(mapId, fileName));
    }

    private static List<Point> readCoordinateStream(InputStream input) {
        List<Point> coordinates = new ArrayList<>();
        if (input == null) {
            return coordinates;
        }
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || isTimestampOrPacketCount(line)) {
                    continue;
                }
                Point point = parseMovementPacket(line);
                if (point != null) {
                    coordinates.add(point);
                }
            }
        } catch (IOException ignored) {
        }
        return coordinates;
    }

    private static InputStream openDiskCsv(int mapId, String fileName) {
        Path filePath = soloMapling.server.SoloMaplingResource.resolveExisting(
                RESOURCE_PATH + "/map" + mapId + "/" + fileName + ".csv");
        if (filePath == null || !Files.isRegularFile(filePath)) {
            return null;
        }
        try {
            return Files.newInputStream(filePath);
        } catch (IOException e) {
            return null;
        }
    }

    private static InputStream openClasspathCsv(int mapId, String fileName) {
        String resource = RESOURCE_PATH + "/map" + mapId + "/" + fileName + ".csv";
        return PlatformParser.class.getClassLoader().getResourceAsStream(resource);
    }

    private static List<Point> fallbackCoordinates(int mapId, String fileName) {
        if (mapId != FM_ENTRANCE) {
            return List.of();
        }
        return switch (fileName) {
            case "m1" -> sampleLine(-400, 1400, 34);
            case "m2" -> sampleLine(-400, 1400, -266);
            case "m5" -> sampleLine(-350, 500, 34);
            default -> List.of();
        };
    }

    private static List<Point> sampleLine(int minX, int maxX, int y) {
        List<Point> points = new ArrayList<>();
        for (int x = minX; x <= maxX; x += 80) {
            points.add(new Point(x, y));
        }
        return points;
    }
}
