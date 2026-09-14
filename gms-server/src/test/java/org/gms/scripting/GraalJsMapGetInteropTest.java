package org.gms.scripting;

import com.oracle.truffle.js.scriptengine.GraalJSScriptEngine;
import org.junit.jupiter.api.Test;

import javax.script.Bindings;
import javax.script.ScriptContext;
import javax.script.ScriptEngine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class GraalJsMapGetInteropTest {
    public static final class MapFactoryProbe {
        public String getMap(int mapid) {
            return "loaded-" + mapid;
        }
    }

    @Test
    void graalJsNumberReachesJavaPrimitiveGetMap() throws Exception {
        ScriptEngine engine = GraalJSScriptEngine.create();
        Bindings bindings = engine.getBindings(ScriptContext.ENGINE_SCOPE);
        bindings.put("polyglot.js.allowHostAccess", true);
        bindings.put("polyglot.js.allowHostClassLookup", true);
        engine.put("factory", new MapFactoryProbe());

        Object result = engine.eval("factory.getMap(200000131)");
        assertNotNull(result, "GraalJS getMap(int) returned null for a JS number");
        assertEquals("loaded-200000131", String.valueOf(result));
    }
}
