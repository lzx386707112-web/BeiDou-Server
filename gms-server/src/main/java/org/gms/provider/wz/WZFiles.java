package org.gms.provider.wz;

import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;

import java.nio.file.Files;
import java.nio.file.Path;

public enum WZFiles {
    QUEST("Quest"),
    ETC("Etc"),
    ITEM("Item"),
    CHARACTER("Character"),
    STRING("String"),
    LIST("List"),
    MOB("Mob"),
    MAP("Map"),
    NPC("Npc"),
    REACTOR("Reactor"),
    SKILL("Skill"),
    SOUND("Sound"),
    UI("UI");

    private final String fileName;
    public static final String DIRECTORY = "wz";

    WZFiles(String name) {
        this.fileName = name + ".wz";
    }

    public Path getBaseFile() {
        return Path.of(DIRECTORY, fileName);
    }

    /**
     * 直接按语言解析路径，不依赖 ServerManager 的 ApplicationContext。
     */
    public Path getLanguageFile(String language) {
        if (language == null || language.isBlank()) {
            return getBaseFile();
        }
        return Path.of(DIRECTORY + "-" + language, fileName);
    }

    public Path getLanguageFile() {
        ServiceProperty serviceProperty = ServerManager.getApplicationContext().getBean(ServiceProperty.class);
        return getLanguageFile(serviceProperty.getLanguage());
    }

    public Path getFile() {
        Path languagePath = getLanguageFile();
        return Files.exists(languagePath) ? languagePath : getBaseFile();
    }

    public Path resolveDataFile(String dataPath) {
        Path relative = Path.of(dataPath + ".xml");
        Path languageFile = getLanguageFile().resolve(relative);
        if (Files.exists(languageFile)) {
            return languageFile;
        }
        return getBaseFile().resolve(relative);
    }

    public String getFilePath() {
        return getFile().toString();
    }
}
