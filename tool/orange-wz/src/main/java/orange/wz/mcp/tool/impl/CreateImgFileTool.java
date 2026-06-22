package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;
import orange.wz.provider.tools.wzkey.WzKey;

import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class CreateImgFileTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public CreateImgFileTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "创建新的 img 文件根节点。", objectSchema(
                Map.of(
                        "fileName", stringSchema(),
                        "key", keySchema()
                ),
                List.of("fileName", "key")
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "create_img_file";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        String fileName = ToolParamHelper.requireString(params, "fileName");
        WzKey key = ToolParamHelper.getWzKey(params, "key");
        return Map.of("node", service.createImg(session, fileName, key));
    }
}
