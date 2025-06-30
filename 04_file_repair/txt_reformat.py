import os
import re
import sys

def fix_novel_text_file(input_path, output_path):
    """
    讀取一個 txt 檔案，並將其格式化為每一行文本後都跟隨一個空行的格式。
    - 解決成對符號（如引號）被斷開的問題。
    - 簡化操作，僅在每行內容後增加空行。
    """
    try:
        print(f"正在讀取檔案: {os.path.basename(input_path)} ...")
        
        # 嘗試使用 UTF-8 編碼打開，如果失敗則回退到 GBK
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(input_path, 'r', encoding='gbk') as f:
                lines = f.readlines()

        processed_lines = []
        for line in lines:
            # 去除每行前後的空白字符（包括換行符），然後檢查該行是否有實際內容
            stripped_line = line.strip()
            if stripped_line:
                # 如果不是空行，就在該行內容後添加一個空行（即兩個換行符）
                processed_lines.append(stripped_line + '\n\n')
        
        # 將處理後的行列表合併成單一字串
        final_text = "".join(processed_lines)

        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # 使用 rstrip() 移除最後可能多餘的空行，使文件結尾更整潔
            f.write(final_text.rstrip())
            
        print(f"處理完成，已保存到: {os.path.basename(output_path)}")

    except FileNotFoundError:
        print(f"錯誤: 檔案未找到 - {input_path}", file=sys.stderr)
    except Exception as e:
        print(f"處理檔案 {input_path} 時發生錯誤: {e}", file=sys.stderr)


def main():
    """
    主函數，獲取使用者輸入並處理單一檔案或整個目錄。
    """
    # 設定預設路徑
    default_path = "/Users/doudouda/Downloads/2/"
    user_path = input(f"請輸入要處理的 txt 文件或目錄路徑 (直接回車將使用預設路徑: {default_path}): ").strip()
    
    if not user_path:
        user_path = default_path
        print(f"未輸入路徑，將使用預設路徑: {user_path}")

    # 檢查路徑是否存在
    if not os.path.exists(user_path):
        print(f"錯誤: 路徑 '{user_path}' 不存在。", file=sys.stderr)
        return

    # 情況一: 路徑是一個目錄
    if os.path.isdir(user_path):
        input_dir = user_path
        output_dir = os.path.join(input_dir, "processed_files")
        print(f"已識別為目錄，將處理其中的所有 .txt 檔案。")
        print(f"輸出目錄設定為: '{output_dir}'")
        
        file_count = 0
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(".txt"):
                file_count += 1
                input_filepath = os.path.join(input_dir, filename)
                output_filename = os.path.splitext(filename)[0] + '_reformatted.txt'
                output_filepath = os.path.join(output_dir, output_filename)
                fix_novel_text_file(input_filepath, output_filepath)
        
        if file_count == 0:
            print(f"在目錄 '{input_dir}' 中沒有找到任何 .txt 檔案。")
        else:
            print(f"\n所有 {file_count} 個 .txt 檔案處理完畢！")

    # 情況二: 路徑是一個檔案
    elif os.path.isfile(user_path):
        if user_path.lower().endswith(".txt"):
            input_filepath = user_path
            base_dir = os.path.dirname(input_filepath)
            output_dir = os.path.join(base_dir, "processed_files")
            
            print(f"已識別為單一檔案，準備處理。")
            print(f"輸出目錄設定為: '{output_dir}'")

            output_filename = os.path.splitext(os.path.basename(input_filepath))[0] + '_reformatted.txt'
            output_filepath = os.path.join(output_dir, output_filename)
            fix_novel_text_file(input_filepath, output_filepath)
            print("\n檔案處理完畢！")
        else:
            print(f"錯誤: '{user_path}' 是一個檔案，但不是 .txt 檔案。", file=sys.stderr)
            
    else:
        print(f"錯誤: '{user_path}' 不是一個有效的檔案或目錄。", file=sys.stderr)


if __name__ == "__main__":
    main()