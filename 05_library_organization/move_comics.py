import os
import shutil

def move_merged_folders_recursively(source_base_dir, target_dir):
    """
    递归扫描源目录及其所有子目录，将所有以 'merged_pdfs' 结尾的
    文件夹移动到目标目录。

    参数:
    source_base_dir (str): 要扫描的源目录路径。
    target_dir (str): 要将文件夹移动到的目标目录路径。
    """
    # 定义要查找的文件夹后缀
    suffix_to_find = 'merged_pdfs'

    # 步骤 1: 检查源目录是否存在
    if not os.path.isdir(source_base_dir):
        print(f"错误：源目录 '{source_base_dir}' 不存在或不是一个有效的目录。")
        return

    # 步骤 2: 确保目标目录存在
    os.makedirs(target_dir, exist_ok=True)
    print(f"开始递归扫描源目录: '{source_base_dir}'")
    print(f"所有匹配的文件夹将被移动到: '{target_dir}'\n")

    found_any = False
    
    # 步骤 3: 使用 os.walk 遍历所有子目录
    # os.walk 会生成三元组 (当前目录路径, [子目录列表], [文件列表])
    for dirpath, dirnames, filenames in os.walk(source_base_dir):
        
        # 我们只关心目录，所以遍历 dirnames 列表
        # 遍历列表的副本 (dirnames[:]) 以便安全地从原列表删除
        for dirname in dirnames[:]: 
            if dirname.endswith(suffix_to_find):
                found_any = True
                
                # 构建匹配文件夹的完整源路径
                full_source_path = os.path.join(dirpath, dirname)
                
                print(f"[*] 找到匹配文件夹: {full_source_path}")

                # 步骤 4: 执行移动操作
                try:
                    print(f"    -> 正在移动...")
                    # 直接将找到的文件夹移动到目标目录下
                    shutil.move(full_source_path, target_dir)
                    print(f"    -> 成功移动到 '{target_dir}'")
                    
                    # 从 dirnames 列表中移除已移动的目录
                    # 防止 os.walk 尝试进入一个已不存在的目录
                    dirnames.remove(dirname)
                    
                except Exception as e:
                    print(f"    -> 移动失败: {e}")
                print("-" * 30)

    if not found_any:
        print("\n扫描完成，在所有子目录中均未找到任何以 'merged_pdfs' 结尾的文件夹。")
    else:
        print("\n所有匹配的文件夹均已处理完毕。")


if __name__ == "__main__":
    # --- 请在这里配置您的路径 ---
    # 源目录: 脚本将从这里开始递归扫描
    source_directory = '/Users/doudouda/Downloads/Personal_doc/Comics/[OriginalPics]'
    
    # 目标目录: 所有找到的文件夹都会被移动到这里
    target_directory = '/Users/doudouda/Downloads/2/'
    
    # 执行主函数
    move_merged_folders_recursively(source_directory, target_directory)