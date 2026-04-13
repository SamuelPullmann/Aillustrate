from __future__ import annotations

import os
import re
import warnings
from pathlib import Path

from pypdf import PdfReader
import ebooklib
from ebooklib import epub as epub_lib
from bs4 import BeautifulSoup

from models.chapter import Chapter


def read_file_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".txt":
        return Path(file_path).read_text(encoding="utf-8", errors="replace")

    if ext == ".pdf":
        return _extract_pdf_text(file_path)

    if ext == ".epub":
        return _extract_epub_text(file_path)

    raise ValueError(f"Unsupported file type: {ext}. Only .txt, .pdf and .epub are supported.")


def get_project_name_from_file(file_path: str) -> str:
    return Path(file_path).stem


def split_into_chapters(file_path: str) -> list[Chapter]:
    """
    Main entry point: try to split the file into chapters.

    Strategy (for PDF):
        1. Try splitting by PDF bookmarks first (most reliable).
        2. Fall back to regex-based chapter detection in text.

    For TXT files only regex-based splitting is used.

    Returns a list of Chapter dataclasses with order_index, title, raw_text.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        chapters = _split_pdf_by_bookmarks(file_path)
        if chapters:
            return chapters

        full_text = _extract_pdf_text(file_path)
        chapters = _split_text_by_chapter_regex(full_text)
        if chapters:
            return chapters

        return [Chapter(order_index=1, title="Whole book", raw_text=full_text.strip())]

    elif ext == ".txt":
        full_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        chapters = _split_text_by_chapter_regex(full_text)
        if chapters:
            return chapters

        return [Chapter(order_index=1, title="Whole book", raw_text=full_text.strip())]

    elif ext == ".epub":
        chapters = _split_epub_by_toc(file_path)
        if chapters:
            return chapters

        chapters = _split_epub_by_spine(file_path)
        if chapters:
            return chapters

        full_text = _extract_epub_text(file_path)
        chapters = _split_text_by_chapter_regex(full_text)
        if chapters:
            return chapters

        return [Chapter(order_index=1, title="Whole book", raw_text=full_text.strip())]

    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf_text(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages_text: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)
    return "\n".join(pages_text)


def _split_pdf_by_bookmarks(file_path: str) -> list[Chapter]:
    reader = PdfReader(file_path)
    outline = reader.outline
    if not outline:
        return []

    bookmark_entries = _flatten_outline(reader, outline)
    if not bookmark_entries:
        return []

    chapter_pattern = re.compile(
        r"^(chapter|kapitola)\s+\w+",
        re.IGNORECASE,
    )
    chapter_bookmarks = [
        (title, page_idx) for title, page_idx in bookmark_entries
        if chapter_pattern.search(title.strip())
    ]

    if not chapter_bookmarks:
        return []

    total_pages = len(reader.pages)
    chapters: list[Chapter] = []

    for i, (title, start_page) in enumerate(chapter_bookmarks):
        if i + 1 < len(chapter_bookmarks):
            end_page = chapter_bookmarks[i + 1][1]
        else:
            end_page = total_pages

        text_parts: list[str] = []
        for p in range(start_page, end_page):
            page_text = reader.pages[p].extract_text()
            if page_text:
                text_parts.append(page_text)

        raw_text = "\n".join(text_parts).strip()
        if raw_text:
            chapters.append(Chapter(
                order_index=i + 1,
                title=title.strip(),
                raw_text=raw_text,
                start_page=start_page + 1,
                end_page=end_page
            ))

    return chapters


def _flatten_outline(reader: PdfReader, outline, parent=None):
    """Recursively flatten nested PDF outline into (title, page_index) pairs, cleaning up null bytes."""
    result = []
    for item in outline:
        if isinstance(item, list):
            result.extend(_flatten_outline(reader, item))
        else:
            try:
                title = item.title.replace('\u0000', '').replace('\x00', '').strip()
                page_idx = reader.get_destination_page_number(item)
                result.append((title, page_idx))
            except Exception:
                pass
    return result


_CHAPTER_RE = re.compile(
    r"^\s*(chapter|kapitola)"
    r"\s+"
    r"(\d+|[IVXLCDM]+)"
    r"(\s*[:–—\-]\s*.+)?$",
    re.IGNORECASE | re.MULTILINE,
)


def _split_text_by_chapter_regex(text: str) -> list[Chapter]:
    matches = list(_CHAPTER_RE.finditer(text))
    if not matches:
        return []

    chapters: list[Chapter] = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        chapter_title = match.group(0).replace('\u0000', '').replace('\x00', '').strip()
        raw_text = text[start:end].strip()

        chapters.append(Chapter(
            order_index=i + 1,
            title=chapter_title,
            raw_text=raw_text,
        ))

    return chapters


def _read_epub(file_path: str):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return epub_lib.read_epub(file_path, options={"ignore_ncx": True})


def _split_epub_by_toc(file_path: str) -> list[Chapter]:
    book = _read_epub(file_path)

    toc_entries = _flatten_epub_toc(book.toc)
    if not toc_entries:
        return []

    items_by_href: dict = {}
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        items_by_href[item.get_name()] = item

    _soup_cache: dict = {}

    def get_soup(href_file: str) -> BeautifulSoup | None:
        if href_file not in _soup_cache:
            item = items_by_href.get(href_file)
            if not item:
                _soup_cache[href_file] = None
            else:
                _soup_cache[href_file] = BeautifulSoup(item.get_content(), "html.parser")
        return _soup_cache[href_file]

    chapters: list[Chapter] = []
    order = 1

    for i, (title, href) in enumerate(toc_entries):
        if "#" in href:
            href_file, anchor = href.split("#", 1)
        else:
            href_file, anchor = href, None

        soup = get_soup(href_file)
        if not soup:
            continue

        next_file = None
        next_anchor = None
        if i + 1 < len(toc_entries):
            next_href = toc_entries[i + 1][1]
            if "#" in next_href:
                next_file, next_anchor = next_href.split("#", 1)
            else:
                next_file, next_anchor = next_href, None

        if next_file == href_file and (anchor or next_anchor):
            text = _extract_text_between_anchors(soup, anchor, next_anchor)
        elif anchor:
            text = _extract_text_from_anchor(soup, anchor)
        else:
            if next_file == href_file and next_anchor:
                text = _extract_text_between_anchors(soup, None, next_anchor)
            else:
                text = soup.get_text(separator="\n").strip()

        if not text or len(text) < 20:
            continue

        chapters.append(Chapter(
            order_index=order,
            title=title,
            raw_text=text,
        ))
        order += 1

    return chapters


def _flatten_epub_toc(toc) -> list[tuple[str, str]]:
    """Flatten ePub TOC (which can be nested with sections) into (title, href) pairs."""
    result = []
    for entry in toc:
        if isinstance(entry, tuple):
            section_link, children = entry
            result.append((section_link.title, section_link.href))
            result.extend(_flatten_epub_toc(children))
        else:
            result.append((entry.title, entry.href))
    return result


def _extract_text_from_anchor(soup: BeautifulSoup, anchor_id: str) -> str:
    anchor_el = soup.find(id=anchor_id) or soup.find("a", attrs={"name": anchor_id})
    if not anchor_el:
        return soup.get_text(separator="\n").strip()

    parts = []
    for sibling in anchor_el.find_all_next(string=True):
        text = sibling.strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_text_between_anchors(soup: BeautifulSoup, start_anchor: str | None, end_anchor: str | None) -> str:
    all_strings = list(soup.find_all(string=True))

    start_idx = 0
    end_idx = len(all_strings)

    if start_anchor:
        anchor_el = soup.find(id=start_anchor) or soup.find("a", attrs={"name": start_anchor})
        if anchor_el:
            for idx, s in enumerate(all_strings):
                if anchor_el in (s.parent, *s.parents):
                    start_idx = idx
                    break
                if s.find_previous(id=start_anchor):
                    start_idx = idx
                    break

    if end_anchor:
        anchor_el = soup.find(id=end_anchor) or soup.find("a", attrs={"name": end_anchor})
        if anchor_el:
            for idx, s in enumerate(all_strings):
                if idx < start_idx:
                    continue
                if s.find_previous(id=end_anchor) and idx > start_idx:
                    end_idx = idx
                    break

    parts = []
    for s in all_strings[start_idx:end_idx]:
        text = s.strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_epub_text(file_path: str) -> str:
    book = _read_epub(file_path)
    texts: list[str] = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n")
        if text and text.strip():
            texts.append(text.strip())

    return "\n".join(texts)


def _split_epub_by_spine(file_path: str) -> list[Chapter]:
    book = _read_epub(file_path)

    items_by_id: dict = {}
    for item in book.get_items():
        items_by_id[item.get_id()] = item

    chapters: list[Chapter] = []
    order = 1

    for spine_entry in book.spine:
        item_id = spine_entry[0] if isinstance(spine_entry, tuple) else spine_entry
        item = items_by_id.get(item_id)
        if not item:
            continue

        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n").strip()

        if not text or len(text) < 50:
            continue

        title = None
        for tag in ("h1", "h2", "h3"):
            heading = soup.find(tag)
            if heading and heading.get_text(strip=True):
                title = heading.get_text(strip=True)
                break

        if not title:
            title = f"Chapter {order}"

        chapters.append(Chapter(
            order_index=order,
            title=title,
            raw_text=text,
        ))
        order += 1

    return chapters
