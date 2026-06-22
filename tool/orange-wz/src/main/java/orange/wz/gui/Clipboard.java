package orange.wz.gui;

import orange.wz.provider.WzDirectory;
import orange.wz.provider.WzImage;
import orange.wz.provider.WzImageProperty;
import orange.wz.provider.WzObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.locks.ReentrantLock;

public final class Clipboard {
    private final List<WzObject> items = new ArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();

    public void lock() {
        lock.lock();
    }

    public void unlock() {
        lock.unlock();
    }

    public void clear() {
        items.clear();
    }

    public void add(WzObject item) {
        items.add(item);
    }

    public boolean isEmpty() {
        return items.isEmpty();
    }

    public List<WzObject> getItems() {
        List<WzObject> items = new ArrayList<>();
        for (WzObject item : this.items) {
            items.add(item.deepClone(null)); // 重新克隆一份，避免剪贴板残留导致资源无法释放
        }

        return items;
    }

    public boolean canPaste(WzObject target) {
        WzObject child = items.getFirst();
        return switch (child) {
            case null -> false;
            case WzDirectory ignored when target instanceof WzDirectory -> true;
            case WzImage ignored when target instanceof WzDirectory -> true;
            case WzImageProperty ignored when target instanceof WzImage -> true;
            default ->
                    child instanceof WzImageProperty && target instanceof WzImageProperty prop && prop.isListProperty();
        };
    }
}
