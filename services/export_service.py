from pathlib import Path

from pypdf import PdfReader, PdfWriter
from fpdf import FPDF
import ebooklib
from ebooklib import epub

from models.project import Project


FONT_PATH = str(Path(__file__).parent.parent / "assets" / "DejaVuSans.ttf")
FONT_NAME = "DejaVu"

def _slugify(text: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in text)
    return safe.strip("_")

def _text_contains_anchor(text: str, anchor: str, min_length: int = 5) -> bool:
    if not text or not anchor:
        return False
    anchor_clean = " ".join(anchor.split()).lower()
    if len(anchor_clean) <= min_length:
        return False
    text_clean = " ".join(text.split()).lower()
    return anchor_clean in text_clean

def export_to_pdf(project: Project, project_dir: Path) -> str:
    exports_dir = project_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    source_pdf = None
    if project.source_filename:
        candidate = project_dir / "source" / project.source_filename
        if candidate.is_file() and candidate.suffix.lower() == ".pdf":
            source_pdf = candidate

    output_filename = f"{_slugify(project.title)}_illustrated.pdf"
    output_path = exports_dir / output_filename

    try:
        if source_pdf:
            _export_pdf_by_insertion(project, source_pdf, output_path)
        else:
            _export_pdf_by_generation(project, output_path)
        return str(output_path)
    except Exception as e:
        if "Latin-1" in str(e) or "charmap" in str(e):
            raise RuntimeError(
                "Encoding error. The text contains characters not supported by the default font. "
                "Try installing a unicode font or checking your text."
            ) from e
        raise e


def export_to_epub(project: Project, project_dir: Path) -> str:
    """
    Export the project to an ePub file.

    Strategy:
    1. If `project.source_filename` exists and is a valid ePub:
       - We perform an "Insert" export: read the original ePub and inject
         scene images at the appropriate anchor positions.
    2. Otherwise:
       - We perform a "Generation" export: create a brand new ePub
         from `chapter.raw_text` + images.

    Returns the absolute path to the generated ePub.
    """
    exports_dir = project_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    source_epub = None
    if project.source_filename:
        candidate = project_dir / "source" / project.source_filename
        if candidate.is_file() and candidate.suffix.lower() == ".epub":
            source_epub = candidate

    output_filename = f"{_slugify(project.title)}.epub"
    output_path = exports_dir / output_filename

    if source_epub:
        _export_epub_by_insertion(project, source_epub, output_path)
        return str(output_path)

    book = epub.EpubBook()
    book.set_identifier(f"id_{_slugify(project.title)}")
    book.set_title(project.title)
    book.set_language('en')

    epub_chapters = []

    for ch in project.chapters:
        c_title = ch.title
        c_filename = f"chap_{ch.order_index}.xhtml"

        html_content = f"<h1>{c_title}</h1>"

        paragraphs = ch.raw_text.split('\n')
        scenes_to_insert = list(ch.scenes) if ch.scenes else []
        remaining_scenes = []
        cumulative_text = ""

        for p in paragraphs:
            stripped = p.strip()
            if not stripped:
                continue
            html_content += f"<p>{stripped}</p>"
            cumulative_text += " " + stripped

            scenes_inserted_here = []
            for sc in scenes_to_insert:
                if sc.anchor_text and sc.image_path and Path(sc.image_path).is_file():
                    if _text_contains_anchor(cumulative_text, sc.anchor_text):
                        scenes_inserted_here.append(sc)

            for sc in scenes_inserted_here:
                scenes_to_insert.remove(sc)
                img_path = Path(sc.image_path)
                img_name = f"img_{sc.id[:8]}.png"

                epub_img = epub.EpubItem(
                    uid=f"img_{sc.id[:8]}",
                    file_name=f"images/{img_name}",
                    media_type="image/png",
                    content=img_path.read_bytes()
                )
                book.add_item(epub_img)

                html_content += f"""
                <div style="text-align:center; margin: 20px 0;">
                    <img src="images/{img_name}" alt="{sc.title}" style="max-width:100%;" />
                    <p style="font-style:italic; font-size: 0.9em; color:#666;">{sc.title}</p>
                </div>
                """

        remaining_scenes.extend(scenes_to_insert)

        if remaining_scenes:
            for sc in remaining_scenes:
                if sc.image_path and Path(sc.image_path).is_file():
                    img_path = Path(sc.image_path)
                    img_name = f"img_{sc.id[:8]}.png"

                    epub_img = epub.EpubItem(
                        uid=f"img_{sc.id[:8]}",
                        file_name=f"images/{img_name}",
                        media_type="image/png",
                        content=img_path.read_bytes()
                    )
                    book.add_item(epub_img)

                    html_content += f"""
                    <div style="text-align:center; margin: 20px 0; page-break-before: always;">
                        <img src="images/{img_name}" alt="{sc.title}" style="max-width:100%;" />
                        <p style="font-style:italic; font-size: 0.9em; color:#666;">{sc.title}</p>
                    </div>
                    """

        chap = epub.EpubHtml(title=c_title, file_name=c_filename, lang='en')
        chap.content = html_content
        book.add_item(chap)
        epub_chapters.append(chap)

    book.spine = ['nav'] + epub_chapters
    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(output_path), book, {})
    return str(output_path)


