import os
import shutil
from PIL import Image, ImageFile
import natsort
import sys
from collections import Counter
import math
import traceback
import json

# --- 全局配置 ---
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

MERGED_LONG_IMAGE_SUBDIR_NAME = "merged_long_img"
SPLIT_IMAGES_SUBDIR_NAME = "split_by_solid_band"
SUCCESS_MOVE_SUBDIR_NAME = "IMG"  # 成功处理的文件夹将被移动到此目录

LONG_IMAGE_FILENAME_BASE = "stitched_long_strip"
IMAGE_EXTENSIONS_FOR_MERGE = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')

MIN_SOLID_COLOR_BAND_HEIGHT = 50
COLOR_MATCH_TOLERANCE = 45

# 韩漫常见背景色配置（已扩展）
SPLIT_BAND_COLORS_RGB = [
    # 基础色
    (255, 255, 255),  # 纯白色
    (0, 0, 0),        # 纯黑色
    
    # 韩漫常见的浅色背景
    (248, 248, 248),  # 浅灰白色
    (240, 240, 240),  # 灰白色
    (250, 250, 250),  # 接近白色
    (245, 245, 245),  # 淡灰色
    (252, 252, 252),  # 极浅灰色
    (242, 242, 242),  # 浅灰色
    (238, 238, 238),  # 中浅灰色
    (235, 235, 235),  # 银灰色
    (230, 230, 230),  # 浅银灰色
    (225, 225, 225),  # 中银灰色
    (220, 220, 220),  # 深银灰色
    (215, 215, 215),  # 浅钢灰色
    (210, 210, 210),  # 钢灰色
    (205, 205, 205),  # 深钢灰色
    (200, 200, 200),  # 中灰色
    
    # 韩漫常见的米色/奶油色背景
    (255, 253, 250),  # 雪白色
    (253, 245, 230),  # 古董白
    (250, 240, 230),  # 亚麻色
    (255, 248, 220),  # 玉米丝色
    (255, 250, 240),  # 花白色
    (253, 245, 230),  # 旧蕾丝色
    (245, 245, 220),  # 米色
    (255, 228, 196),  # 桃仁色
    
    # 韩漫常见的淡粉色背景
    (255, 240, 245),  # 薰衣草红
    (255, 228, 225),  # 薄雾玫瑰
    (255, 218, 185),  # 桃色
    (255, 239, 213),  # 木瓜色
    (255, 235, 205),  # 白杏色
    
    # 韩漫常见的淡蓝色背景
    (240, 248, 255),  # 爱丽丝蓝
    (230, 230, 250),  # 薰衣草色
    (248, 248, 255),  # 幽灵白
    (245, 245, 245),  # 白烟色
    (220, 220, 220),  # 淡灰色
    
    # 韩漫常见的淡绿色背景
    (240, 255, 240),  # 蜜瓜色
    (245, 255, 250),  # 薄荷奶油色
    (240, 255, 255),  # 天蓝色
    
    # 韩漫常见的深色背景
    (195, 195, 195),  # 深中灰色
    (190, 190, 190),  # 暗灰色
    (185, 185, 185),  # 深暗灰色
    (180, 180, 180),  # 灰色
    (175, 175, 175),  # 深灰色
    (170, 170, 170),  # 暗深灰色
    (165, 165, 165),  # 炭灰色
    (160, 160, 160),  # 深炭灰色
    (155, 155, 155),  # 暗炭灰色
    (150, 150, 150),  # 中炭灰色
    (145, 145, 145),  # 深中炭灰色
    (140, 140, 140),  # 暗中炭灰色
    (135, 135, 135),  # 深暗炭灰色
    (130, 130, 130),  # 极深炭灰色
    (125, 125, 125),  # 深极炭灰色
    (120, 120, 120),  # 暗极炭灰色
    (115, 115, 115),  # 深暗极炭灰色
    (110, 110, 110),  # 极暗炭灰色
    (105, 105, 105),  # 深极暗炭灰色
    (100, 100, 100),  # 暗极暗炭灰色
    (95, 95, 95),     # 深暗极暗炭灰色
    (90, 90, 90),     # 极深暗炭灰色
    (85, 85, 85),     # 深极深暗炭灰色
    (80, 80, 80),     # 暗极深暗炭灰色
    (75, 75, 75),     # 深暗极深暗炭灰色
    (70, 70, 70),     # 极暗极深炭灰色
    (65, 65, 65),     # 深极暗极深炭灰色
    (60, 60, 60),     # 暗极暗极深炭灰色
    (55, 55, 55),     # 深暗极暗极深炭灰色
    (50, 50, 50),     # 极深暗极暗炭灰色
    (45, 45, 45),     # 深极深暗极暗炭灰色
    (40, 40, 40),     # 暗极深暗极暗炭灰色
    (35, 35, 35),     # 深暗极深暗极暗炭灰色
    (30, 30, 30),     # 极暗极深暗极暗炭灰色
    (25, 25, 25),     # 深极暗极深暗极暗炭灰色
    (20, 20, 20),     # 暗极暗极深暗极暗炭灰色
    (15, 15, 15),     # 深暗极暗极深暗极暗炭灰色
    (10, 10, 10),     # 极深暗极暗极深暗极暗炭灰色
    (5, 5, 5),        # 接近黑色
]

