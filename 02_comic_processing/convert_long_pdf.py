import os
import fitz  # PyMuPDF
from PIL import Image
import math
import sys
import json
import shutil
import traceback

# --- 可配置参数 ---

# 图像渲染的DPI (分辨率)，越高质量越好，文件也越大
DPI = 300

# 页面最大高度 (像素)，超过此高度将被切割
MAX_PAGE_HEIGHT = 16384

# 输出图片格式 ('png' 或 'jpg')
IMAGE_FORMAT = 'png'

# 新增：处理完的PDF源文件存放目录名
PROCESSED_PDF_FOLDER_NAME = "converted_pdfs"

# --- 脚本主逻辑 ---

def convert_pdf_with_splitting_in_subdirs(root_dir: str):
    """
    扫描根目录下的所有子目录，处理每个子目录中的PDF文件，将其转换为图片。
    如果页面过长，则进行切割。
    每个PDF的输出图片将保存在子目录下一个与PDF同名的子子目录内。
    成功处理的PDF源文件将被移动到各自子目录下的 '子目录名_processed_pdfs' 文件夹。

    Args:
        root_dir (str): 包含多个子目录的根目录，每个子目录包含PDF文件。
    """
    print("-" * 50)
    print(f"[*] 开始处理...")
    print(f"[*] 根目录: {root_dir}")
    print(f"[*] 页面最大高度: {MAX_PAGE_HEIGHT}px")
    print("-" * 50)

    if not os.path.isdir(root_dir):
        print(f"[错误] 根目录 '{root_dir}' 不存在。请检查路径。")
        return

    # 获取所有子目录
    try:
        subdirs = [d for d in os.listdir(root_dir) 
                  if os.path.isdir(os.path.join(root_dir, d)) and not d.startswith('.')]
        if not subdirs:
            print(f"[警告] 在根目录 '{root_dir}' 中未找到任何子目录。")
            return
    except Exception as e:
        print(f"[错误] 无法读取根目录 '{root_dir}': {e}")
        return

    print(f"[*] 找到 {len(subdirs)} 个子目录，准备开始处理。")

    total_successful_conversions = 0
    total_failed_conversions = 0

    # 遍历每个子目录
    for subdir in sorted(subdirs):
        subdir_path = os.path.join(root_dir, subdir)
        print(f"\n{'='*60}")
        print(f"[*] 正在处理子目录: {subdir}")
        print(f"[*] 子目录路径: {subdir_path}")
        print(f"{'='*60}")
        
        # 创建存放已处理PDF的文件夹（以子目录名命名）
        processed_pdfs_dir = os.path.join(subdir_path, f"{subdir}_processed_pdfs")
        os.makedirs(processed_pdfs_dir, exist_ok=True)
        print(f"[*] 已处理的PDF将被移至: {processed_pdfs_dir}")
        
        # 获取当前子目录中的PDF文件
        try:
            pdf_files = [f for f in os.listdir(subdir_path) 
                        if f.lower().endswith('.pdf') and not f.startswith('.')]
            if not pdf_files:
                print(f"[警告] 在子目录 '{subdir}' 中未找到任何PDF文件。")
                continue
        except Exception as e:
            print(f"[错误] 无法读取子目录 '{subdir_path}': {e}")
            continue
        
        print(f"[*] 在子目录 '{subdir}' 中找到 {len(pdf_files)} 个PDF文件。")
        
        successful_conversions = 0
        failed_conversions = 0

        for pdf_file in sorted(pdf_files):
            pdf_path = os.path.join(subdir_path, pdf_file)
            
            if not os.path.exists(pdf_path):
                print(f"\n--- 跳过文件: {pdf_file} ---")
                print(f"  [警告] 文件路径无效或不可读: {pdf_path}")
                failed_conversions += 1
                continue

            pdf_base_name = os.path.splitext(pdf_file)[0]
            current_output_subdir = os.path.join(subdir_path, pdf_base_name)
            
            try:
                os.makedirs(current_output_subdir, exist_ok=True)
                print(f"\n--- 处理文件: {pdf_file} ---")
                print(f"    输出至: {current_output_subdir}")
            except Exception as e:
                print(f"[错误] 创建输出子目录 '{current_output_subdir}' 失败: {e}")
                failed_conversions += 1
                continue 
            
            try:
                doc = fitz.open(pdf_path)
                for i, page in enumerate(doc):
                    page_num = i + 1
                    pix = page.get_pixmap(dpi=DPI)
                    
                    if pix.height <= MAX_PAGE_HEIGHT:
                        image_filename = f"{pdf_base_name}_page_{page_num:03d}.{IMAGE_FORMAT}"
                        output_path = os.path.join(current_output_subdir, image_filename)
                        pix.save(output_path)
                        print(f"  - 已保存页面: {page_num} -> {image_filename}")
                    else:
                        print(f"  - 页面 {page_num} 高度为 {pix.height}px，超过最大值 {MAX_PAGE_HEIGHT}px，正在切割...")
                        img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        num_splits = math.ceil(img_pil.height / MAX_PAGE_HEIGHT)
                        
                        for part_num in range(num_splits):
                            top = part_num * MAX_PAGE_HEIGHT
                            bottom = min((part_num + 1) * MAX_PAGE_HEIGHT, img_pil.height)
                            box = (0, top, img_pil.width, bottom)
                            cropped_img = img_pil.crop(box)
                            image_filename = f"{pdf_base_name}_page_{page_num:03d}_part_{part_num+1:02d}.{IMAGE_FORMAT}"
                            output_path = os.path.join(current_output_subdir, image_filename)
                            cropped_img.save(output_path)
                            print(f"    - 已保存分片: {part_num+1}/{num_splits} -> {image_filename}")
                doc.close()
                print(f"--- 完成文件: {pdf_file} ---")
                successful_conversions += 1

                # 移动已成功处理的PDF文件到子目录专用的processed文件夹
                try:
                    destination_path = os.path.join(processed_pdfs_dir, pdf_file)
                    shutil.move(pdf_path, destination_path)
                    print(f"    -> 已将源文件 '{pdf_file}' 移动至 '{subdir}_processed_pdfs' 文件夹。")
                except Exception as move_error:
                    print(f"    [警告] 移动文件 '{pdf_file}' 失败: {move_error}")

            except Exception as e:
                print(f"[错误] 处理文件 '{pdf_file}' 时发生严重错误: {type(e).__name__} - {e}")
                failed_conversions += 1
                continue

        
        # 子目录处理完成统计
        print(f"\n--- 子目录 '{subdir}' 处理完毕 ---")
        print(f"    成功处理: {successful_conversions} 个PDF文件。")
        print(f"    跳过/失败: {failed_conversions} 个PDF文件。")
        print(f"    输出图片保存在各自PDF同名的子子目录中。")
        print(f"    处理过的PDF源文件已移至 '{subdir}_processed_pdfs' 文件夹。")
        
        total_successful_conversions += successful_conversions
        total_failed_conversions += failed_conversions
    
    # 总体处理完成统计
    print("\n" + "=" * 70)
    print(f"[*] 所有子目录处理完毕。")
    print(f"    总共成功处理: {total_successful_conversions} 个PDF文件。")
    print(f"    总共跳过/失败: {total_failed_conversions} 个PDF文件。")
    print(f"[*] 所有输出的图片均保存在各自PDF同名的子子目录中。")
    print(f"[*] 所有处理过的PDF源文件均已移至各自子目录下的 '子目录名_processed_pdfs' 文件夹。")
    print("=" * 70)

