package org.gms.scripting;

import com.oracle.truffle.js.scriptengine.GraalJSScriptEngine;
import org.junit.jupiter.api.Test;

import javax.script.Bindings;
import javax.script.ScriptContext;
import javax.script.ScriptEngine;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EventStartupNullMapGuardTest {
    public static final class DockedMap {
        public void setDocked(boolean docked) {
            throw new IllegalStateException("should not be called when map is null");
        }
    }

    public static final class MapFactoryProbe {
        public Object getMap(int mapid) {
            return null;
        }
    }

    public static final class ChannelProbe {
        public MapFactoryProbe getMapFactory() {
            return new MapFactoryProbe();
        }
    }

    public static final class EventManagerProbe {
        public ChannelProbe getChannelServer() {
            return new ChannelProbe();
        }

        public void setProperty(String key, String value) {}

        public Object schedule(String method, long delay) {
            return null;
        }

        public Object getBossTime(long value) {
            return value;
        }
    }

    @Test
    void cabinScheduleNewDoesNotThrowWhenDockMapsMissing() throws Exception {
        String cabin = Files.readString(Path.of("scripts-zh-CN/event/Cabin.js"));
        ScriptEngine engine = GraalJSScriptEngine.create();
        Bindings bindings = engine.getBindings(ScriptContext.ENGINE_SCOPE);
        bindings.put("polyglot.js.allowHostAccess", true);
        bindings.put("polyglot.js.allowHostClassLookup", true);
        engine.put("em", new EventManagerProbe());
        engine.eval(cabin);
        assertDoesNotThrow(() -> engine.eval("scheduleNew()"));
    }

    @Test
    void areaBossStartDoesNotThrowWhenFieldMapMissing() throws Exception {
        String bamboo = Files.readString(Path.of("scripts-zh-CN/event/AreaBossBamboo.js"));
        assertTrue(bamboo.contains("if (graysPrairie == null)"));
        ScriptEngine engine = GraalJSScriptEngine.create();
        Bindings bindings = engine.getBindings(ScriptContext.ENGINE_SCOPE);
        bindings.put("polyglot.js.allowHostAccess", true);
        bindings.put("polyglot.js.allowHostClassLookup", true);
        engine.put("em", new EventManagerProbe());
        engine.eval(bamboo);
        assertDoesNotThrow(() -> engine.eval("start()"));
    }

    @Test
    void damienSqlHasNoTrailingCommaAndNoDeprecatedValuesFunction() throws Exception {
        String sql = Files.readString(Path.of(
                "src/main/resources/db/migration/V2.1.91__add_damien_genesis_weapon_drops.sql"));
        int onDup = sql.indexOf("ON DUPLICATE KEY UPDATE");
        assertTrue(onDup > 0);
        String values = sql.substring(0, onDup).stripTrailing();
        assertFalse(values.endsWith(","));
        assertFalse(sql.contains("VALUES(`"));
        assertTrue(sql.contains("`chance` = 10000;"));
    }
}
