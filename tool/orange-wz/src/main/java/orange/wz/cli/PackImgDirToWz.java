package orange.wz.cli;

import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzDirectory;
import orange.wz.provider.WzFile;
import orange.wz.provider.WzFolder;
import orange.wz.provider.WzImageFile;
import orange.wz.provider.WzObject;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.stream.Stream;

public final class PackImgDirToWz {
    private PackImgDirToWz() {
    }

    public static void main(String[] args) throws Exception {
        Config config = Config.parse(args);
        Path outputParent = config.output.getParent();
        if (outputParent != null && !Files.isDirectory(outputParent)) {
            Files.createDirectories(outputParent);
        }

        WzFolder folder = new WzFolder(
                config.input.toString(),
                "GMS",
                WzAESConstant.WZ_GMS_IV,
                WzAESConstant.DEFAULT_KEY
        );
        WzFile wzFile = WzFile.createNewFile(
                config.output.toString(),
                config.version,
                "GMS",
                WzAESConstant.WZ_GMS_IV,
                WzAESConstant.DEFAULT_KEY
        );

        Counter counter = new Counter(countImgFiles(config.input));
        System.out.printf(Locale.ROOT,
                "准备打包客户端 IMG 目录: %s%n共发现 %d 个 .img 文件，输出: %s%n",
                config.input,
                counter.totalImages,
                config.output);
        packFolder(folder, wzFile.getWzDirectory(), counter);

        if (!wzFile.save()) {
            throw new IllegalStateException("保存失败: " + config.output);
        }

        System.out.printf(Locale.ROOT,
                "已打包 %d 个 .img，%d 个目录 -> %s (version=%d)%n",
                counter.images,
                counter.directories,
                config.output,
                (int) config.version);
    }

    private static long countImgFiles(Path input) throws Exception {
        try (Stream<Path> paths = Files.walk(input)) {
            return paths.filter(Files::isRegularFile)
                    .filter(path -> path.getFileName().toString().endsWith(".img"))
                    .count();
        }
    }

    private static void packFolder(WzFolder folder, WzDirectory parent, Counter counter) {
        for (WzObject child : folder.getChildren()) {
            if (child instanceof WzFolder subFolder) {
                WzDirectory dir = new WzDirectory(subFolder.getName(), parent, parent.getWzFile());
                packFolder(subFolder, dir, counter);
                if (!parent.addChild(dir)) {
                    throw new IllegalArgumentException("重复目录: " + dir.getPath());
                }
                counter.directories++;
            } else if (child instanceof WzImageFile imageFile) {
                imageFile.setParent(parent);
                if (!imageFile.parse(false)) {
                    throw new IllegalArgumentException("解析 .img 失败: "
                            + imageFile.getFilePath() + " (" + imageFile.getStatus().getMessage() + ")");
                }
                if (!parent.addChild(imageFile)) {
                    throw new IllegalArgumentException("重复 .img: " + imageFile.getPath());
                }
                counter.images++;
                counter.printProgress(imageFile.getFilePath());
            }
        }
    }

    private static final class Counter {
        final long totalImages;
        int images;
        int directories;
        long lastPrintMillis = System.currentTimeMillis();

        Counter(long totalImages) {
            this.totalImages = totalImages;
        }

        void printProgress(String filePath) {
            long now = System.currentTimeMillis();
            if (images == totalImages || images % 500 == 0 || now - lastPrintMillis >= 5000) {
                System.out.printf(Locale.ROOT,
                        "进度: %d/%d .img，当前: %s%n",
                        images,
                        totalImages,
                        filePath);
                lastPrintMillis = now;
            }
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
                    default -> throw new IllegalArgumentException("未知参数: " + arg);
                }
            }

            if (input == null || output == null) {
                usage();
                throw new IllegalArgumentException("--input 和 --output 必填");
            }
            if (!Files.isDirectory(input)) {
                throw new IllegalArgumentException("输入必须是客户端 .img 目录: " + input);
            }
            return new Config(input, output, version);
        }

        private static String requireValue(String[] args, int index, String option) {
            if (index >= args.length || args[index].startsWith("-")) {
                throw new IllegalArgumentException(option + " 需要一个值");
            }
            return args[index];
        }

        private static void usage() {
            System.out.println("""
                    用法:
                      java orange.wz.cli.PackImgDirToWz --input clien/Data/Character --output /tmp/Character.wz --version 83

                    选项:
                      -i, --input    客户端 Data 下包含 .img 的目录，例如 clien/Data/Character
                      -o, --output   输出 .wz 文件
                      --version      WZ 版本，默认 83
                    """);
        }
    }
}
