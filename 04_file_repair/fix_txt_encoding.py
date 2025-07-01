import os
import sys
import json

def fix_text_file_encoding(file_path, output_path):
    """
    尝试用多种编码读取一个文本文件，并用 UTF-8 格式重新写入。
    
    :param file_path: 原始文件路径。
    :param output_path: 修复后的文件保存路径。
    """
    # 常见的中文编码格式列表，按常用顺序列出
    encodings_to_try = ['utf-8', 'gbk', 'gb18030', 'big5']
    
    content = None
    original_encoding = None

    # 循环尝试用不同的编码格式打开文件
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            original_encoding = encoding
            print(f"  - [成功] 已使用 '{encoding}' 编码格式成功读取文件。")
            break  # 只要成功读取一次，就跳出循环
        except UnicodeDecodeError:
            # 如果解码失败，就继续尝试下一个编码
            continue
        except Exception as e:
            # 捕获其他可能的异常
            print(f"  - [警告] 使用 '{encoding}' 编码时发生未知错误: {e}")
            continue

    # 如果所有编码都尝试失败，则可能不是文本文件或使用了非常见的编码
    if content is None:
        print(f"  - [错误] 无法解码文件: {os.path.basename(file_path)}。该文件可能不是纯文本文件或使用了不支持的编码。")
        return

    # 将读取到的内容以 UTF-8 格式写入新文件
    try:
        # 使用 'utf-8-sig' 会在文件开头写入一个BOM（字节顺序标记），
        # 这有助于某些Windows程序（如记事本）正确识别UTF-8编码。
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.write(content)
        print(f"  -> [完成] 文件已修复并保存至: {os.path.relpath(output_path)}")
    except Exception as e:
        print(f"  - [错误] 写入新文件时失败: {e}")

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
    脚本主函数，负责处理用户输入和文件遍历。
    """
    # --- 修改：动态加载默认路径 ---
    default_path = load_default_path_from_settings()
    
    # 提示用户输入，并显示默认值
    prompt_message = f"请输入需要处理的 TXT 文件所在目录 (直接按回车将使用: {default_path}): "
    target_directory = input(prompt_message).strip() or default_path

    # 检查输入路径是否有效
    if not os.path.isdir(target_directory):
        print(f"错误: 目录 '{target_directory}' 不存在或无效。", file=sys.stderr)
        sys.exit(1)
        
    # 创建统一的输出文件夹
    output_dir = os.path.join(target_directory, "processed_files")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n[*] 开始扫描目录: {os.path.abspath(target_directory)}")
    print(f"[*] 所有处理后的文件将被保存到: {os.path.abspath(output_dir)}")
    
    # 遍历目录（包括所有子目录）
    for root, _, files in os.walk(target_directory):
        # 跳过我们自己创建的输出目录，避免重复处理
        if os.path.abspath(root).startswith(os.path.abspath(output_dir)):
            continue

        for filename in files:
            # 只处理 .txt 文件
            if filename.endswith('.txt'):
                file_path = os.path.join(root, filename)
                output_path = os.path.join(output_dir, filename)
                
                print(f"\n[处理文件] {filename}")
                fix_text_file_encoding(file_path, output_path)
    
    print("\n[*] 所有操作完成。")

if __name__ == "__main__":
    main()