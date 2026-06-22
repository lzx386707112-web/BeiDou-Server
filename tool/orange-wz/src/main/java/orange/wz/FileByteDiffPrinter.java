package orange.wz;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public class FileByteDiffPrinter {

    public static void main(String[] args) throws IOException {
        printDiff(Path.of("0100100.img"),
                Path.of("0100100.img")
        );
    }

    public static void printDiff(Path file1, Path file2) throws IOException {
        byte[] b1 = Files.readAllBytes(file1);
        byte[] b2 = Files.readAllBytes(file2);

        int maxLen = Math.max(b1.length, b2.length);
        int lineSize = 16;

        int lastDiffOffset = Integer.MIN_VALUE;
        boolean currentDifferent = false;

        for (int offset = 0; offset < maxLen; offset += lineSize) {
            currentDifferent = false;
            // 判断当前行是否有差异
            for (int i = 0; i < lineSize; i++) {
                int idx = offset + i;
                byte v1 = idx < b1.length ? b1[idx] : 0;
                byte v2 = idx < b2.length ? b2[idx] : 0;
                if (v1 != v2) {
                    currentDifferent = true;
                    break;
                }
            }

            // 差异块开始：前一行无差异，当前行有差异
            if (currentDifferent) { // 当前行有差异
                if (lastDiffOffset + lineSize != offset) {
                    System.out.println("//==================Diff 开始================");
                }
                lastDiffOffset = offset;
            } else { // 当前行没有差异
                if (lastDiffOffset + lineSize == offset) {
                    System.out.println("//==================Diff 结束================");
                }
            }

            // 地址
            System.out.printf("%08X  ", offset);

            // 第一个文件
            for (int i = 0; i < lineSize; i++) {
                int idx = offset + i;
                // byte v = idx < b1.length ? b1[idx] : 0;
                // System.out.printf("%02X ", v & 0xFF);
                if (idx < b1.length) {
                    System.out.printf("%02X ", b1[idx] & 0xFF);
                } else {
                    System.out.printf("ZZ ");
                }
            }

            System.out.print(" |  ");

            // 第二个文件
            for (int i = 0; i < lineSize; i++) {
                int idx = offset + i;
                // byte v = idx < b2.length ? b2[idx] : 0;
                // System.out.printf("%02X ", v & 0xFF);
                if (idx < b2.length) {
                    System.out.printf("%02X ", b2[idx] & 0xFF);
                } else {
                    System.out.printf("ZZ ");
                }
            }

            System.out.println();
        }

        if (currentDifferent) {
            System.out.println("//==================Diff 结束================");
        }
    }
}
