import os
import sys

# 将项目根目录添加到Python搜索路径中，以便能导入共享工具
# This assumes the script is in a subdirectory of the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_utils import utils

def menu_ebook_workshop():
    """模块三: 电子书处理与生成的独立菜单"""
    module_path = '03_ebook_workshop'
    
    # 加载全局设置
    settings = utils.load_settings()
    
    while True:
        utils.print_header("3. 电子书处理与生成 (TXT/EPUB/HTML)")
        print("--- 创建与转换 ---")
        print(" 1. [创建] 从 TXT 创建带章节目录的 EPUB (⭐新增样式选择)")
        print("    └ 功能: 智能章节识别 + 5种精美样式 + 实时预览 + 自定义封面")
        print(" 2. [创建] 将 Markdown 文件夹批量转为 HTML")
        print(" 3. [转换] 从 EPUB 提取纯文本内容 (TXT)")
        
        print("\n--- 编辑与修复 EPUB ---")
        print(" 4. (元数据) 批量重命名 EPUB 文件")
        print("    └ 功能: 读取EPUB内部标题，让你手动修改或自动规整化文件名。")
        print(" 5. (内容) 仅将 EPUB 内文转为简体中文")
        print("    └ 功能: 只进行繁体到简体的文字转换，不改变排版。")
        print(" 6. (综合) 修复竖排版并转为简体中文 (推荐)")
        print("    └ 功能: 自动检测并修正竖排版和繁体内容，一步到位。")
        print(" 7. (清理) EPUB 清理工具 (封面/字体)")
        print("    └ 功能: 删除 EPUB 中的封面、字体文件和 CSS 字体声明，支持单独或组合操作。")
        
        print("\n--- 高级工具 ---")
        print(" 8. 根据规则批量替换 EPUB/TXT 内容")
        print(" 9. 用统一的 CSS 样式美化 EPUB")
        print(" 10. 按章节数量均等分割 EPUB 文件")
        print(" 11. 合并文件夹内所有 EPUB")
        print(" 12. [工具] EPUB 解包/封装工具")
        print("     └ 功能: 批量解压 EPUB 便于编辑，或从文件夹重新打包成 EPUB。")
        print(" 13. 标点符号补全工具 (TXT/EPUB)")
        print("     └ 功能: 智能补全中文文本中缺失的逗号，跳过非正文内容。")

        print("----------")
        print(" 88. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        if choice == '1':
            utils.run_script("txt_to_epub_convertor.py", cwd=module_path)
        elif choice == '2':
            utils.run_script("convert_md_to_html.py", cwd=module_path)
        elif choice == '3':
            utils.run_script("epub_to_txt_convertor.py", cwd=module_path)
        elif choice == '4':
            utils.run_script("epub_rename.py", cwd=module_path)
        elif choice == '5':
            utils.run_script("epub_convert_tc_to_sc.py", cwd=module_path)
        elif choice == '6':
            utils.run_script("epub_reformat_and_convert_v2.py", cwd=module_path)
        elif choice == '7':
            utils.run_script("epub_cleaner.py", cwd=module_path)
        elif choice == '8':
            utils.run_script("batch_replacer.py", cwd=module_path)
        elif choice == '9':
            utils.run_script("epub_styler.py", cwd=module_path)
        elif choice == '10':
            utils.run_script("split_epub.py", cwd=module_path)
        elif choice == '11':
            utils.run_script("epub_merge.py", cwd=module_path)
        elif choice == '12':
            utils.run_script("epub_toolkit.py", cwd=module_path)
        elif choice == '13':
            utils.run_script("punctuation_fixer.py", cwd=module_path)
        elif choice == '88':
            utils.show_usage(module_path)
        elif choice == '0':
            # 返回主菜单（在子脚本中即为退出）
            break

if __name__ == "__main__":
    try:
        menu_ebook_workshop()
    except KeyboardInterrupt:
        # 当用户在子菜单中按 Ctrl+C 时，优雅退出
        print("\n\n操作被用户中断。")
        sys.exit(0)