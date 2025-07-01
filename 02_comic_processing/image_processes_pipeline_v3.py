import os
import shutil
from PIL import Image, ImageFile, ImageDraw
import natsort
import sys
from collections import Counter
import traceback
import json
try:
    import numpy as np
except ImportError:
    print("错误：此脚本需要 numpy 库。请使用 'pip install numpy' 命令进行安装。")
    sys.exit(1)

# --- 全局配置 ---
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

# --- 目录与文件名配置 ---
MERGED_LONG_IMAGE_SUBDIR_NAME = "merged_long_img"
SPLIT_IMAGES_SUBDIR_NAME = "split_by_solid_band"
FINAL_PDFS_SUBDIR_NAME = "merged_pdfs"
LONG_IMAGE_FILENAME_BASE = "stitched_long_strip"
IMAGE_EXTENSIONS_FOR_MERGE = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')

# --- V3 核心分割逻辑配置 (颜色方差分析) ---
MIN_SOLID_COLOR_BAND_HEIGHT = 50
COLOR_VARIANCE_THRESHOLD = 60

# 重打包时，单个图片文件的最大檔案大小 (MB)
MAX_REPACKED_FILESIZE_MB = 8
# [V3 新增] 重打包时，单个图片文件的最大像素高度，以优化阅读体验
MAX_REPACKED_PAGE_HEIGHT_PX = 30000
# 所有图片在处理流程开始时，就会被统一到这个宽度
PDF_TARGET_PAGE_WIDTH_PIXELS = 1100
# 提升JPEG压缩质量以获得更清晰的图像
PDF_IMAGE_JPEG_QUALITY = 90
PDF_DPI = 300
# --- 全局配置结束 ---


def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
    """在终端打印进度条。"""
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


def merge_to_long_image(source_image_dir, output_long_image_dir, long_image_filename_only, target_width):
    """
    [V3 逻辑] 将源目录中的所有图片垂直合并成一个PNG长图。
    此版本会以最终的PDF目标宽度为标准，在流程最开始就进行唯一一次高质量缩放。
    """
    print(f"\n  --- 步骤 1: 合并图片至标准宽度 {target_width}px (无边框高质量模式) ---")
    if not os.path.isdir(source_image_dir):
        print(f"    错误: 源图片目录 '{source_image_dir}' 未找到。")
        return None

    os.makedirs(output_long_image_dir, exist_ok=True)
    output_long_image_path = os.path.join(output_long_image_dir, long_image_filename_only)

    try:
        image_filenames = [
            f for f in os.listdir(source_image_dir)
            if os.path.isfile(os.path.join(source_image_dir, f)) and \
               f.lower().endswith(IMAGE_EXTENSIONS_FOR_MERGE) and \
               not f.startswith('.')
        ]
    except Exception as e:
        print(f"    错误: 列出目录 '{source_image_dir}' 中的文件失败: {e}")
        return None

    if not image_filenames:
        print(f"    在 '{source_image_dir}' 中未找到符合条件的图片。")
        return None

    sorted_image_filenames = natsort.natsorted(image_filenames)
    images_data = []
    total_height = 0

    print_progress_bar(0, len(sorted_image_filenames), prefix='    分析并计算尺寸:', suffix='完成', length=40)
    for i, filename in enumerate(sorted_image_filenames):
        filepath = os.path.join(source_image_dir, filename)
        try:
            with Image.open(filepath) as img:
                if img.width != target_width:
                    new_height = int(img.height * (target_width / img.width))
                else:
                    new_height = img.height
                
                images_data.append({
                    "path": filepath,
                    "width": img.width,
                    "height": img.height,
                    "new_height": new_height
                })
                total_height += new_height
        except Exception as e:
            print(f"\n    警告: 打开或读取图片 '{filename}' 失败: {e}。已跳过。")
            continue
        print_progress_bar(i + 1, len(sorted_image_filenames), prefix='    分析并计算尺寸:', suffix='完成', length=40)

    if not images_data:
        print("    没有有效的图片可供合并。")
        return None

    if target_width == 0 or total_height == 0:
        print(f"    计算得到的画布尺寸为零 ({target_width}x{total_height})，无法创建长图。")
        return None

    merged_canvas = Image.new('RGB', (target_width, total_height), (255, 255, 255))
    current_y_offset = 0

    print_progress_bar(0, len(images_data), prefix='    粘贴图片:    ', suffix='完成', length=40)
    for i, item_info in enumerate(images_data):
        try:
            with Image.open(item_info["path"]) as img:
                img_rgb = img.convert("RGB")
                
                if img_rgb.width != target_width:
                    img_to_paste = img_rgb.resize((target_width, item_info['new_height']), Image.Resampling.LANCZOS)
                else:
                    img_to_paste = img_rgb

                merged_canvas.paste(img_to_paste, (0, current_y_offset))
                current_y_offset += item_info['new_height']
        except Exception as e:
            print(f"\n    警告: 粘贴图片 '{item_info['path']}' 失败: {e}。")
            pass
        print_progress_bar(i + 1, len(images_data), prefix='    粘贴图片:    ', suffix='完成', length=40)

    try:
        merged_canvas.save(output_long_image_path, format='PNG')
        print(f"    成功合并图片到: {output_long_image_path}")
        return output_long_image_path
    except Exception as e:
        print(f"    错误: 保存合并后的长图失败: {e}")
        return None

