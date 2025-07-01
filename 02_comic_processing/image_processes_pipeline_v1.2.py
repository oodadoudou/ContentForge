import os
import shutil
from PIL import Image, ImageDraw, ImageFile
import natsort
import sys
import datetime
import concurrent.futures
from io import BytesIO
import json

# --- 全局配置 ---
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None # 禁用Pillow的图片总像素限制

# --- 新增：为防止PDF生成错误的尺寸限制 ---
MAX_IMAGE_DIMENSION_FOR_PDF = 65000

MERGED_LONG_IMAGE_SUBDIR_NAME = "merged_long_img"
SPLIT_IMAGES_SUBDIR_NAME = "split_by_solid_band"
FINAL_PDFS_SUBDIR_NAME = "merged_pdfs"
REPACKED_IMAGES_SUBDIR_NAME = "repacked_for_pdf" # 新增：Repack 目录名

LONG_IMAGE_FILENAME_BASE = "stitched_long_strip"
IMAGE_EXTENSIONS_FOR_MERGE = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')

MIN_SOLID_COLOR_BAND_HEIGHT = 125

PDF_TARGET_PAGE_WIDTH_PIXELS = 1500
PDF_IMAGE_JPEG_QUALITY = 90
PDF_DPI = 300

# 新增：Repack 配置
MAX_REPACKED_IMAGE_FILESIZE_MB = 5
MAX_REPACKED_IMAGE_FILESIZE_BYTES = MAX_REPACKED_IMAGE_FILESIZE_MB * 1024 * 1024
REPACK_OUTPUT_FORMAT = 'PNG' # Repack后保存的格式

