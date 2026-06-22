package orange.wz.mcp.tool.support;

import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.session.McpSessionState;
import orange.wz.mcp.tool.McpTool;

import java.util.Map;

public abstract class BaseSessionTool implements McpTool {
    protected final McpSessionManager sessionManager;
    private final String description;
    private final Map<String, Object> inputSchema;

    protected BaseSessionTool(McpSessionManager sessionManager, String description, Map<String, Object> inputSchema) {
        this.sessionManager = sessionManager;
        this.description = description;
        this.inputSchema = inputSchema;
    }

    @Override
    public String description() {
        return description;
    }

    @Override
    public Map<String, Object> inputSchema() {
        return inputSchema;
    }

    protected McpSessionState session(Map<String, Object> params) {
        return sessionManager.getOrCreate(ToolParamHelper.getSessionId(params));
    }
}
