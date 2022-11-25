import fitz  # PyMuPDF
import io
from PIL import Image
import re
from pathlib import Path
from gooey import Gooey, GooeyParser
import os


def extractImagesFromPDF(pdffile, outputfolder, compressionlevel: int):
    pdffile = Path(pdffile)
    if date := re.search(r"\d{1,}\.\d{1,}\.\d{2,}", pdffile.stem):
        d = re.sub(r"(\d+)\.(\d+)\.(\d+)", r"\3-\2-\1", date[0])
        isodate = re.sub(r"\D(\d)$", r"-0\1", re.sub(r"\D(\d)\D", r"-0\1-", d))
    elif isodate := re.search(r"\d{4}-\d{2}-\d{2}", pdffile.stem):
        isodate = isodate[0]
    else:
        isodate = None
    # open the file
    pdf_file = fitz.open(pdffile)
    # iterate over PDF pages
    n = 0
    allpages = len(pdf_file)
    for page_index in range(allpages):
        n += 1
        print(f"Speichere Datei {n} von {allpages}", flush=True)
        # get the page itself
        page = pdf_file[page_index]
        for image_index, img in enumerate(page.get_images(), start=1):
            # get the XREF of the image
            xref = img[0]
            # extract the image bytes
            base_image = pdf_file.extract_image(xref)
            image_bytes = base_image["image"]
            # load it to PIL
            image = Image.open(io.BytesIO(image_bytes))
            # save it to local disk
            if isodate:
                filename = f"{isodate}--{pdffile.stem}_{page_index+1:02}.jpg"
            else:
                filename = f"{pdffile.stem}__{page_index+1:02}.jpg"
            image.save(Path(outputfolder, filename), "JPEG", quality=compressionlevel)


@Gooey(program_name="PDF Image Extraktor", required_cols=1, default_size=(550, 450))
def cli():
    parser = GooeyParser(description="0.3")
    parser.add_argument(
        "Ordner", help="Bitte den Ordner mit PDFs auswählen", widget="DirChooser"
    )
    parser.add_argument("-c", "--compression", type=int)
    args = parser.parse_args()
    inputfolder = Path(args.Ordner)
    compressionlevel = args.compression
    if compressionlevel is None:
        compressionlevel = 90
    for f in inputfolder.glob("*.pdf"):
        print(f"Bearbeite {f}", flush=True)
        outputfolder = Path(os.getcwd(), f.stem)
        outputfolder.mkdir(exist_ok=True)
        extractImagesFromPDF(f, outputfolder, compressionlevel)
    print(f"Alle PDFs konvertiert.", flush=True)


if __name__ == "__main__":
    cli()
