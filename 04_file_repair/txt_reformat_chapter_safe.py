
import os
import re
import sys

def fix_novel_text_file(input_path, output_path):
    """
    读取一个txt文件，修复因PDF转换导致的错误断句，并写入新文件。

    改进：避免将章节标题与正文连接在一起。
    """
    try:
        print(f"正在读取文件: {os.path.basename(input_path)} ...")
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                original_text = f.read()
        except UnicodeDecodeError:
            with open(input_path, 'r', encoding='gbk') as f:
                original_text = f.read()

        # 保留章节标题前后的换行
        chapter_pattern = re.compile(r'^\s*(第[一二三四五六七八九十百千\d]+[章节卷回篇]|[序终尾]章)\s*$', re.MULTILINE)
        marked_text = chapter_pattern.sub(r'§§\1§§', original_text)

        # 第一步：修复段落断开
        pass1_text = re.sub(r'([^\n。！？…”』’])\n{2,}', r'\1', marked_text)

        # 第二步：修复句子内部的单个错误换行，跳过章节行
        pattern_single_newline = re.compile(r'(?<![。！？…”』’])\n(?![\n\u3000\s‘“§])')
        processed_text = pattern_single_newline.sub('', pass1_text)

        # 恢复章节标题的换行格式
        final_text = processed_text.replace('§§', '\n')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_text)
            
        print(f"处理完成，已保存到: {os.path.basename(output_path)}")

    except FileNotFoundError:
        print(f"错误: 文件未找到 - {input_path}", file=sys.stderr)
    except Exception as e:
        print(f"处理文件 {input_path} 时发生错误: {e}", file=sys.stderr)


def main():
    default_dir = "E:\字句断开文件处理\断开文件"
    input_dir = input(f"请输入要处理的txt文件所在的根目录 (直接回车将使用默认目录: {default_dir}): ").strip()
    
    if not input_dir:
        input_dir = default_dir
        print(f"未输入目录，将使用默认目录: {input_dir}")

    if not os.path.isdir(input_dir):
        print(f"错误: 目录 '{input_dir}' 不存在或不是一个有效的目录。", file=sys.stderr)
        return

    output_dir = os.path.join(input_dir, "processed_txt")
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"输出目录 '{output_dir}' 已创建或已存在。")
    except OSError as e:
        print(f"错误: 创建输出目录 '{output_dir}' 失败: {e}", file=sys.stderr)
        return

    file_count = 0
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".txt"):
            file_count += 1
            input_filepath = os.path.join(input_dir, filename)
            output_filename = os.path.splitext(filename)[0] + '_fixed.txt'
            output_filepath = os.path.join(output_dir, output_filename)
            fix_novel_text_file(input_filepath, output_filepath)
    
    if file_count == 0:
        print(f"在目录 '{input_dir}' 中没有找到任何 .txt 文件。")
    else:
        print(f"\n所有 {file_count} 个 .txt 文件处理完毕！")


if __name__ == "__main__":
    main()
