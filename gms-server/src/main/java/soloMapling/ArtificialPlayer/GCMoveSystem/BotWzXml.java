package soloMapling.ArtificialPlayer.GCMoveSystem;

import org.w3c.dom.Element;
import org.w3c.dom.Node;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotWzXml.class */
final class BotWzXml {
    private BotWzXml() {
    }

    static Element findNamedChild(Element parent, String name) {
        if (parent == null) {
            return null;
        }
        Node firstChild = parent.getFirstChild();
        while (true) {
            Node child = firstChild;
            if (child != null) {
                if (child.getNodeType() == 1) {
                    Element element = (Element) child;
                    if (name.equals(element.getAttribute("name"))) {
                        return element;
                    }
                }
                firstChild = child.getNextSibling();
            } else {
                return null;
            }
        }
    }

    static int getIntAttribute(Element element, String name, int defaultValue) {
        if (element == null) {
            return defaultValue;
        }
        String value = element.getAttribute(name);
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    static int getIntValue(Element element, int defaultValue) {
        return getIntAttribute(element, "value", defaultValue);
    }
}
