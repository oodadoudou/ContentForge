#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import logging
import re
import uuid
import json
import shutil
import tempfile
from posixpath import normpath
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED
from xml.dom.minidom import parseString, getDOMImplementation

# --- Compatibility & Setup ---
try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote

# --- Logging Setup ---
logger = logging.getLogger(__name__)
loghandler = logging.StreamHandler()
logformatter = logging.Formatter("%(levelname)s: %(message)s")
loghandler.setFormatter(logformatter)
if not logger.handlers:
    logger.addHandler(loghandler)
logger.setLevel(logging.INFO)

# --- Helper Functions ---
def new_tag(dom, name, attrs=None, text=None):
    """Creates a new XML element."""
    tag = dom.createElement(name)
    if attrs:
        for attr, value in attrs.items():
            tag.setAttribute(attr, value)
    if text:
        tag.appendChild(dom.createTextNode(str(text)))
    return tag

def get_path_part(path):
    """Gets the directory part of a file path."""
    return os.path.dirname(path)

def natural_sort_key(s):
    """Key for natural sorting (e.g., 'vol 2' before 'vol 10')."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', s)]

def sanitize_filename(name):
    """Removes illegal characters from a string for use as a filename."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()

def load_default_path():
    """
    从共享设置文件中读取默认工作目录，如果失败则返回用户下载文件夹。
    逻辑参考自用户提供的 epub_toolkit.py。
    """
    try:
        # 假设项目结构为 .../ProjectRoot/scripts/script.py
        # 且设置文件位于 .../ProjectRoot/shared_assets/settings.json
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            # 如果路径存在且是有效目录，则返回该路径
            if default_dir and os.path.isdir(default_dir):
                return default_dir
    except Exception as e:
        # 在 debug 模式下记录错误，但不中断程序
        logger.debug(f"读取共享设置失败: {e}")
    
    # 最终回退到用户的下载文件夹
    return os.path.join(os.path.expanduser("~"), "Downloads")

