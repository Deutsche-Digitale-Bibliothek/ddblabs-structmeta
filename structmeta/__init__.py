import re
import toml
from natsort import natsorted
import time
import uuid
import pandas as pd
import sys
from lxml import etree
from loguru import logger
from pathlib import Path
from gooey import Gooey, GooeyParser
from .helpers import *
import os
import codecs
from typing import List, Tuple, Union
import pkg_resources

if sys.stdout.encoding != "UTF-8":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
if sys.stderr.encoding != "UTF-8":
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

# get version from setup.py
__version__ = pkg_resources.require("structmeta")[0].version


def getpictures(folder: Path, max_dimensions, jpg_quality: int, outputfolder):
    """Function to process all image needs

    Arguments:
        folder -- Path to folder with images

        max_dimensions -- int or None to scale images by

        jpg_quality -- int to compress jpgs if generating jpgs

        outputfolder -- folder to output generated jpgs to

    Returns:
        jpgs -- list of jpgs to process further

        existingthumbs -- list of exitsing thumbnails (can be empty)

        initialpictureformat -- suffix of supplied images (jpg oder jpeg or tiff/tif)

        alltiffs -- list of file paths to supplied TIF files

    """

    alljpgs = []
    existingthumbs = []

    for ext in ["jpg", "jpeg"]:
        for i in folder.glob("*." + ext):
            if "thumb" not in i.name:
                alljpgs.append(i)
            elif "thumb" in i.name:
                existingthumbs.append(i)

    if len(alljpgs) == 0:
        # wenn wir keine JPGs haben: lese TIFs
        alltiffs = []
        for ext in ["tif", "tiff"]:
            alltiffs.extend(folder.glob("*." + ext))
        if len(alltiffs) == 0:
            # wenn wir auch keine TIFs finden, Exit
            sys.exit("Keine TIFs und keine JPGs gefunden")
        else:
            # Wenn wir TIFs finden, aus denen JPGs machen. Die JPGs werden dann direkt schon in den output folder geschrieben
            initialpictureformat = alltiffs[0].suffix.replace(".", "")
            helpers.createJPGfromTIFF(
                alltiffs, logger, max_dimensions, jpg_quality, outputfolder
            )
            # wenn TIF, dann verweist JPGs direkt auf die erzeugten JPGs im outputordner
            jpgs = [
                Path(outputfolder / "binaries" / (f.stem + ".jpg")) for f in alltiffs
            ]
    else:
        # wir hatten JPGs
        if max_dimensions:
            # Bilder verkleinern?
            helpers.reduceJPGs(
                alljpgs, logger, max_dimensions, jpg_quality, outputfolder
            )
        initialpictureformat = alljpgs[0].suffix.replace(".", "")
        jpgs = alljpgs
        alltiffs = []
    return jpgs, existingthumbs, initialpictureformat, alltiffs


def read_metadata(filepath):

    with open(filepath, "r") as f:
        metadata = toml.loads(f.read())

    return metadata


def flgrp(listofjpgs: Path):
    listofjpgs = [j.stem + j.suffix for j in listofjpgs]
    n = 0
    x = ""
    for i in listofjpgs:
        n += 1
        padded_n = int(str(n).zfill(3))
        x += f"""<mets:file MIMETYPE="image/jpg" ID="default_{padded_n}">
            <mets:FLocat LOCTYPE="URL" xlink:href="{i}"/>
        </mets:file>"""
    return x


def flgrp_thumbs(listofthumbs: Path):
    listofthumbs = [j.stem + j.suffix for j in listofthumbs]
    n = 0
    x = ""
    for i in listofthumbs:
        n += 1
        padded_n = int(str(n).zfill(3))
        x += f"""<mets:file MIMETYPE="image/jpg" ID="thumb_{padded_n}">
            <mets:FLocat LOCTYPE="URL" xlink:href="{i}"/>
        </mets:file>"""
    return x


def structMapPhysical(listofjpgs, OCR, create_filegrp_fulltext):
    n = 0
    x = ""

    for i in listofjpgs:
        n += 1
        if OCR == True or create_filegrp_fulltext == True:
            x += f"""<mets:div xmlns:xs="http://www.w3.org/2001/XMLSchema" TYPE="page" ID="phys_{n}" CONTENTIDS="NULL" ORDER="{n}" ORDERLABEL="{n}">
                    <mets:fptr FILEID="default_{n}"/>
                    <mets:fptr FILEID="thumb_{n}"/>
                     <mets:fptr FILEID="ocr_{n}"/>
                </mets:div>"""
        else:
            x += f"""<mets:div xmlns:xs="http://www.w3.org/2001/XMLSchema" TYPE="page" ID="phys_{n}" CONTENTIDS="NULL" ORDER="{n}" ORDERLABEL="{n}">
                    <mets:fptr FILEID="default_{n}"/>
                    <mets:fptr FILEID="thumb_{n}"/>
                </mets:div>"""
    return x


def structLink(divid, listofjpgs, startpage):
    """
    Wird aufgerufen, wenn es Struktudaten gibt. Für jedes Strukturelement übergeben
    bekommt die Funktion die ID der DMDSec und eine liste mit Bildern zu diesem Element
    """
    n = startpage
    x = ""
    for i in listofjpgs:
        n += 1
        x += f'<mets:smLink xlink:from="{divid}" xlink:to="phys_{n}"/>\n'
    return x