def _export_epub_by_insertion(project: Project, source_epub_path: Path, output_path: Path):
    from bs4 import BeautifulSoup

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        book = epub.read_epub(str(source_epub_path), options={"ignore_ncx": True})

    img_counter = 0
    for ch in project.chapters:
        scenes_to_insert = [sc for sc in ch.scenes if sc.image_path and Path(sc.image_path).is_file()]
        if not scenes_to_insert:
            continue

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            item_text = soup.get_text(separator=" ").strip().lower()

            if not item_text or len(item_text) < 50:
                continue

            chapter_snippet = " ".join(ch.raw_text[:200].split()).lower()
            if chapter_snippet not in " ".join(item_text.split()):
                continue

            remaining_scenes = list(scenes_to_insert)

            for sc in list(remaining_scenes):
                if not sc.anchor_text or len(sc.anchor_text) < 10:
                    continue

                anchor_clean = " ".join(sc.anchor_text.split()).lower()

                # Find the paragraph element containing the anchor text
                for p_tag in soup.find_all(["p", "div"]):
                    p_text = " ".join(p_tag.get_text().split()).lower()
                    if anchor_clean in p_text:
                        # Insert image after this paragraph
                        img_counter += 1
                        img_name = f"img_inserted_{img_counter}.png"
                        img_path = Path(sc.image_path)

                        # Add image item to the book
                        epub_img = epub.EpubItem(
                            uid=f"img_ins_{img_counter}",
                            file_name=f"images/{img_name}",
                            media_type="image/png",
                            content=img_path.read_bytes()
                        )
                        book.add_item(epub_img)

                        # Create the image HTML element
                        img_div = soup.new_tag("div", style="text-align:center; margin: 20px 0;")
                        img_tag = soup.new_tag("img", src=f"images/{img_name}", alt=sc.title, style="max-width:100%;")
                        caption_tag = soup.new_tag("p", style="font-style:italic; font-size: 0.9em; color:#666;")
                        caption_tag.string = sc.title
                        img_div.append(img_tag)
                        img_div.append(caption_tag)

                        p_tag.insert_after(img_div)
                        remaining_scenes.remove(sc)
                        break

            if remaining_scenes:
                body = soup.find("body")
                if not body:
                    body = soup

                for sc in remaining_scenes:
                    img_counter += 1
                    img_name = f"img_inserted_{img_counter}.png"
                    img_path = Path(sc.image_path)

                    epub_img = epub.EpubItem(
                        uid=f"img_ins_{img_counter}",
                        file_name=f"images/{img_name}",
                        media_type="image/png",
                        content=img_path.read_bytes()
                    )
                    book.add_item(epub_img)

                    img_div = soup.new_tag("div", style="text-align:center; margin: 20px 0; page-break-before: always;")
                    img_tag = soup.new_tag("img", src=f"images/{img_name}", alt=sc.title, style="max-width:100%;")
                    caption_tag = soup.new_tag("p", style="font-style:italic; font-size: 0.9em; color:#666;")
                    caption_tag.string = sc.title
                    img_div.append(img_tag)
                    img_div.append(caption_tag)
                    body.append(img_div)

            item.set_content(str(soup).encode("utf-8"))
            break

    epub.write_epub(str(output_path), book, {})