class EpubMerger:
    """
    A class that merges multiple EPUB files by unpacking them, consolidating
    their contents, and repacking them into a single, clean EPUB file.
    This approach is more robust than in-memory manipulation.
    """
    def __init__(self, input_files, output_path, title_opt=None):
        self.input_files = input_files
        self.output_path = output_path
        self.title_opt = title_opt
        self.temp_dir = tempfile.mkdtemp(prefix="epub_merge_")
        self.book_dirs = []
        self.merged_content_dir = os.path.join(self.temp_dir, "merged_OEBPS")
        os.makedirs(self.merged_content_dir, exist_ok=True)
        
        # Data accumulated from all books
        self.manifest_items = []
        self.spine_items = []
        self.toc_navpoints = []
        self.metadata = {
            "titles": [],
            "creators": set(),
            "cover_full_path": None, # Absolute path in temp dir
            "cover_href": None,      # Original href for extension
            "cover_media_type": None
        }

    def run(self):
        """Executes the entire merge process."""
        try:
            logger.info(f"创建临时工作目录: {self.temp_dir}")
            
            self._unpack_all()
            self._process_books()
            self._repack_epub()
            
            logger.info(f"🎉 合并成功! 文件保存在: {self.output_path}")

        except Exception as e:
            logger.error(f"合并过程中发生严重错误: {e}", exc_info=True)
        finally:
            logger.info("清理临时文件...")
            shutil.rmtree(self.temp_dir)

    def _unpack_all(self):
        """Unpacks each input EPUB into its own subdirectory."""
        for i, epub_path in enumerate(self.input_files):
            book_dir = os.path.join(self.temp_dir, f"book_{i+1}")
            os.makedirs(book_dir, exist_ok=True)
            self.book_dirs.append(book_dir)
            logger.info(f"解包 ({i+1}/{len(self.input_files)}): {os.path.basename(epub_path)} -> {os.path.basename(book_dir)}/")
            with ZipFile(epub_path, 'r') as zip_ref:
                zip_ref.extractall(book_dir)

    def _process_books(self):
        """Processes each unpacked book directory to gather data and copy files."""
        for i, book_dir in enumerate(self.book_dirs):
            book_num = i + 1
            logger.info(f"处理解包后的书籍 #{book_num}...")
            
            try:
                container_path = os.path.join(book_dir, "META-INF", "container.xml")
                if not os.path.exists(container_path):
                    logger.warning(f"  书籍 #{book_num} 缺少 container.xml，跳过此书。")
                    continue
                
                with open(container_path, 'rb') as f:
                    container_dom = parseString(f.read())
                
                # Use getElementsByTagNameNS to be namespace-agnostic
                rootfile_path = container_dom.getElementsByTagNameNS("*", "rootfile")[0].getAttribute("full-path")
                opf_path = os.path.join(book_dir, rootfile_path)
                opf_dir = get_path_part(opf_path)

                with open(opf_path, 'rb') as f:
                    opf_dom = parseString(f.read())

                self._gather_metadata(opf_dom, opf_dir, book_num)
                self._process_manifest(opf_dom, opf_dir, book_num)
                self._process_spine(opf_dom, book_num)
                self._process_toc(opf_dom, opf_dir, book_num)

            except Exception as e:
                logger.error(f"  处理书籍 #{book_num} 失败: {e}", exc_info=True)

    def _gather_metadata(self, opf_dom, opf_dir, book_num):
        """Gathers title, creator, and cover info from the OPF DOM."""
        try:
            title = opf_dom.getElementsByTagNameNS("*", "title")[0].firstChild.data
            self.metadata["titles"].append(title)
        except (IndexError, AttributeError):
            self.metadata["titles"].append(f"Book {book_num}")
        
        for creator_node in opf_dom.getElementsByTagNameNS("*", "creator"):
            if creator_node.firstChild:
                self.metadata["creators"].add(creator_node.firstChild.data)

        # Robust cover handling, only from the first book
        if book_num == 1:
            cover_meta = next((m for m in opf_dom.getElementsByTagNameNS("*", "meta") if m.getAttribute("name") == "cover"), None)
            if cover_meta:
                cover_id = cover_meta.getAttribute("content")
                manifest_items = opf_dom.getElementsByTagNameNS("*", "item")
                cover_item = next((i for i in manifest_items if i.getAttribute("id") == cover_id), None)
                if cover_item:
                    href = unquote(cover_item.getAttribute("href"))
                    full_src_path = os.path.join(opf_dir, href)
                    if os.path.exists(full_src_path):
                        self.metadata["cover_full_path"] = full_src_path
                        self.metadata["cover_href"] = href
                        self.metadata["cover_media_type"] = cover_item.getAttribute("media-type")
                        logger.info(f"  找到封面图片: {href}")
                    else:
                        logger.warning(f"  封面在 manifest 中声明，但文件未找到: {full_src_path}")

    def _process_manifest(self, opf_dom, opf_dir, book_num):
        """Copies files and creates new manifest entries."""
        for item in opf_dom.getElementsByTagNameNS("*", "item"):
            item_id = item.getAttribute("id")
            href_orig = unquote(item.getAttribute("href"))
            media_type = item.getAttribute("media-type")

            if media_type == "application/x-dtbncx+xml":
                continue

            src_path = os.path.join(opf_dir, href_orig)
            href_new = normpath(os.path.join(str(book_num), href_orig))
            dest_path = os.path.join(self.merged_content_dir, href_new)
            
            os.makedirs(get_path_part(dest_path), exist_ok=True)
            
            if os.path.exists(src_path):
                shutil.copy2(src_path, dest_path)
                new_id = f"b{book_num}_{item_id}"
                self.manifest_items.append({"id": new_id, "href": href_new, "media-type": media_type})
            else:
                logger.warning(f"  文件在 manifest 中声明但未找到: {src_path}")
    
    def _process_spine(self, opf_dom, book_num):
        """Gathers spine items."""
        for itemref in opf_dom.getElementsByTagNameNS("*", "itemref"):
            idref = itemref.getAttribute("idref")
            new_idref = f"b{book_num}_{idref}"
            self.spine_items.append(new_idref)

    def _process_toc(self, opf_dom, opf_dir, book_num):
        """Gathers and adapts TOC entries."""
        manifest_items = opf_dom.getElementsByTagNameNS("*", "item")
        ncx_item = next((i for i in manifest_items if i.getAttribute("media-type") == "application/x-dtbncx+xml"), None)
        
        book_title = self.metadata["titles"][-1]
        book_navpoint = {"label": book_title, "id": f"book_toc_{book_num}", "children": []}

        first_spine_id = next((s.getAttribute("idref") for s in opf_dom.getElementsByTagNameNS("*", "itemref")), None)
        if first_spine_id:
            first_item = next((i for i in manifest_items if i.getAttribute("id") == first_spine_id), None)
            if first_item:
                first_href = unquote(first_item.getAttribute("href"))
                book_navpoint["src"] = normpath(os.path.join(str(book_num), first_href))

        if not ncx_item:
            logger.warning(f"  书籍 #{book_num} 未找到 toc.ncx 声明。")
            self.toc_navpoints.append(book_navpoint)
            return

        ncx_path = os.path.join(opf_dir, unquote(ncx_item.getAttribute("href")))
        if not os.path.exists(ncx_path):
            logger.warning(f"  toc.ncx 文件在 manifest 中声明但未找到: {ncx_path}")
            self.toc_navpoints.append(book_navpoint)
            return
        
        with open(ncx_path, 'rb') as f:
            ncx_dom = parseString(f.read())
        
        ncx_dir = get_path_part(ncx_path)

        for navpoint in ncx_dom.getElementsByTagNameNS("*", "navPoint"):
            if navpoint.parentNode.tagName == "navMap":
                child = self._parse_navpoint(navpoint, book_num, ncx_dir, opf_dir)
                book_navpoint["children"].append(child)
        
        self.toc_navpoints.append(book_navpoint)

    def _parse_navpoint(self, navpoint_node, book_num, ncx_dir, opf_dir):
        """Recursively parses a navPoint XML node into a dictionary."""
        label = navpoint_node.getElementsByTagNameNS("*", "text")[0].firstChild.data
        content_node = navpoint_node.getElementsByTagNameNS("*", "content")[0]
        src_orig = unquote(content_node.getAttribute("src"))
        
        # Correctly resolve the content path relative to the OPF file
        src_abs_path = os.path.abspath(os.path.join(ncx_dir, src_orig))
        src_rel_to_opf = os.path.relpath(src_abs_path, opf_dir)
        src_new = normpath(os.path.join(str(book_num), src_rel_to_opf))
        
        nav_dict = {
            "id": f"b{book_num}_{navpoint_node.getAttribute('id')}",
            "label": label,
            "src": src_new,
            "children": []
        }
        
        for child_node in navpoint_node.childNodes:
            if child_node.nodeType == child_node.ELEMENT_NODE and child_node.tagName == "navPoint":
                nav_dict["children"].append(self._parse_navpoint(child_node, book_num, ncx_dir, opf_dir))
        
        return nav_dict

    def _repack_epub(self):
        """Builds the final OPF, NCX, and zips everything into a new EPUB."""
        logger.info("构建最终的 EPUB 文件...")
        
        if self.metadata.get("cover_full_path"):
            cover_src_path = self.metadata["cover_full_path"]
            cover_orig_href = self.metadata["cover_href"]
            cover_dest_href = "cover" + os.path.splitext(cover_orig_href)[1]
            cover_dest_path = os.path.join(self.merged_content_dir, cover_dest_href)
            shutil.copy2(cover_src_path, cover_dest_path)

            self.manifest_items.insert(0, {"id": "cover-img", "href": cover_dest_href, "media-type": self.metadata["cover_media_type"]})
            self.manifest_items.insert(1, {"id": "cover-page", "href": "cover.xhtml", "media-type": "application/xhtml+xml"})
            self.spine_items.insert(0, "cover-page")

            cover_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>Cover</title><style type="text/css">body{{margin:0;padding:0;text-align:center;}}img{{max-width:100%;max-height:100vh;}}</style></head>
