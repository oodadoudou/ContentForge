import os
import re
import sys
import subprocess
import xml.etree.ElementTree as ET
from ebooklib import epub
import json
import platform

NAMESPACES = {
    'container': 'urn:oasis:names:tc:opendocument:xmlns:container',
    'opf': 'http://www.idpf.org/2007/opf',
}
ET.register_namespace('', NAMESPACES['opf'])


def print_progress_bar(iteration, total, prefix='进度', suffix='完成', length=50, fill='█'):
    """打印进度条的辅助函数。"""
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

# 阅读器类型配置
READER_TYPES = {
    "1": {
        "name": "静读天下",
        "description": "专为静读天下阅读器优化的样式",
        "css_dir": "Moonreader",
        "preview_file": "moonreader_preview.html"
    },
    "2": {
        "name": "其他阅读器",
        "description": "适用于大多数EPUB阅读器的通用样式",
        "css_dir": "basic",
        "preview_file": "epub_styles_preview.html"
    }
}

# 静读天下样式配置
MOONREADER_STYLE_OPTIONS = {
    "1": {
        "name": "灰度层次样式",
        "description": "灰度配色方案，层次分明，适合专业文档",
        "file": "moonreader_epub_style_grayscale.css"
    },
    "2": {
        "name": "线条层次样式",
        "description": "线条层次设计，清晰结构，适合教育类书籍",
        "file": "moonreader_epub_style_line_hierarchy.css"
    },
    "3": {
        "name": "线性极简样式",
        "description": "线性极简设计，现代风格，适合商务文档",
        "file": "moonreader_epub_style_linear.css"
    },
    "4": {
        "name": "简约网格样式",
        "description": "网格布局设计，简约风格，适合技术手册",
        "file": "moonreader_epub_style_minimal_grid.css"
    },
    "5": {
        "name": "极简线性样式",
        "description": "线性设计，极简风格，适合技术文档",
        "file": "moonreader_epub_style_minimal_linear.css"
    },
    "6": {
        "name": "现代极简样式",
        "description": "现代极简设计，简洁大方，适合现代文学",
        "file": "moonreader_epub_style_minimal_modern.css"
    },
    "7": {
        "name": "简洁现代样式",
        "description": "极简设计，适合商务文档和学术论文",
        "file": "moonreader_epub_style_minimal.css"
    },
    "8": {
        "name": "现代清新样式",
        "description": "左对齐标题，现代感强，适合技术文档和现代文学",
        "file": "moonreader_epub_style_modern.css"
    },
    "9": {
        "name": "单色极简样式",
        "description": "单色设计，极简风格，适合现代阅读体验",
        "file": "moonreader_epub_style_monochrome.css"
    },
    "10": {
        "name": "柔和圆润样式",
        "description": "圆润设计，柔和视觉效果，适合休闲阅读",
        "file": "moonreader_epub_style_soft.css"
    },
    "11": {
        "name": "结构化简约样式",
        "description": "结构化设计，简约风格，适合学术研究",
        "file": "moonreader_epub_style_structured_minimal.css"
    },
    "12": {
        "name": "温馨护眼样式",
        "description": "温暖色调，舒适行距，减少眼部疲劳，适合长时间阅读",
        "file": "moonreader_epub_style_warm.css"
    }
}