# --- 全局配置结束 ---

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
    """
    在循环中调用以创建终端进度条
    @params:
        iteration   - 必需  : 当前迭代次数 (Int)
        total       - 必需  : 总迭代次数 (Int)
        prefix      - 可选  : 前缀字符串 (Str)
        suffix      - 可选  : 后缀字符串 (Str)
        decimals    - 可选  : 百分比完成度的小数位数 (Int)
        length      - 可选  : 进度条的字符长度 (Int)
        fill        - 可选  : 进度条填充字符 (Str)
        print_end   - 可选  : 结尾字符 (例如 "\r", "\r\n") (Str)
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


def merge_to_long_image(source_image_dir, output_long_image_dir, long_image_filename_only):
    """将源目录中的所有图片垂直合并成一个PNG长图。"""
    print(f"\n  --- 步骤 1: 合并 '{os.path.basename(source_image_dir)}' 中的图片成长图 ---")
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
    total_calculated_height = 0
    max_calculated_width = 0

    total_files_to_analyze = len(sorted_image_filenames)
    if total_files_to_analyze > 0:
        print_progress_bar(0, total_files_to_analyze, prefix='    分析图片尺寸:', suffix='完成', length=40)
    for i, filename in enumerate(sorted_image_filenames):
        filepath = os.path.join(source_image_dir, filename)
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
            print(f"\n    警告: 打开或读取图片 '{filename}' 失败: {e}。已跳过。")
            continue
        if total_files_to_analyze > 0:
            print_progress_bar(i + 1, total_files_to_analyze, prefix='    分析图片尺寸:', suffix='完成', length=40)

    if not images_data:
        print("    没有有效的图片可供合并。")
        return None

    if max_calculated_width == 0 or total_calculated_height == 0:
        print(f"    计算得到的画布尺寸为零 ({max_calculated_width}x{total_calculated_height})，无法创建长图。")
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

def get_row_type(pixels, y, width, white_rgb_tuple, black_rgb_tuple):
    """检查给定行是纯白色、纯黑色还是内容。返回 'white', 'black', 或 'content'。"""
    if width == 0:
        return "content"

    first_pixel_rgb = pixels[0, y][:3]

    if first_pixel_rgb == white_rgb_tuple:
        for x in range(1, width):
            if pixels[x, y][:3] != white_rgb_tuple:
                return "content"
        return "white"
    elif first_pixel_rgb == black_rgb_tuple:
        for x in range(1, width):
            if pixels[x, y][:3] != black_rgb_tuple:
                return "content"
        return "black"
    else:
        return "content"

def split_long_image(long_image_path, output_split_dir, min_solid_band_height):
    """根据内容间的纯色带（白色或黑色）分割长图。"""
    print(f"\n  --- 步骤 2: 按内容间纯色带分割长图 '{os.path.basename(long_image_path)}' ---")
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

        white_rgb_tuple = (255, 255, 255)
        black_rgb_tuple = (0, 0, 0)

        original_basename, _ = os.path.splitext(os.path.basename(long_image_path))
        part_index = 1
        current_segment_start_y = 0
        solid_band_after_last_content_start_y = -1

        if img_height > 0:
            print_progress_bar(0, img_height, prefix='    扫描长图:', suffix='完成', length=40)

        for y in range(img_height):
            if img_height > 0:
                print_progress_bar(y + 1, img_height, prefix='    扫描长图:', suffix=f'第 {y+1}/{img_height} 行', length=40)

            current_row_type = get_row_type(pixels, y, img_width, white_rgb_tuple, black_rgb_tuple)

            if current_row_type == "content":
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
            else:
                if solid_band_after_last_content_start_y == -1:
                    solid_band_after_last_content_start_y = y

        if current_segment_start_y < img_height:
            segment = img.crop((0, current_segment_start_y, img_width, img_height))
            output_filename = f"{original_basename}_split_part_{part_index}.png"
            output_filepath = os.path.join(output_split_dir, output_filename)
            try:
                segment.save(output_filepath, "PNG")
                split_image_paths.append(output_filepath)
            except Exception as e_save:
                 print(f"      保存最后一个分割片段 '{output_filename}' 失败: {e_save}")

        if not split_image_paths and img_height > 0 :
            print(f"    未能从 '{os.path.basename(long_image_path)}' 按内容间纯色带分割。")
            print(f"    将使用原始合并长图 '{os.path.basename(long_image_path)}' 进行下一步。")
            temp_copy_name = f"{original_basename}_split_part_1_full.png"
            temp_copy_path = os.path.join(output_split_dir, temp_copy_name)
            try:
                shutil.copy2(long_image_path, temp_copy_path)
                return [temp_copy_path]
            except Exception as e_copy:
                print(f"    复制原始长图到分割目录失败: {e_copy}。将直接尝试使用原始路径。")
                return [long_image_path]

    except FileNotFoundError:
        print(f"    错误: 用于分割的长图未找到: {long_image_path}")
    except Exception as e:
        print(f"    分割图片 '{os.path.basename(long_image_path)}' 时发生错误: {e}")

    return natsort.natsorted(split_image_paths)

def further_split_large_images(image_paths, max_dim, output_dir):
    """
    接收一个图片路径列表，检查它们的尺寸，并分割任何高度过大的图片。
    返回一个新路径列表和所执行的额外分割次数。
    """
    print(f"\n  --- 步骤 2.5: 校验并分割过大尺寸的图片块 (限制: {max_dim}px) ---")
    final_safe_image_paths = []
    sub_split_count = 0

    if not image_paths:
        return [], 0
        
    print_progress_bar(0, len(image_paths), prefix='    校验图片块:', suffix='完成', length=40)
    for i, img_path in enumerate(image_paths):
        try:
            with Image.open(img_path) as img:
                width, height = img.size
                if height > max_dim:
                    print(f"\n    - 图片 '{os.path.basename(img_path)}' 尺寸过高 ({height}px). 正在进行再次分割...")
                    
                    original_basename, _ = os.path.splitext(os.path.basename(img_path))
                    
                    num_splits = height // max_dim + 1
                    for j in range(num_splits):
                        y_start = j * max_dim
                        y_end = min((j + 1) * max_dim, height)
                        
                        if y_start >= y_end: continue

                        chunk = img.crop((0, y_start, width, y_end))
                        
                        sub_split_filename = f"{original_basename}_subsplit_{j+1}.png"
                        sub_split_path = os.path.join(output_dir, sub_split_filename)
                        
                        chunk.save(sub_split_path, "PNG")
                        final_safe_image_paths.append(sub_split_path)
                        sub_split_count += 1
                    
                else:
                    final_safe_image_paths.append(img_path)
        except Exception as e:
            print(f"\n    警告: 无法处理或分割图片块 '{os.path.basename(img_path)}': {e}。已跳过。")
        
        print_progress_bar(i + 1, len(image_paths), prefix='    校验图片块:', suffix='完成', length=40)

    if sub_split_count > 0:
        print(f"    完成再次分割。生成了 {sub_split_count} 个新的小图片块。")
    else:
        print(f"    校验完成。未发现尺寸过大的图片块。")

    return natsort.natsorted(final_safe_image_paths), sub_split_count

# ▼▼▼ Repack Images 函数区 (已使用并行和增量构建进行优化) ▼▼▼
def save_repacked_strip_task(canvas_to_save, output_path, output_format, jpeg_quality):
    """
    用於並行處理的儲存任務。接收一個PIL畫布物件並將其儲存到磁碟。
    """
    try:
        # 如果目標格式是JPEG，先轉換為RGB
        if output_format.upper() == 'JPEG' and canvas_to_save.mode != 'RGB':
            canvas_to_save = canvas_to_save.convert('RGB')
        
        # 執行儲存操作
        canvas_to_save.save(output_path, format=output_format, quality=jpeg_quality, optimize=True)
        return output_path
    except Exception as e:
        print(f"\n    (線程) 錯誤: 儲存重新拼接圖片 '{os.path.basename(output_path)}' 失敗: {e}")
        return None
    finally:
        # 確保畫布物件被關閉以釋放記憶體
        if canvas_to_save:
            canvas_to_save.close()

def repack_images_to_max_size(image_paths, output_dir, max_filesize_bytes, output_format='PNG'):
    """
    (優化版) 將一系列圖片垂直拼接成新的長圖，同時確保每個長圖的檔案大小不超過指定限制。
    此版本使用增量構建和並行儲存來提升速度。
    """
    print(f"\n  --- 步骤 2.7: 重新拼接图片以优化 PDF 页数 (每张不超過 {MAX_REPACKED_IMAGE_FILESIZE_MB}MB) ---")
    if not image_paths:
        print("    沒有圖片可供重新拼接。")
        return []

    os.makedirs(output_dir, exist_ok=True)
    
    repacked_image_paths = []
    
    current_canvas = None
    current_canvas_width = 0
    current_canvas_height = 0
    
    repack_index = 1
    
    max_workers = min(4, os.cpu_count() or 1) 
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        total_images_to_repack = len(image_paths)
        if total_images_to_repack > 0:
            print_progress_bar(0, total_images_to_repack, prefix='    拼接图片块:', suffix='完成', length=40)

        for i, img_path in enumerate(image_paths):
            try:
                with Image.open(img_path) as img:
                    img.load()
                    img_rgba = img.convert("RGBA")

                    if current_canvas is None:
                        current_canvas = img_rgba
                        current_canvas_width = img_rgba.width
                        current_canvas_height = img_rgba.height
                        continue

                    new_width = max(current_canvas_width, img_rgba.width)
                    new_height = current_canvas_height + img_rgba.height
                    
                    proposed_canvas = Image.new('RGBA', (new_width, new_height))
                    proposed_canvas.paste(current_canvas, ((new_width - current_canvas_width) // 2, 0))
                    proposed_canvas.paste(img_rgba, ((new_width - img_rgba.width) // 2, current_canvas_height))

                    mem_buffer = BytesIO()
                    save_format = output_format
                    canvas_for_size_check = proposed_canvas
                    if save_format.upper() == 'JPEG':
                         canvas_for_size_check = proposed_canvas.convert('RGB')
                    
                    canvas_for_size_check.save(mem_buffer, format=save_format, quality=PDF_IMAGE_JPEG_QUALITY)
                    file_size = mem_buffer.tell()
                    mem_buffer.close()

                    if file_size > max_filesize_bytes and current_canvas is not None:
                        output_filename = f"repacked_part_{repack_index}.{output_format.lower()}"
                        output_filepath = os.path.join(output_dir, output_filename)
                        print(f"\n    当前拼接长图大小将超限，提交保存任务: {output_filename}")
                        
                        future = executor.submit(save_repacked_strip_task, current_canvas, output_filepath, output_format, PDF_IMAGE_JPEG_QUALITY)
                        futures.append(future)
                        repack_index += 1
                        
                        current_canvas = img_rgba
                        current_canvas_width = img_rgba.width
                        current_canvas_height = img_rgba.height

                    else:
                        current_canvas.close()
                        current_canvas = proposed_canvas
                        current_canvas_width = new_width
                        current_canvas_height = new_height

                img_rgba.close()

            except Exception as e:
                print(f"\n    警告: 重新拼接图片 '{os.path.basename(img_path)}' 失败: {e}。已跳过。")
            finally:
                print_progress_bar(i + 1, total_images_to_repack, prefix='    拼接图片块:', suffix='完成', length=40)

        if current_canvas is not None:
            output_filename = f"repacked_part_{repack_index}.{output_format.lower()}"
            output_filepath = os.path.join(output_dir, output_filename)
            print(f"\n    提交最后一个拼接长图的保存任务: {output_filename}")
            future = executor.submit(save_repacked_strip_task, current_canvas, output_filepath, output_format, PDF_IMAGE_JPEG_QUALITY)
            futures.append(future)

        print("\n    等待所有图片保存任务完成...")
        for future in concurrent.futures.as_completed(futures):
            result_path = future.result()
            if result_path:
                repacked_image_paths.append(result_path)

    print(f"    完成图片重新拼接。共生成 {len(repacked_image_paths)} 个新的图片文件。")
    return natsort.natsorted(repacked_image_paths)

# ▲▲▲ Repack Images 函数区结束 ▲▲▲

def create_pdf_from_images(image_paths_list, output_pdf_dir, pdf_filename_only,
                           target_page_width_px, image_jpeg_quality, pdf_target_dpi):
    """从图片片段列表创建PDF文件。"""
    print(f"\n  --- 步骤 3: 从图片片段创建 PDF '{pdf_filename_only}' ---")
    if not image_paths_list:
        print("    没有图片片段可用于创建 PDF。")
        return None

    os.makedirs(output_pdf_dir, exist_ok=True)
    pdf_full_path = os.path.join(output_pdf_dir, pdf_filename_only)
    
    processed_pil_images = []
    
    total_images_for_pdf = len(image_paths_list)
    if total_images_for_pdf > 0:
        print_progress_bar(0, total_images_for_pdf, prefix='    处理PDF图片:', suffix='完成', length=40)

    for i, image_path in enumerate(image_paths_list):
        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                original_width, original_height = img.size
                if original_width == 0 or original_height == 0:
                    print(f"    警告: 图片 '{os.path.basename(image_path)}' 尺寸为零，已跳过。")
                    if total_images_for_pdf > 0: print_progress_bar(i + 1, total_images_for_pdf, prefix='    处理PDF图片:', suffix='完成', length=40)
                    continue
                
                img_resized = img
                if original_width > target_page_width_px:
                    ratio = target_page_width_px / original_width
                    new_height = int(original_height * ratio)
                    if new_height <=0: new_height = 1
                    img_resized = img.resize((target_page_width_px, new_height), Image.Resampling.LANCZOS)

                processed_pil_images.append(img_resized)

        except Exception as e:
            print(f"\n    警告: 处理PDF图片 '{os.path.basename(image_path)}' 失败: {e}。已跳过。")
            pass
        if total_images_for_pdf > 0:
            print_progress_bar(i + 1, total_images_for_pdf, prefix='    处理PDF图片:', suffix='完成', length=40)


    if not processed_pil_images:
        print("    没有图片成功处理以包含在PDF中。")
        return None

    try:
        first_image = processed_pil_images[0]
        other_images = processed_pil_images[1:]

        first_image.save(
            pdf_full_path,
            save_all=True,
            append_images=other_images,
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


def cleanup_intermediate_dirs(long_img_dir, split_img_dir, repacked_img_dir=None):
    """清理指定的中间文件目录。"""
    print(f"\n  --- 步骤 4: 清理中间文件 ---")
    dirs_to_clean = [(long_img_dir, "长图合并"), (split_img_dir, "图片分割")]
    if repacked_img_dir:
        dirs_to_clean.append((repacked_img_dir, "图片重新拼接"))

    for dir_to_remove, dir_name_for_log in dirs_to_clean:
        if os.path.isdir(dir_to_remove):
            try:
                shutil.rmtree(dir_to_remove)
                print(f"    已删除中间 {dir_name_for_log} 文件夹: {dir_to_remove}")
            except Exception as e:
                print(f"    删除文件夹 '{dir_to_remove}' 失败: {e}")

if __name__ == "__main__":
    start_time = datetime.datetime.now()
    print("自动化图片批量处理脚本已启动！ (版本: 1.2 - 优化Repack)")
    print("功能：针对每个子文件夹，将执行 1.合并 -> 2.按内容分割 -> 2.5 按尺寸分割 -> 2.7 重新拼接 -> 3.创建PDF -> 4.清理")
    print("-" * 70)
    print("全局配置 (可在脚本顶部修改):")
    print(f"  - PDF图片尺寸限制: {MAX_IMAGE_DIMENSION_FOR_PDF}px (用以防止 'broken data stream' 错误)")
    print(f"  - 长图合并临时目录名: {MERGED_LONG_IMAGE_SUBDIR_NAME}")
    print(f"  - 图片分割临时目录名: {SPLIT_IMAGES_SUBDIR_NAME}")
    print(f"  - 图片重新拼接临时目录名: {REPACKED_IMAGES_SUBDIR_NAME}")
    print(f"  - 单个重新拼接图片最大文件大小: {MAX_REPACKED_IMAGE_FILESIZE_MB}MB")
    print(f"  - 最终PDF输出目录名 (在根目录下): {FINAL_PDFS_SUBDIR_NAME}")
    print(f"  - PDF: 页面宽度={PDF_TARGET_PAGE_WIDTH_PIXELS}px, JPEG质量={PDF_IMAGE_JPEG_QUALITY}, DPI={PDF_DPI}")
    print("-" * 70)

    # --- 新增：動態讀取設定檔以獲取預設路徑 ---
    def load_default_path_from_settings():
        """從共享設定檔中讀取預設工作目錄。"""
        try:
            # 向上兩層找到專案根目錄，再定位到 settings.json
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            # 如果 default_work_dir 為空或 None，也視為無效
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir else "."
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"警告：讀取 settings.json 失敗 ({e})，將使用內建備用路徑。")
            # 在無法讀取設定檔時，提供一個通用的備用路徑
            return os.path.join(os.path.expanduser("~"), "Downloads")

    default_root_dir_name = load_default_path_from_settings()
    # --- 修改結束 ---
    
    root_input_dir = ""
    while True:
        prompt_message = (
            f"请输入包含多个一级子文件夹的【根目录】路径。\n"
            f"脚本将处理每个一级子文件夹内的图片。\n"
            f"如果直接按 Enter 键，将使用默认路径 '{default_root_dir_name}': "
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
            if (not user_provided_path or current_path_to_check == default_root_dir_name) and \
               not os.path.exists(abs_path_to_check):
                if input(f"目录 '{abs_path_to_check}' 不存在。是否创建它? (y/n): ").lower() == 'y':
                    try:
                        os.makedirs(abs_path_to_check)
                        print(f"目录 '{abs_path_to_check}' 已创建。请将包含图片的子文件夹放入该目录后重新运行脚本。")
                        print("脚本已中止，请填充子文件夹后重试。")
                        sys.exit()
                    except Exception as e:
                        print(f"创建目录 '{abs_path_to_check}' 失败: {e}")
            print("-" * 30)

    overall_pdf_output_dir = os.path.join(root_input_dir, FINAL_PDFS_SUBDIR_NAME)
    os.makedirs(overall_pdf_output_dir, exist_ok=True)

    subdirectories = [d for d in os.listdir(root_input_dir)
                      if os.path.isdir(os.path.join(root_input_dir, d)) and \
                         d not in [MERGED_LONG_IMAGE_SUBDIR_NAME, SPLIT_IMAGES_SUBDIR_NAME, FINAL_PDFS_SUBDIR_NAME, REPACKED_IMAGES_SUBDIR_NAME] and \
                         not d.startswith('.')]

    if not subdirectories:
        print(f"\n在根目录 '{root_input_dir}' 下没有找到可处理的一级子文件夹。")
        sys.exit()

    sorted_subdirectories = natsort.natsorted(subdirectories)
    print(f"\n将按顺序处理以下 {len(sorted_subdirectories)} 个子文件夹: {', '.join(sorted_subdirectories)}")

    total_subdirs_to_process = len(sorted_subdirectories)
    overall_progress_prefix = "总进度 (子文件夹):"
    
    failed_subdirs_list = []
    extra_split_projects = []
    repacked_projects = [] 

    for i, subdir_name in enumerate(sorted_subdirectories):
        if total_subdirs_to_process > 0:
            print_progress_bar(i, total_subdirs_to_process, prefix=overall_progress_prefix, suffix=f'{subdir_name}', length=40)

        current_processing_subdir = os.path.join(root_input_dir, subdir_name)
        print(f"\n\n{'='*10} 开始处理子文件夹: {subdir_name} ({i+1}/{total_subdirs_to_process}) {'='*10}")

        path_long_image_output_dir_current = os.path.join(current_processing_subdir, MERGED_LONG_IMAGE_SUBDIR_NAME)
        path_split_images_output_dir_current = os.path.join(current_processing_subdir, SPLIT_IMAGES_SUBDIR_NAME)
        path_repacked_images_output_dir_current = os.path.join(current_processing_subdir, REPACKED_IMAGES_SUBDIR_NAME)

        current_long_image_filename = f"{subdir_name}_{LONG_IMAGE_FILENAME_BASE}.png"

        created_long_image_path = merge_to_long_image(
            current_processing_subdir,
            path_long_image_output_dir_current,
            current_long_image_filename
        )

        pdf_created_for_this_subdir = False
        if created_long_image_path:
            split_segment_paths = split_long_image(
                created_long_image_path,
                path_split_images_output_dir_current,
                MIN_SOLID_COLOR_BAND_HEIGHT
            )
            
            final_safe_paths, sub_split_count = further_split_large_images(
                split_segment_paths,
                MAX_IMAGE_DIMENSION_FOR_PDF,
                path_split_images_output_dir_current
            )
            
            if sub_split_count > 0:
                extra_split_projects.append(subdir_name)

            if final_safe_paths:
                repacked_segment_paths = repack_images_to_max_size(
                    final_safe_paths,
                    path_repacked_images_output_dir_current,
                    MAX_REPACKED_IMAGE_FILESIZE_BYTES,
                    REPACK_OUTPUT_FORMAT
                )
                if len(repacked_segment_paths) < len(final_safe_paths):
                    repacked_projects.append(subdir_name)

                images_for_pdf = repacked_segment_paths if repacked_segment_paths else final_safe_paths
            else:
                images_for_pdf = []

            if images_for_pdf:
                dynamic_pdf_filename_for_subdir = subdir_name + ".pdf"
                created_pdf_path = create_pdf_from_images(
                    images_for_pdf,
                    overall_pdf_output_dir,
                    dynamic_pdf_filename_for_subdir,
                    PDF_TARGET_PAGE_WIDTH_PIXELS,
                    PDF_IMAGE_JPEG_QUALITY,
                    PDF_DPI
                )
                if created_pdf_path:
                    pdf_created_for_this_subdir = True

        if pdf_created_for_this_subdir:
            cleanup_intermediate_dirs(path_long_image_output_dir_current, path_split_images_output_dir_current, path_repacked_images_output_dir_current)
        else:
            print(f"  子文件夹 '{subdir_name}' 未能成功生成PDF或在之前的步骤中失败/跳过，将保留其中间文件（如果有）。")
            failed_subdirs_list.append(subdir_name)

        print(f"{'='*10} 子文件夹 '{subdir_name}' 处理完毕 {'='*10}")
        if total_subdirs_to_process > 0:
            print_progress_bar(i + 1, total_subdirs_to_process, prefix=overall_progress_prefix, suffix='完成', length=40)

    # --- 最终报告 ---
    end_time = datetime.datetime.now()
    total_duration = end_time - start_time
    num_failed = len(failed_subdirs_list)
    num_success = total_subdirs_to_process - num_failed

    print("\n" + "=" * 70)
    print("【自动化处理任务总结报告】")
    print("-" * 70)
    print(f"报告生成时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {total_duration}")
    print(f"最终PDF输出目录: {overall_pdf_output_dir}")
    print("-" * 70)
    print("【任务统计】")
    print(f"  - 总计处理项目 (子文件夹): {total_subdirs_to_process} 个")
    print(f"  - ✅ 成功: {num_success} 个")
    print(f"  - ❌ 失败: {num_failed} 个")
    print("-" * 70)

    if extra_split_projects:
        print("【额外长图分割项目列表】")
        print("  以下项目因图片块高度超过限制，已触发自动二次分割：")
        for proj_name in extra_split_projects:
            print(f"  - {proj_name}")
        print("-" * 70)
    else:
        print("【额外长图分割项目列表】")
        print("  本次任务中没有项目触发额外长图分割。")
        print("-" * 70)
    
    if repacked_projects:
        print("【图片重新拼接项目列表】")
        print(f"  以下项目因图片块被重新拼接以控制文件大小 (限制: {MAX_REPACKED_IMAGE_FILESIZE_MB}MB)：")
        for proj_name in repacked_projects:
            print(f"  - {proj_name}")
        print("-" * 70)
    else:
        print("【图片重新拼接项目列表】")
        print("  本次任务中没有项目触发图片重新拼接。")
        print("-" * 70)

    if failed_subdirs_list:
        print("【失败项目列表】")
        print("  以下项目未能成功生成PDF，其中间文件已被保留用于排查：")
        for failed_dir in failed_subdirs_list:
            print(f"  - {failed_dir}")
        print("-" * 70)
    
    print("所有流程结束。")