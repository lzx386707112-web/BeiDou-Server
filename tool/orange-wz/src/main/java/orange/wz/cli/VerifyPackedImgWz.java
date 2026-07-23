package orange.wz.cli;

import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzHeader;
import orange.wz.provider.tools.WzMutableKey;

import java.io.EOFException;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Independently verifies a packed IMG directory without mapping the complete WZ
 * into a Java ByteBuffer. This is intentionally separate from BinaryReader so
 * files larger than Integer.MAX_VALUE can be checked with 64-bit file positions.
 */
public final class VerifyPackedImgWz {
    private static final long SIGNED_INT_LIMIT = 0x8000_0000L;
    private static final int BUFFER_SIZE = 1024 * 1024;

    private VerifyPackedImgWz() {
    }

    public static void main(String[] args) throws Exception {
        Config config = Config.parse(args);
        byte[] iv = switch (config.region) {
            case "gms" -> WzAESConstant.WZ_GMS_IV;
            case "cms" -> WzAESConstant.WZ_CMS_IV;
            case "latest", "empty" -> WzAESConstant.WZ_EMPTY_IV;
            default -> throw new IllegalArgumentException("未知 region: " + config.region);
        };

        try (Reader reader = new Reader(config.wz, iv)) {
            Header header = reader.readHeader(config.version);
            List<ImageEntry> images = new ArrayList<>();
            Set<Long> visitedDirectories = new HashSet<>();
            reader.position(header.dataStart + 2L);
            readDirectory(reader, header, config.input, Path.of(""), images, visitedDirectories);

            images.sort(Comparator.comparingLong(ImageEntry::offset));
            verifyLayout(images, Files.size(config.wz));
            verifyImages(reader.channel, images);
            printBoundary(images);

            System.out.printf(Locale.ROOT,
                    "验证通过: %d 个 IMG；WZ=%d 字节 (%.3f GiB)；所有目录偏移、源文件大小、校验和及 SHA-256 均一致。%n",
                    images.size(), header.actualSize, header.actualSize / 1024.0 / 1024.0 / 1024.0);
        }
    }

    private static void readDirectory(Reader reader, Header header, Path input, Path relative,
                                      List<ImageEntry> images, Set<Long> visitedDirectories) throws IOException {
        long directoryOffset = reader.position();
        if (!visitedDirectories.add(directoryOffset)) {
            throw new IllegalStateException("目录偏移重复或形成环: " + directoryOffset);
        }

        int count = reader.readCompressedInt();
        if (count < 0 || count > 1_000_000) {
            throw new IllegalStateException("目录条目数异常: offset=" + directoryOffset + ", count=" + count);
        }

        List<DirectoryEntry> subdirectories = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            byte type = reader.readByte();
            String name;
            if (type == 2) {
                int stringOffset = reader.readInt();
                long returnPosition = reader.position();
                reader.position(header.dataStart + Integer.toUnsignedLong(stringOffset));
                type = reader.readByte();
                if (type != 3 && type != 4) {
                    throw new IllegalStateException("字符串引用类型异常: " + type);
                }
                name = reader.readWzString();
                reader.position(returnPosition);
            } else if (type == 3 || type == 4) {
                name = reader.readWzString();
            } else if (type == 1) {
                reader.readInt();
                reader.readShort();
                reader.readOffset(header.dataStart, header.versionHash);
                continue;
            } else {
                throw new IllegalStateException("未知目录类型: " + type + " at " + (reader.position() - 1));
            }

            int size = reader.readCompressedInt();
            int checksum = reader.readCompressedInt();
            long offset = reader.readOffset(header.dataStart, header.versionHash);
            if (type == 3) {
                subdirectories.add(new DirectoryEntry(name, size, checksum, offset));
            } else {
                Path relativeFile = relative.resolve(name);
                images.add(new ImageEntry(relativeFile, input.resolve(relativeFile),
                        Integer.toUnsignedLong(size), checksum, offset));
            }
        }

