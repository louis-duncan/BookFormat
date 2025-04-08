from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Line, PolyLine, Rectangle, Polygon
from pypdf.generic import NameObject, ArrayObject, FloatObject

reader = PdfReader("handbook.pdf")
page = reader.pages[0]
writer = PdfWriter()
writer.add_page(page)

annotation = Polygon(
    vertices=[(50, 550), (200, 650), (70, 750), (50, 700)],
)
writer.add_annotation(page_number=0, annotation=annotation)

# Write the annotated file to disk
with open("annotated-pdf.pdf", "wb") as fp:
    writer.write(fp)
