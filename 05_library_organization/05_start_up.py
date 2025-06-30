import os
import sys

# 将项目根目录添加到Python搜索路径中，以便能导入共享工具
# This assumes the script is in a subdirectory of the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_utils import utils

def menu_library_organization():
    """模块五: 文件库管理的独立菜单 (已精简)"""
    module_path = '05_library_organization'
    
    # 加载全局设置
    settings = utils.load_settings()
    
    while True:
        utils.print_header("5. 文件库管理 (整理与工具)")
        print(" 1. [智能整理] 自动分组、翻译并添加拼音前缀重命名")
        print(" 2. [工具] 从 EPUB 批量提取 CSS 文件")
        print("----------")
        print(" 8. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        if choice == '1':
            # 主程序在调用此模块前会引导用户完成AI配置
            utils.run_script("translate_and_org_dirs.py", cwd=module_path)
        elif choice == '2':
            # 此脚本会引导用户输入要处理的目录
            utils.run_script("extract_epub_css.py", cwd=module_path)
        elif choice == '8':
            utils.show_usage(module_path)
        elif choice == '0':
            # 返回主菜单（在子脚本中即为退出）
            break

if __name__ == "__main__":
    try:
        menu_library_organization()
    except KeyboardInterrupt:
        # 当用户在子菜单中按 Ctrl+C 时，优雅退出
        print("\n\n操作被用户中断。")
        sys.exit(0)