        for (DirectoryEntry directory : subdirectories) {
            reader.position(directory.offset);
            readDirectory(reader, header, input, relative.resolve(directory.name), images, visitedDirectories);
        }
    }

    private static void verifyLayout(List<ImageEntry> images, long wzSize) {
        long previousEnd = 0;
        for (ImageEntry image : images) {
            if (image.offset < previousEnd) {
                throw new IllegalStateException("IMG 区间重叠或偏移倒退: " + image.relative
                        + ", offset=" + image.offset + ", previousEnd=" + previousEnd);
            }
            long end = image.offset + image.size;
            if (end < image.offset || end > wzSize) {
                throw new IllegalStateException("IMG 超出 WZ: " + image.relative
                        + ", offset=" + image.offset + ", size=" + image.size + ", wzSize=" + wzSize);
            }
            previousEnd = end;
        }
        if (!images.isEmpty() && previousEnd != wzSize) {
            throw new IllegalStateException("最后一个 IMG 末尾与 WZ 文件末尾不一致: imageEnd="
                    + previousEnd + ", wzSize=" + wzSize);
        }
    }

    private static void verifyImages(FileChannel wzChannel, List<ImageEntry> images) throws Exception {
        byte[] sourceBytes = new byte[BUFFER_SIZE];
        byte[] wzBytes = new byte[BUFFER_SIZE];
        for (int index = 0; index < images.size(); index++) {
            ImageEntry image = images.get(index);
            if (!Files.isRegularFile(image.source)) {
                throw new IllegalStateException("源 IMG 不存在: " + image.source);
            }
            long sourceSize = Files.size(image.source);
            if (sourceSize != image.size) {
                throw new IllegalStateException("IMG 大小不一致: " + image.relative
                        + ", directory=" + image.size + ", source=" + sourceSize);
            }

            MessageDigest sourceDigest = MessageDigest.getInstance("SHA-256");
            MessageDigest wzDigest = MessageDigest.getInstance("SHA-256");
            int checksum = 0;
            long remaining = image.size;
            long wzPosition = image.offset;
            try (FileChannel sourceChannel = FileChannel.open(image.source)) {
                while (remaining > 0) {
                    int length = (int) Math.min(BUFFER_SIZE, remaining);
                    readFully(sourceChannel, sourceBytes, length, -1);
                    readFully(wzChannel, wzBytes, length, wzPosition);
                    sourceDigest.update(sourceBytes, 0, length);
                    wzDigest.update(wzBytes, 0, length);
                    for (int i = 0; i < length; i++) {
                        checksum += Byte.toUnsignedInt(wzBytes[i]);
                    }
                    if (Arrays.mismatch(sourceBytes, 0, length, wzBytes, 0, length) >= 0) {
                        throw new IllegalStateException("IMG 字节不一致: " + image.relative
                                + ", wzOffset=" + wzPosition);
                    }
                    remaining -= length;
                    wzPosition += length;
                }
            }
            if (checksum != image.checksum) {
                throw new IllegalStateException("IMG checksum 不一致: " + image.relative
                        + ", directory=" + Integer.toUnsignedString(image.checksum)
                        + ", actual=" + Integer.toUnsignedString(checksum));
            }
            String sourceHash = HexFormat.of().formatHex(sourceDigest.digest());
            String wzHash = HexFormat.of().formatHex(wzDigest.digest());
            if (!sourceHash.equals(wzHash)) {
                throw new IllegalStateException("IMG SHA-256 不一致: " + image.relative);
            }
            if ((index + 1) % 500 == 0 || index + 1 == images.size()) {
                System.out.printf(Locale.ROOT, "验证进度: %d/%d，当前: %s%n",
                        index + 1, images.size(), image.relative);
            }
        }
    }

    private static void readFully(FileChannel channel, byte[] bytes, int length, long position) throws IOException {
        ByteBuffer buffer = ByteBuffer.wrap(bytes, 0, length);
        while (buffer.hasRemaining()) {
            int read = position < 0 ? channel.read(buffer) : channel.read(buffer, position + buffer.position());
            if (read < 0) {
                throw new EOFException();
            }
        }
    }

    private static void printBoundary(List<ImageEntry> images) {
        int boundaryIndex = -1;
        for (int i = 0; i < images.size(); i++) {
            ImageEntry image = images.get(i);
            if (image.offset < SIGNED_INT_LIMIT && image.offset + image.size > SIGNED_INT_LIMIT
                    || image.offset >= SIGNED_INT_LIMIT) {
                boundaryIndex = i;
                break;
            }
        }
        if (boundaryIndex < 0) {
            System.out.println("WZ 未跨过 0x80000000 边界。");
            return;
        }
        System.out.println("0x80000000 边界附近 IMG:");
        for (int i = Math.max(0, boundaryIndex - 2); i <= Math.min(images.size() - 1, boundaryIndex + 2); i++) {
            ImageEntry image = images.get(i);
            System.out.printf(Locale.ROOT, "  %s offset=0x%08X size=%d end=0x%08X%n",
                    image.relative, image.offset, image.size, image.offset + image.size);
        }
    }

    private record DirectoryEntry(String name, int size, int checksum, long offset) {
    }

    private record ImageEntry(Path relative, Path source, long size, int checksum, long offset) {
    }

    private record Header(int dataStart, int versionHash, long actualSize) {
    }

    private record Config(Path input, Path wz, short version, String region) {
        static Config parse(String[] args) {
            Path input = null;
            Path wz = null;
            short version = 83;
            String region = "gms";
            for (int i = 0; i < args.length; i++) {
                switch (args[i]) {
                    case "--input", "-i" -> input = Path.of(args[++i]).toAbsolutePath().normalize();
                    case "--wz" -> wz = Path.of(args[++i]).toAbsolutePath().normalize();
                    case "--version" -> version = Short.parseShort(args[++i]);
                    case "--region" -> region = args[++i].toLowerCase(Locale.ROOT);
                    default -> throw new IllegalArgumentException("未知参数: " + args[i]);
                }
            }
            if (input == null || wz == null) {
                throw new IllegalArgumentException("--input 和 --wz 必填");
            }
            return new Config(input, wz, version, region);
        }
    }

    private static final class Reader implements AutoCloseable {
        private final RandomAccessFile file;
        private final FileChannel channel;
        private final WzMutableKey key;
        private final ByteBuffer primitive = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN);

        Reader(Path path, byte[] iv) throws IOException {
            file = new RandomAccessFile(path.toFile(), "r");
            channel = file.getChannel();
            key = new WzMutableKey(iv, WzAESConstant.DEFAULT_KEY);
        }

        Header readHeader(short version) throws IOException {
            position(0);
            byte[] signature = readBytes(4);
            if (!Arrays.equals(signature, "PKG1".getBytes(StandardCharsets.US_ASCII))) {
                throw new IllegalStateException("不是 PKG1 WZ");
            }
            long declaredDataSize = readLong();
            int dataStart = readInt();
            long actualSize = channel.size();
            if (declaredDataSize + dataStart != actualSize) {
                throw new IllegalStateException("WZ 头大小不一致: declared="
                        + (declaredDataSize + dataStart) + ", actual=" + actualSize);
            }
            position(dataStart);
            short encryptedVersion = readShort();
            WzHeader header = new WzHeader(version);
            int versionHash = header.checkAndGetVersionHash(encryptedVersion, version);
            if (versionHash == 0) {
                throw new IllegalStateException("WZ 版本不匹配: " + version);
            }
            return new Header(dataStart, versionHash, actualSize);
        }

        long position() throws IOException {
            return file.getFilePointer();
        }

        void position(long position) throws IOException {
            if (position < 0 || position > channel.size()) {
                throw new IllegalStateException("文件偏移越界: " + position);
            }
            file.seek(position);
        }

        byte readByte() throws IOException {
            int value = file.read();
            if (value < 0) throw new EOFException();
            return (byte) value;
        }

        byte[] readBytes(int length) throws IOException {
            byte[] bytes = new byte[length];
            file.readFully(bytes);
            return bytes;
        }

        short readShort() throws IOException {
            return (short) readPrimitive(2).getShort();
        }

        int readInt() throws IOException {
            return readPrimitive(4).getInt();
        }

        long readLong() throws IOException {
            return readPrimitive(8).getLong();
        }

        private ByteBuffer readPrimitive(int length) throws IOException {
            primitive.clear();
            primitive.limit(length);
            file.readFully(primitive.array(), 0, length);
            return primitive.position(0);
        }

        int readCompressedInt() throws IOException {
            byte value = readByte();
            return value == Byte.MIN_VALUE ? readInt() : value;
        }

        String readWzString() throws IOException {
            int length = readByte();
            if (length < 0) {
                length = length == Byte.MIN_VALUE ? readInt() : -length;
                byte[] bytes = readBytes(length);
                byte mask = (byte) 0xAA;
                for (int i = 0; i < bytes.length; i++) {
                    bytes[i] = (byte) (bytes[i] ^ key.get(i) ^ mask++);
                }
                return new String(bytes, StandardCharsets.US_ASCII);
            }
            if (length == 0) return "";
            length = length == Byte.MAX_VALUE ? readInt() : length;
            byte[] bytes = readBytes(length * 2);
            short mask = (short) 0xAAAA;
            for (int i = 0; i < bytes.length; i += 2) {
                bytes[i] = (byte) (bytes[i] ^ key.get(i) ^ (mask & 0xFF));
                bytes[i + 1] = (byte) (bytes[i + 1] ^ key.get(i + 1) ^ (mask >> 8));
                mask++;
            }
            return new String(bytes, StandardCharsets.UTF_16LE);
        }

        long readOffset(int dataStart, int versionHash) throws IOException {
            int offset = (int) position();
            offset = ~(offset - dataStart);
            offset *= versionHash;
            offset -= WzAESConstant.WZ_OFFSET_CONSTANT;
            offset = Integer.rotateLeft(offset, offset & 0x1F);
            offset ^= readInt();
            offset += dataStart * 2;
            return Integer.toUnsignedLong(offset);
        }

        @Override
        public void close() throws IOException {
            file.close();
        }
    }
}
