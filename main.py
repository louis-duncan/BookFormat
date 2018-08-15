from PyPDF2 import PdfFileReader, PdfFileWriter, pdf
import easygui


def calc_sig_sizes(number_of_pages, number_of_sigs):
    if number_of_pages % 4 != 0:
        return False
    else:
        pass
    base_sig_size = number_of_pages // number_of_sigs
    remainder_pages = number_of_pages % number_of_sigs
    sig_sizes = []
    for s in range(number_of_sigs):
        excess = base_sig_size % 4
        sig_sizes.append(base_sig_size - excess)
        remainder_pages += excess
    assert remainder_pages % 4 == 0
    extra_folios = int(remainder_pages / 4)
    if extra_folios == 0:
        pass
    else:
        middle = round((len(sig_sizes) / 2) + 0.1) - 1
        left_pos = middle
        right_pos = middle + 1
        if (len(sig_sizes) % 2 == 1) and (extra_folios % 2 == 0):
            left_pos -= 1
        else:
            pass
        direction = "L"
        for e in range(extra_folios):
            if direction == "L":
                sig_sizes[left_pos] += 4
                left_pos -= 1
                direction = "R"
            else:
                sig_sizes[right_pos] += 4
                right_pos += 1
                direction = "L"
    assert sum(sig_sizes) == number_of_pages

    return sig_sizes


def can_be_int(text):
    try:
        int(text)
        return True
    except ValueError:
        pass
    except TypeError:
        pass
    return False


def booklet_format(input_pdf, page_range):
    assert ((page_range[1] - page_range[0]) + 1) % 4 == 0
    output_pages = []
    doc_width = input_pdf.getPage(0).mediaBox[2]
    doc_height = input_pdf.getPage(0).mediaBox[3]
    head = page_range[0]
    tail = page_range[1]
    flip = True
    while head < tail:
        if flip:
            left_page_num, right_page_num = tail, head
            flip = False
        else:
            left_page_num, right_page_num = head, tail
            flip = True
        head += 1
        tail -= 1
        print("\t{}-{}".format(left_page_num, right_page_num))
        left_page = input_pdf.getPage(left_page_num)
        right_page = input_pdf.getPage(right_page_num)
        new_page = pdf.PageObject(pdf=input_pdf)
        new_page = new_page.createBlankPage(input_pdf, doc_width * 2, doc_height)
        new_page.mergeTranslatedPage(left_page, 0.0, 0.0, True)
        new_page.mergeTranslatedPage(right_page, doc_width, 0.0, True)

        output_pages.append(new_page)
    return output_pages


def book_format(input_pdf, sig_sizes):
    page_ranges = []
    running_total = 0
    for s in sig_sizes:
        start = running_total
        end = running_total + (s - 1)
        running_total = end + 1
        page_ranges.append((start, end))
    output_pages = []
    for i, pr in enumerate(page_ranges):
        print("Formatting sig. {}: pages {} to {}...".format(i + 1, pr[0], pr[1]))
        for p in booklet_format(input_pdf, pr):
            output_pages.append(p)
    return output_pages


