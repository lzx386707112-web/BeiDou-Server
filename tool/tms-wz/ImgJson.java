import orange.wz.provider.WzImageFile;
import orange.wz.provider.WzAESConstant;
import java.nio.file.Path;

public class ImgJson {
    public static void main(String[] args) throws Exception {
        WzImageFile f = new WzImageFile("x", args[0], "t", WzAESConstant.WZ_LATEST_IV, WzAESConstant.DEFAULT_KEY);
        if (!f.parse()) { System.err.println("PARSE FAILED: " + args[0]); System.exit(1); }
        boolean ok = f.exportToJson(Path.of(args[1]), 2);
        System.out.println((ok ? "OK " : "FAIL ") + args[1]);
    }
}
