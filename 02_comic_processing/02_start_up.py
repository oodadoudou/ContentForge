import os
import sys

# 将项目根目录添加到Python搜索路径中，以便能导入共享工具
# This assumes the script is in a subdirectory of the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_utils import utils

def menu_comic_processing():
    """模块二: 漫画处理与生成的独立菜单"""
    module_path = '02_comic_processing'
    
    # 加载全局设置，以便在将来的脚本中使用
    settings = utils.load_settings()
    
    while True:
        utils.print_header("2. 漫画处理与生成 (图片转PDF)")
        print(" 1. [智能流程] 合并、分割、重打包图片并生成 PDF (推荐)")
        print(" 2. [旧版流程] 合并、分割图片并生成 PDF")
        print(" 3. [快速转换] 将图片文件夹直接转为 PDF (无优化)")
        print("----------")
        print(" 8. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        if choice == '1':
            utils.run_script("image_processes_pipeline_v2.py", cwd=module_path)
        elif choice == '2':
            utils.run_script("image_processes_pipeline_v1.py", cwd=module_path)
        elif choice == '3':
            utils.run_script("convert_to_pdf.py", cwd=module_path)
        elif choice == '8':
            utils.show_usage(module_path)
        elif choice == '0':
            # 返回主菜单（在子脚本中即为退出）
            break

if __name__ == "__main__":
    try:
        menu_comic_processing()
    except KeyboardInterrupt:
        # 当用户在子菜单中按 Ctrl+C 时，优雅退出
        print("\n\n操作被用户中断。")
        sys.exit(0)
