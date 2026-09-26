"""QR code de validação, desenhado com o gerador nativo do ReportLab."""
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing


def draw_qr(c, url, x, y, size):
    """QR em (x, y) com lado `size`; também vira link clicável no PDF."""
    widget = QrCodeWidget(url, barBorder=0)
    x0, y0, x1, y1 = widget.getBounds()
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, x, y)
    c.linkURL(url, (x, y, x + size, y + size), relative=0)
