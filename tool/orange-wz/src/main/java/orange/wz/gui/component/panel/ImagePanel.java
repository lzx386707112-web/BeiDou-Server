package orange.wz.gui.component.panel;

import lombok.Getter;
import lombok.Setter;

import javax.swing.*;
import java.awt.*;
import java.awt.image.BufferedImage;

@Setter
@Getter
public class ImagePanel extends JPanel {
    private double zoomFactor = 1.0; // 当前缩放比例
    private BufferedImage image;

    public void setImage(BufferedImage image) {
        this.image = image;
        repaint();
    }

    @Override
    protected void paintComponent(Graphics g) {
        super.paintComponent(g);
        if (image != null) {
            Graphics2D g2 = (Graphics2D) g.create();
            g2.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            g2.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
            g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

            int imgWidth = (int) (image.getWidth() * zoomFactor);
            int imgHeight = (int) (image.getHeight() * zoomFactor);

            int x = (getWidth() - imgWidth) / 2;
            int y = (getHeight() - imgHeight) / 2;

            g2.drawImage(image, x, y, imgWidth, imgHeight, this);

            g2.dispose();
        }
    }
}
