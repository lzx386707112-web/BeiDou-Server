package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;
import orange.wz.provider.tools.wzkey.WzKey;

import java.io.File;
import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class LoadFilesTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public LoadFilesTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "加载 wz/img/xml 文件或目录到当前 MCP 会话；若目标根已加载则返回错误。", objectSchema(
                Map.of(
                        "paths", arraySchema(stringSchema()),
                        "key", keySchema()
                ),
                List.of("paths", "key")
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "load_files";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        List<File> files = ToolParamHelper.getCanonicalLoadFiles(params, "paths");
        WzKey key = ToolParamHelper.getWzKey(params, "key");
        var session = session(params);
        service.loadFiles(session, files, key);
        return Map.of("loadedCount", files.size(), "rootCount", session.getRoots().size());
    }
}
