import os
import sys
from collections import deque
from ebooklib import epub, ITEM_DOCUMENT
import math
import json
import tempfile
import shutil

# --- 配置 ---
OUTPUT_DIR_NAME = 'processed_files'

def get_nav_points(toc):
    """
    递归地从目录(TOC)中提取所有 navPoint, 并返回一个扁平化的列表.
    这可以处理嵌套的章节结构.
    """
    nav_points = []
    # 使用 deque 实现广度优先或深度优先的遍历
    items_to_process = deque(toc)
    while items_to_process:
        item = items_to_process.popleft()
        if isinstance(item, epub.Link):
            # 这是一个章节链接
            nav_points.append(item)
        elif isinstance(item, tuple):
            # 这是一个包含子章节的 Section
            # 将子章节列表添加到待处理队列的前面
            items_to_process.extendleft(reversed(item[1]))
    return nav_points


def get_all_document_items(book):
    """
    获取EPUB中所有的文档项目，包括HTML文件等内容文件
    """
    document_items = []
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            document_items.append(item)
    return document_items

def process_epub_file(epub_path, num_splits, output_dir):
    """
    处理单个 EPUB 文件, 将其按章节分割成指定数量的新文件.
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 读取原始 EPUB 文件
        original_book = epub.read_epub(epub_path)
        print(f"\n[INFO] 正在处理: {os.path.basename(epub_path)}")
    except Exception as e:
        print(f"[ERROR] 无法读取文件: {os.path.basename(epub_path)}. 错误: {e}")
        return

    # 获取所有文档项目（实际内容文件）
    all_document_items = get_all_document_items(original_book)
    total_documents = len(all_document_items)
    print(f"[INFO] 文件共有 {total_documents} 个内容文档.")
    
    # 同时获取导航点用于TOC构建
    all_chapters = get_nav_points(original_book.toc)
    print(f"[INFO] 文件共有 {len(all_chapters)} 个导航章节.")

    # 检查分割数是否有效
    if num_splits > total_documents:
        print(f"[ERROR] 分割数 ({num_splits}) 大于总文档数 ({total_documents}). 跳过此文件.")
        return
    if num_splits <= 0:
        print(f"[ERROR] 分割数必须大于 0. 跳过此文件.")
        return

    # 计算每个分割文件应包含的文档数
    base_size = total_documents // num_splits
    remainder = total_documents % num_splits
    
    split_sizes = [base_size + 1] * remainder + [base_size] * (num_splits - remainder)
    
    # 获取所有非文档项目 (如 CSS, 图像, 字体等)
    non_document_items = [item for item in original_book.get_items() if item.get_type() != ITEM_DOCUMENT]
    print(f"[INFO] 找到 {len(non_document_items)} 个非文档项目（CSS、图像等）.")

    current_document_index = 0
    for i, size in enumerate(split_sizes):
        part_num = i + 1
        print(f"\n[INFO] 正在创建第 {part_num} 部分，包含 {size} 个文档...")
        
        # 创建一个新的 EPUB book 对象
        new_book = epub.EpubBook()
        
        # --- 复制元数据 ---
        try:
            original_identifier = original_book.get_metadata('DC', 'identifier')[0][0]
            original_title = original_book.get_metadata('DC', 'title')[0][0]
            original_language = original_book.get_metadata('DC', 'language')[0][0]

            new_book.set_identifier(f"{original_identifier}-part{part_num}")
            new_book.set_title(f"{original_title} (Part {part_num}/{num_splits})")
            new_book.set_language(original_language)
        except IndexError:
            base_name = os.path.splitext(os.path.basename(epub_path))[0]
            new_book.set_identifier(f"unknown-id-{base_name}-part{part_num}")
            new_book.set_title(f"{base_name} (Part {part_num}/{num_splits})")
            new_book.set_language('en')
            print(f"  [WARNING] 原始文件缺少部分元数据, 已使用默认值.")

        # --- 添加文档内容 ---
        start_index = current_document_index
        end_index = current_document_index + size
        documents_for_this_part = all_document_items[start_index:end_index]
        
        print(f"  [INFO] 添加文档 {start_index+1} 到 {end_index}...")
        
        # 添加所有文档项目到新书中
        new_book.spine = []
        for doc_item in documents_for_this_part:
            new_book.add_item(doc_item)
            new_book.spine.append(doc_item)
            print(f"    -> 已添加文档: {doc_item.get_name()}")

        # 添加所有非文档项目（CSS、图像等）
        for item in non_document_items:
            new_book.add_item(item)

        # 构建适当的TOC - 只包含与当前部分相关的章节
        relevant_chapters = []
        for chapter in all_chapters:
            # 检查章节是否指向当前部分的文档
            for doc_item in documents_for_this_part:
                if chapter.href in doc_item.get_name() or doc_item.get_name() in chapter.href:
                    relevant_chapters.append(chapter)
                    break
        
        new_book.toc = relevant_chapters if relevant_chapters else all_chapters[:min(len(all_chapters), size)]
        
        new_book.add_item(epub.EpubNcx())
        new_book.add_item(epub.EpubNav())

        # --- 保存新的 EPUB 文件 ---
        base_name = os.path.splitext(os.path.basename(epub_path))[0]
        new_filename = f"{base_name}-{part_num}.epub"
        output_path = os.path.join(output_dir, new_filename)

        try:
            epub.write_epub(output_path, new_book, {})
            print(f"  -> 已创建: {new_filename} (包含 {len(documents_for_this_part)} 个文档)")
        except Exception as e:
            print(f"  -> [ERROR] 创建文件失败: {new_filename}. 错误: {e}")

        current_document_index = end_index

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
    主函数, 用于获取用户输入并启动处理流程.
    """
    # --- 修改：动态加载默认路径 ---
    default_dir = load_default_path_from_settings()
    
    # --- 获取用户输入 ---
    input_dir = input(f"请输入 EPUB 文件所在的目录 (默认为: {default_dir}): ").strip()
    if not input_dir:
        input_dir = default_dir

    if not os.path.isdir(input_dir):
        print(f"[FATAL] 错误: 目录 '{input_dir}' 不存在. 程序退出.")
        sys.exit(1)

    while True:
        try:
            num_splits_str = input("请输入您想将每本书分割成的文件数量: ").strip()
            num_splits = int(num_splits_str)
            if num_splits > 0:
                break
            else:
                print("[ERROR] 分割数量必须是大于0的整数, 请重新输入.")
        except ValueError:
            print("[ERROR] 无效输入. 请输入一个数字.")

    # --- 创建输出目录 ---
    output_dir = os.path.join(input_dir, OUTPUT_DIR_NAME)
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[INFO] 分割后的文件将保存在: {output_dir}")

    # --- 遍历并处理目录中的所有 EPUB 文件 ---
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.epub'):
            epub_path = os.path.join(input_dir, filename)
            process_epub_file(epub_path, num_splits, output_dir)
            
    print("\n[SUCCESS] 所有文件处理完毕!")

if __name__ == '__main__':
    main()