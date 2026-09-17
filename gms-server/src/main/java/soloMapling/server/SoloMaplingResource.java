package soloMapling.server;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileSystem;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Stream;

/**
 * Loads SoloMapling YAML/CSV either from a source-tree checkout or from the
 * packaged classpath. The process working directory is often the repo root or
 * a JAR launch folder, so {@code src/main/java/...} FileReaders fail at runtime.
 */
public final class SoloMaplingResource {
    private SoloMaplingResource() {
    }

    public static Reader openReader(String classpathPath) throws IOException {
        Path disk = resolveExisting(classpathPath);
        if (disk != null && Files.isRegularFile(disk)) {
            return Files.newBufferedReader(disk, StandardCharsets.UTF_8);
        }
        InputStream input = SoloMaplingResource.class.getClassLoader().getResourceAsStream(classpathPath);
        if (input != null) {
            return new InputStreamReader(input, StandardCharsets.UTF_8);
        }
        throw new FileNotFoundException(classpathPath);
    }

    public static Path resolveExisting(String classpathPath) {
        for (Path candidate : diskCandidates(classpathPath)) {
            if (Files.exists(candidate)) {
                return candidate;
            }
        }
        return null;
    }

    public static List<String> listFileStems(String classpathDirectory, String suffix) {
        List<String> fromDisk = listDiskStems(classpathDirectory, suffix);
        if (!fromDisk.isEmpty()) {
            return fromDisk;
        }
        return listClasspathStems(classpathDirectory, suffix);
    }

    private static List<Path> diskCandidates(String classpathPath) {
        Path relative = Paths.get("src", "main", "java").resolve(classpathPath);
        return List.of(
                relative,
                Paths.get("gms-server").resolve(relative),
                Paths.get(classpathPath)
        );
    }

    private static List<String> listDiskStems(String classpathDirectory, String suffix) {
        Path dir = resolveExisting(classpathDirectory);
        List<String> stems = new ArrayList<>();
        if (dir == null || !Files.isDirectory(dir)) {
            return stems;
        }
        try (Stream<Path> stream = Files.list(dir)) {
            stream.map(path -> path.getFileName().toString())
                    .filter(name -> name.endsWith(suffix))
                    .map(name -> name.substring(0, name.length() - suffix.length()))
                    .forEach(stems::add);
        } catch (IOException ignored) {
        }
        return stems;
    }

    private static List<String> listClasspathStems(String classpathDirectory, String suffix) {
        String prefix = classpathDirectory.endsWith("/") ? classpathDirectory : classpathDirectory + "/";
        ClassLoader loader = SoloMaplingResource.class.getClassLoader();
        URL url = loader.getResource(prefix);
        if (url == null) {
            return List.of();
        }
        try {
            if ("file".equals(url.getProtocol())) {
                Path dir = Paths.get(url.toURI());
                List<String> stems = new ArrayList<>();
                try (Stream<Path> stream = Files.list(dir)) {
                    stream.map(path -> path.getFileName().toString())
                            .filter(name -> name.endsWith(suffix))
                            .map(name -> name.substring(0, name.length() - suffix.length()))
                            .forEach(stems::add);
                }
                return stems;
            }
            if ("jar".equals(url.getProtocol())) {
                String spec = url.toExternalForm();
                int bang = spec.indexOf('!');
                URI jarUri = URI.create(spec.substring(0, bang));
                String inside = spec.substring(bang + 1);
                if (inside.startsWith("/")) {
                    inside = inside.substring(1);
                }
                try (FileSystem fs = FileSystems.newFileSystem(jarUri, Collections.emptyMap())) {
                    Path dir = fs.getPath(inside);
                    List<String> stems = new ArrayList<>();
                    try (Stream<Path> stream = Files.list(dir)) {
                        stream.map(path -> path.getFileName().toString())
                                .filter(name -> name.endsWith(suffix))
                                .map(name -> name.substring(0, name.length() - suffix.length()))
                                .forEach(stems::add);
                    }
                    return stems;
                }
            }
        } catch (Exception ignored) {
        }
        return List.of();
    }
}
