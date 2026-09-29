import orange.wz.provider.*;
import orange.wz.provider.properties.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class MapScan {
    static String sval(WzImageProperty p) {
        if (p == null) return null;
        if (p instanceof WzStringProperty s) return s.getValue();
        if (p instanceof WzIntProperty i) return String.valueOf(i.getValue());
        if (p instanceof WzLongProperty l) return String.valueOf(l.getValue());
        if (p instanceof WzShortProperty sh) return String.valueOf(sh.getValue());
        if (p instanceof WzFloatProperty f) return String.valueOf(f.getValue());
        if (p instanceof WzDoubleProperty d) return String.valueOf(d.getValue());
        if (p instanceof WzUOLProperty u) return u.getValue();
        return null;
    }
    static String clean(String s) {
        if (s == null) return "";
        return s.replace('\t',' ').replace('\n',' ').replace('\r',' ').trim();
    }
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]);
        PrintWriter out = new PrintWriter(new BufferedWriter(new OutputStreamWriter(
            new FileOutputStream(args[1]), StandardCharsets.UTF_8)));
        List<Path> files = new ArrayList<>();
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(root)) {
            for (Path p : ds) if (Files.isDirectory(p)) {
                try (DirectoryStream<Path> d2 = Files.newDirectoryStream(p, "*.img")) {
                    for (Path q : d2) files.add(q);
                }
            }
        }
        files.sort(Comparator.comparing(p -> p.getFileName().toString()));
        int ok = 0, fail = 0, i = 0;
        StringBuilder sb = new StringBuilder();
        for (Path p : files) {
            i++;
            try {
                WzImageFile f = new WzImageFile("m", p.toString(), "t",
                        WzAESConstant.WZ_LATEST_IV, WzAESConstant.DEFAULT_KEY);
                if (!f.parse()) { fail++; continue; }
                String id = p.getFileName().toString().replace(".img", "");
                sb.setLength(0);
                sb.append(id);
                // info
                WzImageProperty info = f.getChild("info");
                List<String> kv = new ArrayList<>();
                if (info != null && info.getChildren() != null) {
                    for (WzImageProperty c : info.getChildren()) {
                        if (c == null) continue;
                        String v = sval(c);
                        if (v != null) kv.add(c.getName() + "=" + clean(v));
                    }
                }
                sb.append('\t').append(String.join(";", kv));
                // portal 数量 + 名称
                WzImageProperty portal = f.getChild("portal");
                List<String> ps = new ArrayList<>();
                if (portal != null && portal.getChildren() != null) {
                    for (WzImageProperty c : portal.getChildren()) {
                        if (c == null || c.getChildren() == null) continue;
                        String pn = null, pt = null, pd = null;
                        for (WzImageProperty cc : c.getChildren()) {
                            String n = cc.getName();
                            if ("pn".equals(n)) pn = sval(cc);
                            else if ("tm".equals(n)) pt = sval(cc);
                            else if ("pt".equals(n)) pd = sval(cc);
                        }
                        if (pn != null) ps.add(clean(pn) + (pt != null ? ">" + clean(pt) : ""));
                    }
                }
                sb.append('\t').append(String.join(",", ps));
                // life 统计
                WzImageProperty life = f.getChild("life");
                int mob = 0, npc = 0;
                if (life != null && life.getChildren() != null) {
                    for (WzImageProperty c : life.getChildren()) {
                        if (c == null || c.getChildren() == null) continue;
                        String t = null;
                        for (WzImageProperty cc : c.getChildren())
                            if ("type".equals(cc.getName())) t = sval(cc);
                        if ("m".equals(t)) mob++; else if ("n".equals(t)) npc++;
                    }
                }
                sb.append('\t').append(mob).append('/').append(npc);
                out.println(sb);
                ok++;
            } catch (Throwable t) { fail++; }
            if (i % 2000 == 0) { System.err.println(i + "/" + files.size()); }
        }
        out.close();
        System.err.println("done ok=" + ok + " fail=" + fail);
    }
}
