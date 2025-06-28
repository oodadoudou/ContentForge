import os
from zhconv import convert

def convert_filename(filename):
    """将文件名从繁体转为简体"""
    return convert(filename, 'zh-cn')  # 'zh-cn' 表示简体中文

def main():
    for root, dirs, files in os.walk(".", topdown=False):
        # 先处理文件
        for name in files:
            old_path = os.path.join(root, name)
            new_name = convert_filename(name)
            new_path = os.path.join(root, new_name)
            if old_path != new_path:
                os.rename(old_path, new_path)
                print(f"Renamed: {old_path} -> {new_path}")

        # 再处理文件夹（避免路径问题）
        for name in dirs:
            old_path = os.path.join(root, name)
            new_name = convert_filename(name)
            new_path = os.path.join(root, new_name)
            if old_path != new_path:
                os.rename(old_path, new_path)
                print(f"Renamed: {old_path} -> {new_path}")

if __name__ == "__main__":
    main()