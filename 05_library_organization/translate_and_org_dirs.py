import os
import sys
import json
import requests
import time
import shutil
import re
from pypinyin import pinyin, Style

# --- 全局配置 ---
# --- API 配置 ---
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
API_BEARER_TOKEN = "在此处填入您的API_KEY"
API_MODEL = "doubao-seed-1-6-thinking-250615"

# --- AI 翻译提示词 ---
SYSTEM_PROMPT = "你是一个专业的小说翻译."
# 核心翻译逻辑已部分移至代码中处理（如符号替换），提示词保持核心要求。
TRANSLATION_PROMPT_TEMPLATE = """
核心目标： 将韩语或日语小说标题精准、流畅、且富有情感地翻译为简体中文，为读者提供沉浸式的阅读体验。
一、 格式与结构规则
逐行翻译:
严格按照原文的行数和分段进行翻译。
不允许随意合并或拆分段落和换行。

符号处理 (Symbol Handling):
在译文中，仅保留以下英文标点及符号：!, ?, "", @。
[]中的内容为作者名不需要翻译请删除并且跳过

原文保留 (Content Preservation):
原文中出现的英文单词、代码、数字、网址等内容，应在译文中保持原样。

二、 内容与风格标准
完整性 (Completeness):
除上述规则中需要舍弃的符号外，原文的所有内容均需完整翻译。
这包括但不限于：拟声词 (의성어)、拟态词 (의태어)、语气助词、感叹词以及所有专有名词（如角色名、技能名、地名等）。

准确性 (Accuracy):
译文必须忠实于原文的中心思想和具体含义，避免出现语义偏差、增译或漏译。

流畅性 (Fluency):
译文必须行文流畅，符合现代简体中文的口语化表达习惯。
力求文字自然地道，读起来通顺易懂，坚决杜绝生硬的“翻译腔”。

不要添加任何额外的解释、说明或格式，只返回翻译后的单行文本。

请翻译以下单行文本：
{}
"""

# --- 文件整理器 (File Organizer) 配置 ---
# file_organizer 将处理这些扩展名的文件，将它们放入子文件夹
ORGANIZER_TARGET_EXTENSIONS = ".pdf .epub .txt .jpg .jpeg .png .gif .bmp .tiff .webp .zip .rar .7z .tar .gz"