# ▼▼▼ 主函数已按您的要求进行标准化修改 ▼▼▼
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("=== PDF转图片工具 (批量处理子目录，支持超长图自动分割与源文件归档) ===")
    print("=" * 70)

    # --- 标准化函数：从共享设定档中读取预设工作目录 ---
    def load_default_path_from_settings():
        """从共享设定档中读取预设工作目录。"""
        try:
            # 假设此脚本位于项目子目录，向上两层找到项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            # 如果 default_work_dir 为空或 None，也视为无效
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir else "."
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"警告：读取 settings.json 失败 ({e})，将使用内建备用路径。")
            # 在无法读取设定档时，提供一个通用的备用路径（用户的下载文件夹）
            return os.path.join(os.path.expanduser("~"), "Downloads")
    # --- 标准化函数结束 ---

    default_input_dir_name = load_default_path_from_settings()
    input_dir = "" # 初始化变量

    # --- 标准化路径处理逻辑 ---
    while True:
        prompt_message = (
            f"\n- 请输入包含多个子目录的根目录路径（每个子目录包含待转换的PDF文件）。\n"
            f"  (直接按 Enter 将使用默认路径: '{default_input_dir_name}'): "
        )
        user_input = input(prompt_message).strip()

        # 如果用户未输入内容，则使用默认路径，否则使用用户输入的路径
        path_to_check = user_input if user_input else default_input_dir_name
        
        abs_path_to_check = os.path.abspath(path_to_check)

        if os.path.isdir(abs_path_to_check):
            input_dir = abs_path_to_check
            print(f"\n[*] 将要处理的目录是: {input_dir}")
            break
        else:
            print(f"错误：路径 '{abs_path_to_check}' 不是一个有效的目录或不存在。")
    # --------------------------

    try:
        convert_pdf_with_splitting_in_subdirs(root_dir=input_dir)
    except KeyboardInterrupt:
        print("\n\n[信息] 操作被用户中断，程序已退出。")
        sys.exit(0)
    except Exception as e:
        print("\n" + "!"*70)
        print("脚本在执行过程中遇到意外的严重错误，已终止。")
        print(f"错误详情: {e}")
        traceback.print_exc()
        print("!"*70)

    print("\n脚本执行完毕。")