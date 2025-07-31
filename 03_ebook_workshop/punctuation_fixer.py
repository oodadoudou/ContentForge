import re
import os
import warnings
from pathlib import Path
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from tqdm import tqdm
import html
import sys
import json

# --- 屏蔽已知警告 ---
warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib')
warnings.filterwarnings("ignore", category=FutureWarning, module='ebooklib')
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# --- 常量定义 ---
PROCESSED_DIR_NAME = "processed_files"
REPORT_DIR_NAME = "compare_reference"
HIGHLIGHT_STYLE = "background-color: #f1c40f; color: #000; padding: 2px; border-radius: 3px;"

def generate_report(report_path: Path, changes_log: list, source_filename: str):
    """
    生成HTML格式的变更报告。
    
    Args:
        report_path: 报告文件路径
        changes_log: 变更记录列表，每个元素包含 'original' 和 'modified' 键
        source_filename: 源文件名
    """
    if not changes_log:
        print(f"[!] 没有变更记录，跳过报告生成: {report_path}")
        return
    
    # 获取项目根目录和模板路径
    project_root = Path(__file__).parent.parent
    template_path = project_root / 'shared_assets' / 'report_template.html'
    
    if not template_path.exists():
        print(f"[!] 模板文件不存在: {template_path}")
        return
    
    # 计算从报告文件到shared_assets的相对路径
    report_dir = report_path.parent
    shared_assets_dir = project_root / 'shared_assets'
    try:
        relative_path = os.path.relpath(shared_assets_dir, report_dir)
        css_path = f"{relative_path}/report_styles.css".replace('\\', '/')
        js_path = f"{relative_path}/report_scripts.js".replace('\\', '/')
    except ValueError:
        # 如果无法计算相对路径，使用默认路径
        css_path = "shared_assets/report_styles.css"
        js_path = "shared_assets/report_scripts.js"
    
    # 按替换规则归类
    rule_groups = {}
    for change in changes_log:
        # 提取高亮的原文和替换文本
        original_match = re.search(r'<span class="highlight">([^<]+)</span>', change['original'])
        modified_match = re.search(r'<span class="highlight">([^<]+)</span>', change['modified'])
        
        if original_match and modified_match:
            original_text = original_match.group(1)
            replacement_text = modified_match.group(1)
            rule_key = f"{original_text} → {replacement_text}"
            
            if rule_key not in rule_groups:
                rule_groups[rule_key] = {
                    'original_text': original_text,
                    'replacement_text': replacement_text,
                    'instances': []
                }
            
            rule_groups[rule_key]['instances'].append(change)
    
    # 按实例数量排序
    sorted_rule_groups = sorted(rule_groups.values(), key=lambda x: len(x['instances']), reverse=True)
    total_instances = sum(len(group['instances']) for group in sorted_rule_groups)
    
    # 读取模板文件
    template_content = template_path.read_text(encoding='utf-8')
    
    # 生成规则列表项
    rules_list_items = ""
    for i, group in enumerate(sorted_rule_groups):
        rules_list_items += f'''
                    <div class="rule-list-item" onclick="jumpToRule({i})">
                        <div class="rule-text">
                            <span class="rule-original">{html.escape(group["original_text"])}</span> → 
                            <span class="rule-replacement">{html.escape(group["replacement_text"])}</span>
                        </div>
                        <div class="rule-count">{len(group["instances"])} 次</div>
                    </div>
        '''
    
    # 生成内容区域
    content_sections = ""
    for group_index, group in enumerate(sorted_rule_groups):
        instance_count = len(group['instances'])
        content_sections += f'''
            <div class="rule-group" data-group-index="{group_index}">
                <div class="rule-header" onclick="toggleInstances({group_index})">
                    <div class="rule-title">
                        <span class="rule-badge">{instance_count} 次</span>
                        <span class="toggle-icon" id="toggle-{group_index}">▼</span>
                    </div>
                    <div class="rule-description">
                        <span><strong>{html.escape(group['original_text'])}</strong></span>
                        <span class="rule-arrow">→</span>
                        <span><strong>{html.escape(group['replacement_text'])}</strong></span>
                    </div>
                </div>
                <div class="instances-container" id="instances-{group_index}">
        '''
        
        # 按位置排序实例
        sorted_instances = sorted(group['instances'], key=lambda x: x.get('position', 0))
        
        for instance in sorted_instances:
            content_sections += f'''
                    <div class="instance-item">
                        <div class="instance-content">
                            <div class="original-section">
                                <div class="section-title">原文</div>
                                <div class="text-content">{instance['original']}</div>
                            </div>
                            <div class="modified-section">
                                <div class="section-title">修改后</div>
                                <div class="text-content">{instance['modified']}</div>
                            </div>
                        </div>
                    </div>
            '''
        
        content_sections += '''
                </div>
            </div>
        '''
    
    # 替换模板中的占位符
    html_content = template_content.replace('{{source_filename}}', html.escape(source_filename))
    html_content = html_content.replace('{{rules_count}}', str(len(sorted_rule_groups)))
    html_content = html_content.replace('{{total_instances}}', str(total_instances))
    html_content = html_content.replace('{{rules_list_items}}', rules_list_items)
    html_content = html_content.replace('{{content_sections}}', content_sections)
    html_content = html_content.replace('{{generation_time}}', html.escape(str(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
    
    # 替换CSS和JS文件路径
    html_content = html_content.replace('href="shared_assets/report_styles.css"', f'href="{css_path}"')
    html_content = html_content.replace('src="shared_assets/report_scripts.js"', f'src="{js_path}"')
    
    try:
        report_path.write_text(html_content, encoding='utf-8')
        print(f"[✓] 报告已生成: {report_path}")
    except Exception as e:
        print(f"[!] 无法写入报告文件 {report_path}: {e}")

def is_main_content(content: str) -> bool:
    """
    判断文本是否为正文内容，跳过标题、目录、页眉页脚等非正文内容。
    """
    # 去除首尾空白字符
    content = content.strip()
    
    # 如果内容为空或过短，可能不是正文
    if len(content) < 10:
        return False
    
    # 检查是否为标题类内容（通常较短且可能包含特殊格式）
    if len(content) < 50 and any([
        content.startswith(('第', '章', '节', '卷', '篇')),
        content.endswith(('章', '节', '卷', '篇')),
        re.match(r'^[\d\s]+$', content),  # 纯数字
        re.match(r'^[第\d章节卷篇\s]+$', content),  # 章节标题
    ]):
        return False
    
    # 检查是否为作者、版权等信息
    if any(keyword in content for keyword in [
        '作者', '版权', '出版', '编辑', '译者', '责任编辑', 
        '©', 'Copyright', '版权所有', 'All rights reserved',
        '定价', '元', 'ISBN', '书号'
    ]):
        return False
    
    # 检查是否为目录内容
    if content.count('…') > 3 or content.count('·') > 3:
        return False
    
    # 检查是否为页眉页脚（通常包含页码）
    if re.match(r'^[\d\-\s]+$', content) or len(content.split()) < 3:
        return False
    
    return True

def fix_punctuation_and_get_changes(content: str) -> tuple[str, list]:
    """
    核心标点符号修复函数：对传入的纯文本进行标点符号补全。
    只补全逗号，不补全句号，并跳过非正文内容。
    返回元组: (修改后的文本, 原子化变更列表)
    原子化变更: [{'original_text': '...','replacement_text': '...'}]
    """
    # 首先判断是否为正文内容
    if not is_main_content(content):
        return content, []
    
    modified_content = content
    atomic_changes = []
    
    # 定义标点符号修复规则（只保留逗号补全）
    punctuation_rules = [
        # 规则1: 在中文字符后面跟空格再跟中文字符的地方添加逗号
        {
            'pattern': r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])',
            'replacement': r'\1，\2',
            'description': '中文字符间添加逗号'
        },
        # 规则2: 处理对话中的标点符号
        {
            'pattern': r'([\u4e00-\u9fff])\s+([""])',
            'replacement': r'\1，\2',
            'description': '对话前添加逗号'
        },
        # 规则3: 处理连续的中文字符，在适当位置添加逗号（优化版）
        {
            'pattern': r'([\u4e00-\u9fff]{6,})\s+([\u4e00-\u9fff]{6,})',
            'replacement': r'\1，\2',
            'description': '长句中添加逗号'
        },
        # 规则4: 处理数字和单位之间的空格
        {
            'pattern': r'([\d]+)\s+([元件个只张页卷本章节])',
            'replacement': r'\1\2',
            'description': '数字单位间去除空格'
        }
    ]
    
    # 应用每个规则
    for rule in punctuation_rules:
        pattern = rule['pattern']
        replacement = rule['replacement']
        
        try:
            # 查找所有匹配项
            matches = list(re.finditer(pattern, modified_content))
            if matches:
                # 从后往前替换，避免位置偏移
                for match in reversed(matches):
                    original_text = match.group(0)
                    replacement_text = re.sub(pattern, replacement, original_text)
                    
                    # 只有当替换后的文本不同时才记录变更
                    if original_text != replacement_text:
                        atomic_changes.append({
                            "original_text": original_text,
                            "replacement_text": replacement_text
                        })
                
                # 应用替换
                modified_content = re.sub(pattern, replacement, modified_content)
        except re.error as e:
            print(f"\n[!] 正则表达式错误: '{pattern}'. 错误: {e}. 跳过。")
            continue
    
    # 去重
    unique_atomic_changes = [dict(t) for t in {tuple(d.items()) for d in atomic_changes}]
    return modified_content, unique_atomic_changes

def process_txt_file(file_path: Path, processed_dir: Path, report_dir: Path):
    """处理单个 .txt 文件。"""
    try:
        content = file_path.read_text(encoding='utf-8')
        paragraphs = content.split('\n\n')
        processed_paragraphs = []
        changes_log_for_report = []
        file_was_modified = False
        current_position = 0  # 记录当前在原文中的位置

        for paragraph_index, p_original in enumerate(paragraphs):
            p_modified, atomic_changes = fix_punctuation_and_get_changes(p_original)
            processed_paragraphs.append(p_modified)

            if atomic_changes:
                file_was_modified = True
                original_report = html.escape(p_original)
                modified_report = html.escape(p_modified)

                for change in atomic_changes:
                    orig_esc = html.escape(change["original_text"])
                    repl_esc = html.escape(change["replacement_text"])
                    original_report = original_report.replace(orig_esc, f'<span class="highlight">{orig_esc}</span>')
                    modified_report = modified_report.replace(repl_esc, f'<span class="highlight">{repl_esc}</span>')
                
                changes_log_for_report.append({
                    'original': original_report.replace('\n', '<br>'),
                    'modified': modified_report.replace('\n', '<br>'),
                    'position': current_position + paragraph_index  # 添加位置信息
                })
            
            current_position += len(p_original) + 2  # +2 for \n\n separator

        if file_was_modified:
            new_content = "\n\n".join(processed_paragraphs)
            processed_file_path = processed_dir / file_path.name
            processed_file_path.write_text(new_content, encoding='utf-8')
            report_path = report_dir / f"{file_path.name}.html"
            generate_report(report_path, changes_log_for_report, file_path.name)
            return True

    except Exception as e:
        print(f"\n[!] 处理TXT文件失败 {file_path.name}: {e}")
    return False

def process_epub_file(file_path: Path, processed_dir: Path, report_dir: Path):
    """处理单个 .epub 文件。"""
    try:
        book = epub.read_epub(str(file_path))
        changes_log = []
        book_is_modified = False
        global_position = 0  # 记录全局位置

        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), 'xml')
            if not soup.body:
                continue

            item_is_modified = False
            for p_tag in soup.body.find_all('p'):
                if not p_tag.get_text(strip=True): 
                    continue

                original_p_html = str(p_tag)
                p_text_original = p_tag.get_text()

                p_text_modified, atomic_changes = fix_punctuation_and_get_changes(p_text_original)

                if atomic_changes:
                    book_is_modified = True
                    item_is_modified = True
                    
                    p_tag.string = p_text_modified  # 更安全地替换段落内容
                    modified_p_html = str(p_tag)

                    original_report = original_p_html
                    modified_report = modified_p_html

                    for change in atomic_changes:
                        orig_esc = html.escape(change["original_text"])
                        repl_esc = html.escape(change["replacement_text"])
                        original_report = original_report.replace(orig_esc, f'<span class="highlight">{orig_esc}</span>')
                        modified_report = modified_report.replace(repl_esc, f'<span class="highlight">{repl_esc}</span>')
                    
                    changes_log.append({
                        'original': original_report,
                        'modified': modified_report,
                        'position': global_position  # 添加位置信息
                    })
                
                global_position += len(p_text_original)  # 更新全局位置

            if item_is_modified:
                item.set_content(str(soup).encode('utf-8'))

        if book_is_modified:
            epub.write_epub(str(processed_dir / file_path.name), book, {})
            unique_changes = [dict(t) for t in {tuple(d.items()) for d in changes_log}]
            generate_report(report_dir / f"{file_path.name}.html", unique_changes, file_path.name)
            return True

    except Exception as e:
        print(f"\n[!] 处理EPUB文件失败 {file_path.name}: {e}")
    return False