<body><div><img src="{cover_dest_href}" alt="Cover"/></div></body></html>"""
            with open(os.path.join(self.merged_content_dir, "cover.xhtml"), "w", encoding="utf-8") as f:
                f.write(cover_xhtml)

        unique_id = f"urn:uuid:{uuid.uuid4()}"
        self._write_opf(unique_id)
        self._write_ncx(unique_id)

        with ZipFile(self.output_path, 'w', ZIP_DEFLATED, allowZip64=True) as zf:
            zf.writestr("mimetype", "application/epub+zip", ZIP_STORED)
            
            container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
            zf.writestr("META-INF/container.xml", container_xml)
            
            for root, _, files in os.walk(self.merged_content_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    archive_name = os.path.join("OEBPS", os.path.relpath(file_path, self.merged_content_dir))
                    zf.write(file_path, archive_name)

    def _write_opf(self, unique_id):
        """Writes the content.opf file."""
        dom = getDOMImplementation().createDocument(None, "package", None)
        package = dom.documentElement
        package.setAttribute("version", "2.0")
        package.setAttribute("xmlns", "http://www.idpf.org/2007/opf")
        package.setAttribute("unique-identifier", "bookid")

        metadata = new_tag(dom, "metadata", attrs={"xmlns:dc": "http://purl.org/dc/elements/1.1/", "xmlns:opf": "http://www.idpf.org/2007/opf"})
        package.appendChild(metadata)
        metadata.appendChild(new_tag(dom, "dc:identifier", text=unique_id, attrs={"id": "bookid"}))
        
        # Use the user-provided title if available, otherwise generate one.
        final_title = self.title_opt if self.title_opt else f"{self.metadata['titles'][0]} (Merged)"
        metadata.appendChild(new_tag(dom, "dc:title", text=final_title))

        for creator in sorted(list(self.metadata["creators"])):
            metadata.appendChild(new_tag(dom, "dc:creator", text=creator))
        if self.metadata.get("cover_full_path"):
            metadata.appendChild(new_tag(dom, "meta", attrs={"name": "cover", "content": "cover-img"}))

        manifest = new_tag(dom, "manifest")
        package.appendChild(manifest)
        manifest.appendChild(new_tag(dom, "item", attrs={"id": "ncx", "href": "toc.ncx", "media-type": "application/x-dtbncx+xml"}))
        for item in self.manifest_items:
            manifest.appendChild(new_tag(dom, "item", attrs=item))

        spine = new_tag(dom, "spine", attrs={"toc": "ncx"})
        package.appendChild(spine)
        for idref in self.spine_items:
            spine.appendChild(new_tag(dom, "itemref", attrs={"idref": idref}))

        opf_content = dom.toprettyxml(indent="  ", encoding="utf-8")
        with open(os.path.join(self.merged_content_dir, "content.opf"), "wb") as f:
            f.write(opf_content)

    def _write_ncx(self, unique_id):
        """Writes the toc.ncx file."""
        dom = getDOMImplementation().createDocument(None, "ncx", None)
        ncx = dom.documentElement
        ncx.setAttribute("version", "2.0")
        ncx.setAttribute("xmlns", "http://www.daisy.org/z3986/2005/ncx/")
        
        head = new_tag(dom, "head")
        head.appendChild(new_tag(dom, "meta", attrs={"name": "dtb:uid", "content": unique_id}))
        ncx.appendChild(head)
        
        doc_title = new_tag(dom, "docTitle")
        # Use the user-provided title here as well.
        final_title = self.title_opt if self.title_opt else f"{self.metadata['titles'][0]} (Merged)"
        doc_title.appendChild(new_tag(dom, "text", text=final_title))
        ncx.appendChild(doc_title)
        
        navmap = new_tag(dom, "navMap")
        ncx.appendChild(navmap)
        
        play_order = 1
        
        if self.metadata.get("cover_full_path"):
            cover_nav = new_tag(dom, "navPoint", attrs={"id": "nav-cover", "playOrder": str(play_order)})
            play_order += 1
            nav_label = new_tag(dom, "navLabel")
            nav_label.appendChild(new_tag(dom, "text", text="封面"))
            cover_nav.appendChild(nav_label)
            cover_nav.appendChild(new_tag(dom, "content", attrs={"src": "cover.xhtml"}))
            navmap.appendChild(cover_nav)

        def create_nav_points(parent_node, nav_dicts):
            nonlocal play_order
            for nav_dict in nav_dicts:
                navpoint = new_tag(dom, "navPoint", attrs={"id": nav_dict["id"], "playOrder": str(play_order)})
                play_order += 1
                nav_label = new_tag(dom, "navLabel")
                nav_label.appendChild(new_tag(dom, "text", text=nav_dict["label"]))
                navpoint.appendChild(nav_label)
                if nav_dict.get("src"):
                    navpoint.appendChild(new_tag(dom, "content", attrs={"src": nav_dict["src"]}))
                
                if nav_dict["children"]:
                    create_nav_points(navpoint, nav_dict["children"])
                
                parent_node.appendChild(navpoint)

        create_nav_points(navmap, self.toc_navpoints)

        ncx_content = dom.toprettyxml(indent="  ", encoding="utf-8")
        with open(os.path.join(self.merged_content_dir, "toc.ncx"), "wb") as f:
            f.write(ncx_content)

# --- UI and Execution ---
def run_epub_merge_ui():
    """Main function to run the tool with user interaction."""
    print("=========================================================")
    print("=      增强版 EPUB 合并工具 (解包-整合-打包)      =")
    print("=========================================================")
    print("功能：将指定文件夹内的所有 EPUB 文件彻底解包后重新合并。")
    print("      此方法更稳定，能更好地处理不同结构的 EPUB 文件。")

    # --- 功能更新 1: 默认开启 DEBUG 模式 ---
    logger.setLevel(logging.DEBUG)
    print("\n--- 详细日志 (DEBUG 模式) 已默认启用 ---")

    # --- 功能更新 3: 使用新的默认路径读取逻辑 ---
    default_path = load_default_path()
    input_directory = input(f"\n请输入 EPUB 文件夹路径 (默认为: {default_path}): ").strip() or default_path

    if not os.path.isdir(input_directory):
        sys.exit(f"\n错误：文件夹 '{input_directory}' 不存在。")

    all_epub_files = sorted(
        [f for f in os.listdir(input_directory) if f.lower().endswith('.epub')],
        key=natural_sort_key
    )
    
    output_filename_input = input("\n请输入新 EPUB 的文件名 (例如: 我的合集.epub): ").strip()
    output_filename = sanitize_filename(output_filename_input) if output_filename_input else "merged_epubs.epub"
    if not output_filename.lower().endswith('.epub'):
        output_filename += '.epub'
    
    # 从文件名中提取书名，用于元数据
    new_epub_title = os.path.splitext(output_filename)[0]
    
    files_to_merge_names = [f for f in all_epub_files if f != output_filename]

    if not files_to_merge_names:
        sys.exit(f"\n错误: 在 '{input_directory}' 中没有找到可供合并的 EPUB 文件。")

    # --- 功能更新 2: 交互式排序 ---
    while True:
        print("\n" + "="*80)
        print(f"  检测到以下文件，将按此顺序合并 (共 {len(files_to_merge_names)} 个):")
        print("-"*80)
        print(f"  {'序号':<4} | 文件名")
        print(f"  {'-'*4} | {'-'*73}")
        for i, filename in enumerate(files_to_merge_names, 1):
            # 直接打印完整文件名，不再截断
            print(f"  {i:<4} | {filename}")
        print("="*80)

        reorder_input = input("\n此顺序是否正确？(Y/n): ").lower().strip()
        if reorder_input == 'n':
            print("\n请输入新的顺序号，以空格分隔 (例如: 1 3 2 4)")
            new_order_str = input("> ").strip()
            try:
                # 将用户输入的序号（从1开始）转换成列表索引（从0开始）
                new_order_indices = [int(i) - 1 for i in new_order_str.split()]
                
                # 验证用户输入
                if len(new_order_indices) != len(files_to_merge_names):
                    raise ValueError("输入的序号数量与文件数量不匹配。")
                if len(set(new_order_indices)) != len(new_order_indices):
                    raise ValueError("输入的序号包含重复数字。")
                if not all(0 <= i < len(files_to_merge_names) for i in new_order_indices):
                     raise ValueError("输入的序号超出了有效范围。")
                
                # 根据用户输入的新顺序重新排列文件列表
                original_list = list(files_to_merge_names)
                files_to_merge_names = [original_list[i] for i in new_order_indices]
                
                print("\n✅ 顺序已更新。")
                # 循环将继续，并显示新的顺序供用户再次确认
            
            except ValueError as e:
                print(f"\n❌ 错误: {e} 请重试。")
                # 继续循环，让用户重新输入
        
        elif reorder_input in ('y', ''):
            print("\n顺序已确认。")
            break # 顺序正确，跳出循环
        
        else:
            print("无效输入，请输入 'y' 或 'n'。")
    
    confirm = input(f"\n即将开始合并，输出文件为 '{output_filename}'。\n确认开始吗？(Y/n): ").lower().strip()
    if confirm == 'n':
        sys.exit("操作已取消。")
        
    print("-" * 20)

    output_filepath = os.path.join(input_directory, output_filename)
    files_to_merge_paths = [os.path.join(input_directory, f) for f in files_to_merge_names]
    
    merger = EpubMerger(files_to_merge_paths, output_filepath, title_opt=new_epub_title)
    merger.run()

if __name__ == "__main__":
    run_epub_merge_ui()