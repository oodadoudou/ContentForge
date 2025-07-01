import os
import shutil
from PIL import Image, ImageFile
import natsort
import sys
import traceback
import json
import time

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

# ▼▼▼ [全新] V8 核心分割逻辑配置 (两阶段色彩同质性分析) ▼▼▼
# 色彩量化因子。数值越大，颜色被简化的程度越高。32是一个均衡的起点。
QUANTIZATION_FACTOR = 32
# 被视为空白背景行的最大“量化后”颜色种类数。用于对抗噪点。
MAX_UNIQUE_COLORS_IN_BG = 5
# 最小连续空白区高度。
MIN_SOLID_COLOR_BAND_HEIGHT = 30
# 边缘一致性校验的边距百分比。0.1 表示检查最左侧10%和最右侧10%的区域。
EDGE_MARGIN_PERCENT = 0.10

# --- 重打包与PDF输出配置 ---
MAX_REPACKED_FILESIZE_MB = 8
MAX_REPACKED_PAGE_HEIGHT_PX = 30000
PDF_TARGET_PAGE_WIDTH_PIXELS = 1500
PDF_IMAGE_JPEG_QUALITY = 85
PDF_DPI = 300
# --- 配置结束 ---


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
    """将源目录中的所有图片垂直合并成一个PNG长图。"""
    print(f"\n  --- 步骤 1: 合并图片至标准宽度 {target_width}px ---")
    if not os.path.isdir(source_image_dir):
        print(f"    错误: 源图片目录 '{source_image_dir}' 未找到。")
        return None

    os.makedirs(output_long_image_dir, exist_ok=True)
    output_long_image_path = os.path.join(output_long_image_dir, long_image_filename_only)

    image_filenames = [f for f in os.listdir(source_image_dir) if os.path.isfile(os.path.join(source_image_dir, f)) and f.lower().endswith(IMAGE_EXTENSIONS_FOR_MERGE) and not f.startswith('.')]
    if not image_filenames:
        print(f"    在 '{source_image_dir}' 中未找到符合条件的图片。")
        return None

    sorted_image_filenames = natsort.natsorted(image_filenames)
    images_data, total_height = [], 0
    print_progress_bar(0, len(sorted_image_filenames), prefix='    分析并计算尺寸:', suffix='完成', length=40)
    for i, filename in enumerate(sorted_image_filenames):
        filepath = os.path.join(source_image_dir, filename)
        try:
            with Image.open(filepath) as img:
                new_height = int(img.height * (target_width / img.width)) if img.width != target_width else img.height
                images_data.append({"path": filepath, "new_height": new_height})
                total_height += new_height
        except Exception as e:
            print(f"\n    警告: 打开或读取图片 '{filename}' 失败: {e}。已跳过。")
            continue
        print_progress_bar(i + 1, len(sorted_image_filenames), prefix='    分析并计算尺寸:', suffix='完成', length=40)

    if not images_data or target_width <= 0 or total_height <= 0:
        print(f"    计算得到的画布尺寸异常 ({target_width}x{total_height})，无法创建长图。")
        return None

    merged_canvas = Image.new('RGB', (target_width, total_height), (255, 255, 255))
    current_y_offset = 0
    print_progress_bar(0, len(images_data), prefix='    粘贴图片:    ', suffix='完成', length=40)
    for i, item_info in enumerate(images_data):
        try:
            with Image.open(item_info["path"]) as img:
                img_rgb = img.convert("RGB")
                img_to_paste = img_rgb.resize((target_width, item_info['new_height']), Image.Resampling.LANCZOS) if img_rgb.width != target_width else img_rgb
                merged_canvas.paste(img_to_paste, (0, current_y_offset))
                current_y_offset += item_info['new_height']
        except Exception as e:
            print(f"\n    警告: 粘贴图片 '{item_info['path']}' 失败: {e}。")
        print_progress_bar(i + 1, len(images_data), prefix='    粘贴图片:    ', suffix='完成', length=40)

    try:
        merged_canvas.save(output_long_image_path, format='PNG')
        print(f"    成功合并图片到: {output_long_image_path}")
        return output_long_image_path
    except Exception as e:
        print(f"    错误: 保存合并后的长图失败: {e}")
        return None

