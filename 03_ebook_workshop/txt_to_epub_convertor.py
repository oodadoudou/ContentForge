import os
import re
import sys
import zipfile
import subprocess
import xml.etree.ElementTree as ET
import shutil
from ebooklib import epub
import json


# 注册 EPUB 相关的 XML 命名空间，以便正确解析
NAMESPACES = {
    'container': 'urn:oasis:names:tc:opendocument:xmlns:container',
    'opf': 'http://www.idpf.org/2007/opf',
}
ET.register_namespace('', NAMESPACES['opf'])

def remove_epub_navigation(epub_path):
    """
    直接修改给定的 EPUB 文件，移除其导航文件 (nav.xhtml)，以优化超长目录。
    这是一个破坏性操作，会直接修改传入路径的文件。

    Args:
        epub_path (str): 要处理的 EPUB 文件的路径。

    Returns:
        bool: 如果处理成功则返回 True，否则返回 False。
    """
    print(f"  [LOG] 开始优化 EPUB: {os.path.basename(epub_path)}")
    # 创建一个临时备份文件名
    backup_path = epub_path + ".backup"
    temp_epub_path = epub_path + ".tmp"
    try:
        # 使用 shutil 复制文件进行备份，比重命名更安全
        shutil.copy2(epub_path, backup_path)

        # 直接在原文件上进行操作
        with zipfile.ZipFile(backup_path, 'r') as zin:
            # --- 步骤 1: 找到 OPF 清单文件的路径 ---
            container_data = zin.read('META-INF/container.xml')
            container_root = ET.fromstring(container_data)
            rootfile_element = container_root.find('container:rootfiles/container:rootfile', NAMESPACES)
            if rootfile_element is None:
                raise ValueError("在 META-INF/container.xml 中找不到 rootfile 元素。")
            opf_path = rootfile_element.get('full-path')

            # --- 步骤 2: 读取并修改 OPF 清单文件 ---
            opf_content = zin.read(opf_path)
            opf_root = ET.fromstring(opf_content)
            manifest = opf_root.find('opf:manifest', NAMESPACES)
            nav_item = manifest.find("opf:item[@properties='nav']", NAMESPACES)

            if nav_item is None:
                print(f"  [警告] 在清单中未找到导航文件条目，无需移除。")
                return True # 无需操作也视为成功

            nav_full_path = os.path.normpath(os.path.join(os.path.dirname(opf_path), nav_item.get('href')))
            manifest.remove(nav_item)
            print(f"  [LOG] 已从清单中移除 '{nav_full_path}' 的条目。")
            modified_opf_bytes = ET.tostring(opf_root, encoding='utf-8', xml_declaration=True)

            # --- 步骤 3: 创建不含导航的新 EPUB 文件 ---
            with zipfile.ZipFile(temp_epub_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == nav_full_path:
                        continue
                    elif item.filename == opf_path:
                        zout.writestr(item.filename, modified_opf_bytes)
                    else:
                        zout.writestr(item, zin.read(item.filename))
        
        # 用修改后的临时文件覆盖原始文件
        os.replace(temp_epub_path, epub_path)
        print(f"  [成功] 已从 {os.path.basename(epub_path)} 中移除导航文件。")
        return True

    except Exception as e:
        print(f"  [错误] 移除导航文件时出错: {e}")
        # 如果出错，从备份恢复
        if os.path.exists(backup_path):
            os.replace(backup_path, epub_path)
        return False
    finally:
        # 无论成功与否，都删除备份文件
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(temp_epub_path):
            os.remove(temp_epub_path)

def print_progress_bar(iteration, total, prefix='进度', suffix='完成', length=50, fill='█'):
    """打印进度条的辅助函数。"""
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

# 样式配置
STYLE_OPTIONS = {
    "1": {
        "name": "经典简约样式",
        "description": "标准电子书排版，适合大多数小说和文学作品",
        "file": "epub_style_classic.css"
    },
    "2": {
        "name": "温馨护眼样式",
        "description": "温暖色调，舒适行距，减少眼部疲劳，适合长时间阅读",
        "file": "epub_style_warm.css"
    },
    "3": {
        "name": "现代清新样式",
        "description": "左对齐标题，现代感强，适合技术文档和现代文学",
        "file": "epub_style_modern.css"
    },
    "4": {
        "name": "优雅古典样式",
        "description": "古典风格，适合古典文学、诗词和传统文化类书籍",
        "file": "epub_style_elegant.css"
    },
    "5": {
        "name": "简洁现代样式",
        "description": "极简设计，适合商务文档和学术论文",
        "file": "epub_style_minimal.css"
    },
    "6": {
        "name": "灰度层次样式",
        "description": "灰度配色方案，层次分明，适合专业文档",
        "file": "epub_style_grayscale.css"
    },
    "7": {
        "name": "单色极简样式",
        "description": "单色设计，极简风格，适合现代阅读体验",
        "file": "epub_style_monochrome.css"
    },
    "8": {
        "name": "护眼低对比样式",
        "description": "低对比度设计，保护视力，适合长时间阅读",
        "file": "epub_style_eyecare.css"
    },
    "9": {
        "name": "高对比度样式",
        "description": "高对比度设计，清晰易读，适合视力不佳的读者",
        "file": "epub_style_contrast.css"
    },
    "10": {
        "name": "柔和圆润样式",
        "description": "圆润设计，柔和视觉效果，适合休闲阅读",
        "file": "epub_style_soft.css"
    },
    "11": {
        "name": "现代极简样式",
        "description": "现代极简设计，简洁大方，适合现代文学",
        "file": "epub_style_minimal_modern.css"
    },
    "12": {
        "name": "黑白简约样式",
        "description": "黑白配色，简约设计，适合经典文学作品",
        "file": "epub_style_clean.css"
    },
    "13": {
        "name": "几何极简样式",
        "description": "几何元素，极简设计，适合现代艺术类书籍",
        "file": "epub_style_geometric.css"
    },
    "14": {
        "name": "极简线性样式",
        "description": "线性设计，极简风格，适合技术文档",
        "file": "epub_style_minimal_linear.css"
    },
    "15": {
        "name": "纯净极简样式",
        "description": "纯净设计，极简风格，适合学术论文",
        "file": "epub_style_minimal_grid.css"
    },
    "16": {
        "name": "几何框架样式",
        "description": "几何框架设计，现代感强，适合设计类书籍",
        "file": "epub_style_geometric_frame.css"
    },
    "17": {
        "name": "简约网格样式",
        "description": "网格布局，简约设计，适合技术手册",
        "file": "epub_style_fantasy.css"
    },
    "18": {
        "name": "线条层次样式",
        "description": "线条层次设计，清晰结构，适合教育类书籍",
        "file": "epub_style_line_hierarchy.css"
    },
    "19": {
        "name": "线性极简样式",
        "description": "线性极简设计，现代风格，适合商务文档",
        "file": "epub_style_linear.css"
    },
    "20": {
        "name": "结构化简约样式",
        "description": "结构化设计，简约风格，适合学术研究",
        "file": "epub_style_structured_minimal.css"
    }
}

def select_epub_style():
    """让用户选择EPUB样式"""
    print("\n" + "="*60)
    print("📚 选择电子书样式")
    print("="*60)
    print("\n🎨 可用样式:")
    
    # 分组显示，每行显示2个样式
    items = list(STYLE_OPTIONS.items())
    for i in range(0, len(items), 2):
        line = ""
        for j in range(2):
            if i + j < len(items):
                key, style = items[i + j]
                line += f"{key:>2}. {style['name']:<20}"
                if j == 0 and i + j + 1 < len(items):  # 不是最后一个且不是行末
                    line += "  "
        print(line)
    
    print("\n💡 提示: 输入 'p' 预览所有样式")
    
    while True:
        choice = input("请选择样式 (1-20，默认为1，p=预览): ").strip().lower()
        if not choice:
            choice = "1"
        
        # 处理预览请求
        if choice in ['p', 'preview']:
            open_style_preview()
            print("\n🎨 可用样式:")
            # 分组显示，每行显示2个样式
            items = list(STYLE_OPTIONS.items())
            for i in range(0, len(items), 2):
                line = ""
                for j in range(2):
                    if i + j < len(items):
                        key, style = items[i + j]
                        line += f"{key:>2}. {style['name']:<20}"
                        if j == 0 and i + j + 1 < len(items):  # 不是最后一个且不是行末
                            line += "  "
                print(line)
            print()
            continue
        
        if choice in STYLE_OPTIONS:
            selected_style = STYLE_OPTIONS[choice]
            print(f"\n✅ 已选择样式: {selected_style['name']}")
            return selected_style['file']
        else:
            print("❌ 无效选择，请输入1-20之间的数字，或输入 'p' 查看预览")

def open_style_preview():
    """打开样式预览页面"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        preview_path = os.path.join(project_root, 'shared_assets', 'epub_styles_preview.html')
        
        if not os.path.exists(preview_path):
            print(f"⚠️  预览文件不存在: {preview_path}")
            return
        
        print(f"🌐 正在打开样式预览页面...")
        
        # 根据操作系统选择合适的打开命令
        import platform
        system = platform.system()
        
        if system == "Darwin":  # macOS
            subprocess.run(["open", preview_path])
        elif system == "Windows":
            subprocess.run(["start", preview_path], shell=True)
        else:  # Linux
            subprocess.run(["xdg-open", preview_path])
            
        print(f"✅ 样式预览已在浏览器中打开")
        print(f"📁 预览文件位置: {preview_path}")
        
    except Exception as e:
        print(f"❌ 打开预览失败: {e}")
        print("💡 您可以手动打开项目根目录下的 'epub_styles_preview.html' 文件")

def load_style_content(style_filename):
    """加载指定的样式文件内容"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    style_path = os.path.join(project_root, 'shared_assets', 'epub_css', style_filename)
    
    try:
        with open(style_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"⚠️  加载样式文件失败: {e}")
        print("正在尝试加载默认样式...")
        
        # 回退到默认样式
        try:
            default_css_path = os.path.join(project_root, 'shared_assets', "new_style.css")
            with open(default_css_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e2:
            print(f"❌ 加载默认样式也失败: {e2}")
            return None

def scan_directory(work_dir):
    """扫描目录，查找 TXT, 封面图片和 CSS 文件。"""
    txt_files, cover_image_path, css_content = [], None, None
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']
    
    print("\n--- 正在扫描工作目录 ---")
    for filename in sorted(os.listdir(work_dir)):
        full_path = os.path.join(work_dir, filename)
        if not os.path.isfile(full_path): continue

        if filename.lower().endswith('.txt'):
            txt_files.append(full_path)
            
        if not cover_image_path and any(filename.lower().endswith(ext) for ext in image_extensions):
            cover_image_path = full_path
            print(f"  [发现封面] 将使用 '{filename}' 作为封面。")

        if css_content is None and filename.lower().endswith('.css'):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    css_content = f.read()
                print(f"  [加载样式] 成功加载用户目录中的样式文件: '{filename}'。")
            except Exception as e:
                print(f"  [警告] 读取CSS文件 '{filename}' 失败: {e}。将使用样式选择器。")
    
    # 如果没有找到用户自定义CSS，让用户选择样式
    if css_content is None:
        print("  [提示] 未在工作目录中找到CSS文件，请选择内置样式...")
        selected_style_file = select_epub_style()
        css_content = load_style_content(selected_style_file)
        
        if css_content is None:
            print(f"\n[致命错误] 无法加载任何样式文件")
            sys.exit(1)
        else:
            print(f"  [加载样式] 成功加载样式: {selected_style_file}")
        
    if not txt_files:
        print("\n[错误] 在指定目录中未找到任何 .txt 文件。")
        sys.exit(1)

    return txt_files, cover_image_path, css_content

def get_toc_rules():
    """向用户询问并获取提取目录的正则表达式规则。"""
    print("\n--- 步骤 1: 定义目录规则 ---")
    use_default = input("是否使用默认规则提取目录? ('#' 代表一级, '##' 代表二级) (按回车确认, 输入n修改): ").lower()
    
    if use_default != 'n':
        return r'^#\s*(.*)', r'^##\s*(.*)'
    else:
        level1_regex = input("请输入一级目录的正则表达式 (例如: ^第.*?章): ").strip()
        level2_regex = input(r"请输入二级目录的正则表达式 (例如: ^\d+\.\d+): ").strip()
        if not level1_regex:
            print("[错误] 一级目录的正则表达式不能为空。")
            sys.exit(1)
        return level1_regex, level2_regex

def extract_toc_from_text(txt_path, level1_regex, level2_regex):
    """根据正则表达式从TXT文件中提取目录结构。"""
    toc = []
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if level2_regex:
                    match_l2 = re.match(level2_regex, line)
                    if match_l2:
                        toc.append((match_l2.group(1).strip(), 2))
                        continue
                match_l1 = re.match(level1_regex, line)
                if match_l1:
                    toc.append((match_l1.group(1).strip(), 1))
    except Exception as e:
        print(f"\n[错误] 读取或解析TXT文件 '{txt_path}' 时出错: {e}")
        return None
    return toc

def print_toc_for_confirmation(toc):
    """友好地打印出目录结构供用户确认。"""
    print("\n" + "="*50)
    print(f"已识别出 {len(toc)} 项目录结构，请检查:")
    print("="*50)
    if not toc:
        print("(未识别到任何目录)")
    for title, level in toc:
        if level == 1:
            print(f"- {title}")
        else:
            print(f"    - {title}")
    print("="*50)

def confirm_and_edit_toc(current_txt_file, l1_regex, l2_regex):
    """让用户确认目录，如果用户选择否则提供交互式修改功能。"""
    print("\n--- 步骤 2: 确认与修改目录 ---")
    
    toc = extract_toc_from_text(current_txt_file, l1_regex, l2_regex)
    if toc is None: return None

    while True:
        print_toc_for_confirmation(toc)
        is_correct = input("以上目录是否正确? (按回车确认, 输入n修改): ").lower()
        if is_correct != 'n':
            return toc
        
        print("\n请按以下格式复制、修改并粘贴新的目录结构。")
        print("格式说明: \n  - 一级目录: `- 标题`\n  - 二级目录: `    - 标题`")
        print("完成编辑后，粘贴到此处，然后按两次回车键结束输入。")
        
        lines = []
        while True:
            try:
                line = input()
                if not line: break
                lines.append(line)
            except EOFError: break
        
        new_toc = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith('- '):
                title = line_stripped[2:].strip()
                # 检查原始行是否以4个空格开头（二级目录）
                if line.startswith('    - '):
                    new_toc.append((title, 2))
                else:
                    new_toc.append((title, 1))
        toc = new_toc

def text_to_html(text):
    """将纯文本转换为简单的 HTML，段落用 <p> 包裹。"""
    if not text or not text.strip(): return ""
    paragraphs = re.split(r'\n\s*\n', text.strip())
    html_paragraphs = [f'<p>{p.replace(os.linesep, "<br/>").strip()}</p>' for p in paragraphs if p.strip()]
    return '\n'.join(html_paragraphs)

def create_epub(txt_path, final_toc, css_content, cover_path, l1_regex, l2_regex, output_dir):
    """核心函数：创建 EPUB 文件。"""
    default_book_name = os.path.splitext(os.path.basename(txt_path))[0]
    print(f"\n--- 步骤 3: 确认电子书标题 ---")
    new_title = input(f"请输入电子书标题 (默认为: '{default_book_name}'): ").strip()
    book_name = new_title if new_title else default_book_name
    print(f"[LOG] 电子书标题将设为: '{book_name}'")
    print("\n--- 步骤 4: 正在生成 EPUB 文件... ---")
    
    book = epub.EpubBook()
    book.set_identifier(f"id_{book_name}_{os.path.getmtime(txt_path)}")
    book.set_title(book_name)
    book.set_language('zh')
    book.add_author("未知作者")
    output_path = os.path.join(output_dir, f"{book_name}.epub")

    if cover_path:
        try:
            book.set_cover("cover.jpg", open(cover_path, 'rb').read())
            print(f"[LOG] 成功添加封面: '{os.path.basename(cover_path)}'")
        except Exception as e: print(f"[警告] 添加封面失败: {e}")

    with open(txt_path, 'r', encoding='utf-8') as f:
        full_text = f.read()

    print("[LOG] 开始在原文中定位所有章节标题...")
    all_headings_map = []
    combined_regex_str = f"({l2_regex})|({l1_regex})" if l2_regex else f"({l1_regex})"
    pattern = re.compile(combined_regex_str, re.MULTILINE)

    for match in pattern.finditer(full_text):
        title, level = None, None
        if l2_regex and match.group(1):
            title = match.group(2).strip()
            level = 2
        elif match.group(3):
            title = match.group(4).strip()
            level = 1
        
        if title is not None and any(toc_title == title for toc_title, toc_level in final_toc if toc_level == level):
            all_headings_map.append({'title': title, 'level': level, 'start': match.start(), 'end': match.end()})
            
    print(f"[LOG] 定位完成，共找到 {len(all_headings_map)} 个有效标题。")
    
    chapters = []
    chapter_map = []

    if not all_headings_map:
        chapter_item = epub.EpubHtml(title=book_name, file_name='chap_0.xhtml', lang='zh')
        chapter_item.content = text_to_html(full_text)
        chapters.append(chapter_item)
    else:
        total_headings = len(all_headings_map)
        print_progress_bar(0, total_headings, prefix='[PROGRESS] 创建章节文件:', suffix='完成')

        for i, heading_info in enumerate(all_headings_map):
            content_start = heading_info['end']
            content_end = all_headings_map[i + 1]['start'] if i + 1 < len(all_headings_map) else len(full_text)
            raw_content = full_text[content_start:content_end].strip()
            html_content = text_to_html(raw_content)
            
            filename = f'chap_{i}.xhtml'
            chapter_item = epub.EpubHtml(title=heading_info['title'], file_name=filename, lang='zh')
            chapter_item.content = f'<h{heading_info["level"]} class="titlel{heading_info["level"]}std">{heading_info["title"]}</h{heading_info["level"]}>\n{html_content}'
            chapters.append(chapter_item)
            chapter_map.append({'title': heading_info['title'], 'level': heading_info['level'], 'filename': filename})
            print_progress_bar(i + 1, total_headings, prefix='[PROGRESS] 创建章节文件:', suffix='完成')

    epub_toc = []
    l1_section = None
    for chap_info in chapter_map:
        if chap_info['level'] == 1:
            l1_link = epub.Link(chap_info['filename'], chap_info['title'], f'uid_{chap_info["filename"]}')
            l1_section = (l1_link, [])
            epub_toc.append(l1_section)
        elif chap_info['level'] == 2:
            if l1_section is None:
                l1_link = epub.Link("#", "章节", f"uid_parent_{chap_info['title']}")
                l1_section = (l1_link, [])
                epub_toc.append(l1_section)
            l2_link = epub.Link(chap_info['filename'], chap_info['title'], f'uid_{chap_info["filename"]}')
            l1_section[1].append(l2_link)
    
    style_item = epub.EpubItem(uid="style_default", file_name="style/default.css", media_type="text/css", content=css_content)
    book.add_item(style_item)
    
    book.toc = epub_toc
    book.add_item(epub.EpubNcx())
    
    # 创建自定义的导航文件，包含CSS样式引用
    nav_content = f'''<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh" xml:lang="zh">
  <head>
    <title>{book_name}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
  </head>
  <body>
    <nav epub:type="toc" id="id" role="doc-toc">
      <h2>{book_name}</h2>
      <ol>'''
    
    for item in epub_toc:
        if isinstance(item, tuple) and len(item) == 2:
            # 一级目录
            link, sub_items = item
            nav_content += f'''
        <li>
          <a href="{link.href}">{link.title}</a>'''
            if sub_items:
                nav_content += '\n          <ol>'
                for sub_link in sub_items:
                    nav_content += f'''
            <li>
              <a href="{sub_link.href}">{sub_link.title}</a>
            </li>'''
                nav_content += '\n          </ol>'
            else:
                nav_content += '\n          <ol/>'
            nav_content += '\n        </li>'
        else:
            # 单个链接
            nav_content += f'''
        <li>
          <a href="{item.href}">{item.title}</a>
          <ol/>
        </li>'''
    
    nav_content += '''
      </ol>
    </nav>
  </body>
</html>'''
    
    nav_item = epub.EpubHtml(title='Navigation', file_name='nav.xhtml', lang='zh')
    nav_item.content = nav_content
    nav_item.add_item(style_item)
    book.add_item(nav_item) 
    
    book.spine = ['nav'] + chapters
    if cover_path:
        book.spine.insert(0, 'cover')
        
    for chap in chapters:
        chap.add_item(style_item)
        book.add_item(chap)

    try:
        epub.write_epub(output_path, book, {})
        print(f"\n[成功] EPUB 文件已保存到: {output_path}")

        if len(final_toc) > 15:
            print("-" * 50)
            prompt = (f"[提示] 检测到目录超过15项 ({len(final_toc)}项)，这可能影响在某些设备上的阅读体验。\n"
                      f"是否要移除EPUB的导航文件以优化性能? (按回车确认, 输入n保留): ")
            if input(prompt).lower() != 'n':
                print("\n--- 步骤 5: 优化超长目录 ---")
                remove_epub_navigation(output_path)
            else:
                 print("  [跳过] 已根据您的选择保留导航目录。")

    except Exception as e:
        print(f"  [错误] 写入 EPUB 文件时失败: {e}")

# --- 新增：函数用于从 settings.json 加载默认路径 ---
def load_default_path_from_settings():
    """从共享设置文件中读取默认工作目录。"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        default_dir = settings.get("default_work_dir")
        return default_dir if default_dir else "."
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")

if __name__ == "__main__":
    print("="*60)
    print(" " * 18 + "TXT to EPUB 转换器")
    print("="*60)
    
    # --- 修改：动态加载默认路径并获取用户输入 ---
    default_path = load_default_path_from_settings()
    path_input = input(f"请输入TXT文件所在的目录 (默认为: {default_path}): ").strip()
    work_directory = path_input if path_input else default_path
    
    if not os.path.isdir(work_directory):
        print(f"\n[错误] 目录 '{work_directory}' 不存在。请检查路径是否正确。")
        sys.exit(1)
        
    print(f"\n工作目录设置为: {work_directory}")
    # --- 修改结束 ---
    
    output_dir = os.path.join(work_directory, "processed_files")
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[提示] 所有生成的EPUB文件将被保存在: {output_dir}")
    
    txt_files_list, cover_image, css_data = scan_directory(work_directory)
    
    print(f"\n在目录中总共找到了 {len(txt_files_list)} 个 TXT 文件，将逐一处理。")
    print("-" * 60)
    
    for i, current_txt_file in enumerate(txt_files_list):
        print(f"\n>>> 开始处理第 {i+1}/{len(txt_files_list)} 个文件: {os.path.basename(current_txt_file)}")
        
        l1_regex, l2_regex = get_toc_rules()
        final_toc_list = confirm_and_edit_toc(current_txt_file, l1_regex, l2_regex)
        
        if final_toc_list is None:
            print("因读取文件失败，跳过此文件。")
            continue
            
        create_epub(current_txt_file, final_toc_list, css_data, cover_image, l1_regex, l2_regex, output_dir)
        print("-" * 60)

    print("\n所有任务已完成！")