def createDMDsec(elemname, idno):
    xml = f"""
    <mets:dmdSec ID="DMDLOG_{idno}">
            <mets:mdWrap MDTYPE="MODS">
                <mets:xmlData>
                    <mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
                        <mods:titleInfo>
                            <mods:title>{elemname}</mods:title>
                        </mods:titleInfo>
                    </mods:mods>
                </mets:xmlData>
            </mets:mdWrap>
    </mets:dmdSec>
    """
    return xml


def flgrp_fulltext(listofjpgs, OCR, create_filegrp_fulltext):
    listofjpgs = [j.stem + j.suffix for j in listofjpgs]
    if OCR == True or create_filegrp_fulltext == True:
        n = 0
        start = '<mets:fileGrp USE="FULLTEXT">'
        end = "</mets:fileGrp>"
        x = ""

        listofjpgs = natsorted(listofjpgs)
        for i in listofjpgs:
            n += 1
            padded_n = int(str(n).zfill(3))
            filename = i.split(".")[0] + ".xml"
            x += f"""<mets:file MIMETYPE="text/xml" ID="ocr_{padded_n}">
                <mets:FLocat LOCTYPE="URL" xlink:href="{filename}"/>
            </mets:file>"""
        return start + x + end
    else:
        return ""


def newspaperMETS(
    folder,
    metadata,
    do_thumbs,
    OCR,
    outputfolder,
    create_filegrp_fulltext,
    tesseract_language,
    renameimages,
    max_dimensions,
    jpg_quality,
):

    zdb_id = folder.name
    issuefolders = [f for f in folder.glob("*") if f.is_dir()]
    i = 0

    for issue in issuefolders:
        i += 1
        print(f"Fortschritt: {i} von {len(issuefolders)}", flush=True)
        isodate = re.findall(r"(\d{4}-\d{2}-\d{2})", issue.name)
        if len(isodate) != 0:
            dateissued = isodate[0]
        else:
            print(f"Bei {issue} konnte kein ISO Tagesdatum erkannt werden.", flush=True)
            logger.error(f"Bei {issue} konnte kein ISO Tagesdatum erkannt werden.")
            break
        modsnumber = re.sub(r"(\d{4})-(\d{2})-(\d{2})", r"\3.\2.\1", dateissued)
        identifier = zdb_id + "__" + issue.name
        datecreated = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        recordChangeDate = datecreated
        if "imagebaseurl" in metadata["objects"]:
            imagebaseurl = metadata["objects"]["imagebaseurl"]
        else:
            imagebaseurl = None

        jpgs, thumbs = processImages(
            issue,
            max_dimensions,
            jpg_quality,
            tesseract_language,
            identifier,
            do_thumbs,
            outputfolder,
            renameimages,
            OCR,
            imagebaseurl,
        )

        metsvorlage = f"""
            <mets:mets
            OBJID="{identifier}" TYPE="newspaper"
            xmlns:mets="http://www.loc.gov/METS/"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            xmlns:mods="http://www.loc.gov/mods/v3"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-8.xsd http://www.loc.gov/METS/ http://www.loc.gov/standards/mets/mets.xsd">
                <mets:metsHdr CREATEDATE="{time.strftime("%Y-%m-%dT%H:%M:%SZ")}" LASTMODDATE="{datecreated}">
                    <mets:agent
                        xmlns:dv="http://dfg-viewer.de/" ROLE="CREATOR" TYPE="ORGANIZATION">
                        <mets:name>{metadata['institution']['name']}</mets:name>
                    </mets:agent>
                    <mets:agent ROLE="OTHER" TYPE="OTHER" OTHERTYPE="SOFTWARE">
                        <mets:name>Structmeta {__version__}</mets:name>
                    </mets:agent>
                </mets:metsHdr>
                <mets:dmdSec ID="dmd">
                    <mets:mdWrap MDTYPE="MODS">
                        <mets:xmlData>
                            <mods:mods>
                                <mods:part order="{re.sub("-", "", dateissued)}">
                                    <mods:detail type="issue">
                                        <mods:number>{modsnumber}</mods:number>
                                    </mods:detail>
                                </mods:part>
                                <mods:originInfo eventType="publication">
                                    <mods:dateIssued encoding="iso8601">{dateissued}</mods:dateIssued>
                                </mods:originInfo>
                                <mods:originInfo eventType="digitization">
                                    <mods:dateCaptured encoding="iso8601">{metadata['objects']['year_of_digitization']}</mods:dateCaptured>
                                    <mods:publisher>{metadata['institution']['name']}</mods:publisher>
                                </mods:originInfo>
                                <mods:language>
                                    <mods:languageTerm type="code" valueURI="http://id.loc.gov/vocabulary/iso639-2/ger">{metadata['objects']['sprache']}</mods:languageTerm>
                                </mods:language>
                                <mods:physicalDescription>
                                    <mods:extent>{len(jpgs)} Seiten</mods:extent>
                                </mods:physicalDescription>
                                <mods:relatedItem type="host">
                                    <mods:identifier type="zdb">{zdb_id}</mods:identifier>
                                    <mods:titleInfo>
                                        <mods:title>{metadata['objects']['title']}</mods:title>
                                    </mods:titleInfo>
                                </mods:relatedItem>
                                <mods:recordInfo>
                                    <mods:recordIdentifier source="{metadata['institution']['isil']}">{identifier}</mods:recordIdentifier>
                                    <mods:recordChangeDate encoding="iso8601">{recordChangeDate}</mods:recordChangeDate>
                                </mods:recordInfo>
                                <mods:genre displayLabel="document type">issue</mods:genre>
                                <mods:typeOfResource>text</mods:typeOfResource>
                            </mods:mods>
                        </mets:xmlData>
                    </mets:mdWrap>
                </mets:dmdSec>
                <mets:amdSec xmlns:dv="http://dfg-viewer.de/" ID="amd">
                    <mets:rightsMD ID="RIGHTS">
                        <mets:mdWrap MIMETYPE="text/xml" MDTYPE="OTHER" OTHERMDTYPE="DVRIGHTS">
                            <mets:xmlData>
                                <dv:rights>
                                <dv:owner>{metadata['institution']['name']}</dv:owner>
                                        <dv:ownerLogo>{metadata['institution']['logoURL']}</dv:ownerLogo>
                                        <dv:ownerSiteURL>{metadata['institution']['siteURL']}</dv:ownerSiteURL>
                                        <dv:ownerContact>{metadata['institution']['contact']}</dv:ownerContact>
                                        <dv:license>{metadata['institution']['license']}</dv:license>
                                        {'<dv:sponsor>' + metadata['institution']['sponsor'] + '</dv:sponsor>' if 'sponsor' in metadata['institution'] else ''}
                                </dv:rights>
                            </mets:xmlData>
                        </mets:mdWrap>
                    </mets:rightsMD>
                </mets:amdSec>
                <mets:fileSec>
                    <mets:fileGrp USE="DEFAULT">
                        {flgrp(jpgs)}
                    </mets:fileGrp>
                    <mets:fileGrp USE="THUMBS">
                        {flgrp_thumbs(thumbs)}
                    </mets:fileGrp>
                    {flgrp_fulltext(jpgs, OCR, create_filegrp_fulltext)}
                </mets:fileSec>
                <mets:structMap TYPE="PHYSICAL">
                    <mets:div ID="phys" CONTENTIDS="NULL" TYPE="physSequence">
                        {structMapPhysical(jpgs, OCR, create_filegrp_fulltext)}
                    </mets:div>
                </mets:structMap>
                <mets:structMap TYPE="LOGICAL">
                    <mets:div TYPE="issue" ID="LOG" DMDID="dmd" ADMID="amd" ORDER="1" ORDERLABEL="{dateissued}" LABEL="{metadata['objects']['title'] + ' ' + modsnumber }"></mets:div>
                </mets:structMap>
                <mets:structLink>
                        {structLink('LOG', jpgs, 0)}
                </mets:structLink>
            </mets:mets>
        """

        metsvorlage = re.sub("&", "&amp;", metsvorlage)
        try:
            # Output auf Validität prüfen und speichern
            doc = etree.fromstring(metsvorlage)
        except etree.XMLSyntaxError as e:
            logger.warning(f"Fehler beim parsen des erstellen XML: {e}")
            return
        else:
            with open(outputfolder / (identifier + "_mets.xml"), "w") as f:
                f.write(etree.tostring(doc, encoding="unicode", pretty_print=True))
            logger.info(f"Wrote METS/MODS: {issue.name}_mets.xml")