def _export_pdf_by_insertion(project: Project, source_pdf_path: Path, output_pdf_path: Path):
    reader = PdfReader(source_pdf_path)
    writer = PdfWriter()

    page_width_pt = 595.28
    page_height_pt = 841.89
    if len(reader.pages) > 0:
        box = reader.pages[0].mediabox
        page_width_pt = float(box.width)
        page_height_pt = float(box.height)

    pt_to_mm = 0.352778
    page_width_mm = page_width_pt * pt_to_mm
    page_height_mm = page_height_pt * pt_to_mm

    total_source_pages = len(reader.pages)
    sorted_chapters = sorted(project.chapters, key=lambda c: c.order_index)
    current_search_idx = 0

    for ch in sorted_chapters:
        if ch.start_page and ch.start_page > 0:
            if (ch.start_page - 1) > current_search_idx:
                current_search_idx = ch.start_page - 1
            continue

        found_page_idx = -1

        # We search for a snippet of the raw text.
        # Ideally, we take the unique beginning of the chapter (Title + Intro).
        # This avoids matching the Table of Contents (which has Title but no Intro).
        if ch.raw_text and len(ch.raw_text) > 20:
            snippet = ch.raw_text[:100]
            search_str = " ".join(snippet.split()).lower()
        else:
            search_str = " ".join(ch.title.split()).lower()

        for p_idx in range(current_search_idx, total_source_pages):
            try:
                page_text = reader.pages[p_idx].extract_text()
                if not page_text:
                    continue

                # Normalize page text same way
                page_clean = " ".join(page_text.split()).lower()

                if search_str in page_clean:
                    found_page_idx = p_idx
                    break
            except Exception:
                pass

        if found_page_idx != -1:
            ch.start_page = found_page_idx + 1
            current_search_idx = found_page_idx

    current_source_page_idx = 0

    for ch in sorted_chapters:
        start_p = (ch.start_page - 1) if ch.start_page else current_source_page_idx
        end_p = total_source_pages

        next_valid_start = None
        for next_ch in sorted_chapters:
            if next_ch.order_index > ch.order_index and next_ch.start_page:
                next_valid_start = next_ch.start_page - 1
                break

        if next_valid_start is not None:
            end_p = next_valid_start
        elif ch.end_page:
            end_p = ch.end_page

        if start_p < current_source_page_idx:
            start_p = current_source_page_idx
        if end_p > total_source_pages:
            end_p = total_source_pages
        if end_p < start_p:
            end_p = start_p

        scene_insertions = {}
        remaining_scenes = []
        
        for sc in ch.scenes:
            if not sc.image_path or not Path(sc.image_path).is_file():
                continue
                
            inserted = False
            if hasattr(sc, "anchor_text") and sc.anchor_text:
                if len(sc.anchor_text) > 10:
                    for p_idx in range(start_p, end_p):
                        try:
                            page_text = reader.pages[p_idx].extract_text()
                            if not page_text: continue

                            if _text_contains_anchor(page_text, sc.anchor_text):
                                if p_idx not in scene_insertions:
                                    scene_insertions[p_idx] = []
                                scene_insertions[p_idx].append(sc)
                                inserted = True
                                break
                        except Exception:
                            pass
                            
            if not inserted:
                remaining_scenes.append(sc)

        page_count_added = 0
        for p_idx in range(start_p, end_p):
            if p_idx < total_source_pages:
                writer.add_page(reader.pages[p_idx])
                page_count_added += 1
                current_source_page_idx = p_idx + 1

                if p_idx in scene_insertions:
                    temp_pdf_path = output_pdf_path.parent / f"temp_scenes_{ch.order_index}_{p_idx}.pdf"
                    _create_images_pdf_overlay(scene_insertions[p_idx], temp_pdf_path, width_mm=page_width_mm, height_mm=page_height_mm)

                    if temp_pdf_path.exists():
                        try:
                            img_reader = PdfReader(str(temp_pdf_path))
                            for ip in img_reader.pages:
                                writer.add_page(ip)
                        except Exception:
                            pass
                        try:
                            temp_pdf_path.unlink()
                        except Exception:
                            pass

        if remaining_scenes:
            temp_pdf_path = output_pdf_path.parent / f"temp_scenes_{ch.order_index}_end.pdf"
            _create_images_pdf_overlay(remaining_scenes, temp_pdf_path, width_mm=page_width_mm, height_mm=page_height_mm)

            if temp_pdf_path.exists():
                try:
                    img_reader = PdfReader(str(temp_pdf_path))
                    for ip in img_reader.pages:
                        writer.add_page(ip)
                except Exception:
                    pass
                try:
                    temp_pdf_path.unlink()
                except Exception:
                    pass

    if current_source_page_idx < total_source_pages:
        for p_idx in range(current_source_page_idx, total_source_pages):
            writer.add_page(reader.pages[p_idx])

    writer.write(output_pdf_path)