# --- 进度条函数 ---
def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
    if total == 0:
        percent_str, filled_length = "0.0%", 0
    else:
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        percent_str, filled_length = f"{percent}%", int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent_str} {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')
        sys.stdout.flush()

# ==============================================================================
# 模块 1: 文件整理 (File Organizer)
# ==============================================================================
def clean_name_for_grouping(filename: str) -> str:
    cleaned = filename
    if cleaned.startswith('['):
        try:
            idx = cleaned.index(']') + 1
            cleaned = cleaned[idx:].strip()
        except ValueError:
            pass
    cleaned = os.path.splitext(cleaned)[0]
    cut_pos = len(cleaned)
    for ch in '0123456789[]()@#%&':
        pos = cleaned.find(ch)
        if pos != -1 and pos < cut_pos:
            cut_pos = pos
    cleaned = cleaned[:cut_pos].strip()
    return re.sub(r'\s+', ' ', cleaned)

def get_folder_name_for_group(group: list[str]) -> str:
    if not group: return "Unnamed_Group"
    cleaned_group_names = [clean_name_for_grouping(f) for f in group if clean_name_for_grouping(f)]
    if not cleaned_group_names:
        return re.sub(r'[\\/*?:"<>|]', '_', os.path.splitext(group[0])[0])[:50] or "Organized_Files"
    folder_name = os.path.commonprefix(cleaned_group_names).strip(' -_')
    if len(folder_name) < 3:
        folder_name = cleaned_group_names[0]
    return folder_name[:50] or "Organized_Group"

def organize_files_into_subdirs(root_directory: str):
    """根据文件名将根目录下的松散文件整理到子文件夹中。"""
    print(f"\n--- 预处理步骤: 开始整理根目录下的文件 ---")
    target_extensions = set(ext.lower() for ext in ORGANIZER_TARGET_EXTENSIONS.split())
    try:
        all_files = [
            f for f in os.listdir(root_directory)
            if os.path.isfile(os.path.join(root_directory, f)) and os.path.splitext(f)[1].lower() in target_extensions
        ]
        if not all_files:
            print("    根目录下没有需要整理的文件。")
            return
        
        print(f"    发现 {len(all_files)} 个待整理的文件。正在进行智能分组...")
        groups = {}
        for filename in all_files:
            group_key = clean_name_for_grouping(filename)
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(filename)

        moved_count = 0
        print_progress_bar(0, len(groups), prefix='    文件整理进度:', suffix='完成', length=40)
        i = 0
        for group_key, file_list in groups.items():
            i += 1
            folder_name_raw = group_key if len(group_key) > 2 else os.path.splitext(file_list[0])[0]
            folder_name_sanitized = re.sub(r'[\\/*?:"<>|]', '_', folder_name_raw).strip()
            if not folder_name_sanitized: continue

            folder_path = os.path.join(root_directory, folder_name_sanitized)
            os.makedirs(folder_path, exist_ok=True)

            for filename in file_list:
                source_path = os.path.join(root_directory, filename)
                destination_path = os.path.join(folder_path, filename)
                if os.path.exists(source_path):
                    shutil.move(source_path, destination_path)
                    moved_count += 1
            print_progress_bar(i, len(groups), prefix='    文件整理进度:', suffix='完成', length=40)
        
        print(f"    文件整理完成，共移动 {moved_count} 个文件到新创建的子文件夹中。")
    except Exception as e:
        print(f"    文件整理过程中发生错误: {e}")

# ==============================================================================
# 模块 2: 提取、翻译和初步重命名
# ==============================================================================
def extract_folder_names_to_file(root_directory: str) -> list:
    """扫描目录获取子文件夹名，保存到list.txt并返回列表。"""
    print(f"\n--- 步骤 1: 开始扫描目录并生成 list.txt ---")
    try:
        subdirectories = [
            entry_name for entry_name in os.listdir(root_directory)
            if os.path.isdir(os.path.join(root_directory, entry_name)) and not entry_name.startswith('.')
        ]
        subdirectories.sort()
        if not subdirectories:
            print("    在该目录下没有找到任何子文件夹。")
            return []
        print(f"    找到 {len(subdirectories)} 个子文件夹。")
        with open(os.path.join(root_directory, "list.txt"), 'w', encoding='utf-8') as f:
            for dir_name in subdirectories:
                f.write(dir_name + '\n')
        print(f"    成功将文件夹名称列表写入到: {os.path.join(root_directory, 'list.txt')}")
        return subdirectories
    except Exception as e:
        print(f"    步骤 1 发生错误: {e}")
    return []

def translate_names_via_api(root_directory: str, original_names: list) -> list:
    """逐个调用AI API翻译文件夹名称列表，并将结果保存到list-zh.txt。"""
    print(f"\n--- 步骤 2: 发送至AI进行翻译并生成 list-zh.txt ---")
    if not original_names: return []
    translated_names = []
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_BEARER_TOKEN}"}
    total_names = len(original_names)
    print_progress_bar(0, total_names, prefix='    翻译进度:', suffix='完成', length=40)
    for i, original_name in enumerate(original_names):
        # 【修改】在翻译前，先将特定符号替换为空格，以确保翻译的准确性
        name_to_translate = original_name.replace('+', ' ').replace('_', ' ').strip()
        if original_name != name_to_translate:
            print(f"\n    预处理: '{original_name}' -> '{name_to_translate}'")
            
        data = { "model": API_MODEL, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": TRANSLATION_PROMPT_TEMPLATE.format(name_to_translate)}]}
        try:
            response = requests.post(API_URL, headers=headers, data=json.dumps(data), timeout=60)
            response.raise_for_status()
            response_json = response.json()
            translated_text = response_json['choices'][0]['message']['content'].strip()
            final_translation = translated_text.split('\n')[0].strip()
            translated_names.append(final_translation)
        except Exception as e:
            print(f"\n    翻译 '{name_to_translate}' 失败: {e}。将使用原始名称作为占位符。")
            translated_names.append(original_name) # 出错时保留原始名称
            
        print_progress_bar(i + 1, total_names, prefix='    翻译进度:', suffix='完成', length=40)
        time.sleep(0.5)
        
    print("    所有名称翻译尝试完毕。")
    with open(os.path.join(root_directory, "list-zh.txt"), 'w', encoding='utf-8') as f:
        for name in translated_names: f.write(name + '\n')
    print(f"    成功将翻译结果写入到: {os.path.join(root_directory, 'list-zh.txt')}")
    return translated_names

def rename_dirs_to_chinese(root_directory: str, original_names: list, translated_names: list) -> list:
    """根据翻译结果将文件夹重命名为中文名，并返回成功重命名后的新名称列表。"""
    print(f"\n--- 步骤 3: 根据翻译结果重命名文件夹为中文 ---")
    if not original_names or not translated_names or len(original_names) != len(translated_names):
        print("    错误: 名称列表为空或数量不匹配，中止重命名。")
        return []
    renamed_pairs = []
    successful_renames = []
    for original_name, new_name in zip(original_names, translated_names):
        original_path = os.path.join(root_directory, original_name)
        # 如果翻译失败，new_name可能等于original_name，此时跳过重命名
        if original_name == new_name:
            print(f"    跳过: 翻译结果与原名相同 '{original_name}'")
            successful_renames.append(original_name) # 仍然需要将其加入列表以进行后续拼音处理
            continue

        invalid_chars = r'[\\/*?:"<>|]'
        cleaned_new_name = "".join(c for c in new_name if c not in invalid_chars)
        new_path = os.path.join(root_directory, cleaned_new_name)
        
        if os.path.isdir(original_path):
            if not os.path.exists(new_path):
                try:
                    os.rename(original_path, new_path)
                    print(f"    成功: '{original_name}' -> '{cleaned_new_name}'")
                    successful_renames.append(cleaned_new_name)
                except Exception as e:
                    print(f"    失败: 重命名 '{original_name}' 时发生错误: {e}")
            else:
                print(f"    跳过: 目标名称 '{cleaned_new_name}' 已存在。")
                successful_renames.append(cleaned_new_name) # 目标已存在，也视为已处理
        else:
            print(f"    跳过: 找不到原始文件夹 '{original_path}'。")

    print("    中文重命名完成。")
    return successful_renames

# ==============================================================================
# 模块 3: 添加拼音前缀
# ==============================================================================
def add_pinyin_prefix_to_dirs(root_directory: str, dir_names: list) -> list:
    """为给定的中文文件夹名称添加拼音首字母前缀。"""
    print(f"\n--- 步骤 4: 添加拼音首字母前缀 ---")
    if not dir_names:
        print("    没有文件夹可供添加前缀。")
        return []
    
    final_names = []
    renamed_count = 0
    error_count = 0
    
    print_progress_bar(0, len(dir_names), prefix='    添加前缀进度:', suffix='完成', length=40)
    for i, original_name in enumerate(dir_names):
        # 检查是否已经有前缀了
        if re.match(r'^[A-Z]-', original_name):
            print(f"    跳过: '{original_name}' 已有前缀。")
            final_names.append(original_name)
            continue

        first_char_match = re.search(r'([\u4e00-\u9fff]|[A-Za-z])', original_name)
        if not first_char_match:
            print(f"    警告: 无法为 '{original_name}' 确定首字母，跳过。")
            final_names.append(original_name)
            error_count += 1
            continue
        
        prefix = ''
        try:
            first_char = first_char_match.group(1)
            if '\u4e00' <= first_char <= '\u9fff':
                prefix = pinyin(first_char, style=Style.FIRST_LETTER)[0][0].upper()
            elif 'a' <= first_char.lower() <= 'z':
                prefix = first_char.upper()
        except Exception as e:
            print(f"    生成前缀失败 for '{original_name}': {e}")
            prefix = 'X' # Fallback prefix
        
        if prefix:
            new_name_with_prefix = f"{prefix}-{original_name}"
            original_path = os.path.join(root_directory, original_name)
            new_path = os.path.join(root_directory, new_name_with_prefix)
            
            if os.path.isdir(original_path):
                if not os.path.exists(new_path):
                    try:
                        os.rename(original_path, new_path)
                        print(f"    成功: '{original_name}' -> '{new_name_with_prefix}'")
                        renamed_count += 1
                        final_names.append(new_name_with_prefix)
                    except Exception as e:
                        print(f"    失败: 重命名 '{original_name}' 添加前缀时出错: {e}")
                        error_count += 1
                        final_names.append(original_name)
                else:
                    print(f"    跳过: 带前缀的名称 '{new_name_with_prefix}' 已存在。")
                    final_names.append(new_name_with_prefix)
            else:
                 final_names.append(original_name)
        else:
             final_names.append(original_name)
        
        print_progress_bar(i + 1, len(dir_names), prefix='    添加前缀进度:', suffix='完成', length=40)

    print(f"    前缀添加完成。成功: {renamed_count}, 失败/跳过: {error_count}")
    return final_names

# ==============================================================================
# 主执行流程
# ==============================================================================
if __name__ == "__main__":
    print("文件整理、翻译及重命名流水线脚本")
    print("-" * 50)

    # 【修改】添加默认路径并优化用户输入体验
    default_path = "/Users/doudouda/Downloads/2/"
    
    try:
        target_directory_input = input(f"请输入【根目录】路径 (默认: {default_path})，然后按 Enter: ").strip()
        
        if not target_directory_input:
            target_directory = default_path
            print(f"    使用默认路径: {target_directory}")
        else:
            target_directory = target_directory_input

        while not os.path.isdir(target_directory):
            print(f"错误: '{target_directory}' 不是一个有效的目录路径。")
            target_directory_input = input("请重新输入路径，或直接按 Enter 退出: ").strip()
            if not target_directory_input:
                print("未输入有效路径，脚本退出。")
                sys.exit()
            target_directory = target_directory_input

    except KeyboardInterrupt:
        print("\n操作被用户中断。脚本退出。")
        sys.exit()


    # --- 执行预处理步骤：整理文件 ---
    organize_files_into_subdirs(target_directory)

    # --- 执行步骤1：提取文件夹名称 ---
    original_folders = extract_folder_names_to_file(target_directory)

    if original_folders:
        # --- 执行步骤2：翻译文件夹名称 ---
        translated_folders = translate_names_via_api(target_directory, original_folders)

        if translated_folders and len(original_folders) == len(translated_folders):
            # --- 执行步骤3：重命名为中文 ---
            renamed_to_chinese_folders = rename_dirs_to_chinese(target_directory, original_folders, translated_folders)
            
            if renamed_to_chinese_folders:
                # --- 执行步骤4：添加拼音前缀 ---
                add_pinyin_prefix_to_dirs(target_directory, renamed_to_chinese_folders)

    print("\n所有流程执行完毕。")
