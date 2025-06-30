import unittest
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock

# 将项目根目录添加到 Python 的搜索路径中
# 以便测试脚本能正确地导入 main 和 shared_utils
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# 导入我们需要测试的目标模块
import main

class TestMainDispatcher(unittest.TestCase):

    @patch('main.utils.get_input')
    @patch('subprocess.run')
    def test_menu_navigation(self, mock_subprocess_run, mock_get_input):
        """
        测试主菜单的所有导航选项是否能正确调用对应的子模块入口脚本。
        """
        
        # 定义主菜单的选项、描述和它们应该调用的脚本路径
        menu_actions = {
            '1': ('内容获取 (从网站下载漫画)', '01_acquisition/01_start_up.py'),
            '2': ('漫画处理与生成 (图片转PDF)', '02_comic_processing/02_start_up.py'),
            '3': ('电子书处理与生成 (TXT/EPUB/HTML)', '03_ebook_workshop/03_start_up.py'),
            '4': ('文件修复与工具 (解决常见问题)', '04_file_repair/04_start_up.py'),
            '5': ('文件库管理 (整理、归档、重命名)', '05_library_organization/05_start_up.py'),
        }

        for choice, (description, expected_script) in menu_actions.items():
            # 为每次测试重置模拟对象
            mock_subprocess_run.reset_mock()
            
            # 模拟用户输入：只输入菜单选项，然后让测试因 StopIteration 停止
            mock_get_input.side_effect = [choice]

            print(f"\n--- 测试菜单选项 '{choice}': {description} ---")
            print(f"  [模拟] 用户输入: '{choice}'")
            
            # 使用一个模拟的 main_loop 来执行单次选择
            # 我们假设选择一个模块后程序会返回主菜单，这里通过捕获异常来模拟这个行为
            with self.assertRaises(StopIteration): # get_input 会在 side_effect 用尽后抛出此异常
                main.main()

            # 验证 subprocess.run 是否被正确调用
            print(f"  [验证] 是否尝试调用子进程 `subprocess.run`...")
            self.assertTrue(mock_subprocess_run.called, f"选项 '{choice}' 未触发任何脚本调用！")
            print(f"    - 调用成功。")
            
            # 获取调用时的参数
            call_args, _ = mock_subprocess_run.call_args
            
            # call_args[0] 是一个列表，例如 [sys.executable, 'path/to/script.py']
            called_script_path = call_args[0][1]
            
            # 构造期望的脚本绝对路径
            expected_abs_path = os.path.join(PROJECT_ROOT, expected_script)
            
            print(f"  [验证] 调用脚本是否为: {expected_script}")
            # 断言调用的脚本路径与期望的路径一致
            self.assertEqual(called_script_path, expected_abs_path, 
                             f"选项 '{choice}' 调用了错误的脚本！\n"
                             f"  期望: {expected_abs_path}\n"
                             f"  实际: {called_script_path}")
            print(f"    - 路径匹配成功。")
            
            print(f"  ✅ 测试通过！")
    
    @patch('main.menu_system_settings')
    @patch('main.utils.get_input')
    def test_settings_menu_call(self, mock_get_input, mock_settings_menu):
        """测试选择 '6' 是否能正确调用设置菜单函数。"""
        mock_get_input.side_effect = ['6']
        
        print(f"\n--- 测试菜单选项 '6': 系统设置与依赖 ---")
        print(f"  [模拟] 用户输入: '6'")

        with self.assertRaises(StopIteration):
            main.main()
            
        print(f"  [验证] 是否调用了函数 `main.menu_system_settings`...")
        self.assertTrue(mock_settings_menu.called, "选项 '6' 未能调用 menu_system_settings 函数！")
        print(f"    - 调用成功。")

        print("  ✅ 测试通过！")


# 这使得你可以直接从命令行运行此文件
if __name__ == '__main__':
    # 我们需要模拟 main 函数中的首次运行配置，使其不执行
    with patch('main.configure_default_path'):
        # 使用 verbosity=2 来获取 unittest 框架提供的详细输出
        unittest.main(verbosity=2)
