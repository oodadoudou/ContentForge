import os
import re
import sys
from ebooklib import epub

# --- 默认的 CSS 样式 ---
DEFAULT_CSS = """
/* --- 全局与页面设置 --- */
@namespace epub "http://www.idpf.org/2007/ops";

@font-face {
    font-family: "ReaderFont";
    src: url(res:///system/fonts/DroidSansFallback.ttf); /* 兼容旧设备 */
}

body {
    font-family: -apple-system, "system-ui", "BlinkMacSystemFont", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", "sans-serif", "ReaderFont";
    line-height: 1.7; /* 舒适的行高 */
    margin: 3% 5%;    /* 页面边距 */
    text-align: justify; /* 两端对齐 */
    widows: 2;
    orphans: 2;
}


/* --- 段落与文本 --- */
p {
    font-size: 1em; /* 基准字体大小 */
    margin-top: 0;
    margin-bottom: 1.2em; /* 段后距 */
    text-indent: 0;     /* 首行缩进 */
}

p.no-indent {
    text-indent: 0;
}


/* --- 标题层级 --- */
h1, .titlel1std {
    font-size: 1.3em;
    font-weight: bold;
    margin-top: 3em;
    margin-bottom: 1.5em;
    line-height: 1.3;
    text-indent: 0;
    page-break-before: always; /* 每个大章都另起一页 */
    border-bottom: 1px solid #cccccc; /* 添加一条底部分隔线 */
    padding-bottom: 0.3em;
}

h2, .titlel2std {
    font-size: 1.25em;
    font-weight: bold;
    margin-top: 2.5em;
    margin-bottom: 1.2em;
    line-height: 1.4;
    text-indent: 0;
    border-bottom: 0.75px solid #cccccc; /* 添加一条底部分隔线 */
    padding-bottom: 0.3em;
}

h3, .titlel3std {
    font-size: 1.2em;
    font-weight: bold;
    margin-top: 2em;
    margin-bottom: 1em;
    line-height: 1.5;
    text-indent: 0;
}

h4, h5, h6 {
    font-size: 1.1em;
    font-weight: bold;
    margin-top: 2em;
    margin-bottom: 0.8em;
    line-height: 1.6;
    text-indent: 0;
}


/* --- 图像 --- */
div.centeredimage, .image-container {
    display: block;
    text-align: center;
    margin: 2em 0; /* 图片的垂直边距 */
    text-indent: 0;
    page-break-inside: avoid; /* 避免图片被分页符截断 */
}

img, img.attpic {
    max-width: 95%; /* 图片最大宽度不超过屏幕的95% */
    height: auto;
    display: inline-block;
    border: 1px solid #dddddd; /* 给图片一个浅色边框 */
    padding: 4px;
    box-sizing: border-box;
}


/* --- 其他 --- */
.booktitle {
    font-size: 2.5em;
    font-weight: bold;
    text-align: center;
    margin-top: 30%;
}

.bookauthor {
    font-size: 1.5em;
    text-align: center;
    margin-top: 1em;
    page-break-after: always;
}

/* --- 【核心修正】: 针对目录页 (nav.xhtml) 的样式 --- */
nav[epub|type="toc"] ol {
    padding: 0;
    margin: 0 0 0 2em;
    list-style-type: none; /* 移除列表前的默认数字序号 */
}
nav[epub|type="toc"] li {
    margin: 0;
    padding: 0;
}
nav[epub|type="toc"] ol ol {
    margin-left: 2em; /* 为二级目录创建缩进 */
}
nav[epub|type="toc"] a {
    text-decoration: none; /* 默认无下划线 */
    color: #333333;       /* 深灰色字体 */
    font-size: 1.1em;
    line-height: 1.8;
}
nav[epub|type="toc"] a:hover {
    text-decoration: underline; /* 鼠标悬停时显示下划线 */
}
"""

def print_progress_bar(iteration, total, prefix='进度', suffix='完成', length=50, fill='█'):
    """
    打印进度条的辅助函数。
    """
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

def get_user_input_path():
    """
    获取用户输入的工作目录路径。
    """
    default_path = "/Users/doudouda/Downloads/2/"
    path = input(f"请输入TXT文件所在的目录 (默认为: {default_path}): ").strip()
    if not path:
        path = default_path
    
    if not os.path.isdir(path):
        print(f"\n[错误] 目录 '{path}' 不存在。请检查路径是否正确。")
        sys.exit(1)
        
    print(f"\n工作目录设置为: {path}")
    return path