# ▼▼▼ [全新] V8 核心函数 - 两阶段色彩同质性分析 ▼▼▼
def get_dominant_color_numpy(pixels_quantized):
    """[V7 性能核心] 使用纯NumPy从量化后的像素块中找到主色调。"""
    if pixels_quantized.size == 0:
        return None, 0
    pixels_list = pixels_quantized.reshape(-1, 3)
    unique_colors, counts = np.unique(pixels_list, axis=0, return_counts=True)
    num_unique_colors = len(unique_colors)
    if num_unique_colors == 0:
        return None, 0
    dominant_color = tuple(unique_colors[np.argmax(counts)])
    return dominant_color, num_unique_colors

def split_long_image_v8(long_image_path, output_split_dir, quantization_factor, max_unique_colors, min_band_height, edge_margin_percent):
    """
    [V8 核心逻辑] 通过两阶段向量化分析来识别和分割图像，实现极致速度。
    """
    print(f"\n  --- 步骤 2 (V8 - 两阶段极速分析): 分割长图 '{os.path.basename(long_image_path)}' ---")
    start_time = time.time()
    if not os.path.isfile(long_image_path):
        print(f"    错误: 长图路径 '{long_image_path}' 未找到。")
        return []

    os.makedirs(output_split_dir, exist_ok=True)
    
    try:
        with Image.open(long_image_path) as img:
            img_rgb = img.convert("RGB")
            img_width, img_height = img_rgb.size
            if img_height < min_band_height * 3: # 如果图片太短，没必要分割
                print("    图片太短，无需分割。")
                dest_path = os.path.join(output_split_dir, os.path.basename(long_image_path))
                shutil.copy2(long_image_path, dest_path)
                return [dest_path]

            print(f"    分析一个 {img_width}x{img_height} 的图片...")
            print("    [1/3] 色彩量化...")
            quantized_array = np.array(img_rgb) // quantization_factor
            
            margin_width = int(img_width * edge_margin_percent)
            center_start, center_end = margin_width, img_width - margin_width

            # --- [V8 核心优化 1: 快速筛选阶段] ---
            print("    [2/3] 快速筛选候选行...")
            candidate_indices = []
            candidate_dominant_colors = {}
            # 依然逐行，但只做最快的中心区域分析
            for y in range(img_height):
                center_pixels = quantized_array[y, center_start:center_end]
                dominant_color, color_count = get_dominant_color_numpy(center_pixels)
                if color_count <= max_unique_colors and dominant_color is not None:
                    candidate_indices.append(y)
                    candidate_dominant_colors[y] = dominant_color
            
            if not candidate_indices:
                print("    未能找到任何候选行，无需分割。")
                dest_path = os.path.join(output_split_dir, os.path.basename(long_image_path))
                shutil.copy2(long_image_path, dest_path)
                return [dest_path]

            # --- [V8 核心优化 2: 精准验证阶段] ---
            print(f"    [3/3] 从 {len(candidate_indices)} 个候选行中精准验证边缘...")
            row_types = np.full(img_height, 'complex', dtype=object)
            # 只对少数候选行进行耗时的边缘分析
            for y in candidate_indices:
                center_dominant_color = candidate_dominant_colors[y]
                
                # 分析左边缘
                left_pixels = quantized_array[y, :margin_width]
                left_dominant_color, left_color_count = get_dominant_color_numpy(left_pixels)
                if left_color_count > max_unique_colors or left_dominant_color != center_dominant_color:
                    continue

                # 分析右边缘
                right_pixels = quantized_array[y, -margin_width:]
                right_dominant_color, right_color_count = get_dominant_color_numpy(right_pixels)
                if right_color_count > max_unique_colors or right_dominant_color != center_dominant_color:
                    continue
                
                row_types[y] = 'simple'
            
            analysis_duration = time.time() - start_time
            print(f"    分析完成，耗时: {analysis_duration:.2f} 秒。")

            # --- 后续的切块与保存逻辑 ---
            blocks, last_y = [], 0
            change_points = np.where(row_types[:-1] != row_types[1:])[0] + 1
            for y_change in change_points:
                blocks.append({'type': row_types[last_y], 'start': last_y, 'end': y_change})
                last_y = y_change
            blocks.append({'type': row_types[last_y], 'start': last_y, 'end': img_height})
            
            original_basename, _ = os.path.splitext(os.path.basename(long_image_path))
            part_index, last_cut_y, cut_found = 1, 0, False
            split_image_paths = []
            
            print(f"    正在从 {len(blocks)} 个内容/空白区块中寻找切割点...")
            for i, block in enumerate(blocks):
                if block['type'] == 'simple' and (block['end'] - block['start']) >= min_band_height:
                    if i > 0 and i < len(blocks) - 1:
                        cut_found = True
                        cut_point_y = block['start'] + (block['end'] - block['start']) // 2
                        segment = img_rgb.crop((0, last_cut_y, img_width, cut_point_y))
                        output_filename = f"{original_basename}_split_part_{part_index}.png"
                        output_filepath = os.path.join(output_split_dir, output_filename)
                        segment.save(output_filepath, "PNG")
                        split_image_paths.append(output_filepath)
                        print(f"      在 Y={cut_point_y} 处找到合格空白区，已切割并保存: {output_filename}")
                        part_index += 1
                        last_cut_y = cut_point_y

            segment = img_rgb.crop((0, last_cut_y, img_width, img_height))
            output_filename = f"{original_basename}_split_part_{part_index}.png"
            output_filepath = os.path.join(output_split_dir, output_filename)
            segment.save(output_filepath, "PNG")
            split_image_paths.append(output_filepath)
            
            if not cut_found:
                print("\n    [V8 诊断报告] 未能找到任何合格的空白区进行分割。")
                print(f"    建议检查参数: MAX_UNIQUE_COLORS_IN_BG={max_unique_colors}, MIN_SOLID_COLOR_BAND_HEIGHT={min_band_height}")
                if len(split_image_paths) == 1:
                    os.remove(split_image_paths[0])
                dest_path = os.path.join(output_split_dir, os.path.basename(long_image_path))
                shutil.copy2(long_image_path, dest_path)
                print("    由于未执行任何分割，已将原图复制到输出目录。")
                return [dest_path]

            return natsort.natsorted(split_image_paths)

    except Exception as e:
        print(f"    分割图片 '{os.path.basename(long_image_path)}' 时发生严重错误: {e}")
        traceback.print_exc()
        return []


