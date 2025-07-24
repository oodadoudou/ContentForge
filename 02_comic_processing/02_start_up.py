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
        print(" 1. [V5 智能融合] 双重保障分割算法 (★强烈推荐★)")
        print(" 2. [V2 快速流程] 合并、分割、重打包并生成 PDF")
        print(" 3. [V4 实验流程] 使用最新算法处理 (若V2分割失败可尝试)")
        print(" 4. [快速转换] 将图片文件夹直接转为 PDF (无优化)")
        print(" 5. [PDF 合并] 将各子文件夹内的所有PDF合并为单个文件")
        print(" 6. [PDF 转图片] 将PDF转为图片 (支持超长图分割)")
        print("----------")
        print(" 8. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        if choice == '1':
            # 运行V5智能融合版本，双重保障分割算法
            utils.run_script("image_processes_pipeline_v5.py", cwd=module_path)
        elif choice == '2':
            # 运行稳定的V2版本
            utils.run_script("image_processes_pipeline_v2.py", cwd=module_path)
        elif choice == '3':
            # 运行最新的V4版本，作为备用选项
            utils.run_script("image_processes_pipeline_v4.py", cwd=module_path)
        elif choice == '4':
            utils.run_script("convert_img_to_pdf.py", cwd=module_path)
        elif choice == '5':
            # 运行PDF合并脚本
            utils.run_script("merge_pdfs.py", cwd=module_path)
        elif choice == '6':
            # 运行PDF转图片（支持长图分割）的脚本
            utils.run_script("convert_long_pdf.py", cwd=module_path)
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