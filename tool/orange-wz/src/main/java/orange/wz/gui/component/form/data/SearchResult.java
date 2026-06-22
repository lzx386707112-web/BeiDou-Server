package orange.wz.gui.component.form.data;

import java.util.List;

public record SearchResult(String name, String value, List<String> path) {

    public String getPathString() {
        return String.join("/", path);
    }
}
