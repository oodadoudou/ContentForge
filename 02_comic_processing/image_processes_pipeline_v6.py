"""自动化图片批量处理流程 (V6 - 并行加速实验版)

基于 V5 智能融合版复制而来。分割 / 合并 / 重打包 / PDF 生成的判定逻辑与 V5 完全一致，
V6 只在不改变处理逻辑的前提下做性能加速：

  1. 多项目并行处理：不同子文件夹（章节）之间相互独立，使用多进程并行（进程数按
     CPU 核心数与可用内存动态检测，也可用 --workers 手动指定）。
  2. V2 纯色带扫描向量化：原来逐像素的 is_solid_color_row 循环改为 NumPy 分块整批
     计算，判定标准（行首像素匹配预设背景色 + 整行颜色一致）与逐像素版完全一致。
  3. V4 候选行筛选向量化：每行中心区唯一颜色计数改为 NumPy 分块排序整批计算，
     唯一色计数与 np.unique 结果完全一致，后续验证阶段保持 V5 原样。
  4. 长图合并阶段使用线程池预解码图片（有界队列，粘贴顺序与布局不变）。
  5. 中间 PNG 统一使用快速压缩等级（compress_level=1，仅中间产物，像素内容与
     默认压缩完全一致，最终 PDF 的编码参数保持 V5 原样）。

用法:
    python image_processes_pipeline_v6.py -p <根目录>              # 自动检测并行度
    python image_processes_pipeline_v6.py -p <根目录> --workers 4 # 手动指定进程数
    python image_processes_pipeline_v6.py -p <根目录> --serial     # 单进程顺序模式（输出风格同 V5）
"""

import os
import sys
import shutil
import re
import math
import traceback
import time
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

from PIL import Image, ImageFile

try:
    import numpy as np
except ImportError:
    print("错误：此脚本需要 numpy 库。请使用 'pip install numpy' 命令进行安装。")
    sys.exit(1)


def natural_sort_key(value):
    """本地自然排序，避免 natsort 在某些 Windows 环境导入时触发 WMI 卡死。"""
    text = str(value)
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]


def natsorted(values):
    return sorted(values, key=natural_sort_key)

# --- 全局配置 ---
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

# --- 目录与文件名配置 ---
MERGED_LONG_IMAGE_SUBDIR_NAME = "merged_long_img"
SPLIT_IMAGES_SUBDIR_NAME = "split_by_solid_band"
SUCCESS_MOVE_SUBDIR_NAME = "IMG"  # 成功处理的文件夹将被移动到此目录
LONG_IMAGE_FILENAME_BASE = "stitched_long_strip"
IMAGE_EXTENSIONS_FOR_MERGE = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')

# --- V2 分割配置 ---
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

# --- V4 分割配置 ---
QUANTIZATION_FACTOR = 32
MAX_UNIQUE_COLORS_IN_BG = 5
MIN_SOLID_COLOR_BAND_HEIGHT_V4 = 30
EDGE_MARGIN_PERCENT = 0.10

# --- 重打包与PDF输出配置 ---
MAX_REPACKED_FILESIZE_MB = 8
MAX_REPACKED_PAGE_HEIGHT_PX = 30000
PDF_TARGET_PAGE_WIDTH_PIXELS = 1500
PDF_IMAGE_JPEG_QUALITY = 85
PDF_DPI = 300

# --- V6 性能配置 ---
MAX_PARALLEL_WORKERS = 8        # 并行进程数上限（防止小内存机器被压垮）
ESTIMATED_WORKER_MEM_GB = 2.0   # 预估单个并行进程的峰值内存（用于内存自适应）
MAX_DECODE_THREADS = 8         # 单进程内图片预解码线程上限
V2_SCAN_CHUNK_ROWS = 4096      # V2 向量化扫描的分块行数
V4_SCAN_CHUNK_ROWS = 4096      # V4 向量化筛选的分块行数
PNG_SAVE_COMPRESS_LEVEL = 1    # 中间 PNG 的压缩等级(1=最快, PIL 默认 6)；仅影响中间产物速度
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


def _save_png_fast(img, output_path):
    """V6: 保存中间 PNG（快速压缩等级）。像素内容与默认压缩完全一致，仅写盘更快。"""
    img.save(output_path, "PNG", compress_level=PNG_SAVE_COMPRESS_LEVEL)


# --- V6 CPU/内存检测 ---


def get_logical_cpu_count():
    """获取当前进程可用的逻辑 CPU 核心数（兼容不同 Python 版本）。"""
    getter = getattr(os, "process_cpu_count", None)  # Python 3.13+
    if callable(getter):
        try:
            return getter() or 1
        except Exception:
            pass
    return os.cpu_count() or 1


