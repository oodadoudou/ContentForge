import os
import sys

# 将项目根目录添加到Python搜索路径中，以便能导入共享工具
# This assumes the script is in a subdirectory of the project root
# 确保可以找到 shared_utils
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from shared_utils import utils

def menu_library_organization():
    """模块五: 文件库管理的独立菜单"""
    module_path = '05_library_organization'
    
    while True:
        utils.clear_screen()
        utils.print_header("5. 文件库管理 (整理与工具)")
        print(" 1. [智能整理] 自动分组、翻译并添加拼音前缀重命名")
        print(" 2. [工具] 从 EPUB 批量提取 CSS 文件")
        print(" 3. [工具] 文件夹加密与解密") # <-- 新增的启动项
        print("----------")
        print(" 8. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        
        # 使用共享工具中的 get_input
        choice = utils.get_input("请选择")

        if choice == '1':
            # 主程序在调用此模块前会引导用户完成AI配置
            utils.run_script("translate_and_org_dirs.py", cwd=module_path)
            input("\n按回车键返回菜单...")
        
        elif choice == '2':
            # 此脚本会引导用户输入要处理的目录
            utils.run_script("extract_epub_css.py", cwd=module_path)
            input("\n按回车键返回菜单...")

        elif choice == '3': # <-- 新增的逻辑
            # 调用新集成的文件夹加密/解密工具
            utils.run_script("folder_codec.py", cwd=module_path)
            # folder_codec.py 内部有退出机制，这里不需要 input()
            
        elif choice == '8':
            utils.show_usage(module_path)
            input("\n按回车键返回菜单...")

        elif choice == '0':
            # 返回主菜单（在子脚本中即为退出）
            break

        else:
            input("无效输入，请按回车键重试...")


if __name__ == "__main__":
    try:
        menu_library_organization()
    except KeyboardInterrupt:
        # 当用户在子菜单中按 Ctrl+C 时，优雅退出
        print("\n\n操作被用户中断。")
        sys.exit(0)