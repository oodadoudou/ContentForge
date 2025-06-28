import os
from PIL import Image
import natsort # 用于自然排序文件名 (e.g., img1, img2, img10)

# --- 全局配置 ---
# 支持的图片文件扩展名列表
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')

# 输出相关配置 (这些仍然可以硬编码或将来也改为交互式输入)
OUTPUT_SUBFOLDER_NAME = "merged_output"         # 在选定的输入目录内部创建的用于存放输出结果的子文件夹名称
MERGED_IMAGE_FILENAME = "stitched_long_image.png" # 合并后的图片文件名
# --- 全局配置结束 ---

def merge_images_vertically(image_folder_path, output_image_path):
    """
    将指定文件夹中的所有图片按文件名顺序垂直合并成一张大长图。

    参数:
        image_folder_path (str): 包含源图片的文件夹路径。
        output_image_path (str): 合并后大长图的完整保存路径。
    """
    # image_folder_path 已经是经过验证的目录路径
    
    try:
        image_filenames = [
            f for f in os.listdir(image_folder_path)
            if os.path.isfile(os.path.join(image_folder_path, f)) and f.lower().endswith(IMAGE_EXTENSIONS)
        ]
    except Exception as e: # Should not happen if image_folder_path is valid dir, but good for safety
        print(f"读取输入文件夹 '{image_folder_path}' 时发生意外错误: {e}")
        return

    if not image_filenames:
        print(f"在文件夹 '{os.path.abspath(image_folder_path)}' 中没有找到支持的图片文件。")
        print(f"支持的格式包括: {', '.join(IMAGE_EXTENSIONS)}")
        return

    sorted_image_filenames = natsort.natsorted(image_filenames)

    print(f"\n在目录 '{os.path.abspath(image_folder_path)}' 中找到 {len(sorted_image_filenames)} 张图片，将按以下顺序合并:")
    for name in sorted_image_filenames:
        print(f"  - {name}")

    images_info = []
    print("\n正在分析图片尺寸...")
    for filename in sorted_image_filenames:
        filepath = os.path.join(image_folder_path, filename)
        try:
            with Image.open(filepath) as img:
                images_info.append({
                    "path": filepath,
                    "width": img.width,
                    "height": img.height
                })
        except Exception as e:
            print(f"警告：无法打开或读取图片 '{filename}' 的尺寸信息，将跳过此图片: {e}")

    valid_images_info = [info for info in images_info if "width" in info]
    if not valid_images_info:
        print("没有有效的图片可供合并。")
        return

    total_height = sum(info['height'] for info in valid_images_info)
    max_width = max(info['width'] for info in valid_images_info)

    print(f"\n计算出的合并后图片尺寸: 宽度 = {max_width}px, 高度 = {total_height}px")

    merged_image = Image.new('RGBA', (max_width, total_height), (0, 0, 0, 0))

    current_y_offset = 0
    print("\n正在合并图片...")
    for item_info in valid_images_info:
        try:
            with Image.open(item_info["path"]) as img:
                img_rgba = img.convert("RGBA")
                x_offset = (max_width - img_rgba.width) // 2
                merged_image.paste(img_rgba, (x_offset, current_y_offset))
                current_y_offset += img_rgba.height
                print(f"  已粘贴: {os.path.basename(item_info['path'])}")
        except Exception as e:
            print(f"警告：粘贴图片 '{os.path.basename(item_info['path'])}' 时发生错误，已跳过: {e}")

    output_dir_for_image = os.path.dirname(output_image_path)
    if not os.path.exists(output_dir_for_image):
        try:
            os.makedirs(output_dir_for_image)
            print(f"\n已创建输出子目录: {os.path.abspath(output_dir_for_image)}")
        except Exception as e:
            print(f"错误：创建输出子目录 '{output_dir_for_image}' 失败: {e}")
            return


    try:
        print(f"\n正在保存合并后的图片 (使用最大无损压缩等级，可能需要一些时间)...")
        merged_image.save(output_image_path, format='PNG', optimize=True, compress_level=9)
        print(f"图片成功合并并保存为: {os.path.abspath(output_image_path)}")
        file_size_mb = os.path.getsize(output_image_path) / (1024 * 1024)
        print(f"最终文件大小: {file_size_mb:.2f} MB")
    except Exception as e:
        print(f"错误：保存合并后的图片失败: {e}")

