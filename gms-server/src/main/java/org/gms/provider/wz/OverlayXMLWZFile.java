package org.gms.provider.wz;

import org.gms.provider.Data;
import org.gms.provider.DataDirectoryEntry;
import org.gms.provider.DataEntity;
import org.gms.provider.DataFileEntry;
import org.gms.provider.DataProvider;

import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Language WZ overlay: files in {@code wz-&lt;lang&gt;} win, missing files fall back to {@code wz}.
 */
public class OverlayXMLWZFile implements DataProvider {
    private final XMLWZFile base;
    private final XMLWZFile overlay;
    private final DataDirectoryEntry mergedRoot;

    public OverlayXMLWZFile(Path baseRoot, Path overlayRoot) {
        this.base = new XMLWZFile(baseRoot);
        this.overlay = new XMLWZFile(overlayRoot);
        this.mergedRoot = merge(base.getRoot(), overlay.getRoot(), null);
    }

    @Override
    public synchronized Data getData(String path) {
        Data data = overlay.getData(path);
        return data != null ? data : base.getData(path);
    }

    @Override
    public DataDirectoryEntry getRoot() {
        return mergedRoot;
    }

    private static WZDirectoryEntry merge(DataDirectoryEntry baseDir, DataDirectoryEntry overlayDir, DataEntity parent) {
        String name = baseDir != null ? baseDir.getName() : overlayDir.getName();
        WZDirectoryEntry merged = new WZDirectoryEntry(name, 0, 0, parent);

        Map<String, DataDirectoryEntry> baseDirs = indexDirs(baseDir);
        Map<String, DataDirectoryEntry> overlayDirs = indexDirs(overlayDir);
        LinkedHashSet<String> dirNames = new LinkedHashSet<>();
        dirNames(baseDirs, overlayDirs, dirNames);
        for (String dirName : dirNames) {
            merged.addDirectory(merge(baseDirs.get(dirName), overlayDirs.get(dirName), merged));
        }

        Map<String, DataFileEntry> baseFiles = indexFiles(baseDir);
        Map<String, DataFileEntry> overlayFiles = indexFiles(overlayDir);
        LinkedHashSet<String> fileNames = new LinkedHashSet<>();
        fileNames.addAll(baseFiles.keySet());
        fileNames.addAll(overlayFiles.keySet());
        for (String fileName : fileNames) {
            DataFileEntry chosen = overlayFiles.getOrDefault(fileName, baseFiles.get(fileName));
            merged.addFile(new WZFileEntry(chosen.getName(), chosen.getSize(), chosen.getChecksum(), merged));
        }
        return merged;
    }

    private static void dirNames(Map<String, DataDirectoryEntry> baseDirs,
                                  Map<String, DataDirectoryEntry> overlayDirs,
                                  LinkedHashSet<String> dirNames) {
        dirNames.addAll(baseDirs.keySet());
        dirNames.addAll(overlayDirs.keySet());
    }

    private static Map<String, DataDirectoryEntry> indexDirs(DataDirectoryEntry dir) {
        if (dir == null) {
            return Map.of();
        }
        return dir.getSubdirectories().stream().collect(Collectors.toMap(DataDirectoryEntry::getName, d -> d, (a, b) -> b));
    }

    private static Map<String, DataFileEntry> indexFiles(DataDirectoryEntry dir) {
        if (dir == null) {
            return Map.of();
        }
        return dir.getFiles().stream().collect(Collectors.toMap(DataFileEntry::getName, f -> f, (a, b) -> b));
    }
}
