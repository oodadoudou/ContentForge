import os
import sys
import zipfile
import tempfile
import re
from xml.etree import ElementTree as ET
import json

def find_opf_file(unzip_dir):
    """在解压目录中找到 .opf 文件。"""
    for root, _, files in os.walk(unzip_dir):
        for file in files:
            if file.endswith('.opf'):
                return os.path.join(root, file)
    return None

def get_cover_info(opf_path):
    """
    从 .opf 文件中解析出封面图片和封面页面的信息。
    返回一个包含封面图片路径和封面HTML文件路径的字典。
    """
    if not opf_path:
        return None

    cover_info = {'image_path': None, 'html_path': None}
    try:
        # 注册命名空间以便正确解析
        namespaces = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }
        ET.register_namespace('opf', namespaces['opf'])
        ET.register_namespace('dc', namespaces['dc'])

        tree = ET.parse(opf_path)
        root = tree.getroot()
        
        # --- 步骤 1: 找到封面图片的ID ---
        cover_id = None
        # 首先尝试EPUB3的<meta>标签
        meta_cover = root.find('.//opf:meta[@name="cover"]', namespaces)
        if meta_cover is not None:
            cover_id = meta_cover.get('content')
        
        # --- 步骤 2: 从manifest中根据ID找到图片路径 ---
        manifest = root.find('opf:manifest', namespaces)
        if manifest is None: return None
        
        if cover_id:
            cover_item = manifest.find(f".//opf:item[@id='{cover_id}']", namespaces)
            if cover_item is not None:
                cover_info['image_path'] = cover_item.get('href')

        # 如果没有找到，则尝试寻找带有 cover-image 属性的 item
        if not cover_info['image_path']:
            cover_item = manifest.find(".//*[@properties='cover-image']", namespaces)
            if cover_item is not None:
                cover_info['image_path'] = cover_item.get('href')
        
        if not cover_info['image_path']:
             print("  - [警告] 未在 .opf 文件中明确找到封面图片定义。")
             return None

        # --- 步骤 3: 找到封面XHTML文件 ---
        # 寻找引用了封面图片的 XHTML 文件
        for item in manifest.findall('.//opf:item', namespaces):
            href = item.get('href', '')
            if 'cover' in href.lower() and href.endswith(('.xhtml', '.html')):
                cover_info['html_path'] = href
                break
        
        if not cover_info['html_path']:
            print("  - [警告] 未找到明确的封面HTML文件，将创建一个新的。")
            cover_info['html_path'] = 'cover.xhtml' # 如果找不到，就创建一个

        return cover_info
    except Exception as e:
        print(f"  - [错误] 解析OPF文件时出错: {e}")
        return None

def create_and_write_cover_html(unzip_dir, cover_info):
    """
    创建或覆盖封面HTML文件，写入标准化的内容。
    """
    # 计算封面图片相对于封面HTML的路径
    html_full_path = os.path.join(os.path.dirname(os.path.join(unzip_dir, 'DUMMY')), cover_info['html_path'])
    image_full_path = os.path.join(os.path.dirname(os.path.join(unzip_dir, 'DUMMY')), cover_info['image_path'])
    
    # 获取两个文件的目录路径
    html_dir = os.path.dirname(html_full_path)
    image_dir = os.path.dirname(image_full_path)
    
    # 计算相对路径
    relative_image_path = os.path.relpath(image_dir, html_dir)
    # 组合成最终的src路径
    final_image_src = os.path.join(relative_image_path, os.path.basename(image_full_path)).replace('\\', '/')
    
    # 兼容性最好的封面HTML模板
    cover_html_template = f"""<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Cover</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <style type="text/css">
    html, body {{ margin: 0; padding: 0; height: 100%; width: 100%; overflow: hidden; }}
    .cover-container {{ width: 100%; height: 100%; text-align: center; }}
    .cover-image {{ max-width: 100%; max-height: 100%; height: auto; width: auto; }}
  </style>
</head>
<body>
  <div class="cover-container">
    <img src="{final_image_src}" alt="Cover" class="cover-image"/>
  </div>
</body>
</html>"""

    # 找到OPF文件所在的目录，通常是内容文件的根目录
    opf_path = find_opf_file(unzip_dir)
    content_root = os.path.dirname(opf_path)
    
    # 写入新的封面HTML文件
    target_html_path = os.path.join(content_root, cover_info['html_path'])
    os.makedirs(os.path.dirname(target_html_path), exist_ok=True)
    with open(target_html_path, 'w', encoding='utf-8') as f:
        f.write(cover_html_template)
    print(f"  - [修复] 已生成标准化封面文件: {cover_info['html_path']}")


def fix_cover(epub_path, output_dir):
    """
    修复单个EPUB文件的封面。
    """
    print(f"\n[处理] {os.path.basename(epub_path)}")
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                zf.extractall(temp_dir)
            
            opf_path = find_opf_file(temp_dir)
            if not opf_path:
                print("  - [错误] 未找到 .opf 文件，无法处理。")
                return

            cover_info = get_cover_info(opf_path)
            if not cover_info or not cover_info.get('image_path'):
                print("  - [跳过] 未能识别出封面信息。")
                return

            create_and_write_cover_html(os.path.dirname(opf_path), cover_info)
            
            # 重新打包
            base_name, _ = os.path.splitext(os.path.basename(epub_path))
            new_epub_path = os.path.join(output_dir, f"{base_name}-cover-fixed.epub")
            
            with zipfile.ZipFile(new_epub_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                mimetype_path = os.path.join(temp_dir, 'mimetype')
                if os.path.exists(mimetype_path):
                    zf.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
                
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file != 'mimetype':
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, temp_dir)
                            zf.write(full_path, arcname)
            
            print(f"  -> [成功] 封面已修复, 新文件保存至: {os.path.basename(output_dir)}")
        
        except Exception as e:
            print(f"  - [严重错误] 处理过程中发生意外: {e}")

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
    """脚本主入口"""
    # --- 修改：动态加载默认路径 ---
    default_path = load_default_path_from_settings()
    prompt_message = f"请输入需要修复封面的EPUB文件所在目录 (直接按回车将使用: {default_path}): "
    target_directory = input(prompt_message).strip() or default_path

    if not os.path.isdir(target_directory):
        print(f"错误: 目录 '{target_directory}' 不存在或无效。", file=sys.stderr)
        sys.exit(1)
        
    output_dir = os.path.join(target_directory, "processed_files")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[*] 开始扫描目录: {os.path.abspath(target_directory)}")
    print(f"[*] 所有修复后的文件将被保存到: {os.path.abspath(output_dir)}")
    
    for filename in os.listdir(target_directory):
        if filename.endswith('.epub') and '-cover-fixed' not in filename:
            file_path = os.path.join(target_directory, filename)
            if os.path.isfile(file_path):
                fix_cover(file_path, output_dir)
    
    print("\n[*] 所有操作完成。")

if __name__ == "__main__":
    main()