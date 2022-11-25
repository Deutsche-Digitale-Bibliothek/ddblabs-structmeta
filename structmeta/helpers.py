import pytesseract
from natsort import natsorted
from PIL import Image, ImageFile
from pathlib import Path
from zipfile import ZipFile
import time
import fitz  # PyMuPDF
import io
import re
from typing import List, Tuple
import shutil


def extractImagesFromPDF(pdffile: Path, outputfolder: Path, compressionlevel: int):

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
    for page_index in range(len(pdf_file)):
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


def renamePictures(
    listofjpgs: list, recordIdentifier: str, outputfolder: Path, suffix: str
) -> list:
    newjpgs = []
    # Die Sortierung spinnt, weil sie bspw. 10 vor 1 sieht
    listofjpgs = natsorted(listofjpgs)
    n = 0

    for j in listofjpgs:
        n += 1
        padded_n = str(n).zfill(3)
        renamedjpgpath = Path(recordIdentifier + "_" + padded_n + suffix + j.suffix)
        newjpgs.append(Path(outputfolder / "binaries" / renamedjpgpath))

        if j.parts[-2] == "binaries":
            # wenn die bereits Datei im Ausgangsorder liegt (weil bsp. aus TIF konvertiert), wird sie hier umbenannt
            j.rename(Path(outputfolder / "binaries" / renamedjpgpath))
        else:
            # wenn die Datei noch nicht im Ausgangsordner liegt wird sie dahin verschoben
            shutil.copy(str(j), str(Path(outputfolder / "binaries" / renamedjpgpath)))
    return newjpgs


def ocr(
    listofimages: List[Path],
    logger,
    tesseract_language: str,
    outputfolder: Path,
    rename: bool,
    recordIdentifier: str,
) -> None:
    if tesseract_language is not None:
        print(f"Führe OCR mit Sprache '{tesseract_language}' durch", flush=True)
    else:
        print(f"Führe OCR durch", flush=True)
    listofimages = natsorted(listofimages)
    i = 0
    for j in listofimages:
        i += 1
        padded_n = str(i).zfill(3)
        print(f"OCR Datei {i} von {len(listofimages)} ({j})", flush=True)
        if rename == True:
            altoname = Path(
                outputfolder / "binaries" / (recordIdentifier + "_" + padded_n + ".xml")
            )
        else:
            altoname = Path(outputfolder / "binaries" / (j.stem + ".xml"))
        try:
            xml = pytesseract.image_to_alto_xml(Image.open(j), lang=tesseract_language)
        except Exception as e:
            logger.error(e)
        else:
            with open(altoname, "wb") as f:
                f.write(xml)


def zipfiles(inputfolder: Path, outputfolder: Path, logger, logname: str, OCR: bool):
    print("Zippe Daten...", flush=True)
    t = time.strftime("%Y-%m-%d_%H-%M-%S")
    binarieszip = outputfolder / (t + "__" + inputfolder.name + "_binaries.zip")
    metszip = outputfolder / (t + "__" + inputfolder.name + "_mets.zip")

    with ZipFile(binarieszip, "w") as zipObj:
        for f in list(Path(outputfolder / "binaries").rglob("*.jpg")):
            zipObj.write(f, arcname=f.name)
            f.unlink(missing_ok=True)
        logger.info("JPGs gezippt")
    if OCR == True:
        with ZipFile(binarieszip, "a") as zipObj:
            for f in list(Path(outputfolder / "binaries").rglob("*.xml")):
                zipObj.write(f, arcname=f.name)
                f.unlink(missing_ok=True)
            logger.info("ALTO XML gezippt")

    with ZipFile(metszip, "w") as zipObj:
        for f in list(Path(outputfolder).glob("*.xml")):
            zipObj.write(f, arcname=f.name)
            f.unlink(missing_ok=True)
        print("METS Dateien gezippt", flush=True)
        logger.info("METS Dateien gezippt")

    print("ZIP Vorgang abgeschlossen", flush=True)


def createJPGfromTIFF(
    listoftiffs: list,
    logger,
    max_dimensions: int,
    jpg_compression_level: int,
    outputfolder: Path,
):
    print(f"Erstelle JPGs aus {len(listoftiffs)} Dateien", flush=True)
    logger.info(f"Erstelle JPGs aus {len(listoftiffs)} Dateien", flush=True)
    listoftiffs = natsorted(listoftiffs)
    for j in listoftiffs:
        jpgfilename = j.stem + ".jpg"
        try:
            img = Image.open(j)
        except Exception as e:
            logger.error(e)
            pass
        else:
            try:
                # als Default keine Skalierung.
                if max_dimensions:
                    img.thumbnail((max_dimensions, max_dimensions))
                img.save(
                    Path(outputfolder / "binaries" / jpgfilename),
                    "JPEG",
                    quality=jpg_compression_level,
                )
            except Exception as e:
                logger.error(e)
            else:
                logger.debug(
                    f"Converted TIF to JPG and saved to {str(Path(outputfolder / 'binaries' / jpgfilename))}."
                )


def generate_thumbails(
    listofjpgs: list, logger, outputfolder: Path, recordIdentifier: str, rename: bool
):
    print(f"Erstelle Thumbnails für {len(listofjpgs)} Dateien", flush=True)
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    # Thumbnail-Derivat erzeugen
    listofjpgs = natsorted(listofjpgs)
    n = 0
    for j in listofjpgs:
        n += 1
        padded_n = str(n).zfill(3)
        if rename == True:
            thumbfn = Path(
                outputfolder
                / "binaries"
                / (recordIdentifier + "_" + padded_n + "_thumb" + j.suffix)
            )
        else:
            thumbfn = Path(outputfolder / "binaries" / (j.stem + "_thumb" + j.suffix))
        try:
            img = Image.open(j)
        except Exception as e:
            logger.info(e)
            pass
        else:
            try:
                img.thumbnail((250, 250))
            except Exception as e:
                logger.info(e)
            else:
                try:
                    img.save(thumbfn)
                except Exception as e:
                    logger.info(e)
                else:
                    logger.debug(f"Saved {thumbfn}")
