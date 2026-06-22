package orange.wz.gui.component.form.data;

import lombok.Getter;
import orange.wz.provider.tools.MediaExportType;

@Getter
public final class ExportXmlData {
    private final int indent;
    private final MediaExportType meType;
    private final String exportPath;
    private final boolean linux;

    public ExportXmlData(int indent, MediaExportType meType, String exportPath, boolean linux) {
        this.indent = indent;
        this.meType = meType;
        this.exportPath = exportPath;
        this.linux = linux;
    }
}
