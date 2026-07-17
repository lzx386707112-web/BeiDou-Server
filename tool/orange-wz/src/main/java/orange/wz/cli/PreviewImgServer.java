package orange.wz.cli;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzImage;
import orange.wz.provider.WzImageFile;
import orange.wz.provider.WzImageProperty;
import orange.wz.provider.properties.*;

import java.io.IOException;
import java.io.OutputStream;
import java.net.BindException;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.stream.Stream;

public final class PreviewImgServer {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final int MAX_TREE_NODES = 6000;
    private static final int PORT_RETRY_COUNT = 20;

    private final Path input;
    private final Region region;
    private final List<String> imgPaths;
    private final Set<String> imgPathSet;
    private final boolean skillMode;
    private final boolean effectMode;
    private final Map<String, Integer> categoryCounts;
    private final Map<String, String> thumbnailCache = new HashMap<>();
    private final Map<String, Boolean> cashCache = new HashMap<>();
    private final LinkedHashMap<String, WzImageFile> cache = new LinkedHashMap<>(32, 0.75f, true) {
        @Override
        protected boolean removeEldestEntry(Map.Entry<String, WzImageFile> eldest) {
            if (size() <= 24) {
                return false;
            }
            eldest.getValue().clear();
            return true;
        }
    };

    private PreviewImgServer(Path input, Region region) throws IOException {
        this.input = input.toAbsolutePath().normalize();
        this.region = region;
        this.imgPaths = indexImages(this.input);
        this.imgPathSet = new HashSet<>(imgPaths);
        this.skillMode = this.input.getFileName() != null
                && "Skill".equalsIgnoreCase(this.input.getFileName().toString());
        this.effectMode = this.input.getFileName() != null
                && "Effect".equalsIgnoreCase(this.input.getFileName().toString());
        this.categoryCounts = countCategories(imgPaths);
    }

    public static void main(String[] args) throws Exception {
        Config config = Config.parse(args);
        PreviewImgServer app = new PreviewImgServer(config.input, config.region);
        ServerBinding binding = createServer(config.port);
        HttpServer server = binding.server;
        server.createContext("/", app::handle);
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.start();
        System.out.printf(Locale.ROOT,
                "IMG 预览服务已启动: http://127.0.0.1:%d/  input=%s  region=%s  images=%d%n",
                binding.port,
                app.input,
                config.region.optionName,
                app.imgPaths.size());
    }

