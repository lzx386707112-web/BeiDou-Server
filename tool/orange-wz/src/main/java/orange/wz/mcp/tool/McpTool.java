package orange.wz.mcp.tool;

import java.util.Map;

public interface McpTool {
    String name();

    String description();

    Map<String, Object> inputSchema();

    Map<String, Object> invoke(Map<String, Object> params);
}