# 通用阅读器样式配置
BASIC_STYLE_OPTIONS = {
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
        "name": "简约网格样式",
        "description": "网格布局设计，简约风格，适合技术手册",
        "file": "epub_style_minimal_grid.css"
    },
    "16": {
        "name": "几何框架样式",
        "description": "几何框架设计，现代感强，适合设计类书籍",
        "file": "epub_style_geometric_frame.css"
    },
    "17": {
        "name": "奇幻冒险样式",
        "description": "充满想象力的设计，适合奇幻小说和冒险故事",
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

def select_reader_type():
    """选择阅读器类型"""
    print("\n" + "="*60)
    print("📱 选择阅读器类型")
    print("="*60)
    
    # 显示阅读器类型选项
    for key, reader in READER_TYPES.items():
        print(f"{key}. {reader['name']}")
        print(f"   {reader['description']}")
        print()
    
    while True:
        try:
            choice = input("请选择阅读器类型 (默认选择1): ").strip()
            if not choice:
                choice = "1"  # 默认选择静读天下
            
            if choice in READER_TYPES:
                return choice, READER_TYPES[choice]
            else:
                print("❌ 无效的选择，请重新选择")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ 输入无效，请重新选择")

def select_epub_style(reader_type_info):
    """让用户选择EPUB样式"""
    print("\n" + "="*60)
    print(f"📚 {reader_type_info['name']} - 选择电子书样式")
    print("="*60)
    
    # 根据阅读器类型选择样式配置
    if reader_type_info['css_dir'] == 'Moonreader':
        style_options = MOONREADER_STYLE_OPTIONS
    else:
        style_options = BASIC_STYLE_OPTIONS
    
    print("\n🎨 可用样式:")
    
    # 分组显示，每行显示2个样式
    items = list(style_options.items())
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
        max_choice = len(style_options)
        choice = input(f"请选择样式 (1-{max_choice}，默认为1，p=预览): ").strip().lower()
        if not choice:
            choice = "1"
        
        # 处理预览请求
        if choice in ['p', 'preview']:
            open_style_preview(reader_type_info)
            print("\n🎨 可用样式:")
            # 分组显示，每行显示2个样式
            items = list(style_options.items())
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
        
        if choice in style_options:
            selected_style = style_options[choice]
            print(f"\n✅ 已选择样式: {selected_style['name']}")
            return choice
        else:
            print(f"❌ 无效选择，请输入1-{max_choice}之间的数字，或输入 'p' 查看预览")

def open_style_preview(reader_type_info):
    """打开样式预览页面"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        preview_path = os.path.join(project_root, 'shared_assets', reader_type_info['preview_file'])
        
        if not os.path.exists(preview_path):
            print(f"⚠️  预览文件不存在: {preview_path}")
            return
        
        print(f"🌐 正在打开样式预览页面...")
        
        # 根据操作系统选择合适的打开命令
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

def load_style_content(style_filename, reader_type_info):
    """加载样式文件内容"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        style_path = os.path.join(project_root, 'shared_assets', 'epub_css', reader_type_info['css_dir'], style_filename)
        
        if not os.path.exists(style_path):
            print(f"⚠️  样式文件不存在: {style_path}")
            return None
            
        with open(style_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ 加载样式文件失败: {e}")
        return None

def scan_directory(work_dir):
    """扫描目录，查找 TXT, 封面图片和 CSS 文件。"""
    txt_files, cover_image_path, css_content = [], None, None
    selected_style_key = None
    reader_type_info = None
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
                selected_style_key = 'custom'
            except Exception as e:
                print(f"  [警告] 读取CSS文件 '{filename}' 失败: {e}。将使用样式选择器。")
    
    # 如果没有找到用户自定义CSS，让用户选择样式
    if css_content is None:
        print("  [提示] 未在工作目录中找到CSS文件，请选择内置样式...")
        
        # 选择阅读器类型
        reader_type_key, reader_type_info = select_reader_type()
        
        # 选择样式
        selected_style_key = select_epub_style(reader_type_info)
        
        if selected_style_key is None:
            print(f"\n[用户取消] 用户取消了样式选择，程序退出")
            sys.exit(0)
        
        # 根据阅读器类型获取样式配置
        if reader_type_info['css_dir'] == 'Moonreader':
            style_options = MOONREADER_STYLE_OPTIONS
        else:
            style_options = BASIC_STYLE_OPTIONS
        
        style_filename = style_options[selected_style_key]['file']
        css_content = load_style_content(style_filename, reader_type_info)
        
        if css_content is None:
            print(f"\n[致命错误] 无法加载样式文件")
            sys.exit(1)
        else:
            style_name = style_options[selected_style_key]['name']
            print(f"  [加载样式] 成功加载样式: {style_name}")
            print(f"  [继续流程] 开始生成EPUB文件...")
        
    if not txt_files:
        print("\n[错误] 在指定目录中未找到任何 .txt 文件。")
        sys.exit(1)

    return txt_files, cover_image_path, css_content, selected_style_key, reader_type_info

def get_toc_rules():
    """向用户询问并获取提取目录的正则表达式规则。"""
    print("\n--- 步骤 1: 定义目录规则 ---")
    use_default = input("是否使用默认规则提取目录? ('#' 代表一级, '##' 代表二级) (按回车确认, 输入n修改): ").lower()
    
    if use_default != 'n':
        return r'^[\s　]*#\s*(.*)', r'^[\s　]*##\s*(.*)'
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

def create_epub(txt_path, final_toc, css_content, cover_path, l1_regex, l2_regex, output_dir, selected_style_key, reader_type_info):
    """核心函数：创建 EPUB 文件。"""
    default_book_name = os.path.splitext(os.path.basename(txt_path))[0]
    print(f"\n--- 步骤 3: 确认电子书标题 ---")
    new_title = input(f"请输入电子书标题 (默认为: '{default_book_name}'): ").strip()
    book_name = new_title if new_title else default_book_name
    print(f"[LOG] 电子书标题将设为: '{book_name}'")
    print("\n--- 步骤 4: 正在生成 EPUB 文件... ---")
    
    # 确定CSS文件名
    if selected_style_key == 'custom':
        css_filename = "style/custom.css"
    else:
        # 根据阅读器类型获取样式配置
        if reader_type_info and reader_type_info['css_dir'] == 'Moonreader':
            style_options = MOONREADER_STYLE_OPTIONS
        else:
            style_options = BASIC_STYLE_OPTIONS
        
        style_file = style_options[selected_style_key]['file']
        css_filename = f"style/{style_file}"
    
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
        html_content = text_to_html(full_text)
        chapter_item.content = f'''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>{book_name}</title>
<link rel="stylesheet" type="text/css" href="{css_filename}"/>
</head>
<body>
{html_content}
</body>
</html>'''
        # 确保CSS样式表被链接到章节中
        chapter_item.add_link(href=css_filename, rel="stylesheet", type="text/css")
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
            chapter_content = f'<h{heading_info["level"]} class="titlel{heading_info["level"]}std">{heading_info["title"]}</h{heading_info["level"]}>' + '\n' + html_content
            chapter_item.content = f'''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>{heading_info["title"]}</title>
<link rel="stylesheet" type="text/css" href="{css_filename}"/>
</head>
<body>
{chapter_content}
</body>
</html>'''
            # 确保CSS样式表被链接到章节中
            chapter_item.add_link(href=css_filename, rel="stylesheet", type="text/css")
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
    
    style_item = epub.EpubItem(uid="style_default", file_name=css_filename, media_type="text/css", content=css_content)
    book.add_item(style_item)
    
    book.toc = epub_toc
    book.add_item(epub.EpubNcx())
    
    # 先添加所有章节到书籍中
    for chap in chapters:
        book.add_item(chap)
    
    # 设置spine（阅读顺序）
    book.spine = chapters
    if cover_path:
        book.spine.insert(0, 'cover')

    try:
        epub.write_epub(output_path, book, {})
        print(f"\n[成功] EPUB 文件已保存到: {output_path}")

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
    
    txt_files_list, cover_image, css_data, style_key, reader_info = scan_directory(work_directory)
    
    print(f"\n在目录中总共找到了 {len(txt_files_list)} 个 TXT 文件，将逐一处理。")
    print("-" * 60)
    
    for i, current_txt_file in enumerate(txt_files_list):
        print(f"\n>>> 开始处理第 {i+1}/{len(txt_files_list)} 个文件: {os.path.basename(current_txt_file)}")
        
        l1_regex, l2_regex = get_toc_rules()
        final_toc_list = confirm_and_edit_toc(current_txt_file, l1_regex, l2_regex)
        
        if final_toc_list is None:
            print("因读取文件失败，跳过此文件。")
            continue
            
        create_epub(current_txt_file, final_toc_list, css_data, cover_image, l1_regex, l2_regex, output_dir, style_key, reader_info)
        print("-" * 60)

    print("\n所有任务已完成！")