def multi_page_format():
    file_name = easygui.fileopenbox("Select PDF to format:","","*.pdf", ["*.pdf", "*.*"])
    if file_name is None:
        return None
    else:
        pass

    input_fh = open(file_name, "rb")
    reader = PdfFileReader(input_fh, strict=False)
    number_of_pages = reader.getNumPages()
    if number_of_pages % 2 == 0:
        pass
    else:
        easygui.msgbox("The document should have an even number of pages.\n"
                       "This document has {} pages, and so a blank page will be added at the end.")
    output_file_name = easygui.filesavebox("Select save location:", "", "multi-page.pdf", "*.pdf")
    if output_file_name is None:
        return None
    else:
        pass

    new_page_height = 297  # In mm !
    new_page_width = 210  # In mm !
    final_page_height = 125   # In mm !

    # Convert mm to inches, then to the PDF space
    new_page_height = float((new_page_height * 0.03937007874) / (1 / 72))
    new_page_width = float((new_page_width * 0.03937007874) / (1 / 72))
    final_page_height = float((final_page_height * 0.03937007874) / (1 / 72))

    doc_width = float(reader.getPage(0).mediaBox[2])
    doc_height = float(reader.getPage(0).mediaBox[3])
    effective_scale = float(final_page_height / doc_height)
    scaled_width = float(effective_scale * doc_width)

    print("Scale: {}%\n"
          "Original doc width: {}, scaled to {}\n"
          "Original doc height: {}, scaled to {}".format(round(effective_scale * 100, 2), doc_width, scaled_width,
                                                         doc_height, round(doc_height * effective_scale)))

    d_x = (new_page_width - scaled_width) / 2
    top_d_y = ((new_page_height / 2) - final_page_height) / 2
    bottom_d_y = top_d_y + (new_page_height / 2)

    output_pages = []
    for p in range(0, number_of_pages, 4):
        print("{}, {}, {}, {}".format(p, p + 1, p + 2, p + 3))
        new_front_page = pdf.PageObject(pdf=reader)
        new_front_page = new_front_page.createBlankPage(reader, new_page_width, new_page_height)
        try:
            new_front_page.mergeScaledTranslatedPage(reader.getPage(p), effective_scale, d_x, top_d_y, True)
        except IndexError:
            pass
        try:
            new_front_page.mergeScaledTranslatedPage(reader.getPage(p + 2), effective_scale, d_x, bottom_d_y, True)
        except IndexError:
            pass
        new_back_page = pdf.PageObject(pdf=reader)
        new_back_page = new_back_page.createBlankPage(reader, new_page_width, new_page_height)
        try:
            new_back_page.mergeScaledTranslatedPage(reader.getPage(p + 1), effective_scale, d_x, top_d_y, True)
        except IndexError:
            pass
        try:
            new_back_page.mergeScaledTranslatedPage(reader.getPage(p + 3), effective_scale, d_x, bottom_d_y, True)
        except IndexError:
            pass
        output_pages.append(new_front_page)
        output_pages.append(new_back_page)

    # Put output pages into an output stream
    output_stream = PdfFileWriter()
    print("\nSaving...")
    for op in output_pages:
        output_stream.addPage(op)
    output_fh = open(output_file_name, "bw")
    output_stream.write(output_fh)
    # Close the output stream
    output_fh.close()
    # Close the input stream
    input_fh.close()
    easygui.msgbox("Done!")


def double_up_format():
    file_name = easygui.fileopenbox("Select PDF to format:","","*.pdf", ["*.pdf", "*.*"])
    if file_name is None:
        return None
    else:
        pass

    input_fh = open(file_name, "rb")
    reader = PdfFileReader(input_fh, strict=False)
    number_of_pages = reader.getNumPages()
    if number_of_pages % 2 == 0:
        pass
    else:
        easygui.msgbox("The document should have an even number of pages.\n"
                       "This document has {} pages, and so a blank page will be added at the end.")
    output_file_name = easygui.filesavebox("Select save location:", "", "double-up.pdf", "*.pdf")
    if output_file_name is None:
        return None
    else:
        pass

    # Give sizes for new pages, they will ba A4.
    new_page_height = 297  # In mm !
    new_page_width = 210  # In mm !
    # This is the height we want our input pages to be scaled to.
    final_page_height = 124   # In mm !

    # Convert mm to inches, then to the PDF space
    new_page_height = float((new_page_height * 0.03937007874) / (1 / 72))
    new_page_width = float((new_page_width * 0.03937007874) / (1 / 72))
    final_page_height = float((final_page_height * 0.03937007874) / (1 / 72))

    doc_width = float(reader.getPage(0).mediaBox[2])
    doc_height = float(reader.getPage(0).mediaBox[3])
    effective_scale = float(final_page_height / doc_height)
    scaled_width = float(effective_scale * doc_width)

    print("Scale: {}%\n"
          "Original doc width: {}, scaled to {}\n"
          "Original doc height: {}, scaled to {}".format(round(effective_scale * 100, 2), doc_width, scaled_width,
                                                         doc_height, round(doc_height * effective_scale)))

    d_x = (new_page_width - scaled_width) / 2
    top_d_y = ((new_page_height / 2) - final_page_height) / 2
    bottom_d_y = top_d_y + (new_page_height / 2)

    output_pages = []
    for p in range(0, number_of_pages):
        print("> {}".format(p))
        new_page = pdf.PageObject(pdf=reader)
        new_page = new_page.createBlankPage(reader, new_page_width, new_page_height)
        new_page.mergeScaledTranslatedPage(reader.getPage(p), effective_scale, d_x, top_d_y, True)
        new_page.mergeScaledTranslatedPage(reader.getPage(p), effective_scale, d_x, bottom_d_y, True)

        output_pages.append(new_page)

    # Put output pages into an output stream
    output_stream = PdfFileWriter()
    print("\nSaving...")
    for op in output_pages:
        output_stream.addPage(op)
    output_fh = open(output_file_name, "bw")
    output_stream.write(output_fh)
    # Close the output stream
    output_fh.close()
    # Close the input stream
    input_fh.close()
    easygui.msgbox("Done!")