def scan_directory(work_dir):
    """
    扫描目录，查找 TXT, 封面图片和 CSS 文件。
    """
    txt_files = []
    cover_image_path = None
    css_content = DEFAULT_CSS
    css_file_found = False

    image_extensions = ['.jpg', '.jpeg', '.png']
    
    for filename in sorted(os.listdir(work_dir)):
        full_path = os.path.join(work_dir, filename)
        if not os.path.isfile(full_path):
            continue

        if filename.lower().endswith('.txt'):
            txt_files.append(full_path)
            
        if not cover_image_path and any(filename.lower().endswith(ext) for ext in image_extensions):
            cover_image_path = full_path
            print(f"  [发现封面] 将使用 '{filename}' 作为封面。")

        if filename.lower().endswith('.css'):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    css_content = f.read()
                css_file_found = True
                print(f"  [发现CSS] 将使用自定义样式文件 '{filename}'。")
            except Exception as e:
                print(f"  [警告] 读取CSS文件 '{filename}' 失败: {e}。将使用默认样式。")

    if not css_file_found:
        print("  [提示] 未在目录中找到CSS文件，将使用内置的默认样式。")
        
    if not txt_files:
        print("\n[错误] 在指定目录中未找到任何 .txt 文件。")
        sys.exit(1)

    return txt_files, cover_image_path, css_content

def get_toc_rules():
    """
    向用户询问并获取提取目录的正则表达式规则。
    """
    print("\n--- 步骤 1: 定义目录规则 ---")
    use_default = input("是否使用默认规则提取目录? ('#' 代表一级, '##' 代表二级) [y/n]: ").lower()
    
    if use_default == 'y':
        return r'^#\s*(.*)', r'^##\s*(.*)'
    else:
        level1_regex = input("请输入一级目录的正则表达式 (例如: ^第.*?章): ").strip()
        level2_regex = input(r"请输入二级目录的正则表达式 (例如: ^\d+\.\d+): ").strip()
        if not level1_regex:
            print("[错误] 一级目录的正则表达式不能为空。")
            sys.exit(1)
        return level1_regex, level2_regex

def extract_toc_from_text(txt_path, level1_regex, level2_regex):
    """
    根据正则表达式从TXT文件中提取目录结构。
    """
    toc = []
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
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
    """
    友好地打印出目录结构供用户确认。
    """
    print("\n" + "="*50)
    print("已识别出的目录结构如下，请检查:")
    print("="*50)
    if not toc:
        print("(未识别到任何目录)")
    for title, level in toc:
        # 【核心修正】: 恢复显示原始标题，包括序号
        if level == 1:
            print(f"- {title}")
        else:
            print(f"    - {title}")
    print("="*50)

def confirm_and_edit_toc(current_txt_file, l1_regex, l2_regex):
    """
    让用户确认目录，如果用户选择否则提供交互式修改功能。
    """
    print("\n--- 步骤 2: 确认与修改目录 ---")
    
    toc = extract_toc_from_text(current_txt_file, l1_regex, l2_regex)
    if toc is None:
        return None

    while True:
        print_toc_for_confirmation(toc)
        is_correct = input("以上目录是否正确? [y/n]: ").lower()
        if is_correct == 'y':
            return toc
        
        print("\n请按以下格式复制、修改并粘贴新的目录结构。")
        print("格式说明: ")
        print("  - 一级目录: `- 标题`")
        print("  - 二级目录: `    - 标题`")
        print("完成编辑后，粘贴到此处，然后按两次回车键结束输入。")
        
        lines = []
        while True:
            try:
                line = input()
                if not line: break
                lines.append(line)
            except EOFError:
                break
        
        new_toc = []
        for line in lines:
            if line.strip().startswith('- '):
                # We assume the user has provided the clean title now
                title = line.strip()[2:].strip()
                if line.startswith('    '):
                    new_toc.append((title, 2))
                else:
                    new_toc.append((title, 1))
        toc = new_toc

def text_to_html(text):
    """
    将纯文本转换为简单的 HTML，段落用 <p> 包裹。
    """
    if not text or not text.strip():
        return ""
    paragraphs = re.split(r'\n\s*\n', text.strip())
    html_paragraphs = [f'<p>{p.replace(os.linesep, "<br/>").strip()}</p>' for p in paragraphs if p.strip()]
    return '\n'.join(html_paragraphs)

