package orange.wz.mcp.tool.impl;

import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.session.McpSessionState;
import orange.wz.mcp.tool.McpTool;

import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.emptyObjectSchema;

public final class CreateSessionTool implements McpTool {
    private final McpSessionManager sessionManager;

    public CreateSessionTool(McpSessionManager sessionManager) {
        this.sessionManager = sessionManager;
    }

    @Override
    public String name() {
        return "create_session";
    }

    @Override
    public String description() {
        return "创建新的 MCP 会话。HTTP MCP 通常通过 initialize 创建会话。";
    }

    @Override
    public Map<String, Object> inputSchema() {
        return emptyObjectSchema();
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        McpSessionState session = sessionManager.createSession();
        return Map.of("sessionId", session.getSessionId().toString());
    }
}
