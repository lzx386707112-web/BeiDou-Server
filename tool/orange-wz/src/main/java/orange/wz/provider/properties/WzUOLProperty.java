package orange.wz.provider.properties;

import lombok.Getter;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import orange.wz.provider.WzImage;
import orange.wz.provider.WzObject;
import orange.wz.provider.tools.BinaryWriter;
import orange.wz.provider.tools.WzType;

import java.util.Arrays;

@Slf4j
@Getter
@Setter
public class WzUOLProperty extends WzExtended {
    private String value;

    public WzUOLProperty(String name, String value, WzObject parent, WzImage wzImage) {
        super(name, WzType.UOL_PROPERTY, parent, wzImage);
        this.value = value;
    }

    public WzObject getUolTarget() {
        return getUolTarget(getParent(), value.split("/"), 0);
    }

    private WzObject getUolTarget(WzObject wzObject, String[] path, int step) {
        if (path.length == 0) return null;

        if (wzObject instanceof WzListProperty list) {
            if (path.length == step + 1) {
                WzObject obj = list.getChild(path[step]);
                if (obj instanceof WzCanvasProperty cav) {
                    return cav;
                } else if (obj instanceof WzListProperty listObj && listObj.getChild("0") instanceof WzCanvasProperty cav) {
                    return cav;
                } else if (obj instanceof WzSoundProperty sound) {
                    return sound;
                } else {
                    log.warn("UOL 对象是个奇怪的东西 : {}", String.join("/", path));
                    return null;
                }
            } else {
                String childName = path[step];
                if (childName.equalsIgnoreCase("..")) {
                    return getUolTarget(list.getParent(), path, step + 1);
                } else {
                    return getUolTarget(list.getChild(childName), path, step + 1);
                }
            }
        } else if (wzObject instanceof WzImage img) {
            if (path.length == step + 1) {
                return (WzCanvasProperty) (img.getChild(path[step]));
            } else {
                String childName = path[step];
                if (childName.equalsIgnoreCase("..")) {
                    throw new RuntimeException("Img节点无法再往上查询 : " + String.join("/", Arrays.copyOfRange(path, 0, step + 1)));
                } else {
                    return getUolTarget(img.getChild(childName), path, step + 1);
                }
            }
        } else {
            log.warn("UOL 加载到 [{}] 目标不是List或者Image, 无法继续下去了", String.join("/", Arrays.copyOfRange(path, 0, step + 1)));
            return null;
        }
    }

    @Override
    public void writeValue(BinaryWriter writer) {
        writer.writeStringBlock(WzExtendedType.UOL.getString(), WzImage.withoutOffsetFlag, WzImage.withOffsetFlag);
        writer.putByte((byte) 0);
        writer.writeStringBlock(value, 0x00, 0x01);
    }

    @Override
    public WzUOLProperty deepClone(WzObject parent) {
        return new WzUOLProperty(name, value, parent, null);
    }
}