def _merge_image_list_for_repack(image_paths, output_path):
    """一个专门用于重打包的内部合并函数。"""
    if not image_paths: return False
    images_data, total_height, target_width = [], 0, 0
    for path in image_paths:
        try:
            with Image.open(path) as img:
                if target_width == 0: target_width = img.width
                images_data.append({"path": path, "height": img.height})
                total_height += img.height
        except Exception: continue
    if not images_data or target_width == 0: return False
    merged_canvas = Image.new('RGB', (target_width, total_height))
    current_y = 0
    for item in images_data:
        with Image.open(item["path"]) as img:
            merged_canvas.paste(img.convert("RGB"), (0, current_y))
            current_y += item["height"]
    merged_canvas.save(output_path, "PNG")
    return True


def repack_split_images(split_image_paths, output_dir, base_filename, max_size_mb, max_height_px):
    """按“双重限制”重新打包分割后的图片。"""
    print(f"\n  --- 步骤 2.5: 按双重限制重打包 (上限: {max_size_mb}MB, {max_height_px}px) ---")
    if not split_image_paths or len(split_image_paths) <= 1:
        print("    仅有1个或没有图片块，无需重打包。")
        return split_image_paths

    max_size_bytes = max_size_mb * 1024 * 1024
    os.makedirs(output_dir, exist_ok=True)
    repacked_paths, current_bucket_paths, current_bucket_size, current_bucket_height = [], [], 0, 0
    repack_index = 1

    for img_path in split_image_paths:
        try:
            file_size = os.path.getsize(img_path)
            with Image.open(img_path) as img: img_height = img.height
        except Exception as e:
            print(f"\n    警告: 无法读取图片 '{os.path.basename(img_path)}' 的属性: {e}")
            continue
        
        if current_bucket_paths and ((current_bucket_size + file_size > max_size_bytes) or (current_bucket_height + img_height > max_height_px)):
            output_filename = f"{base_filename}_repacked_{repack_index}.png"
            output_path = os.path.join(output_dir, output_filename)
            if _merge_image_list_for_repack(current_bucket_paths, output_path):
                repacked_paths.append(output_path)
            repack_index += 1
            current_bucket_paths, current_bucket_size, current_bucket_height = [img_path], file_size, img_height
        else:
            current_bucket_paths.append(img_path)
            current_bucket_size += file_size
            current_bucket_height += img_height

    if current_bucket_paths:
        output_filename = f"{base_filename}_repacked_{repack_index}.png"
        output_path = os.path.join(output_dir, output_filename)
        if _merge_image_list_for_repack(current_bucket_paths, output_path):
            repacked_paths.append(output_path)
    
    print(f"    重打包完成，共生成 {len(repacked_paths)} 个新的图片块。")
    print("    ... 正在清理原始分割文件 ...")
    original_files_to_clean = [p for p in split_image_paths if p not in repacked_paths]
    for path in original_files_to_clean:
        if os.path.exists(path): os.remove(path)
            
    return natsort.natsorted(repacked_paths)


