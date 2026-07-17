package orange.wz.cli;

import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzImage;
import orange.wz.provider.WzImageFile;
import orange.wz.provider.WzImageProperty;
import orange.wz.provider.properties.*;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class BuildSupremeRings {
    private static final int FIRST_ID = 1118063;
    private static final String NAME = "至高无上·逼王戒";
    private static final String DESCRIPTION = "世间所有逼格，在此戒面前皆为浮云。\r\n"
            + "它不属于任何时代，也不被任何规则束缚。戒身由纯粹的“凡人不可直视之光”凝聚而成，镶嵌着一颗不断变幻颜色的至高原石。"
            + "传说只要佩戴它，你即成为本服逼王本王，无人能出其右。低调？不存在的。";
    private static final List<SourceEffect> EFFECTS = List.of(
            new SourceEffect(4, "1104046"), new SourceEffect(4, "1104053"),
            new SourceEffect(4, "1104054"), new SourceEffect(4, "1104058"),
            new SourceEffect(4, "1104059"), new SourceEffect(4, "1104060"),
            new SourceEffect(3, "1104063"), new SourceEffect(3, "1104065"),
            new SourceEffect(3, "1104075"), new SourceEffect(3, "1104076"),
            new SourceEffect(3, "1104077"), new SourceEffect(3, "1104078"),
            new SourceEffect(3, "1104079"), new SourceEffect(3, "1104080"),
            new SourceEffect(3, "1104081"), new SourceEffect(3, "1104082")
    );

    private BuildSupremeRings() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 8) {
            throw new IllegalArgumentException("需要参数: templateRing targetRingDir sourceEff3 sourceEff4 targetEffect targetEqp iconPng xmlFragment");
        }
        Path templatePath = Path.of(args[0]);
        Path ringDir = Path.of(args[1]);
        WzImageFile source3 = open(Path.of(args[2]), WzAESConstant.WZ_CMS_IV);
        WzImageFile source4 = open(Path.of(args[3]), WzAESConstant.WZ_CMS_IV);
        WzImageFile targetEffect = open(Path.of(args[4]), WzAESConstant.WZ_GMS_IV);
        WzImageFile targetEqp = open(Path.of(args[5]), WzAESConstant.WZ_GMS_IV);
        BufferedImage icon = requireImage(Path.of(args[6]));
        Path fragmentPath = Path.of(args[7]);
        WzImageFile template = open(templatePath, WzAESConstant.WZ_GMS_IV);
        WzImageProperty ringStrings = require(targetEqp, "Eqp/Ring");
        WzImageProperty stringTemplate = require(targetEqp, "Eqp/Ring/1118062");
        List<WzImageProperty> addedEffects = new ArrayList<>();
        Files.createDirectories(ringDir);

        for (int index = 0; index < EFFECTS.size(); index++) {
            SourceEffect source = EFFECTS.get(index);
            String newId = Integer.toString(FIRST_ID + index);
            String paddedId = "0" + newId;
            WzImageFile sourceFile = source.fileNumber == 3 ? source3 : source4;

            WzImageProperty effect = require(sourceFile, source.id).deepClone(targetEffect);
            effect.setNameAnyway(newId);
            effect.setParent(targetEffect);
            effect.setWzImage(targetEffect);
            effect.setChildrenWzImage(targetEffect);
            makeCanvasesLossless(effect);
            if (!targetEffect.addChild(effect)) throw new IllegalStateException("效果 ID 已存在: " + newId);
            addedEffects.add(effect);

            WzImage ring = template.deepClone(null);
            ring.setNameAnyway(paddedId + ".img");
            ring.setChildrenWzImage();
            ((WzStringProperty) require(ring, "info/effect/path")).setValue("Effect/CharacterEff.img/" + newId);
            ((WzIntProperty) require(ring, "info/effect/pos")).setValue(0);
            setIcon(ring, "info/icon", icon);
            setIcon(ring, "info/iconRaw", icon);
            ring.setChanged(true);
            if (!ring.save(ringDir.resolve(paddedId + ".img"))) {
                throw new IllegalStateException("戒指保存失败: " + paddedId);
            }

            WzImageProperty text = stringTemplate.deepClone(ringStrings);
            text.setNameAnyway(newId);
            text.setParent(ringStrings);
            text.setWzImage(targetEqp);
            text.setChildrenWzImage(targetEqp);
            ((WzStringProperty) require(text, "name")).setValue(NAME);
            ((WzStringProperty) require(text, "desc")).setValue(DESCRIPTION);
            if (!ringStrings.addChild(text)) throw new IllegalStateException("文本 ID 已存在: " + newId);
            System.out.printf("%s -> CharacterEff%d/%s%n", newId, source.fileNumber, source.id);
        }

        Files.writeString(fragmentPath, effectXml(addedEffects), StandardCharsets.UTF_8);
        if (!targetEffect.save()) throw new IllegalStateException("CharacterEff.img 保存失败");
        if (!targetEqp.save()) throw new IllegalStateException("Eqp.img 保存失败");
    }

    private static void makeCanvasesLossless(WzImageProperty property) {
        if (property instanceof WzCanvasProperty canvas) {
            canvas.setPng(canvas.getPngImage(false), WzPngFormat.ARGB8888, 0);
        }
        List<WzImageProperty> children = property.getChildren();
        if (children != null) children.forEach(BuildSupremeRings::makeCanvasesLossless);
    }

    private static String effectXml(List<WzImageProperty> effects) {
        StringBuilder out = new StringBuilder();
        for (WzImageProperty effect : effects) writeXml(effect, 1, out);
        return out.toString();
    }

    private static void writeXml(WzImageProperty property, int indent, StringBuilder out) {
        String pad = "  ".repeat(indent);
        if (property instanceof WzCanvasProperty canvas) {
            out.append(pad).append("<canvas name=\"").append(xml(property.getName()))
                    .append("\" width=\"").append(canvas.getWidth()).append("\" height=\"")
                    .append(canvas.getHeight()).append("\">\n");
            if (property.getChildren() != null) property.getChildren().forEach(child -> writeXml(child, indent + 1, out));
            out.append(pad).append("</canvas>\n");
        } else if (property instanceof WzVectorProperty value) {
            out.append(pad).append("<vector name=\"").append(xml(property.getName())).append("\" x=\"")
                    .append(value.getX()).append("\" y=\"").append(value.getY()).append("\"/>\n");
        } else if (property instanceof WzIntProperty value) {
            scalar(out, pad, "int", property.getName(), value.getValue());
        } else if (property instanceof WzStringProperty value) {
            scalar(out, pad, "string", property.getName(), value.getValue());
        } else {
            out.append(pad).append("<imgdir name=\"").append(xml(property.getName())).append("\">\n");
            if (property.getChildren() != null) property.getChildren().forEach(child -> writeXml(child, indent + 1, out));
            out.append(pad).append("</imgdir>\n");
        }
    }

    private static void scalar(StringBuilder out, String pad, String tag, String name, Object value) {
        out.append(pad).append('<').append(tag).append(" name=\"").append(xml(name)).append("\" value=\"")
                .append(xml(String.valueOf(value))).append("\"/>\n");
    }

    private static String xml(String value) {
        return value.replace("&", "&amp;").replace("\"", "&quot;").replace("<", "&lt;").replace(">", "&gt;");
    }

    private static void setIcon(WzImage image, String path, BufferedImage icon) {
        WzCanvasProperty canvas = (WzCanvasProperty) require(image, path);
        canvas.setPng(icon, WzPngFormat.ARGB8888, 0);
        if (canvas.getChild("origin") instanceof WzVectorProperty origin) {
            origin.setX(0);
            origin.setY(icon.getHeight());
        }
    }

    private static BufferedImage requireImage(Path path) throws Exception {
        BufferedImage image = ImageIO.read(path.toFile());
        if (image == null) throw new IllegalArgumentException("无法读取 PNG: " + path);
        return image;
    }

    private static WzImageFile open(Path path, byte[] iv) {
        WzImageFile image = new WzImageFile(path.getFileName().toString(), path.toString(), "", iv,
                WzAESConstant.DEFAULT_KEY);
        if (!image.parse()) throw new IllegalArgumentException("IMG 解析失败: " + path);
        return image;
    }

    private static WzImageProperty require(WzImage image, String path) {
        WzImageProperty current = null;
        for (String part : path.split("/")) {
            current = current == null ? image.getChild(part) : current.getChild(part);
            if (current == null) throw new IllegalArgumentException("找不到节点: " + image.getName() + "/" + path);
        }
        return current;
    }

    private static WzImageProperty require(WzImageProperty property, String path) {
        WzImageProperty current = property;
        for (String part : path.split("/")) {
            current = current.getChild(part);
            if (current == null) throw new IllegalArgumentException("找不到节点: " + property.getPath() + "/" + path);
        }
        return current;
    }

    private record SourceEffect(int fileNumber, String id) {
    }
}
