#!/usr/bin/env python3
import argparse
import fitz  # PyMuPDF


def add_sample_number(
    input_pdf: str,
    output_pdf: str,
    label: str,
    sample_nr: str,
) -> None:
    """
    Add "<label>: <sample_nr>" to the top of the FIRST page of a PDF.
    """
    doc = fitz.open(input_pdf)
    page = doc[0]
    rect = page.rect

    # Compose final text
    text = f"{label}: {sample_nr}"

    # Style
    font_size = 14.0
    font_name = "helv"

    # Measure width for centering
    text_width = fitz.get_text_length(
        text,
        fontname=font_name,
        fontsize=font_size
    )

    x = (rect.width - text_width) / 2.0
    y = 20.0  # distance from the top

    # Draw on page
    page.insert_text(
        (x, y),
        text,
        fontsize=font_size,
        fontname=font_name,
        fill=(0, 0, 0),
    )

    doc.save(output_pdf)
    doc.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add labeled sample number to FIRST page of a PDF."
    )
    parser.add_argument("--to", required=True, help="Input PDF file")
    parser.add_argument("--label", required=True, help="Label prefix, e.g. LIMS_Sample_Nr")
    parser.add_argument("--sample-nr", required=True, help="Sample number or ID")
    parser.add_argument("--out", required=True, help="Output PDF file")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    add_sample_number(
        input_pdf=args.to,
        output_pdf=args.out,
        label=args.label,
        sample_nr=args.sample_nr
    )


if __name__ == "__main__":
    main()