def monographMETS(
    folder,
    metadata,
    do_thumbs,
    OCR,
    outputfolder,
    create_filegrp_fulltext,
    tesseract_language,
    renameimages,
    max_dimensions,
    jpg_quality,
):
    i = 0
    bookfolders = [f for f in folder.glob("*") if f.is_dir()]
    for book in bookfolders:
        # jedes Buch ist ein Pfad zu einem Ordner
        booktitle = book.name.split("_")[0]
        datecreated = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        i += 1
        print(f"Fortschritt: {i} von {len(bookfolders)} Büchern", flush=True)
        strukturdaten = [f for f in book.glob("*") if f.is_dir()]
        additionalslogs = []
        additionalslogsDMDIDs = []
        slink = ""
        if "imagebaseurl" in metadata["objects"]:
            imagebaseurl = metadata["objects"]["imagebaseurl"]
        else:
            imagebaseurl = None
        if strukturdaten:
            alljpgs = []
            allthumbs = []
            print("Strukturdaten erkannt", flush=True)
            idno = 1
            maxnumber = 0

            for elem in natsorted(strukturdaten):
                elemname = elem.name.split("_")[-1]
                structjpgs, structthumbs = processImages(
                    elem,
                    max_dimensions,
                    jpg_quality,
                    tesseract_language,
                    booktitle.replace(" ", "_")
                    + "_"
                    + elemname.replace(" ", "_")
                    + "_",
                    do_thumbs,
                    outputfolder,
                    renameimages,
                    OCR,
                    imagebaseurl,
                )
                alljpgs.extend(structjpgs)
                allthumbs.extend(structthumbs)
                # wir müssen wissen bei welcher Physischen Seite wird an sich sind
                # ein elem ist ein Unterornder unter dem book
                # structjpgs = [f for f in list(Path(elem).glob("**/*.jpg"))]
                slink += structLink(f"LOG_{idno + 1}", structjpgs, maxnumber)
                maxnumber += len(structjpgs)

                idno += 1
                # für jede Strukturebene eine weitere dmdSec erstellen und die an eine Liste mit weiteren dmdSecs anhängen
                additionalslogs.append(createDMDsec(elemname, idno))
                d = {"name": "", "idno": ""}
                d["name"] = elemname
                d["idno"] = idno
                additionalslogsDMDIDs.append(d)

            slink += structLink(f"LOG_1", alljpgs, 0)
        else:
            alljpgs, allthumbs = processImages(
                book,
                max_dimensions,
                jpg_quality,
                tesseract_language,
                booktitle.replace(" ", "_"),
                do_thumbs,
                outputfolder,
                renameimages,
                OCR,
                imagebaseurl,
            )
            slink += structLink(f"LOG_1", alljpgs, 0)

        if len(additionalslogsDMDIDs) != 0:
            structmapLogical = f'<mets:div ADMID="AMD" DMDID="DMDLOG_1" ID="LOG_1" LABEL="{booktitle}" TYPE="monograph">'
            orderid = 0
            for id in additionalslogsDMDIDs:
                orderid += 1
                idno = id["idno"]
                titel = id["name"]
                structmapLogical += f'<mets:div ID="LOG_{idno}" DMDID="DMDLOG_{idno}" LABEL="{titel}" TYPE="chapter" ORDER="{orderid}"/>\n'
            structmapLogical += "</mets:div>"
        else:
            # wenn es keine Strukturelemente unterhalb des Buches gibt
            structmapLogical = f'<mets:div ID="LOG_1" DMDID="DMDLOG_1" LABEL="{booktitle}" TYPE="monograph" ORDER="1"/>\n'

        metsvorlage = f"""
    <mets:mets xmlns:mets="http://www.loc.gov/METS/" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-8.xsd http://www.loc.gov/METS/ http://www.loc.gov/standards/mets/mets.xsd">
        <mets:metsHdr CREATEDATE="{time.strftime("%Y-%m-%dT%H:%M:%SZ")}" LASTMODDATE="{datecreated}">
                    <mets:agent ROLE="CREATOR" TYPE="ORGANIZATION">
                        <mets:name>{metadata['institution']['name']}</mets:name>
                    </mets:agent>
                    <mets:agent ROLE="OTHER" TYPE="OTHER" OTHERTYPE="SOFTWARE">
                        <mets:name>Structmeta {__version__}</mets:name>
                    </mets:agent>

        </mets:metsHdr>
        <mets:dmdSec ID="DMDLOG_1">
            <mets:mdWrap MDTYPE="MODS">
                <mets:xmlData>
                    <mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
                        <mods:location>
                            <mods:physicalLocation valueURI="http://ld.zdb-services.de/resource/organisations/{metadata['institution']['isil']}">{metadata['institution']['name']}</mods:physicalLocation>
                        </mods:location>
                        <mods:originInfo eventType="publication">
                           {'<mods:edition>' + metadata['objects']['auflage'] + '</mods:edition>' if 'auflage' in metadata['objects'] else ''}
                            {'<mods:publisher>' + metadata['objects']['verlag'] + '</mods:publisher>' if 'auflage' in metadata['objects'] else ''}
                            <mods:place><mods:placeTerm type="text">{metadata['objects']['erscheinungsort']}</mods:placeTerm></mods:place>
                            {'<mods:dateIssued>' + metadata['objects']['erscheinungsjahr'] + '</mods:dateIssued>' if 'auflage' in metadata['objects'] else ''}
                        </mods:originInfo>
                        <mods:originInfo eventType="digitization">
                            <mods:place>
                                <mods:placeTerm type="text">{metadata['objects']['place_of_digitization']}</mods:placeTerm>
                            </mods:place>
                            <mods:dateCaptured encoding="iso8601">{metadata['objects']['year_of_digitization']}</mods:dateCaptured>
                            <mods:publisher>{metadata['institution']['name']}</mods:publisher>
                            <mods:edition>[Electronic ed.]</mods:edition>
                        </mods:originInfo>
                        {'<mods:name type="personal"><mods:displayForm>' + metadata['objects']['autor'] + '</mods:displayForm><mods:role><mods:roleTerm authority="marcrelator" type="code">aut</mods:roleTerm></mods:role> </mods:name>'}
                        <mods:recordInfo>
                            <mods:recordIdentifier source="{metadata['institution']['isil']}">{metadata['institution']['isil'] + '_' + booktitle}</mods:recordIdentifier>
                            <mods:recordCreationDate encoding="iso8601">{datecreated}</mods:recordCreationDate>
                            <mods:recordInfoNote type="license">{metadata['institution']['license']}</mods:recordInfoNote>
                        </mods:recordInfo>
                        <mods:titleInfo>
                            <mods:title>{booktitle}</mods:title>
                        </mods:titleInfo>
                        <mods:language><mods:languageTerm authority="iso639-2b" type="code">{metadata['objects']['sprache']}</mods:languageTerm></mods:language>
                        <mods:physicalDescription>
                            <mods:extent>{len(alljpgs)}</mods:extent>
                        </mods:physicalDescription>
                        <mods:typeOfResource>text</mods:typeOfResource>
                    </mods:mods>
                </mets:xmlData>
            </mets:mdWrap>
        </mets:dmdSec>
        {("").join(additionalslogs)}
        <mets:amdSec ID="AMD">
            <mets:rightsMD ID="RIGHTS">
                <mets:mdWrap MDTYPE="OTHER" MIMETYPE="text/xml" OTHERMDTYPE="DVRIGHTS">
                    <mets:xmlData>
                        <dv:rights xmlns:dv="http://dfg-viewer.de/">
                            <dv:owner>{metadata['institution']['name']}</dv:owner>
                            <dv:ownerLogo>{metadata['institution']['logoURL']}</dv:ownerLogo>
                            <dv:ownerSiteURL>{metadata['institution']['siteURL']}</dv:ownerSiteURL>
                            <dv:ownerContact>{metadata['institution']['contact']}</dv:ownerContact>
                            <dv:license>{metadata['institution']['license']}</dv:license>
                            {'<dv:sponsor>' + metadata['institution']['sponsor'] + '</dv:sponsor>' if 'sponsor' in metadata['institution'] else ''}
                        </dv:rights>
                    </mets:xmlData>
                </mets:mdWrap>
            </mets:rightsMD>
        </mets:amdSec>
        <mets:fileSec>
            <mets:fileGrp USE="DEFAULT">
                {flgrp(alljpgs)}
            </mets:fileGrp>
            <mets:fileGrp USE="THUMBS">
                {flgrp_thumbs(allthumbs)}
            </mets:fileGrp>
        </mets:fileSec>
        <mets:structMap TYPE="LOGICAL">
                {structmapLogical}
        </mets:structMap>
        <mets:structMap TYPE="PHYSICAL">
            <mets:div ID="phys" CONTENTIDS="NULL" TYPE="physSequence">
                {structMapPhysical(alljpgs, OCR, create_filegrp_fulltext)}
            </mets:div>
        </mets:structMap>
        <mets:structLink>
                {slink}
        </mets:structLink>
    </mets:mets>
    """

        metsvorlage = re.sub("&", "&amp;", metsvorlage)
        try:
            # Output auf Validität prüfen und speichern
            doc = etree.fromstring(metsvorlage)
        except etree.XMLSyntaxError as e:
            logger.warning(f"Fehler beim parsen des erstellen XML: {e}")
            return
        else:
            with open(outputfolder / (book.name + "_mets.xml"), "w") as f:
                f.write(etree.tostring(doc, encoding="unicode", pretty_print=True))
            logger.info(f"Wrote METS/MODS: {book.name}_mets.xml")


