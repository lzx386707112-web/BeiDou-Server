package orange.wz.cli;

import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzImageFile;
import orange.wz.provider.WzImageProperty;
import orange.wz.provider.properties.WzCanvasProperty;
import orange.wz.provider.properties.WzPngFormat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;

public final class OptimizeImgCanvasCompression {
    private OptimizeImgCanvasCompression() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            throw new IllegalArgumentException("需要参数: outputDir input.img [input.img ...]");
        }
        Path outputDir = Path.of(args[0]);
        Files.createDirectories(outputDir);

        long inputBytes = 0;
        long outputBytes = 0;
        int files = 0;
        int canvases = 0;
        int converted = 0;
        for (Path input : Arrays.stream(args).skip(1).map(Path::of).toList()) {
            Path output = outputDir.resolve(input.getFileName());
            WzImageFile image = open(input);
            int[] optimized = optimize(image.getChildren());
            if (!image.save(output)) throw new IllegalStateException("保存失败: " + output);
            inputBytes += Files.size(input);
            outputBytes += Files.size(output);
            files++;
            canvases += optimized[0];
            converted += optimized[1];
            System.out.printf("%s: canvases=%d converted=%d input=%d output=%d%n",
                    input.getFileName(), optimized[0], optimized[1], Files.size(input), Files.size(output));
        }
        System.out.printf("完成: files=%d canvases=%d converted=%d input=%d output=%d saved=%d ratio=%.2f%%%n",
                files, canvases, converted, inputBytes, outputBytes, inputBytes - outputBytes,
                inputBytes == 0 ? 0 : (inputBytes - outputBytes) * 100.0 / inputBytes);
    }

    private static WzImageFile open(Path path) {
        WzImageFile image = new WzImageFile(path.getFileName().toString(), path.toString(), "",
                WzAESConstant.WZ_GMS_IV, WzAESConstant.DEFAULT_KEY);
        if (!image.parse()) throw new IllegalArgumentException("IMG 解析失败: " + path);
        return image;
    }

    private static int[] optimize(List<WzImageProperty> properties) {
        int count = 0;
        int converted = 0;
        for (WzImageProperty property : properties) {
            if (property instanceof WzCanvasProperty canvas) {
                if (canvas.getFormat() == WzPngFormat.ARGB8888) {
                    canvas.setPng(canvas.getPngImage(false), WzPngFormat.ARGB4444, 0);
                    converted++;
                }
                canvas.optimizeCompression();
                count++;
            }
            List<WzImageProperty> children = property.getChildren();
            if (children != null) {
                int[] childResult = optimize(children);
                count += childResult[0];
                converted += childResult[1];
            }
        }
        return new int[]{count, converted};
    }
}
