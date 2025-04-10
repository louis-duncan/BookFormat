import io
import json
import logging
import time
from json import JSONDecodeError
from math import ceil
from pathlib import Path
from typing import Generator, Any

from pypdf import PdfReader, PdfWriter, PaperSize, Transformation, PageObject
from pypdf.annotations import Line, PolyLine, Rectangle
from pypdf.generic import RectangleObject, FloatObject, ArrayObject, NameObject
from pypdf.papersizes import Dimensions

import wx


VERSION = "2.0.0"
IDEAL_MAX_SIG_SIZE = 4
SETTINGS_PATH = Path("./settings.json")


class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        root = wx.Panel(self)

        w_browse = wx.Button(root, label="Browse")
        w_input_text = wx.StaticText(root, label="Select input document...")
        s_input = wx.StaticBoxSizer(wx.HORIZONTAL, root, "Input")
        s_input.Add(w_browse)
        s_input.Add(w_input_text, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=10)

        s_main = wx.BoxSizer(wx.VERTICAL)
        s_main.Add(s_input, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=5)
        s_main.AddSpacer(1)

        root.SetSizer(s_main)

        s_main.Fit(self)

        # self.load_settings()

    """
    def load_settings(self):
        try:
            with SETTINGS_PATH.open("r") as fh:
                settings_data = json.load(fh)
            self.w_add_side_lines.setChecked(settings_data['add_side_lines'])
            self.w_double_up.setChecked(settings_data['double_up'])
            self.w_double_up_scale.setValue(settings_data['double_up_scale'])
            self.w_save_signatures_separately.setChecked(settings_data['save_signatures_separately'])

        except FileNotFoundError:
            logging.debug("No settings file")
        except JSONDecodeError as e:
            logging.exception(e)

    def save_settings(self):
        try:
            settings_data = {
                'add_side_lines': self.w_add_side_lines.isChecked(),
                'double_up': self.w_double_up.isChecked(),
                'double_up_scale': self.w_double_up_scale.value(),
                'save_signatures_separately': self.w_save_signatures_separately.isChecked()
            }
            with open(SETTINGS_PATH, "w") as fh:
                # noinspection PyTypeChecker
                json.dump(settings_data, fh)
        except Exception as e:
            logging.exception(e)

    def get_num_pages(self):
        return (self.w_end_page.value() - self.w_start_page.value()) + 1

    def select_input_path(self):
        if self.input_document_path:
            start_dir = str(Path(self.input_document_path).parent)
        else:
            start_dir = "${HOME}"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            start_dir,
            "PDF Files (*.pdf)",
        )
        if file_path:
            self.w_input_document_label.setText(file_path)
            self.input_document_path = file_path
            self.read_input_file()
            if self.input_document_path and self.output_document_path:
                self.w_start_process.setDisabled(False)
            else:
                self.w_start_process.setDisabled(True)
        else:
            pass

    def select_output_path(self):
        if self.output_document_path:
            start_dir = str(Path(self.output_document_path).parent)
        elif self.input_document_path:
            start_dir = str(Path(self.input_document_path).parent)
        else:
            start_dir = "${HOME}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select File",
            start_dir + "/output.pdf",
            "PDF Files (*.pdf)",
        )
        if file_path:
            self.w_output_document_label.setText(file_path)
            self.output_document_path = file_path
            if self.input_document_path and self.output_document_path:
                self.w_start_process.setDisabled(False)
            else:
                self.w_start_process.setDisabled(True)
        else:
            pass

    def number_of_signatures_changed(self, n: int):
        for w in self.sig_size_spins:
            self.l_signature_sizes.removeWidget(w)

        self.sig_size_spins = [QSpinBox() for _ in range(n)]
        for w in self.sig_size_spins:
            w.setMinimum(1)
            if self.pdf_reader is None:
                w.setValue(1)
            else:
                sig_sizes = calc_signature_sizes(self.get_num_pages(), n)
                for size, size_control in zip(sig_sizes, self.sig_size_spins):
                    size_control.setValue(size)
            self.l_signature_sizes.addWidget(w)
            w.valueChanged.connect(self.check_sheet_counts)

    def read_input_file(self):
        if self.input_document_path:
            self.pdf_reader = PdfReader(self.input_document_path)
            num_pages = self.pdf_reader.get_num_pages()

            if num_pages % 4 == 0:
                self.w_start_page.setMaximum(num_pages - 3)
                self.w_end_page.setMaximum(num_pages)
                self.w_end_page.setValue(num_pages)
                self.update_signature_suggestions()
            else:
                QMessageBox.critical(
                    self,
                    "Bad File",
                    f"Input PDF must have a number of pages divisible by 4, has {num_pages}.",
                    buttons=QMessageBox.StandardButton.Ok
                )
                self.pdf_reader = None
                self.input_document_path = ""
                self.w_input_document_label.setText("Select input document...")
        else:
            logging.error(f"Cannot read input file, input path is {repr(self.input_document_path)}")

    def update_signature_suggestions(self):
        logging.debug("Fired update signatures")
        if self.pdf_reader is None:
            logging.error("Cannot update suggested signatures, reader is None")
        else:
            self.w_start_page.setMaximum(self.w_end_page.value() - 3)
            self.w_end_page.setMinimum(self.w_start_page.value() + 3)
            num_pages = self.get_num_pages()
            self.w_num_pages_label.setText(
                f"({num_pages} pages, {num_pages // 4} sheets)"
            )
            max_size = num_pages // 4
            n = 0
            has_looped = False
            force_update = False
            if len(self.sig_size_spins) == 1:
                force_update = True
            while max_size > IDEAL_MAX_SIG_SIZE or not has_looped:
                n += 1
                self.w_num_sigs.setValue(n)
                if force_update:
                    self.number_of_signatures_changed(n)
                    force_update = False
                max_size = max([s.value() for s in self.sig_size_spins])
                has_looped = True
            self.w_sigs_error_label.setText("")

    def check_sheet_counts(self, _):
        if self.pdf_reader is None:
            self.w_sigs_error_label.setText("")
        else:
            num_sheets = sum([s.value() for s in self.sig_size_spins])
            if num_sheets * 4 != self.get_num_pages():
                self.w_sigs_error_label.setText(f"Incorrect number of sheets: {num_sheets}")
            else:
                self.w_sigs_error_label.setText("")

    def closeEvent(self, a0):
        self.save_settings()
        super().closeEvent(a0)

    def process_document(self):
        if self.pdf_reader is None:
            raise ValueError("Should not have access process function without a pdfreader loaded.")

        self.settings_widget.setDisabled(True)
        self.w_progress_bar.show()
        self.w_progress_label.show()
        self.w_start_process.setDisabled(True)

        if self.w_add_side_lines.isChecked():
            logging.debug("Adding lines")
            line_writer = PdfWriter(self.pdf_reader)
            page_width = self.pdf_reader.pages[0].mediabox.width
            page_height = self.pdf_reader.pages[0].mediabox.height

            top_line = Rectangle(
                rect=(
                    0, page_height - 0.25,
                    page_width, page_height
                ),
                interior_color="#000000"
            )
            top_line[NameObject("/C")] = ArrayObject(
                [FloatObject(0.0)]
            )

            side_line = Rectangle(
                rect=(
                    page_width - 0.25, 0,
                    page_width, page_height
                ),
                interior_color="#000000"
            )
            side_line[NameObject("/C")] = ArrayObject(
                [FloatObject(0.0), FloatObject(0.0), FloatObject(0.0)]
            )

            page_index = line_writer.get_num_pages() - 1
            line_writer.add_annotation(page_index, top_line)
            line_writer.add_annotation(page_index, side_line)
            output_bytes = io.BytesIO()
            line_writer.write(output_bytes)
            output_bytes.seek(0)
            with open("lined.pdf", "wb") as fh:
                fh.write(output_bytes.read())
            output_bytes.seek(0)
            self.pdf_reader = PdfReader(output_bytes)

        self.w_progress_label.setText("Creating signatures...")
        total_sides = self.get_num_pages() // 2
        self.w_progress_bar.setMaximum(total_sides)

        sig_sizes = [s.value() for s in self.sig_size_spins]
        signatures: list[PdfWriter] = []
        for page_range in get_signature_page_indexes(sig_sizes, self.w_start_page.value() - 1):
            signatures.append(
                create_signature(
                    self.pdf_reader,
                    page_range,
                    self.w_progress_bar
                )
            )

        if self.w_double_up.isChecked():
            logging.info("Doubling up pages")
            doubled_up_sigs = []
            self.w_progress_bar.reset()
            self.w_progress_label.setText("Creating doubled-up pages...")
            for sig in signatures:
                doubled_up_sigs.append(create_double_up(sig, progress_bar=self.w_progress_bar))
            signatures = doubled_up_sigs

        self.w_progress_bar.reset()
        self.w_progress_bar.setMaximum(len(signatures))

        if self.w_save_signatures_separately.isChecked():
            self.w_progress_label.setText("Saving signatures...")
            for i, s in enumerate(signatures):
                file_name, ext = self.output_document_path.rsplit(".", 1)
                with open(file_name + f"_{i}." + ext, "bw") as fh:
                    writer = PdfWriter()
                    for page in s.pages:
                        writer.insert_page(page, writer.get_num_pages())
                    writer.write(fh)
                    writer.close()
                    self.w_progress_bar.setValue(self.w_progress_bar.value() + 1)
                    QCoreApplication.processEvents()
        else:
            merger = PdfWriter()
            self.w_progress_label.setText("Merging Signatures...")
            for s in signatures:
                for page in s.pages:
                    merger.insert_page(page, merger.get_num_pages())
                    self.w_progress_bar.setValue(self.w_progress_bar.value() + 1)
                    QCoreApplication.processEvents()

            self.w_progress_label.setText("Saving output PDF...")
            with open(self.output_document_path, "bw") as fh:
                merger.write(fh)
                merger.close()

        self.w_progress_bar.hide()
        self.w_progress_label.setText("Done!")
        self.settings_widget.setDisabled(False)
    """