def processImages(
    folder: Path,
    max_dimensions: Union[int, bool],
    jpg_quality: int,
    tesseract_language: Union[str, bool],
    identifier: str,
    do_thumbs: bool,
    outputfolder: Path,
    renameimages: bool,
    OCR: bool,
    imagebaseurl: Union[str, bool],
):
    """
    Diese Funktion regelt alle Angelegenheiten, die die Bilder betreffen:
    Return:
        - eine Liste mit Pfaden zu den Bilddateien als JPG im Ausgabe Ordner
        - eine Liste mit Pfaden zu den Thumbnails als JPG im Ausgabe Ordner
    """
    # In der Subfunktion getpictures werden ggf. die Bilder auch komprimiert/kleingerechnet
    jpgs, existingthumbs, initialpictureformat, alltiffs = getpictures(
        folder, max_dimensions, jpg_quality, outputfolder
    )
    # initialjpgs sollte immer auf die Originalpfade verweisen
    # jpgs verweist immer auf die entweder erzeugten oder kopierten
    initialjpgs = jpgs

    # --------------------------------------
    # Umbenennen
    # --------------------------------------
    if renameimages == True:
        # wenn umbenannt werde soll:
        jpgs = helpers.renamePictures(jpgs, identifier, outputfolder, "")
    else:
        # wenn nicht umbennant werden soll, schauen ob wir ursprünglich JPGs hatten
        if initialpictureformat in ["jpg", "jpeg"]:
            # wenn ja, werden die in den outputerfolder kopiert. Wenn nicht sind die JPGs aus den TIF Dateien ja eh dahin erstellt worden
            if max_dimensions:
                # wenn max_dimensions vergeben ist, sind die Bilder ja schon verkleinert im Output-Ordner.
                pass
            else:
                for j in initialjpgs:
                    shutil.copy(str(j), str(Path(outputfolder / "binaries" / j.name)))
        # --------------------------------------
    # Thumbnails
    # --------------------------------------
    # zwei Möglichkeiten: Es gibt bereits Thumbnails: Dann kopieren - es gibt keine? Dann ggf. erstellen
    if len(existingthumbs) != 0:
        # Es gibt bereits Thumbnails
        if do_thumbs == True:
            print("Es sind schon Thumbnails vorhanden", flush=True)
            pass
        if renameimages == True:
            # vorhandene Thumbs umbenennen und in den output Ordner kopieren
            thumbs = helpers.renamePictures(
                existingthumbs, identifier, outputfolder, "_thumb"
            )
        else:
            # es gibt schon welche und die sollen nicht umbennant weden. Dann werden sie in den Output ordner kopiert.
            for j in existingthumbs:
                shutil.copy(str(j), str(Path(outputfolder / "binaries" / j.name)))
            thumbs = [Path(outputfolder / "binaries" / t) for t in existingthumbs]
    else:
        # Es gibt noch keine Thumbails
        if do_thumbs == True:
            if renameimages == True:
                if initialpictureformat in ["jpg", "jpeg"]:

                    helpers.generate_thumbails(
                        initialjpgs, logger, outputfolder, identifier, rename=True
                    )
                    thumbs = [Path(j.stem + "_thumb.jpg") for j in jpgs]
                else:
                    helpers.generate_thumbails(
                        jpgs, logger, outputfolder, identifier, rename=True
                    )
                    thumbs = [Path(j.stem + "_thumb.jpg") for j in jpgs]
            else:
                # Thumbnails erstellen
                helpers.generate_thumbails(
                    jpgs, logger, outputfolder, identifier, rename=False
                )
                thumbs = [Path(j.stem + "_thumb.jpg") for j in jpgs]
        else:
            # es gibt keine Thumbnails und es sollen auch keine generiert werden.
            thumbs = [Path(j.stem + "_thumb.jpg") for j in jpgs]
    # --------------------------------------
    # OCR
    # --------------------------------------

    if OCR == True:
        if len(alltiffs) != 0:
            # Wenn es TIFFs waren, dann OCR auf die TIFFs - dann dürfen die JPGs aber nicht kleingerechnet werden...
            helpers.ocr(
                alltiffs,
                logger,
                tesseract_language,
                outputfolder,
                renameimages,
                identifier,
            )
        else:
            helpers.ocr(
                jpgs,
                logger,
                tesseract_language,
                outputfolder,
                renameimages,
                identifier,
            )
    # --------------------------------------
    # URL Prefix
    # --------------------------------------
    if imagebaseurl is not None:
        # wenn es eine URL geben soll die vor die Bilder kommt, werden die URLs angepasst
        thumbs = [
            imagebaseurl + str(j.parent.name) + "/" + +str(j.stem) + ".jpg"
            for j in thumbs
        ]
        jpgs = [
            imagebaseurl + str(j.parent.name) + "/" + str(j.stem) + str(j.suffix)
            for j in jpgs
        ]
    return jpgs, thumbs


