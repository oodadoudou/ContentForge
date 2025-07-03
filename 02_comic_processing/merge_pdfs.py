import os
import sys
import re
import pikepdf
import natsort
import logging
import json

# --- 配置 ---
# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 定义合并后PDF存放的子目录名称
MERGED_PDF_SUBDIR_NAME = "merged_pdf"

# --- 项目路径和设置加载 ---
try:
    # 根据脚本位置推断项目根目录 (.../ContentForge/)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.append(PROJECT_ROOT)
except NameError:
    # 在无法使用 __file__ 的环境中运行时, 使用当前工作目录作为后备
    PROJECT_ROOT = os.getcwd()

def load_settings():
    """
    从项目根目录的 'shared_assets/settings.json' 文件中加载设置。
    """
    # 更新: 指向 shared_assets 子文件夹
    settings_path = os.path.join(PROJECT_ROOT, "shared_assets", "settings.json")
    default_settings = {"default_input_directory": ""}
    
    if not os.path.exists(settings_path):
        logging.warning(f"配置文件未找到: {settings_path}。")
        return default_settings
    
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            logging.info(f"成功读取配置文件: {settings_path}")
            return json.load(f)
    except json.JSONDecodeError:
        logging.error(f"解析 {settings_path} 出错, 请检查文件格式是否为有效的JSON。")
        return default_settings
    except Exception as e:
        logging.error(f"读取 {settings_path} 时发生未知错误: {e}")
        return default_settings

# --- 已修改: 获取根目录的函数 ---
def get_root_directory():
    """
    获取要处理的根目录。
    优先级顺序: 1. 命令行参数 -> 2. 用户手动输入 -> 3. settings.json中的默认值 -> 4. 当前工作目录
    """
    # 优先级1: 检查是否通过命令行参数传入了路径
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
        print(f"    - 检测到命令行参数, 将使用指定目录: {root_dir}")
        return root_dir
    
    # 优先级3: 从 settings.json 加载默认路径
    settings = load_settings()
    default_path_from_settings = settings.get("default_input_directory", "").strip()

    try:
        # 根据是否从配置文件中加载到有效路径, 来决定默认路径和提示信息
        if default_path_from_settings and os.path.isdir(default_path_from_settings):
            # 情况A: 配置文件存在且路径有效
            prompt_message = (
                f"\n- 请输入目标根文件夹的路径。\n"
                f"  (直接按 Enter 将使用配置文件中的默认路径: '{default_path_from_settings}'): "
            )
            fallback_path = default_path_from_settings
            fallback_source = "配置文件"
        else:
            # 情况B: 配置文件不存在或路径无效, 使用当前目录作为后备
            cwd = os.getcwd()
            prompt_message = (
                f"\n- 请输入目标根文件夹的路径。\n"
                f"  (配置文件中无有效路径, 直接按 Enter 将使用当前目录: '{cwd}'): "
            )
            fallback_path = cwd
            fallback_source = "当前工作目录"

        # 优先级2: 获取用户手动输入
        user_input = input(prompt_message).strip()

        if user_input:
            print(f"\n  您输入了路径: {user_input}")
            return user_input
        else:
            # 用户直接按回车, 使用情况A或B确定的后备路径
            print(f"\n  使用来自<{fallback_source}>的路径: {fallback_path}")
            return fallback_path
            
    except Exception as e:
        print(f"\n    - 读取输入时出错: {e}")
        sys.exit("    - 程序终止。")


def natural_sort_key(s: str) -> list:
    """
    为文件名生成自然排序的键。
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]


def merge_pdfs_in_directory(root_dir: str):
    """
    合并指定目录结构下的PDF文件。
    """
    # 创建 merged_pdf 输出目录
    output_dir = os.path.join(root_dir, MERGED_PDF_SUBDIR_NAME)
    os.makedirs(output_dir, exist_ok=True)
    logging.info(f"输出目录 '{output_dir}' 已准备就绪。")

    subfolders = [d.path for d in os.scandir(root_dir) if d.is_dir() and d.name != MERGED_PDF_SUBDIR_NAME]
    
    if not subfolders:
        logging.warning(f"在根目录 '{root_dir}' 下没有找到需要处理的子文件夹。")
        return

    print(f"\n--- 发现 {len(subfolders)} 个子文件夹,准备开始合并 ---")

    for subfolder_path in natsort.natsorted(subfolders):
        subfolder_name = os.path.basename(subfolder_path)
        logging.info(f"===== 开始处理子文件夹: {subfolder_name} =====")

        pdf_files_to_merge = []
        logging.info(f"正在 '{subfolder_name}' 及其所有子目录中搜索PDF文件...")
        for dirpath, _, filenames in os.walk(subfolder_path):
            for filename in filenames:
                if filename.lower().endswith('.pdf'):
                    pdf_path = os.path.join(dirpath, filename)
                    pdf_files_to_merge.append(pdf_path)
                    logging.info(f"  [找到文件] {os.path.relpath(pdf_path, subfolder_path)}")

        pdf_files_to_merge = natsort.natsorted(pdf_files_to_merge)

        if not pdf_files_to_merge:
            logging.warning(f"在 '{subfolder_name}' 中没有找到任何PDF文件, 跳过。")
            print(f"  🟡 在 '{subfolder_name}' 中未发现PDF, 跳过。\n")
            continue
        
        print(f"  - 在 '{subfolder_name}' 中总共找到 {len(pdf_files_to_merge)} 个PDF文件, 准备合并。")
        
        output_pdf_path = os.path.join(output_dir, f"{subfolder_name}.pdf")
        new_pdf = pikepdf.Pdf.new()

        try:
            for i, pdf_path in enumerate(pdf_files_to_merge):
                try:
                    with pikepdf.open(pdf_path) as src_pdf:
                        new_pdf.pages.extend(src_pdf.pages)
                        print(f"    ({i+1}/{len(pdf_files_to_merge)}) 已添加: {os.path.basename(pdf_path)}")
                except Exception as e:
                    logging.error(f"    合并文件 '{os.path.basename(pdf_path)}' 时出错: {e}")

            if len(new_pdf.pages) > 0:
                new_pdf.save(output_pdf_path)
                print(f"  ✅ 成功! 合并后的文件保存在: '{output_pdf_path}'\n")
            else:
                logging.warning(f"'{subfolder_name}' 的合并结果为空, 未生成PDF文件。")
        except Exception as e:
            logging.error(f"保存合并后的PDF '{output_pdf_path}' 时发生严重错误: {e}")
        finally:
             pass

def main():
    """
    主执行函数
    """
    print("\n--- PDF 合并工具 ---")
    print("本工具将自动查找每个子文件夹(及其所有后代目录)中的PDF文件,")
    print("并将它们合并成一个以该子文件夹命名的PDF文件。")
    
    root_dir = get_root_directory()

    if not os.path.isdir(root_dir):
        print(f"\n错误: 提供的路径 '{root_dir}' 不是一个有效的目录。")
        sys.exit("程序终止。")
    
    print(f"\n--- 开始处理, 根目录: {root_dir} ---")
    merge_pdfs_in_directory(root_dir)
    print("\n--- 所有操作完成 ---")

if __name__ == "__main__":
    main()