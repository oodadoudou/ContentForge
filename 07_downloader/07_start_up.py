import os
import sys

# 将项目根目录添加到Python搜索路径中，以便能导入共享工具
# This assumes the script is in a subdirectory of the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_utils import utils

def menu_downloader():
    """模块七: 下载器的独立菜单"""
    module_path = '07_downloader'
    
    # 加载全局设置，以备将来可能的扩展使用
    settings = utils.load_settings()
    
    while True:
        utils.print_header("7. 通用下载器模块")
        print(" 1. [Diritto] 小说下载器")
        print("----------")
        print(" 8. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        if choice == '1':
            # 运行 Diritto 小说下载器
            utils.run_script("diritto_downloader.py", cwd=module_path)
        elif choice == '8':
            # 显示本模块的 README.md
            utils.show_usage(module_path)
        elif choice == '0':
            # 返回主菜单
            break

if __name__ == "__main__":
    try:
        menu_downloader()
    except KeyboardInterrupt:
        # 当用户在子菜单中按 Ctrl+C 时，优雅退出
        print("\n\n操作被用户中断。")
        sys.exit(0)