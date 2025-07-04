#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import logging
import re
import uuid
import json
from posixpath import normpath
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED
from time import time
from xml.dom.minidom import parseString, getDOMImplementation, Element
from six import text_type as unicode
try:
    from urllib.parse import unquote  # Python 3
except ImportError:
    from urllib import unquote        # Python 2

# Setup basic logging
logger = logging.getLogger(__name__)
loghandler = logging.StreamHandler()
loghandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(loghandler)
logger.setLevel(logging.INFO) # Set to INFO for less verbose output, or DEBUG for more

# --- Helper functions and classes from original script ---

def newTag(dom, name, attrs=None, text=None):
    """Utility method for creating new XML tags."""
    tag = dom.createElement(name)
    if attrs is not None:
        for attr, value in attrs.items():
            tag.setAttribute(attr, value)
    if text is not None:
        tag.appendChild(dom.createTextNode(unicode(text)))
    return tag

def get_path_part(n):
    """Gets the directory part of a path."""
    relpath = os.path.dirname(n)
    if len(relpath) > 0:
        relpath = relpath + "/"
    return relpath

def sanitize_filename(name):
    """Removes illegal characters from a string to make it a valid filename."""
    invalid_chars = r'<>:"/\|?*'
    if name:
        for char in invalid_chars:
            name = name.replace(char, '')
        return name.strip()
    return "Untitled"

