import pandas as pd
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

def find_rules_file(directory: Path) -> Path | None:
    """在目录中查找 .txt 规则文件。会忽略以 '~$' 开头的临时文件。"""
    for file in directory.glob('*.txt'):
        if not file.name.startswith('~$'):
            if 'rules' in file.name.lower():
                return file
    return None

def load_rules(rules_file: Path) -> pd.DataFrame:
    """加载替换规则, 仅支持 .txt 格式。"""
    print(f"[*] 正在从 {rules_file.name} 加载替换规则...")
    rules_list = []
    try:
        with open(rules_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = re.match(r'^(.*?)\s*->\s*(.*?)\s*\(Mode:\s*(Text|Regex)\s*\)$', line, re.IGNORECASE)
                
                if not match:
                    match_no_replacement = re.match(r'^(.*?)\s*->\s*\(Mode:\s*(Text|Regex)\s*\)$', line, re.IGNORECASE)
                    if match_no_replacement:
                        original, mode = match_no_replacement.groups()
                        replacement = ""
                    else:
                        print(f"[!] 警告: 第 {i} 行规则格式不正确，已忽略: \"{line}\"")
                        continue
                else:
                    original, replacement, mode = match.groups()

                rules_list.append({
                    'Original': original.strip(),
                    'Replacement': replacement.strip(),
                    'Mode': mode.strip().capitalize()
                })
        
        df = pd.DataFrame(rules_list)
        
        if df.empty:
            print("[!] 警告: 规则文件为空或所有规则均无效。")
        else:
            print(f"[+] 成功加载 {len(df)} 条规则。")
        
        return df

    except Exception as e:
        print(f"[!] 加载规则文件失败: {e}")
        exit(1)


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
        
    try:
        report_path.write_text(html_content, encoding='utf-8')
        print(f"[✓] 报告已生成: {report_path}")
    except Exception as e:
        print(f"[!] 无法写入报告文件 {report_path}: {e}")

def process_and_get_changes(content: str, rules: pd.DataFrame) -> tuple[str, list]:
    """
    核心处理函数：对传入的纯文本进行所有替换。
    返回元组: (修改后的文本, 原子化变更列表)
    原子化变更: [{'original_text': '...','replacement_text': '...'}]
    """
    modified_content = content
    atomic_changes = []

    for _, rule in rules.iterrows():
        original, replacement, mode = rule['Original'], rule['Replacement'], rule['Mode']
        if pd.isna(original) or original == "" or original == "nan":
            continue
        
        search_pattern = re.escape(original) if mode.lower() == 'text' else original
        
        try:
            # 必须在最新版本的字符串上查找，以处理链式替换
            matches = list(re.finditer(search_pattern, modified_content))
            if matches:
                # 记录下每次匹配到的原文和它将被替换成的新文本
                for match in matches:
                    atomic_changes.append({
                        "original_text": match.group(0),
                        "replacement_text": match.expand(replacement)
                    })
                # 应用本条规则的替换
                modified_content = re.sub(search_pattern, replacement, modified_content)
        except re.error as e:
            print(f"\n[!] 正则表达式错误: '{search_pattern}'. 错误: {e}. 跳过。")
            continue

    unique_atomic_changes = [dict(t) for t in {tuple(d.items()) for d in atomic_changes}]
    return modified_content, unique_atomic_changes


def process_txt_file(file_path: Path, rules: pd.DataFrame, processed_dir: Path, report_dir: Path):
    """处理单个 .txt 文件。"""
    try:
        content = file_path.read_text(encoding='utf-8')
        paragraphs = content.split('\n\n')
        processed_paragraphs = []
        changes_log_for_report = []
        file_was_modified = False
        current_position = 0  # 记录当前在原文中的位置

        for paragraph_index, p_original in enumerate(paragraphs):
            p_modified, atomic_changes = process_and_get_changes(p_original, rules)
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

def process_epub_file(file_path: Path, rules: pd.DataFrame, processed_dir: Path, report_dir: Path):
    """处理单个 .epub 文件 (已修复)。"""
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
                if not p_tag.get_text(strip=True): continue

                original_p_html = str(p_tag)
                p_text_original = p_tag.get_text()

                p_text_modified, atomic_changes = process_and_get_changes(p_text_original, rules)

                if atomic_changes:
                    book_is_modified = True
                    item_is_modified = True
                    
                    p_tag.string = p_text_modified # 更安全地替换段落内容
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

# --- 新增：函数用于从 settings.json 加载默认路径 ---
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
    # --- 修改：动态加载默认路径 ---
    default_path = load_default_path_from_settings()
    
    prompt_message = (
        f"请输入包含源文件和规则文件的文件夹路径。\n"
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

    rules_file = find_rules_file(base_dir)
    if not rules_file:
        print("[!] 错误: 在指定文件夹中未找到 'rules.txt' 格式的规则文件。")
        return
    rules = load_rules(rules_file)

    if rules.empty:
        print("[!] 规则为空，未执行任何替换。")
        return

    all_target_files = list(base_dir.glob('*.txt')) + list(base_dir.glob('*.epub'))
    files_to_process = [f for f in all_target_files if f.resolve() != rules_file.resolve()]

    if not files_to_process:
        print("[!] 在指定文件夹中没有找到任何需要处理的 .txt 或 .epub 文件。")
        return

    print(f"[*] 发现 {len(files_to_process)} 个待处理文件。")

    modified_count = 0
    with tqdm(total=len(files_to_process), desc="处理进度", unit="个文件") as pbar:
        for file_path in files_to_process:
            pbar.set_postfix_str(file_path.name, refresh=True)
            was_modified = False
            if file_path.suffix == '.txt':
                was_modified = process_txt_file(file_path, rules, processed_dir, report_dir)
            elif file_path.suffix == '.epub':
                was_modified = process_epub_file(file_path, rules, processed_dir, report_dir)
            
            if was_modified:
                modified_count += 1
            pbar.update(1)

    print("\n----------------------------------------")
    print(f"[✓] 任务完成！")
    print(f"    - 共处理 {len(files_to_process)} 个文件。")
    print(f"    - 其中 {modified_count} 个文件被修改。")
    print(f"    - 结果已保存至 '{PROCESSED_DIR_NAME}' 和 '{REPORT_DIR_NAME}' 文件夹。")

if __name__ == '__main__':
    main()