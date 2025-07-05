#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import json
import time
import zipfile
import threading
import itertools
import subprocess

# --- Global availability check for native command-line tools ---
NATIVE_7Z_PATH = shutil.which('7z')
NATIVE_ZIP_PATH = shutil.which('zip')
NATIVE_UNZIP_PATH = shutil.which('unzip')

try:
    import py7zr
    PYTHON_LIBS_AVAILABLE = True
except ImportError:
    PYTHON_LIBS_AVAILABLE = False


def run_native_command_with_spinner(command, msg):
    """Runs a native command-line process and shows a spinner."""
    spinner = itertools.cycle(['-', '\\', '|', '/'])
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    sys.stdout.write(f"  -> {msg}...  ")
    sys.stdout.flush()

    while process.poll() is None:
        sys.stdout.write(next(spinner))
        sys.stdout.flush()
        time.sleep(0.1)
        sys.stdout.write('\b')
    
    stderr = process.communicate()[1]
    if process.returncode != 0:
        sys.stdout.write("❌ 失败\n")
        if isinstance(stderr, bytes):
            try:
                stderr = stderr.decode(sys.getdefaultencoding(), errors='ignore')
            except Exception:
                stderr = str(stderr)
        sys.stderr.write(f"     错误详情: {stderr.strip()}\n")
        return False
    else:
        sys.stdout.write("✓ 完成\n")
        return True

def run_python_func_with_spinner(target_func, msg):
    """Runs a Python function in a separate thread and shows a spinner."""
    exception_container = []
    
    def target_wrapper():
        try:
            target_func()
        except Exception as e:
            exception_container.append(e)

    thread = threading.Thread(target=target_wrapper)
    thread.start()
    
    spinner = itertools.cycle(['-', '\\', '|', '/'])
    sys.stdout.write(f"  -> {msg}...  ")
    sys.stdout.flush()
    
    while thread.is_alive():
        sys.stdout.write(next(spinner))
        sys.stdout.flush()
        time.sleep(0.1)
        sys.stdout.write('\b')
    
    thread.join()

    if exception_container:
        sys.stdout.write("❌ 失败\n")
        sys.stderr.write(f"     错误详情: {exception_container[0]}\n")
        return False
    else:
        sys.stdout.write("✓ 完成\n")
        return True

