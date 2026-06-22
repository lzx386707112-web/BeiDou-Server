package orange.wz.mcp.http;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import orange.wz.mcp.server.McpServerBootstrap;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.session.McpSessionState;
import orange.wz.mcp.support.McpException;
import orange.wz.mcp.ui.McpUiBridge;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@RestController
@ConditionalOnProperty(name = "orange.mcp.http.enabled", havingValue = "true", matchIfMissing = true)
@RequestMapping("${orange.mcp.http.path:/mcp}")
public final class McpHttpController {
    private static final String JSON_RPC = "2.0";
    private static final String SESSION_HEADER = "Mcp-Session-Id";
    private static final String PROTOCOL_HEADER = "MCP-Protocol-Version";
    private static final Set<String> LOCAL_HOSTS = Set.of("localhost", "127.0.0.1", "::1", "[::1]");
    private static final String INVALID_REQUEST = "Invalid Request";

    private final ObjectMapper objectMapper;
    private final McpServerBootstrap bootstrap;
    private final McpSessionManager sessionManager;
    private final McpSseSessionRegistry sseSessionRegistry;
    private final McpUiBridge uiBridge;

    @Value("${orange.mcp.protocol-version:2025-03-26}")
    private String protocolVersion;

    @Value("${orange.mcp.server-name:orange-wz-http-mcp}")
    private String serverName;

    @Value("${version:unknown}")
    private String serverVersion;

    public McpHttpController(
            ObjectMapper objectMapper,
            McpServerBootstrap bootstrap,
            McpSseSessionRegistry sseSessionRegistry,
            McpUiBridge uiBridge
    ) {
        this.objectMapper = objectMapper;
        this.bootstrap = bootstrap;
        this.sessionManager = bootstrap.sessionManager();
        this.sseSessionRegistry = sseSessionRegistry;
        this.uiBridge = uiBridge;
    }

    @PostMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> post(
            @RequestBody String body,
            HttpServletRequest request
    ) {
        validateOrigin(request);

        if (body == null || body.isBlank()) {
            return ResponseEntity.badRequest().body(JsonRpcResponse.error(null, -32600, INVALID_REQUEST, "Request body cannot be empty"));
        }
        JsonNode root;
        try {
            root = objectMapper.readTree(body);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(JsonRpcResponse.error(null, -32700, "Parse error", e.getMessage()));
        }
        if (root.isArray()) {
            if (root.isEmpty()) {
                return ResponseEntity.badRequest().body(JsonRpcResponse.error(null, -32600, INVALID_REQUEST, "Batch array cannot be empty"));
            }
            List<JsonRpcResponse> responses = new ArrayList<>();
            for (JsonNode node : root) {
                JsonRpcResponse response = handleNode(node, request, null);
                if (response != null) {
                    responses.add(response);
                }
            }
            if (responses.isEmpty()) {
                return acceptedBuilder().build();
            }
            return okBuilder().body(responses);
        }

        Holder<UUID> initSession = new Holder<>();
        JsonRpcResponse response = handleNode(root, request, initSession);
        if (response == null) {
            return acceptedBuilder().build();
        }

        ResponseEntity.BodyBuilder builder = okBuilder();
        if (initSession.value != null) {
            builder.header(SESSION_HEADER, initSession.value.toString());
        }
        return builder.body(response);
    }

    @GetMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public ResponseEntity<SseEmitter> get(HttpServletRequest request) {
        validateOrigin(request);
        UUID sessionId = requireExistingSession(request);
        SseEmitter emitter = sseSessionRegistry.open(sessionId);
        return okBuilder()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(SESSION_HEADER, sessionId.toString())
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .body(emitter);
    }

    @DeleteMapping
    public ResponseEntity<Void> delete(HttpServletRequest request) {
        validateOrigin(request);
        UUID sessionId = requireSessionId(request);
        if (sessionManager.get(sessionId) == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        }
        sseSessionRegistry.close(sessionId);
        sessionManager.remove(sessionId);
        return ResponseEntity.noContent().header(PROTOCOL_HEADER, protocolVersion).build();
    }

    private JsonRpcResponse handleNode(JsonNode node, HttpServletRequest request, Holder<UUID> initSession) {
        if (node == null || !node.isObject()) {
            return JsonRpcResponse.error(null, -32600, INVALID_REQUEST, "JSON-RPC request body must be an object");
        }

        Object id = readId(node.get("id"));
        String version = text(node.get("jsonrpc"));
        String method = text(node.get("method"));
        JsonNode params = node.get("params");

        if (!JSON_RPC.equals(version) || method == null || method.isBlank()) {
            return JsonRpcResponse.error(id, -32600, INVALID_REQUEST, "A valid jsonrpc version and method are required");
        }

        try {
            if ("initialize".equals(method)) {
                McpSessionState session = sessionManager.createSession();
                if (initSession != null) {
                    initSession.value = session.getSessionId();
                }
                return JsonRpcResponse.result(id, initializeResult());
            }

            UUID sessionId = requireExistingSession(request);

            if (method.startsWith("notifications/")) {
                return null;
            }
            if ("ping".equals(method)) {
                return JsonRpcResponse.result(id, Map.of());
            }
            if ("tools/list".equals(method)) {
                return JsonRpcResponse.result(id, Map.of("tools", toolDescriptors()));
            }
            if ("tools/call".equals(method)) {
                Map<String, Object> paramMap = asMap(params);
                String toolName = stringParam(paramMap, "name");
                Map<String, Object> arguments = childMap(paramMap, "arguments");
                McpSessionState session = sessionManager.get(sessionId);
                if (session != null) {
                    uiBridge.syncSessionRoots(session);
                }
                uiBridge.beforeToolCall(toolName, arguments);
                arguments.put("sessionId", sessionId.toString());
                try {
                    Map<String, Object> toolResult = bootstrap.invokeTool(toolName, arguments);
                    if (session != null) {
                        arguments.put("__sessionRoots", new ArrayList<>(session.getRoots()));
                    }
                    uiBridge.afterToolCall(toolName, arguments, toolResult);
                    return JsonRpcResponse.result(id, Map.of(
                            "content", List.of(Map.of(
                                    "type", "text",
                                    "text", objectMapper.writeValueAsString(toolResult)
                            )),
                            "structuredContent", toolResult,
                            "isError", false
                    ));
                } catch (Exception e) {
                    String message = e instanceof McpException ? e.getMessage() : "tool 执行失败: " + e.getMessage();
                    return JsonRpcResponse.result(id, Map.of(
                            "content", List.of(Map.of(
                                    "type", "text",
                                    "text", message
                            )),
                            "isError", true
                    ));
                }
            }
            return JsonRpcResponse.error(id, -32601, "Method not found", method);
        } catch (InvalidSessionHttpException e) {
            throw e;
        } catch (Exception e) {
            return JsonRpcResponse.error(id, -32603, "Internal error", e.getMessage());
        }
    }

