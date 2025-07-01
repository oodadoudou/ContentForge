import os
import sys

# 将项目根目录添加到Python搜索路径中，以便能导入共享工具
# This assumes the script is in a subdirectory of the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_utils import utils

def menu_acquisition():
    """模块一: 内容获取的独立菜单"""
    module_path = '01_acquisition'
    script_name = "bomtoontwext.py"
    
    # 加载全局设置，以便使用默认下载目录
    settings = utils.load_settings()
    
    while True:
        utils.print_header("1. 内容获取 (从网站下载漫画)")
        print("--- 准备工作 ---")
        print(" 1. 自动更新/生成登录凭证 (⭐推荐先执行此项)")
        print("\n--- 发现漫画 (获取漫畫ID) ---")
        print(" 2. 列出已购买的所有漫画")
        print(" 3. 按关键词搜索漫画")
        print("\n--- 下载漫画 ---")
        print(" 4. (手动)列出指定漫画的章节")
        print(" 5. 下载指定漫画的特定章节")
        print(" 6. 下载指定漫画的全部章节")
        print(" 7. 按序号范围下载章节 (如: 1-5, 8, 10)")
        print("----------")
        print(" 8. 查看本模块用法说明 (README)")
        print(" 0. 返回主菜单")
        choice = utils.get_input("请选择")

        base_command = f'{script_name}'
        default_dir = settings.get('default_work_dir', ".")

        if choice == '1':
            utils.run_script("update_token.py", cwd=module_path)
        elif choice == '2':
            utils.run_script(f"{base_command} list-comic", cwd=module_path)
        elif choice == '3':
            keyword = utils.get_input("请输入漫画关键词")
            if keyword:
                utils.run_script(f'{base_command} search "{keyword}"', cwd=module_path)
        elif choice == '4':
            comic_id = utils.get_input("请输入漫畫ID")
            if comic_id:
                utils.run_script(f'{base_command} list-chapter "{comic_id}"', cwd=module_path)
        
        # --- 修改后的下载流程 ---
        elif choice in ['5', '6', '7']:
            # 步骤 1: 自动列出所有已购买漫画，方便用户查找ID
            utils.print_header("步骤 1: 列出所有已购买的漫画")
            utils.run_script(f"{base_command} list-comic", cwd=module_path)
            comic_id = utils.get_input("\n? 请从上方列表复制并输入您想操作的【漫畫ID】")
            if not comic_id:
                print("未输入漫畫ID，操作已取消。")
                input("按回车键继续...")
                continue
            
            # 步骤 2: 获取保存目录
            output_dir = utils.get_input(f"\n? 请输入下载保存的目录", default=default_dir)
            if not os.path.isdir(output_dir):
                print(f"❌ 错误: 目录 '{output_dir}' 无效。")
                input("按回车键继续...")
                continue

            # 步骤 3: 根据不同选项执行不同操作
            if choice == '5': # 下载特定章节
                # 3a: 自动列出该漫画的所有章节
                utils.print_header(f"步骤 2: 列出漫画 '{comic_id}' 的所有章节")
                utils.run_script(f'{base_command} list-chapter "{comic_id}"', cwd=module_path)
                chapters = utils.get_input("\n? 请从上方列表复制一个或多个【章節ID】(用空格分隔)")
                if chapters:
                    utils.run_script(f'{base_command} dl -o "{output_dir}" "{comic_id}" {chapters}', cwd=module_path)

            elif choice == '6': # 下载全部章节
                print("\n即将开始下载该漫画的全部章节...")
                utils.run_script(f'{base_command} dl-all -o "{output_dir}" "{comic_id}"', cwd=module_path)

            elif choice == '7': # 按序号下载
                # 3a: 自动列出该漫画的所有章节和序号
                utils.print_header(f"步骤 2: 列出漫画 '{comic_id}' 的所有章节及其序号")
                utils.run_script(f'{base_command} list-chapter "{comic_id}"', cwd=module_path)
                seq = utils.get_input("\n? 请根据上方序号输入下载范围 (例如: 1-5 或 3,5,r1)")
                if seq:
                    utils.run_script(f'{base_command} dl-seq -o "{output_dir}" "{comic_id}" "{seq}"', cwd=module_path)
        
        elif choice == '8':
            utils.show_usage(module_path)
        elif choice == '0':
            break

if __name__ == "__main__":
    try:
        menu_acquisition()
    except KeyboardInterrupt:
        print("\n\n操作被用户中断。")
        sys.exit(0)