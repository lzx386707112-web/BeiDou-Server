package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.awt.Rectangle;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import org.gms.provider.wz.WZFiles;
import org.gms.server.life.Monster;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.xml.sax.SAXException;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotMobHitboxProvider.class */
final class BotMobHitboxProvider {
    private static final Logger log = LoggerFactory.getLogger(BotMobHitboxProvider.class);
    private static final Rectangle UNRESOLVED_BOUNDS = new Rectangle(Integer.MIN_VALUE, 0, 0, 0);
    private static final String[] FRAME_GROUP_FALLBACK = {"stand", "move", "fly"};
    private static final Map<Integer, Rectangle> boundsByMobId = new ConcurrentHashMap();
    private static volatile Path cachedMobRoot = null;

    private BotMobHitboxProvider() {
    }

    static Rectangle getMobBounds(Monster mob) {
        if (mob == null) {
            return null;
        }
        return getMobBounds(mob.getId(), mob.getPosition(), mob.isFacingLeft());
    }

    static Rectangle getMobBounds(int mobId, Point position, boolean facingLeft) {
        ensureCurrentMobRoot();
        Rectangle modelBounds = boundsByMobId.computeIfAbsent(Integer.valueOf(mobId), (v0) -> {
            return loadMobBounds(v0);
        });
        if (modelBounds == UNRESOLVED_BOUNDS) {
            return null;
        }
        return calculateWorldBounds(modelBounds, position, facingLeft);
    }

    private static void ensureCurrentMobRoot() {
        Path currentMobRoot = WZFiles.MOB.getFile();
        Path previousMobRoot = cachedMobRoot;
        if (previousMobRoot != null && previousMobRoot.equals(currentMobRoot)) {
            return;
        }
        synchronized (boundsByMobId) {
            if (cachedMobRoot == null || !cachedMobRoot.equals(currentMobRoot)) {
                boundsByMobId.clear();
                cachedMobRoot = currentMobRoot;
            }
        }
    }

    private static Rectangle loadMobBounds(int mobId) {
        Path mobFile = WZFiles.MOB.getFile().resolve(String.format("%07d.img.xml", Integer.valueOf(mobId)));
        if (!Files.isRegularFile(mobFile, new LinkOption[0])) {
            // BOTLOG-MUTE: log.debug("Bot mob hitbox: no WZ file for mob {} - caching miss", Integer.valueOf(mobId));
            return UNRESOLVED_BOUNDS;
        }
        Document document = parseXmlDocument(mobFile);
        if (document == null) {
            return UNRESOLVED_BOUNDS;
        }
        Rectangle bounds = loadFrameBounds(document.getDocumentElement());
        if (bounds == null) {
            // BOTLOG-MUTE: log.debug("Bot mob hitbox: no lt/rb bounds on any of {} for mob {} - caching miss", String.join(",", FRAME_GROUP_FALLBACK), Integer.valueOf(mobId));
            return UNRESOLVED_BOUNDS;
        }
        return bounds;
    }

    private static Rectangle loadFrameBounds(Element root) {
        Element frame;
        Rectangle bounds;
        Element linkedRoot = resolveLinkedRoot(root);
        for (String frameGroup : FRAME_GROUP_FALLBACK) {
            Element group = BotWzXml.findNamedChild(linkedRoot, frameGroup);
            if (group != null && (frame = BotWzXml.findNamedChild(group, "0")) != null && (bounds = toBounds(BotWzXml.findNamedChild(frame, "lt"), BotWzXml.findNamedChild(frame, "rb"))) != null) {
                return bounds;
            }
        }
        return null;
    }

    private static Element resolveLinkedRoot(Element root) {
        Element info = BotWzXml.findNamedChild(root, "info");
        int linkedMobId = BotWzXml.getIntValue(BotWzXml.findNamedChild(info, "link"), 0);
        if (linkedMobId <= 0) {
            return root;
        }
        Path linkedFile = WZFiles.MOB.getFile().resolve(String.format("%07d.img.xml", Integer.valueOf(linkedMobId)));
        if (!Files.isRegularFile(linkedFile, new LinkOption[0])) {
            return root;
        }
        Document linkedDocument = parseXmlDocument(linkedFile);
        return linkedDocument != null ? linkedDocument.getDocumentElement() : root;
    }

    private static Rectangle calculateWorldBounds(Rectangle modelBounds, Point origin, boolean facingLeft) {
        int left = modelBounds.x;
        int right = modelBounds.x + modelBounds.width;
        if (facingLeft) {
            left = -right;
            right = -left;
        }
        return new Rectangle(origin.x + left, origin.y + modelBounds.y, right - left, modelBounds.height);
    }

    private static Rectangle toBounds(Element lt, Element rb) {
        if (lt == null || rb == null) {
            return null;
        }
        int left = Math.min(BotWzXml.getIntAttribute(lt, "x", 0), BotWzXml.getIntAttribute(rb, "x", 0));
        int right = Math.max(BotWzXml.getIntAttribute(lt, "x", 0), BotWzXml.getIntAttribute(rb, "x", 0));
        int top = Math.min(BotWzXml.getIntAttribute(lt, "y", 0), BotWzXml.getIntAttribute(rb, "y", 0));
        int bottom = Math.max(BotWzXml.getIntAttribute(lt, "y", 0), BotWzXml.getIntAttribute(rb, "y", 0));
        if (left >= right || top >= bottom) {
            return null;
        }
        return new Rectangle(left, top, right - left, bottom - top);
    }

    private static Document parseXmlDocument(Path path) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            DocumentBuilder builder = factory.newDocumentBuilder();
            return builder.parse(path.toFile());
        } catch (IOException | ParserConfigurationException | SAXException e) {
            // BOTLOG-MUTE: log.warn("Failed to load bot mob hitbox data from {}", path, e);
            return null;
        }
    }
}
