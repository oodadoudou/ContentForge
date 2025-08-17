import os
import sys
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from tqdm import tqdm
import json

# --- 配置 ---
# 设置输出文件夹的名称
OUTPUT_DIR_NAME = 'processed_files' 

def convert_epub_to_txt(epub_path, output_txt_path):
    """
    将单个 EPUB 文件转换为 TXT 文件，保留段落结构。

    Args:
        epub_path (str): 源 EPUB 文件的路径。
        output_txt_path (str): 输出 TXT 文件的保存路径。

    Returns:
        bool: 如果转换成功则返回 True，否则返回 False。
    """
    try:
        # 使用 ebooklib 读取 EPUB 文件
        book = epub.read_epub(epub_path)
        
        all_paragraphs = []

        # 遍历 EPUB 中的所有文档项 (通常是章节的 XHTML 文件)
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            # 获取章节内容的原始 HTML
            html_content = item.get_content()
            
            # 使用 BeautifulSoup 解析 HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找所有的文本内容标签 (段落和标题)
            # 包括段落标签 <p> 和标题标签 <h1> 到 <h6>
            content_tags = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            
            for tag in content_tags:
                # 获取标签内的所有文本
                text = tag.get_text(' ', strip=True)
                if text: # 确保不添加空内容
                    all_paragraphs.append(text)
        
        # 将所有段落用两个换行符（即一个空行）连接起来
        final_text = "\n\n".join(all_paragraphs)
        
        # 将最终的文本内容以 UTF-8 编码写入 TXT 文件
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write(final_text)
            
        return True

    except Exception as e:
        # 如果过程中发生任何错误，打印错误信息
        print(f"\n[!] 处理文件 '{os.path.basename(epub_path)}' 时发生错误: {e}")
        return False

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
    主函数，处理用户输入、目录扫描和文件转换流程。
    """
    print("--- EPUB to TXT 转换工具 ---")

    # --- 修改：动态加载默认路径 ---
    default_dir = load_default_path_from_settings()
    
    # 获取用户输入，如果用户直接按回车，则使用默认路径
    input_dir = input(f"请输入包含 EPUB 文件的目录 (默认为: {default_dir}): ").strip()
    if not input_dir:
        input_dir = default_dir
        print(f"[*] 未输入路径，已使用默认目录: {input_dir}")

    # 检查指定的目录是否存在
    if not os.path.isdir(input_dir):
        print(f"[!] 错误: 目录 '{input_dir}' 不存在。程序退出。")
        sys.exit(1)

    # 创建用于存放处理后文件的输出目录
    output_dir = os.path.join(input_dir, OUTPUT_DIR_NAME)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[*] 转换后的 .txt 文件将保存在: {output_dir}")

    # 扫描目录，找到所有 .epub 文件
    epub_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.epub')]

    if not epub_files:
        print("\n[!] 在指定目录中未找到任何 .epub 文件。")
        return

    print(f"\n[*] 发现 {len(epub_files)} 个 EPUB 文件，开始转换...")
    
    success_count = 0
    fail_count = 0

    # 使用 tqdm 创建一个进度条来可视化处理过程
    with tqdm(total=len(epub_files), desc="转换进度", unit="个文件") as pbar:
        for filename in epub_files:
            pbar.set_postfix_str(filename, refresh=True)
            
            source_epub_path = os.path.join(input_dir, filename)
            
            # 构建输出的 .txt 文件名
            base_name = os.path.splitext(filename)[0]
            output_txt_path = os.path.join(output_dir, f"{base_name}.txt")
            
            # 调用核心转换函数
            if convert_epub_to_txt(source_epub_path, output_txt_path):
                success_count += 1
            else:
                fail_count += 1
            
            pbar.update(1)

    print("\n----------------------------------------")
    print(f"[✓] 任务完成！")
    print(f"    - 成功转换: {success_count} 个文件")
    print(f"    - 转换失败: {fail_count} 个文件")
    print(f"    - 结果已保存至 '{OUTPUT_DIR_NAME}' 文件夹。")

# 当该脚本被直接执行时，运行 main 函数
if __name__ == '__main__':
    main()