import os
import sys
import zipfile
import tempfile
import re
from xml.etree import ElementTree as ET

# 导入 OpenCC 模块，如果失败则提供清晰的安装指引
try:
    from opencc import OpenCC
    # 导入模块本身以获取其路径
    import opencc as opencc_module
except ImportError:
    print("错误: 无法导入 OpenCC。请先安装库: pip install opencc-python-reimplemented", file=sys.stderr)
    sys.exit(1)

def check_epub_needs_processing(epub_path, cc):
    """
    检查 EPUB 文件是否需要处理。
    返回: (是否需要格式转换, 是否需要文字转换)
    """
    needs_layout_change = False
    needs_char_conversion = False
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                zf.extractall(temp_dir)
            
            opf_path = find_opf_file(temp_dir)
            if not opf_path:
                return False, False

            # 1. 检查是否需要格式转换 (竖排 -> 横排)
            tree = ET.parse(opf_path)
            root = tree.getroot()
            ns = {'opf': 'http://www.idpf.org/2007/opf'}
            spine = root.find('opf:spine', ns)
            if spine is not None and spine.get('page-progression-direction') == 'rtl':
                needs_layout_change = True
            
            # --- START: 优化后的繁简内容检测逻辑 ---
            # 参考 epub_convert_tc_to_sc.py 的 check_if_translation_needed 函数
            # 遍历内容文件进行抽样检查，比之前只检查第一个文件更可靠
            for root_dir, _, files in os.walk(temp_dir):
                content_files = [f for f in files if f.endswith(('.xhtml', '.html', '.opf'))]
                if not content_files:
                    continue
                
                # 遍历目录中所有可能包含繁体字的文件
                for filename in content_files:
                    sample_file_path = os.path.join(root_dir, filename)
                    sample_text = ""
                    try:
                        # 增加更安全的编码处理
                        with open(sample_file_path, 'r', encoding='utf-8') as f:
                            sample_text = f.read(2048) # 读取 2KB 样本
                    except UnicodeDecodeError:
                        try:
                            with open(sample_file_path, 'r', encoding='gbk', errors='ignore') as f:
                                sample_text = f.read(2048)
                        except Exception:
                            continue # 如果两种编码都读取失败，则跳过此文件
                    
                    if sample_text and sample_text != cc.convert(sample_text):
                        needs_char_conversion = True
                        break # 找到一个需要转换的文件就足够了
                
                if needs_char_conversion:
                    break # 已确认需要转换，无需再检查其他目录
            # --- END: 优化后的繁简内容检测逻辑 ---

    except Exception:
        # 如果文件解析失败，则当作不需要处理
        return False, False

    return needs_layout_change, needs_char_conversion


def find_opf_file(temp_dir):
    """在解压后的目录中查找 .opf 文件路径。"""
    for root, _, files in os.walk(temp_dir):
        for filename in files:
            if filename.endswith('.opf'):
                return os.path.join(root, filename)
    return None

def modify_opf_file(opf_path, cc, do_layout, do_chars):
    """修改 .opf 文件，根据需要转换格式和文字。"""
    if not do_layout and not do_chars:
        return
    try:
        ET.register_namespace('dc', "http://purl.org/dc/elements/1.1/")
        ET.register_namespace('opf', "http://www.idpf.org/2007/opf")
        tree = ET.parse(opf_path)
        root = tree.getroot()
        ns = {'opf': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}

        if do_layout:
            spine = root.find('opf:spine', ns)
            if spine is not None:
                spine.set('page-progression-direction', 'ltr')
                print("  - [格式] 页面翻页方向 -> 'ltr'.")

        # --- START: 优化后的元数据转换逻辑 ---
        # 参考 epub_convert_tc_to_sc.py 的做法，转换所有元数据而不仅是标题
        if do_chars:
            metadata = root.find('opf:metadata', ns)
            if metadata is not None:
                # 遍历元数据中的所有节点
                for elem in metadata.iter():
                    # 转换节点的文本内容
                    if elem.text and elem.text.strip():
                        elem.text = cc.convert(elem.text)
                    # 转换节点的尾部文本 (通常是同一行内的混合内容)
                    if elem.tail and elem.tail.strip():
                        elem.tail = cc.convert(elem.tail)
                print("  - [文字] 书籍元数据 -> 简体。")
        # --- END: 优化后的元数据转换逻辑 ---

        if sys.version_info >= (3, 9):
            ET.indent(tree)
        tree.write(opf_path, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print(f"  - [错误] 修改 OPF 文件时出错: {e}")

def modify_content_files(temp_dir, cc, do_layout, do_chars):
    """修改内容文件，根据需要转换格式和文字。"""
    for root_dir, _, files in os.walk(temp_dir):
        for filename in files:
            if not filename.endswith(('.xhtml', '.html', '.css', '.ncx')):
                continue

            file_path = os.path.join(root_dir, filename)
            try:
                # 增加更安全的编码处理
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                        content = f.read()
                        
                original_content = content
                
                if do_layout and filename.endswith('.css'):
                    content = content.replace('vertical-rl', 'horizontal-tb')
                    content = content.replace(".vrtl", ".hltr")
                    content = re.sub(r'local\("@(.*?)"\)', r'local("\1")', content)

                if filename.endswith(('.xhtml', '.html', '.ncx')):
                    if do_layout:
                         content = content.replace('class="vrtl"', 'class="hltr"')
                    if do_chars:
                        content = cc.convert(content)

                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"  - [修改] 已更新: {os.path.relpath(file_path, temp_dir)}")
            except Exception as e:
                print(f"  - [错误] 处理文件 {filename} 失败: {e}")

