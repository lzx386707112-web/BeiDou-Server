import orange.wz.provider.*;
import orange.wz.provider.properties.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class QuestScan {
    static String sval(WzImageProperty p) {
        if (p == null) return "";
        if (p instanceof WzStringProperty s) return s.getValue();
        if (p instanceof WzIntProperty i) return String.valueOf(i.getValue());
        if (p instanceof WzLongProperty l) return String.valueOf(l.getValue());
        if (p instanceof WzShortProperty sh) return String.valueOf(sh.getValue());
        if (p instanceof WzUOLProperty u) return u.getValue();
        return "";
    }
    static String clean(String s) {
        return s == null ? "" : s.replace('\t',' ').replace('\n',' ').replace('\r',' ');
    }
    public static void main(String[] args) throws Exception {
        Path dir = Path.of(args[0]);
        PrintWriter out = new PrintWriter(new BufferedWriter(new OutputStreamWriter(
            new FileOutputStream(args[1]), StandardCharsets.UTF_8)));
        List<Path> files = new ArrayList<>();
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, "*.img")) {
            for (Path p : ds) files.add(p);
        }
        files.sort(Comparator.comparing(p -> p.getFileName().toString()));
        int ok = 0, fail = 0, i = 0;
        for (Path p : files) {
            i++;
            try {
                WzImageFile f = new WzImageFile("q", p.toString(), "t",
                        WzAESConstant.WZ_LATEST_IV, WzAESConstant.DEFAULT_KEY);
                if (!f.parse()) { fail++; continue; }
                WzImageProperty qi = f.getChild("QuestInfo");
                if (qi == null) { fail++; continue; }
                String name = sval(qi.getChild("name"));
                String area = sval(qi.getChild("area"));
                String reqType = sval(qi.getChild("reqType"));
                String lvmin = "", lvmax = "", npc = "";
                WzImageProperty chk = f.getChild("Check");
                if (chk != null && chk.getChildren() != null) {
                    for (WzImageProperty c : chk.getChildren()) {
                        if (c == null || c.getChildren() == null) continue;
                        for (WzImageProperty cc : c.getChildren()) {
                            String cn = cc.getName();
                            if ("lvmin".equals(cn) && lvmin.isEmpty()) lvmin = sval(cc);
                            else if ("lvmax".equals(cn) && lvmax.isEmpty()) lvmax = sval(cc);
                            else if ("npc".equals(cn) && npc.isEmpty()) npc = sval(cc);
                        }
                    }
                }
                String id = p.getFileName().toString().replace(".img", "");
                out.println(id + "\t" + clean(name) + "\t" + clean(area) + "\t" + clean(reqType)
                        + "\t" + lvmin + "\t" + lvmax + "\t" + npc);
                ok++;
            } catch (Throwable t) {
                fail++;
            }
            if (i % 2000 == 0) { System.err.println(i + "/" + files.size()); }
        }
        out.close();
        System.err.println("done ok=" + ok + " fail=" + fail);
    }
}
