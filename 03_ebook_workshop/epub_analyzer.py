import os
import sys
import zipfile
import xml.etree.ElementTree as ET
import html
import argparse
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import logging
import glob

# --- 日志设置 ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class EpubAnalyzer:
    """一个用于全面分析 EPUB 文件并返回结构化数据的工具。"""

    def __init__(self, epub_path):
        if not Path(epub_path).exists():
            raise FileNotFoundError(f"文件不存在: {epub_path}")
        self.epub_path = Path(epub_path)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="epub_analyzer_"))
        self.ns = {
            'cn': 'urn:oasis:names:tc:opendocument:xmlns:container',
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'ncx': 'http://www.daisy.org/z3986/2005/ncx/'
        }

    def analyze(self) -> dict:
        """
        执行完整的分析流程并返回一个包含所有数据的字典。
        """
        analysis_data = {'epub_filename': self.epub_path.name}
        try:
            self._extract_epub()
            opf_path = self._find_opf_path()
            analysis_data['opf_path'] = opf_path.relative_to(self.temp_dir)
            
            self._parse_opf(opf_path, analysis_data)
            
            ncx_item = analysis_data['manifest'].get(analysis_data.get('spine_toc_id'))
            # **修复**: 使用 opf_path.parent 作为基准来构建 NCX 文件的完整路径
            if ncx_item and ncx_item['exists']:
                full_ncx_path = opf_path.parent / ncx_item['href']
                analysis_data['toc'] = self._parse_ncx(full_ncx_path)
            else:
                analysis_data['toc'] = []

            analysis_data['file_tree'] = self._get_file_tree()
            return analysis_data

        finally:
            shutil.rmtree(self.temp_dir)
            logger.info(f"临时目录 {self.temp_dir} 已为 '{self.epub_path.name}' 清理。")

    def _extract_epub(self):
        """解压 EPUB 文件到临时目录。"""
        with zipfile.ZipFile(self.epub_path, 'r') as zf:
            zf.extractall(self.temp_dir)
        logger.info(f"EPUB '{self.epub_path.name}' 已解压到: {self.temp_dir}")

    def _find_opf_path(self) -> Path:
        """解析 container.xml 找到 .opf 文件的路径。"""
        container_path = self.temp_dir / 'META-INF' / 'container.xml'
        if not container_path.exists():
            raise FileNotFoundError("META-INF/container.xml 未找到。")
        
        tree = ET.parse(container_path)
        rootfile = tree.find('.//cn:rootfile', self.ns)
        if rootfile is None or not rootfile.get('full-path'):
            raise ValueError("在 container.xml 中无法找到 rootfile。")
        
        return self.temp_dir / rootfile.get('full-path')

    def _parse_opf(self, opf_path: Path, analysis_data: dict):
        """解析 OPF 文件。"""
        tree = ET.parse(opf_path)
        
        # Metadata
        metadata = {}
        for elem in tree.findall('.//dc:*', self.ns):
            tag = elem.tag.split('}')[-1]
            metadata[f"dc:{tag}"] = elem.text if elem.text else ""
        analysis_data['metadata'] = metadata

        # Manifest
        manifest = {}
        opf_dir = opf_path.parent
        for item in tree.findall('.//opf:item', self.ns):
            item_id = item.get('id')
            href = item.get('href', '')
            media_type = item.get('media-type', '')
            file_path = opf_dir / href
            manifest[item_id] = {
                'href': href,
                'media_type': media_type,
                'exists': file_path.exists()
            }
        analysis_data['manifest'] = manifest

        # Spine
        spine = []
        spine_node = tree.find('.//opf:spine', self.ns)
        analysis_data['spine_toc_id'] = spine_node.get('toc') if spine_node is not None else None
        for itemref in spine_node.findall('.//opf:itemref', self.ns):
            spine.append(itemref.get('idref'))
        analysis_data['spine'] = spine

    def _parse_ncx(self, ncx_path: Path) -> list:
        """解析 NCX 文件以获取目录结构，返回字典列表。"""
        def parse_navpoint(element):
            nav_label = element.find('ncx:navLabel/ncx:text', self.ns)
            content = element.find('ncx:content', self.ns)
            
            point_data = {
                'text': nav_label.text if nav_label is not None else "无标题",
                'src': content.get('src', '#') if content is not None else '#',
                'children': []
            }

            sub_points = element.findall('ncx:navPoint', self.ns)
            for sub_point in sub_points:
                point_data['children'].append(parse_navpoint(sub_point))
            return point_data

        tree = ET.parse(ncx_path)
        nav_map = tree.find('.//ncx:navMap', self.ns)
        toc_data = []
        if nav_map is not None:
            for nav_point in nav_map.findall('ncx:navPoint', self.ns):
                toc_data.append(parse_navpoint(nav_point))
        return toc_data

    def _get_file_tree(self) -> list:
        """生成物理文件结构的列表。"""
        def build_tree(dir_path: Path):
            tree_list = []
            items = sorted(list(dir_path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
            for item in items:
                if item.is_dir():
                    tree_list.append({'name': item.name, 'type': 'folder', 'children': build_tree(item)})
                else:
                    tree_list.append({'name': item.name, 'type': 'file'})
            return tree_list
        return build_tree(self.temp_dir)

def generate_markdown_report(all_analysis_data: list, output_path: Path):
    """根据分析数据列表生成一个统一的 Markdown 报告。"""
    md = f"# EPUB 分析报告\n\n"
    md += f"**报告生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += f"本次共分析了 **{len(all_analysis_data)}** 个 EPUB 文件。\n\n"

    for data in all_analysis_data:
        md += f"---\n\n"
        md += f"## 📖 文件名: `{data['epub_filename']}`\n\n"

        # Metadata
        md += "### 一、元数据 (Metadata)\n\n"
        md += "| 项目 | 内容 |\n"
        md += "| :--- | :--- |\n"
        for k, v in data.get('metadata', {}).items():
            md += f"| `{k}` | {v} |\n"
        md += "\n"

        # Manifest
        md += "### 二、文件清单 (Manifest)\n\n"
        md += "| ID | 路径 (href) | 媒体类型 | 文件状态 |\n"
        md += "| :--- | :--- | :--- | :--- |\n"
        for item_id, info in data.get('manifest', {}).items():
            status = "✅ 存在" if info['exists'] else "❌ **缺失**"
            md += f"| `{item_id}` | `{info['href']}` | `{info['media_type']}` | {status} |\n"
        md += "\n"

        # Spine
        md += "### 三、阅读顺序 (Spine)\n\n"
        for i, idref in enumerate(data.get('spine', [])):
            href = data.get('manifest', {}).get(idref, {}).get('href', '未知')
            md += f"{i+1}. `{idref}` -> `{href}`\n"
        md += "\n"

        # TOC
        md += "### 四、目录结构 (Table of Contents - NCX)\n\n"
        def format_toc(toc_list, level=0):
            toc_md = ""
            for item in toc_list:
                indent = "  " * level
                src_file, _, src_anchor = item['src'].partition('#')
                anchor_part = f" -> `#{src_anchor}`" if src_anchor else ""
                toc_md += f"{indent}- {item['text']} (`{src_file}`{anchor_part})\n"
                if item['children']:
                    toc_md += format_toc(item['children'], level + 1)
            return toc_md
        toc_content = format_toc(data.get('toc', []))
        md += toc_content if toc_content else "未找到或无法解析目录。\n"
        md += "\n"

        # File Tree
        md += "### 五、物理文件结构\n\n"
        def format_tree(tree_list, level=0):
            tree_md = ""
            for item in tree_list:
                indent = "  " * level
                icon = "📁" if item['type'] == 'folder' else "📄"
                tree_md += f"{indent}- {icon} `{item['name']}`\n"
                if 'children' in item:
                    tree_md += format_tree(item['children'], level + 1)
            return tree_md
        md += "```\n"
        md += format_tree(data.get('file_tree', []))
        md += "```\n\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"\n✅ 分析报告已生成: {output_path}")

def main():
    """脚本主入口。"""
    parser = argparse.ArgumentParser(description="分析指定目录下的所有 EPUB 文件并生成一份统一的 Markdown 报告。")
    parser.add_argument("target_dir", nargs='?', default='', help="包含 EPUB 文件的文件夹路径 (可选)。")
    
    args = parser.parse_args()
    target_dir_str = args.target_dir

    if not target_dir_str:
        # **修复**: 设置用户指定的默认路径
        default_path = "/Users/doudouda/Downloads/2/"
        prompt = f"请输入要分析的文件夹路径 (直接按 Enter 键将使用: {default_path}): "
        target_dir_str = input(prompt).strip()
        if not target_dir_str:
            target_dir_str = default_path

    target_path = Path(target_dir_str)
    if not target_path.is_dir():
        print(f"错误: 路径 '{target_path}' 不是一个有效的文件夹。", file=sys.stderr)
        sys.exit(1)

    epub_files = glob.glob(os.path.join(target_dir_str, '*.epub'))
    if not epub_files:
        print(f"在 '{target_dir_str}' 中没有找到任何 .epub 文件。")
        sys.exit(0)
    
    print(f"[*] 在目录中发现 {len(epub_files)} 个 EPUB 文件，开始分析...")
    
    all_analysis_data = []
    for epub_file in epub_files:
        try:
            print(f"  -> 正在分析: {os.path.basename(epub_file)}")
            analyzer = EpubAnalyzer(epub_file)
            analysis_data = analyzer.analyze()
            all_analysis_data.append(analysis_data)
        except Exception as e:
            print(f"    ❌ 分析文件 '{os.path.basename(epub_file)}' 时出错: {e}")
            logger.error(f"分析文件 '{epub_file}' 时出错。", exc_info=True)
    
    if all_analysis_data:
        report_path = target_path / "_EPUB_Analysis_Report.md"
        generate_markdown_report(all_analysis_data, report_path)

if __name__ == '__main__':
    main()