def do_merge_core(output_filepath, input_files):
    """
    Core merging logic adapted from the original epubmerge script's doMerge function.
    """
    # --- Initialization ---
    outputepub = ZipFile(output_filepath, "w", compression=ZIP_STORED, allowZip64=True)
    outputepub.writestr("mimetype", "application/epub+zip")
    outputepub.close()

    outputepub = ZipFile(output_filepath, "a", compression=ZIP_DEFLATED, allowZip64=True)

    # --- Create META-INF/container.xml ---
    containerdom = getDOMImplementation().createDocument(None, "container", None)
    containertop = containerdom.documentElement
    containertop.setAttribute("version", "1.0")
    containertop.setAttribute("xmlns", "urn:oasis:names:tc:opendocument:xmlns:container")
    rootfiles = containerdom.createElement("rootfiles")
    containertop.appendChild(rootfiles)
    rootfiles.appendChild(newTag(containerdom, "rootfile", {"full-path": "OEBPS/content.opf", "media-type": "application/oebps-package+xml"}))
    outputepub.writestr("META-INF/container.xml", containerdom.toprettyxml(indent='  ', encoding='utf-8'))

    # --- Data structures for merging ---
    items = [("ncx", "toc.ncx", "application/x-dtbncx+xml")]
    itemrefs = []
    navmaps = []
    booktitles = []
    allauthors = []
    fileasauthors = {}
    firstitemhrefs = []
    itemhrefs = {}
    filelist = []
    cover_info = {} # To store data, media_type for the main cover
    
    # --- Process each input epub ---
    booknum = 1
    for epub_path in input_files:
        logger.info("Processing: %s" % os.path.basename(epub_path))
        try:
            epub = ZipFile(epub_path, 'r')
            book_prefix = "%d" % booknum
            book_dir = "OEBPS/%s/" % book_prefix

            container = epub.read("META-INF/container.xml")
            containerdom = parseString(container)
            rootfilename = containerdom.getElementsByTagName("rootfile")[0].getAttribute("full-path")
            opf_path_part = get_path_part(rootfilename)

            contentdom = parseString(epub.read(rootfilename))
            
            # --- Find and store cover from the FIRST book ---
            if booknum == 1:
                meta_tags = contentdom.getElementsByTagName("meta")
                cover_id = None
                for meta in meta_tags:
                    if meta.getAttribute("name") == "cover":
                        cover_id = meta.getAttribute("content")
                        break
                
                if cover_id:
                    for item in contentdom.getElementsByTagName("item"):
                        if item.getAttribute("id") == cover_id:
                            cover_href = unquote(item.getAttribute("href"))
                            try:
                                cover_data = epub.read(normpath(os.path.join(opf_path_part, cover_href)))
                                cover_info = {
                                    "data": cover_data,
                                    "media_type": item.getAttribute("media-type"),
                                }
                                logger.info("Found cover image from first book: %s" % cover_href)
                            except KeyError:
                                logger.warning("Cover image '%s' listed in manifest but not found." % cover_href)
                            break
            
            try:
                booktitles.append(contentdom.getElementsByTagName("dc:title")[0].firstChild.data)
            except:
                booktitles.append("(Title Missing)")

            authors = []
            for creator in contentdom.getElementsByTagName("dc:creator"):
                if (creator.getAttribute("opf:role") == "aut" or not creator.hasAttribute("opf:role")) and creator.firstChild:
                    author_name = creator.firstChild.data
                    authors.append(author_name)
                    if creator.getAttribute("opf:file-as"):
                        fileasauthors[author_name] = creator.getAttribute("opf:file-as")
            if not authors:
                authors.append("(Author Missing)")
            allauthors.append(authors)

            manifest_items = contentdom.getElementsByTagName("item")
            ncx_href = ''
            for item in manifest_items:
                item_id = item.getAttribute("id")
                item_href_orig = unquote(item.getAttribute("href"))
                
                if item.getAttribute("media-type") == "application/x-dtbncx+xml":
                    ncx_href = normpath(os.path.join(opf_path_part, item_href_orig))
                    continue

                new_id = book_prefix + "_" + item_id
                new_href = normpath(os.path.join(book_dir, item_href_orig))
                
                itemhrefs[new_id] = new_href
                if new_href not in filelist:
                    try:
                        filedata = epub.read(normpath(os.path.join(opf_path_part, item_href_orig)))
                        outputepub.writestr(new_href, filedata)
                        items.append((new_id, new_href.replace("OEBPS/", ""), item.getAttribute("media-type")))
                        filelist.append(new_href)
                    except KeyError:
                        logger.warning("Skipping missing file: %s in %s" % (item_href_orig, os.path.basename(epub_path)))
                        if new_id in itemhrefs:
                            del itemhrefs[new_id]
            
            spine_itemrefs = contentdom.getElementsByTagName("itemref")
            first_found = False
            for itemref in spine_itemrefs:
                idref = book_prefix + "_" + itemref.getAttribute("idref")
                if idref in itemhrefs:
                    itemrefs.append(idref)
                    if not first_found:
                        firstitemhrefs.append(itemhrefs[idref])
                        first_found = True
            if not first_found:
                 firstitemhrefs.append("OEBPS/content.opf")

            if ncx_href:
                tocdom = parseString(epub.read(ncx_href))
                for navpoint in tocdom.getElementsByTagName("navPoint"):
                    navpoint.setAttribute("id", book_prefix + "_" + navpoint.getAttribute("id"))
                for content in tocdom.getElementsByTagName("content"):
                    src = content.getAttribute("src")
                    new_src_path = normpath(os.path.join(book_dir, src.split('#')[0])).replace("OEBPS/", "")
                    new_src = new_src_path + ('#' + src.split('#', 1)[1] if '#' in src else '')
                    content.setAttribute("src", new_src)
                navmaps.append(tocdom.getElementsByTagName("navMap")[0])
            else:
                 navmaps.append(None)

            booknum += 1
        except Exception as e:
            logger.error("Failed to process file: %s. Error: %s" % (epub_path, e))
            raise

    # --- Write Cover files if found ---
    cover_item_id = "cover-img"
    cover_xhtml_id = "cover"
    cover_image_filename = ""
    cover_xhtml_filename = "cover.xhtml"

    if cover_info:
        ext = 'jpg'
        if 'jpeg' in cover_info['media_type']: ext = 'jpg'
        elif 'png' in cover_info['media_type']: ext = 'png'
        elif 'gif' in cover_info['media_type']: ext = 'gif'
        cover_image_filename = "cover." + ext
        
        outputepub.writestr(os.path.join("OEBPS", cover_image_filename), cover_info['data'])
        
        cover_xhtml_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>Cover</title><style type="text/css">body{{margin:0;padding:0;text-align:center;}}img{{max-width:100%;max-height:100vh;}}</style></head>