def split_long_image_v3(long_image_path, output_split_dir, min_band_height, variance_threshold):
    """
    [V3 核心逻辑 - NumPy 优化] 通过分析每一行像素的“颜色方差”来识别和分割图像。
    此版本使用 NumPy 进行高速向量化计算，并提供进度反馈。
    """
    print(f"\n  --- 步骤 2 (V3 - NumPy): 按颜色方差分割长图 '{os.path.basename(long_image_path)}' ---")
    if not os.path.isfile(long_image_path):
        print(f"    错误: 长图路径 '{long_image_path}' 未找到。")
        return []

    os.makedirs(output_split_dir, exist_ok=True)
    split_image_paths = []

    try:
        img = Image.open(long_image_path).convert("RGB")
        img_width, img_height = img.size

        if img_height == 0 or img_width == 0:
            print(f"    图片 '{os.path.basename(long_image_path)}' 尺寸为零，无法分割。")
            return []

        print("    正在将图片加载到内存以进行高速分析...")
        img_array = np.array(img, dtype=np.int16)

        chunk_size = 5000
        all_variances = []
        
        print_progress_bar(0, img_height, prefix='    分析行颜色方差:', suffix='完成', length=40)
        for y_start in range(0, img_height, chunk_size):
            y_end = min(y_start + chunk_size, img_height)
            chunk = img_array[y_start:y_end, :, :]
            
            chunk_variances = np.ptp(chunk, axis=1).sum(axis=1)
            all_variances.append(chunk_variances)
            
            print_progress_bar(y_end, img_height, prefix='    分析行颜色方差:', suffix=f'{y_end}/{img_height}', length=40)

        variances = np.concatenate(all_variances)
        
        row_types = np.where(variances <= variance_threshold, 'simple', 'complex')

        blocks = []
        if row_types.size == 0: return []
        
        change_points = np.where(row_types[:-1] != row_types[1:])[0] + 1
        
        last_y = 0
        for y in change_points:
            blocks.append({'type': row_types[last_y], 'start': last_y, 'end': y})
            last_y = y
        blocks.append({'type': row_types[last_y], 'start': last_y, 'end': img_height})
        
        original_basename, _ = os.path.splitext(os.path.basename(long_image_path))
        part_index = 1
        last_cut_y = 0
        
        print(f"    分析完成，共识别出 {len(blocks)} 个内容/空白区块。正在寻找切割点...")

        for i, block in enumerate(blocks):
            if block['type'] == 'simple':
                block_height = block['end'] - block['start']
                if block_height >= min_band_height and i > 0 and i < len(blocks) - 1:
                    cut_point_y = block['start'] + (block_height // 2)
                    
                    segment = img.crop((0, last_cut_y, img_width, cut_point_y))
                    output_filename = f"{original_basename}_split_part_{part_index}.png"
                    output_filepath = os.path.join(output_split_dir, output_filename)
                    
                    segment.save(output_filepath, "PNG")
                    split_image_paths.append(output_filepath)
                    
                    print(f"      在 Y={cut_point_y} 处找到合格空白区 (高度: {block_height}px)，已切割并保存: {output_filename}")

                    part_index += 1
                    last_cut_y = cut_point_y

        if last_cut_y < img_height:
            segment = img.crop((0, last_cut_y, img_width, img_height))
            output_filename = f"{original_basename}_split_part_{part_index}.png"
            output_filepath = os.path.join(output_split_dir, output_filename)
            segment.save(output_filepath, "PNG")
            split_image_paths.append(output_filepath)

        if not split_image_paths and img_height > 0:
            print(f"    V3未能找到任何合格的空白区进行分割。")
            print(f"    将使用原始合并长图进行下一步。")
            dest_path = os.path.join(output_split_dir, os.path.basename(long_image_path))
            shutil.copy2(long_image_path, dest_path)
            return [dest_path]

    except Exception as e:
        print(f"    分割图片 '{os.path.basename(long_image_path)}' 时发生严重错误: {e}")
        traceback.print_exc()

    return natsort.natsorted(split_image_paths)


def _merge_image_list_for_repack(image_paths, output_path):
    """
    一个专门用于重打包的内部合并函数，采用无边框逻辑。
    """
    if not image_paths:
        return False
    
    images_data = []
    total_height = 0
    target_width = 0
    
    for path in image_paths:
        try:
            with Image.open(path) as img:
                if target_width == 0:
                    target_width = img.width
                images_data.append({"path": path, "height": img.height})
                total_height += img.height
        except Exception:
            continue
            
    if not images_data or target_width == 0: return False

    merged_canvas = Image.new('RGB', (target_width, total_height), (255, 255, 255))
    current_y = 0
    for item in images_data:
        with Image.open(item["path"]) as img:
            img_rgb = img.convert("RGB")
            merged_canvas.paste(img_rgb, (0, current_y))
            current_y += item["height"]
            
    merged_canvas.save(output_path, "PNG")
    return True

# ▼▼▼ [V3.5 函数已重写] ▼▼▼
def repack_split_images(split_image_paths, output_dir, base_filename, max_size_mb, max_height_px):
    """
    [V3.5 逻辑] 将分割后的图片按“双重限制”（文件大小和像素高度）重新打包合并。
    """
    print(f"\n  --- 步骤 2.5: 按双重限制重打包 (上限: {max_size_mb}MB, {max_height_px}px) ---")
    if not split_image_paths:
        print("    没有可供重打包的图片。")
        return []

    max_size_bytes = max_size_mb * 1024 * 1024
    os.makedirs(output_dir, exist_ok=True)
    
    repacked_paths = []
    current_bucket_paths = []
    current_bucket_size = 0
    current_bucket_height = 0
    repack_index = 1
    
    total_files = len(split_image_paths)
    print_progress_bar(0, total_files, prefix='    处理图片块:', suffix='开始', length=40)

    for i, img_path in enumerate(split_image_paths):
        if not os.path.exists(img_path): continue
        
        try:
            file_size = os.path.getsize(img_path)
            with Image.open(img_path) as img:
                img_height = img.height
        except Exception as e:
            print(f"\n    警告: 无法读取图片 '{os.path.basename(img_path)}' 的属性: {e}")
            continue
        
        # 检查加入新图片后是否会超出任一限制
        if current_bucket_paths and \
           ((current_bucket_size + file_size > max_size_bytes) or \
            (current_bucket_height + img_height > max_height_px)):
            
            # 先打包当前的桶
            output_filename = f"{base_filename}_repacked_{repack_index}.png"
            output_path = os.path.join(output_dir, output_filename)
            if _merge_image_list_for_repack(current_bucket_paths, output_path):
                repacked_paths.append(output_path)
            repack_index += 1
            
            # 用当前文件开始一个新的桶
            current_bucket_paths = [img_path]
            current_bucket_size = file_size
            current_bucket_height = img_height
        else:
            # 桶还有空间，加入当前文件
            current_bucket_paths.append(img_path)
            current_bucket_size += file_size
            current_bucket_height += img_height
        
        print_progress_bar(i + 1, total_files, prefix='    处理图片块:', suffix=f'完成 {repack_index-1} 个包', length=40)

    # 处理循环结束后所有剩余在桶中的图片
    if current_bucket_paths:
        output_filename = f"{base_filename}_repacked_{repack_index}.png"
        output_path = os.path.join(output_dir, output_filename)
        if _merge_image_list_for_repack(current_bucket_paths, output_path):
            repacked_paths.append(output_path)
    
    print_progress_bar(total_files, total_files, prefix='    处理图片块:', suffix='全部完成', length=40)
    print(f"    重打包完成，共生成 {len(repacked_paths)} 个新的图片块。")

    print("    ... 正在清理原始分割文件 ...")
    for path in split_image_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            print(f"      无法删除原始文件 {os.path.basename(path)}: {e}")

    return natsort.natsorted(repacked_paths)


def create_pdf_from_images(image_paths_list, output_pdf_dir, pdf_filename_only,
                           target_page_width_px, image_jpeg_quality, pdf_target_dpi):
    """从图片片段列表创建PDF文件，并跳过尺寸超限的图片。"""
    print(f"\n  --- 步骤 3: 从图片片段创建 PDF '{pdf_filename_only}' ---")
    if not image_paths_list:
        print("    没有图片片段可用于创建 PDF。")
        return None

    safe_image_paths = []
    print("    正在进行PDF兼容性尺寸预检...")
    for image_path in image_paths_list:
        try:
            with Image.open(image_path) as img:
                if img.height > 65500 or img.width > 65500:
                    print(f"\n    警告: 图片 '{os.path.basename(image_path)}' 的尺寸 ({img.width}x{img.height}) 超过了PDF生成库的最大限制(65500px)。")
                    print("           此图片将被跳过，不会包含在最终的PDF中。")
                else:
                    safe_image_paths.append(image_path)
        except Exception as e:
            print(f"\n    警告: 无法打开图片 '{os.path.basename(image_path)}' 进行尺寸检查: {e}")
    
    if not safe_image_paths:
        print("    没有尺寸合格的图片可用于创建 PDF。")
        return None

    os.makedirs(output_pdf_dir, exist_ok=True)
    pdf_full_path = os.path.join(output_pdf_dir, pdf_filename_only)
    
    images_for_pdf = []
    
    total_images_for_pdf = len(safe_image_paths)
    if total_images_for_pdf > 0:
        print_progress_bar(0, total_images_for_pdf, prefix='    准备PDF图片:', suffix='完成', length=40)

    for i, image_path in enumerate(safe_image_paths):
        try:
            img = Image.open(image_path)
            
            if img.mode != 'RGB':
                images_for_pdf.append(img.convert('RGB'))
                img.close()
            else:
                images_for_pdf.append(img)

        except Exception as e:
            print(f"\n    警告: 处理PDF图片 '{os.path.basename(image_path)}' 失败: {e}。已跳过。")
            pass
        print_progress_bar(i + 1, total_images_for_pdf, prefix='    准备PDF图片:', suffix='完成', length=40)

    if not images_for_pdf:
        print("    没有图片成功处理以包含在PDF中。")
        return None

    try:
        first_image_to_save = images_for_pdf[0]
        images_to_append = images_for_pdf[1:]

        first_image_to_save.save(
            pdf_full_path,
            save_all=True,
            append_images=images_to_append,
            resolution=float(pdf_target_dpi),
            quality=image_jpeg_quality,
            optimize=True
        )
        print(f"    成功创建 PDF: {pdf_full_path}")
        return pdf_full_path
    except Exception as e:
        print(f"    保存 PDF 失败: {e}")
        return None
    finally:
        for img_obj in images_for_pdf:
            try:
                img_obj.close()
            except Exception:
                pass


def cleanup_intermediate_dirs(long_img_dir, split_img_dir):
    """清理指定的中间文件目录。"""
    print(f"\n  --- 步骤 4: 清理中间文件 ---")
    for dir_to_remove, dir_name_for_log in [(long_img_dir, "长图合并"), (split_img_dir, "图片分割与打包")]:
        if os.path.isdir(dir_to_remove):
            try:
                shutil.rmtree(dir_to_remove)
                print(f"    已删除中间 {dir_name_for_log} 文件夹: {dir_to_remove}")
            except Exception as e:
                print(f"    删除文件夹 '{dir_to_remove}' 失败: {e}")


if __name__ == "__main__":
    print("自动化图片批量处理流程脚本启动！ (V3 - 双重打包限制)")
    print("注意: 此版本需要 numpy 库。如果未安装，请运行: pip install numpy")
    print("流程：1.合并 -> 2.按颜色方差分割 -> 2.5.按双重限制重打包 -> 3.创建PDF -> 4.清理")
    print("-" * 70)
    
    def load_default_path_from_settings():
        """从共享设定档中读取预设工作目录。"""
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir else "."
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return os.path.join(os.path.expanduser("~"), "Downloads")
    
    default_root_dir_name = load_default_path_from_settings()

    root_input_dir = ""
    while True:
        prompt_message = (
            f"请输入包含多个一级子文件夹的【根目录】路径。\n"
            f"(直接按 Enter 键，将使用默认路径 '{default_root_dir_name}'): "
        )
        user_provided_path = input(prompt_message).strip()
        current_path_to_check = user_provided_path if user_provided_path else default_root_dir_name
        if not user_provided_path:
            print(f"使用默认路径: {current_path_to_check}")

        abs_path_to_check = os.path.abspath(current_path_to_check)
        if os.path.isdir(abs_path_to_check):
            root_input_dir = abs_path_to_check
            print(f"已选定根处理目录: {root_input_dir}")
            break
        else:
            print(f"错误：路径 '{abs_path_to_check}' 不是一个有效的目录或不存在。")

    overall_pdf_output_dir = os.path.join(root_input_dir, FINAL_PDFS_SUBDIR_NAME)
    os.makedirs(overall_pdf_output_dir, exist_ok=True)

    subdirectories = [d for d in os.listdir(root_input_dir)
                      if os.path.isdir(os.path.join(root_input_dir, d)) and \
                         d not in [MERGED_LONG_IMAGE_SUBDIR_NAME, SPLIT_IMAGES_SUBDIR_NAME, FINAL_PDFS_SUBDIR_NAME] and \
                         not d.startswith('.')]

    if not subdirectories:
        print(f"\n在根目录 '{root_input_dir}' 下没有找到可处理的一级子文件夹。")
        sys.exit()

    sorted_subdirectories = natsort.natsorted(subdirectories)
    print(f"\n将按顺序处理以下 {len(sorted_subdirectories)} 个子文件夹: {', '.join(sorted_subdirectories)}")

    total_subdirs_to_process = len(sorted_subdirectories)
    failed_subdirs_list = []

    for i, subdir_name in enumerate(sorted_subdirectories):
        print_progress_bar(i, total_subdirs_to_process, prefix="总进度:", suffix=f'{subdir_name}', length=40)
        print(f"\n\n{'='*10} 开始处理子文件夹: {subdir_name} ({i+1}/{total_subdirs_to_process}) {'='*10}")
        
        current_processing_subdir = os.path.join(root_input_dir, subdir_name)

        path_long_image_output_dir_current = os.path.join(current_processing_subdir, MERGED_LONG_IMAGE_SUBDIR_NAME)
        path_split_images_output_dir_current = os.path.join(current_processing_subdir, SPLIT_IMAGES_SUBDIR_NAME)
        current_long_image_filename = f"{subdir_name}_{LONG_IMAGE_FILENAME_BASE}.png"
        
        if os.path.isdir(path_long_image_output_dir_current):
            print(f"    检测到旧的合并目录，正在清理以强制重新合并...")
            shutil.rmtree(path_long_image_output_dir_current)

        created_long_image_path = merge_to_long_image(
            current_processing_subdir,
            path_long_image_output_dir_current,
            current_long_image_filename,
            PDF_TARGET_PAGE_WIDTH_PIXELS
        )

        pdf_created_for_this_subdir = False
        if created_long_image_path:
            if os.path.isdir(path_split_images_output_dir_current):
                print(f"    检测到旧的分割目录，正在清理以强制重新分割...")
                shutil.rmtree(path_split_images_output_dir_current)
            
            split_segment_paths = split_long_image_v3(
                created_long_image_path,
                path_split_images_output_dir_current,
                MIN_SOLID_COLOR_BAND_HEIGHT,
                COLOR_VARIANCE_THRESHOLD
            )

            # [V3.5] 调用重打包函数时，传入新的高度限制参数
            repacked_final_paths = repack_split_images(
                split_segment_paths,
                path_split_images_output_dir_current,
                base_filename=subdir_name,
                max_size_mb=MAX_REPACKED_FILESIZE_MB,
                max_height_px=MAX_REPACKED_PAGE_HEIGHT_PX
            )

            if repacked_final_paths:
                dynamic_pdf_filename_for_subdir = subdir_name + ".pdf"
                created_pdf_path = create_pdf_from_images(
                    repacked_final_paths,
                    overall_pdf_output_dir,
                    dynamic_pdf_filename_for_subdir,
                    PDF_TARGET_PAGE_WIDTH_PIXELS,
                    PDF_IMAGE_JPEG_QUALITY,
                    PDF_DPI
                )
                if created_pdf_path:
                    pdf_created_for_this_subdir = True

        if pdf_created_for_this_subdir:
            cleanup_intermediate_dirs(path_long_image_output_dir_current, path_split_images_output_dir_current)
        else:
            print(f"  子文件夹 '{subdir_name}' 未能成功生成PDF，将保留中间文件。")
            failed_subdirs_list.append(subdir_name)

        print(f"{'='*10} 子文件夹 '{subdir_name}' 处理完毕 {'='*10}")
        print_progress_bar(i + 1, total_subdirs_to_process, prefix="总进度:", suffix='完成', length=40)

    print("\n" + "=" * 70)
    print("【任务总结报告】")
    print("-" * 70)
    
    success_count = total_subdirs_to_process - len(failed_subdirs_list)
    
    print(f"总计处理项目 (子文件夹): {total_subdirs_to_process} 个")
    print(f"  - ✅ 成功: {success_count} 个")
    print(f"  - ❌ 失败: {len(failed_subdirs_list)} 个")
    
    if failed_subdirs_list:
        print("\n失败项目列表:")
        for failed_dir in failed_subdirs_list:
            print(f"  - {failed_dir}")
    
    print("-" * 70)
    print(f"所有成功生成的PDF文件（如有）已保存在: {overall_pdf_output_dir}")
    print("脚本执行完毕。")