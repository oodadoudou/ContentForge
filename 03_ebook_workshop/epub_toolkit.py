#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import zipfile
import json

def load_default_path_from_settings():
    """从共享设置文件中读取默认工作目录。"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir and os.path.isdir(default_dir) else "."
        else:
             return os.path.join(os.path.expanduser("~"), "Downloads")
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")

def create_epub(src_dir_path, out_file_path):
    """将源文件夹重新打包成 EPUB 文件。"""
    os.makedirs(os.path.dirname(out_file_path), exist_ok=True)

    try:
        with zipfile.ZipFile(out_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            mimetype_path = os.path.join(src_dir_path, 'mimetype')
            zf.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

            for root, _, files in os.walk(src_dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, src_dir_path)
                    
                    if arcname == 'mimetype':
                        continue
                    
                    zf.write(file_path, arcname)
        
        print(f"  ✅ 成功创建: {os.path.basename(out_file_path)}")

    except Exception as e:
        print(f"  ❌ 处理 '{os.path.basename(src_dir_path)}' 时发生错误: {e}")

def unpack_epub_batch(parent_dir):
    """批量解包目录下的所有 EPUB 文件。"""
    print("\n--- 执行模式：解包 EPUB -> 文件夹 ---")
    
    epub_files = [f for f in os.listdir(parent_dir) if f.lower().endswith('.epub')]
    if not epub_files:
        sys.exit(f"在 '{parent_dir}' 中未找到任何 .epub 文件。")

    print(f"\n找到 {len(epub_files)} 个 EPUB 文件待处理。")
    print("--- 开始批量解包 ---")

    for filename in sorted(epub_files):
        print(f"\n--- 正在处理: {filename} ---")
        epub_path = os.path.join(parent_dir, filename)
        dir_name = os.path.splitext(filename)[0]
        output_dir = os.path.join(parent_dir, dir_name)

        if os.path.exists(output_dir):
            print(f"  ⚠️  目标文件夹 '{dir_name}' 已存在，跳过此文件。")
            continue

        try:
            os.makedirs(output_dir, exist_ok=True)
            with zipfile.ZipFile(epub_path, 'r') as zf:
                zf.extractall(output_dir)
            print(f"  ✅ 成功解包至: {dir_name}")
        except Exception as e:
            print(f"  ❌ 处理 '{filename}' 时发生错误: {e}")

    print("\n--- 所有解包任务已完成 ---")

def repack_epub_batch(parent_dir):
    """批量封装目录下的所有解压过的 EPUB 文件夹。"""
    print("\n--- 执行模式：封装 文件夹 -> EPUB ---")
    
    dirs_to_repack = []
    for item in os.listdir(parent_dir):
        item_path = os.path.join(parent_dir, item)
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'mimetype')):
            dirs_to_repack.append(item_path)
    
    if not dirs_to_repack:
        sys.exit(f"在 '{parent_dir}' 中未找到任何可重新封装的文件夹。")

    print(f"\n找到 {len(dirs_to_repack)} 个待处理的文件夹。")
    print("--- 开始批量封装 ---")

    for subdir_path in sorted(dirs_to_repack):
        dir_name = os.path.basename(subdir_path)
        print(f"\n--- 正在处理: {dir_name} ---")
        
        output_filename = f"{dir_name}.epub"
        output_filepath = os.path.join(parent_dir, output_filename)
        
        if os.path.exists(output_filepath):
            print(f"  ⚠️  目标文件 '{output_filename}' 已存在，跳过此文件夹。")
            continue

        create_epub(subdir_path, output_filepath)

    print("\n--- 所有封装任务已完成 ---")
    print(f"所有重新封装的 EPUB 文件已保存在原工作目录。")

def main():
    """主执行函数"""
    print("=====================================================")
    print("=      EPUB 解包 & 封装工具 (批量处理版)      =")
    print("=====================================================")
    
    print(" 1. 解包 EPUB -> 文件夹")
    print(" 2. 封装 文件夹 -> EPUB")
    print("----------")
    print(" 0. 退出")
    
    mode = input("请选择操作模式: ").strip()

    if mode in ['1', '2']:
        default_path = load_default_path_from_settings()
        prompt_message = (
            f"\n请输入包含 EPUB 文件的工作目录路径 (默认为: {default_path}): " if mode == '1'
            else f"\n请输入包含解压文件夹的工作目录路径 (默认为: {default_path}): "
        )
        parent_dir = input(prompt_message).strip() or default_path

        if not os.path.isdir(parent_dir):
            sys.exit(f"\n错误：目录 '{parent_dir}' 不存在。")

        if mode == '1':
            unpack_epub_batch(parent_dir)
        elif mode == '2':
            repack_epub_batch(parent_dir)
            
    elif mode == '0':
        sys.exit("操作已取消。")
        
    else:
        sys.exit("\n错误：无效的选择。请输入 1, 2, 或 0。")


if __name__ == "__main__":
    main()
