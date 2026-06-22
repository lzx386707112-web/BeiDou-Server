package orange.wz.mcp.session;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public final class McpSessionManager {
    private final Map<UUID, McpSessionState> sessions = new ConcurrentHashMap<>();

    public McpSessionState createSession() {
        UUID id = UUID.randomUUID();
        McpSessionState session = new McpSessionState(id);
        sessions.put(id, session);
        return session;
    }

    public McpSessionState getOrCreate(UUID id) {
        return sessions.computeIfAbsent(id, McpSessionState::new);
    }

    public McpSessionState get(UUID id) {
        return sessions.get(id);
    }

    public void remove(UUID id) {
        sessions.remove(id);
    }
}