def load_default_path_from_settings():
    """从共享设置文件中读取默认工作目录。"""
    try:
        # 向上导航两级以到达项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        # 如果 "default_work_dir" 存在且不为空，则返回它
        default_dir = settings.get("default_work_dir")
        return default_dir if default_dir else "."
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"警告：读取 settings.json 失败 ({e})，将使用用户主目录下的 'Downloads' 作为备用路径。")
        # 提供一个通用的备用路径
        return os.path.join(os.path.expanduser("~"), "Downloads")

def main():
    """主函数"""
    print("[*] 标点符号补全工具")
    print("[*] 支持自动修复中文文本中缺失的标点符号")
    print("[*] 支持处理 .txt 和 .epub 文件")
    print()
    
    # 动态加载默认路径
    default_path = load_default_path_from_settings()
    
    prompt_message = (
        f"请输入包含源文件的文件夹路径。\n"
        f"(直接按 Enter 键，将使用默认路径 '{default_path}') : "
    )
    user_input = input(prompt_message)

    if not user_input.strip():
        directory_path = default_path
        print(f"[*] 未输入路径，已使用默认路径: {directory_path}")
    else:
        directory_path = user_input.strip()

    base_dir = Path(directory_path)
    if not base_dir.is_dir():
        print(f"[!] 错误: 文件夹 '{base_dir}' 不存在。")
        return

    processed_dir = base_dir / PROCESSED_DIR_NAME
    report_dir = base_dir / REPORT_DIR_NAME
    processed_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)

    print(f"[*] 工作目录: {base_dir}")
    print(f"[*] 输出文件夹已准备就绪:\n    - 处理后文件: {processed_dir}\n    - 变更报告: {report_dir}")

    # 查找所有需要处理的文件
    all_target_files = list(base_dir.glob('*.txt')) + list(base_dir.glob('*.epub'))
    files_to_process = all_target_files

    if not files_to_process:
        print("[!] 在指定文件夹中没有找到任何需要处理的 .txt 或 .epub 文件。")
        return

    print(f"[*] 发现 {len(files_to_process)} 个待处理文件。")
    print("[*] 开始标点符号补全处理...")

    modified_count = 0
    with tqdm(total=len(files_to_process), desc="处理进度", unit="个文件") as pbar:
        for file_path in files_to_process:
            pbar.set_postfix_str(file_path.name, refresh=True)
            was_modified = False
            if file_path.suffix == '.txt':
                was_modified = process_txt_file(file_path, processed_dir, report_dir)
            elif file_path.suffix == '.epub':
                was_modified = process_epub_file(file_path, processed_dir, report_dir)
            
            if was_modified:
                modified_count += 1
            pbar.update(1)

    print("\n----------------------------------------")
    print(f"[✓] 标点符号补全任务完成！")
    print(f"    - 共处理 {len(files_to_process)} 个文件。")
    print(f"    - 其中 {modified_count} 个文件被修改。")
    print(f"    - 结果已保存至 '{PROCESSED_DIR_NAME}' 和 '{REPORT_DIR_NAME}' 文件夹。")
    
    if modified_count > 0:
        print(f"\n[*] 请查看 '{REPORT_DIR_NAME}' 文件夹中的 HTML 报告以了解详细修改内容。")

if __name__ == '__main__':
    main()