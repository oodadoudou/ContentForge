#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shlex
import shutil
import json
import re

# --- 全局配置 ---
# 获取脚本所在的根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 定义各个功能模块的路径
ACQUISITION_PATH = os.path.join(PROJECT_ROOT, "01_acquisition")
COMIC_PROCESSING_PATH = os.path.join(PROJECT_ROOT, "02_comic_processing")
EBOOK_WORKSHOP_PATH = os.path.join(PROJECT_ROOT, "03_ebook_workshop")
FILE_REPAIR_PATH = os.path.join(PROJECT_ROOT, "04_file_repair")
LIBRARY_ORGANIZATION_PATH = os.path.join(PROJECT_ROOT, "05_library_organization")
UTILITIES_PATH = os.path.join(PROJECT_ROOT, "06_utilities")
SHARED_ASSETS_PATH = os.path.join(PROJECT_ROOT, "shared_assets")
SETTINGS_FILE_PATH = os.path.join(SHARED_ASSETS_PATH, "settings.json")

# 全局设置变量
global_settings = {}

# --- 辅助函数 ---
def clear_screen():
    """清空终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """打印带标题的分割线"""
    clear_screen()
    print("=" * 60)
    print(f"{' ' * ((60 - len(title)) // 2)}{title}")
    print("=" * 60)
    print()

def run_script(command, cwd=None):
    """统一的脚本执行函数。"""
    try:
        args = shlex.split(command)
        print(f"\n▶️  正在执行命令: {' '.join(args)}")
        print("-" * 60)
        python_executable = sys.executable
        final_args = [python_executable] + args[1:] if args[0] in ['python', 'python3'] else args
        subprocess.run(final_args, cwd=cwd, check=True)
        print("-" * 60)
        print("✅ 命令执行成功！")
    except FileNotFoundError:
        print(f"❌ 错误: 找不到命令或脚本 '{args[0]}'。请检查路径是否正确。")
    except subprocess.CalledProcessError as e:
        print(f"❌ 错误: 脚本执行出错，返回码 {e.returncode}。")
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
    input("\n按回车键返回菜单...")

def get_input(prompt, default=None):
    """获取用户输入，支持默认值"""
    if default:
        return input(f"{prompt} (默认: {default}): ") or default
    else:
        return input(f"{prompt}: ")

def show_usage(module_path):
    """读取并显示模块的用法介绍 (README.md)"""
    readme_path = os.path.join(module_path, "README.md")
    print_header("功能用法介绍")
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            print(f.read())
    else:
        print(f"未找到用法说明文件: {readme_path}")
    input("\n按回车键返回...")

# --- 新增：设置管理 ---
def load_settings():
    """加载全局设置"""
    global global_settings
    try:
        if os.path.exists(SETTINGS_FILE_PATH):
            with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
                global_settings = json.load(f)
        else:
            global_settings = {}
    except (json.JSONDecodeError, IOError):
        global_settings = {}

def save_settings():
    """保存全局设置"""
    try:
        os.makedirs(SHARED_ASSETS_PATH, exist_ok=True)
        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(global_settings, f, indent=4)
        return True
    except IOError as e:
        print(f"\n❌ 保存设置失败: {e}")
        return False

def configure_default_path(first_time=False):
    """交互式配置默认工作目录"""
    global global_settings
    if first_time:
        print_header("首次运行设置")
        print("为了方便使用，请先设置一个默认的工作目录。")
        print("之后所有需要输入路径的地方，都会将此目录作为默认选项。")
    else:
        print_header("设置默认工作目录")
    
    current_path = global_settings.get('default_work_dir')
    while True:
        new_path = get_input("请输入您的默认工作目录路径", default=current_path)
        if os.path.isdir(new_path):
            global_settings['default_work_dir'] = new_path
            if save_settings():
                print(f"\n✅ 默认工作目录已更新为: {new_path}")
            break
        else:
            print(f"❌ 错误: 路径 '{new_path}' 不是一个有效的目录，请重新输入。")
    
    if not first_time:
        input("\n按回车键返回设置菜单...")

def manage_ai_config():
    """交互式地加载、显示、更新AI配置"""
    global global_settings
    config = global_settings.get('ai_config', {})
    
    while True:
        print_header("AI 翻译配置")
        if config:
            masked_key = config.get('api_key', '')
            if len(masked_key) > 8:
                masked_key = f"{masked_key[:4]}...{masked_key[-4:]}"
            
            print("检测到已保存的配置：")
            print(f"  [1] API Base URL: {config.get('base_url', '未设置')}")
            print(f"  [2] 模型名称:       {config.get('model_name', '未设置')}")
            print(f"  [3] API Key:       {masked_key}")
            print("-" * 60)
            
            use_current = get_input("是否使用此配置? (y/n, n代表修改)", default="y").lower()
            if use_current == 'y':
                return config
        
        print("请输入新的 AI 配置信息：")
        config['base_url'] = get_input("  [1/3] 请输入 API Base URL", default=config.get('base_url', "https://ark.cn-beijing.volces.com/api/v3/chat/completions"))
        config['model_name'] = get_input("  [2/3] 请输入模型名称", default=config.get('model_name', "doubao-seed-1-6-thinking-250615"))
        config['api_key'] = get_input("  [3/3] 请输入您的 API Key")
        
        global_settings['ai_config'] = config
        if save_settings():
            print("\n✅ AI 配置已成功保存。")
        return config
        
def menu_settings():
    """设置菜单"""
    while True:
        print_header("全局设置")
        print("1. 设置默认工作目录")
        print("2. 配置 AI 翻译")
        print("\n0. 返回主菜单")
        choice = get_input("请输入选项")

        if choice == '1':
            configure_default_path()
        elif choice == '2':
            manage_ai_config()
        elif choice == '0':
            break
        else:
            print("无效输入，请重试。")

def run_translation_with_config(config):
    """使用给定的配置运行翻译脚本"""
    if not all([config.get('base_url'), config.get('model_name'), config.get('api_key')]):
        print("❌ AI 配置不完整，无法继续。")
        input("\n按回车键返回菜单...")
        return

    source_script_path = os.path.join(LIBRARY_ORGANIZATION_PATH, "translate_and_org_dirs.py")
    temp_script_path = os.path.join(LIBRARY_ORGANIZATION_PATH, "_temp_runner.py")
    
    try:
        with open(source_script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()

        script_content = re.sub(r'^(API_URL\s*=\s*").*(")', f'API_URL = "{config["base_url"]}"', script_content, flags=re.MULTILINE)
        script_content = re.sub(r'^(API_BEARER_TOKEN\s*=\s*").*(")', f'API_BEARER_TOKEN = "{config["api_key"]}"', script_content, flags=re.MULTILINE)
        script_content = re.sub(r'^(API_MODEL\s*=\s*").*(")', f'API_MODEL = "{config["model_name"]}"', script_content, flags=re.MULTILINE)
        
        with open(temp_script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
            
        run_script(f'python "{temp_script_path}"')

    except Exception as e:
        print(f"❌ 准备或执行翻译脚本时出错: {e}")
    finally:
        if os.path.exists(temp_script_path):
            os.remove(temp_script_path)
        else:
            input("\n按回车键返回菜单...")

def archive_folders_dynamically(source_base_dir, target_dir, suffix_to_find):
    """动态地、递归地移动文件夹。"""
    print_header("归档已处理文件夹")
    print(f"[*] 开始扫描源目录: '{source_base_dir}'")
    print(f"    将把所有以 '{suffix_to_find}' 结尾的文件夹移动到: '{target_dir}'")
    print("-" * 60)

    try:
        os.makedirs(target_dir, exist_ok=True)
        found_any = False
        
        for dirpath, dirnames, _ in os.walk(source_base_dir):
            for dirname in dirnames[:]:
                if dirname.endswith(suffix_to_find):
                    found_any = True
                    full_source_path = os.path.join(dirpath, dirname)
                    print(f"[*] 找到匹配文件夹: {full_source_path}")
                    try:
                        print(f"    -> 正在移动...")
                        shutil.move(full_source_path, target_dir)
                        print(f"    -> 成功移动到 '{target_dir}'")
                        dirnames.remove(dirname)
                    except Exception as e:
                        print(f"    -> 移动失败: {e}")
        
        if not found_any:
            print("\n[*] 扫描完成，未找到任何匹配的文件夹。")
        else:
            print("\n[*] 所有匹配的文件夹均已处理完毕。")
    except Exception as e:
        print(f"❌ 归档过程中发生错误: {e}")
    
    input("\n按回车键返回菜单...")


# --- 功能菜单定义（部分） ---
def menu_install_dependencies():
    """一键安装/更新依赖"""
    print_header("一键安装/更新所有依赖")
    
    requirements = [
        "httpx", "beautifulsoup4", "pycryptodome", "Pillow", "natsort",
        "opencc-python-reimplemented", "zhconv", "pandas", "EbookLib", "lxml",
        "tqdm", "requests", "pypinyin", "browser-cookie3", "markdown2",
    ]
    
    requirements_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    
    print("将生成/更新 requirements.txt 文件...")
    try:
        with open(requirements_path, "w", encoding="utf-8") as f:
            f.write("\n".join(requirements) + "\n")
        print(f"✅ requirements.txt 已在 '{PROJECT_ROOT}' 中创建/更新。")
    except Exception as e:
        print(f"❌ 创建 requirements.txt 文件失败: {e}")
        input("\n按回车键返回菜单...")
        return
        
    print("\n即将开始安装所有必需的 Python 库。过程可能需要几分钟...")
    confirm = get_input("是否继续? (y/n)", default="y")
    
    if confirm.lower() == 'y':
        command = f'pip install --upgrade -r "{requirements_path}"'
        run_script(command)
    else:
        print("操作已取消。")
        input("\n按回车键返回菜单...")

def menu_acquisition():
    """模块一: 内容获取"""
    while True:
        print_header("1. 内容获取 (Bomtoon 下载)")
        print("1. [自动更新] 更新/生成登录凭证 (⭐第一步)")
        print("2. 列出已购买的所有漫画")
        print("3. 搜索漫画")
        print("4. 列出指定漫画的章节")
        print("5. 下载指定章节")
        print("6. 下载漫画全部章节")
        print("7. 按序号下载章节")
        print("\n9. 功能用法介绍")
        print("0. 返回主菜单")
        choice = get_input("请输入选项")

        default_dir = global_settings.get('default_work_dir', ".")
        script_path = os.path.join(ACQUISITION_PATH, "bomtoontwext.py")
        command_base = f'python "{script_path}"'

        if choice == '1':
            script_path_update = os.path.join(ACQUISITION_PATH, "update_token.py")
            run_script(f'python "{script_path_update}"', cwd=ACQUISITION_PATH)
        elif choice in ['2', '3', '4']:
            if choice == '2':
                run_script(f'{command_base} list-comic', cwd=ACQUISITION_PATH)
            elif choice == '3':
                keyword = get_input("请输入漫画关键词")
                run_script(f'{command_base} search "{keyword}"', cwd=ACQUISITION_PATH)
            elif choice == '4':
                comic_id = get_input("请输入漫畫ID")
                run_script(f'{command_base} list-chapter "{comic_id}"', cwd=ACQUISITION_PATH)
        elif choice in ['5', '6', '7']:
            comic_id = get_input("请输入漫畫ID")
            output_dir = get_input("请输入下载目录", default=default_dir)
            if choice == '5':
                chapters = get_input("请输入一个或多个章節ID (用空格分隔)")
                run_script(f'{command_base} dl -o "{output_dir}" "{comic_id}" {chapters}', cwd=ACQUISITION_PATH)
            elif choice == '6':
                run_script(f'{command_base} dl-all -o "{output_dir}" "{comic_id}"', cwd=ACQUISITION_PATH)
            elif choice == '7':
                seq = get_input("请输入章节序号 (例如: 1-5 或 3,5,r1)")
                run_script(f'{command_base} dl-seq -o "{output_dir}" "{comic_id}" "{seq}"', cwd=ACQUISITION_PATH)
        elif choice == '9':
            show_usage(ACQUISITION_PATH)
        elif choice == '0':
            break
        else:
            print("无效输入，请重试。")

# ▼▼▼ 函数已修改 ▼▼▼
def menu_comic_processing():
    """模块二: 漫画处理"""
    while True:
        print_header("2. 漫画处理 (生成PDF)")
        print("1. [推荐] 完整处理流程 (v2 智能版: 合并->分割->打包->PDF)")
        print("2. [旧版] 完整处理流程 (v1 兼容版: 合并->分割->PDF)")
        print("3. [新增] 直接将图片文件夹转为PDF (无合并步骤)")
        print("4. [工具] 仅合并图片到一个长图")
        print("\n9. 功能用法介绍")
        print("0. 返回主菜单")
        choice = get_input("请输入选项")
        
        if choice == '1':
            script_path = os.path.join(COMIC_PROCESSING_PATH, "image_processes_pipeline_v2.py")
            run_script(f'python "{script_path}"')
        elif choice == '2':
            script_path = os.path.join(COMIC_PROCESSING_PATH, "image_processes_pipeline_v1.py")
            run_script(f'python "{script_path}"')
        elif choice == '3':
            script_path = os.path.join(COMIC_PROCESSING_PATH, "convert_to_pdf.py")
            run_script(f'python "{script_path}"')
        elif choice == '4':
            script_path = os.path.join(COMIC_PROCESSING_PATH, "merge_long_image.py")
            run_script(f'python "{script_path}"')
        elif choice == '9':
            show_usage(COMIC_PROCESSING_PATH)
        elif choice == '0':
            break
        else:
            print("无效输入，请重试。")
# ▲▲▲ 函数修改结束 ▲▲▲

def menu_ebook_workshop():
    """模块三: 电子书工坊"""
    while True:
        print_header("3. 电子书工坊")
        print("1. 从 TXT 创建 EPUB")
        print("2. 分割 EPUB 文件")
        print("3. 批量替换 EPUB/TXT 内容")
        print("4. 批量统一 EPUB 样式")
        print("5. 从 Markdown 创建 HTML")
        print("\n9. 功能用法介绍")
        print("0. 返回主菜单")
        choice = get_input("请输入选项")

        if choice == '1':
            script_path = os.path.join(EBOOK_WORKSHOP_PATH, "txt_to_epub_convertor.py")
            run_script(f'python "{script_path}"')
        elif choice == '2':
            script_path = os.path.join(EBOOK_WORKSHOP_PATH, "split_epub.py")
            run_script(f'python "{script_path}"')
        elif choice == '3':
            print_header("批量替换 EPUB/TXT 内容")
            print("\n💡 准备工作提示:")
            print(f"   1. 在 shared_assets 文件夹中可以找到 'rules.txt' 模板文件。")
            print("   2. 将其【复制】到您将要处理的电子书所在的目录。")
            print("   3. 根据您的需求，修改该目录下的 'rules.txt' 文件。")
            print("\n   脚本运行时，会自动寻找并使用与电子书在同一目录下的 'rules.txt'。")
            input("\n   准备好后，按回车键继续以运行脚本...")

            script_path = os.path.join(EBOOK_WORKSHOP_PATH, "batch_replacer.py")
            run_script(f'python "{script_path}"')
        elif choice == '4':
            script_path = os.path.join(EBOOK_WORKSHOP_PATH, "epub_styler.py")
            run_script(f'python "{script_path}"')
        elif choice == '5':
            script_path = os.path.join(EBOOK_WORKSHOP_PATH, "convert_md_to_html.py")
            target_dir = get_input("请输入包含 Markdown 文件的目录路径", default=global_settings.get('default_work_dir'))
            if os.path.isdir(target_dir):
                run_script(f'python "{script_path}" "{target_dir}"')
            else:
                print(f"❌ 错误: 目录 '{target_dir}' 不存在。")
                input("按回车键返回...")
        elif choice == '9':
            show_usage(EBOOK_WORKSHOP_PATH)
        elif choice == '0':
            break
        else:
            print("无效输入，请重试。")

def menu_file_repair():
    """模块四: 文件修复"""
    while True:
        print_header("4. 文件修复与格式化")
        print("1. EPUB 综合修复")
        print("2. EPUB 封面修复")
        print("3. TXT 编码修复")
        print("4. TXT 段落修复")
        print("\n9. 功能用法介绍")
        print("0. 返回主菜单")
        choice = get_input("请输入选项")

        if choice == '1':
            script_path = os.path.join(FILE_REPAIR_PATH, "epub_reformat_and_convert_v2.py")
            run_script(f'python "{script_path}"')
        elif choice == '2':
            script_path = os.path.join(FILE_REPAIR_PATH, "cover_repair.py")
            run_script(f'python "{script_path}"')
        elif choice == '3':
            script_path = os.path.join(FILE_REPAIR_PATH, "fix_txt_encoding.py")
            run_script(f'python "{script_path}"')
        elif choice == '4':
            script_path = os.path.join(FILE_REPAIR_PATH, "txt_reformat_chapter_safe.py")
            run_script(f'python "{script_path}"')
        elif choice == '9':
            show_usage(FILE_REPAIR_PATH)
        elif choice == '0':
            break
        else:
            print("无效输入，请重试。")

def menu_library_organization():
    """模块五: 文件库管理"""
    while True:
        print_header("5. 文件库管理")
        print("1. 智能整理与翻译文件夹")
        print("2. 归档已处理文件夹")
        print("3. (工具) 批量转换文件名 (繁->简)")
        print("4. (工具) 从 EPUB 提取 CSS")
        print("\n9. 功能用法介绍")
        print("0. 返回主菜单")
        choice = get_input("请输入选项")

        if choice == '1':
            ai_config = manage_ai_config()
            if ai_config:
                run_translation_with_config(ai_config)
        elif choice == '2':
            print_header("归档已处理文件夹")
            print("此功能将递归扫描一个源目录，并将所有匹配的文件夹移动到目标目录。")
            default_dir = global_settings.get('default_work_dir')
            source_dir = get_input("请输入要扫描的【源目录】路径", default=default_dir)
            if not os.path.isdir(source_dir):
                print(f"❌ 错误: 源目录 '{source_dir}' 不存在。")
                input("\n按回车键返回...")
                continue
            
            target_dir = get_input("请输入要移动到的【目标目录】路径", default=default_dir)
            suffix = get_input("请输入要查找的文件夹名称/后缀", default="merged_pdfs")
            
            archive_folders_dynamically(source_dir, target_dir, suffix)

        elif choice == '3':
            script_path = os.path.join(LIBRARY_ORGANIZATION_PATH, "convert_tc_to_sc.py")
            target_dir = get_input("请输入要批量重命名文件名的根目录", default=global_settings.get('default_work_dir'))
            if os.path.isdir(target_dir):
                run_script(f'python "{script_path}"', cwd=target_dir)
            else:
                print(f"❌ 错误: 目录 '{target_dir}' 不存在。")
                input("按回车键返回...")
        elif choice == '4':
            script_path = os.path.join(LIBRARY_ORGANIZATION_PATH, "extract_epub_css.py")
            run_script(f'python "{script_path}"')
        elif choice == '9':
            show_usage(LIBRARY_ORGANIZATION_PATH)
        elif choice == '0':
            break
        else:
            print("无效输入，请重试。")

def menu_utilities():
    """模块六: 辅助工具"""
    while True:
        print_header("6. 辅助工具")
        print("1. 批量打开网页")
        print("\n9. 功能用法介绍")
        print("0. 返回主菜单")
        choice = get_input("请输入选项")

        if choice == '1':
            script_path = os.path.join(UTILITIES_PATH, "open_bomtoon.py")
            run_script(f'python "{script_path}"')
        elif choice == '9':
            show_usage(UTILITIES_PATH)
        elif choice == '0':
            break
        else:
            print("无效输入，请重试。")


# --- 主循环 ---
def main():
    """主函数，显示主菜单并处理用户选择。"""
    # 【已修改】启动时加载并确认/配置默认工作目录
    load_settings()
    print_header("欢迎使用 ContentForge")
    
    current_path = global_settings.get('default_work_dir')
    
    if current_path:
        print(f"检测到已保存的默认工作目录: {current_path}")
        new_path_input = input("按回车键直接使用，或输入新路径进行更改: ").strip()
        
        if new_path_input: # 如果用户输入了新路径
            while not os.path.isdir(new_path_input):
                print(f"❌ 错误: 路径 '{new_path_input}' 不是一个有效的目录。")
                new_path_input = input("请重新输入有效路径: ").strip()
                if not new_path_input: # 如果用户放弃输入，则跳出循环
                    break 
            
            if new_path_input: # 确保用户没有放弃输入
                global_settings['default_work_dir'] = new_path_input
                save_settings()
                print(f"✅ 本次及后续运行的默认目录已更新为: {new_path_input}")
                input("按回车键继续...")
    else: # 如果没有设置文件或文件中没有路径
        configure_default_path(first_time=True)
    
    # 重新加载设置以确保在本次会话中生效
    load_settings()

    menu_map = {
        "1": ("内容获取 (Bomtoon 下载)", menu_acquisition),
        "2": ("漫画处理 (生成PDF)", menu_comic_processing),
        "3": ("电子书工坊 (创建/编辑EPUB)", menu_ebook_workshop),
        "4": ("文件修复与格式化", menu_file_repair),
        "5": ("文件库管理", menu_library_organization),
        "6": ("辅助工具", menu_utilities),
        "7": ("全局设置", menu_settings),
        "8": ("一键安装/更新所有依赖", menu_install_dependencies),
        "0": ("退出程序", sys.exit),
    }

    while True:
        print_header("ContentForge - 主菜单")
        print(f"当前默认工作目录: {global_settings.get('default_work_dir', '未设置')}")
        print("-" * 60)

        for key, (desc, _) in menu_map.items():
            print(f"{key.rstrip('.')} . {desc}")
        print("-" * 60)
        
        choice = get_input("请选择要使用的功能模块编号")

        selected = menu_map.get(choice) or menu_map.get(choice + '.')
        
        if selected:
            _, menu_func = selected
            if menu_func:
                menu_func()
        else:
            print("无效的选项，请输入菜单中的编号。")
            input("按回车键重试...")

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        print("\n感谢使用 ContentForge，再见！")
    except KeyboardInterrupt:
        print("\n\n操作被用户中断。感谢使用 ContentForge，再见！")
        sys.exit(0)