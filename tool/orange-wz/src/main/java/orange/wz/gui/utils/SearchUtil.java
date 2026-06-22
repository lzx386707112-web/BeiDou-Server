package orange.wz.gui.utils;

import orange.wz.gui.component.form.data.SearchResult;
import orange.wz.gui.component.panel.EditPane;
import orange.wz.provider.WzObject;
import orange.wz.provider.properties.WzStringProperty;
import orange.wz.provider.properties.WzUOLProperty;

import javax.swing.tree.DefaultMutableTreeNode;
import java.util.List;

public final class SearchUtil {
    public static void search(String search, boolean isName, boolean isValue, boolean isEqual, boolean isLow, boolean parseImg, List<SearchResult> searchResults, DefaultMutableTreeNode node, EditPane editPane) {
        WzObject wzObject = (WzObject) node.getUserObject();

        String name = wzObject.getName();
        if (name.equals("List.wz")) return;
        String value = null;
        if (isValue && wzObject instanceof WzStringProperty property) {
            value = property.getValue();
        } else if (isValue && wzObject instanceof WzUOLProperty property) {
            value = property.getValue();
        }

        if ((isName && matchesString(name, search, isEqual, isLow))
                || (isValue && matchesString(value, search, isEqual, isLow))
        ) {
            searchResults.add(new SearchResult(name, value, TreeNodeUtil.getNodePathWithoutRoot(node)));
        }

        // 向下遍历
        if (node.isLeaf()) {
            editPane.expandTreeNode(node, true, parseImg, false);
        }

        for (int j = 0; j < node.getChildCount(); j++) {
            DefaultMutableTreeNode child = (DefaultMutableTreeNode) node.getChildAt(j);
            search(search, isName, isValue, isEqual, isLow, parseImg, searchResults, child, editPane);
        }
    }

    private static boolean matchesString(String name, String search, boolean isEqual, boolean ignoreCase) {
        if (name == null || search == null || name.isEmpty() || search.isEmpty()) return false;

        if (isEqual) {
            // 严格匹配
            if (ignoreCase) {
                return name.equalsIgnoreCase(search);
            } else {
                return name.equals(search);
            }
        } else {
            // 非严格匹配，只要包含即可
            if (ignoreCase) {
                return name.toLowerCase().contains(search.toLowerCase());
            } else {
                return name.contains(search);
            }
        }
    }
}