def create_pdf_from_images(image_paths_list, output_pdf_dir, pdf_filename_only):
    """从图片列表创建PDF。"""
    print(f"\n  --- 步骤 3: 从图片片段创建 PDF '{pdf_filename_only}' ---")
    if not image_paths_list:
        print("    没有图片可用于创建 PDF。")
        return None

    safe_image_paths = []
    for image_path in image_paths_list:
        try:
            with Image.open(image_path) as img:
                if img.height > 65500 or img.width > 65500:
                    print(f"\n    警告: 图片 '{os.path.basename(image_path)}' 尺寸过大，已跳过。")
                else:
                    safe_image_paths.append(image_path)
        except Exception as e:
            print(f"    警告: 无法打开图片 '{image_path}' 进行尺寸检查: {e}")
    
    if not safe_image_paths: return None

    os.makedirs(output_pdf_dir, exist_ok=True)
    pdf_full_path = os.path.join(output_pdf_dir, pdf_filename_only)
    
    images_for_pdf = [Image.open(p).convert('RGB') for p in safe_image_paths]
    if not images_for_pdf: return None

    try:
        images_for_pdf[0].save(pdf_full_path, save_all=True, append_images=images_for_pdf[1:], resolution=float(PDF_DPI), quality=PDF_IMAGE_JPEG_QUALITY, optimize=True)
        print(f"    成功创建 PDF: {pdf_full_path}")
        return pdf_full_path
    finally:
        for img_obj in images_for_pdf: img_obj.close()


def cleanup_intermediate_dirs(long_img_dir, split_img_dir):
    """清理中间文件目录。"""
    print(f"\n  --- 步骤 4: 清理中间文件 ---")
    for dir_path in [long_img_dir, split_img_dir]:
        if os.path.isdir(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"    已删除中间文件夹: {dir_path}")
            except Exception as e:
                print(f"    删除文件夹 '{dir_path}' 失败: {e}")