def load_default_path_from_settings():
    """从共享设置文件中读取默认工作目录。"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir and os.path.isdir(default_dir) else "."
        else:
             return os.path.join(os.path.expanduser("~"), "Downloads")
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")

def _pack_directory(full_dir_path, parent_dir):
    """对单个目录执行打包流程，优先使用原生命令。"""
    dir_name = os.path.basename(full_dir_path)
    temp_7z_path = os.path.join(parent_dir, f"{dir_name}.7z")
    renamed_7z_path = os.path.join(parent_dir, f"{dir_name}.7删z")
    final_zip_path = os.path.join(parent_dir, f"{dir_name}.z删ip")

    try:
        if NATIVE_7Z_PATH and NATIVE_ZIP_PATH:
            cmd_7z = [NATIVE_7Z_PATH, 'a', '-p1111', temp_7z_path, full_dir_path]
            if not run_native_command_with_spinner(cmd_7z, "步骤A: 7z 加密压缩"): return False
            
            print(f"  -> 步骤B: 重命名为 .7删z...", end=''); shutil.move(temp_7z_path, renamed_7z_path); print(" ✓ 完成")

            original_cwd = os.getcwd()
            os.chdir(parent_dir)
            cmd_zip = [NATIVE_ZIP_PATH, '-q', '-j', os.path.basename(final_zip_path), os.path.basename(renamed_7z_path)]
            if not run_native_command_with_spinner(cmd_zip, "步骤C: ZIP 二次压缩"):
                os.chdir(original_cwd); return False
            os.chdir(original_cwd)
        else:
            def create_7z():
                with py7zr.SevenZipFile(temp_7z_path, 'w', password='1111') as archive:
                    archive.writeall(full_dir_path, arcname=dir_name)
            if not run_python_func_with_spinner(create_7z, "步骤A: 7z 加密压缩"): return False

            print(f"  -> 步骤B: 重命名为 .7删z...", end=''); shutil.move(temp_7z_path, renamed_7z_path); print(" ✓ 完成")

            print("  -> 步骤C: ZIP 二次压缩...", end='')
            with zipfile.ZipFile(final_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(renamed_7z_path, arcname=os.path.basename(renamed_7z_path))
            print(" ✓ 完成")

    except Exception as e:
        print(f" ❌ 处理失败\n错误: {e}")
        if os.path.exists(temp_7z_path): os.remove(temp_7z_path)
        if os.path.exists(renamed_7z_path): os.remove(renamed_7z_path)
        return False
    finally:
        if os.path.exists(renamed_7z_path):
            print(f"  -> 步骤D: 清理临时文件...", end=''); os.remove(renamed_7z_path); print(" ✓ 完成")
            
    return True

def encode_items_in_dir(parent_dir):
    """加密打包模式，保留源文件。"""
    print("\n--- 执行模式：加密打包 (文件/文件夹 -> .z删ip) ---")
    items_to_process = [item for item in os.listdir(parent_dir) if not item.endswith(('.z删ip', '.zip', '.7z')) and not item.startswith('.')]
    if not items_to_process: sys.exit(f"在 '{parent_dir}' 中未找到任何可处理的文件或文件夹。")
    
    total_items = len(items_to_process)
    print(f"\n找到 {total_items} 个待处理项目。")
    
    for i, item_name in enumerate(sorted(items_to_process)):
        item_path = os.path.join(parent_dir, item_name)
        dir_to_pack, temp_folder_path = None, None
        
        print(f"\n--- 正在处理: {item_name} ({i+1}/{total_items}) ---")

        if os.path.isdir(item_path):
            dir_to_pack = item_path
        elif os.path.isfile(item_path):
            folder_name = os.path.splitext(item_name)[0]
            new_folder_path = os.path.join(parent_dir, f"{folder_name}_pack_temp_{int(time.time())}")
            if os.path.exists(new_folder_path):
                print(f"  [!] 警告: 临时文件夹 '{new_folder_path}' 已存在，跳过。"); continue
            try:
                print(f"  -> 预处理: 创建临时文件夹...", end=''); os.makedirs(new_folder_path); print(" ✓ 完成")
                print(f"  -> 预处理: 复制文件入内...", end=''); shutil.copy(item_path, new_folder_path); print(" ✓ 完成")
                dir_to_pack, temp_folder_path = new_folder_path, new_folder_path
            except Exception as e:
                print(f" ❌ 失败\n错误: 文件预处理失败: {e}", file=sys.stderr)
                if os.path.exists(new_folder_path): shutil.rmtree(new_folder_path)
                continue
        
        if dir_to_pack:
            _pack_directory(dir_to_pack, parent_dir)
            if temp_folder_path:
                print(f"  -> 清理临时文件夹...", end=''); shutil.rmtree(temp_folder_path); print(" ✓ 完成")
    print("\n--- 所有加密打包任务已完成 ---")

def decode_files_in_dir(parent_dir):
    """解密恢复模式，优先使用原生命令。"""
    print("\n--- 执行模式：解密恢复 (.z删ip -> 文件夹) ---")
    target_files = [f for f in os.listdir(parent_dir) if '删' in f and f.endswith('.z删ip')]
    if not target_files: sys.exit(f"在 '{parent_dir}' 中未找到任何包含 '删' 的待处理文件。")

    total_files = len(target_files)
    print(f"\n找到 {total_files} 个待处理的文件。")
    
    for i, filename in enumerate(sorted(target_files)):
        print(f"\n--- 正在处理: {filename} ({i+1}/{total_files}) ---")
        full_file_path = os.path.join(parent_dir, filename)
        inner_7z_path, temp_zip_path = "", ""
        
        try:
            if NATIVE_UNZIP_PATH and NATIVE_7Z_PATH:
                temp_zip_path = os.path.join(parent_dir, filename.replace('.z删ip', '.zip'))
                shutil.copy(full_file_path, temp_zip_path)
                
                cmd_unzip = [NATIVE_UNZIP_PATH, '-o', temp_zip_path, '-d', parent_dir]
                if not run_native_command_with_spinner(cmd_unzip, "步骤1: 正在解压 ZIP"): continue

                inner_7z_renamed_path = os.path.join(parent_dir, filename.replace('z删ip', '7删z'))
                inner_7z_path = inner_7z_renamed_path.replace('.7删z', '.7z')
                shutil.move(inner_7z_renamed_path, inner_7z_path)

                target_dir_name = os.path.splitext(os.path.basename(inner_7z_path))[0]
                cmd_7z_extract = [NATIVE_7Z_PATH, 'x', f'-p1111', f'-o{os.path.join(parent_dir, target_dir_name)}', '-y', inner_7z_path]
                if not run_native_command_with_spinner(cmd_7z_extract, "步骤2: 正在解压7Z"): continue
            else:
                print(f"  -> 步骤1: 正在解压 ZIP...", end='')
                with zipfile.ZipFile(full_file_path, 'r') as zf:
                    if not zf.namelist(): raise ValueError("ZIP文件为空")
                    inner_filename = zf.namelist()[0]
                    inner_7z_path = os.path.join(parent_dir, inner_filename)
                    zf.extract(inner_filename, parent_dir)
                print(" ✓ 完成")

                def extract_7z():
                    with py7zr.SevenZipFile(inner_7z_path, mode='r', password='1111') as z:
                        z.extractall(path=parent_dir)
                if not run_python_func_with_spinner(extract_7z, "步骤2: 正在解压7Z"): continue

            target_dir_name = os.path.splitext(os.path.basename(filename).replace(".z删ip", ""))[0]
            target_dir_path = os.path.join(parent_dir, target_dir_name)
            print(f"  -> 步骤3: 检查并修复目录结构...", end='')
            nested_dir_path = os.path.join(target_dir_path, target_dir_name)
            if os.path.isdir(nested_dir_path):
                print(" ✓ 检测到冗余，开始修复...")
                for item in os.listdir(nested_dir_path): shutil.move(os.path.join(nested_dir_path, item), target_dir_path)
                os.rmdir(nested_dir_path); print("     -> 修复完成。")
            else: print(" ✓ 结构正常。")

        except Exception as e:
            print(f" ❌ 处理失败\n错误: {e}")
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)
            if inner_7z_path and os.path.exists(inner_7z_path):
                print(f"  -> 步骤4: 清理临时文件...", end=''); os.remove(inner_7z_path); print(" ✓ 完成")

    print("\n--- 所有解密恢复任务已完成 ---")

def print_final_speedup_info(missing_commands):
    """在程序退出前，打印平台特定的性能提升建议。"""
    if not missing_commands:
        return

    print("\n\n=====================================================")
    print("            🚀 性能提升建议 🚀")
    print("-----------------------------------------------------")
    print("检测到您正在兼容模式下运行。为了获得最快的压缩/解压")
    print("速度，建议您安装以下缺失的原生命令行工具:")
    
    if sys.platform == "darwin":  # macOS
        print("\n[针对 macOS 系统]")
        if '7z' in missing_commands:
            print("  - 7z:  请在终端运行 `brew install p7zip`")
        if 'zip' in missing_commands or 'unzip' in missing_commands:
            print("  - zip/unzip: 请运行 `brew install zip`")
    
    elif sys.platform == "win32": # Windows
        print("\n[针对 Windows 系统]")
        if '7z' in missing_commands:
            print("  - 7z:  请从官网 https://www.7-zip.org 下载并安装")
        if 'zip' in missing_commands or 'unzip' in missing_commands:
            print("  - zip/unzip: 可通过 winget 或 scoop 安装 (例如 `winget install 7zip.7zip`)")

    elif sys.platform.startswith("linux"): # Linux
        print("\n[针对 Linux 系统]")
        # Check for package manager
        if shutil.which('apt-get'):
            if '7z' in missing_commands:
                print("  - 7z:  请运行 `sudo apt-get install p7zip-full`")
            if 'zip' in missing_commands:
                print("  - zip: 请运行 `sudo apt-get install zip`")
            if 'unzip' in missing_commands:
                print("  - unzip: 请运行 `sudo apt-get install unzip`")
        elif shutil.which('yum'):
            if '7z' in missing_commands:
                print("  - 7z:  请运行 `sudo yum install p7zip p7zip-plugins`")
            if 'zip' in missing_commands or 'unzip' in missing_commands:
                print("  - zip/unzip: 请运行 `sudo yum install zip unzip`")
        else:
            print("  - 请使用您发行版的包管理器安装 'p7zip', 'zip', 'unzip'")
            
    print("\n安装后，下次运行本工具将自动切换到高速模式。")
    print("=====================================================")


def main():
    """主执行函数"""
    print("====================================================="); print("=          文件夹加密打包 & 解密恢复工具          ="); print("=====================================================")
    
    missing_commands = []
    use_native = NATIVE_7Z_PATH and NATIVE_ZIP_PATH and NATIVE_UNZIP_PATH
    
    if use_native:
        print("\n【模式】检测到原生 7z/zip 命令，将以高速模式运行。")
    else:
        print("\n【模式】未检测到部分或全部原生命令，将以纯Python兼容模式运行 (速度较慢)。")
        if not PYTHON_LIBS_AVAILABLE:
            print("\n错误: 纯Python模式所需的 'py7zr' 库也未安装。")
            print("请先通过 'pip install py7zr' 命令进行安装。")
            sys.exit(1)
        
        if not NATIVE_7Z_PATH: missing_commands.append('7z')
        if not NATIVE_ZIP_PATH: missing_commands.append('zip')
        if not NATIVE_UNZIP_PATH: missing_commands.append('unzip')

    try:
        print("\n 1. 加密打包 (文件/文件夹 -> .z删ip) [保留源文件]")
        print(" 2. 解密恢复 (.z删ip -> 文件夹)")
        print("----------"); print(" 0. 退出")
        mode = input("\n请选择操作模式: ").strip()
        if mode in ['1', '2']:
            default_path = load_default_path_from_settings()
            prompt_message = f"\n请输入工作目录路径 (回车使用默认: {default_path}): "
            parent_dir = input(prompt_message).strip() or default_path
            if not os.path.isdir(parent_dir): sys.exit(f"\n错误：目录 '{parent_dir}' 不存在。")
            if mode == '1': encode_items_in_dir(parent_dir)
            elif mode == '2': decode_files_in_dir(parent_dir)
        elif mode == '0':
            pass # Allow to proceed to finally block
        else:
            print("\n错误：无效的选择。")
    
    finally:
        print_final_speedup_info(missing_commands)
        sys.exit("操作完成，程序已退出。")


if __name__ == "__main__":
    main()