import os
import sys
import zipfile
import shutil
import tempfile
import json

# --- 配置 ---
NEW_CSS_FILENAME = "new_style.css"
SHARED_ASSETS_DIR_NAME = "shared_assets"
OUTPUT_DIR_NAME = "processed_files"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_new_css_content():
    """根据新的目录结构，读取shared_assets中的CSS文件内容"""
    css_path = os.path.join(PROJECT_ROOT, SHARED_ASSETS_DIR_NAME, NEW_CSS_FILENAME)
    
    if not os.path.exists(css_path):
        print(f"错误: 样式文件 '{NEW_CSS_FILENAME}' 未在 '{SHARED_ASSETS_DIR_NAME}' 目录中找到。")
        print(f"请确保 '{css_path}' 文件存在。")
        return None
    
    with open(css_path, 'r', encoding='utf-8') as f:
        return f.read()

def modify_single_epub(epub_path, output_dir, new_css_content):
    """处理单个ePub文件，替换其CSS样式"""
    base_name = os.path.basename(epub_path)
    output_epub_path = os.path.join(output_dir, base_name)
    
    # 创建一个临时目录来解压ePub
    temp_extract_dir = tempfile.mkdtemp(prefix=f"{os.path.splitext(base_name)[0]}_")
    
    print(f"\n[+] 正在处理: {base_name}")

    try:
        # 1. 解压 ePub 文件
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
            print(f"  -> 已解压到临时目录: {os.path.basename(temp_extract_dir)}")

        # 2. 查找并替换所有 CSS 文件
        css_replaced_count = 0
        for root, _, files in os.walk(temp_extract_dir):
            for file in files:
                if file.endswith('.css'):
                    css_file_path = os.path.join(root, file)
                    with open(css_file_path, 'w', encoding='utf-8') as f:
                        f.write(new_css_content)
                    css_replaced_count += 1
                    print(f"  -> 已替换样式文件: {os.path.relpath(css_file_path, temp_extract_dir)}")
        
        if css_replaced_count == 0:
            print("  -> 警告: 未在该 ePub 中找到任何 CSS 文件。")

        # 3. 重新打包成 ePub
        print(f"  -> 正在重新打包为: {base_name}")
        with zipfile.ZipFile(output_epub_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            mimetype_path = os.path.join(temp_extract_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                zip_out.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            else:
                 print("  -> 警告: 未找到 mimetype 文件，这可能导致ePub文件无效。")

            for root, _, files in os.walk(temp_extract_dir):
                for file in files:
                    if file == 'mimetype':
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_extract_dir)
                    zip_out.write(file_path, arcname)

        print(f"  -> 处理完成, 已保存到: {os.path.relpath(output_epub_path)}")
        return True

    except zipfile.BadZipFile:
        print(f"  -> 错误: '{base_name}' 不是一个有效的ZIP/ePub文件，已跳过。")
        return False
    except Exception as e:
        print(f"  -> 处理 '{base_name}' 时发生未知错误: {e}")
        return False
    finally:
        # 4. 清理临时文件
        shutil.rmtree(temp_extract_dir)

def process_epub_directory(root_dir):
    """处理指定根目录下的所有ePub文件"""
    print("--- ePub 样式批量替换工具 ---")
    
    new_css_content = get_new_css_content()
    if new_css_content is None:
        return

    # 在目标ePub目录下创建输出文件夹
    output_path = os.path.join(root_dir, OUTPUT_DIR_NAME)
    os.makedirs(output_path, exist_ok=True)
    
    print(f"\n扫描目录: {os.path.abspath(root_dir)}")
    print(f"处理后的文件将存放在: {os.path.abspath(output_path)}")
    
    epub_files = [f for f in os.listdir(root_dir) if f.lower().endswith('.epub')]
    
    if not epub_files:
        print("\n未在指定目录中找到任何 .epub 文件。")
        return
        
    success_count = 0
    fail_count = 0
    
    for epub_file in epub_files:
        epub_full_path = os.path.join(root_dir, epub_file)
        if modify_single_epub(epub_full_path, output_path, new_css_content):
            success_count += 1
        else:
            fail_count += 1
            
    print("\n--- 处理完毕 ---")
    print(f"总计: {len(epub_files)} 个文件 | 成功: {success_count} 个 | 失败: {fail_count} 个")

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
    # --- 修改：动态加载默认路径 ---
    default_path = load_default_path_from_settings()

    # 获取用户输入
    prompt_message = (
        "请输入要处理的 ePub 文件所在的目录路径\n"
        f"(直接按 Enter 键将使用默认路径: {default_path}): "
    )
    target_dir_input = input(prompt_message)

    # 如果用户未输入（或输入为空白），则使用默认路径
    target_dir = target_dir_input.strip().strip('\'"') if target_dir_input.strip() else default_path
    
    if not target_dir_input.strip():
        print(f"未输入路径，将使用默认目录: {target_dir}")

    # 检查最终确定的目录是否存在
    if not os.path.isdir(target_dir):
        print(f"\n错误: 目录 '{target_dir}' 不存在或不是一个有效的目录。")
        print("请检查路径是否正确，或者默认路径是否存在。")
        sys.exit(1)
        
    process_epub_directory(target_dir)