if __name__ == "__main__":
    try:
        from PIL import Image
    except ImportError:
        print("错误：Pillow 库未安装。")
        print("请在终端或命令行运行: pip install Pillow")
        exit()
    try:
        import natsort
    except ImportError:
        print("错误：natsort 库未安装。")
        print("请在终端或命令行运行: pip install natsort")
        exit()

    print("欢迎使用图片合并脚本！")
    print("-" * 30)

    # --- 交互式获取输入目录 ---
    default_input_directory_name = "input_images_to_merge" # 默认的文件夹名
    selected_input_dir = ""

    while True:
        prompt_message = (
            f"请输入包含待合并图片的文件夹路径。\n"
            f"(例如: 'my_comics' 或 '/path/to/your/images')\n"
            f"如果直接按 Enter 键，将尝试使用当前目录下的 '{default_input_directory_name}' 文件夹: "
        )
        user_provided_path = input(prompt_message).strip()

        if not user_provided_path: # 用户按 Enter，使用默认
            current_path_to_check = default_input_directory_name
            print(f"尝试使用默认路径: ./{current_path_to_check}")
        else:
            current_path_to_check = user_provided_path
        
        # 转换为绝对路径以便清晰显示和判断
        abs_path_to_check = os.path.abspath(current_path_to_check)

        if os.path.isdir(abs_path_to_check):
            selected_input_dir = abs_path_to_check
            print(f"已选定输入目录: {selected_input_dir}")
            break 
        else:
            print(f"错误：路径 '{abs_path_to_check}' 不是一个有效的目录或不存在。")
            # 询问用户是否创建默认目录（如果用户尝试了默认路径且该路径不存在）
            if (not user_provided_path or current_path_to_check == default_input_directory_name) and not os.path.exists(abs_path_to_check):
                create_choice = input(f"目录 '{abs_path_to_check}' 不存在。是否现在创建它? (y/n): ").lower()
                if create_choice == 'y':
                    try:
                        os.makedirs(abs_path_to_check)
                        print(f"目录 '{abs_path_to_check}' 已创建。请将图片放入该目录后重新运行脚本或指定其他目录。")
                        # 可以选择在这里退出，让用户填充目录，或者继续循环
                        # For now, let's re-loop, user might want to specify another path.
                    except Exception as e:
                        print(f"创建目录 '{abs_path_to_check}' 失败: {e}")
            print("-" * 30) # 分隔符，准备下一次输入提示

    # --- 输入目录选定完毕 ---

    # 检查选定目录中是否有图片文件（早期反馈）
    found_images_in_dir = False
    try:
        for item in os.listdir(selected_input_dir):
            if os.path.isfile(os.path.join(selected_input_dir, item)) and item.lower().endswith(IMAGE_EXTENSIONS):
                found_images_in_dir = True
                break
    except Exception as e:
        print(f"检查目录 '{selected_input_dir}' 内容时出错: {e}")
        # Decide how to handle this, for now, let merge_images_vertically handle it if listdir fails later.

    if not found_images_in_dir:
        print(f"提示：在目录 '{selected_input_dir}' 中初步检查未直接找到支持的图片文件。")
        print(f"脚本将继续执行，但如果确实没有符合条件的图片，则不会生成合并图片。")
        # continue_anyway = input("是否仍要继续处理此目录? (y/n): ").lower()
        # if continue_anyway != 'y':
        #     print("脚本已中止。")
        #     exit()
    print("-" * 30)

    # 构建输出路径
    output_subdirectory_full_path = os.path.join(selected_input_dir, OUTPUT_SUBFOLDER_NAME)
    full_output_image_path = os.path.join(output_subdirectory_full_path, MERGED_IMAGE_FILENAME)

    # 调用合并函数
    merge_images_vertically(selected_input_dir, full_output_image_path)

    print("-" * 30)
    print("脚本处理完成。")