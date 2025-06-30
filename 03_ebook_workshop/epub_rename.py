import os
import sys
import zipfile
import tempfile
import shutil
import xml.etree.ElementTree as ET

def sanitize_filename(name):
    """移除字符串中的非法字符，使其成为有效的文件名。"""
    invalid_chars = r'<>:"/\|?*'
    if name:
        for char in invalid_chars:
            name = name.replace(char, '')
        return name.strip()
    return "Untitled"

def get_unique_filepath(path):
    """检查文件路径是否存在。如果存在，则附加一个数字使其唯一。"""
    if not os.path.exists(path):
        return path
    directory, filename = os.path.split(path)
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_name = f"{name} ({counter}){ext}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def run_epub_modifier_v8_final():
    """
    v8: 最终版。所有文件都会被处理，跳过的文件使用其原始元数据标题命名。
    """
    print("=====================================================")
    print("=     EPUB 修改脚本 (v8 - 最终完整处理版)     =")
    print("=====================================================")
    print("功能：")
    print("  - 所有扫描到的文件都将被处理并放入 'processed_files' 文件夹。")
    print("  - 输入新标题将使用新标题命名。")
    print("  - 直接回车将使用书籍自身的元数据标题命名。")

    default_path = "/Users/doudouda/Downloads/2/"
    folder_path = input(f"\n请输入 EPUB 文件夹路径 (默认为: {default_path}): ").strip() or default_path

    if not os.path.isdir(folder_path):
        sys.exit(f"\n错误：文件夹 '{folder_path}' 不存在。")

    processed_folder_path = os.path.join(folder_path, "processed_files")
    os.makedirs(processed_folder_path, exist_ok=True)

    epub_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.epub')])
    if not epub_files:
        sys.exit(f"在 '{folder_path}' 中未找到 EPUB 文件。")
        
    print("\n找到以下待处理文件:")
    for i, filename in enumerate(epub_files): print(f"  {i+1}. {filename}")

    # 获取用户意图
    tasks = []
    print("\n----------------------------------------")
    for i, filename in enumerate(epub_files):
        user_input = input(f"\n{i+1}. 请为 '{filename}' 输入新标题 (或直接回车以规整文件名): ")
        tasks.append({'filename': filename, 'new_title_input': user_input.strip()})
    
    print("\n--- 开始批量处理 ---")
    
    for task in tasks:
        original_filename = task['filename']
        new_title_input = task['new_title_input']
        original_path = os.path.join(folder_path, original_filename)
        temp_dir = None
        
        print(f"\n--- 正在处理: {original_filename} ---")
        try:
            temp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(original_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            container_path = os.path.join(temp_dir, 'META-INF', 'container.xml')
            if not os.path.exists(container_path):
                raise FileNotFoundError("错误: 找不到 META-INF/container.xml")
            
            tree = ET.parse(container_path)
            root = tree.getroot()
            ns = {'cn': 'urn:oasis:names:tc:opendocument:xmlns:container'}
            opf_path_element = root.find('cn:rootfiles/cn:rootfile', ns)
            if opf_path_element is None: raise FileNotFoundError("错误: 在 container.xml 中找不到 <rootfile> 标签")
            
            opf_file_rel_path = opf_path_element.get('full-path')
            opf_file_abs_path = os.path.join(temp_dir, opf_file_rel_path)
            print(f"  - 找到元数据文件: {opf_file_rel_path}")

            opf_ns = {'dc': 'http://purl.org/dc/elements/1.1/'}
            tree = ET.parse(opf_file_abs_path)
            root = tree.getroot()
            
            title_element = root.find('.//dc:title', opf_ns)
            if title_element is None: raise ValueError(f"错误: 在 '{opf_file_rel_path}' 中找不到 <dc:title> 标签")

            current_title = title_element.text or ""
            
            # 决定最终标题
            if new_title_input:
                target_title = new_title_input
                print(f"  - 用户输入新标题: '{target_title}'")
                title_element.text = target_title
                tree.write(opf_file_abs_path, encoding='utf-8', xml_declaration=True)
            else:
                target_title = current_title
                print(f"  - 用户选择跳过，使用书中原有标题: '{target_title}'")

            # 重新打包
            new_safe_filename = sanitize_filename(target_title) + '.epub'
            destination_path = get_unique_filepath(os.path.join(processed_folder_path, new_safe_filename))
            
            print(f"  - 重新打包为: {os.path.basename(destination_path)}")
            with zipfile.ZipFile(destination_path, 'w') as zip_out:
                mimetype_path = os.path.join(temp_dir, 'mimetype')
                if os.path.exists(mimetype_path):
                    zip_out.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
                
                for root_dir, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        if arcname != 'mimetype':
                            zip_out.write(file_path, arcname, compress_type=zipfile.ZIP_DEFLATED)
            print("  - 处理成功！")

        except Exception as e:
            print(f"  ! 处理 '{original_filename}' 时发生严重错误: {e}")
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    print("\n--- 所有任务已完成 ---")

if __name__ == "__main__":
    run_epub_modifier_v8_final()