def journalMETS(
    folder,
    metadata,
    do_thumbs,
    OCR,
    outputfolder,
    create_filegrp_fulltext,
    tesseract_language,
    renameimages,
    max_dimensions,
    jpg_quality,
):
    """
    Ausgabe: Pro Jahrgang eine METS Datei, in der die einzelnen Ausgaben eigene dmdSecs haben.
    """
    i = 0
    volumefolders = [f for f in folder.glob("*") if f.is_dir()]
    for volume in volumefolders:
        # volume ist ein Path
        i += 1
        print(f"Fortschritt: {i} von {len(volumefolders)} Jahrgängen", flush=True)
        year = volume.name.split("_")[1]
        dateissued = year + "-01-01"
        title = volume.name.split("_")[0]
        datecreated = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        strukturdaten = [f for f in volume.glob("*") if f.is_dir()]
        additionalslogs = []
        additionalslogsDMDIDs = []
        slink = ""
        if "imagebaseurl" in metadata["objects"]:
            imagebaseurl = metadata["objects"]["imagebaseurl"]
        else:
            imagebaseurl = None

        # -------------------------------------------------------
        if strukturdaten:
            alljpgs = []
            allthumbs = []
            print("Strukturdaten erkannt", flush=True)
            idno = 1
            maxnumber = 0

            for elem in natsorted(strukturdaten):
                elemname = elem.name.split("_")[-1]
                structjpgs, structthumbs = processImages(
                    elem,
                    max_dimensions,
                    jpg_quality,
                    tesseract_language,
                    title.replace(" ", "_")
                    + "_"
                    + year
                    + "_"
                    + elemname.replace(" ", "_")
                    + "_",
                    do_thumbs,
                    outputfolder,
                    renameimages,
                    OCR,
                    imagebaseurl,
                )
                alljpgs.extend(structjpgs)
                allthumbs.extend(structthumbs)
                # wir müssen wissen bei welcher Physischen Seite wird an sich sind
                # ein elem ist ein Unterornder unter dem Volume
                # structjpgs = [f for f in list(Path(elem).glob("**/*.jpg"))]
                slink += structLink(f"LOG_{idno + 1}", structjpgs, maxnumber)
                maxnumber += len(structjpgs)

                idno += 1
                # für jede Strukturebene eine weitere dmdSec erstellen und die an eine Liste mit weiteren dmdSecs anhängen
                additionalslogs.append(createDMDsec(elemname, idno))
                d = {"name": "", "idno": ""}
                d["name"] = elemname
                d["idno"] = idno
                additionalslogsDMDIDs.append(d)

            slink += structLink(f"LOG_1", alljpgs, 0)
        else:
            alljpgs, thumbs = processImages(
                volume,
                max_dimensions,
                jpg_quality,
                tesseract_language,
                title.replace(" ", "_") + "_" + year,
                do_thumbs,
                outputfolder,
                renameimages,
                OCR,
                imagebaseurl,
            )

        structmaplogical = ""
        orderid = 0
        for id in additionalslogsDMDIDs:
            orderid += 1
            idno = id["idno"]
            titel = id["name"]
            structmaplogical += f'<mets:div ID="LOG_{idno}" DMDID="DMDLOG_{idno}" LABEL="{titel}" TYPE="chapter" ORDER="{orderid}"/>\n'

        recordIdentifier = (
            metadata["institution"]["isil"] + "_" + title + "_" + dateissued
        )

        metsvorlage = f"""
    <mets:mets xmlns:mets="http://www.loc.gov/METS/" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-8.xsd http://www.loc.gov/METS/ http://www.loc.gov/standards/mets/mets.xsd">
        <mets:metsHdr CREATEDATE="{time.strftime("%Y-%m-%dT%H:%M:%SZ")}" LASTMODDATE="{datecreated}">
                    <mets:agent
                        xmlns:dv="http://dfg-viewer.de/" ROLE="CREATOR" TYPE="ORGANIZATION">
                        <mets:name>{metadata['institution']['name']}</mets:name>
                    </mets:agent>
                    <mets:agent ROLE="OTHER" TYPE="OTHER" OTHERTYPE="SOFTWARE">
                        <mets:name>Structmeta {__version__}</mets:name>
                    </mets:agent>
        </mets:metsHdr>
        <mets:dmdSec ID="DMDLOG_1">
            <mets:mdWrap MDTYPE="MODS">
                <mets:xmlData>
                    <mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
                        <mods:location>
                            <mods:physicalLocation valueURI="http://ld.zdb-services.de/resource/organisations/{metadata['institution']['isil']}">{metadata['institution']['name']}</mods:physicalLocation>
                        </mods:location>
                        <mods:originInfo eventType="publication">
                            {'<mods:edition>' + metadata['objects']['auflage'] + '</mods:edition>' if 'auflage' in metadata['objects'] else ''}
                            {'<mods:publisher>' + metadata['objects']['verlag'] + '</mods:publisher>' if 'auflage' in metadata['objects'] else ''}
                            <mods:place><mods:placeTerm type="text">{metadata['objects']['erscheinungsort']}</mods:placeTerm></mods:place>
                            <mods:dateIssued encoding="iso8601" keyDate="yes">{dateissued}</mods:dateIssued>
                        </mods:originInfo>
                        <mods:originInfo eventType="digitization">
                            <mods:place>
                                <mods:placeTerm type="text">{metadata['objects']['place_of_digitization']}</mods:placeTerm>
                            </mods:place>
                            <mods:dateCaptured encoding="iso8601">{metadata['objects']['year_of_digitization']}</mods:dateCaptured>
                            <mods:publisher>{metadata['institution']['name']}</mods:publisher>
                            <mods:edition>[Electronic ed.]</mods:edition>
                        </mods:originInfo>
                        <mods:recordInfo>
                            <mods:recordIdentifier source="{metadata['institution']['isil']}">{metadata['institution']['isil'] + '_' + title + '_' + dateissued}</mods:recordIdentifier>
                            <mods:recordCreationDate encoding="iso8601">{datecreated}</mods:recordCreationDate>
                            <mods:recordInfoNote type="license">{metadata['institution']['license']}</mods:recordInfoNote>
                        </mods:recordInfo>
                        <mods:titleInfo>
                            <mods:title>{title}</mods:title>
                        </mods:titleInfo>
                        <mods:language><mods:languageTerm authority="iso639-2b" type="code">{metadata['objects']['sprache']}</mods:languageTerm></mods:language>
                        <mods:physicalDescription>
                            <mods:extent>{len(alljpgs)}</mods:extent>
                        </mods:physicalDescription>
                        <mods:typeOfResource>text</mods:typeOfResource>
                    </mods:mods>
                </mets:xmlData>
            </mets:mdWrap>
        </mets:dmdSec>
        {("").join(additionalslogs)}
        <mets:amdSec ID="AMD">
            <mets:rightsMD ID="RIGHTS">
                <mets:mdWrap MDTYPE="OTHER" MIMETYPE="text/xml" OTHERMDTYPE="DVRIGHTS">
                    <mets:xmlData>
                        <dv:rights xmlns:dv="http://dfg-viewer.de/">
                            <dv:owner>{metadata['institution']['name']}</dv:owner>
                            <dv:ownerLogo>{metadata['institution']['logoURL']}</dv:ownerLogo>
                            <dv:ownerSiteURL>{metadata['institution']['siteURL']}</dv:ownerSiteURL>
                            <dv:ownerContact>{metadata['institution']['contact']}</dv:ownerContact>
                            <dv:license>{metadata['institution']['license']}</dv:license>
                            {'<dv:sponsor>' + metadata['institution']['sponsor'] + '</dv:sponsor>' if 'sponsor' in metadata['institution'] else ''}
                        </dv:rights>
                    </mets:xmlData>
                </mets:mdWrap>
            </mets:rightsMD>
        </mets:amdSec>
        <mets:fileSec>
            <mets:fileGrp USE="DEFAULT">
                {flgrp(alljpgs)}
            </mets:fileGrp>
            <mets:fileGrp USE="THUMBS">
                {flgrp_thumbs(allthumbs)}
            </mets:fileGrp>
            {flgrp_fulltext(alljpgs, OCR, create_filegrp_fulltext)}
        </mets:fileSec>
        <mets:structMap TYPE="LOGICAL">
            <mets:div ID="LOG_1" DMDID="DMDLOG_1" LABEL="{title}" ADMID="AMD" TYPE="monograph">
                {structmaplogical}
            </mets:div>
        </mets:structMap>
        <mets:structMap TYPE="PHYSICAL">
            <mets:div ID="phys" CONTENTIDS="NULL" TYPE="physSequence">
                {structMapPhysical(alljpgs, OCR, create_filegrp_fulltext)}
            </mets:div>
        </mets:structMap>
        <mets:structLink>
                {slink}
        </mets:structLink>
    </mets:mets>
    """

        """
        Output auf Validität prüfen und speichern
        """
        metsvorlage = re.sub("&", "&amp;", metsvorlage)
        try:
            doc = etree.fromstring(metsvorlage)
        except etree.XMLSyntaxError as e:
            logger.warning(f"Fehler beim parsen des erstellen XML: {e}")
            return
        else:
            with open(outputfolder / (volume.name + "_mets.xml"), "w") as f:
                f.write(etree.tostring(doc, encoding="unicode", pretty_print=True))
            logger.info(f"Wrote METS/MODS: {volume.name}_mets.xml")


