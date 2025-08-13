import os
import shutil
import zipfile
import hashlib
import json
from bs4 import BeautifulSoup
from ebooklib import epub

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

def get_unique_css_files(unzip_dir):
    """获取解压目录中所有唯一的CSS文件。"""
    css_files = {}
    for root, _, files in os.walk(unzip_dir):
        for file in files:
            if file.endswith('.css'):
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                if file_hash not in css_files:
                    css_files[file_hash] = os.path.relpath(file_path, unzip_dir)
    return list(css_files.values())

def fix_epub_css(epub_path, output_dir):
    """修复单个EPUB文件中的CSS链接。"""
    temp_dir = os.path.join(output_dir, 'temp_epub_unpack')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        unique_css_paths = get_unique_css_files(temp_dir)
        if not unique_css_paths:
            print(f"  - 在 {os.path.basename(epub_path)} 中未找到CSS文件，跳过。")
            return "skipped", "No CSS files found"

        modified = False
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(('.html', '.xhtml')):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        soup = BeautifulSoup(f, 'html.parser')

                    # 检查是否没有样式表链接
                    if not (soup.head and soup.head.find_all('link', rel='stylesheet')):
                        head = soup.head
                        # 如果没有 <head> 标签，则创建一个
                        if not head:
                            head = soup.new_tag('head')
                            html_tag = soup.find('html')
                            if html_tag:
                                html_tag.insert(0, head)
                            else:
                                # 如果没有<html>标签，这是一个格式不正确的文件，但我们仍尝试处理
                                soup.insert(0, head)
                                print(f"  - 警告: 文件 {file} 缺少 <html> 标签，已尝试创建 <head> 标签。")

                        for css_path in unique_css_paths:
                            relative_css_path = os.path.relpath(os.path.join(temp_dir, css_path), root).replace('\\', '/')
                            link_tag = soup.new_tag('link', rel='stylesheet', type='text/css', href=relative_css_path)
                            head.append(link_tag)
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(str(soup))
                        modified = True

        if modified:
            fixed_epub_path = os.path.join(output_dir, os.path.basename(epub_path))
            shutil.make_archive(fixed_epub_path.replace('.epub', ''), 'zip', temp_dir)
            os.rename(fixed_epub_path.replace('.epub', '.zip'), fixed_epub_path)
            return "fixed", None
        else:
            return "skipped", "All HTML files already have CSS links"

    except Exception as e:
        return "failed", str(e)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def main():
    """主函数，处理所有EPUB文件。"""
    default_path = load_default_path_from_settings()
    input_dir = input(f"请输入包含EPUB文件的文件夹路径（默认为：{default_path}）：") or default_path
    
    if not os.path.isdir(input_dir):
        print(f"错误：路径 '{input_dir}' 不是一个有效的文件夹。")
        return

    output_dir = os.path.join(input_dir, 'fixed_epubs')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    epub_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.epub')]
    
    if not epub_files:
        print("在指定目录中未找到EPUB文件。")
        return

    fixed_files = []
    skipped_files = []
    failed_files = []

    print(f"\n开始处理 {len(epub_files)} 个EPUB文件...")
    for filename in epub_files:
        epub_path = os.path.join(input_dir, filename)
        print(f"处理中: {filename}")
        status, reason = fix_epub_css(epub_path, output_dir)
        
        if status == "fixed":
            fixed_files.append(filename)
            print(f"  - 状态：已修复")
        elif status == "skipped":
            skipped_files.append(f"{filename} (原因: {reason})")
            print(f"  - 状态：已跳过")
        elif status == "failed":
            failed_files.append(f"{filename} (原因: {reason})")
            print(f"  - 状态：失败")

    print("\n--- 处理报告 ---")
    print(f"总文件数: {len(epub_files)}")
    print(f"成功修复数: {len(fixed_files)}")
    print(f"跳过文件数: {len(skipped_files)}")
    print(f"失败文件数: {len(failed_files)}")

    if fixed_files:
        print("\n已修复文件:")
        for f in fixed_files:
            print(f"- {f}")
    
    if skipped_files:
        print("\n已跳过文件:")
        for f in skipped_files:
            print(f"- {f}")

    if failed_files:
        print("\n失败文件:")
        for f in failed_files:
            print(f"- {f}")

if __name__ == "__main__":
    main()