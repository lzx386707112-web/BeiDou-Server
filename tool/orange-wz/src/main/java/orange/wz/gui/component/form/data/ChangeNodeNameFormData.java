package orange.wz.gui.component.form.data;

import lombok.Getter;

@Getter
public class ChangeNodeNameFormData extends NodeFormData {
    private final String oldName;
    private final String newName;
    private final int degree;

    public ChangeNodeNameFormData(String name, String type, String oldName, String newName, int degree) {
        super(name, type);
        this.oldName = oldName;
        this.newName = newName;
        this.degree = degree;
    }
}
