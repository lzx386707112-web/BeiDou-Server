package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;

import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.emptyObjectSchema;

public final class UnloadAllTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public UnloadAllTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "卸载当前会话中的全部已加载对象。", emptyObjectSchema());
        this.service = service;
    }

    @Override
    public String name() {
        return "unload_all";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        service.unloadAll(session);
        return Map.of("ok", true);
    }
}