def repack_epub(temp_dir, new_epub_path):
    """将修改后的文件重新打包成 EPUB。"""
    try:
        mimetype_path = os.path.join(temp_dir, 'mimetype')
        with zipfile.ZipFile(new_epub_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 确保 mimetype 文件是第一个且未压缩
            zf.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            for root_dir, _, files in os.walk(temp_dir):
                for filename in files:
                    if filename != 'mimetype':
                        file_path = os.path.join(root_dir, filename)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arcname)
        print(f"  -> [成功] 新文件已保存至: {os.path.basename(os.path.dirname(new_epub_path))}{os.sep}{os.path.basename(new_epub_path)}")
    except Exception as e:
        print(f"  - [错误] 重新打包 EPUB 失败: {e}")

def process_epub_file(epub_path, output_dir, cc):
    """处理单个EPUB文件，包含检测和按需转换。"""
    print(f"\n[检查] {os.path.basename(epub_path)}")
    needs_layout, needs_chars = check_epub_needs_processing(epub_path, cc)

    if not needs_layout and not needs_chars:
        print("  - [跳过] 文件无需转换。")
        return

    print(f"  - [任务] 检测到需要进行: {'格式转换 ' if needs_layout else ''}{'文字转换' if needs_chars else ''}")
    
    base_name, _ = os.path.splitext(os.path.basename(epub_path))
    new_epub_path = os.path.join(output_dir, f"{base_name}.epub")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                zf.extractall(temp_dir)
            
            opf_path = find_opf_file(temp_dir)
            if not opf_path:
                print("  - [错误] 无法找到 .opf 配置文件！")
                return

            modify_opf_file(opf_path, cc, needs_layout, needs_chars)
            modify_content_files(temp_dir, cc, needs_layout, needs_chars)
            repack_epub(temp_dir, new_epub_path)

        except Exception as e:
            print(f"  - [严重错误] 处理EPUB时发生未知问题: {e}")
            
def process_txt_file(txt_path, output_dir, cc):
    """处理单个TXT文件，仅进行繁简转换。"""
    print(f"\n[处理TXT] {os.path.basename(txt_path)}")
    try:
        # 增加更安全的编码处理
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(txt_path, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read()
        
        converted_content = cc.convert(content)

        if content == converted_content:
            print("  - [跳过] TXT文件无需转换。")
            return
            
        new_txt_path = os.path.join(output_dir, os.path.basename(txt_path))
        with open(new_txt_path, 'w', encoding='utf-8') as f:
            f.write(converted_content)
        print(f"  -> [成功] 新文件已保存至: {os.path.basename(output_dir)}{os.sep}{os.path.basename(new_txt_path)}")

    except Exception as e:
        print(f"  - [错误] 处理TXT文件时出错: {e}")

def initialize_opencc():
    """初始化OpenCC转换器，包含健壮的后备方案。"""
    try:
        # 优先尝试标准初始化方法，传入不带 .json 的文件名
        return OpenCC('t2s')
    except Exception as e_simple:
        print("[警告] 标准 OpenCC 初始化失败，尝试使用后备方案...")
        try:
            # 后备方案：手动查找配置文件的绝对路径
            package_path = opencc_module.__path__[0]
            
            # 尝试在几个常见位置查找配置文件
            possible_paths = [
                os.path.join(package_path, 'data', 'config', 't2s.json'),
                os.path.join(package_path, 'config', 't2s.json'),
                os.path.join(package_path, 't2s.json')
            ]
            
            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
            
            if not config_path:
                 raise FileNotFoundError("在 OpenCC 包目录中找不到配置文件 (t2s.json)。")

            print(f"[信息] 成功找到配置文件路径: {config_path}")
            return OpenCC(config_path)
            
        except Exception as e_fallback:
            print("错误：无法初始化 OpenCC 转换器。", file=sys.stderr)
            print("标准模式和后备模式均已失败。这可能是因为库安装不完整或权限问题。", file=sys.stderr)
            print(f"\n- 标准模式错误: {e_simple}", file=sys.stderr)
            print(f"- 后备模式错误: {e_fallback}", file=sys.stderr)
            print("\n请尝试彻底卸载并重新安装库: pip uninstall opencc-python-reimplemented -y && pip install opencc-python-reimplemented", file=sys.stderr)
            sys.exit(1)

def main():
    """脚本主入口。"""
    cc = initialize_opencc()
    print("[信息] OpenCC 初始化成功。")

    default_path = "/Users/doudouda/Downloads/2/"
    prompt_message = f"请输入目标根目录 (直接按回车将使用: {default_path}): "
    target_directory = input(prompt_message).strip() or default_path

    if not os.path.isdir(target_directory):
        print(f"错误: 目录 '{target_directory}' 不存在或无效。", file=sys.stderr)
        sys.exit(1)
        
    # 创建统一的输出文件夹
    output_dir = os.path.join(target_directory, "processed_files")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[*] 开始扫描目录: {os.path.abspath(target_directory)}")
    print(f"[*] 所有处理后的文件将被保存到: {output_dir}")
    
    for root, _, files in os.walk(target_directory):
        # 避免扫描输出目录本身
        if os.path.abspath(root).startswith(os.path.abspath(output_dir)):
            continue

        for filename in files:
            file_path = os.path.join(root, filename)
            if filename.endswith('.epub'):
                process_epub_file(file_path, output_dir, cc)
            elif filename.endswith('.txt'):
                process_txt_file(file_path, output_dir, cc)
    
    print("\n[*] 所有操作完成。")

if __name__ == "__main__":
    main()