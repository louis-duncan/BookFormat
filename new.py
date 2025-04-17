import io
import json
import logging
import time
from json import JSONDecodeError
from math import ceil
from pathlib import Path
from typing import Generator, Any, Optional, Union

import pymupdf
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

        self.root = wx.Panel(self)
        root = self.root

        self.input_document_path = None
        self.output_document_path = None
        self.pdf_reader = None
        self.start_page = 0
        self.end_page = 0

        self.s_input_sizer = wx.StaticBoxSizer(wx.VERTICAL, root, "Input")
        w_browse_button = wx.Button(root, label="Browse")
        w_browse_button.Bind(wx.EVT_BUTTON, self.select_input_path)
        self.w_input_text = wx.StaticText(root, label="Select input document...")
        s_input_file_select = wx.BoxSizer(wx.HORIZONTAL)
        s_input_file_select.Add(w_browse_button, flag=wx.ALIGN_CENTER_VERTICAL)
        s_input_file_select.Add(self.w_input_text, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, border=10)

        s_input_pages = wx.BoxSizer(wx.HORIZONTAL)
        s_input_pages.Add(wx.StaticText(root, label="Pages:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self.w_pages_input = wx.TextCtrl(root, size=wx.Size(50, -1))
        s_input_pages.Add(self.w_pages_input, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=10)
        w_refresh_button = wx.Button(root, label="Update")
        s_input_pages.Add(w_refresh_button, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=10)
        w_refresh_button.Bind(wx.EVT_BUTTON, self.refresh_button)
        w_reset_button = wx.Button(root, label="Reset")
        s_input_pages.Add(w_reset_button, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=10)
        w_reset_button.Bind(wx.EVT_BUTTON, self.reset_button)

        self.s_input_sizer.Add(s_input_file_select)
        self.s_input_sizer.Add(s_input_pages, flag=wx.TOP, border=10)

        s_signatures = wx.StaticBoxSizer(wx.VERTICAL, root, "Signatures")
        s_num_signatures = wx.BoxSizer(wx.HORIZONTAL)
        s_num_signatures.Add(wx.StaticText(root, label="Num' Signatures:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self.w_num_signatures = wx.SpinCtrl(root, value="5", size=wx.Size(40, -1))
        self.w_num_signatures.Disable()
        self.w_num_signatures.SetMin(1)
        self.w_num_signatures.Bind(wx.EVT_SPINCTRL, self.number_of_sig_changes)
        s_num_signatures.Add(self.w_num_signatures, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        s_signatures.Add(s_num_signatures)

        self.s_sig_spins = wx.StaticBoxSizer(wx.HORIZONTAL, root, "")
        self.sig_spins: list[wx.SpinCtrl] = []
        for _ in range(5):
            n = wx.SpinCtrl(root, value="1", size=wx.Size(40, -1))
            self.sig_spins.append(n)
            self.s_sig_spins.Add(n)
            n.Disable()
        s_signatures.Add(self.s_sig_spins, flag=wx.TOP, border=5)

        self.w_signatures_label = wx.StaticText(root, label="")
        s_signatures.Add(self.w_signatures_label, flag=wx.TOP, border=5)

        s_options = wx.StaticBoxSizer(wx.HORIZONTAL, root, "Options")
        s_options_grid = wx.GridBagSizer(5, 5)
        s_options_grid.Add(
            wx.StaticText(root, label="Add Lines:"),
            (0, 0),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        self.w_add_lines = wx.CheckBox(root)
        s_options_grid.Add(self.w_add_lines, (0, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)
        s_options_grid.Add(
            wx.StaticText(root, label="Double Up:"),
            (0, 3),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        self.w_double_up = wx.CheckBox(root)
        s_options_grid.Add(self.w_double_up, (0, 4), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)
        s_options_grid.Add(
            wx.StaticText(root, label="Double Up Page Height:"),
            (1, 3),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        self.w_double_up_page_height = wx.SpinCtrlDouble(root, value="100", inc=0.1, max=999)
        s_options_grid.Add(self.w_double_up_page_height, (1, 4), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)
        s_options_grid.Add(
            wx.StaticText(root, label="mm"),
            (1, 5),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT
        )
        s_options_grid.Add(
            wx.StaticText(root, label="Double Up Center Margin:"),
            (2, 3),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        self.w_double_up_centre_margin = wx.SpinCtrlDouble(root, value="-1", min=-1, inc=0.5, max=99)
        s_options_grid.Add(self.w_double_up_centre_margin, (2, 4), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)
        s_options_grid.Add(
            wx.StaticText(root, label="mm (-1 will auto margin)"),
            (2, 5),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT
        )
        s_options.Add(s_options_grid, flag=wx.EXPAND)

        s_output = wx.StaticBoxSizer(wx.VERTICAL, root, "Output")
        w_output_browse_button = wx.Button(root, label="Browse")
        w_output_browse_button.Bind(wx.EVT_BUTTON, self.select_output_path)
        self.w_output_text = wx.StaticText(root, label="Select output destination...")
        s_output_file_select = wx.BoxSizer(wx.HORIZONTAL)
        s_output_file_select.Add(w_output_browse_button, flag=wx.ALIGN_CENTER_VERTICAL)
        s_output_file_select.Add(self.w_output_text, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, border=10)
        s_output.Add(s_output_file_select)
        s_save_sigs_separately = wx.BoxSizer(wx.HORIZONTAL)
        s_save_sigs_separately.Add(
            wx.StaticText(root, label="Save Signatures Separately:"),
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT, border=10
        )
        self.w_save_sigs_separately = wx.CheckBox(root)
        s_save_sigs_separately.Add(self.w_save_sigs_separately, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        s_output.Add(s_save_sigs_separately, flag=wx.TOP, border=10)

        self.w_start_process = wx.Button(root, label="Start Process")
        self.w_start_process.Disable()
        self.w_start_process.Bind(wx.EVT_BUTTON, self.process_document)

        self.w_progress_bar = wx.Gauge(root, range=100)
        self.w_progress_text = wx.StaticText(root, label="foo", style=wx.ALIGN_CENTER)
        self.w_progress_bar.Hide()
        self.w_progress_text.Hide()

        self.s_main = wx.BoxSizer(wx.VERTICAL)
        self.s_main.Add(self.s_input_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        self.s_main.Add(s_signatures, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        self.s_main.Add(s_options, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        self.s_main.Add(s_output, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        self.s_main.Add(self.w_start_process, flag=wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        self.s_main.Add(self.w_progress_bar, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        self.s_main.Add(self.w_progress_text, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        root.SetSizer(self.s_main)
        self.s_main.Fit(self)
        self.SetMinSize(self.GetSize())

        self.load_settings()
        self.Bind(wx.EVT_CLOSE, self.save_settings)

    def load_settings(self):
        try:
            with SETTINGS_PATH.open("r") as fh:
                settings_data = json.load(fh)
            self.w_add_lines.SetValue(settings_data['add_side_lines'])
            self.w_double_up.SetValue(settings_data['double_up'])
            self.w_double_up_page_height.SetValue(settings_data['double_up_height'])
            self.w_double_up_centre_margin.SetValue(settings_data['double_up_margin'])
            self.w_save_sigs_separately.SetValue(settings_data['save_signatures_separately'])

        except FileNotFoundError:
            logging.debug("No settings file")
        except JSONDecodeError as e:
            logging.exception(e)

    def save_settings(self, event: wx.Event):
        try:
            settings_data = {
                'add_side_lines': self.w_add_lines.GetValue(),
                'double_up': self.w_double_up.GetValue(),
                'double_up_height': self.w_double_up_page_height.GetValue(),
                'double_up_margin': self.w_double_up_centre_margin.GetValue(),
                'save_signatures_separately': self.w_save_sigs_separately.GetValue()
            }
            with open(SETTINGS_PATH, "w") as fh:
                # noinspection PyTypeChecker
                json.dump(settings_data, fh)
        except Exception as e:
            logging.exception(e)
        event.Skip()

    def refresh_button(self, _=None):
        if self.pdf_reader is not None:
            new_start, new_end = get_page_range_numbers(self.w_pages_input.GetValue(), self.pdf_reader.get_num_pages())
            new_num = new_end - new_start + 1
            if new_num % 4 != 0:
                dlg = wx.MessageDialog(
                    self,
                    f"Input page range must have a number of pages divisible by 4, has {new_num}.",
                    "Bad Page Range",
                    wx.OK | wx.ICON_WARNING | wx.CENTER
                )
                dlg.ShowModal()
            else:
                self.start_page = new_start
                self.end_page = new_end
                self.input_pages_changed()

    def reset_button(self, _=None):
        if self.pdf_reader is not None:
            self.start_page = 1
            self.end_page = self.pdf_reader.get_num_pages()
            self.w_pages_input.ChangeValue(f"1-{self.end_page}")
            self.refresh_button()

    def get_num_pages(self):
        return (self.end_page - self.start_page) + 1

    def select_input_path(self, _):
        if self.input_document_path:
            start_dir = str(Path(self.input_document_path).parent)
        else:
            start_dir = "${HOME}"

        with wx.FileDialog(
                self,
                message="Open PDF file",
                defaultDir=start_dir,
                wildcard="PDF files (*.pdf)|*.pdf",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            file_path = fileDialog.GetPath()

        self.w_input_text.SetLabelText(file_path)
        self.input_document_path = file_path
        self.read_input_file()
        if self.input_document_path and self.output_document_path:
            self.w_start_process.Enable()
        else:
            self.w_start_process.Disable()

    def select_output_path(self, _):
        if self.output_document_path:
            start_dir = str(Path(self.output_document_path).parent)
        elif self.input_document_path:
            start_dir = str(Path(self.input_document_path).parent)
        else:
            start_dir = "${HOME}"

        with wx.FileDialog(
                self,
                message="Save PDF file",
                defaultDir=start_dir,
                defaultFile="output.pdf",
                wildcard="PDF files (*.pdf)|*.pdf",
                style=wx.FD_SAVE
        ) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            file_path = fileDialog.GetPath()

        self.w_output_text.SetLabelText(file_path)
        self.output_document_path = file_path
        if self.input_document_path and self.output_document_path:
            self.w_start_process.Enable()
        else:
            self.w_start_process.Disable()
        self.s_main.Fit(self)
        self.Update()

    def number_of_sig_changes(self, e):
        if self.pdf_reader is not None:
            self.update_sig_spins(e.Int)

    def update_sig_spins(self, n: int):
        self.s_sig_spins.Clear(True)

        sizes = calc_signature_sizes(self.get_num_pages(), n)
        self.sig_spins = [wx.SpinCtrl(self.root, value=str(s), size=wx.Size(40, -1)) for s in sizes]

        for w in self.sig_spins:
            self.s_sig_spins.Add(w)
            # TODO: Add bind

        self.s_main.Fit(self)
        self.s_main.Layout()

    def input_pages_changed(self):
        num_sigs = get_ideal_num_sigs(self.get_num_pages())
        self.w_num_signatures.SetValue(num_sigs)
        self.w_signatures_label.SetLabelText(f"({self.get_num_pages() // 4} sheets)")
        self.update_sig_spins(n=num_sigs)
        self.w_num_signatures.Enable()

    def read_input_file(self):
        if self.input_document_path:
            self.pdf_reader = PdfReader(self.input_document_path)
            num_pages = self.pdf_reader.get_num_pages()

            if num_pages % 4 == 0:
                self.w_pages_input.ChangeValue(f"{1}-{num_pages}")
                self.start_page = 1
                self.end_page = self.pdf_reader.get_num_pages()
                self.input_pages_changed()
            else:
                dlg = wx.MessageDialog(
                    self,
                    f"Input PDF must have a number of pages divisible by 4, has {num_pages}.",
                    "Bad File",
                    wx.OK | wx.ICON_WARNING | wx.CENTER
                )
                dlg.ShowModal()

                self.pdf_reader = None
                self.input_document_path = ""
                self.w_input_text.SetLabelText("Select input document...")
        else:
            logging.error(f"Cannot read input file, input path is {repr(self.input_document_path)}")

    """
    def check_sheet_counts(self, _):
        if self.pdf_reader is None:
            self.w_sigs_error_label.setText("")
        else:
            num_sheets = sum([s.value() for s in self.sig_size_spins])
            if num_sheets * 4 != self.get_num_pages():
                self.w_sigs_error_label.setText(f"Incorrect number of sheets: {num_sheets}")
            else:
                self.w_sigs_error_label.setText("")
    """

    def process_document(self, _):
        if self.pdf_reader is None:
            raise ValueError("Should not have access process function without a pdfreader loaded.")

        if sum([s.GetValue() for s in self.sig_spins]) != self.get_num_pages() // 4:
            dlg = wx.MessageDialog(
                self,
                f"Signature sizes do not sum to the expected value; "
                f"{sum([s.GetValue() for s in self.sig_spins])}, expected {self.get_num_pages() // 4}.",
                "Invalid Signature Values",
                wx.OK | wx.ICON_WARNING | wx.CENTER
            )
            dlg.ShowModal()
            return

        self.w_progress_bar.Show()
        self.w_progress_text.Show()
        self.w_start_process.Disable()
        self.s_main.Fit(self)

        if self.w_add_lines.GetValue():
            self.pdf_reader = add_lines(self.pdf_reader, self.end_page - 1)

        self.w_progress_text.SetLabelText("Creating signatures...")
        total_sides = self.get_num_pages() // 2
        self.w_progress_bar.SetRange(total_sides)

        sig_sizes = [s.GetValue() for s in self.sig_spins]
        signatures: list[PdfWriter] = []
        for page_range in get_signature_page_indexes(sig_sizes, self.start_page - 1):
            signatures.append(
                create_signature(
                    self.pdf_reader,
                    page_range,
                    self.w_progress_bar
                )
            )

        if self.w_double_up.GetValue():
            logging.info("Doubling up pages")
            doubled_up_sigs = []
            self.w_progress_bar.SetValue(0)
            self.w_progress_text.SetLabelText("Creating doubled-up pages...")
            center_margin = None if self.w_double_up_centre_margin.GetValue() < 0 \
                else self.w_double_up_centre_margin.GetValue()
            for sig in signatures:
                doubled_up_sigs.append(
                    create_double_up(
                        sig,
                        target_height_mm=self.w_double_up_page_height.GetValue(),
                        progress_bar=self.w_progress_bar,
                        center_margin_mm=center_margin
                    )
                )
            signatures = doubled_up_sigs

        self.w_progress_bar.SetValue(0)
        self.w_progress_bar.SetRange(len(signatures))

        if self.w_save_sigs_separately.GetValue():
            self.w_progress_text.SetLabelText("Saving signatures...")
            for i, s in enumerate(signatures):
                file_name, ext = self.output_document_path.rsplit(".", 1)
                with open(file_name + f"_{i}." + ext, "bw") as fh:
                    writer = PdfWriter()
                    for page in s.pages:
                        writer.insert_page(page, writer.get_num_pages())
                    writer.write(fh)
                    writer.close()
                    self.w_progress_bar.SetValue(self.w_progress_bar.GetValue() + 1)
        else:
            merger = PdfWriter()
            self.w_progress_text.SetLabelText("Merging Signatures...")
            for s in signatures:
                for page in s.pages:
                    merger.insert_page(page, merger.get_num_pages())
                    self.w_progress_bar.SetValue(self.w_progress_bar.GetValue() + 1)

            self.w_progress_text.SetLabelText("Saving output PDF...")
            with open(self.output_document_path, "bw") as fh:
                merger.write(fh)
                merger.close()

        self.w_progress_bar.Hide()
        self.w_progress_text.SetLabelText("Done!")
        self.s_main.Fit(self)


def add_lines(reader: PdfReader, line_page_index: int) -> PdfReader:
    logging.debug("Adding lines")

    tmp_writer = PdfWriter(reader)
    pdf_stream = io.BytesIO()
    tmp_writer.write(stream=pdf_stream)
    pdf_stream.seek(0)
    mu_pdf = pymupdf.Document(stream=pdf_stream)
    last_page = mu_pdf.load_page(line_page_index)
    width = last_page.mediabox.width
    height = last_page.mediabox.height
    # pymupdf uses top left as origin
    top_p1 = (0, 0)
    top_p2 = (width, 0)
    side_p1 = top_p2
    side_p2 = (width, height)
    last_page.draw_line(
        p1=top_p1,
        p2=top_p2
    )
    last_page.draw_line(
        p1=side_p1,
        p2=side_p2
    )
    mu_stream = io.BytesIO(mu_pdf.tobytes())
    mu_stream.seek(0)
    return PdfReader(mu_stream)


def get_page_range_numbers(range_str: str, max_page: int) -> tuple[int, int]:
    p1, p2 = range_str.split("-")
    try:
        start = int(p1)
    except ValueError:
        start = 1
    try:
        end = int(p2)
    except ValueError:
        end = max_page

    return start, end


def create_signature(
        reader: PdfReader,
        pages: tuple[int, int],
        progress_bar: Optional[wx.Gauge] = None
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
            progress_bar.SetValue(progress_bar.GetValue() + 1)
            wx.Yield()

    return new_pdf


def create_double_up(
        document: PdfReader | PdfWriter,
        output_size: Dimensions = PaperSize.A4,
        target_height_mm: Optional[float] = None,
        progress_bar: Union[None, wx.Gauge] = None,
        center_margin_mm: Optional[int] = None
) -> PdfWriter:
    writer = PdfWriter()

    target_height_points = mm_to_pnt(target_height_mm)
    scale = target_height_points / document.pages[0].mediabox.height
    scaled_size = document.pages[0].mediabox.width * scale, document.pages[0].mediabox.height * scale

    if center_margin_mm is None:
        logging.debug("Placing double up pages equally spaced")
        bottom_y = (output_size.height // 2 - scaled_size[1]) // 2
        top_y = bottom_y + (output_size.height // 2)
    else:
        logging.debug(f"Placing double up pages with {center_margin_mm}mm center margin")
        bottom_y = ((output_size.height // 2) - scaled_size[1]) - mm_to_pnt(center_margin_mm)
        top_y = (output_size.height // 2) + mm_to_pnt(center_margin_mm)

    x = (output_size.width - scaled_size[0]) // 2

    top_transform = Transformation().scale(scale, scale).translate(x, top_y)
    bottom_transform = Transformation().scale(scale, scale).translate(x, bottom_y)

    for original_page in document.pages:
        writer.add_blank_page(output_size.width, output_size.height)
        new_page = writer.pages[len(writer.pages) - 1]
        new_page.merge_transformed_page(original_page, top_transform)
        new_page.merge_transformed_page(original_page, bottom_transform)

        if progress_bar is not None:
            progress_bar.SetValue(progress_bar.GetValue() + 1)
            wx.Yield()

    return writer


def mm_to_pnt(mm: float) -> float:
    return mm * 2.8346472


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


def get_ideal_num_sigs(num_pages: int) -> int:
    n = 1
    sizes = [num_pages]
    while max(sizes) > IDEAL_MAX_SIG_SIZE:
        n += 1
        sizes = calc_signature_sizes(num_pages, n)
    return n


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
