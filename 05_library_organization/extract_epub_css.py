import os
import zipfile
import sys

def extract_css_from_epubs(base_dir):
    """
    遍历指定的基础目录，查找所有子目录中的 .epub 文件，
    并将其中的 .css 文件提取到 .epub 文件所在的目录。

    :param base_dir: 用户指定的要搜索的基础目录路径。
    """
    # 检查指定的路径是否存在且是一个目录
    if not os.path.isdir(base_dir):
        print(f"错误: 目录 '{base_dir}' 不存在或不是一个有效的目录。", file=sys.stderr)
        # 提示用户检查默认路径是否正确
        if base_dir == '/Users/doudouda/Downloads/2/':
             print("提示: 默认路径不存在，请确认路径是否正确或手动输入一个有效路径。", file=sys.stderr)
        sys.exit(1)

    print(f"[*] 开始扫描目录: {os.path.abspath(base_dir)}")
    
    # os.walk 会递归地遍历目录树
    for root, dirs, files in os.walk(base_dir):
        for filename in files:
            # 检查文件是否以 .epub 结尾
            if filename.endswith('.epub'):
                epub_path = os.path.join(root, filename)
                print(f"\n[+] 找到 EPUB 文件: {epub_path}")

                try:
                    # EPUB 文件本质上是 ZIP 压缩文件，所以我们用 zipfile 库打开
                    with zipfile.ZipFile(epub_path, 'r') as zf:
                        # 获取 EPUB 包内所有文件的列表
                        all_zip_files = zf.namelist()
                        
                        # 筛选出所有以 .css 结尾的文件
                        css_files_in_zip = [f for f in all_zip_files if f.endswith('.css')]

                        if not css_files_in_zip:
                            print(f"  -> 在 '{filename}' 中未找到 CSS 文件。")
                            continue

                        print(f"  -> 发现 {len(css_files_in_zip)} 个 CSS 文件，准备提取...")

                        # 遍历找到的 CSS 文件并提取
                        for css_file_path in css_files_in_zip:
                            # 将 CSS 文件提取到 epub 文件所在的目录 (root)
                            zf.extract(css_file_path, path=root)
                            # os.path.basename 用于获取纯文件名，使输出更整洁
                            extracted_filename = os.path.basename(css_file_path)
                            print(f"    - 已提取 '{extracted_filename}' 到 '{root}'")

                except zipfile.BadZipFile:
                    print(f"  [!] 警告: 无法打开 '{filename}'。文件可能已损坏或不是有效的 EPUB/ZIP 文件。")
                except Exception as e:
                    print(f"  [!] 错误: 处理 '{filename}' 时发生未知错误: {e}")

    print("\n[*] 所有操作完成。")

if __name__ == "__main__":
    # 定义默认目录
    default_path = "/Users/doudouda/Downloads/2/"
    
    # 提示用户输入，并显示默认值
    prompt_message = f"请输入目标目录路径 (直接按回车将使用默认路径: {default_path}): "
    user_input = input(prompt_message)
    
    # 如果用户没有输入任何内容（直接按了回车），则使用默认路径
    # 否则，使用用户输入的路径
    target_directory = user_input.strip() if user_input.strip() else default_path
    
    # 调用主函数
    extract_css_from_epubs(target_directory)