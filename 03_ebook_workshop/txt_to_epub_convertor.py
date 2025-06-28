import os
import re
import sys
from ebooklib import epub

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
    【修复】现在会从项目根目录正确查找 shared_assets 文件夹。
    """
    txt_files = []
    cover_image_path = None
    css_content = None
    
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']
    
    print("\n--- 正在扫描工作目录 ---")
    for filename in sorted(os.listdir(work_dir)):
        full_path = os.path.join(work_dir, filename)
        if not os.path.isfile(full_path):
            continue

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
                print(f"  [警告] 读取CSS文件 '{filename}' 失败: {e}。将尝试加载默认样式。")
    
    if css_content is None:
        print("  [提示] 未在工作目录中找到CSS文件，正在尝试加载内置的默认样式...")
        try:
            # --- 【核心修复】 ---
            # 1. 获取脚本所在的目录 (e.g., .../03_ebook_workshop)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # 2. 获取上一级目录，即项目根目录
            project_root = os.path.dirname(script_dir)
            
            default_css_filename = "new_style.css"
            
            # 3. 从项目根目录构建'shared_assets'的路径
            default_css_path = os.path.join(project_root, 'shared_assets', default_css_filename)
            
            # 为了兼容您之前的提问，也检查'shared_asserts'
            if not os.path.exists(default_css_path):
                 fallback_path = os.path.join(project_root, 'shared_asserts', default_css_filename)
                 if os.path.exists(fallback_path):
                     default_css_path = fallback_path
            # --- 【修复结束】 ---

            with open(default_css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
            print(f"  [加载样式] 成功加载默认样式: {default_css_path}")
        except FileNotFoundError:
            print(f"\n[致命错误] 默认样式文件未找到！")
            # 更新了错误提示，使其更准确
            print(f"  请确保项目根目录下存在 'shared_assets/{default_css_filename}' 文件。")
            # 打印脚本尝试查找的路径以帮助调试
            print(f"  脚本尝试查找的路径为: {default_css_path}")
            sys.exit(1)
        except Exception as e:
            print(f"\n[致命错误] 读取默认样式文件时出错: {e}")
            sys.exit(1)
        
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