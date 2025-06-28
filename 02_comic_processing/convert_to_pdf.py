# -*- coding: utf-8 -*-

import os
import shutil
import sys
import re
from PIL import Image, ImageFile
import natsort
import traceback

# --- 全局配置 ---
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

FINAL_PDFS_SUBDIR_NAME = "merged_pdfs"
IMAGE_EXTENSIONS_FOR_MERGE = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')

# --- PDF页面与图像质量设置 ---
PDF_TARGET_PAGE_WIDTH_PIXELS = 1600
# PDF文件的DPI（每英寸点数）
PDF_DPI = 300
# --- 全局配置结束 ---


def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
    """
    在终端打印一个可视化的进度条。
    """
    if total == 0:
        percent_str = "0.0%"
        filled_length = 0
    else:
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        percent_str = f"{percent}%"
        filled_length = int(length * iteration // total)

    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent_str} {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')
        sys.stdout.flush()


def find_image_folders(root_dir):
    """
    递归遍历根目录，找到所有直接包含图片文件的文件夹。
    """
    print("\n--- 步骤 1: 正在扫描并查找所有包含图片的文件夹 ---")
    image_folders = []
    excluded_dir_name = FINAL_PDFS_SUBDIR_NAME

    for dirpath, dirnames, filenames in os.walk(root_dir):
        if os.path.basename(dirpath) == excluded_dir_name:
            dirnames[:] = []
            continue

        if any(f.lower().endswith(IMAGE_EXTENSIONS_FOR_MERGE) for f in filenames):
            image_folders.append(dirpath)
    
    sorted_folders = natsort.natsorted(image_folders)
    print(f"    🔍 已找到 {len(sorted_folders)} 个需要处理的图片文件夹。")
    return sorted_folders


def create_pdf_from_images(image_paths_list, output_pdf_path,
                           target_page_width_px, pdf_target_dpi):
    """
    从一系列图片文件路径创建一个PDF文件。
    """
    if not image_paths_list:
        print("    警告: 没有有效的图片可用于创建此PDF。")
        return None

    processed_pil_images = []
    total_images_for_pdf = len(image_paths_list)
    print_progress_bar(0, total_images_for_pdf, prefix='      转换图片:', suffix='完成', length=40)

    for i, image_path in enumerate(image_paths_list):
        try:
            with Image.open(image_path) as img:
                img_to_process = img
                if img_to_process.mode in ['RGBA', 'P']:
                    background = Image.new("RGB", img_to_process.size, (255, 255, 255))
                    background.paste(img_to_process, mask=img_to_process.split()[3] if img_to_process.mode == 'RGBA' else None)
                    img_to_process = background
                elif img_to_process.mode != 'RGB':
                    img_to_process = img_to_process.convert('RGB')

                original_width, original_height = img_to_process.size
                if original_width > target_page_width_px:
                    ratio = target_page_width_px / original_width
                    new_height = int(original_height * ratio)
                    img_resized = img_to_process.resize((target_page_width_px, new_height), Image.Resampling.LANCZOS)
                else:
                    img_resized = img_to_process.copy()

                processed_pil_images.append(img_resized)
        except Exception as e:
            sys.stdout.write(f"\r      警告: 处理图片 '{os.path.basename(image_path)}' 失败: {e}。已跳过。\n")
        finally:
            print_progress_bar(i + 1, total_images_for_pdf, prefix='      转换图片:', suffix='完成', length=40)

    if not processed_pil_images:
        print("    错误: 没有图片成功处理，无法创建PDF。")
        return None

    try:
        if len(processed_pil_images) == 1:
            processed_pil_images[0].save(
                output_pdf_path,
                resolution=float(pdf_target_dpi),
                optimize=True
            )
        else:
            first_image = processed_pil_images[0]
            other_images = processed_pil_images[1:]
            first_image.save(
                output_pdf_path,
                save_all=True,
                append_images=other_images,
                resolution=float(pdf_target_dpi),
                optimize=True
            )
        
        print(f"    ✅ 成功创建 PDF: {os.path.basename(output_pdf_path)}")
        return output_pdf_path
    except Exception as e:
        print(f"    ❌ 错误: 保存 PDF '{os.path.basename(output_pdf_path)}' 失败: {e}")
        traceback.print_exc()
        return None
    finally:
        for img_obj in processed_pil_images:
            try:
                img_obj.close()
            except Exception:
                pass


def normalize_filenames(pdf_dir):
    """
    清理并规范化PDF文件夹中所有文件的名称。
    """
    print("\n--- 步骤 3: 正在规范化PDF文件名 ---")
    try:
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    except FileNotFoundError:
        print(f"    目录 '{pdf_dir}' 未找到，跳过文件名规范化。")
        return

    renamed_count = 0
    for filename in pdf_files:
        base, ext = os.path.splitext(filename)
        cleaned_base = re.sub(r'[\s()\[\]【】。.]', '', base)
        
        normalized_name = cleaned_base + ext
        
        if normalized_name != filename:
            original_path = os.path.join(pdf_dir, filename)
            new_path = os.path.join(pdf_dir, normalized_name)
            try:
                os.rename(original_path, new_path)
                print(f"    重命名: '{filename}' -> '{normalized_name}'")
                renamed_count += 1
            except OSError as e:
                print(f"    ❌ 错误: 重命名 '{filename}' 失败: {e}")
                
    if renamed_count > 0:
        print(f"    ✨ 共规范化了 {renamed_count} 个文件名。")
    else:
        print("    所有文件名已符合规范，无需更改。")


def run_conversion_process(root_dir):
    """
    执行从查找文件夹到生成PDF再到重命名的完整流程。
    """
    folders_to_process = find_image_folders(root_dir)

    if not folders_to_process:
        print("\n在指定目录及其子目录中未找到任何包含图片的文件夹。脚本执行结束。")
        return

    print("\n--- 步骤 2: 开始将图片文件夹批量转换为 PDF ---")
    overall_pdf_output_dir = os.path.join(root_dir, FINAL_PDFS_SUBDIR_NAME)
    os.makedirs(overall_pdf_output_dir, exist_ok=True)
    
    total_folders = len(folders_to_process)
    failed_tasks = []
    success_count = 0

    for i, image_dir_path in enumerate(folders_to_process):
        folder_name = os.path.basename(image_dir_path)
        print(f"\n--- ({i+1}/{total_folders}) 正在处理: {folder_name} ---")

        try:
            image_filenames = [f for f in os.listdir(image_dir_path)
                               if f.lower().endswith(IMAGE_EXTENSIONS_FOR_MERGE) and not f.startswith('.')]
        except Exception as e:
            print(f"  ❌ 错误: 无法读取文件夹 '{folder_name}' 的内容: {e}")
            failed_tasks.append(folder_name)
            continue
            
        if not image_filenames:
            print("    文件夹内未找到符合条件的图片，已跳过。")
            continue

        sorted_image_paths = [os.path.join(image_dir_path, f) for f in natsort.natsorted(image_filenames)]
        output_pdf_filename = f"{folder_name}.pdf"
        output_pdf_filepath = os.path.join(overall_pdf_output_dir, output_pdf_filename)

        result_path = create_pdf_from_images(
            sorted_image_paths, output_pdf_filepath,
            PDF_TARGET_PAGE_WIDTH_PIXELS, PDF_DPI
        )
        
        if result_path:
            success_count += 1
        else:
            failed_tasks.append(folder_name)

    normalize_filenames(overall_pdf_output_dir)

    print("\n" + "=" * 70)
    print("【任务总结报告】")
    print("-" * 70)
    print(f"总计查找项目 (文件夹): {total_folders} 个")
    print(f"  - ✅ 成功生成 PDF: {success_count} 个")
    print(f"  - ❌ 失败: {len(failed_tasks)} 个")
    
    if failed_tasks:
        print("\n失败的项目列表:")
        for task in failed_tasks:
            print(f"  - {task}")
    
    print("-" * 70)
    print(f"所有成功生成的PDF文件已保存在: {overall_pdf_output_dir}")


if __name__ == "__main__":
    # ▼▼▼ 标题已根据您的要求简化 ▼▼▼
    print("=" * 70)
    print("=== 批量图片文件夹转PDF脚本 ===")
    print("=" * 70)
    
    root_input_dir = ""
    default_root_dir_name = "/Users/doudouda/Downloads/2"
    
    while True:
        prompt_message = (
            f"请输入包含多个图片子文件夹的【根目录】路径。\n"
            f"(直接按 Enter 键将使用默认路径: '{default_root_dir_name}'): "
        )
        user_provided_path = input(prompt_message).strip()
        
        current_path_to_check = user_provided_path if user_provided_path else default_root_dir_name
        if not user_provided_path:
            print(f"\n使用默认路径: {current_path_to_check}")

        abs_path_to_check = os.path.abspath(current_path_to_check)
        if os.path.isdir(abs_path_to_check):
            root_input_dir = abs_path_to_check
            print(f"已确认根处理目录: {root_input_dir}")
            break
        else:
            print(f"\n错误：路径 '{abs_path_to_check}' 不是一个有效的目录或不存在。请重试。\n")
    
    try:
        run_conversion_process(root_input_dir)
    except Exception as e:
        print("\n" + "!"*70)
        print("脚本在执行过程中遇到意外的严重错误，已终止。")
        print(f"错误详情: {e}")
        traceback.print_exc()
        print("!"*70)

    print("\n脚本执行完毕。")