    private Map<String, Object> initializeResult() {
        return Map.of(
                "protocolVersion", protocolVersion,
                "capabilities", Map.of(
                        "tools", Map.of(),
                        "prompts", Map.of(),
                        "resources", Map.of()
                ),
                "serverInfo", Map.of(
                        "name", serverName,
                        "version", serverVersion
                )
        );
    }

    private List<McpToolDescriptor> toolDescriptors() {
        return bootstrap.toolRegistry().all().stream()
                .map(tool -> new McpToolDescriptor(tool.name(), tool.description(), tool.inputSchema()))
                .toList();
    }

    private Object readId(JsonNode node) {
        if (node == null || node.isNull()) return null;
        if (node.isIntegralNumber()) return node.longValue();
        if (node.isFloatingPointNumber()) return node.doubleValue();
        if (node.isTextual()) return node.textValue();
        return node.toString();
    }

    private String text(JsonNode node) {
        return node == null || node.isNull() ? null : node.asText();
    }

    private UUID requireExistingSession(HttpServletRequest request) {
        UUID sessionId = requireSessionId(request);
        if (sessionManager.get(sessionId) == null) {
            throw new InvalidSessionHttpException(HttpStatus.NOT_FOUND, "会话不存在或已过期");
        }
        return sessionId;
    }

    private UUID requireSessionId(HttpServletRequest request) {
        String sessionHeader = request.getHeader(SESSION_HEADER);
        if (sessionHeader == null || sessionHeader.isBlank()) {
            throw new InvalidSessionHttpException(HttpStatus.BAD_REQUEST, "缺少 Mcp-Session-Id 请求头");
        }
        try {
            return UUID.fromString(sessionHeader);
        } catch (IllegalArgumentException e) {
            throw new InvalidSessionHttpException(HttpStatus.BAD_REQUEST, "Mcp-Session-Id 非法");
        }
    }

    private void validateOrigin(HttpServletRequest request) {
        String origin = request.getHeader(HttpHeaders.ORIGIN);
        if (origin == null || origin.isBlank() || "null".equalsIgnoreCase(origin)) {
            return;
        }
        try {
            URI uri = URI.create(origin);
            String host = uri.getHost();
            if (host == null || !LOCAL_HOSTS.contains(host.toLowerCase(Locale.ROOT))) {
                throw new InvalidSessionHttpException(HttpStatus.FORBIDDEN, "非法 Origin: " + origin);
            }
        } catch (IllegalArgumentException e) {
            throw new InvalidSessionHttpException(HttpStatus.FORBIDDEN, "非法 Origin: " + origin);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> asMap(JsonNode node) {
        if (node == null || node.isNull()) {
            return new HashMap<>();
        }
        return objectMapper.convertValue(node, Map.class);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> childMap(Map<String, Object> source, String key) {
        Object value = source.get(key);
        if (value instanceof Map<?, ?> map) {
            return new HashMap<>((Map<String, Object>) map);
        }
        return new HashMap<>();
    }

    private String stringParam(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (value == null) {
            throw new McpException("缺少参数: " + key);
        }
        String text = String.valueOf(value);
        if (text.isBlank()) {
            throw new McpException("参数为空: " + key);
        }
        return text;
    }

    @org.springframework.web.bind.annotation.ExceptionHandler(InvalidSessionHttpException.class)
    public ResponseEntity<JsonRpcResponse> handleHttpError(InvalidSessionHttpException e) {
        return ResponseEntity.status(e.status)
                .header(PROTOCOL_HEADER, protocolVersion)
                .contentType(MediaType.APPLICATION_JSON)
                .body(JsonRpcResponse.error(null, -32001, e.getMessage(), null));
    }

    private ResponseEntity.BodyBuilder okBuilder() {
        return ResponseEntity.ok().header(PROTOCOL_HEADER, protocolVersion);
    }

    private ResponseEntity.BodyBuilder acceptedBuilder() {
        return ResponseEntity.status(HttpStatus.ACCEPTED).header(PROTOCOL_HEADER, protocolVersion);
    }

    private static final class Holder<T> {
        private T value;
    }

    private static final class InvalidSessionHttpException extends RuntimeException {
        private final HttpStatus status;

        private InvalidSessionHttpException(HttpStatus status, String message) {
            super(message);
            this.status = status;
        }
    }
}
