package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;

import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.nodeReferenceWithAutoParseSchema;

public final class SaveNodeTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public SaveNodeTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "保存指定文件节点。", nodeReferenceWithAutoParseSchema());
        this.service = service;
    }

    @Override
    public String name() {
        return "save_node";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        boolean autoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
        service.saveNode(session, ToolParamHelper.getNodeReference(params), autoParse);
        return Map.of("ok", true);
    }
}
