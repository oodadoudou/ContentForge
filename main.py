import os
import sys
import json
import shlex
import shutil
import subprocess
import re

# =================================================================
#                 全局变量与路径设置
# =================================================================

# --- FIX: 将项目根目录添加到Python搜索路径中，以便能导入共享工具 ---
try:
    # 获取脚本文件所在的目录
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # 兼容在某些交互式环境中 __file__ 未定义的情况
    PROJECT_ROOT = os.getcwd()

# 将项目根目录添加到sys.path
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# --- NEW: 从共享模块导入所有工具函数 ---
from shared_utils import utils


# =================================================================
#                 系统设置相关函数
# =================================================================

def configure_default_path(first_time=False):
    """交互式配置默认工作目录"""
    if first_time:
        utils.print_header("首次运行设置")
        print("欢迎使用 ContentForge！这是一个功能强大的内容处理工具集。")
        print("为了方便后续操作，请先设置一个默认的工作目录。")
        print("例如：'D:\\Downloads' 或 '/Users/YourName/Documents'")
        print("之后所有模块需要输入路径时，都会将此目录作为默认选项。")
    else:
        utils.print_header("配置默认工作目录")
    
    current_path = utils.settings.get('default_work_dir', '未设置')
    
    while True:
        new_path = utils.get_input("请输入您的默认工作目录路径", default=current_path)
        if os.path.isdir(new_path):
            utils.settings['default_work_dir'] = new_path
            if utils.save_settings():
                print(f"\n✅ 默认工作目录已更新为: {new_path}")
            break
        else:
            print(f"❌ 错误: 路径 '{new_path}' 不是一个有效的目录，请重新输入。")
    
    if not first_time:
        input("\n按回车键返回设置菜单...")


def manage_ai_config():
    """交互式地加载、显示、更新AI配置"""
    utils.print_header("AI 翻译配置管理")
    config = utils.settings.get('ai_config', {})
    print("当前 AI 配置:")
    print(f"  API Key: {config.get('api_key', '未设置')}")
    print(f"  Base URL: {config.get('base_url', '未设置')}")
    print(f"  Model Name: {config.get('model_name', '未设置')}")
    print("-" * 60)

    if utils.get_input("是否要修改配置? (按回车确认, 输入 n 取消): ").lower() != 'n':
        api_key = utils.get_input("请输入新的 API Key", config.get('api_key'))
        base_url = utils.get_input("请输入新的 Base URL", config.get('base_url'))
        model_name = utils.get_input("请输入新的 Model Name", config.get('model_name'))
        utils.settings['ai_config'] = {
            'api_key': api_key,
            'base_url': base_url,
            'model_name': model_name
        }
        utils.save_settings()
        print("✅ AI 配置已更新。")


def menu_install_dependencies():
    """一键安装/更新依赖"""
    utils.print_header("安装/更新项目依赖")
    
    requirements_path = os.path.join(utils.PROJECT_ROOT, 'requirements.txt')

    if not os.path.exists(requirements_path):
        print(f"❌ 错误: 在项目根目录中找不到 'requirements.txt' 文件。")
        input("按回车键返回...")
        return
        
    print(f"将使用 pip 安装 '{requirements_path}' 中的所有依赖。")
    if utils.get_input("是否继续? (按回车确认, 输入 n 取消): ").lower() != 'n':
        try:
            # --- 修改：简化指令以提高跨平台兼容性 ---
            command = f'pip install -r "{requirements_path}"'
            print(f"\n▶️  正在执行: {command}")
            print("注意：此操作依赖于 'pip' 在您系统的环境变量中。")
            print("-" * 60)
            subprocess.check_call(command, shell=True)
            print("\n✅ 依赖安装成功！")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ 依赖安装失败。错误: {e}")
        except FileNotFoundError:
            print("\n❌ 错误: 'pip' 命令未找到。请确保 Python 和 Pip 已正确安装并已添加到您系统的 PATH 环境变量中。")
        except Exception as e:
            print(f"\n❌ 发生未知错误: {e}")
    
    input("按回车键返回菜单...")

def menu_system_settings():
    """模块六: 系统设置与依赖"""
    while True:
        utils.print_header("6. 系统设置与依赖")
        print(" 1. 配置默认工作目录")
        print(" 2. 配置 AI 翻译 API")
        print(" 3. 安装/更新项目依赖 (pip)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        if choice == '1':
            configure_default_path()
        elif choice == '2':
            manage_ai_config()
            input("\n按回车键返回...")
        elif choice == '3':
            menu_install_dependencies()
        elif choice == '0':
            break

# =================================================================
#                         主函数
# =================================================================

def main():
    """主函数，显示主菜单并调用子模块入口。"""
    
    # --- 新增：首次运行检查 ---
    settings_path = os.path.join(PROJECT_ROOT, 'shared_assets', 'settings.json')

    # 检查配置文件是否存在
    if not os.path.exists(settings_path):
        # 如果不存在，则认为是首次运行，引导用户进行配置
        configure_default_path(first_time=True)
    
    # 无论文件之前是否存在，现在都加载配置
    # 如果文件是新创建的，会加载新配置；如果已存在，则加载现有配置
    utils.load_settings()

    # 保留一个备用检查：防止 settings.json 存在但 default_work_dir 无效
    if not os.path.isdir(utils.settings.get('default_work_dir', '')):
        print("\n警告：检测到配置文件中的默认工作目录无效或未设置。")
        configure_default_path(first_time=False)


    main_menu = {
        '1': ('内容获取 (从网站下载漫画)', '01_acquisition/01_start_up.py'),
        '2': ('漫画处理与生成 (图片转PDF)', '02_comic_processing/02_start_up.py'),
        '3': ('电子书处理与生成 (TXT/EPUB/HTML)', '03_ebook_workshop/03_start_up.py'),
        '4': ('文件修复与工具 (解决常见问题)', '04_file_repair/04_start_up.py'),
        '5': ('文件库管理 (整理、归档、重命名)', '05_library_organization/05_start_up.py'),
        '6': ('系统设置与依赖', menu_system_settings),
        '0': ('退出程序', lambda: sys.exit(0)) # 使用lambda包装以统一调用方式
    }

    while True:
        utils.print_header("欢迎使用 ContentForge 主菜单")
        for key, (text, _) in main_menu.items():
            if key != '0':
                print(f" {key}. {text}")
        print(" 0. 退出程序")

        choice = utils.get_input("请选择一个模块")
        
        if choice in main_menu:
            action = main_menu[choice][1]
            if isinstance(action, str): # 如果是脚本路径
                script_path = os.path.join(PROJECT_ROOT, action)
                subprocess.run([sys.executable, script_path], cwd=PROJECT_ROOT)
            else: # 如果是函数
                if choice == '0':
                     print("\n\n感谢使用 ContentForge！(｡･ω･｡)ﾉ♡")
                action()
        else:
            print("无效输入，请重新选择。")
            input("按回车键继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n感谢使用 ContentForge！(｡･ω･｡)ﾉ♡")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        print(f"\n发生意外的顶层错误: {e}")
        sys.exit(1)