QProgressBar = Any
def create_signature(
        reader: PdfReader,
        pages: tuple[int, int],
        progress_bar: None | QProgressBar = None
) -> PdfWriter:
    page_width = reader.pages[0].mediabox.width
    page_height = reader.pages[0].mediabox.height
    new_sheet_size = (2 * page_width, page_height)

    new_pdf = PdfWriter("")

    left_transform = Transformation().translate(
        tx = (new_sheet_size[0] // 2) - page_width,
        ty = (new_sheet_size[1] - page_height) // 2
    )
    right_transform = Transformation().translate(
        tx = new_sheet_size[0] // 2,
        ty = (new_sheet_size[1] - page_height) // 2
    )

    for left_index, right_index in gen_signature_page_orderings(pages):
        new_pdf.add_blank_page(*new_sheet_size)
        new_page = new_pdf.pages[-1]
        try:
            logging.debug(f"Reading pages: {left_index}, {right_index}")
            new_page.merge_transformed_page(reader.pages[left_index], left_transform)
            new_page.merge_transformed_page(reader.pages[right_index], right_transform)
        except IndexError as e:
            logging.exception(e)
            logging.error(f"Attempted to read pages: {left_index}, {right_index}")
            raise e

        if progress_bar is not None:
            progress_bar.setValue(progress_bar.value() + 1)
            QCoreApplication.processEvents()

    return new_pdf


def create_double_up(
        document: PdfReader | PdfWriter,
        output_size: Dimensions = PaperSize.A4,
        scale: float = 1.0,
        progress_bar: None | QProgressBar = None
) -> PdfWriter:
    writer = PdfWriter()

    scaled_size = document.pages[0].mediabox.width * scale, document.pages[0].mediabox.height * scale

    bottom_y = (output_size.height // 2 - scaled_size[1]) // 2
    top_y = bottom_y + (output_size.height // 2)
    x = (output_size.width - scaled_size[0]) // 2

    top_transform = Transformation().scale(scale, scale).translate(x, top_y)
    bottom_transform = Transformation().scale(scale, scale).translate(x, bottom_y)

    for original_page in document.pages:
        writer.add_blank_page(output_size.width, output_size.height)
        new_page = writer.pages[len(writer.pages) - 1]
        new_page.merge_transformed_page(original_page, top_transform)
        new_page.merge_transformed_page(original_page, bottom_transform)

        if progress_bar is not None:
            progress_bar.setValue(progress_bar.value() + 1)
            QCoreApplication.processEvents()

    return writer


def gen_signature_page_orderings(pages: tuple[int, int]) -> Generator[tuple[int, int], None, None]:
    num_pages = (pages[1] - pages[0]) + 1
    flip = True
    for i in range(num_pages // 2):
        if flip:
            yield pages[1] - i, pages[0] + i
        else:
            yield pages[0] + i, pages[1] - i
        flip = not flip


def get_signature_page_indexes(signature_sizes: list[int], start_index=0) -> list[tuple[int, int]]:
    """Takes signature sizes (sheets) and returns page indexes."""
    signature_ranges: list[tuple[int, int]] = []
    current_page = start_index
    for sig in signature_sizes:
        signature_ranges.append((current_page, current_page + (sig * 4) - 1))
        current_page += (sig * 4)
    return signature_ranges


def calc_signature_sizes(num_pages: int, num_signatures: int) -> list[int]:
    """
    Calculate the number of sheets in each signature for a given number of pages and signature count.
    """
    if num_pages % 4 != 0:
        raise ValueError("Number of pages must be a multiple of 4.")
    num_sheets = num_pages // 4

    if num_sheets < num_signatures:
        raise ValueError(f"Not enough pages ({num_pages}) for {num_signatures} signatures, "
                         f"need minimum {num_signatures * 4}.")

    signature_sizes = [num_sheets // num_signatures] * num_signatures
    remaining_sheets = num_sheets - ((num_sheets // num_signatures) * num_signatures)
    assert remaining_sheets < num_signatures
    middle_sig_pos = ceil(num_signatures / 2) - 1

    if remaining_sheets == 0:
        pass
    elif remaining_sheets % 2 == 0:
        left_block_start = middle_sig_pos - ((remaining_sheets // 2) - 1)
        left_block_stop = middle_sig_pos
        if num_signatures % 2 == 1:
            left_block_start -= 1
            left_block_stop -= 1
        right_block_start = middle_sig_pos + 1
        right_block_stop = middle_sig_pos + 1 + ((remaining_sheets // 2) - 1)
        for i in range(left_block_start, left_block_stop + 1):
            signature_sizes[i] += 1
        for i in range(right_block_start, right_block_stop + 1):
            signature_sizes[i] += 1
    else:
        block_start = middle_sig_pos - (remaining_sheets // 2)
        for i in range(block_start, block_start + remaining_sheets):
            signature_sizes[i] += 1

    return signature_sizes


def calc_signature_page_ranges(signature_sizes: list[int]) -> list[tuple[int, int]]:
    """
    Parameters
    ----------
    signature_sizes: list[int]
        Number of sheets in each signature, each sheet will be 4 pages.

    Returns
    -------
    list[tuple[int, int]]
        Start and ending page numbers for each signature.
    """

    page_blocks: list[tuple[int, int]] = []
    current_page = 0
    for sig_size in signature_sizes:
        page_blocks.append((current_page, current_page + 4 * sig_size - 1))
        current_page = page_blocks[-1][1] + 1
    return page_blocks


def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s')
    app = wx.App()
    frm = MainWindow(None, title="Louis' Book Formatter - 2.0.0")
    frm.Show()
    app.MainLoop()



if __name__ == '__main__':
    main()
