import os
import sys
import json
import shlex
import subprocess

# =================================================================
#                 全局路径与配置
# =================================================================

# 定义项目根目录，确保所有路径操作都基于此
try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    PROJECT_ROOT = os.path.dirname(os.getcwd())

# 定义共享资源和配置文件的绝对路径
SHARED_ASSETS_PATH = os.path.join(PROJECT_ROOT, "shared_assets")
SETTINGS_FILE_PATH = os.path.join(SHARED_ASSETS_PATH, "settings.json")

# 全局设置变量
settings = {}

# =================================================================
#                 通用辅助函数
# =================================================================

def clear_screen():
    """清空终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """打印带标题的分割线"""
    clear_screen()
    print("=" * 60)
    print(f"{title:^60}")
    print("=" * 60)

def run_script(command, cwd="."):
    """
    统一的脚本执行函数。
    :param command: 要执行的脚本名或命令。
    :param cwd: 脚本执行时的工作目录(相对于PROJECT_ROOT)。
    """
    absolute_cwd = os.path.join(PROJECT_ROOT, cwd)
    try:
        # shlex.split 用于正确处理带空格的路径和参数
        args = [sys.executable] + shlex.split(command)
        print(f"\n▶️  正在执行: {' '.join(args)}")
        print(f"   工作目录: {os.path.abspath(absolute_cwd)}")
        print("-" * 60)
        process = subprocess.Popen(args, cwd=absolute_cwd)
        process.wait()
    except FileNotFoundError:
        print(f"❌ 错误: 找不到脚本 '{command.split()[0]}'")
    except Exception as e:
        print(f"❌ 执行脚本时发生未知错误: {e}")
    
    print("-" * 60)
    input("按回车键返回菜单...")

def get_input(prompt, default=None):
    """获取用户输入，支持默认值"""
    if default is not None:
        return input(f"{prompt} (默认: {default}): ") or default
    else:
        return input(f"{prompt}: ")

def show_usage(module_path):
    """读取并显示模块的用法介绍 (README.md)"""
    readme_path = os.path.join(PROJECT_ROOT, module_path, 'README.md')
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            print_header(f"模块用法说明: {os.path.basename(module_path)}")
            print(f.read())
            print("=" * 60)
            input("按回车键返回菜单...")
    except FileNotFoundError:
        print(f"ℹ️  未找到模块 '{module_path}' 的 README.md 用法说明。")
        input("按回车键返回菜单...")

def load_settings():
    """加载全局设置"""
    global settings
    if os.path.exists(SETTINGS_FILE_PATH):
        try:
            with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            settings = {}
    else:
        settings = {}

    # 确保基本结构存在，避免后续代码出错
    if 'default_work_dir' not in settings:
        settings['default_work_dir'] = os.path.join(os.path.expanduser('~'), 'Downloads')
    if 'ai_config' not in settings:
        settings['ai_config'] = {
            'api_key': 'YOUR_API_KEY',
            'base_url': 'YOUR_API_BASE_URL',
            'model_name': 'YOUR_MODEL_NAME'
        }
    return settings

def save_settings():
    """保存全局设置"""
    try:
        os.makedirs(SHARED_ASSETS_PATH, exist_ok=True)
        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"\n❌ 保存设置失败: {e}")
        return False
        