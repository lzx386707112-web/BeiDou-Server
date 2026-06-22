package orange.wz.cli;

import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzDirectory;
import orange.wz.provider.WzFile;
import orange.wz.provider.WzXmlFile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.stream.Stream;

public final class PackXmlToWz {
    private PackXmlToWz() {
    }

    public static void main(String[] args) throws Exception {
        Config config = Config.parse(args);
        Path outputParent = config.output.getParent();
        if (outputParent != null && !Files.isDirectory(outputParent)) {
            Files.createDirectories(outputParent);
        }

        WzFile wzFile = WzFile.createNewFile(
                config.output.toString(),
                config.version,
                "GMS",
                WzAESConstant.WZ_GMS_IV,
                WzAESConstant.DEFAULT_KEY
        );

        List<Path> xmlFiles = collectXmlFiles(config.input);
        if (xmlFiles.isEmpty()) {
            throw new IllegalArgumentException("No .img.xml files found under " + config.input);
        }

        WzDirectory root = wzFile.getWzDirectory();
        for (Path xml : xmlFiles) {
            Path rel = Files.isRegularFile(config.input)
                    ? xml.getFileName()
                    : config.input.relativize(xml);
            addXml(root, wzFile, config.input, rel, xml);
        }

        if (!wzFile.save()) {
            throw new IllegalStateException("Failed to save " + config.output);
        }

        System.out.printf(Locale.ROOT,
                "packed %d .img.xml file(s) -> %s (version=%d)%n",
                xmlFiles.size(),
                config.output,
                (int) config.version);
    }

    private static List<Path> collectXmlFiles(Path input) throws Exception {
        if (Files.isRegularFile(input)) {
            if (!input.getFileName().toString().endsWith(".img.xml")) {
                throw new IllegalArgumentException("Input file must end with .img.xml: " + input);
            }
            return List.of(input);
        }
        try (Stream<Path> paths = Files.walk(input)) {
            List<Path> out = new ArrayList<>();
            paths.filter(Files::isRegularFile)
                    .filter(path -> path.getFileName().toString().endsWith(".img.xml"))
                    .sorted(Comparator.comparing(Path::toString))
                    .forEach(out::add);
            return out;
        }
    }

    private static void addXml(
            WzDirectory root,
            WzFile wzFile,
            Path inputRoot,
            Path rel,
            Path xml
    ) {
        WzDirectory parent = root;
        int nameCount = rel.getNameCount();
        for (int i = 0; i < nameCount - 1; i++) {
            String dirName = rel.getName(i).toString();
            WzDirectory next = parent.getDirectory(dirName);
            if (next == null) {
                next = new WzDirectory(dirName, parent, wzFile);
                parent.addChild(next);
            }
            parent = next;
        }

        String xmlName = rel.getFileName().toString();
        String imgName = xmlName.substring(0, xmlName.length() - ".xml".length());
        WzXmlFile image = new WzXmlFile(
                imgName,
                xml.toString(),
                "GMS",
                WzAESConstant.WZ_GMS_IV,
                WzAESConstant.DEFAULT_KEY
        );
        image.setParent(parent);
        if (!image.parse()) {
            throw new IllegalArgumentException("Failed to parse XML: " + inputRoot.relativize(xml));
        }
        if (!parent.addChild(image)) {
            throw new IllegalArgumentException("Duplicate image name under "
                    + parent.getPath() + ": " + imgName);
        }
    }

    private record Config(Path input, Path output, short version) {
        static Config parse(String[] args) {
            Path input = null;
            Path output = null;
            short version = 83;

            for (int i = 0; i < args.length; i++) {
                String arg = args[i];
                switch (arg) {
                    case "--input", "-i" -> input = Path.of(requireValue(args, ++i, arg)).toAbsolutePath().normalize();
                    case "--output", "-o" -> output = Path.of(requireValue(args, ++i, arg)).toAbsolutePath().normalize();
                    case "--version" -> version = Short.parseShort(requireValue(args, ++i, arg));
                    case "--help", "-h" -> {
                        usage();
                        System.exit(0);
                    }
                    default -> throw new IllegalArgumentException("Unknown argument: " + arg);
                }
            }

            if (input == null || output == null) {
                usage();
                throw new IllegalArgumentException("--input and --output are required");
            }
            if (!Files.exists(input)) {
                throw new IllegalArgumentException("Input does not exist: " + input);
            }
            return new Config(input, output, version);
        }

        private static String requireValue(String[] args, int index, String option) {
            if (index >= args.length || args[index].startsWith("-")) {
                throw new IllegalArgumentException(option + " requires a value");
            }
            return args[index];
        }

        private static void usage() {
            System.out.println("""
                    Usage:
                      java orange.wz.cli.PackXmlToWz --input gms-server/wz/Skill.wz --output /tmp/Skill.wz --version 83

                    Options:
                      -i, --input    Directory containing .img.xml files, or one .img.xml file
                      -o, --output   Output .wz file
                      --version      WZ version hash seed, default: 83
                    """);
        }
    }
}
