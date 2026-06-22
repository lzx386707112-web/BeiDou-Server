package orange.wz.mcp.http;

import java.util.Map;

public record McpToolDescriptor(
        String name,
        String description,
        Map<String, Object> inputSchema
) {
}