@Gooey(
    program_name="Structmeta",
    required_cols=1,
    requires_shell=False,
    default_size=(600, 715),
    menu=[
        {
            "name": "Help",
            "items": [
                {
                    "type": "AboutDialog",
                    "menuTitle": "About",
                    "name": "Structmeta",
                    "description": "METS/MODS aus Ordnerstrukturen erzeugen",
                    "version": __version__,
                    "copyright": "2022",
                    "developer": "Karl Krägelin (mail@karlkraeglin.de)",
                    "license": "MIT",
                }
            ],
        }
    ],
)
def main():
    parser = GooeyParser(description=__version__)
    parser.add_argument(
        "--metadata",
        dest="Metadaten",
        help="Bitte hier die TOML Datei auswählen",
        widget="FileChooser",
    )
    parser.add_argument(
        "--folder",
        dest="Ordner",
        help="Hier den Ordner mit Bilddateien auswählen",
        widget="DirChooser",
    )

    opt = parser.add_argument_group(
        "Erweiterte Funktionen", "Aktivieren Sie diese Funktionen bei Bedarf"
    )

    opt.add_argument(
        "--output",
        metavar="Ausgabe-Ordner",
        help="Angabe eines Ausgabe-Ordners",
        widget="DirChooser",
    )
    opt.add_argument(
        "--thumbnails",
        dest="Thumbnails",
        action="store_true",
        help="Erstelle Thumnails von den Bilddateien",
    )
    opt.add_argument(
        "--zip",
        metavar="Zip files",
        action="store_true",
        help="Zippe die erstellten Dateien (JPGs und METS Dateien und ggf. erzeugte ALTO XML Dateien)",
    )
    opt.add_argument(
        "--rename",
        metavar="Rename Images",
        action="store_true",
        help="Bennene die Bilddateien eindeutig um",
    )

    mutual_parser = opt.add_mutually_exclusive_group(
        gooey_options={"title": "Volltext Funktionalitäten"}
    )
    mutual_parser.add_argument(
        "--noocr",
        dest="Kein Volltext",
        action="store_true",
        help="Keine Volltext Funktionalitäten",
    )
    mutual_parser.add_argument(
        "--ocr", dest="OCR", action="store_true", help="Führe OCR mit Tesseract durch"
    )
    mutual_parser.add_argument(
        "--fulltext",
        metavar="FileGrp FULLTEXT",
        action="store_true",
        help="Erstelle eine fileGrp FULLTEXT auf Basis der Bildnamen",
    )

    args = parser.parse_args()
    metadata = read_metadata(args.Metadaten)
    inputfolder = Path(args.Ordner)
    thumbnails = args.Thumbnails
    zip = args.zip
    renameimages = args.rename
    output = args.output
    try:
        metadata["images"]["max_dimensions"]
    except:
        max_dimensions = None
    else:
        max_dimensions = metadata["images"]["max_dimensions"]

    try:
        metadata["images"]["jpg_quality"]
    except:
        jpg_quality = 90
    else:
        jpg_quality = metadata["images"]["jpg_quality"]
    ocr = args.OCR
    if ocr == True:
        try:
            pytesseract.pytesseract.tesseract_cmd = metadata["OCR"][
                "tesseract_executable"
            ]
        except:
            pass
        else:
            pytesseract.pytesseract.tesseract_cmd = metadata["OCR"][
                "tesseract_executable"
            ]

        try:
            tesseract_language = metadata["OCR"]["tesseract_language"]
        except:
            tesseract_language = None
        else:
            tesseract_language = metadata["OCR"]["tesseract_language"]
        try:
            tver = pytesseract.get_tesseract_version()
        except Exception as e:
            print(f"Fehler: {e}", flush=True)
            ocr = False
        else:
            print(f"Tesseract Version: {tver}", flush=True)
    else:
        tesseract_language = None
    create_filegrp_fulltext = args.fulltext
    # ------------------------------------------------

    if output is not None:
        outputfolder = Path(output)
    else:
        outputfolder = Path(os.getcwd(), "structmeta_output")

    outputfolder.mkdir(exist_ok=True)

    Path(outputfolder, "binaries").mkdir(exist_ok=True)
    # ------------------------------------------------
    logger.remove()
    lognamefilename = time.strftime("%Y-%m-%d_%H-%M-%S") + "_structmeta.log"
    logfile = Path(outputfolder / lognamefilename)
    PARAMETER = logger.level("PARAMETER", no=38, color="<blue>")
    logger.add(
        logfile,
        level=0,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        enqueue=True,
    )
    logger.log("PARAMETER", f"Input Ordner: {str(inputfolder)}")
    logger.log("PARAMETER", f"Output Ordner: {str(outputfolder)}")
    logger.log("PARAMETER", f"OCR: {ocr}")
    logger.log("PARAMETER", f"tesseract_language: {tesseract_language}")
    logger.log("PARAMETER", f"renameimages: {renameimages}")
    # ------------------------------------------------
    if metadata["objects"]["type"] == "journal":
        logger.info(f"Bearbeite als Journal")
        journalMETS(
            inputfolder,
            metadata,
            thumbnails,
            ocr,
            outputfolder,
            create_filegrp_fulltext,
            tesseract_language,
            renameimages,
            max_dimensions,
            jpg_quality,
        )
    elif metadata["objects"]["type"] == "monograph":
        monographMETS(
            inputfolder,
            metadata,
            thumbnails,
            ocr,
            outputfolder,
            create_filegrp_fulltext,
            tesseract_language,
            renameimages,
            max_dimensions,
            jpg_quality,
        )
    elif metadata["objects"]["type"] == "newspaper":
        newspaperMETS(
            inputfolder,
            metadata,
            thumbnails,
            ocr,
            outputfolder,
            create_filegrp_fulltext,
            tesseract_language,
            renameimages,
            max_dimensions,
            jpg_quality,
        )
    else:
        logger.error("Fehler")
    # ------------------------------------------------
    if zip:
        helpers.zipfiles(inputfolder, outputfolder, logger, logfile, ocr)

        try:
            # wenn nicht gezippt wird, sind die Ordner nicht leer und werden nicht gelöscht
            Path(outputfolder, "binaries").rmdir()
        except:
            logger.error(f"Konnte {outputfolder}/binaries nicht löschen")
        else:
            logger.info(f"{outputfolder}/binaries gelöscht")
            logger.debug("Vorgang beendet")
    else:
        logger.debug("Vorgang beendet")


if __name__ == "__main__":

    main()
