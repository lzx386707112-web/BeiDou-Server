package orange.wz.cli;

import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzImage;
import orange.wz.provider.WzImageFile;
import orange.wz.provider.WzImageProperty;
import orange.wz.provider.properties.WzCanvasProperty;
import orange.wz.provider.properties.WzPngFormat;
import orange.wz.provider.properties.WzStringProperty;
import orange.wz.provider.properties.WzVectorProperty;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public final class BuildSkyLordRings {
    private static final int FIRST_ID = 1118043;
    private static final List<String> EFFECT_IDS = List.of(
            "1104001", "1104002", "1104003", "1104004",
            "1104022", "1104023", "1104024", "1104025", "1104026",
            "1104028", "1104029", "1104030", "1104031",
            "1104036", "1104038", "1104039", "1104040",
            "1104032", "1104035", "1104037"
    );
    private static final String DESCRIPTION = "跪下，众生皆在吾之穹顶之下。\r\n"
            + "这枚戒指由陨落的星河核心铸成，表面流动着永不熄灭的青紫星辉。佩戴者每一次呼吸，都会引动天穹共鸣。"
            + "传说中，它曾属于那位只手遮天的古老天帝，凡人触碰即会被其威压震碎心神，只有真正的霸主才有资格驾驭。";

    private BuildSkyLordRings() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 7) {
            throw new IllegalArgumentException("需要参数: templateRing targetRingDir sourceEffect targetEffect targetEqp frameDir iconPng");
        }
        Path templateRingPath = Path.of(args[0]);
        Path targetRingDir = Path.of(args[1]);
        Path sourceEffectPath = Path.of(args[2]);
        Path targetEffectPath = Path.of(args[3]);
        Path targetEqpPath = Path.of(args[4]);
        Path frameDir = Path.of(args[5]);
        Path iconPath = Path.of(args[6]);
        Files.createDirectories(targetRingDir);

        BufferedImage icon = requireImage(iconPath);
        WzImageFile templateRing = open(templateRingPath, WzAESConstant.WZ_GMS_IV);
        WzImageFile sourceEffect = open(sourceEffectPath, WzAESConstant.WZ_CMS_IV);
        WzImageFile targetEffect = open(targetEffectPath, WzAESConstant.WZ_GMS_IV);
        WzImageFile targetEqp = open(targetEqpPath, WzAESConstant.WZ_GMS_IV);
        WzImageProperty ringStrings = require(targetEqp, "Eqp/Ring");
        WzImageProperty stringTemplate = require(targetEqp, "Eqp/Ring/1118042");

        for (int index = 0; index < EFFECT_IDS.size(); index++) {
            String effectId = EFFECT_IDS.get(index);
            String newId = Integer.toString(FIRST_ID + index);
            String paddedId = "0" + newId;
            String name = "苍穹霸主戒" + (index + 1);

            WzImageProperty effect = require(sourceEffect, effectId).deepClone(targetEffect);
            effect.setNameAnyway(newId);
            effect.setParent(targetEffect);
            effect.setWzImage(targetEffect);
            effect.setChildrenWzImage(targetEffect);
            for (WzImageProperty child : effect.getChildren()) {
                replaceEffectPngs(child, "", frameDir.resolve(effectId));
            }
            if (!targetEffect.addChild(effect)) {
                throw new IllegalStateException("效果 ID 已存在: " + newId);
            }

            WzImage ring = templateRing.deepClone(null);
            ring.setNameAnyway(paddedId + ".img");
            ring.setChildrenWzImage();
            setString(ring, "info/effect/path", "Effect/CharacterEff.img/" + newId);
            setIcon(ring, "info/icon", icon);
            setIcon(ring, "info/iconRaw", icon);
            Path ringPath = targetRingDir.resolve(paddedId + ".img");
            if (!ring.save(ringPath)) {
                throw new IllegalStateException("戒指保存失败: " + ringPath);
            }

            WzImageProperty stringNode = stringTemplate.deepClone(ringStrings);
            stringNode.setNameAnyway(newId);
            stringNode.setParent(ringStrings);
            stringNode.setWzImage(targetEqp);
            stringNode.setChildrenWzImage(targetEqp);
            ((WzStringProperty) require(stringNode, "name")).setValue(name);
            ((WzStringProperty) require(stringNode, "desc")).setValue(DESCRIPTION);
            if (!ringStrings.addChild(stringNode)) {
                throw new IllegalStateException("文本 ID 已存在: " + newId);
            }
            System.out.printf("%s -> %s (%s)%n", newId, effectId, name);
        }

        if (!targetEffect.save()) throw new IllegalStateException("CharacterEff.img 保存失败");
        if (!targetEqp.save()) throw new IllegalStateException("Eqp.img 保存失败");
    }

    private static WzImageFile open(Path path, byte[] iv) {
        WzImageFile image = new WzImageFile(path.getFileName().toString(), path.toString(), "", iv,
                WzAESConstant.DEFAULT_KEY);
        if (!image.parse()) {
            throw new IllegalArgumentException("IMG 解析失败: " + path);
        }
        return image;
    }

    private static BufferedImage requireImage(Path path) throws Exception {
        BufferedImage image = ImageIO.read(path.toFile());
        if (image == null) throw new IllegalArgumentException("无法读取 PNG: " + path);
        return image;
    }

    private static void replaceEffectPngs(WzImageProperty property, String relative, Path root) throws Exception {
        String path = relative.isEmpty() ? property.getName() : relative + "/" + property.getName();
        if (property instanceof WzCanvasProperty canvas) {
            Path png = root.resolve(path + ".png");
            canvas.setPng(requireImage(png), WzPngFormat.ARGB8888, 0);
        }
        List<WzImageProperty> children = property.getChildren();
        if (children != null) {
            for (WzImageProperty child : children) replaceEffectPngs(child, path, root);
        }
    }

    private static void setIcon(WzImage image, String path, BufferedImage icon) {
        WzCanvasProperty canvas = (WzCanvasProperty) require(image, path);
        canvas.setPng(icon, WzPngFormat.ARGB8888, 0);
        WzImageProperty origin = canvas.getChild("origin");
        if (origin instanceof WzVectorProperty vector) {
            vector.setX(0);
            vector.setY(icon.getHeight());
        }
    }

    private static void setString(WzImage image, String path, String value) {
        ((WzStringProperty) require(image, path)).setValue(value);
        image.setChanged(true);
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
}
