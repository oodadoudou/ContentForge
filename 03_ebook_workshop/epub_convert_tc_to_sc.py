import os
import sys
import zipfile
import tempfile
import re
from xml.etree import ElementTree as ET
import json

# 导入 OpenCC 模块，如果失败则提供清晰的安装指引
try:
    from opencc import OpenCC
    # 导入模块本身以获取其路径
    import opencc as opencc_module
except ImportError:
    print("错误: 无法导入 OpenCC。请先安装库: pip install opencc-python-reimplemented", file=sys.stderr)
    sys.exit(1)

def initialize_opencc():
    """初始化OpenCC转换器，包含健壮的后备方案。"""
    try:
        # 优先尝试标准初始化方法，传入不带 .json 的文件名
        return OpenCC('t2s')
    except Exception as e_simple:
        print("[警告] 标准 OpenCC 初始化失败，尝试使用后备方案...")
        try:
            package_path = opencc_module.__path__[0]
            config_path = os.path.join(package_path, 'config', 't2s.json')
            
            if not os.path.exists(config_path):
                 raise FileNotFoundError("在 OpenCC 包目录中找不到配置文件 (t2s.json)。")

            print(f"[信息] 成功找到配置文件路径: {config_path}")
            return OpenCC(config_path)
            
        except Exception as e_fallback:
            print("错误：无法初始化 OpenCC 转换器。", file=sys.stderr)
            print("标准模式和后备模式均已失败。", file=sys.stderr)
            print(f"\n- 标准模式错误: {e_simple}", file=sys.stderr)
            print(f"- 后备模式错误: {e_fallback}", file=sys.stderr)
            sys.exit(1)

def check_if_translation_needed(temp_dir, cc):
    """
    检查 EPUB 是否包含需要转换为简体的内容。
    """
    for root, _, files in os.walk(temp_dir):
        # 优先检查内容文件
        content_files = [f for f in files if f.endswith(('.xhtml', '.html', '.opf'))]
        if not content_files:
            continue
        
        # 抽样检查第一个找到的内容文件
        sample_file_path = os.path.join(root, content_files[0])
        try:
            with open(sample_file_path, 'r', encoding='utf-8') as f:
                sample_text = f.read(2048)  # 读取 2KB 样本
                if sample_text != cc.convert(sample_text):
                    return True # 发现繁体字，需要转换
        except Exception:
            continue # 如果读取失败，尝试下一个文件
            
    return False # 未发现需要转换的内容

def translate_text_files_in_epub(temp_dir, cc):
    """
    遍历临时目录，翻译所有文本文件的内容。
    """
    # 需要处理的文件类型
    text_extensions = ('.xhtml', '.html', '.opf', '.ncx', '.css')
    
    for root, _, files in os.walk(temp_dir):
        for filename in files:
            if filename.endswith(text_extensions):
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 仅当文件是XML/HTML类型时才进行内容转换
                    if not filename.endswith('.css'):
                        converted_content = cc.convert(content)
                    else:
                        converted_content = content

                    # 仅当内容有变化时才写回文件
                    if converted_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(converted_content)
                        print(f"  - [翻译] 已更新文件: {os.path.relpath(file_path, temp_dir)}")
                        
                except Exception as e:
                    print(f"  - [警告] 处理文件 {filename} 时跳过，原因: {e}")

def repack_epub(temp_dir, new_epub_path):
    """
    将修改后的文件重新打包成 EPUB。
    """
    try:
        mimetype_path = os.path.join(temp_dir, 'mimetype')
        with zipfile.ZipFile(new_epub_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # mimetype 文件必须是第一个且不能压缩
            zf.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            for root_dir, _, files in os.walk(temp_dir):
                for filename in files:
                    if filename != 'mimetype':
                        file_path = os.path.join(root_dir, filename)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arcname)
        print(f"  -> [成功] 新文件已保存: {os.path.basename(new_epub_path)}")
    except Exception as e:
        print(f"  - [错误] 重新打包 EPUB 失败: {e}")

def process_epub(epub_path, output_dir, cc):
    """
    处理单个 EPUB 文件的完整流程：解压、判断、翻译、重新打包。
    """
    print(f"\n[检查] {os.path.basename(epub_path)}")
    
    # 在临时目录中解压并检查
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                zf.extractall(temp_dir)

            if not check_if_translation_needed(temp_dir, cc):
                print("  - [跳过] 文件内容已是简体或无需转换。")
                return

            print("  - [任务] 检测到繁体内容，开始转换...")
            
            # 翻译所有文本文件
            translate_text_files_in_epub(temp_dir, cc)

            # 创建新文件名并打包
            base_name, _ = os.path.splitext(os.path.basename(epub_path))
            new_epub_path = os.path.join(output_dir, f"{base_name}-zhCN.epub")
            repack_epub(temp_dir, new_epub_path)

        except zipfile.BadZipFile:
            print(f"  - [错误] '{os.path.basename(epub_path)}' 不是一个有效的 EPUB 文件。")
        except Exception as e:
            print(f"  - [严重错误] 处理 EPUB 时发生未知问题: {e}")

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

def main():
    """
    脚本主入口。
    """
    cc = initialize_opencc()
    print("[信息] OpenCC 初始化成功。")

    # --- 修改：动态加载默认路径 ---
    default_path = load_default_path_from_settings()
    prompt_message = f"请输入包含 EPUB 的根目录 (直接按回车将使用: {default_path}): "
    target_directory = input(prompt_message).strip() or default_path

    if not os.path.isdir(target_directory):
        print(f"错误: 目录 '{target_directory}' 不存在或无效。", file=sys.stderr)
        sys.exit(1)
        
    output_dir = os.path.join(target_directory, "translated_files")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[*] 开始扫描目录: {os.path.abspath(target_directory)}")
    print(f"[*] 所有翻译后的文件将被保存到: {os.path.abspath(output_dir)}")
    
    for root, _, files in os.walk(target_directory):
        if os.path.abspath(root).startswith(os.path.abspath(output_dir)):
            continue

        for filename in files:
            if filename.endswith('.epub'):
                # 避免处理已经转换过的文件
                if '-zhCN' in filename:
                    continue
                file_path = os.path.join(root, filename)
                process_epub(file_path, output_dir, cc)
    
    print("\n[*] 所有操作完成。")

if __name__ == "__main__":
    main()
