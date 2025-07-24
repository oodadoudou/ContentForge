#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB 清理工具
功能：删除 EPUB 文件中的封面、字体文件和 CSS 样式中的字体声明
作者：ContentForge 项目
"""

import os
import sys
import zipfile
import shutil
import tempfile
import re
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

# --- 配置 ---
OUTPUT_DIR_NAME = "processed_files"
DEFAULT_INPUT_PATH = "/Users/doudouda/Downloads/2/"

# 字体文件扩展名
FONT_EXTENSIONS = {
    '.ttf', '.otf', '.woff', '.woff2', '.eot', '.svg'
}

# CSS 中字体相关的正则表达式
FONT_FACE_PATTERN = re.compile(r'@font-face\s*{[^}]*}', re.IGNORECASE | re.DOTALL)
FONT_FAMILY_PATTERN = re.compile(r'font-family\s*:\s*[^;]+;', re.IGNORECASE)
FONT_PATTERN = re.compile(r'font\s*:\s*[^;]+;', re.IGNORECASE)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_unique_filepath(path):
    """检查文件路径是否存在，如果存在则添加数字使其唯一"""
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

def load_default_path_from_settings():
    """从共享设置文件中读取默认工作目录"""
    try:
        settings_path = os.path.join(PROJECT_ROOT, 'shared_assets', 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir and os.path.isdir(default_dir) else DEFAULT_INPUT_PATH
        else:
            return DEFAULT_INPUT_PATH
    except Exception:
        return DEFAULT_INPUT_PATH

def clean_css_fonts(css_content):
    """
    清理 CSS 内容中的字体相关声明
    
    Args:
        css_content (str): 原始 CSS 内容
        
    Returns:
        tuple: (清理后的CSS内容, 删除的字体声明数量)
    """
    removed_count = 0
    
    # 删除 @font-face 声明
    original_content = css_content
    css_content = FONT_FACE_PATTERN.sub('', css_content)
    removed_count += len(FONT_FACE_PATTERN.findall(original_content))
    
    # 删除 font-family 声明
    original_content = css_content
    css_content = FONT_FAMILY_PATTERN.sub('', css_content)
    removed_count += len(FONT_FAMILY_PATTERN.findall(original_content))
    
    # 删除包含字体的 font 简写声明（保守处理，只删除明显包含字体名的）
    font_matches = FONT_PATTERN.findall(css_content)
    for match in font_matches:
        # 检查是否包含常见字体名称或引号（表示自定义字体）
        if any(keyword in match.lower() for keyword in ['serif', 'sans-serif', 'monospace', '"', "'"]):
            css_content = css_content.replace(match, '')
            removed_count += 1
    
    # 清理多余的空行和空白
    css_content = re.sub(r'\n\s*\n', '\n', css_content)
    css_content = css_content.strip()
    
    return css_content, removed_count

def remove_cover_from_epub(temp_dir, opf_abs_path, namespaces):
    """
    从 EPUB 中删除封面
    
    Args:
        temp_dir (str): 临时解压目录
        opf_abs_path (str): OPF 文件绝对路径
        namespaces (dict): XML 命名空间
        
    Returns:
        tuple: (是否成功, 处理信息)
    """
    try:
        opf_tree = ET.parse(opf_abs_path)
        opf_root = opf_tree.getroot()
        opf_dir = os.path.dirname(opf_abs_path)
        
        # 查找封面元数据
        meta_cover = opf_root.find('.//opf:meta[@name="cover"]', namespaces)
        if meta_cover is None:
            return True, "未找到封面元数据，跳过封面删除"
        
        cover_id = meta_cover.get('content')
        print(f"  -> 找到封面元数据 ID: '{cover_id}'")
        
        manifest = opf_root.find('opf:manifest', namespaces)
        if manifest is None:
            return False, "无法找到 manifest 节点"
        
        # 查找并删除封面图片
        cover_item = manifest.find(f'opf:item[@id="{cover_id}"]', namespaces)
        if cover_item is None:
            return False, f"无法找到 ID 为 '{cover_id}' 的封面项目"
        
        cover_href = unquote(cover_item.get('href'))
        cover_image_path = os.path.join(opf_dir, cover_href)
        print(f"  -> 找到封面图片: '{cover_href}'")
        
        # 查找并删除封面 HTML 文件
        cover_html_item = None
        html_items = manifest.findall('.//opf:item[@media-type="application/xhtml+xml"]', namespaces)
        for item in html_items:
            html_rel_path = unquote(item.get('href'))
            html_abs_path = os.path.join(opf_dir, html_rel_path)
            if not os.path.exists(html_abs_path):
                continue
            
            try:
                html_tree = ET.parse(html_abs_path)
                # 搜索指向封面的 <img> 或 <svg:image>
                for img in html_tree.findall('.//xhtml:img', namespaces):
                    if img.get('src') and os.path.basename(unquote(img.get('src'))) == os.path.basename(cover_href):
                        cover_html_item = item
                        break
                if cover_html_item:
                    break
                for img in html_tree.findall('.//svg:image', namespaces):
                    if img.get('{http://www.w3.org/1999/xlink}href') and os.path.basename(unquote(img.get('{http://www.w3.org/1999/xlink}href'))) == os.path.basename(cover_href):
                        cover_html_item = item
                        break
                if cover_html_item:
                    break
            except ET.ParseError:
                continue
        
        # 删除封面 HTML 文件
        if cover_html_item is not None:
            cover_html_id = cover_html_item.get('id')
            cover_html_href = unquote(cover_html_item.get('href'))
            cover_html_path = os.path.join(opf_dir, cover_html_href)
            print(f"  -> 找到封面 HTML 页面: '{cover_html_href}'")
            
            # 从 manifest 中删除
            manifest.remove(cover_html_item)
            print("  -> 已从 manifest 中删除封面 HTML")
            
            # 从 spine 中删除
            spine = opf_root.find('opf:spine', namespaces)
            if spine is not None:
                spine_item = spine.find(f'opf:itemref[@idref="{cover_html_id}"]', namespaces)
                if spine_item is not None:
                    spine.remove(spine_item)
                    print("  -> 已从 spine 中删除封面 HTML")
            
            # 删除文件
            if os.path.exists(cover_html_path):
                os.remove(cover_html_path)
                print("  -> 已删除封面 HTML 文件")
        
        # 删除封面图片文件
        if os.path.exists(cover_image_path):
            os.remove(cover_image_path)
            print(f"  -> 已删除封面图片: {os.path.basename(cover_image_path)}")
        
        # 从 manifest 中删除封面图片项目
        manifest.remove(cover_item)
        print("  -> 已从 manifest 中删除封面图片")
        
        # 删除封面元数据
        metadata = opf_root.find('opf:metadata', namespaces)
        if metadata is not None:
            metadata.remove(meta_cover)
            print("  -> 已删除封面元数据")
        
        # 保存修改后的 OPF 文件
        opf_tree.write(opf_abs_path, encoding='utf-8', xml_declaration=True)
        
        return True, "封面删除成功"
        
    except Exception as e:
        return False, f"删除封面时出错: {e}"

def remove_fonts_from_epub_content(temp_dir):
    """
    从解压的 EPUB 内容中删除字体文件和 CSS 字体声明
    
    Args:
        temp_dir (str): 临时解压目录
        
    Returns:
        tuple: (字体文件删除数量, CSS文件处理数量, CSS声明删除数量)
    """
    font_files_removed = 0
    css_files_processed = 0
    total_css_declarations_removed = 0
    
    # 扫描并删除字体文件
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = Path(file).suffix.lower()
            
            if file_ext in FONT_EXTENSIONS:
                os.remove(file_path)
                font_files_removed += 1
                print(f"  -> 已删除字体文件: {os.path.relpath(file_path, temp_dir)}")
    
    # 处理 CSS 文件
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            if file.endswith('.css'):
                css_file_path = os.path.join(root, file)
                
                try:
                    with open(css_file_path, 'r', encoding='utf-8') as f:
                        original_content = f.read()
                    
                    cleaned_content, removed_count = clean_css_fonts(original_content)
                    
                    if removed_count > 0:
                        with open(css_file_path, 'w', encoding='utf-8') as f:
                            f.write(cleaned_content)
                        
                        css_files_processed += 1
                        total_css_declarations_removed += removed_count
                        print(f"  -> 已清理 CSS 文件: {os.path.relpath(css_file_path, temp_dir)} (删除 {removed_count} 个字体声明)")
                
                except UnicodeDecodeError:
                    print(f"  -> 警告: 无法读取 CSS 文件 {file} (编码问题)")
                except Exception as e:
                    print(f"  -> 警告: 处理 CSS 文件 {file} 时出错: {e}")
    
    return font_files_removed, css_files_processed, total_css_declarations_removed

def process_single_epub(epub_path, output_dir, mode):
    """
    处理单个 EPUB 文件
    
    Args:
        epub_path (str): EPUB 文件路径
        output_dir (str): 输出目录
        mode (str): 处理模式 ('c'=封面, 'f'=字体, 'b'=两者)
        
    Returns:
        bool: 处理是否成功
    """
    base_name = os.path.basename(epub_path)
    output_epub_path = get_unique_filepath(os.path.join(output_dir, base_name))
    
    # 创建临时目录
    temp_extract_dir = tempfile.mkdtemp(prefix=f"{os.path.splitext(base_name)[0]}_")
    
    print(f"\n[+] 正在处理: {base_name}")
    
    try:
        # 1. 解压 EPUB 文件
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
            print(f"  -> 已解压到临时目录")
        
        # 2. 根据模式处理内容
        cover_success = True
        cover_info = ""
        font_files_removed = 0
        css_files_processed = 0
        total_css_declarations_removed = 0
        
        if mode in ['c', 'b']:  # 处理封面
            # 查找 OPF 文件
            container_path = os.path.join(temp_extract_dir, 'META-INF', 'container.xml')
            if os.path.exists(container_path):
                container_tree = ET.parse(container_path)
                container_root = container_tree.getroot()
                ns_cn = {'cn': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                opf_path_element = container_root.find('cn:rootfiles/cn:rootfile', ns_cn)
                
                if opf_path_element is not None:
                    opf_rel_path = opf_path_element.get('full-path')
                    opf_abs_path = os.path.join(temp_extract_dir, opf_rel_path)
                    
                    # 定义命名空间
                    namespaces = {
                        'opf': 'http://www.idpf.org/2007/opf',
                        'dc': 'http://purl.org/dc/elements/1.1/',
                        'xhtml': 'http://www.w3.org/1999/xhtml',
                        'svg': 'http://www.w3.org/2000/svg',
                        'xlink': 'http://www.w3.org/1999/xlink'
                    }
                    for prefix, uri in namespaces.items():
                        ET.register_namespace(prefix, uri)
                    
                    cover_success, cover_info = remove_cover_from_epub(temp_extract_dir, opf_abs_path, namespaces)
                    print(f"  -> {cover_info}")
                else:
                    print("  -> 警告: 无法找到 OPF 文件路径")
            else:
                print("  -> 警告: 无法找到 container.xml 文件")
        
        if mode in ['f', 'b']:  # 处理字体
            font_files_removed, css_files_processed, total_css_declarations_removed = remove_fonts_from_epub_content(temp_extract_dir)
        
        # 3. 重新打包 EPUB
        print(f"  -> 正在重新打包...")
        with zipfile.ZipFile(output_epub_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            # 首先添加 mimetype 文件（必须不压缩）
            mimetype_path = os.path.join(temp_extract_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                zip_out.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            else:
                print("  -> 警告: 未找到 mimetype 文件")
            
            # 添加其他文件
            for root, dirs, files in os.walk(temp_extract_dir):
                for file in files:
                    if file == 'mimetype':
                        continue
                    
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):  # 确保文件存在（可能已被删除）
                        arcname = os.path.relpath(file_path, temp_extract_dir)
                        zip_out.write(file_path, arcname)
        
        # 4. 显示处理结果
        print(f"  -> 处理完成!")
        if mode in ['c', 'b']:
            print(f"     封面处理: {cover_info}")
        if mode in ['f', 'b']:
            print(f"     删除字体文件: {font_files_removed} 个")
            print(f"     处理 CSS 文件: {css_files_processed} 个")
            print(f"     删除字体声明: {total_css_declarations_removed} 个")
        print(f"     输出文件: {os.path.relpath(output_epub_path)}")
        
        return True
        
    except zipfile.BadZipFile:
        print(f"  -> 错误: '{base_name}' 不是有效的 ZIP/EPUB 文件")
        return False
    except Exception as e:
        print(f"  -> 错误: 处理 '{base_name}' 时发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时文件
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)

def process_epub_directory(input_dir, mode):
    """
    处理指定目录下的所有 EPUB 文件
    
    Args:
        input_dir (str): 输入目录路径
        mode (str): 处理模式 ('c'=封面, 'f'=字体, 'b'=两者)
    """
    print("=" * 60)
    print("           EPUB 清理工具")
    print("=" * 60)
    
    mode_desc = {
        'c': '删除封面',
        'f': '删除字体',
        'b': '删除封面和字体'
    }
    print(f"处理模式: {mode_desc.get(mode, '未知')}")
    
    # 创建输出目录
    output_dir = os.path.join(input_dir, OUTPUT_DIR_NAME)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n扫描目录: {os.path.abspath(input_dir)}")
    print(f"输出目录: {os.path.abspath(output_dir)}")
    
    # 查找所有 EPUB 文件
    epub_files = [f for f in os.listdir(input_dir) 
                  if f.lower().endswith('.epub') and os.path.isfile(os.path.join(input_dir, f))]
    
    if not epub_files:
        print("\n未在指定目录中找到任何 .epub 文件。")
        return
    
    print(f"\n找到 {len(epub_files)} 个 EPUB 文件待处理")
    print("-" * 60)
    
    # 处理每个 EPUB 文件
    success_count = 0
    fail_count = 0
    
    for epub_file in sorted(epub_files):
        epub_full_path = os.path.join(input_dir, epub_file)
        if process_single_epub(epub_full_path, output_dir, mode):
            success_count += 1
        else:
            fail_count += 1
    
    # 显示处理结果
    print("\n" + "=" * 60)
    print("                处理完成")
    print("=" * 60)
    print(f"总计: {len(epub_files)} 个文件")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"\n处理后的文件保存在: {os.path.abspath(output_dir)}")

def get_processing_mode():
    """
    获取用户选择的处理模式
    
    Returns:
        str: 处理模式 ('c', 'f', 'b')
    """
    print("\n" + "=" * 60)
    print("           选择处理模式")
    print("=" * 60)
    print("ℹ️  请选择要执行的操作:")
    print("   [f] 删除字体 - 删除 EPUB 中的字体文件和 CSS 字体声明")
    print("   [c] 删除封面 - 删除 EPUB 中的封面图片和封面页面")
    print("   [b] 删除两者 - 同时删除封面和字体")
    print("-" * 60)
    
    while True:
        choice = input("请输入选项 (f/c/b): ").strip().lower()
        if choice in ['f', 'c', 'b']:
            return choice
        else:
            print("❌ 无效选项，请输入 f、c 或 b")

def main():
    """主函数"""
    print("=" * 60)
    print("           EPUB 清理工具")
    print("=" * 60)
    print("功能: 删除 EPUB 文件中的封面、字体文件和 CSS 字体声明")
    
    # 1. 获取处理模式
    mode = get_processing_mode()
    
    # 2. 获取目录路径
    default_path = load_default_path_from_settings()
    prompt_message = (
        f"\n请输入包含 EPUB 文件的目录路径\n"
        f"(直接按 Enter 使用默认路径: {default_path}): "
    )
    
    user_input = input(prompt_message).strip().strip('"\'')
    target_dir = user_input if user_input else default_path
    
    if not user_input:
        print(f"使用默认目录: {target_dir}")
    
    # 3. 验证目录
    if not os.path.isdir(target_dir):
        print(f"\n❌ 错误: 目录 '{target_dir}' 不存在或不是有效目录。")
        sys.exit(1)
    
    # 4. 开始处理
    process_epub_directory(target_dir, mode)

if __name__ == "__main__":
    main()