    private static ServerBinding createServer(int startPort) throws IOException {
        BindException lastBindException = null;
        for (int port = startPort; port < startPort + PORT_RETRY_COUNT; port++) {
            try {
                if (port != startPort) {
                    System.out.printf(Locale.ROOT, "端口 %d 已被占用，尝试端口 %d...%n", port - 1, port);
                }
                return new ServerBinding(HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0), port);
            } catch (BindException e) {
                lastBindException = e;
            }
        }
        throw new BindException("端口 " + startPort + "-" + (startPort + PORT_RETRY_COUNT - 1)
                + " 都不可用: " + (lastBindException == null ? "" : lastBindException.getMessage()));
    }

    private static List<String> indexImages(Path input) throws IOException {
        try (Stream<Path> paths = Files.walk(input)) {
            return paths.filter(Files::isRegularFile)
                    .filter(path -> path.getFileName().toString().endsWith(".img"))
                    .map(path -> input.relativize(path).toString().replace('\\', '/'))
                    .sorted()
                    .toList();
        }
    }

    private void handle(HttpExchange exchange) throws IOException {
        try {
            String path = exchange.getRequestURI().getPath();
            if (path.equals("/") || path.equals("/index.html")) {
                write(exchange, 200, "text/html; charset=utf-8", html().getBytes(StandardCharsets.UTF_8));
            } else if (path.equals("/api/meta")) {
                writeJson(exchange, Map.of(
                        "input", input.toString(),
                        "region", region.optionName,
                        "mode", effectMode ? "effect" : skillMode ? "skill" : "equip",
                        "count", imgPaths.size()
                ));
            } else if (path.equals("/api/search")) {
                handleSearch(exchange);
            } else if (path.equals("/api/categories")) {
                handleCategories(exchange);
            } else if (path.equals("/api/items")) {
                handleItems(exchange);
            } else if (path.equals("/api/tree")) {
                handleTree(exchange);
            } else if (path.equals("/api/png")) {
                handlePng(exchange);
            } else if (path.equals("/api/thumb")) {
                handleThumb(exchange);
            } else if (path.equals("/api/wear")) {
                handleWear(exchange);
            } else if (path.equals("/api/effect")) {
                handleEffect(exchange);
            } else {
                writeJson(exchange, 404, Map.of("error", "not found"));
            }
        } catch (Exception e) {
            writeJson(exchange, 500, Map.of("error", e.getMessage() == null ? e.toString() : e.getMessage()));
        } finally {
            exchange.close();
        }
    }

    private static Map<String, Integer> countCategories(List<String> paths) {
        Map<String, Integer> counts = new HashMap<>();
        for (String path : paths) {
            String category = categoryOf(path);
            counts.put(category, counts.getOrDefault(category, 0) + 1);
        }
        return counts;
    }

    private static String categoryOf(String imgPath) {
        String[] parts = imgPath.split("/");
        if (parts.length >= 3 && "Character".equalsIgnoreCase(parts[0])) {
            return parts[1];
        }
        if (parts.length >= 2 && "Effect".equalsIgnoreCase(parts[0])) {
            return switch (parts[1]) {
                case "SetEff.img" -> "SetEffect";
                case "ItemEff.img" -> "ItemEffect";
                default -> idOf(parts[1]);
            };
        }
        if (parts.length >= 2 && "UI".equalsIgnoreCase(parts[0])) {
            return idOf(parts[1]);
        }
        if (parts.length >= 2 && "Etc".equalsIgnoreCase(parts[0])) {
            return idOf(parts[1]);
        }
        if (parts.length >= 2 && "String".equalsIgnoreCase(parts[0])) {
            return idOf(parts[1]) + "String";
        }
        int slash = imgPath.indexOf('/');
        return slash < 0 ? idOf(imgPath) : imgPath.substring(0, slash);
    }

    private static String categoryName(String category) {
        return switch (category) {
            case "Accessory" -> "饰品";
            case "Cap" -> "帽子";
            case "Cape" -> "披风";
            case "Glove" -> "手套";
            case "Longcoat" -> "套服/衣服";
            case "Coat" -> "上衣";
            case "Pants" -> "裤子";
            case "Ring" -> "戒指";
            case "Shoes" -> "鞋子";
            case "Weapon" -> "武器";
            case "Shield" -> "盾牌/副手";
            case "PetEquip" -> "宠物装备";
            case "TamingMob" -> "骑宠";
            case "SetEffect" -> "套装特效";
            case "ItemEffect" -> "物品特效";
            case "ChatBalloon" -> "聊天气泡";
            case "NameTag" -> "名字标签";
            case "Commodity" -> "商城商品表";
            case "EqpString" -> "装备文本";
            case "Body" -> "身体";
            case "Face" -> "脸型";
            case "Hair" -> "发型";
            default -> category;
        };
    }

    private static String categoryKind(String category) {
        return switch (category) {
            case "Accessory", "Cap", "Cape", "Glove", "Longcoat", "Coat", "Pants", "Ring",
                    "Shoes", "Weapon", "Shield", "PetEquip", "TamingMob", "Body", "Face", "Hair" -> "equip";
            default -> "node";
        };
    }

    private static String idOf(String imgPath) {
        String name = imgPath.substring(imgPath.lastIndexOf('/') + 1);
        return name.endsWith(".img") ? name.substring(0, name.length() - 4) : name;
    }

    private void handleSearch(HttpExchange exchange) throws IOException {
        Map<String, String> query = query(exchange);
        String q = query.getOrDefault("q", "").toLowerCase(Locale.ROOT);
        int limit = parseInt(query.get("limit"), 250);
        List<String> results = new ArrayList<>();
        for (String path : imgPaths) {
            if (q.isEmpty() || path.toLowerCase(Locale.ROOT).contains(q)) {
                results.add(path);
                if (results.size() >= limit) {
                    break;
                }
            }
        }
        writeJson(exchange, Map.of("items", results, "total", imgPaths.size()));
    }

    private void handleCategories(HttpExchange exchange) throws IOException {
        if (effectMode) {
            List<Map<String, Object>> categories = imgPaths.stream().map(img -> {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("id", img);
                item.put("name", idOf(img));
                item.put("count", "");
                return item;
            }).toList();
            writeJson(exchange, Map.of("items", categories));
            return;
        }
        if (skillMode) {
            handleSkillCategories(exchange);
            return;
        }
        List<Map<String, Object>> categories = categoryCounts.entrySet().stream()
                .sorted((a, b) -> Integer.compare(categoryOrder(a.getKey()), categoryOrder(b.getKey())) != 0
                        ? Integer.compare(categoryOrder(a.getKey()), categoryOrder(b.getKey()))
                        : a.getKey().compareToIgnoreCase(b.getKey()))
                .map(entry -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", entry.getKey());
                    item.put("name", categoryName(entry.getKey()));
                    item.put("rawName", entry.getKey());
                    item.put("kind", categoryKind(entry.getKey()));
                    item.put("count", entry.getValue());
                    return item;
                })
                .toList();
        writeJson(exchange, Map.of("items", categories));
    }

    private static int categoryOrder(String category) {
        return switch (category) {
            case "Body" -> 0;
            case "Face" -> 1;
            case "Hair" -> 2;
            case "Cap" -> 3;
            case "Accessory" -> 4;
            case "Coat" -> 5;
            case "Longcoat" -> 6;
            case "Pants" -> 7;
            case "Shoes" -> 8;
            case "Glove" -> 9;
            case "Cape" -> 10;
            case "Weapon" -> 11;
            case "Shield" -> 12;
            case "Ring" -> 13;
            case "PetEquip" -> 14;
            case "TamingMob" -> 15;
            case "SetEffect" -> 30;
            case "ItemEffect" -> 31;
            case "ChatBalloon" -> 40;
            case "NameTag" -> 41;
            case "Commodity" -> 50;
            case "EqpString" -> 60;
            default -> 100;
        };
    }

    private void handleItems(HttpExchange exchange) throws IOException {
        if (effectMode) {
            handleEffectItems(exchange);
            return;
        }
        if (skillMode) {
            handleSkillItems(exchange);
            return;
        }
        Map<String, String> query = query(exchange);
        String category = query.getOrDefault("category", "Body");
        if (!"equip".equals(categoryKind(category))) {
            handleNodeItems(exchange, category);
            return;
        }
        String q = query.getOrDefault("q", "").toLowerCase(Locale.ROOT);
        String cashFilter = query.getOrDefault("cash", "all").toLowerCase(Locale.ROOT);
        Boolean cashRequired = switch (cashFilter) {
            case "all" -> null;
            case "cash" -> true;
            case "normal" -> false;
            default -> throw new IllegalArgumentException("未知 cash 筛选: " + cashFilter);
        };
        int offset = parseInt(query.get("offset"), 0);
        int limit = Math.min(parseInt(query.get("limit"), 360), 800);
        List<Map<String, Object>> items = new ArrayList<>();
        int matched = 0;
        for (String path : imgPaths) {
            if (!categoryOf(path).equals(category)) {
                continue;
            }
            String id = idOf(path);
            if (!q.isEmpty()
                    && !id.toLowerCase(Locale.ROOT).contains(q)
                    && !path.toLowerCase(Locale.ROOT).contains(q)) {
                continue;
            }
            boolean cash = isCash(path);
            if (cashRequired != null && cash != cashRequired) {
                continue;
            }
            if (matched >= offset && items.size() < limit) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("img", path);
                item.put("id", id);
                item.put("category", category);
                item.put("typeName", categoryName(category));
                item.put("kind", "equip");
                item.put("cash", cash);
                items.add(item);
            }
            matched++;
        }
        writeJson(exchange, Map.of(
                "items", items,
                "category", category,
                "offset", offset,
                "limit", limit,
                "matched", matched
        ));
    }

    private void handleNodeItems(HttpExchange exchange, String category) throws IOException {
        Map<String, String> query = query(exchange);
        String q = query.getOrDefault("q", "").toLowerCase(Locale.ROOT);
        int offset = parseInt(query.get("offset"), 0);
        int limit = Math.min(parseInt(query.get("limit"), 360), 800);
        List<Map<String, Object>> items = new ArrayList<>();
        int matched = 0;
        for (String img : imgPaths) {
            if (!categoryOf(img).equals(category)) {
                continue;
            }
            WzImageFile image = loadImage(img);
            synchronized (image) {
                for (WzImageProperty child : image.getChildren()) {
                    String id = child.getName();
                    if (!q.isEmpty()
                            && !id.toLowerCase(Locale.ROOT).contains(q)
                            && !img.toLowerCase(Locale.ROOT).contains(q)) {
                        continue;
                    }
                    CanvasCandidate preview = firstCanvas(child.getChildren(), child.getName());
                    if (child instanceof WzCanvasProperty) {
                        preview = new CanvasCandidate(child.getName());
                    }
                    if (preview == null) {
                        continue;
                    }
                    if (matched >= offset && items.size() < limit) {
                        Map<String, Object> item = new LinkedHashMap<>();
                        item.put("img", img);
                        item.put("id", id);
                        item.put("category", category);
                        item.put("typeName", categoryName(category));
                        item.put("kind", "effect");
                        item.put("key", img + "/" + id);
                        item.put("icon", "/api/png?img=" + urlEncode(img) + "&path=" + urlEncode(preview.path()));
                        items.add(item);
                    }
                    matched++;
                }
            }
        }
        writeJson(exchange, Map.of(
                "items", items,
                "category", category,
                "offset", offset,
                "limit", limit,
                "matched", matched
        ));
    }

    private void handleEffectItems(HttpExchange exchange) throws IOException {
        Map<String, String> query = query(exchange);
        String img = query.getOrDefault("category", imgPaths.isEmpty() ? "" : imgPaths.get(0));
        if (!imgPathSet.contains(img)) {
            throw new IllegalArgumentException("找不到 Effect img: " + img);
        }
        String q = query.getOrDefault("q", "").toLowerCase(Locale.ROOT);
        int offset = parseInt(query.get("offset"), 0);
        int limit = Math.min(parseInt(query.get("limit"), 360), 800);
        WzImageFile image = loadImage(img);
        List<Map<String, Object>> items = new ArrayList<>();
        int matched = 0;
        synchronized (image) {
            for (WzImageProperty child : image.getChildren()) {
                String id = child.getName();
                if (!q.isEmpty() && !id.toLowerCase(Locale.ROOT).contains(q)) {
                    continue;
                }
                CanvasCandidate preview = firstCanvas(child.getChildren(), child.getName());
                if (child instanceof WzCanvasProperty) {
                    preview = new CanvasCandidate(child.getName());
                }
                if (preview == null) {
                    continue;
                }
                if (matched >= offset && items.size() < limit) {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("img", img);
                    item.put("id", id);
                    item.put("category", img);
                    item.put("typeName", idOf(img));
                    item.put("kind", "effect");
                    item.put("key", img + "/" + id);
                    item.put("icon", "/api/png?img=" + urlEncode(img) + "&path=" + urlEncode(preview.path()));
                    items.add(item);
                }
                matched++;
            }
        }
        writeJson(exchange, Map.of("items", items, "category", img, "offset", offset,
                "limit", limit, "matched", matched));
    }

    private void handleSkillCategories(HttpExchange exchange) throws IOException {
        List<Map<String, Object>> categories = new ArrayList<>();
        for (String img : imgPaths) {
            int count = countSkillItems(img);
            if (count == 0) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", idOf(img));
            item.put("name", idOf(img));
            item.put("count", count);
            categories.add(item);
        }
        writeJson(exchange, Map.of("items", categories));
    }

    private void handleSkillItems(HttpExchange exchange) throws IOException {
        Map<String, String> query = query(exchange);
        String category = query.getOrDefault("category", imgPaths.isEmpty() ? "" : idOf(imgPaths.get(0)));
        String img = category.endsWith(".img") ? category : category + ".img";
        if (!imgPathSet.contains(img)) {
            throw new IllegalArgumentException("找不到 Skill img: " + category);
        }
        String q = query.getOrDefault("q", "").toLowerCase(Locale.ROOT);
        int offset = parseInt(query.get("offset"), 0);
        int limit = Math.min(parseInt(query.get("limit"), 360), 800);
        WzImageFile image = loadImage(img);
        List<Map<String, Object>> items = new ArrayList<>();
        int matched = 0;
        synchronized (image) {
            WzImageProperty skillRoot = image.getChild("skill");
            List<WzImageProperty> skills = skillRoot == null ? image.getChildren() : skillRoot.getChildren();
            String basePath = skillRoot == null ? "" : "skill/";
            for (WzImageProperty child : skills) {
                SkillIcon icon = skillIcon(child, basePath);
                if (icon == null) {
                    continue;
                }
                String id = child.getName();
                if (!q.isEmpty()
                        && !id.toLowerCase(Locale.ROOT).contains(q)
                        && !img.toLowerCase(Locale.ROOT).contains(q)) {
                    continue;
                }
                if (matched >= offset && items.size() < limit) {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("img", img);
                    item.put("id", id);
                    item.put("category", category);
                    item.put("typeName", category);
                    item.put("kind", "skill");
                    item.put("key", category + "/" + id);
                    item.put("icon", "/api/png?img=" + urlEncode(img) + "&path=" + urlEncode(icon.path()));
                    items.add(item);
                }
                matched++;
            }
        }
        writeJson(exchange, Map.of(
                "items", items,
                "category", category,
                "offset", offset,
                "limit", limit,
                "matched", matched
        ));
    }

    private int countSkillItems(String img) {
        WzImageFile image = loadImage(img);
        int count = 0;
        synchronized (image) {
            WzImageProperty skillRoot = image.getChild("skill");
            List<WzImageProperty> skills = skillRoot == null ? image.getChildren() : skillRoot.getChildren();
            String basePath = skillRoot == null ? "" : "skill/";
            for (WzImageProperty child : skills) {
                if (skillIcon(child, basePath) != null) {
                    count++;
                }
            }
        }
        return count;
    }

    private void handleTree(HttpExchange exchange) throws IOException {
        String img = require(query(exchange), "img");
        WzImageFile image = loadImage(img);
        NodeCounter counter = new NodeCounter();
        List<Map<String, Object>> children = new ArrayList<>();
        synchronized (image) {
            for (WzImageProperty child : image.getChildren()) {
                children.add(node(child, "", counter));
            }
        }
        writeJson(exchange, Map.of(
                "img", img,
                "truncated", counter.truncated,
                "children", children
        ));
    }

    private void handlePng(HttpExchange exchange) throws IOException {
        Map<String, String> query = query(exchange);
        String img = require(query, "img");
        String propPath = require(query, "path");
        WzImageFile image = loadImage(img);
        byte[] bytes;
        synchronized (image) {
            WzImageProperty property = findProperty(image, propPath);
            if (!(property instanceof WzCanvasProperty canvas)) {
                throw new IllegalArgumentException("不是 Canvas 节点: " + propPath);
            }
            bytes = canvas.getImageBytes(false);
        }
        if (bytes == null) {
            throw new IllegalStateException("无法生成 PNG: " + propPath);
        }
        write(exchange, 200, "image/png", bytes);
    }

    private void handleThumb(HttpExchange exchange) throws IOException {
        String img = require(query(exchange), "img");
        String propPath = thumbnailPath(img);
        WzImageFile image = loadImage(img);
        byte[] bytes;
        synchronized (image) {
            WzImageProperty property = findProperty(image, propPath);
            if (!(property instanceof WzCanvasProperty canvas)) {
                throw new IllegalStateException("缩略图不是 Canvas: " + propPath);
            }
            bytes = canvas.getImageBytes(false);
        }
        if (bytes == null) {
            throw new IllegalStateException("无法生成缩略图: " + img);
        }
        write(exchange, 200, "image/png", bytes);
    }

    private void handleWear(HttpExchange exchange) throws IOException {
        Map<String, String> query = query(exchange);
        String img = require(query, "img");
        String category = query.getOrDefault("category", categoryOf(img));
        WzImageFile image = loadImage(img);
        List<WearLayer> layers;
        synchronized (image) {
            layers = wearLayers(image, category);
        }
        layers.sort((a, b) -> {
            int zCompare = Integer.compare(zOrder(a.z), zOrder(b.z));
            return zCompare != 0 ? zCompare : a.path.compareTo(b.path);
        });

        List<Map<String, Object>> out = new ArrayList<>();
        for (WearLayer layer : layers) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("path", layer.path);
            item.put("url", "/api/png?img=" + urlEncode(img) + "&path=" + urlEncode(layer.path));
            item.put("width", layer.width);
            item.put("height", layer.height);
            item.put("originX", layer.originX);
            item.put("originY", layer.originY);
            item.put("z", layer.z);
            out.add(item);
        }
        writeJson(exchange, Map.of(
                "img", img,
                "id", idOf(img),
                "category", category,
                "layers", out
        ));
    }

    private void handleEffect(HttpExchange exchange) throws IOException {
        Map<String, String> query = query(exchange);
        String img = require(query, "img");
        String effectPath = require(query, "path");
        WzImageFile image = loadImage(img);
        List<Map<String, Object>> groups = new ArrayList<>();
        synchronized (image) {
            WzImageProperty effect = findProperty(image, effectPath);
            collectEffectGroups(effect, effectPath, groups);
        }
        writeJson(exchange, Map.of("img", img, "path", effectPath, "groups", groups));
    }

    private static void collectEffectGroups(WzImageProperty property, String path,
                                            List<Map<String, Object>> groups) {
        List<WzImageProperty> children = property.getChildren();
        if (children == null) {
            if (property instanceof WzCanvasProperty canvas) {
                groups.add(effectGroup(path, List.of(canvas), path.substring(0, path.lastIndexOf('/') + 1)));
            }
            return;
        }
        List<WzCanvasProperty> frames = children.stream()
                .filter(WzCanvasProperty.class::isInstance)
                .map(WzCanvasProperty.class::cast)
                .sorted((a, b) -> naturalCompare(a.getName(), b.getName()))
                .toList();
        if (!frames.isEmpty()) {
            groups.add(effectGroup(path, frames, path + "/"));
        }
        for (WzImageProperty child : children) {
            if (!(child instanceof WzCanvasProperty)) {
                collectEffectGroups(child, path + "/" + child.getName(), groups);
            }
        }
    }

    private static Map<String, Object> effectGroup(String path, List<WzCanvasProperty> frames,
                                                    String framePathPrefix) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (WzCanvasProperty canvas : frames) {
            int originX = 0;
            int originY = 0;
            WzImageProperty origin = canvas.getChild("origin");
            if (origin instanceof WzVectorProperty vector) {
                originX = vector.getX();
                originY = vector.getY();
            }
            Map<String, Object> frame = new LinkedHashMap<>();
            String framePath = frames.size() == 1 && path.equals(framePathPrefix.substring(0, framePathPrefix.length() - 1))
                    ? path : framePathPrefix + canvas.getName();
            frame.put("path", framePath);
            frame.put("url", "/api/png?img=" + urlEncode(canvas.getWzImage().getName())
                    + "&path=" + urlEncode(framePath));
            frame.put("delay", intChildValue(canvas, "delay", 100));
            frame.put("width", canvas.getWidth());
            frame.put("height", canvas.getHeight());
            frame.put("originX", originX);
            frame.put("originY", originY);
            out.add(frame);
        }
        return Map.of("path", path, "frames", out);
    }

    private static int intChildValue(WzImageProperty property, String name, int defaultValue) {
        WzImageProperty child = property.getChild(name);
        return child instanceof WzIntProperty value ? value.getValue() : defaultValue;
    }

    private static int naturalCompare(String left, String right) {
        try {
            return Integer.compare(Integer.parseInt(left), Integer.parseInt(right));
        } catch (NumberFormatException ignored) {
            return left.compareToIgnoreCase(right);
        }
    }

    private synchronized WzImageFile loadImage(String rel) {
        if (!imgPathSet.contains(rel)) {
            throw new IllegalArgumentException("img 不在输入目录内: " + rel);
        }
        WzImageFile cached = cache.get(rel);
        if (cached != null) {
            return cached;
        }
        Path file = input.resolve(rel).normalize();
        if (!file.startsWith(input)) {
            throw new IllegalArgumentException("非法路径: " + rel);
        }
        WzImageFile image = new WzImageFile(file.getFileName().toString(), file.toString(),
                region.keyBoxName, region.iv, WzAESConstant.DEFAULT_KEY);
        if (!image.parse()) {
            throw new IllegalArgumentException("解析失败: " + rel + " (" + image.getStatus().getMessage() + ")");
        }
        cache.put(rel, image);
        return image;
    }

    private synchronized boolean isCash(String img) {
        Boolean cached = cashCache.get(img);
        if (cached != null) {
            return cached;
        }
        WzImageFile image = loadImage(img);
        boolean cash;
        synchronized (image) {
            cash = cashValue(image) != 0;
        }
        cashCache.put(img, cash);
        return cash;
    }

    private static int cashValue(WzImage image) {
        WzImageProperty info = image.getChild("info");
        if (info == null) {
            return 0;
        }
        WzImageProperty cash = info.getChild("cash");
        if (cash instanceof WzIntProperty intProperty) {
            return intProperty.getValue();
        }
        if (cash instanceof WzStringProperty stringProperty) {
            return parseInt(stringProperty.getValue(), 0);
        }
        return 0;
    }

    private synchronized String thumbnailPath(String img) {
        String cached = thumbnailCache.get(img);
        if (cached != null) {
            return cached;
        }
        WzImageFile image = loadImage(img);
        for (String preferred : List.of("info/icon", "info/iconRaw", "info/iconD", "stand1/0/body", "walk1/0/body")) {
            WzImageProperty property = findPropertyOrNull(image, preferred);
            if (property instanceof WzCanvasProperty) {
                thumbnailCache.put(img, preferred);
                return preferred;
            }
        }
        CanvasCandidate candidate = firstCanvas(image.getChildren(), "");
        if (candidate == null) {
            throw new IllegalArgumentException("找不到可预览 Canvas: " + img);
        }
        thumbnailCache.put(img, candidate.path);
        return candidate.path;
    }

    private static List<WearLayer> wearLayers(WzImage image, String category) {
        for (String rootPath : wearRootCandidates(category)) {
            WzImageProperty root = findPropertyOrNull(image, rootPath);
            if (root == null) {
                continue;
            }
            List<WearLayer> layers = new ArrayList<>();
            collectWearLayers(root, rootPath, layers);
            if (!layers.isEmpty()) {
                return layers;
            }
        }
        return new ArrayList<>();
    }

    private static List<String> wearRootCandidates(String category) {
        return switch (category) {
            case "Body" -> List.of("stand1/0", "stand2/0", "walk1/0", "walk2/0");
            case "Face" -> List.of("default", "blink/0", "smile/0");
            case "Hair" -> List.of("default", "stand1/0", "walk1/0");
            case "TamingMob" -> List.of("stand/0", "move/0", "fly/0");
            default -> List.of("stand1/0", "stand2/0", "walk1/0", "default/0", "0");
        };
    }

    private static void collectWearLayers(WzImageProperty property, String path, List<WearLayer> layers) {
        if (property instanceof WzCanvasProperty canvas && canvas.getWidth() > 0 && canvas.getHeight() > 0) {
            layers.add(wearLayer(path, canvas));
        }
        List<WzImageProperty> children = property.getChildren();
        if (children == null) {
            return;
        }
        for (WzImageProperty child : children) {
            collectWearLayers(child, path + "/" + child.getName(), layers);
        }
    }

    private static WearLayer wearLayer(String path, WzCanvasProperty canvas) {
        int originX = 0;
        int originY = 0;
        WzImageProperty origin = canvas.getChild("origin");
        if (origin instanceof WzVectorProperty vector) {
            originX = vector.getX();
            originY = vector.getY();
        }
        String z = "";
        WzImageProperty zProp = canvas.getChild("z");
        if (zProp instanceof WzStringProperty stringProperty) {
            z = stringProperty.getValue();
        }
        return new WearLayer(path, canvas.getWidth(), canvas.getHeight(), originX, originY, z);
    }

    private static int zOrder(String z) {
        return switch (z) {
            case "backHair", "backAccessory", "backWeapon", "capeBelowBody", "cape" -> 10;
            case "body", "arm", "mail", "pants", "shoes" -> 20;
            case "head", "face", "hair" -> 30;
            case "ear", "earOverHair", "accessoryFace", "accessoryEye", "accessoryEar" -> 40;
            case "cap", "capOverHair", "weapon", "glove", "shield" -> 50;
            default -> 30;
        };
    }

    private static WzImageProperty findProperty(WzImage image, String propPath) {
        WzImageProperty property = findPropertyOrNull(image, propPath);
        if (property == null) {
            throw new IllegalArgumentException("找不到节点: " + propPath);
        }
        return property;
    }

    private static WzImageProperty findPropertyOrNull(WzImage image, String propPath) {
        String[] parts = propPath.split("/");
        WzImageProperty current = null;
        for (int i = 0; i < parts.length; i++) {
            current = i == 0
                    ? image.getChild(parts[i])
                    : current == null ? null : current.getChild(parts[i]);
            if (current == null) {
                return null;
            }
        }
        return current;
    }

    private static CanvasCandidate firstCanvas(List<WzImageProperty> properties, String parentPath) {
        if (properties == null) {
            return null;
        }
        for (WzImageProperty property : properties) {
            String path = parentPath.isEmpty() ? property.getName() : parentPath + "/" + property.getName();
            if (property instanceof WzCanvasProperty canvas && canvas.getWidth() > 0 && canvas.getHeight() > 0) {
                return new CanvasCandidate(path);
            }
            CanvasCandidate child = firstCanvas(property.getChildren(), path);
            if (child != null) {
                return child;
            }
        }
        return null;
    }

    private static SkillIcon skillIcon(WzImageProperty skill, String basePath) {
        for (String candidate : List.of("icon", "iconMouseOver", "info/icon")) {
            WzImageProperty property = findChildPropertyOrNull(skill, candidate);
            if (property instanceof WzCanvasProperty canvas && canvas.getWidth() > 0 && canvas.getHeight() > 0) {
                return new SkillIcon(basePath + skill.getName() + "/" + candidate);
            }
        }
        return null;
    }

    private static WzImageProperty findChildPropertyOrNull(WzImageProperty parent, String propPath) {
        String[] parts = propPath.split("/");
        WzImageProperty current = parent;
        for (String part : parts) {
            current = current == null ? null : current.getChild(part);
            if (current == null) {
                return null;
            }
        }
        return current;
    }

    private record CanvasCandidate(String path) {
    }

    private record SkillIcon(String path) {
    }

    private record WearLayer(String path, int width, int height, int originX, int originY, String z) {
    }

    private static Map<String, Object> node(WzImageProperty property, String parentPath, NodeCounter counter) {
        counter.count++;
        if (counter.count > MAX_TREE_NODES) {
            counter.truncated = true;
            return Map.of("name", "...", "type", "truncated", "path", parentPath);
        }

        String path = parentPath.isEmpty() ? property.getName() : parentPath + "/" + property.getName();
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("name", property.getName());
        out.put("path", path);
        out.put("type", property.getType().name());
        Object value = value(property);
        if (value != null) {
            out.put("value", value);
        }
        if (property instanceof WzCanvasProperty canvas) {
            out.put("canvas", true);
            out.put("width", canvas.getWidth());
            out.put("height", canvas.getHeight());
            out.put("format", canvas.getFormat().name());
        }
        List<WzImageProperty> children = property.getChildren();
        if (children != null && !children.isEmpty() && !counter.truncated) {
            List<Map<String, Object>> childNodes = new ArrayList<>();
            for (WzImageProperty child : children) {
                childNodes.add(node(child, path, counter));
                if (counter.truncated) {
                    break;
                }
            }
            out.put("children", childNodes);
        }
        return out;
    }

    private static Object value(WzImageProperty property) {
        if (property instanceof WzStringProperty p) return p.getValue();
        if (property instanceof WzIntProperty p) return p.getValue();
        if (property instanceof WzShortProperty p) return p.getValue();
        if (property instanceof WzLongProperty p) return p.getValue();
        if (property instanceof WzFloatProperty p) return p.getValue();
        if (property instanceof WzDoubleProperty p) return p.getValue();
        if (property instanceof WzVectorProperty p) return p.getX() + "," + p.getY();
        if (property instanceof WzUOLProperty p) return p.getValue();
        if (property instanceof WzRawDataProperty p) return p.getLength() + " bytes";
        if (property instanceof WzSoundProperty p) return p.getLenMs() + " ms";
        if (property instanceof WzLuaProperty) return "lua";
        return null;
    }

    private static Map<String, String> query(HttpExchange exchange) {
        Map<String, String> out = new HashMap<>();
        String raw = exchange.getRequestURI().getRawQuery();
        if (raw == null || raw.isEmpty()) {
            return out;
        }
        for (String pair : raw.split("&")) {
            int eq = pair.indexOf('=');
            String key = eq >= 0 ? pair.substring(0, eq) : pair;
            String value = eq >= 0 ? pair.substring(eq + 1) : "";
            out.put(decode(key), decode(value));
        }
        return out;
    }

    private static String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }

    private static String urlEncode(String value) {
        return java.net.URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static String require(Map<String, String> query, String key) {
        String value = query.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("缺少参数: " + key);
        }
        return value;
    }

    private static int parseInt(String value, int defaultValue) {
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        return Integer.parseInt(value);
    }

    private static void writeJson(HttpExchange exchange, Object value) throws IOException {
        writeJson(exchange, 200, value);
    }

    private static void writeJson(HttpExchange exchange, int status, Object value) throws IOException {
        write(exchange, status, "application/json; charset=utf-8", JSON.writeValueAsBytes(value));
    }

    private static void write(HttpExchange exchange, int status, String contentType, byte[] body) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", contentType);
        exchange.sendResponseHeaders(status, body.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(body);
        }
    }

    private static String html() {
        return """
                <!doctype html>
                <html lang="zh-CN">
                <head>
                  <meta charset="utf-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1">
                  <title>Character IMG Browser</title>
                  <style>
                    :root { color-scheme: light; --line:#d8dee8; --text:#1d2733; --muted:#667085; --accent:#0f766e; --accent-soft:#e6f4f1; --bg:#f6f7f9; --panel:#fff; --slot:#eef1f5; }
                    * { box-sizing: border-box; }
                    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--text); background:var(--bg); font-size:14px; }
                    header { height:52px; display:flex; align-items:center; gap:14px; padding:0 18px; border-bottom:1px solid var(--line); background:var(--panel); }
                    h1 { font-size:16px; margin:0; font-weight:700; }
                    .meta { color:var(--muted); font-size:12px; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
                    .app { display:grid; grid-template-columns:minmax(0,1fr) 360px; height:calc(100vh - 52px); min-height:0; }
                    .browser { min-width:0; min-height:0; display:flex; flex-direction:column; border-right:1px solid var(--line); }
                    .toolbar { flex:0 0 auto; display:flex; align-items:center; gap:10px; padding:10px 14px; background:var(--panel); border-bottom:1px solid var(--line); }
                    input { width:260px; max-width:45vw; height:34px; border:1px solid var(--line); border-radius:6px; padding:0 10px; outline:none; background:#fff; }
                    input:focus { border-color:var(--accent); box-shadow:0 0 0 2px rgba(15,118,110,.13); }
                    button { border:1px solid var(--line); background:#fff; border-radius:6px; min-height:30px; padding:0 10px; cursor:pointer; color:var(--text); }
                    button:hover { border-color:var(--accent); color:var(--accent); }
                    .filters { display:flex; align-items:center; gap:6px; }
                    .filter.active { background:var(--accent-soft); border-color:var(--accent); color:var(--accent); }
                    .tabs { flex:0 0 auto; display:flex; gap:6px; padding:8px 14px; overflow:auto; border-bottom:1px solid var(--line); background:#fbfcfd; }
                    .tab { flex:0 0 auto; display:flex; align-items:center; gap:6px; height:32px; border-radius:6px; }
                    .tab.active { background:var(--accent); border-color:var(--accent); color:white; }
                    .count { opacity:.72; font-size:12px; }
                    .content { flex:1 1 auto; min-height:0; overflow:auto; padding:14px; }
                    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(104px,1fr)); gap:10px; align-items:stretch; }
                    .card { min-width:0; height:124px; display:grid; grid-template-rows:86px 1fr; padding:8px; border:1px solid var(--line); border-radius:7px; background:var(--panel); cursor:pointer; }
                    .card:hover, .card.active { border-color:var(--accent); box-shadow:0 0 0 2px rgba(15,118,110,.12); }
                    .thumb { position:relative; display:grid; place-items:center; min-width:0; min-height:0; background:var(--slot); border-radius:5px; overflow:hidden; }
                    .thumb img { max-width:80px; max-height:76px; image-rendering:auto; }
                    .badge { position:absolute; left:5px; top:5px; min-width:28px; height:18px; border-radius:4px; display:grid; place-items:center; padding:0 5px; font-size:11px; line-height:18px; color:#fff; background:#64748b; }
                    .badge.cash { background:#0f766e; }
                    .type-badge { position:absolute; right:5px; top:5px; max-width:62px; height:18px; border-radius:4px; display:block; padding:0 5px; font-size:11px; line-height:18px; color:#344054; background:rgba(255,255,255,.86); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
                    .id { align-self:end; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:center; font:12px ui-monospace,SFMono-Regular,Menlo,monospace; color:#344054; }
                    .side { min-width:0; min-height:0; display:flex; flex-direction:column; background:var(--panel); }
                    .side-head { padding:12px 14px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; gap:10px; }
                    .side-title { font-weight:700; }
                    .stage { min-height:260px; flex:0 0 38%; display:grid; place-items:center; overflow:auto; background:
                      linear-gradient(45deg,#e6e9ef 25%,transparent 25%),linear-gradient(-45deg,#e6e9ef 25%,transparent 25%),
                      linear-gradient(45deg,transparent 75%,#e6e9ef 75%),linear-gradient(-45deg,transparent 75%,#e6e9ef 75%);
                      background-size:22px 22px; background-position:0 0,0 11px,11px -11px,-11px 0; }
                    .mannequin { position:relative; width:220px; height:260px; flex:0 0 auto; }
                    .dummy { position:absolute; left:74px; top:66px; width:72px; height:146px; border-radius:42px 42px 28px 28px; background:#f2d2bd; opacity:.35; }
                    .dummy:before { content:""; position:absolute; left:19px; top:-34px; width:34px; height:34px; border-radius:50%; background:#f2d2bd; }
                    .layer { position:absolute; image-rendering:auto; filter:drop-shadow(0 1px 1px rgba(0,0,0,.18)); }
                    .effect-frame { position:absolute; image-rendering:auto; filter:drop-shadow(0 1px 2px rgba(0,0,0,.2)); visibility:hidden; }
                    .effect-frame.active { visibility:visible; }
                    .effect-controls { display:none; align-items:center; gap:6px; padding:8px 12px; border-top:1px solid var(--line); }
                    .effect-controls select { min-width:0; flex:1; height:30px; border:1px solid var(--line); border-radius:5px; background:#fff; }
                    .tree { min-height:0; overflow:auto; padding:10px 12px 16px; border-top:1px solid var(--line); font:12px ui-monospace,SFMono-Regular,Menlo,monospace; }
                    .tree details { margin-left:12px; }
                    .tree summary { cursor:pointer; line-height:24px; }
                    .tree-value { color:var(--muted); }
                    .selected-list { min-height:0; overflow:auto; padding:10px 12px 14px; display:flex; flex-direction:column; gap:8px; border-top:1px solid var(--line); }
                    .selected-row { display:grid; grid-template-columns:70px 44px minmax(0,1fr) auto; align-items:center; gap:8px; min-height:42px; border:1px solid var(--line); border-radius:7px; padding:6px; }
                    .selected-row img { max-width:40px; max-height:34px; justify-self:center; }
                    .selected-row .name { font:12px ui-monospace,SFMono-Regular,Menlo,monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
                    .selected-row .cat { color:var(--muted); font-size:12px; }
                    .empty { color:var(--muted); padding:16px; }
                    .load { margin:14px auto 4px; display:block; min-width:120px; }
                    .error { color:#b42318; padding:14px; }
                    @media (max-width: 1000px) { .app { grid-template-columns:1fr; height:auto; } .browser { height:70vh; border-right:0; } .side { height:52vh; border-top:1px solid var(--line); } input { width:100%; max-width:none; } }
                  </style>
                </head>
                <body>
                  <header><h1 id="title">IMG Browser</h1><div id="meta" class="meta"></div></header>
                  <main class="app">
                    <section class="browser">
                      <div class="toolbar">
                        <input id="q" placeholder="搜索 id 或路径">
                        <button id="clear">清空</button>
                        <div id="cashFilters" class="filters">
                          <button class="filter active" data-cash="all">全部</button>
                          <button class="filter" data-cash="cash">现金</button>
                          <button class="filter" data-cash="normal">普通</button>
                        </div>
                        <div id="resultMeta" class="meta"></div>
                      </div>
                      <div id="tabs" class="tabs"></div>
                      <div class="content">
                        <div id="grid" class="grid"></div>
                        <button id="more" class="load">加载更多</button>
                      </div>
                    </section>
                    <aside class="side">
                      <div class="side-head">
                        <div><div class="side-title">预览台</div><div id="previewMeta" class="meta">点击卡片加入预览</div></div>
                        <button id="reset">重置</button>
                      </div>
                      <div class="stage"><div id="mannequin" class="mannequin"><div class="dummy"></div></div></div>
                      <div id="effectControls" class="effect-controls">
                        <button id="prevFrame" title="上一帧">&#9664;</button>
                        <button id="togglePlay" title="播放或暂停">&#10074;&#10074;</button>
                        <button id="nextFrame" title="下一帧">&#9654;</button>
                        <select id="effectGroup" aria-label="效果分组"></select>
                      </div>
                      <div id="selectedList" class="selected-list"><div class="empty">未选择装备</div></div>
                      <div id="tree" class="tree" hidden></div>
                    </aside>
                  </main>
                  <script>
                    const $ = id => document.getElementById(id);
                    const enc = encodeURIComponent;
                    const state = { mode: "equip", categories: [], category: "", q: "", cash: "all", offset: 0, limit: 360, matched: 0, items: [], selected: {}, loadSeq: 0, effect: null, group: 0, frame: 0, timer: 0, playing: true, mountedGroup: -1 };
                    const layerOrder = ["Body","Hair","Face","Coat","Longcoat","Pants","Shoes","Glove","Cape","Accessory","Cap","Shield","Weapon","Ring","PetEquip","TamingMob"];
                    const previewAnchor = { x: 110, y: 178 };

                    async function api(url) {
                      const res = await fetch(url);
                      const data = await res.json();
                      if (!res.ok || data.error) throw new Error(data.error || res.statusText);
                      return data;
                    }

                    function thumbUrl(img) { return `/api/thumb?img=${enc(img)}`; }

                    async function boot() {
                      const [meta, cats] = await Promise.all([api("/api/meta"), api("/api/categories")]);
                      state.mode = meta.mode || "equip";
                      $("title").textContent = state.mode === "effect" ? "Effect IMG Browser" : state.mode === "skill" ? "Skill IMG Browser" : "Character IMG Browser";
                      $("meta").textContent = `${meta.input} · ${meta.region} · ${meta.count} images`;
                      $("cashFilters").style.display = state.mode === "equip" ? "flex" : "none";
                      state.categories = cats.items;
                      state.category = state.categories[0]?.id || "Body";
                      renderTabs();
                      await loadItems(true);
                    }

                    function renderTabs() {
                      $("tabs").innerHTML = state.categories.map(c => `
                        <button class="tab ${c.id === state.category ? "active" : ""}" data-category="${c.id}">
                          <span>${c.name}</span><span class="count">${c.count}</span>
                        </button>`).join("");
                    }

                    async function loadItems(reset) {
                      if (reset) {
                        state.offset = 0;
                        state.items = [];
                        $("grid").innerHTML = "";
                      }
                      $("resultMeta").textContent = "加载中...";
                      const seq = ++state.loadSeq;
                      try {
                        const data = await api(`/api/items?category=${enc(state.category)}&q=${enc(state.q)}&cash=${enc(state.cash)}&offset=${state.offset}&limit=${state.limit}`);
                        if (seq !== state.loadSeq) return;
                        state.matched = data.matched;
                        state.items = state.items.concat(data.items);
                        state.offset += data.items.length;
                        renderGrid(data.items, !reset);
                        $("resultMeta").textContent = resultLabel();
                        $("more").style.display = state.offset < state.matched ? "block" : "none";
                      } catch (e) {
                        if (seq !== state.loadSeq) return;
                        $("grid").innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
                        $("resultMeta").textContent = "";
                      }
                    }

                    function typeName(item) {
                      return item.typeName || item.category || "";
                    }

                    function renderGrid(items, append) {
                      const html = items.map(item => `
                        <button class="card" data-img="${escapeAttr(item.img)}" data-id="${escapeAttr(item.id)}" data-category="${escapeAttr(item.category)}" data-kind="${escapeAttr(item.kind || "")}" data-type-name="${escapeAttr(typeName(item))}" data-key="${escapeAttr(item.key || item.category)}" data-icon="${escapeAttr(item.icon || "")}" title="${escapeAttr(typeName(item) + " · " + item.img + " / " + item.id)}">
                          <span class="thumb">${state.mode === "equip" && (item.kind || "equip") === "equip" ? `<span class="badge ${item.cash ? "cash" : ""}">${item.cash ? "现金" : "普通"}</span>` : ""}<span class="type-badge">${escapeHtml(typeName(item))}</span><img loading="lazy" src="${item.icon || thumbUrl(item.img)}" alt="" onerror="this.style.display='none'"></span>
                          <span class="id">${escapeHtml(item.id)}</span>
                        </button>`).join("");
                      if (append) $("grid").insertAdjacentHTML("beforeend", html);
                      else $("grid").innerHTML = html || `<div class="empty">没有匹配的资源</div>`;
                      markActiveCards();
                    }

                    async function selectItem(card) {
                      const item = { img: card.dataset.img, id: card.dataset.id, category: card.dataset.category, kind: card.dataset.kind, typeName: card.dataset.typeName, key: card.dataset.key, icon: card.dataset.icon };
                      if (state.mode === "effect" || item.kind === "effect") {
                        await selectEffect(item);
                        return;
                      }
                      state.selected[item.key] = { ...item, loading: true, layers: [] };
                      renderPreview();
                      markActiveCards();
                      try {
                        const data = await api(`/api/wear?img=${enc(item.img)}&category=${enc(item.category)}`);
                        state.selected[item.key] = {
                          ...item,
                          loading: false,
                          layers: data.layers || [],
                          note: data.layers && data.layers.length ? "" : "无穿戴帧"
                        };
                      } catch (e) {
                        state.selected[item.key] = { ...item, loading: false, error: e.message, layers: [] };
                      }
                      renderPreview();
                      markActiveCards();
                    }

                    async function selectEffect(item) {
                      stopEffectTimer();
                      state.selected = { [item.key]: item };
                      state.effect = null;
                      state.group = 0;
                      state.frame = 0;
                      state.mountedGroup = -1;
                      $("previewMeta").textContent = `${item.img} / ${item.id} · 加载中`;
                      markActiveCards();
                      try {
                        const [effect, tree] = await Promise.all([
                          api(`/api/effect?img=${enc(item.img)}&path=${enc(item.id)}`),
                          api(`/api/tree?img=${enc(item.img)}`)
                        ]);
                        state.effect = { item, groups: effect.groups || [] };
                        renderEffectControls();
                        mountEffectGroup(true);
                        renderEffectFrame();
                        renderTree((tree.children || []).find(node => node.name === item.id));
                      } catch (e) {
                        $("previewMeta").textContent = e.message;
                      }
                    }

                    function renderEffectControls() {
                      const groups = state.effect?.groups || [];
                      $("effectControls").style.display = groups.length ? "flex" : "none";
                      $("effectGroup").innerHTML = groups.map((group, index) => `<option value="${index}">${escapeHtml(group.path)} · ${group.frames.length} 帧</option>`).join("");
                      $("effectGroup").value = String(state.group);
                      $("selectedList").innerHTML = groups.length ? `<div class="selected-row"><div class="cat">${escapeHtml(state.effect.item.typeName || "Effect")}</div><img src="${state.effect.item.icon}" alt=""><div class="name">${escapeHtml(state.effect.item.img)} / ${escapeHtml(state.effect.item.id)}</div><button data-remove="${escapeAttr(state.effect.item.key)}">移除</button></div>` : `<div class="empty">没有可播放的 Canvas 帧</div>`;
                    }

                    function renderEffectFrame() {
                      stopEffectTimer();
                      const group = state.effect?.groups?.[state.group];
                      const frame = group?.frames?.[state.frame];
                      if (!frame) return;
                      if (state.mountedGroup !== state.group) mountEffectGroup(true);
                      $("mannequin").querySelectorAll(".effect-frame").forEach((img, index) => img.classList.toggle("active", index === state.frame));
                      $("previewMeta").textContent = `${state.effect.item.id} · ${state.frame + 1}/${group.frames.length} · ${frame.delay} ms`;
                      $("togglePlay").innerHTML = state.playing ? "&#10074;&#10074;" : "&#9654;";
                      if (state.playing && group.frames.length > 1) {
                        state.timer = setTimeout(() => stepEffect(1), Math.max(16, frame.delay || 100));
                      }
                    }

                    function mountEffectGroup(autoplay = false) {
                      const frames = state.effect?.groups?.[state.group]?.frames || [];
                      const mannequin = $("mannequin");
                      mannequin.innerHTML = "";
                      state.mountedGroup = state.group;
                      if (!frames.length) return;
                      if (autoplay) state.playing = false;
                      const minX = Math.min(...frames.map(frame => -frame.originX));
                      const minY = Math.min(...frames.map(frame => -frame.originY));
                      const maxX = Math.max(...frames.map(frame => frame.width - frame.originX));
                      const maxY = Math.max(...frames.map(frame => frame.height - frame.originY));
                      const width = Math.max(1, maxX - minX);
                      const height = Math.max(1, maxY - minY);
                      const stage = mannequin.parentElement;
                      const scale = Math.min(1, Math.max(0.05, (stage.clientWidth - 28) / width), Math.max(0.05, (stage.clientHeight - 28) / height));
                      mannequin.style.width = `${Math.ceil(width * scale)}px`;
                      mannequin.style.height = `${Math.ceil(height * scale)}px`;
                      const images = frames.map((frame, index) => {
                        const img = document.createElement("img");
                        img.className = `effect-frame${index === state.frame ? " active" : ""}`;
                        img.src = frame.url;
                        img.alt = frame.path;
                        img.decoding = "async";
                        img.style.left = `${(-frame.originX - minX) * scale}px`;
                        img.style.top = `${(-frame.originY - minY) * scale}px`;
                        img.style.width = `${frame.width * scale}px`;
                        img.style.height = `${frame.height * scale}px`;
                        mannequin.appendChild(img);
                        return img;
                      });
                      if (autoplay) {
                        const mountedGroup = state.group;
                        Promise.all(images.map(img => img.complete
                          ? img.decode().catch(() => {})
                          : new Promise(resolve => { img.onload = resolve; img.onerror = resolve; })))
                          .then(() => {
                            if (state.effect && state.group === mountedGroup) {
                              state.playing = true;
                              renderEffectFrame();
                            }
                          });
                      }
                    }

                    function stepEffect(delta) {
                      const frames = state.effect?.groups?.[state.group]?.frames || [];
                      if (!frames.length) return;
                      state.frame = (state.frame + delta + frames.length) % frames.length;
                      renderEffectFrame();
                    }

                    function stopEffectTimer() {
                      clearTimeout(state.timer);
                      state.timer = 0;
                    }

                    function renderTree(node) {
                      $("tree").hidden = !node;
                      $("tree").innerHTML = node ? treeNode(node, true) : "";
                    }

                    function treeNode(node, open) {
                      const children = node.children || [];
                      const label = `${escapeHtml(node.name)} <span class="tree-value">${escapeHtml(node.type || "")}${node.value === undefined ? "" : " = " + escapeHtml(node.value)}</span>`;
                      if (!children.length) return `<div>${label}</div>`;
                      return `<details ${open ? "open" : ""}><summary>${label}</summary>${children.map(child => treeNode(child, false)).join("")}</details>`;
                    }

                    function renderPreview() {
                      const selected = Object.values(state.selected);
                      $("previewMeta").textContent = selected.length ? `${selected.length} 件已选` : "点击卡片加入预览";
                      const mannequin = $("mannequin");
                      mannequin.innerHTML = `<div class="dummy"></div>`;
                      selected.sort((a, b) => layerOrder.indexOf(a.category) - layerOrder.indexOf(b.category)).forEach((item, itemIndex) => {
                        (item.layers || []).forEach((layer, layerIndex) => {
                          const img = document.createElement("img");
                          img.className = "layer";
                          img.src = `${layer.url}&t=${Date.now()}`;
                          img.alt = `${item.id}/${layer.path}`;
                          img.style.left = `${previewAnchor.x - layer.originX}px`;
                          img.style.top = `${previewAnchor.y - layer.originY}px`;
                          img.style.width = `${layer.width}px`;
                          img.style.height = `${layer.height}px`;
                          img.style.zIndex = String(10 + itemIndex * 20 + layerIndex);
                          mannequin.appendChild(img);
                        });
                      });
                      $("selectedList").innerHTML = selected.length ? selected.map(item => `
                        <div class="selected-row">
                          <div class="cat">${escapeHtml(item.typeName || item.category)}</div>
                          <img src="${item.icon || thumbUrl(item.img)}" alt="" onerror="this.style.display='none'">
                          <div class="name" title="${escapeAttr(item.img)}">${escapeHtml(item.id)}${item.loading ? " · 加载中" : ""}${item.note ? " · " + escapeHtml(item.note) : ""}${item.error ? " · " + escapeHtml(item.error) : ""}</div>
                          <button data-remove="${escapeAttr(item.key)}">移除</button>
                        </div>`).join("") : `<div class="empty">未选择装备</div>`;
                    }

                    function markActiveCards() {
                      const selectedKeys = new Set(Object.values(state.selected).map(item => item.key));
                      document.querySelectorAll(".card").forEach(card => card.classList.toggle("active", selectedKeys.has(card.dataset.key)));
                    }

                    function resultLabel() {
                      return state.mode === "skill"
                        ? `${currentCategoryName()} · ${state.items.length}/${state.matched}`
                        : state.mode === "effect"
                          ? `${currentCategoryName()} · ${state.items.length}/${state.matched}`
                          : `${currentCategoryName()} · ${cashLabel(state.cash)} · ${state.items.length}/${state.matched}`;
                    }

                    function currentCategoryName() {
                      return state.categories.find(c => c.id === state.category)?.name || state.category;
                    }

                    function cashLabel(value) {
                      return value === "cash" ? "现金" : value === "normal" ? "普通" : "全部";
                    }

                    function escapeHtml(value) {
                      return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
                    }
                    function escapeAttr(value) { return escapeHtml(value); }

                    $("tabs").addEventListener("click", event => {
                      const tab = event.target.closest(".tab");
                      if (!tab) return;
                      state.category = tab.dataset.category;
                      renderTabs();
                      loadItems(true);
                    });
                    $("grid").addEventListener("click", event => {
                      const card = event.target.closest(".card");
                      if (card) selectItem(card);
                    });
                    $("cashFilters").addEventListener("click", event => {
                      const button = event.target.closest("button[data-cash]");
                      if (!button) return;
                      state.cash = button.dataset.cash;
                      document.querySelectorAll(".filter").forEach(filter => filter.classList.toggle("active", filter === button));
                      loadItems(true);
                    });
                    $("selectedList").addEventListener("click", event => {
                      const button = event.target.closest("button[data-remove]");
                      if (!button) return;
                      if (state.mode === "effect" || state.effect) {
                        stopEffectTimer(); state.selected = {}; state.effect = null;
                        $("mannequin").innerHTML = ""; $("effectControls").style.display = "none";
                        $("selectedList").innerHTML = `<div class="empty">未选择效果</div>`; $("tree").hidden = true;
                        markActiveCards(); return;
                      }
                      delete state.selected[button.dataset.remove];
                      renderPreview();
                      markActiveCards();
                    });
                    $("q").addEventListener("input", () => {
                      clearTimeout(window.__searchTimer);
                      window.__searchTimer = setTimeout(() => {
                        state.q = $("q").value.trim();
                        loadItems(true);
                      }, 180);
                    });
                    $("clear").onclick = () => { $("q").value = ""; state.q = ""; loadItems(true); };
                    $("more").onclick = () => loadItems(false);
                    $("effectGroup").onchange = () => { state.group = Number($("effectGroup").value); state.frame = 0; mountEffectGroup(true); renderEffectFrame(); };
                    $("prevFrame").onclick = () => { state.playing = false; stepEffect(-1); };
                    $("nextFrame").onclick = () => { state.playing = false; stepEffect(1); };
                    $("togglePlay").onclick = () => { state.playing = !state.playing; renderEffectFrame(); };
                    window.addEventListener("resize", () => { if (state.mode === "effect" && state.effect) { mountEffectGroup(); renderEffectFrame(); } });
                    $("reset").onclick = () => { stopEffectTimer(); state.selected = {}; const hadEffect = !!state.effect; state.effect = null; state.mode === "effect" || hadEffect ? ($("selectedList").innerHTML = `<div class="empty">未选择效果</div>`, $("mannequin").innerHTML = "", $("effectControls").style.display = "none", $("tree").hidden = true) : renderPreview(); markActiveCards(); };
                    boot().catch(e => $("grid").innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`);
                  </script>
                </body>
                </html>
                """;
    }
    private enum Region {
        GMS("gms", "GMS", WzAESConstant.WZ_GMS_IV),
        CMS("cms", "CMS", WzAESConstant.WZ_CMS_IV),
        LATEST("latest", "LATEST", WzAESConstant.WZ_LATEST_IV),
        EMPTY("empty", "EMPTY", WzAESConstant.WZ_EMPTY_IV);

        final String optionName;
        final String keyBoxName;
        final byte[] iv;

        Region(String optionName, String keyBoxName, byte[] iv) {
            this.optionName = optionName;
            this.keyBoxName = keyBoxName;
            this.iv = iv;
        }

        static Region parse(String value) {
            for (Region region : values()) {
                if (region.optionName.equalsIgnoreCase(value)) {
                    return region;
                }
            }
            throw new IllegalArgumentException("未知 region: " + value + "，可选: gms, cms, latest, empty");
        }
    }

    private static final class NodeCounter {
        int count;
        boolean truncated;
    }

    private record ServerBinding(HttpServer server, int port) {
    }

    private record Config(Path input, int port, Region region) {
        static Config parse(String[] args) {
            Path input = null;
            int port = 8787;
            Region region = Region.LATEST;
            for (int i = 0; i < args.length; i++) {
                String arg = args[i];
                switch (arg) {
                    case "--input", "-i" -> input = Path.of(requireValue(args, ++i, arg));
                    case "--port", "-p" -> port = Integer.parseInt(requireValue(args, ++i, arg));
                    case "--region" -> region = Region.parse(requireValue(args, ++i, arg));
                    case "--help", "-h" -> {
                        usage();
                        System.exit(0);
                    }
                    default -> throw new IllegalArgumentException("未知参数: " + arg);
                }
            }
            if (input == null) {
                usage();
                throw new IllegalArgumentException("--input 必填");
            }
            if (!Files.isDirectory(input)) {
                throw new IllegalArgumentException("输入必须是 .img 目录: " + input);
            }
            return new Config(input, port, region);
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
                      java orange.wz.cli.PreviewImgServer --input /path/to/Data/Character --port 8787 --region latest

                    选项:
                      -i, --input    包含 .img 的目录
                      -p, --port     本地端口，默认 8787
                      --region       WZ 编码/IV: gms, cms, latest, empty，默认 latest
                    """);
        }
    }
}
