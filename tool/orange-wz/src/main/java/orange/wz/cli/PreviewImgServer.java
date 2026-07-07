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
        int slash = imgPath.indexOf('/');
        return slash < 0 ? "Body" : imgPath.substring(0, slash);
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
        List<Map<String, Object>> categories = categoryCounts.entrySet().stream()
                .sorted((a, b) -> Integer.compare(categoryOrder(a.getKey()), categoryOrder(b.getKey())) != 0
                        ? Integer.compare(categoryOrder(a.getKey()), categoryOrder(b.getKey()))
                        : a.getKey().compareToIgnoreCase(b.getKey()))
                .map(entry -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", entry.getKey());
                    item.put("name", entry.getKey());
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
            default -> 100;
        };
    }

    private void handleItems(HttpExchange exchange) throws IOException {
        Map<String, String> query = query(exchange);
        String category = query.getOrDefault("category", "Body");
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

    private record CanvasCandidate(String path) {
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
                    .id { align-self:end; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:center; font:12px ui-monospace,SFMono-Regular,Menlo,monospace; color:#344054; }
                    .side { min-width:0; min-height:0; display:flex; flex-direction:column; background:var(--panel); }
                    .side-head { padding:12px 14px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; gap:10px; }
                    .side-title { font-weight:700; }
                    .stage { min-height:260px; flex:0 0 38%; display:grid; place-items:center; overflow:auto; background:
                      linear-gradient(45deg,#e6e9ef 25%,transparent 25%),linear-gradient(-45deg,#e6e9ef 25%,transparent 25%),
                      linear-gradient(45deg,transparent 75%,#e6e9ef 75%),linear-gradient(-45deg,transparent 75%,#e6e9ef 75%);
                      background-size:22px 22px; background-position:0 0,0 11px,11px -11px,-11px 0; }
                    .mannequin { position:relative; width:220px; height:260px; }
                    .dummy { position:absolute; left:74px; top:66px; width:72px; height:146px; border-radius:42px 42px 28px 28px; background:#f2d2bd; opacity:.35; }
                    .dummy:before { content:""; position:absolute; left:19px; top:-34px; width:34px; height:34px; border-radius:50%; background:#f2d2bd; }
                    .layer { position:absolute; image-rendering:auto; filter:drop-shadow(0 1px 1px rgba(0,0,0,.18)); }
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
                  <header><h1>Character IMG Browser</h1><div id="meta" class="meta"></div></header>
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
                      <div id="selectedList" class="selected-list"><div class="empty">未选择装备</div></div>
                    </aside>
                  </main>
                  <script>
                    const $ = id => document.getElementById(id);
                    const enc = encodeURIComponent;
                    const state = { categories: [], category: "", q: "", cash: "all", offset: 0, limit: 360, matched: 0, items: [], selected: {}, loadSeq: 0 };
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
                      $("meta").textContent = `${meta.input} · ${meta.region} · ${meta.count} images`;
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
                        $("resultMeta").textContent = `${state.category} · ${cashLabel(state.cash)} · ${state.items.length}/${state.matched}`;
                        $("more").style.display = state.offset < state.matched ? "block" : "none";
                      } catch (e) {
                        if (seq !== state.loadSeq) return;
                        $("grid").innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
                        $("resultMeta").textContent = "";
                      }
                    }

                    function renderGrid(items, append) {
                      const html = items.map(item => `
                        <button class="card" data-img="${escapeAttr(item.img)}" data-id="${escapeAttr(item.id)}" data-category="${escapeAttr(item.category)}" title="${escapeAttr(item.img)}">
                          <span class="thumb"><span class="badge ${item.cash ? "cash" : ""}">${item.cash ? "现金" : "普通"}</span><img loading="lazy" src="${thumbUrl(item.img)}" alt="" onerror="this.style.display='none'"></span>
                          <span class="id">${escapeHtml(item.id)}</span>
                        </button>`).join("");
                      if (append) $("grid").insertAdjacentHTML("beforeend", html);
                      else $("grid").innerHTML = html || `<div class="empty">没有匹配的资源</div>`;
                      markActiveCards();
                    }

                    async function selectItem(card) {
                      const item = { img: card.dataset.img, id: card.dataset.id, category: card.dataset.category };
                      state.selected[item.category] = { ...item, loading: true, layers: [] };
                      renderPreview();
                      markActiveCards();
                      try {
                        const data = await api(`/api/wear?img=${enc(item.img)}&category=${enc(item.category)}`);
                        state.selected[item.category] = {
                          ...item,
                          loading: false,
                          layers: data.layers || [],
                          note: data.layers && data.layers.length ? "" : "无穿戴帧"
                        };
                      } catch (e) {
                        state.selected[item.category] = { ...item, loading: false, error: e.message, layers: [] };
                      }
                      renderPreview();
                      markActiveCards();
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
                          <div class="cat">${escapeHtml(item.category)}</div>
                          <img src="${thumbUrl(item.img)}" alt="" onerror="this.style.display='none'">
                          <div class="name" title="${escapeAttr(item.img)}">${escapeHtml(item.id)}${item.loading ? " · 加载中" : ""}${item.note ? " · " + escapeHtml(item.note) : ""}${item.error ? " · " + escapeHtml(item.error) : ""}</div>
                          <button data-remove="${escapeAttr(item.category)}">移除</button>
                        </div>`).join("") : `<div class="empty">未选择装备</div>`;
                    }

                    function markActiveCards() {
                      const selectedImgs = new Set(Object.values(state.selected).map(item => item.img));
                      document.querySelectorAll(".card").forEach(card => card.classList.toggle("active", selectedImgs.has(card.dataset.img)));
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
                    $("reset").onclick = () => { state.selected = {}; renderPreview(); markActiveCards(); };
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
