from PyPDF2 import PdfFileReader, PdfFileWriter
import easygui


def calc_sigs_from_number(number_of_pages, number_of_sigs):
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