<body><div><img src="{}" alt="Cover Image"/></div></body></html>""".format(cover_image_filename)
        outputepub.writestr(os.path.join("OEBPS", cover_xhtml_filename), cover_xhtml_content.encode('utf-8'))

    # --- Assemble new content.opf ---
    uniqueid = "urn:uuid:%s" % uuid.uuid4()
    contentdom = getDOMImplementation().createDocument(None, "package", None)
    package = contentdom.documentElement
    package.setAttribute("version", "2.0")
    package.setAttribute("xmlns", "http://www.idpf.org/2007/opf")
    package.setAttribute("unique-identifier", "bookid")

    metadata = newTag(contentdom, "metadata", attrs={"xmlns:dc": "http://purl.org/dc/elements/1.1/", "xmlns:opf": "http://www.idpf.org/2007/opf"})
    package.appendChild(metadata)
    
    metadata.appendChild(newTag(contentdom, "dc:identifier", text=uniqueid, attrs={"id": "bookid"}))
    
    title = (booktitles[0] + " (Merged)") if booktitles else "Merged Book"
    metadata.appendChild(newTag(contentdom, "dc:title", text=title))

    if cover_info:
        metadata.appendChild(newTag(contentdom, "meta", attrs={"name": "cover", "content": cover_item_id}))

    usedauthors = set()
    for authorlist in allauthors:
        for author in authorlist:
            if author not in usedauthors:
                tagattrs = {"opf:role": "aut"}
                if author in fileasauthors:
                    tagattrs["opf:file-as"] = fileasauthors[author]
                metadata.appendChild(newTag(contentdom, "dc:creator", text=author, attrs=tagattrs))
                usedauthors.add(author)

    manifest = newTag(contentdom, "manifest")
    package.appendChild(manifest)
    
    if cover_info:
        manifest.appendChild(newTag(contentdom, "item", attrs={'id': cover_item_id, 'href': cover_image_filename, 'media-type': cover_info['media_type']}))
        manifest.appendChild(newTag(contentdom, "item", attrs={'id': cover_xhtml_id, 'href': cover_xhtml_filename, 'media-type': 'application/xhtml+xml'}))

    for item_id, href, media_type in items:
        manifest.appendChild(newTag(contentdom, "item", attrs={'id': item_id, 'href': href, 'media-type': media_type}))

    spine = newTag(contentdom, "spine", attrs={"toc": "ncx"})
    package.appendChild(spine)
    
    if cover_info:
        spine.appendChild(newTag(contentdom, "itemref", attrs={"idref": cover_xhtml_id}))

    for idref in itemrefs:
        if idref in itemhrefs:
            spine.appendChild(newTag(contentdom, "itemref", attrs={"idref": idref}))

    if cover_info:
        guide = newTag(contentdom, "guide")
        package.appendChild(guide)
        guide.appendChild(newTag(contentdom, "reference", attrs={"type": "cover", "title": "Cover", "href": cover_xhtml_filename}))

    outputepub.writestr("OEBPS/content.opf", contentdom.toprettyxml(indent='  ', encoding='utf-8'))

    # --- Assemble new toc.ncx ---
    tocncxdom = getDOMImplementation().createDocument(None, "ncx", None)
    ncx = tocncxdom.documentElement
    ncx.setAttribute("version", "2005-1")
    ncx.setAttribute("xmlns", "http://www.daisy.org/z3986/2005/ncx/")
    
    head = newTag(tocncxdom, "head")
    ncx.appendChild(head)
    head.appendChild(newTag(tocncxdom, "meta", attrs={"name": "dtb:uid", "content": uniqueid}))
    
    docTitle = newTag(tocncxdom, "docTitle")
    ncx.appendChild(docTitle)
    docTitle.appendChild(newTag(tocncxdom, "text", text=title))

    tocnavMap = newTag(tocncxdom, "navMap")
    ncx.appendChild(tocnavMap)
    
    play_order = 1
    for i, navmap in enumerate(navmaps):
        if navmap is None: continue
        
        book_title = booktitles[i]
        
        book_navpoint = newTag(tocncxdom, "navPoint", {"id": "book_%d" % (i + 1), "playOrder": str(play_order)})
        play_order += 1
        
        navlabel = newTag(tocncxdom, "navLabel")
        navlabel.appendChild(newTag(tocncxdom, "text", text=book_title))
        book_navpoint.appendChild(navlabel)
        book_navpoint.appendChild(newTag(tocncxdom, "content", {"src": firstitemhrefs[i].replace("OEBPS/","")}))
        
        for node in navmap.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.tagName == 'navPoint':
                for sub_navpoint in node.getElementsByTagName("*"):
                    if sub_navpoint.hasAttribute("playOrder"):
                         sub_navpoint.setAttribute("playOrder", str(play_order))
                         play_order += 1
                node.setAttribute("playOrder", str(play_order))
                play_order += 1
                book_navpoint.appendChild(node)

        tocnavMap.appendChild(book_navpoint)

    outputepub.writestr("OEBPS/toc.ncx", tocncxdom.toprettyxml(indent='  ', encoding='utf-8'))

    # --- Finalize ---
    outputepub.close()
    logger.info("🎉 Merge complete! File saved to: %s" % output_filepath)

# --- Project Integration Functions ---

def load_default_path_from_settings():
    """从共享设置文件中读取默认工作目录。"""
    try:
        # Assumes this script is in a subdirectory of the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir and os.path.isdir(default_dir) else "."
    except Exception:
        # Fallback if settings file is missing or corrupt
        pass
    return os.path.join(os.path.expanduser("~"), "Downloads")

def run_epub_merge():
    """Main function to run the EPUB merging process with user prompts."""
    print("=====================================================")
    print("=             EPUB 合并工具 (Calibre 逻辑)          =")
    print("=====================================================")
    print("功能：将指定文件夹内的所有 EPUB 文件合并成一个。")

    default_path = load_default_path_from_settings()
    input_directory = input(f"\n请输入 EPUB 文件夹路径 (默认为: {default_path}): ").strip() or default_path

    if not os.path.isdir(input_directory):
        sys.exit(f"\n错误：文件夹 '{input_directory}' 不存在。")

    # Scan for all epub files first
    all_epub_files = sorted(
        [f for f in os.listdir(input_directory) if f.lower().endswith('.epub')]
    )

    if not all_epub_files:
        sys.exit(f"\n错误: 在 '{input_directory}' 中未找到任何 .epub 文件。")

    # Display the list of files to be merged before asking for the output name
    print("\n" + "="*20)
    print("发现以下 EPUB 文件，将按此顺序合并：")
    for i, filename in enumerate(all_epub_files):
        print(f"  {i+1}. {filename}")
    print("="*20)

    # Now, ask for the output filename
    output_filename_input = input("\n请输入合并后的文件名 (默认为: merged_epubs.epub): ").strip()
    if not output_filename_input:
        output_filename = "merged_epubs.epub"
    else:
        # Ensure the filename has the .epub extension
        name, ext = os.path.splitext(output_filename_input)
        output_filename = sanitize_filename(name) + '.epub'
    
    # Exclude the potential output file from the list of files to merge
    files_to_merge_names = [f for f in all_epub_files if f != output_filename]

    if not files_to_merge_names:
        sys.exit(f"\n错误: 没有可供合并的输入文件 (目录中仅存在输出文件或没有其他 EPUB)。")

    print(f"\n最终输出文件名为: {output_filename}")
    print("开始执行合并...")
    print("-" * 20)

    output_filepath = os.path.join(input_directory, output_filename)
    files_to_merge_paths = [os.path.join(input_directory, f) for f in files_to_merge_names]
    
    try:
        import six
    except ImportError:
        print("\nWarning: The 'six' library is not installed. It might be required.")
        print("You can install it by running: pip install six")
        # The script might still work for Python 3 without it for basic cases
        
    do_merge_core(output_filepath, files_to_merge_paths)


if __name__ == "__main__":
    run_epub_merge()