PDF_TARGET_PAGE_WIDTH_PIXELS = 1500
PDF_IMAGE_JPEG_QUALITY = 85
PDF_DPI = 300
# --- 全局配置结束 ---


def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
    """
    在终端打印进度条。
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


def merge_to_long_image(source_project_dir, output_long_image_dir, long_image_filename_only):
    """
    递归查找源项目目录及其子目录中的所有图片，
    进行自然排序，然后垂直合并成一个PNG长图。
    """
    print(f"\n  --- 步骤 1: 合并项目 '{os.path.basename(source_project_dir)}' 中的所有图片以制作长图 ---")
    if not os.path.isdir(source_project_dir):
        print(f"    错误: 源项目目录 '{source_project_dir}' 未找到。")
        return None

    os.makedirs(output_long_image_dir, exist_ok=True)
    output_long_image_path = os.path.join(output_long_image_dir, long_image_filename_only)

    print(f"    ... 正在递归扫描 '{os.path.basename(source_project_dir)}' 及其所有子文件夹以查找图片 ...")
    image_filepaths = []
    try:
        for dirpath, _, filenames in os.walk(source_project_dir):
            # 确保不扫描脚本自己创建的中间文件夹
            if MERGED_LONG_IMAGE_SUBDIR_NAME in dirpath or SPLIT_IMAGES_SUBDIR_NAME in dirpath:
                continue
            
            for filename in filenames:
                if filename.lower().endswith(IMAGE_EXTENSIONS_FOR_MERGE) and not filename.startswith('.'):
                    image_filepaths.append(os.path.join(dirpath, filename))
    except Exception as e:
        print(f"    错误: 扫描目录 '{source_project_dir}' 时发生错误: {e}")
        return None
        
    if not image_filepaths:
        print(f"    在 '{os.path.basename(source_project_dir)}' 及其子目录中未找到符合条件的图片。")
        return None

    # 对收集到的所有完整路径进行自然排序
    sorted_image_filepaths = natsort.natsorted(image_filepaths)

    images_data = []
    total_calculated_height = 0
    max_calculated_width = 0

    total_files_to_analyze = len(sorted_image_filepaths)
    if total_files_to_analyze > 0:
        print_progress_bar(0, total_files_to_analyze, prefix='    分析图片尺寸:', suffix='完成', length=40)
    
    for i, filepath in enumerate(sorted_image_filepaths):
        try:
            with Image.open(filepath) as img:
                images_data.append({
                    "path": filepath,
                    "width": img.width,
                    "height": img.height
                })
                total_calculated_height += img.height
                if img.width > max_calculated_width:
                    max_calculated_width = img.width
        except Exception as e:
            print(f"\n    警告: 打开或读取图片 '{os.path.basename(filepath)}' 失败: {e}。已跳过。")
            continue
        if total_files_to_analyze > 0:
            print_progress_bar(i + 1, total_files_to_analyze, prefix='    分析图片尺寸:', suffix='完成', length=40)

    if not images_data:
        print("    没有有效的图片可供合并。")
        return None

    if max_calculated_width == 0 or total_calculated_height == 0:
        print(f"    计算出的画布尺寸为零 ({max_calculated_width}x{total_calculated_height})，无法创建长图。")
        return None

    merged_canvas = Image.new('RGBA', (max_calculated_width, total_calculated_height), (0, 0, 0, 0))
    current_y_offset = 0

    total_files_to_paste = len(images_data)
    if total_files_to_paste > 0:
        print_progress_bar(0, total_files_to_paste, prefix='    粘贴图片:    ', suffix='完成', length=40)
    for i, item_info in enumerate(images_data):
        try:
            with Image.open(item_info["path"]) as img:
                img_to_paste = img.convert("RGBA")
                x_offset = (max_calculated_width - img_to_paste.width) // 2
                merged_canvas.paste(img_to_paste, (x_offset, current_y_offset), img_to_paste if img_to_paste.mode == 'RGBA' else None)
                current_y_offset += item_info["height"]
        except Exception as e:
            print(f"\n    警告: 粘贴图片 '{item_info['path']}' 失败: {e}。")
            pass
        if total_files_to_paste > 0:
            print_progress_bar(i + 1, total_files_to_paste, prefix='    粘贴图片:    ', suffix='完成', length=40)

    try:
        merged_canvas.save(output_long_image_path, format='PNG')
        print(f"    成功合并图片到: {output_long_image_path}")
        return output_long_image_path
    except Exception as e:
        print(f"    错误: 保存合并后的长图失败: {e}")
        return None


# 注意：原 detect_and_add_background_colors 函数已删除
# 现在直接使用预设的韩漫常见背景色，提高速度和效率

def are_colors_close(color1, color2, tolerance):
    """根据欧氏距离检查两种RGB颜色是否接近。"""
    if tolerance == 0:
        return color1 == color2
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    distance = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
    return distance <= tolerance

def is_solid_color_row(pixels, y, width, solid_colors_list, tolerance):
    """检查给定行是否为纯色带，允许一定的容差。"""
    if width == 0:
        return False

    first_pixel_rgb = pixels[0, y][:3]
    
    base_color_match = None
    for base_color in solid_colors_list:
        if are_colors_close(first_pixel_rgb, base_color, tolerance):
            base_color_match = first_pixel_rgb
            break
            
    if base_color_match is None:
        return False
        
    for x in range(1, width):
        if not are_colors_close(pixels[x, y][:3], base_color_match, tolerance):
            return False
            
    return True

def split_long_image(long_image_path, output_split_dir, min_solid_band_height, band_colors_list, tolerance):
    """基于在足够高的纯色带后找到内容行的逻辑来分割长图。"""
    print(f"\n  --- 步骤 2: 按纯色带分割长图 '{os.path.basename(long_image_path)}' ---")
    if not os.path.isfile(long_image_path):
        print(f"    错误: 长图路径 '{long_image_path}' 未找到。")
        return []

    os.makedirs(output_split_dir, exist_ok=True)
    split_image_paths = []

    try:
        if min_solid_band_height < 1: min_solid_band_height = 1

        img = Image.open(long_image_path).convert("RGBA")
        pixels = img.load()
        img_width, img_height = img.size

        if img_height == 0 or img_width == 0:
            print(f"    图片 '{os.path.basename(long_image_path)}' 尺寸为零，无法分割。")
            return []

        original_basename, _ = os.path.splitext(os.path.basename(long_image_path))
        part_index = 1
        current_segment_start_y = 0
        solid_band_after_last_content_start_y = -1

        print_progress_bar(0, img_height, prefix='    扫描长图:    ', suffix='完成', length=40)

        for y in range(img_height):
            print_progress_bar(y + 1, img_height, prefix='    扫描长图:    ', suffix=f'第 {y+1}/{img_height} 行', length=40)

            is_solid = is_solid_color_row(pixels, y, img_width, band_colors_list, tolerance)

            if not is_solid: # 这是一个 "内容" 行
                if solid_band_after_last_content_start_y != -1:
                    solid_band_height = y - solid_band_after_last_content_start_y
                    if solid_band_height >= min_solid_band_height:
                        cut_point_y = solid_band_after_last_content_start_y + (solid_band_height // 2)
                        if cut_point_y > current_segment_start_y:
                            segment = img.crop((0, current_segment_start_y, img_width, cut_point_y))
                            output_filename = f"{original_basename}_split_part_{part_index}.png"
                            output_filepath = os.path.join(output_split_dir, output_filename)
                            try:
                                segment.save(output_filepath, "PNG")
                                split_image_paths.append(output_filepath)
                                part_index += 1
                            except Exception as e_save:
                                print(f"      保存分割片段 '{output_filename}' 失败: {e_save}")
                        current_segment_start_y = cut_point_y
                solid_band_after_last_content_start_y = -1
            else: # 这是一个 "纯色" 行
                if solid_band_after_last_content_start_y == -1:
                    solid_band_after_last_content_start_y = y

        if current_segment_start_y < img_height:
            segment = img.crop((0, current_segment_start_y, img_width, img_height))
            if segment.height > 10: # 避免保存过小的切片
                output_filename = f"{original_basename}_split_part_{part_index}.png"
                output_filepath = os.path.join(output_split_dir, output_filename)
                try:
                    segment.save(output_filepath, "PNG")
                    split_image_paths.append(output_filepath)
                except Exception as e_save:
                     print(f"      保存最后一个分割片段 '{output_filename}' 失败: {e_save}")

        if not split_image_paths and img_height > 0:
            print(f"    未能根据指定的纯色带分割 '{os.path.basename(long_image_path)}'。")
            print(f"    将使用原始合并长图进行下一步。")
            shutil.copy2(long_image_path, os.path.join(output_split_dir, os.path.basename(long_image_path)))
            return [os.path.join(output_split_dir, os.path.basename(long_image_path))]

    except Exception as e:
        print(f"    分割图片 '{os.path.basename(long_image_path)}' 时发生错误: {e}")
        traceback.print_exc()

    return natsort.natsorted(split_image_paths)


def _merge_image_list_for_repack(image_paths, output_path):
    """一个专门用于重打包的内部辅助函数。"""
    if not image_paths:
        return False
    
    images_data = []
    total_height = 0
    max_width = 0
    for path in image_paths:
        try:
            with Image.open(path) as img:
                images_data.append({"path": path, "width": img.width, "height": img.height})
                total_height += img.height
                if img.width > max_width:
                    max_width = img.width
        except Exception:
            continue
            
    if not images_data: return False

    merged_canvas = Image.new('RGBA', (max_width, total_height))
    current_y = 0
    for item in images_data:
        with Image.open(item["path"]) as img:
            img_to_paste = img.convert("RGBA")
            x_offset = (max_width - item["width"]) // 2
            merged_canvas.paste(img_to_paste, (x_offset, current_y), img_to_paste)
            current_y += item["height"]
            
    merged_canvas.save(output_path, "PNG")
    return True


def repack_split_images(split_image_paths, output_dir, base_filename, max_size_mb=8):
    """
    将分割后的图片按大小重新打包合并。
    - 合并后的图片块上限为 max_size_mb。
    - 如果单张图片已超过上限，则直接保留，不参与合并。
    """
    print(f"\n  --- 步骤 2.5: 重打包图片块 (目标大小: < {max_size_mb}MB) ---")
    if not split_image_paths:
        print("    没有可供重打包的图片。")
        return []

    max_size_bytes = max_size_mb * 1024 * 1024
    
    repacked_paths = []
    current_bucket = []
    current_bucket_size = 0
    repack_index = 1
    
    total_files = len(split_image_paths)
    print_progress_bar(0, total_files, prefix='    处理图片块: ', suffix='开始', length=40)

    for i, img_path in enumerate(split_image_paths):
        if not os.path.exists(img_path): continue
        
        file_size = os.path.getsize(img_path)
        
        # 情况1: 单个文件已经超过上限
        if file_size > max_size_bytes:
            # 首先，打包当前桶中已有的图片
            if current_bucket:
                output_filename = f"{base_filename}_repacked_{repack_index}.png"
                output_path = os.path.join(output_dir, output_filename)
                if _merge_image_list_for_repack(current_bucket, output_path):
                    repacked_paths.append(output_path)
                    repack_index += 1
                current_bucket = []
                current_bucket_size = 0
            
            # 然后，直接复制这个过大的文件
            output_filename_oversized = f"{base_filename}_repacked_{repack_index}.png"
            output_path_oversized = os.path.join(output_dir, output_filename_oversized)
            shutil.copy2(img_path, output_path_oversized)
            repacked_paths.append(output_path_oversized)
            repack_index += 1
            print_progress_bar(i + 1, total_files, prefix='    处理图片块: ', suffix=f'{repack_index-1} 个包完成', length=40)
            continue # 处理下一个文件

        # 情况2: 将当前文件加入桶中会超出上限
        if current_bucket and (current_bucket_size + file_size) > max_size_bytes:
            # 先打包当前的桶
            output_filename = f"{base_filename}_repacked_{repack_index}.png"
            output_path = os.path.join(output_dir, output_filename)
            if _merge_image_list_for_repack(current_bucket, output_path):
                repacked_paths.append(output_path)
                repack_index += 1
            
            # 用当前文件开始一个新的桶
            current_bucket = [img_path]
            current_bucket_size = file_size
        else:
            # 情况3: 桶还有空间，加入当前文件
            current_bucket.append(img_path)
            current_bucket_size += file_size
        
        print_progress_bar(i + 1, total_files, prefix='    处理图片块: ', suffix=f'{repack_index-1} 个包完成', length=40)

    # 处理循环结束后所有剩余在桶中的图片
    if current_bucket:
        output_filename = f"{base_filename}_repacked_{repack_index}.png"
        output_path = os.path.join(output_dir, output_filename)
        if _merge_image_list_for_repack(current_bucket, output_path):
            repacked_paths.append(output_path)
    
    print_progress_bar(total_files, total_files, prefix='    处理图片块: ', suffix='全部完成', length=40)
    print(f"    重打包完成。生成了 {len(repacked_paths)} 个新的图片块。")

    # 清理掉原始的、未打包的分割图片
    print("    ... 正在清理原始分割文件 ...")
    for path in split_image_paths:
        try:
            os.remove(path)
        except OSError as e:
            print(f"      无法删除原始文件 {os.path.basename(path)}: {e}")

    return natsort.natsorted(repacked_paths)

def create_pdf_from_images(image_paths_list, output_pdf_dir, pdf_filename_only,
                           target_page_width_px, image_jpeg_quality, pdf_target_dpi):
    """从图片路径列表创建PDF文件。"""
    print(f"\n  --- 步骤 3: 从图片块创建 PDF '{pdf_filename_only}' ---")
    if not image_paths_list:
        print("    没有可用的图片块来创建 PDF。")
        return None

    pdf_full_path = os.path.join(output_pdf_dir, pdf_filename_only)
    
    processed_pil_images = []
    
    total_images_for_pdf = len(image_paths_list)
    if total_images_for_pdf > 0:
        print_progress_bar(0, total_images_for_pdf, prefix='    处理PDF图片:', suffix='完成', length=40)

    for i, image_path in enumerate(image_paths_list):
        try:
            with Image.open(image_path) as img:
                img_to_process = img
                if img_to_process.mode not in ['RGB', 'L']:
                    background = Image.new("RGB", img_to_process.size, (255, 255, 255))
                    try:
                        mask = img_to_process.getchannel('A')
                        background.paste(img_to_process, mask=mask)
                    except (ValueError, KeyError):
                        background.paste(img_to_process.convert("RGB"))
                    img_to_process = background
                elif img_to_process.mode == 'L':
                    img_to_process = img_to_process.convert('RGB')

                original_width, original_height = img_to_process.size
                if original_width == 0 or original_height == 0:
                    print(f"    警告: 图片 '{os.path.basename(image_path)}' 尺寸为零，已跳过。")
                    if total_images_for_pdf > 0: print_progress_bar(i + 1, total_images_for_pdf, prefix='    处理PDF图片:', suffix='完成', length=40)
                    continue
                
                if original_width > target_page_width_px:
                    ratio = target_page_width_px / original_width
                    new_height = int(original_height * ratio)
                    if new_height <=0: new_height = 1
                    img_resized = img_to_process.resize((target_page_width_px, new_height), Image.Resampling.LANCZOS)
                else:
                    img_resized = img_to_process.copy()

                processed_pil_images.append(img_resized)

        except Exception as e:
            print(f"\n    警告: 处理PDF图片 '{os.path.basename(image_path)}' 失败: {e}。已跳过。")
            pass
        if total_images_for_pdf > 0:
            print_progress_bar(i + 1, total_images_for_pdf, prefix='    处理PDF图片:', suffix='完成', length=40)

    if not processed_pil_images:
        print("    没有图片被成功处理以包含在PDF中。")
        return None

    try:
        first_image_to_save = processed_pil_images[0]
        images_to_append = processed_pil_images[1:]

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
        for img_obj in processed_pil_images:
            try:
                img_obj.close()
            except Exception:
                pass


def cleanup_intermediate_dirs(long_img_dir, split_img_dir):
    """清理指定的中间文件目录。"""
    print(f"\n  --- 步骤 4: 清理中间文件 ---")
    for dir_to_remove, dir_name_for_log in [(long_img_dir, "长图合并"), (split_img_dir, "图片分割与重打包")]:
        if os.path.isdir(dir_to_remove):
            try:
                shutil.rmtree(dir_to_remove)
                print(f"    已删除中间 {dir_name_for_log} 文件夹: {dir_to_remove}")
            except Exception as e:
                print(f"    删除文件夹 '{dir_to_remove}' 失败: {e}")


if __name__ == "__main__":
    print("自动化图片批量处理流程 (V3.6 - 集中式PDF输出文件夹)")
    print("工作流程: 1.合并 -> 2.分割 -> 2.5.重打包 -> 3.创建PDF -> 4.清理 -> 5.移动成功项")
    print("-" * 70)
    
    def load_default_path_from_settings():
        """从共享设置文件中读取默认工作目录。"""
        try:
            # 向上导航两层以找到项目根目录，然后定位到 settings.json
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            # 同时将空或null的 default_work_dir 视为无效
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir else "."
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"警告: 读取 settings.json 失败 ({e})。将使用备用路径。")
            # 如果无法读取设置文件，则提供一个通用的备用路径
            return os.path.join(os.path.expanduser("~"), "Downloads")
    
    default_root_dir_name = load_default_path_from_settings()

    root_input_dir = ""
    while True:
        prompt_message = (
            f"请输入包含一个或多个项目子文件夹的【根目录】路径。\n"
            f"脚本将递归处理每个项目子文件夹中的所有图片。\n"
            f"(直接按 Enter 键将使用默认路径: '{default_root_dir_name}'): "
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
            print(f"错误: 路径 '{abs_path_to_check}' 不是一个有效的目录或不存在。")

    # 根据根目录名称创建唯一的PDF输出文件夹
    root_dir_basename = os.path.basename(os.path.abspath(root_input_dir))
    overall_pdf_output_dir = os.path.join(root_input_dir, f"{root_dir_basename}_pdfs")
    os.makedirs(overall_pdf_output_dir, exist_ok=True)
    
    # 创建用于存放成功处理项目的文件夹
    success_move_target_dir = os.path.join(root_input_dir, SUCCESS_MOVE_SUBDIR_NAME)
    os.makedirs(success_move_target_dir, exist_ok=True)

    # 扫描要处理的项目子文件夹，排除脚本的管理文件夹
    subdirectories = [d for d in os.listdir(root_input_dir)
                      if os.path.isdir(os.path.join(root_input_dir, d)) and \
                         d != SUCCESS_MOVE_SUBDIR_NAME and \
                         d != os.path.basename(overall_pdf_output_dir) and \
                         not d.startswith('.')]

    if not subdirectories:
        print(f"\n在根目录 '{root_input_dir}' 中未找到可处理的项目子文件夹。")
        sys.exit()

    sorted_subdirectories = natsort.natsorted(subdirectories)
    print(f"\n将按顺序处理以下 {len(sorted_subdirectories)} 个项目文件夹: {', '.join(sorted_subdirectories)}")

    total_subdirs_to_process = len(sorted_subdirectories)
    failed_subdirs_list = []

    for i, subdir_name in enumerate(sorted_subdirectories):
        print_progress_bar(i, total_subdirs_to_process, prefix="总进度:", suffix=f'{subdir_name}', length=40)
        print(f"\n\n{'='*10} 开始处理项目文件夹: {subdir_name} ({i+1}/{total_subdirs_to_process}) {'='*10}")
        
        current_processing_subdir = os.path.join(root_input_dir, subdir_name)

        # 中间文件存储在正在处理的项目文件夹内部
        path_long_image_output_dir_current = os.path.join(current_processing_subdir, MERGED_LONG_IMAGE_SUBDIR_NAME)
        path_split_images_output_dir_current = os.path.join(current_processing_subdir, SPLIT_IMAGES_SUBDIR_NAME)
        current_long_image_filename = f"{subdir_name}_{LONG_IMAGE_FILENAME_BASE}.png"

        # 调用修改后的合并函数，它将递归扫描 current_processing_subdir
        created_long_image_path = merge_to_long_image(
            current_processing_subdir,
            path_long_image_output_dir_current,
            current_long_image_filename
        )

        pdf_created_for_this_subdir = False
        if created_long_image_path:
            # 直接使用预设的韩漫常见背景色，提高速度和效率
            print(f"    🎨 使用预设的韩漫常见背景色进行分割，提高速度和效率...")
            
            split_segment_paths = split_long_image(
                created_long_image_path,
                path_split_images_output_dir_current,
                MIN_SOLID_COLOR_BAND_HEIGHT,
                SPLIT_BAND_COLORS_RGB,
                COLOR_MATCH_TOLERANCE
            )

            repacked_final_paths = repack_split_images(
                split_segment_paths,
                path_split_images_output_dir_current,
                base_filename=subdir_name,
                max_size_mb=5
            )

            if repacked_final_paths:
                dynamic_pdf_filename_for_subdir = subdir_name + ".pdf"
                
                # 始终使用唯一的、总体的PDF输出目录
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
            
            print(f"\n  --- 步骤 5: 移动已成功处理的项目文件夹 ---")
            source_folder_to_move = current_processing_subdir
            destination_parent_folder = success_move_target_dir
            
            try:
                print(f"    准备将 '{os.path.basename(source_folder_to_move)}' 移动到 '{os.path.basename(destination_parent_folder)}' 文件夹中...")
                shutil.move(source_folder_to_move, destination_parent_folder)
                moved_path = os.path.join(destination_parent_folder, os.path.basename(source_folder_to_move))
                print(f"    成功移动文件夹至: {moved_path}")
            except Exception as e:
                print(f"    错误: 移动文件夹 '{os.path.basename(source_folder_to_move)}' 失败: {e}")
                if subdir_name not in failed_subdirs_list:
                    failed_subdirs_list.append(f"{subdir_name} (移动失败)")
            
        else:
            print(f"  项目文件夹 '{subdir_name}' 未能成功生成PDF。将保留中间文件和原始文件夹。")
            failed_subdirs_list.append(subdir_name)

        print(f"{'='*10} 项目文件夹 '{subdir_name}' 处理完毕 {'='*10}")
        print_progress_bar(i + 1, total_subdirs_to_process, prefix="总进度:", suffix='完成', length=40)

    print("\n" + "=" * 70)
    print("【任务总结报告】")
    print("-" * 70)
    
    success_count = total_subdirs_to_process - len(failed_subdirs_list)
    
    print(f"总计处理项目 (一级子文件夹): {total_subdirs_to_process} 个")
    print(f"  - ✅ 成功: {success_count} 个")
    print(f"  - ❌ 失败: {len(failed_subdirs_list)} 个")
    
    if failed_subdirs_list:
        print("\n失败项目列表 (已保留在原位):")
        for failed_dir in failed_subdirs_list:
            print(f"  - {failed_dir}")
    
    print("-" * 70)
    print(f"所有成功生成的PDF文件（如有）已保存在: {overall_pdf_output_dir}")
    print(f"所有成功处理的原始项目文件夹（如有）已移至: {success_move_target_dir}")
    print("脚本执行完毕。")