def create_epub(txt_path, final_toc, css_content, cover_path, l1_regex, l2_regex):
    """
    核心函数：创建 EPUB 文件。
    """
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
    output_path = os.path.join(os.path.dirname(txt_path), f"{book_name}.epub")

    if cover_path:
        try:
            book.set_cover("cover.jpg", open(cover_path, 'rb').read())
            print(f"[LOG] 成功添加封面: '{os.path.basename(cover_path)}'")
        except Exception as e:
            print(f"[警告] 添加封面失败: {e}")

    with open(txt_path, 'r', encoding='utf-8') as f:
        full_text = f.read()

    print("[LOG] 开始在原文中定位所有章节标题...")
    all_headings_map = []
    
    combined_regex_str = f"({l2_regex})|({l1_regex})"
    pattern = re.compile(combined_regex_str, re.MULTILINE)
    print(f"[LOG] 使用的组合正则表达式: {pattern.pattern}")

    for match in pattern.finditer(full_text):
        title, level = None, None
        
        if match.group(1): 
            title = match.group(2).strip()
            level = 2
        elif match.group(3):
            title = match.group(4).strip()
            level = 1
        
        if title is not None and any(toc_title == title for toc_title, toc_level in final_toc if toc_level == level):
            all_headings_map.append({
                'title': title,
                'level': level,
                'start': match.start(),
                'end': match.end()
            })
            
    print(f"[LOG] 定位完成，共找到 {len(all_headings_map)} 个有效标题。")
    
    chapters = []
    chapter_map = []

    if not all_headings_map:
        print("[LOG] 未找到任何章节标题，将全文作为单一章节处理。")
        chapter_item = epub.EpubHtml(title=book_name, file_name='chap_0.xhtml', lang='zh')
        chapter_item.content = text_to_html(full_text)
        chapters.append(chapter_item)
    else:
        total_headings = len(all_headings_map)
        print_progress_bar(0, total_headings, prefix='[PROGRESS] 创建章节文件:', suffix='完成')

        for i, heading_info in enumerate(all_headings_map):
            original_title = heading_info['title']
            level = heading_info['level']
            
            content_start = heading_info['end']
            content_end = all_headings_map[i + 1]['start'] if i + 1 < len(all_headings_map) else len(full_text)
            
            raw_content = full_text[content_start:content_end].strip()
            html_content = text_to_html(raw_content)
            
            filename = f'chap_{i}.xhtml'
            # 【核心修正】: 恢复使用原始标题
            chapter_item = epub.EpubHtml(title=original_title, file_name=filename, lang='zh')
            
            chapter_item.content = f'<h{level} class="titlel{level}std">{original_title}</h{level}>\n{html_content}'
            
            chapters.append(chapter_item)
            
            chapter_map.append({'title': original_title, 'level': level, 'filename': filename})
            print_progress_bar(i + 1, total_headings, prefix='[PROGRESS] 创建章节文件:', suffix='完成')

    print("[LOG] 开始构建可导航的TOC目录...")
    epub_toc = []
    l1_section = None
    for chap_info in chapter_map:
        original_title = chap_info['title']
        level = chap_info['level']
        filename = chap_info['filename']
        
        # 【核心修正】: 恢复使用原始标题作为TOC链接文本
        if level == 1:
            l1_link = epub.Link(filename, original_title, f'uid_{filename}')
            l1_section = (l1_link, [])
            epub_toc.append(l1_section)
            print(f"[LOG] 添加一级目录: '{original_title}' -> {filename}")
        elif level == 2:
            if l1_section is None:
                print(f"[警告] 二级标题 '{original_title}' 没有找到对应的一级父级，已为其创建虚拟父级。")
                l1_link = epub.Link("#", "章节", f"uid_parent_{original_title}")
                l1_section = (l1_link, [])
                epub_toc.append(l1_section)
            
            l2_link = epub.Link(filename, original_title, f'uid_{filename}')
            l1_section[1].append(l2_link)
            print(f"  [LOG] -> 添加二级目录: '{original_title}' -> {filename}")
    
    print("[LOG] 正在组合EPUB文件...")
    style_item = epub.EpubItem(uid="style_default", file_name="style/default.css", media_type="text/css", content=css_content)
    book.add_item(style_item)
    
    nav_html = epub.EpubNav(uid='nav', file_name='nav.xhtml')
    nav_html.add_item(style_item)
    
    for chap in chapters:
        chap.add_item(style_item)
        book.add_item(chap)
        
    book.toc = epub_toc
    book.add_item(epub.EpubNcx())
    book.add_item(nav_html) 
    
    spine_items = []
    if cover_path:
        spine_items.append('cover')
    spine_items.append(nav_html) 
    spine_items.extend(chapters)
    book.spine = spine_items
    
    spine_files = []
    for item in book.spine:
        if hasattr(item, 'file_name'):
            spine_files.append(item.file_name)
        elif isinstance(item, str):
            spine_files.append(item)
    print(f"\n[LOG] 书脊顺序: {spine_files}")
    print(f"[LOG] 最终生成的目录结构（TOC）条目数: {len(epub_toc)}")

    try:
        epub.write_epub(output_path, book, {})
        print(f"  [成功] EPUB 文件已保存到: {output_path}")
    except Exception as e:
        print(f"  [错误] 写入 EPUB 文件时失败: {e}")

if __name__ == "__main__":
    print("="*60)
    print(" " * 18 + "TXT to EPUB 转换器")
    print("="*60)
    
    work_directory = get_user_input_path()
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
            
        create_epub(current_txt_file, final_toc_list, css_data, cover_image, l1_regex, l2_regex)
        print("-" * 60)

    print("\n所有任务已完成！")
