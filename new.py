import logging
from math import ceil, inf
from pathlib import Path
from token import LEFTSHIFT

from PyQt6.QtWidgets import QApplication, QPushButton, QMainWindow, QVBoxLayout, QGridLayout, QLabel, QSpinBox, QWidget, \
    QHBoxLayout, QFileDialog, QMessageBox

from pypdf import PdfReader, PdfWriter, PaperSize

VERSION = "2.0.0"
IDEAL_MAX_SIG_SIZE = 4


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Louis' Book Formatter - {VERSION}")

        self.pdf_reader: None | PdfReader = None
        self.pdf_writer = PdfWriter()

        l_input_document = QHBoxLayout()
        w_input_browse_button = QPushButton("Browse")
        w_input_browse_button.pressed.connect(self.select_input_path)
        self.w_input_document_label = QLabel("Select input document...")
        self.input_document_path = ""
        l_input_document.addWidget(w_input_browse_button)
        l_input_document.addWidget(self.w_input_document_label)
        l_input_document.addStretch()


        l_num_signatures = QHBoxLayout()
        l_num_signatures.addWidget(QLabel("Number of Signatures:"))
        self.w_num_sigs = QSpinBox()
        self.w_num_sigs.setMinimum(1)
        self.w_num_sigs.setValue(5)
        self.w_num_sigs.valueChanged.connect(self.number_of_signatures_changed)
        l_num_signatures.addWidget(self.w_num_sigs)
        self.w_num_pages_label = QLabel("")
        l_num_signatures.addWidget(self.w_num_pages_label)
        l_num_signatures.addStretch()

        self.l_signature_sizes = QHBoxLayout()
        self.sig_size_spins: list[QSpinBox] = []
        self.number_of_signatures_changed(self.w_num_sigs.value())

        layout = QVBoxLayout()
        layout.addLayout(l_input_document)
        layout.addLayout(l_num_signatures)
        layout.addLayout(self.l_signature_sizes)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

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
                sig_sizes = calc_signature_sizes(self.pdf_reader.get_num_pages(), n)
                for size, size_control in zip(sig_sizes, self.sig_size_spins):
                    size_control.setValue(size)
            self.l_signature_sizes.addWidget(w)

    def read_input_file(self):
        if self.input_document_path:
            self.pdf_reader = PdfReader(self.input_document_path)

            if self.pdf_reader.get_num_pages() % 4 == 0:
                self.w_num_pages_label.setText(
                    f"({self.pdf_reader.get_num_pages()} pages, {self.pdf_reader.get_num_pages() // 4} sheets)"
                )
                self.update_signature_suggestions()
            else:
                QMessageBox.critical(
                    self,
                    "Bad File",
                    f"Input PDF must have a number of pages divisible by 4, has {self.pdf_reader.get_num_pages()}.",
                    buttons=QMessageBox.StandardButton.Ok
                )
                self.pdf_reader = None
                self.input_document_path = ""
                self.w_input_document_label.setText("Select input document...")
        else:
            logging.error(f"Cannot read input file, input path is {repr(self.input_document_path)}")

    def update_signature_suggestions(self):
        if self.pdf_reader is None:
            logging.error("Cannot update suggested signatures, reader is None")
        else:
            num_pages = self.pdf_reader.get_num_pages()
            max_size = num_pages
            n = 0
            while max_size > IDEAL_MAX_SIG_SIZE:
                n += 1
                self.w_num_sigs.setValue(n)
                max_size = max([s.value() for s in self.sig_size_spins])


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


def test():
    with open("handbook.pdf", "rb") as fh:
        reader = PdfReader(fh)

    writer = PdfWriter()
    writer.add_blank_page(width=PaperSize.A4.width, height=PaperSize.A4.height)

    with open("test.pdf", "bw") as fh:
        writer.write(fh)
        writer.close()


def main():
    app = QApplication([])

    window = MainWindow()
    window.show()

    app.exec()



if __name__ == '__main__':
    main()