def main():
    # Get file
    print("Select Source File...")
    file_name = easygui.fileopenbox("Select File", "", "*.pdf", ["\*.pdf", "*.*"])
    if file_name is None:
        return None
    else:
        pass
    print(file_name)
    # Get number of sigs
    input_fh = open(file_name, "rb")
    reader = PdfFileReader(input_fh, strict=False)
    number_of_pages = reader.getNumPages()
    if number_of_pages % 4 == 0:
        pass
    else:
        easygui.msgbox("The document must have a number of pages divisible by 4.\n"
                       "The selected document has {} pages.".format(number_of_pages))
        return None
    number_of_sigs = None
    msg = "Enter Desired Number of Signatures:"
    warning = "Input must be a whole number!"
    while not can_be_int(number_of_sigs):
        number_of_sigs = easygui.enterbox(msg, "")
        if number_of_sigs is None:
            return None
        else:
            pass
        if msg.endswith(warning):
            pass
        else:
            msg += "\n" + warning
    number_of_sigs = int(number_of_sigs)
    sig_sizes = calc_sig_sizes(number_of_pages, number_of_sigs=number_of_sigs)
    labels = []
    working_sig_sizes = []
    for i, s in enumerate(sig_sizes):
        labels.append("Sig. " + str(i + 1))
        working_sig_sizes.append(str(int(s / 4)))
    # Show sig sizing
    happy = False
    sig_base_msg = "These are the recommended signature sizes (number of sheets).\n" \
                   "Adjust if desired. Click OK to commence formatting:\n" \
                   "(Total number must equal {})".format(int(sum(sig_sizes) / 4))
    msg = sig_base_msg
    while not happy:
        working_sig_sizes = easygui.multenterbox(msg,
                                                 "",
                                                 labels,
                                                 working_sig_sizes,
                                                 )
        if working_sig_sizes is None:
            return None
        else:
            pass

        count = 0
        value_error = False
        for w in working_sig_sizes:
            try:
                count += int(w)
            except ValueError:
                value_error = True
        total_error = False
        if count != int(sum(sig_sizes) / 4):
            total_error = True
        else:
            pass
        msg = sig_base_msg
        if value_error:
            msg += "\n\nInputs must be whole numbers!"
        if total_error:
            msg += "\n\nInputs do not total {}!".format(int(sum(sig_sizes) / 4))
        if True in (value_error, total_error):
            happy = False
        else:
            happy = True
    for i, s in enumerate(working_sig_sizes):
        sig_sizes[i] = int(s) * 4

    # Get output dir
    print("\nSelect Output File...")
    output_file_name = easygui.filesavebox("Select Save Location", "", "ouput.pdf", "*.pdf")
    if output_file_name is None:
        return None
    else:
        if output_file_name.upper().endswith(".PDF"):
            pass
        else:
            output_file_name = output_file_name + ".pdf"
    print(output_file_name)

    # Run pdf merging
    print("\nOrdering pages:")
    output_pages = book_format(reader, sig_sizes)

    # Put output pages into an output stream
    output_stream = PdfFileWriter()
    print("\nSaving...")
    for op in output_pages:
        output_stream.addPage(op)
    output_fh = open(output_file_name, "bw")
    output_stream.write(output_fh)
    # Close the output stream
    output_fh.close()
    # Close the input stream
    input_fh.close()
    easygui.msgbox("Done!")


def alt_flip():
    input_fh = open(easygui.fileopenbox(), "rb")
    reader = PdfFileReader(input_fh, strict=False)
    doc_width = float(reader.getPage(0).mediaBox[2])
    doc_height = float(reader.getPage(0).mediaBox[3])

    output_pages = []

    for p in range(reader.getNumPages()):
        current_page: pdf.PageObject = reader.getPage(p)
        if bool(p % 2):
            current_page.rotateClockwise(180)
        else:
            pass
        output_pages.append(current_page)

    output_stream = PdfFileWriter()
    for op in output_pages:
        output_stream.addPage(op)

    output_fh = open(easygui.filesavebox(), "bw")
    output_stream.write(output_fh)


if __name__ == '__main__':
    choices = ["Book Format", "Multi-page Format", "Double-up Format", "Close"]
    choice = easygui.buttonbox("", "", choices)
    if choice == choices[0]:
        main()
    elif choice == choices[1]:
        multi_page_format()
    elif choice == choices[2]:
        double_up_format()
    else:
        pass