if __name__ == "__main__":
    print("自动化图片批量处理流程脚本启动！ (V8 - 两阶段极速版)")
    print("流程：1.合并 -> 2.两阶段同质性分割 -> 2.5.重打包 -> 3.创建PDF -> 4.清理")
    print("-" * 70)
    
    def load_default_path_from_settings():
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            settings_path = os.path.join(script_dir, 'shared_assets', 'settings.json')
            if not os.path.exists(settings_path):
                settings_path = os.path.join(os.path.dirname(script_dir), 'shared_assets', 'settings.json')
            with open(settings_path, 'r', encoding='utf-8') as f: return json.load(f).get("default_work_dir")
        except:
            return os.path.join(os.path.expanduser("~"), "Downloads")
    
    default_root_dir_name = load_default_path_from_settings() or "."

    while True:
        user_input = input(f"请输入根目录路径 (Enter 使用默认: '{default_root_dir_name}'): ").strip()
        root_input_dir = os.path.abspath(user_input or default_root_dir_name)
        if os.path.isdir(root_input_dir):
            print(f"已选定根处理目录: {root_input_dir}")
            break
        else:
            print(f"错误：路径 '{root_input_dir}' 不是一个有效的目录。")

    overall_pdf_output_dir = os.path.join(root_input_dir, FINAL_PDFS_SUBDIR_NAME)
    os.makedirs(overall_pdf_output_dir, exist_ok=True)
    
    subdirectories = [d for d in os.listdir(root_input_dir) if os.path.isdir(os.path.join(root_input_dir, d)) and d not in [MERGED_LONG_IMAGE_SUBDIR_NAME, SPLIT_IMAGES_SUBDIR_NAME, FINAL_PDFS_SUBDIR_NAME] and not d.startswith('.')]
    if not subdirectories:
        print(f"\n在 '{root_input_dir}' 下没有找到可处理的一级子文件夹。")
        sys.exit()

    sorted_subdirectories = natsort.natsorted(subdirectories)
    print(f"\n将按顺序处理以下 {len(sorted_subdirectories)} 个子文件夹: {', '.join(sorted_subdirectories)}")
    failed_subdirs_list = []

    for i, subdir_name in enumerate(sorted_subdirectories):
        print(f"\n\n{'='*10} 开始处理: {subdir_name} ({i+1}/{len(sorted_subdirectories)}) {'='*10}")
        current_processing_subdir = os.path.join(root_input_dir, subdir_name)
        path_long_image_output_dir = os.path.join(current_processing_subdir, MERGED_LONG_IMAGE_SUBDIR_NAME)
        path_split_images_output_dir = os.path.join(current_processing_subdir, SPLIT_IMAGES_SUBDIR_NAME)
        
        if os.path.isdir(path_long_image_output_dir): shutil.rmtree(path_long_image_output_dir)
        if os.path.isdir(path_split_images_output_dir): shutil.rmtree(path_split_images_output_dir)

        created_long_image_path = merge_to_long_image(
            current_processing_subdir, path_long_image_output_dir,
            f"{subdir_name}_{LONG_IMAGE_FILENAME_BASE}.png", PDF_TARGET_PAGE_WIDTH_PIXELS
        )

        pdf_created_for_this_subdir = False
        if created_long_image_path:
            # ▼▼▼ 调用全新的 V8 两阶段分割函数 ▼▼▼
            split_segment_paths = split_long_image_v8(
                created_long_image_path, path_split_images_output_dir,
                QUANTIZATION_FACTOR, MAX_UNIQUE_COLORS_IN_BG,
                MIN_SOLID_COLOR_BAND_HEIGHT, EDGE_MARGIN_PERCENT
            )

            if split_segment_paths:
                repacked_final_paths = repack_split_images(
                    split_segment_paths, path_split_images_output_dir, base_filename=subdir_name,
                    max_size_mb=MAX_REPACKED_FILESIZE_MB, max_height_px=MAX_REPACKED_PAGE_HEIGHT_PX
                )

                if repacked_final_paths:
                    created_pdf_path = create_pdf_from_images(
                        repacked_final_paths, overall_pdf_output_dir, f"{subdir_name}.pdf"
                    )
                    if created_pdf_path: pdf_created_for_this_subdir = True

        if pdf_created_for_this_subdir:
            cleanup_intermediate_dirs(path_long_image_output_dir, path_split_images_output_dir)
        else:
            print(f"  ❌ 子文件夹 '{subdir_name}' 未能成功生成PDF，将保留中间文件以供检查。")
            failed_subdirs_list.append(subdir_name)

        print(f"{'='*10} '{subdir_name}' 处理完毕 {'='*10}")
        print_progress_bar(i + 1, len(sorted_subdirectories), prefix="总进度:", suffix='完成', length=40)

    print("\n" + "=" * 70 + "\n【任务总结报告】\n" + "-" * 70)
    success_count = len(sorted_subdirectories) - len(failed_subdirs_list)
    print(f"总计处理项目: {len(sorted_subdirectories)} 个\n  - ✅ 成功: {success_count} 个\n  - ❌ 失败: {len(failed_subdirs_list)} 个")
    if failed_subdirs_list:
        print("\n失败项目列表:\n" + "\n".join(f"  - {d}" for d in failed_subdirs_list))
    print("-" * 70 + f"\n所有成功生成的PDF文件已保存在: {overall_pdf_output_dir}\n脚本执行完毕。")