def _create_images_pdf_overlay(scenes: list, output_path: Path, width_mm=210, height_mm=297):
    pdf = FPDF(unit="mm", format=[width_mm, height_mm])
    pdf.set_auto_page_break(False)

    for sc in scenes:
        pdf.add_page()
        img_path = str(Path(sc.image_path).resolve())

        from PIL import Image
        try:
            with Image.open(img_path) as im:
                w, h = im.size
                aspect = h / w if w else 1.0
        except Exception:
            aspect = 1.0

        margin = width_mm * 0.1
        available_w = width_mm - (2 * margin)
        available_h = height_mm - (2 * margin) - 20

        if aspect > (available_h / available_w):
            target_h = available_h
            target_w = target_h / aspect
        else:
            target_w = available_w
            target_h = target_w * aspect

        x_pos = (width_mm - target_w) / 2
        y_pos = (height_mm - target_h) / 2 if target_h < (height_mm - 40) else margin

        pdf.image(img_path, x=x_pos, y=y_pos, w=target_w)

        try:
            if Path(FONT_PATH).exists():
                pdf.add_font(FONT_NAME, '', FONT_PATH)
                pdf.set_font(FONT_NAME, size=12)
            else:
                pdf.set_font("Helvetica", size=12)

            caption_y = y_pos + target_h + 5
            if caption_y > (height_mm - margin):
                caption_y = height_mm - margin

            pdf.set_y(caption_y)
            safe_title = sc.title.encode("latin-1", errors="replace").decode("latin-1") if not Path(FONT_PATH).exists() else sc.title
            pdf.multi_cell(0, 10, safe_title, align='C')

        except Exception:
            pass

    pdf.output(str(output_path))


def _safe_text(text: str, has_unicode: bool) -> str:
    if has_unicode:
        return text
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _export_pdf_by_generation(project: Project, output_pdf_path: Path):
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)

    has_unicode_font = False
    if Path(FONT_PATH).exists():
        try:
            pdf.add_font(FONT_NAME, '', FONT_PATH)
            pdf.set_font(FONT_NAME, size=11)
            has_unicode_font = True
        except Exception:
            pass

    if not has_unicode_font:
        pdf.set_font("Helvetica", size=11)

    pdf.add_page()
    pdf.set_font_size(24)
    pdf.cell(0, 60, '', ln=1)
    pdf.multi_cell(0, 10, _safe_text(project.title, has_unicode_font), align='C')
    pdf.set_font_size(14)
    pdf.cell(0, 20, _safe_text(f"Style: {project.art_style}", has_unicode_font), ln=1, align='C')

    pdf.add_page()

    for ch in project.chapters:
        pdf.set_font_size(18)
        pdf.cell(0, 15, _safe_text(ch.title, has_unicode_font), ln=1, align='L')
        pdf.ln(5)

        pdf.set_font_size(11)

        paragraphs = ch.raw_text.split('\n')
        scenes_to_insert = list(ch.scenes) if ch.scenes else []
        remaining_scenes = []
        cumulative_text = ""

        for p in paragraphs:
            if not p.strip():
                continue
            pdf.multi_cell(0, 6, _safe_text(p.strip(), has_unicode_font))
            pdf.ln(2)
            cumulative_text += " " + p.strip()

            scenes_inserted_here = []
            for sc in scenes_to_insert:
                if sc.anchor_text and sc.image_path and Path(sc.image_path).is_file():
                    if _text_contains_anchor(cumulative_text, sc.anchor_text):
                        scenes_inserted_here.append(sc)

            for sc in scenes_inserted_here:
                scenes_to_insert.remove(sc)
                pdf.add_page()
                img_path = str(Path(sc.image_path).resolve())

                from PIL import Image
                try:
                    with Image.open(img_path) as im:
                        w, h = im.size
                        aspect = h / w if w else 1.0
                except Exception:
                    aspect = 1.0

                avail_w = 180
                avail_h = 250

                target_w = avail_w
                target_h = target_w * aspect
                if target_h > avail_h:
                    target_h = avail_h
                    target_w = target_h / aspect

                x_pos = (210 - target_w) / 2
                pdf.image(img_path, x=x_pos, y=pdf.get_y(), w=target_w)
                pdf.set_y(pdf.get_y() + target_h + 5)
                pdf.set_font_size(10)
                pdf.cell(0, 10, _safe_text(sc.title, has_unicode_font), ln=1, align='C')
                pdf.set_font_size(11)
                pdf.add_page()

        remaining_scenes.extend(scenes_to_insert)
        pdf.ln(10)

        if remaining_scenes:
            pdf.add_page()
            pdf.set_font_size(14)
            pdf.cell(0, 10, 'Illustrations', ln=1, align='C')
            pdf.ln(5)

            for sc in remaining_scenes:
                if sc.image_path and Path(sc.image_path).is_file():
                    img_path = str(Path(sc.image_path).resolve())

                    from PIL import Image
                    try:
                        with Image.open(img_path) as im:
                            w, h = im.size
                            aspect = h / w if w else 1.0
                    except Exception:
                        aspect = 1.0

                    target_w = 140
                    target_h = target_w * aspect

                    if pdf.get_y() + target_h + 20 > 280:
                        pdf.add_page()

                    pdf.image(img_path, w=target_w, x=(210-target_w)/2)
                    pdf.ln(5)

    pdf.output(str(output_pdf_path))
