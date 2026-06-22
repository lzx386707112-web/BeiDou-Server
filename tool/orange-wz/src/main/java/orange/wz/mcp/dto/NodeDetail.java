package orange.wz.mcp.dto;

import java.util.Map;

public record NodeDetail(
        NodeSummary node,
        Map<String, Object> value
) {
}