def detect_parallel_workers(num_tasks, user_workers=None):
    """根据 CPU 核心数与可用内存动态计算并行进程数。

    返回 (workers, cpu_count, mem_note)。
    - 未安装 psutil 时跳过内存检测，仅按 CPU 核心数与任务数限制。
    - user_workers 显式指定时优先使用。
    """
    cpu = get_logical_cpu_count()
    candidates = [cpu, num_tasks, MAX_PARALLEL_WORKERS]
    mem_note = "未安装 psutil（内存自适应不可用，建议 pip install psutil）"
    try:
        import psutil  # type: ignore
        avail_gb = psutil.virtual_memory().available / (1024 ** 3)
        mem_cap = max(1, int(avail_gb // ESTIMATED_WORKER_MEM_GB))
        candidates.append(mem_cap)
        mem_note = f"可用内存 {avail_gb:.1f} GB (单进程峰值预估 {ESTIMATED_WORKER_MEM_GB:.1f} GB)"
    except Exception:
        pass

    workers = max(1, min(candidates))
    if user_workers:  # 显式指定优先
        workers = max(1, min(int(user_workers), 32))
    return workers, cpu, mem_note


# --- V6 向量化行判定（判定标准与 V5 逐像素版完全一致） ---


def are_colors_close(color1, color2, tolerance):
    """根据欧氏距离检查两种RGB颜色是否接近。（V5 参考实现，保留用于对照）"""
    if tolerance == 0:
        return color1 == color2
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    distance = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
    return distance <= tolerance


def is_solid_color_row(pixels, y, width, solid_colors_list, tolerance):
    """检查给定行是否为纯色带，允许一定的容差。（V5 参考实现，保留用于对照）"""
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


def _compute_solid_rows_vectorized(rgb_array, band_colors_list, tolerance, chunk_rows=V2_SCAN_CHUNK_ROWS, progress_callback=None):
    """V6 加速核心：向量化批量计算每一行是否为纯色带。

    判定标准与 V5 的 is_solid_color_row 完全一致：
      1) 行首像素与任一预设背景色的欧氏距离 <= tolerance；
      2) 该行所有像素与行首像素的欧氏距离 <= tolerance。
    使用整数平方距离比较，避免浮点误差（sqrt(d2) <= t 等价于 d2 <= t*t）。
    """
    img_height, img_width = rgb_array.shape[0], rgb_array.shape[1]
    solid = np.zeros(img_height, dtype=bool)
    if img_width == 0:
        return solid

    tol2 = int(tolerance) * int(tolerance)
    bases = np.asarray(band_colors_list, dtype=np.int32)  # (K, 3)

    for start in range(0, img_height, chunk_rows):
        end = min(start + chunk_rows, img_height)
        chunk = rgb_array[start:end].astype(np.int32)      # (h, W, 3)
        first = chunk[:, :1, :]                            # (h, 1, 3) 行首像素
        diff = chunk - first
        row_max_d2 = np.einsum('ijk,ijk->ij', diff, diff).max(axis=1)

        fp = chunk[:, 0, :]                               # (h, 3)
        bdiff = fp[:, None, :] - bases[None, :, :]         # (h, K, 3)
        base_d2 = np.einsum('ijk,ijk->ij', bdiff, bdiff).min(axis=1)

        solid[start:end] = (row_max_d2 <= tol2) & (base_d2 <= tol2)
        if progress_callback is not None:
            progress_callback(end, img_height)

    return solid


def _count_unique_colors_per_row(quantized_array, start_col, end_col, chunk_rows=V4_SCAN_CHUNK_ROWS):
    """V6 加速核心：向量化计算每行在 [start_col, end_col) 区间内量化后的唯一颜色数。

    与 V5 对每行调用 np.unique(axis=0) 的 unique 数完全一致（(r,g,b) 三元组与整数编码一一对应）。
    区间为空时返回 0（与 V5 中 get_dominant_color_numpy 返回 count=0 的行为一致）。
    """
    height = quantized_array.shape[0]
    counts = np.empty(height, dtype=np.int64)
    if end_col <= start_col:
        counts[:] = 0
        return counts

    for s in range(0, height, chunk_rows):
        e = min(s + chunk_rows, height)
        block = quantized_array[s:e, start_col:end_col]
        codes = (block[:, :, 0].astype(np.int32) << 16) | \
                (block[:, :, 1].astype(np.int32) << 8) | \
                block[:, :, 2].astype(np.int32)
        sorted_rows = np.sort(codes, axis=1)
        changes = sorted_rows[:, 1:] != sorted_rows[:, :-1]
        counts[s:e] = changes.sum(axis=1) + 1
    return counts


# --- 步骤 1: 合并长图 ---


def _read_image_size(filepath):
    """读取图片宽高（仅读文件头）。失败时返回异常对象。"""
    try:
        with Image.open(filepath) as img:
            return (img.width, img.height)
    except Exception as e:
        return e


def _decode_for_paste(path, target_width, target_height):
    """解码单张图片用于粘贴（与 V5 粘贴阶段的处理一致：转 RGB + 按需 LANCZOS 缩放）。"""
    with Image.open(path) as img:
        rgb = img.convert("RGB")
    if target_width and rgb.width != target_width:
        return rgb.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return rgb


def merge_to_long_image(source_project_dir, output_long_image_dir, long_image_filename_only,
                         target_width=None, verbose=True, decode_threads=1):
    """将源目录中的所有图片（包括子目录）垂直合并成一个长图。

    V6 加速：图片尺寸分析与解码使用线程池并行预取（有界队列），
    分析顺序、粘贴顺序、画布布局与 V5 完全一致。
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
    sorted_image_filepaths = natsorted(image_filepaths)

    images_data = []
    total_calculated_height = 0
    max_calculated_width = 0

    total_files_to_analyze = len(sorted_image_filepaths)
    if verbose and total_files_to_analyze > 0:
        print_progress_bar(0, total_files_to_analyze, prefix='    分析图片尺寸:', suffix='完成', length=40)

    # V6: 并行读取图片尺寸（仅文件头，顺序与 V5 一致）
    if decode_threads > 1 and total_files_to_analyze > 1:
        with ThreadPoolExecutor(max_workers=decode_threads) as size_pool:
            size_results = list(size_pool.map(_read_image_size, sorted_image_filepaths))
    else:
        size_results = [_read_image_size(p) for p in sorted_image_filepaths]

    for i, (filepath, size_info) in enumerate(zip(sorted_image_filepaths, size_results)):
        if isinstance(size_info, Exception):
            print(f"\n    警告: 打开或读取图片 '{os.path.basename(filepath)}' 失败: {size_info}。已跳过。")
            continue
        img_width, img_height = size_info
        if target_width and img_width != target_width:
            new_height = int(img_height * (target_width / img_width))
            images_data.append({
                "path": filepath,
                "width": target_width,
                "height": new_height,
                "original_width": img_width,
                "original_height": img_height
            })
            total_calculated_height += new_height
            max_calculated_width = target_width
        else:
            images_data.append({
                "path": filepath,
                "width": img_width,
                "height": img_height,
                "original_width": img_width,
                "original_height": img_height
            })
            total_calculated_height += img_height
            if img_width > max_calculated_width:
                max_calculated_width = img_width
        if verbose and total_files_to_analyze > 0:
            print_progress_bar(i + 1, total_files_to_analyze, prefix='    分析图片尺寸:', suffix='完成', length=40)

    if not images_data:
        print("    没有有效的图片可供合并。")
        return None

    if max_calculated_width == 0 or total_calculated_height == 0:
        print(f"    计算出的画布尺寸为零 ({max_calculated_width}x{total_calculated_height})，无法创建长图。")
        return None

    merged_canvas = Image.new('RGB', (max_calculated_width, total_calculated_height), (255, 255, 255))
    current_y_offset = 0

    total_files_to_paste = len(images_data)
    if verbose and total_files_to_paste > 0:
        print_progress_bar(0, total_files_to_paste, prefix='    粘贴图片:    ', suffix='完成', length=40)

    # V6: 解码线程池 + 有界预取队列（保证粘贴顺序不变，内存占用有界）
    use_threads = decode_threads > 1 and total_files_to_paste > 1
    pool = ThreadPoolExecutor(max_workers=decode_threads) if use_threads else None
    pending = deque()
    next_submit = [0]
    max_pending = max(2, decode_threads * 2)

    def _fill_pending():
        while next_submit[0] < total_files_to_paste and len(pending) < max_pending:
            info = images_data[next_submit[0]]
            next_submit[0] += 1
            pending.append(pool.submit(_decode_for_paste, info["path"], target_width, info["height"]))

    try:
        if pool is not None:
            _fill_pending()
        for i, item_info in enumerate(images_data):
            # V6: 预取解码结果（失败处理与 V5 一致：警告并跳过，不推进 y 偏移）
            if pool is not None:
                future = pending.popleft()
                _fill_pending()
                try:
                    img_to_paste = future.result()
                except Exception as e:
                    print(f"\n    警告: 粘贴图片 '{item_info['path']}' 失败: {e}。")
                    continue
            else:
                try:
                    img_to_paste = _decode_for_paste(item_info["path"], target_width, item_info["height"])
                except Exception as e:
                    print(f"\n    警告: 粘贴图片 '{item_info['path']}' 失败: {e}。")
                    continue

            try:
                if target_width:
                    merged_canvas.paste(img_to_paste, (0, current_y_offset))
                else:
                    x_offset = (max_calculated_width - img_to_paste.width) // 2
                    merged_canvas.paste(img_to_paste, (x_offset, current_y_offset))
                current_y_offset += item_info["height"]
            except Exception as e:
                print(f"\n    警告: 粘贴图片 '{item_info['path']}' 失败: {e}。")
            finally:
                img_to_paste = None  # 及时释放已粘贴图片的内存

            if verbose and total_files_to_paste > 0:
                print_progress_bar(i + 1, total_files_to_paste, prefix='    粘贴图片:    ', suffix='完成', length=40)
    finally:
        if pool is not None:
            for future in pending:
                future.cancel()
            pool.shutdown(wait=False, cancel_futures=True)

    try:
        _save_png_fast(merged_canvas, output_long_image_path)
        print(f"    成功合并图片到: {output_long_image_path}")
        return output_long_image_path
    except Exception as e:
        print(f"    错误: 保存合并后的长图失败: {e}")
        return None


# --- V2 分割相关函数 ---


def split_long_image_v2(long_image_path, output_split_dir, min_solid_band_height, band_colors_list, tolerance, verbose=True):
    """V2 分割方法：基于在足够高的纯色带后找到内容行的逻辑来分割长图。

    V6 加速：逐像素的行判定改为 NumPy 分块向量化（判定标准不变），
    切割点状态机与 V5 完全一致。
    """
    print(f"\n  --- 步骤 2 (V2 - 传统纯色带分析): 分割长图 '{os.path.basename(long_image_path)}' ---")
    if not os.path.isfile(long_image_path):
        print(f"    错误: 长图路径 '{long_image_path}' 未找到。")
        return []

    os.makedirs(output_split_dir, exist_ok=True)
    split_image_paths = []

    try:
        if min_solid_band_height < 1:
            min_solid_band_height = 1

        # V6: 用 RGB 代替 V5 的 RGBA（判定只使用前 3 通道，结果一致且更省内存）
        img = Image.open(long_image_path).convert("RGB")
        img_width, img_height = img.size

        if img_height == 0 or img_width == 0:
            print(f"    图片 '{os.path.basename(long_image_path)}' 尺寸为零，无法分割。")
            return []

        rgb_array = np.asarray(img)
        print(f"    [V6 加速] NumPy 向量化扫描 {img_height} 行 (判定标准与逐像素版一致)...")

        def _chunk_progress(done, total):
            if verbose:
                print_progress_bar(done, total, prefix='    扫描长图:    ', suffix=f'已扫描 {done}/{total} 行', length=40)

        solid_rows = _compute_solid_rows_vectorized(rgb_array, band_colors_list, tolerance, progress_callback=_chunk_progress)
        print(f"    扫描完成: {img_height} 行中共有 {int(solid_rows.sum())} 行纯色带。")

        # --- 以下切割状态机与 V5 完全一致 ---
        original_basename, _ = os.path.splitext(os.path.basename(long_image_path))
        part_index = 1
        current_segment_start_y = 0
        solid_band_after_last_content_start_y = -1

        for y in range(img_height):
            is_solid = bool(solid_rows[y])

            if not is_solid:  # 这是一个 "内容" 行
                if solid_band_after_last_content_start_y != -1:
                    solid_band_height = y - solid_band_after_last_content_start_y
                    if solid_band_height >= min_solid_band_height:
                        cut_point_y = solid_band_after_last_content_start_y + (solid_band_height // 2)
                        if cut_point_y > current_segment_start_y:
                            segment = img.crop((0, current_segment_start_y, img_width, cut_point_y))
                            output_filename = f"{original_basename}_split_part_{part_index}.png"
                            output_filepath = os.path.join(output_split_dir, output_filename)
                            try:
                                _save_png_fast(segment, output_filepath)
                                split_image_paths.append(output_filepath)
                                part_index += 1
                            except Exception as e_save:
                                print(f"      保存分割片段 '{output_filename}' 失败: {e_save}")
                        current_segment_start_y = cut_point_y
                solid_band_after_last_content_start_y = -1
            else:  # 这是一个 "纯色" 行
                if solid_band_after_last_content_start_y == -1:
                    solid_band_after_last_content_start_y = y

        if current_segment_start_y < img_height:
            segment = img.crop((0, current_segment_start_y, img_width, img_height))
            if segment.height > 10:  # 避免保存过小的切片
                output_filename = f"{original_basename}_split_part_{part_index}.png"
                output_filepath = os.path.join(output_split_dir, output_filename)
                try:
                    _save_png_fast(segment, output_filepath)
                    split_image_paths.append(output_filepath)
                except Exception as e_save:
                    print(f"      保存最后一个分割片段 '{output_filename}' 失败: {e_save}")

        if not split_image_paths and img_height > 0:
            print(f"    V2 方法未能根据指定的纯色带分割 '{os.path.basename(long_image_path)}'。")
            return []

    except Exception as e:
        print(f"    V2 分割图片 '{os.path.basename(long_image_path)}' 时发生错误: {e}")
        traceback.print_exc()
        return []

    return natsorted(split_image_paths)


# --- V4 分割相关函数 ---
def get_dominant_color_numpy(pixels_quantized):
    """[V4 性能核心] 使用纯NumPy从量化后的像素块中找到主色调。"""
    if pixels_quantized.size == 0:
        return None, 0
    pixels_list = pixels_quantized.reshape(-1, 3)
    unique_colors, counts = np.unique(pixels_list, axis=0, return_counts=True)
    num_unique_colors = len(unique_colors)
    if num_unique_colors == 0:
        return None, 0
    dominant_color = tuple(unique_colors[np.argmax(counts)])
    return dominant_color, num_unique_colors


def split_long_image_v4(long_image_path, output_split_dir, quantization_factor, max_unique_colors, min_band_height, edge_margin_percent, verbose=True):
    """V4 分割方法：通过两阶段向量化分析来识别和分割图像，实现极致速度。

    V6 加速：候选行筛选阶段（每行中心区唯一颜色计数）改为 NumPy 分块整批计算，
    唯一色计数与 V5 的逐行 np.unique 完全一致；边缘验证与切割逻辑保持 V5 原样。
    """
    print(f"\n  --- 步骤 2 (V4 - 两阶段极速分析): 分割长图 '{os.path.basename(long_image_path)}' ---")
    start_time = time.time()
    if not os.path.isfile(long_image_path):
        print(f"    错误: 长图路径 '{long_image_path}' 未找到。")
        return []

    os.makedirs(output_split_dir, exist_ok=True)

    try:
        with Image.open(long_image_path) as img:
            img_rgb = img.convert("RGB")
            img_width, img_height = img_rgb.size
            if img_height < min_band_height * 3:  # 如果图片太短，没必要分割
                print("    图片太短，无需分割。")
                return []

            print(f"    分析一个 {img_width}x{img_height} 的图片...")
            print("    [1/3] 色彩量化...")
            quantized_array = np.array(img_rgb) // quantization_factor

            margin_width = int(img_width * edge_margin_percent)
            center_start, center_end = margin_width, img_width - margin_width

            # --- [V6 核心优化 1: 向量化快速筛选阶段] ---
            print("    [2/3] 快速筛选候选行 (V6 向量化)...")
            unique_counts = _count_unique_colors_per_row(quantized_array, center_start, center_end)
            candidate_mask = (unique_counts >= 1) & (unique_counts <= max_unique_colors)
            candidate_rows = np.nonzero(candidate_mask)[0]
            candidate_dominant_colors = {}
            for y in candidate_rows:
                dominant_color, color_count = get_dominant_color_numpy(quantized_array[y, center_start:center_end])
                if color_count <= max_unique_colors and dominant_color is not None:
                    candidate_dominant_colors[int(y)] = dominant_color

            if not candidate_dominant_colors:
                print("    未能找到任何候选行，V4 方法无法分割。")
                return []

            # --- [V4 核心优化 2: 精准验证阶段] (与 V5 一致) ---
            print(f"    [3/3] 从 {len(candidate_dominant_colors)} 个候选行中精准验证边缘...")
            row_types = np.full(img_height, 'complex', dtype=object)
            # 只对少数候选行进行耗时的边缘分析
            for y in candidate_dominant_colors:
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

            # --- 后续的切块与保存逻辑 (与 V5 一致) ---
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
                        _save_png_fast(segment, output_filepath)
                        split_image_paths.append(output_filepath)
                        if verbose:
                            print(f"      在 Y={cut_point_y} 处找到合格空白区，已切割并保存: {output_filename}")
                        part_index += 1
                        last_cut_y = cut_point_y

            segment = img_rgb.crop((0, last_cut_y, img_width, img_height))
            output_filename = f"{original_basename}_split_part_{part_index}.png"
            output_filepath = os.path.join(output_split_dir, output_filename)
            _save_png_fast(segment, output_filepath)
            split_image_paths.append(output_filepath)

            if not cut_found:
                print("\n    [V4 诊断报告] 未能找到任何合格的空白区进行分割。")
                print(f"    建议检查参数: MAX_UNIQUE_COLORS_IN_BG={max_unique_colors}, MIN_SOLID_COLOR_BAND_HEIGHT={min_band_height}")
                return []

            return natsorted(split_image_paths)

    except Exception as e:
        print(f"    V4 分割图片 '{os.path.basename(long_image_path)}' 时发生严重错误: {e}")
        traceback.print_exc()
        return []


# --- 融合分割函数 ---
def split_long_image_hybrid(long_image_path, output_split_dir, verbose=True):
    """融合分割方法：先尝试 V2，如果 PDF 创建失败则自动切换到 V4。"""
    print(f"\n  --- 步骤 2 (V5 - 智能融合分割): 分割长图 '{os.path.basename(long_image_path)}' ---")
    print("    🔄 采用智能双重分割策略：V2传统方法 → V4极速方法")

    # 首先尝试 V2 方法
    print("\n    📋 第一阶段：尝试 V2 传统纯色带分析方法...")
    print("    🎨 使用预设的韩漫常见背景色进行分割，提高速度和效率...")

    v2_result = split_long_image_v2(
        long_image_path,
        output_split_dir,
        MIN_SOLID_COLOR_BAND_HEIGHT,
        SPLIT_BAND_COLORS_RGB,
        COLOR_MATCH_TOLERANCE,
        verbose=verbose
    )

    if v2_result and len(v2_result) > 1:
        print(f"    ✅ V2 分割成功！共分割出 {len(v2_result)} 个片段。")
        return v2_result

    print("    ⚠️  V2 方法未能有效分割图片，正在切换到 V4 方法...")

    # 清理 V2 可能产生的文件
    if v2_result:
        print("    🧹 清理 V2 分割产生的文件...")
        for file_path in v2_result:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"      已删除: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"      删除失败 {os.path.basename(file_path)}: {e}")

    # 尝试 V4 方法
    print("\n    🚀 第二阶段：启用 V4 两阶段极速分析方法...")
    v4_result = split_long_image_v4(
        long_image_path,
        output_split_dir,
        QUANTIZATION_FACTOR,
        MAX_UNIQUE_COLORS_IN_BG,
        MIN_SOLID_COLOR_BAND_HEIGHT_V4,
        EDGE_MARGIN_PERCENT,
        verbose=verbose
    )

    if v4_result and len(v4_result) > 1:
        print(f"    ✅ V4 方法成功！共分割出 {len(v4_result)} 个片段。")
        return v4_result

    print("    ❌ 两种分割方法都未能有效分割图片，将使用原图。")

    # 如果两种方法都失败，复制原图
    dest_path = os.path.join(output_split_dir, os.path.basename(long_image_path))
    shutil.copy2(long_image_path, dest_path)
    return [dest_path]


def split_long_image_hybrid_with_pdf_fallback(long_image_path, output_split_dir, pdf_output_dir, pdf_filename, subdir_name, verbose=True):
    """融合分割方法：先尝试 V2 + PDF 创建，如果 PDF 创建失败则清理 V2 文件并切换到 V4。

    失败判定标准（与 V5 一致）：
    - V2 分割成功但 PDF 创建失败时，清除 V2 分割的图片，重新使用 V4 方式进行分割
    - V2 分割成功但重打包失败时，清除 V2 分割的图片，重新使用 V4 方式进行分割
    - V2 分割本身失败时，直接使用 V4 方式进行分割
    """
    print(f"\n  --- 步骤 2 (V5 - 智能融合分割): 分割长图 '{os.path.basename(long_image_path)}' ---")
    print("    🔄 采用智能双重分割策略：V2传统方法 → V4极速方法")
    print("    📋 失败判定标准：PDF 创建失败时自动切换方法")

    # 首先尝试 V2 方法
    print("\n    📋 第一阶段：尝试 V2 传统纯色带分析方法...")
    print("    🎨 使用预设的韩漫常见背景色进行分割，提高速度和效率...")

    v2_result = split_long_image_v2(
        long_image_path,
        output_split_dir,
        MIN_SOLID_COLOR_BAND_HEIGHT,
        SPLIT_BAND_COLORS_RGB,
        COLOR_MATCH_TOLERANCE,
        verbose=verbose
    )

    if v2_result and len(v2_result) >= 1:
        print(f"    ✅ V2 分割成功！共分割出 {len(v2_result)} 个片段。")
        print("    📄 正在尝试从 V2 分割结果创建 PDF...")

        # 尝试重打包
        repacked_v2_paths = repack_split_images(
            v2_result, output_split_dir, base_filename=subdir_name,
            max_size_mb=MAX_REPACKED_FILESIZE_MB, max_height_px=MAX_REPACKED_PAGE_HEIGHT_PX,
            verbose=verbose
        )

        if repacked_v2_paths:
            # 尝试创建 PDF
            created_pdf_path = create_pdf_from_images(
                repacked_v2_paths, pdf_output_dir, pdf_filename, verbose=verbose
            )

            if created_pdf_path:
                print(f"    ✅ V2 方法完全成功！PDF 已创建: {os.path.basename(created_pdf_path)}")
                return repacked_v2_paths, created_pdf_path
            else:
                print("    ❌ V2 分割成功但 PDF 创建失败，正在清理 V2 文件并切换到 V4 方法...")
                # 清理 V2 产生的所有文件
                print("    🧹 清理 V2 分割和重打包产生的所有文件...")
                for file_path in v2_result:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            print(f"      已删除 V2 分割文件: {os.path.basename(file_path)}")
                        except Exception as e:
                            print(f"      删除失败 {os.path.basename(file_path)}: {e}")

                for file_path in repacked_v2_paths:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            print(f"      已删除 V2 重打包文件: {os.path.basename(file_path)}")
                        except Exception as e:
                            print(f"      删除失败 {os.path.basename(file_path)}: {e}")
        else:
            print("    ❌ V2 分割成功但重打包失败，正在清理 V2 文件并切换到 V4 方法...")
            # 清理 V2 分割文件
            print("    🧹 清理 V2 分割产生的文件...")
            for file_path in v2_result:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"      已删除 V2 分割文件: {os.path.basename(file_path)}")
                    except Exception as e:
                        print(f"      删除失败 {os.path.basename(file_path)}: {e}")
    else:
        print("    ⚠️  V2 方法分割失败，正在切换到 V4 方法...")

    # 清理可能创建的失败 PDF
    potential_pdf_path = os.path.join(pdf_output_dir, pdf_filename)
    if os.path.exists(potential_pdf_path):
        try:
            os.remove(potential_pdf_path)
            print(f"      已删除失败的 PDF 文件: {pdf_filename}")
        except Exception as e:
            print(f"      删除失败的 PDF 文件失败: {e}")

    # 尝试 V4 方法
    print("\n    🚀 第二阶段：启用 V4 两阶段极速分析方法...")
    v4_result = split_long_image_v4(
        long_image_path,
        output_split_dir,
        QUANTIZATION_FACTOR,
        MAX_UNIQUE_COLORS_IN_BG,
        MIN_SOLID_COLOR_BAND_HEIGHT_V4,
        EDGE_MARGIN_PERCENT,
        verbose=verbose
    )

    if v4_result and len(v4_result) >= 1:
        print(f"    ✅ V4 分割成功！共分割出 {len(v4_result)} 个片段。")
        print("    📄 正在从 V4 分割结果创建 PDF...")

        # 尝试重打包
        repacked_v4_paths = repack_split_images(
            v4_result, output_split_dir, base_filename=subdir_name,
            max_size_mb=MAX_REPACKED_FILESIZE_MB, max_height_px=MAX_REPACKED_PAGE_HEIGHT_PX,
            verbose=verbose
        )

        if repacked_v4_paths:
            # 尝试创建 PDF
            created_pdf_path = create_pdf_from_images(
                repacked_v4_paths, pdf_output_dir, pdf_filename, verbose=verbose
            )

            if created_pdf_path:
                print(f"    ✅ V4 方法完全成功！PDF 已创建: {os.path.basename(created_pdf_path)}")
                return repacked_v4_paths, created_pdf_path
            else:
                print("    ❌ V4 分割成功但 PDF 创建失败。")
                return repacked_v4_paths, None
        else:
            print("    ❌ V4 分割成功但重打包失败。")
            return v4_result, None

    print("    ❌ 两种分割方法都未能有效分割图片，将使用原图。")

    # 如果两种方法都失败，复制原图并尝试创建 PDF
    dest_path = os.path.join(output_split_dir, os.path.basename(long_image_path))
    shutil.copy2(long_image_path, dest_path)

    created_pdf_path = create_pdf_from_images(
        [dest_path], pdf_output_dir, pdf_filename, verbose=verbose
    )

    return [dest_path], created_pdf_path


def _merge_image_list_for_repack(image_paths, output_path):
    """一个专门用于重打包的内部合并函数。"""
    if not image_paths:
        return False
    images_data, total_height, target_width = [], 0, 0
    for path in image_paths:
        try:
            with Image.open(path) as img:
                if target_width == 0:
                    target_width = img.width
                images_data.append({"path": path, "height": img.height})
                total_height += img.height
        except Exception:
            continue
    if not images_data or target_width == 0:
        return False
    merged_canvas = Image.new('RGB', (target_width, total_height))
    current_y = 0
    for item in images_data:
        with Image.open(item["path"]) as img:
            merged_canvas.paste(img.convert("RGB"), (0, current_y))
            current_y += item["height"]
    _save_png_fast(merged_canvas, output_path)
    return True


def repack_split_images(split_image_paths, output_dir, base_filename, max_size_mb, max_height_px, verbose=True):
    """按"双重限制"重新打包分割后的图片。（分桶逻辑与 V5 完全一致）"""
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
            with Image.open(img_path) as img:
                img_height = img.height
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
        if os.path.exists(path):
            os.remove(path)

    return natsorted(repacked_paths)


def create_pdf_from_images(image_paths_list, output_pdf_dir, pdf_filename_only, verbose=True):
    """从图片列表创建PDF。（编码参数与 V5 完全一致）"""
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

    if not safe_image_paths:
        return None

    os.makedirs(output_pdf_dir, exist_ok=True)
    pdf_full_path = os.path.join(output_pdf_dir, pdf_filename_only)

    images_for_pdf = [Image.open(p).convert('RGB') for p in safe_image_paths]
    if not images_for_pdf:
        return None

    try:
        images_for_pdf[0].save(pdf_full_path, save_all=True, append_images=images_for_pdf[1:], resolution=float(PDF_DPI), quality=PDF_IMAGE_JPEG_QUALITY, optimize=True)
        print(f"    成功创建 PDF: {pdf_full_path}")
        return pdf_full_path
    finally:
        for img_obj in images_for_pdf:
            img_obj.close()


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


# --- V6 单项目处理（可在子进程中运行） ---


def process_single_subdir(task):
    """处理单个项目子文件夹：合并 -> 智能分割+PDF创建 -> 清理 -> 移动成功项。

    处理流程与 V5 主循环完全一致；不同子文件夹之间互不依赖，可安全并行。
    返回结果字典（含 success / pdf_path / reason / elapsed）。
    """
    (root_input_dir, subdir_name, overall_pdf_output_dir, success_move_target_dir,
     task_index, task_total, decode_threads, verbose) = task

    result = {"subdir": subdir_name, "success": False, "pdf_path": None,
              "reason": None, "error": None, "elapsed": 0.0}
    start_time = time.time()

    print(f"\n\n{'='*15} 开始处理项目: {subdir_name} ({task_index}/{task_total}) {'='*15}", flush=True)
    try:
        current_processing_subdir = os.path.join(root_input_dir, subdir_name)
        path_long_image_output_dir = os.path.join(current_processing_subdir, MERGED_LONG_IMAGE_SUBDIR_NAME)
        path_split_images_output_dir = os.path.join(current_processing_subdir, SPLIT_IMAGES_SUBDIR_NAME)

        # 每次都清理旧的中间文件，以防上次失败残留
        if os.path.isdir(path_long_image_output_dir):
            shutil.rmtree(path_long_image_output_dir)
        if os.path.isdir(path_split_images_output_dir):
            shutil.rmtree(path_split_images_output_dir)

        created_long_image_path = merge_to_long_image(
            current_processing_subdir, path_long_image_output_dir,
            f"{subdir_name}_{LONG_IMAGE_FILENAME_BASE}.png", PDF_TARGET_PAGE_WIDTH_PIXELS,
            verbose=verbose, decode_threads=decode_threads
        )

        pdf_created_for_this_subdir = False
        created_pdf_path = None

        if created_long_image_path:
            # 调用 V5 融合分割函数（包含 PDF 创建失败自动切换逻辑）
            repacked_final_paths, created_pdf_path = split_long_image_hybrid_with_pdf_fallback(
                created_long_image_path,
                path_split_images_output_dir,
                overall_pdf_output_dir,
                f"{subdir_name}.pdf",
                subdir_name,
                verbose=verbose
            )

            if created_pdf_path:
                pdf_created_for_this_subdir = True
                result["pdf_path"] = created_pdf_path
                print(f"\n  ✅ 项目 '{subdir_name}' 处理成功！PDF 已创建: {os.path.basename(created_pdf_path)}", flush=True)
            else:
                print(f"\n  ❌ 项目 '{subdir_name}' 处理失败：无法创建 PDF 文件。", flush=True)
        else:
            result["reason"] = "未找到可合并的图片"

        if pdf_created_for_this_subdir:
            cleanup_intermediate_dirs(path_long_image_output_dir, path_split_images_output_dir)

            # --- 移动处理成功的文件夹 ---
            print(f"\n  --- 步骤 5: 移动已成功处理的项目文件夹 ---")
            source_folder_to_move = current_processing_subdir
            destination_parent_folder = success_move_target_dir

            try:
                print(f"    准备将 '{os.path.basename(source_folder_to_move)}' 移动到 '{os.path.basename(destination_parent_folder)}' 文件夹中...")
                shutil.move(source_folder_to_move, destination_parent_folder)
                moved_path = os.path.join(destination_parent_folder, os.path.basename(source_folder_to_move))
                print(f"    成功移动文件夹至: {moved_path}")
                result["success"] = True
            except Exception as e:
                print(f"    错误: 移动文件夹 '{os.path.basename(source_folder_to_move)}' 失败: {e}", flush=True)
                result["reason"] = "移动失败"
        else:
            print(f"  ❌ 项目文件夹 '{subdir_name}' 未能成功生成PDF，将保留中间文件以供检查。", flush=True)
            if not result["reason"]:
                result["reason"] = "PDF创建失败"

    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ 项目 '{subdir_name}' 处理时发生未捕获异常: {e}", flush=True)
        traceback.print_exc()
    finally:
        result["elapsed"] = time.time() - start_time
        print(f"{'='*15} '{subdir_name}' 处理完毕 ({result['elapsed']:.1f}s) {'='*15}", flush=True)

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="自动化图片批量处理流程 (V6 - 并行加速实验版)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-p', '--path',
        required=True,
        help='(必须) 指定包含一个或多个项目子文件夹的【根目录】路径。'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int, default=None,
        help='(可选) 并行进程数。默认根据 CPU 核心数与可用内存自动检测。'
    )
    parser.add_argument(
        '--serial',
        action='store_true',
        help='(可选) 强制单进程顺序模式（行为与 V5 一致）。'
    )
    args = parser.parse_args(argv)

    print("🚀 自动化图片批量处理流程 (V6 - 并行加速实验版)")
    print("💡 基于 V5 智能融合版：分割/合并/重打包/PDF 逻辑保持一致")
    print("⚡ V6 加速点: 多项目多进程并行 | V2/V4 扫描向量化 | 解码线程池预取 | 中间PNG快速压缩")
    print("📋 工作流程: 1.合并 -> 2.智能分割+PDF创建 -> 3.清理 -> 4.移动成功项")
    print("🔄 失败判定：V2方式分割后PDF创建失败时，清理V2分割文件并自动切换到V4方式")
    print("-" * 80)

    root_input_dir = os.path.abspath(args.path)
    if not os.path.isdir(root_input_dir):
        print(f"错误: 路径 '{root_input_dir}' 不是一个有效的目录或不存在。")
        return 1

    print(f"已选定根处理目录: {root_input_dir}")

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
        return 0

    sorted_subdirectories = natsorted(subdirectories)

    # --- V6 性能检测 ---
    if args.serial:
        workers, cpu_count, mem_note = 1, get_logical_cpu_count(), None
    else:
        workers, cpu_count, mem_note = detect_parallel_workers(len(sorted_subdirectories), args.workers)

    if workers <= 1:
        print(f"🔧 性能检测: 逻辑CPU {cpu_count} 核 | 单进程顺序模式 (--serial, 行为同 V5)")
        decode_threads = max(1, min(MAX_DECODE_THREADS, cpu_count))
        print(f"🧵 长图合并阶段使用 {decode_threads} 个解码线程")
    else:
        print(f"🔧 性能检测: 逻辑CPU {cpu_count} 核 | {mem_note}")
        print(f"⚡ 并行策略: {workers} 个并行进程 (每个进程内含图片解码线程池)")
        decode_threads = max(1, min(MAX_DECODE_THREADS, cpu_count // workers))

    task_total = len(sorted_subdirectories)
    if workers > 1:
        print(f"\n将并行处理以下 {task_total} 个项目文件夹: {', '.join(sorted_subdirectories)}")
    else:
        print(f"\n将按顺序处理以下 {task_total} 个项目文件夹: {', '.join(sorted_subdirectories)}")

    tasks = [
        (root_input_dir, subdir_name, overall_pdf_output_dir, success_move_target_dir,
         task_index, task_total, decode_threads, workers <= 1)
        for task_index, subdir_name in enumerate(sorted_subdirectories, start=1)
    ]

    results = []
    start_all = time.time()
    executor = None
    try:
        if workers <= 1:
            # --- 顺序模式（输出风格与 V5 一致） ---
            for i, task in enumerate(tasks):
                results.append(process_single_subdir(task))
                print_progress_bar(i + 1, task_total, prefix="总进度:", suffix='完成', length=40)
        else:
            # --- V6 并行模式 ---
            executor = ProcessPoolExecutor(max_workers=workers)
            future_map = {executor.submit(process_single_subdir, t): t[1] for t in tasks}
            done_count = 0
            for future in as_completed(future_map):
                done_count += 1
                name = future_map[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"subdir": name, "success": False, "pdf_path": None,
                              "reason": "进程异常", "error": str(exc), "elapsed": 0.0}
                results.append(result)
                if result.get("success"):
                    print(f"  ✅ [{result['subdir']}] 处理完成 ({result['elapsed']:.1f}s)", flush=True)
                else:
                    reason = result.get("reason") or result.get("error") or "未知原因"
                    print(f"  ❌ [{result['subdir']}] 处理失败: {reason}", flush=True)
                print_progress_bar(done_count, task_total, prefix="总进度:", suffix='完成', length=40)
    except KeyboardInterrupt:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
        print("\n\n⚠️ 操作被用户中断，已取消未开始的任务。")
        return 130
    finally:
        if executor is not None:
            executor.shutdown(wait=False)

    # --- 任务总结报告 ---
    total_elapsed = time.time() - start_all
    failed_subdirs_list = []
    for r in results:
        if not r.get("success"):
            if r.get("reason") == "移动失败":
                failed_subdirs_list.append(f"{r['subdir']} (移动失败)")
            else:
                failed_subdirs_list.append(r["subdir"])

    print("\n" + "=" * 80 + "\n【任务总结报告】\n" + "-" * 80)
    success_count = len(results) - len(failed_subdirs_list)
    print(f"总计处理项目: {len(results)} 个\n  - ✅ 成功: {success_count} 个\n  - ❌ 失败: {len(failed_subdirs_list)} 个")
    if failed_subdirs_list:
        print("\n失败项目列表 (已保留在原位):\n" + "\n".join(f"  - {d}" for d in failed_subdirs_list))
    print("-" * 80)
    if total_elapsed > 0 and results:
        avg = sum(r.get("elapsed", 0.0) for r in results) / len(results)
        print(f"⏱️  总耗时: {total_elapsed:.1f} 秒 | 并行进程数: {workers} | 单项目平均: {avg:.1f} 秒")
    print(f"所有成功生成的PDF文件（如有）已保存在: {overall_pdf_output_dir}")
    print(f"所有成功处理的原始项目文件夹（如有）已移至: {success_move_target_dir}")
    print("🎉 V6 并行加速实验版脚本执行完毕！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
