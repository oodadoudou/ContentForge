import os
import sys

# 将项目根目录添加到Python搜索路径中，以便能导入共享工具
# This assumes the script is in a subdirectory of the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_utils import utils

def menu_file_repair_and_utilities():
    """模块四: 文件修复与工具的独立菜单"""
    module_path_repair = '04_file_repair'
    module_path_utils = '06_utilities'
    
    # 加载全局设置
    settings = utils.load_settings()
    
    while True:
        utils.print_header("4. 文件修复与工具 (解决常见问题)")
        print("--- EPUB 修复 ---")
        print(" 1. 自动修复竖排版并转为简体中文")
        print(" 2. 修复 Kindle 等设备不显示封面的问题")
        print("\n--- TXT 修复 ---")
        print(" 3. TXT 文件格式化 (添加段落间距)")
        print(" 4. 修复 TXT 文件的编码问题 (解决乱码)")
        print("\n--- 辅助工具 ---")
        print(" 5. 在浏览器中批量打开 Bomtoon 链接")
        print("----------")
        print(" 8. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        if choice == '1':
            utils.run_script("epub_reformat_and_convert_v2.py", cwd=module_path_repair)
        elif choice == '2':
            utils.run_script("cover_repair.py", cwd=module_path_repair)
        elif choice == '3':
            utils.run_script("txt_reformat.py", cwd=module_path_repair)
        elif choice == '4':
            utils.run_script("fix_txt_encoding.py", cwd=module_path_repair)
        elif choice == '5':
            utils.run_script("open_bomtoon.py", cwd=module_path_utils)
        elif choice == '8':
            utils.show_usage(module_path_repair)
        elif choice == '0':
            # 返回主菜单（在子脚本中即为退出）
            break

if __name__ == "__main__":
    try:
        menu_file_repair_and_utilities()
    except KeyboardInterrupt:
        # 当用户在子菜单中按 Ctrl+C 时，优雅退出
        print("\n\n操作被用户中断。")
        sys.exit(0)
