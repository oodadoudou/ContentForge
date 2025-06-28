import webbrowser
import os

def open_urls_in_chrome(start_num, end_num):
    """
    在 Chrome 浏览器中打开指定数字范围的网页。

    参数:
    start_num (int): 起始数字
    end_num (int): 结束数字
    """
    base_url = "https://www.bomtoon.tw/viewer/PAYBACK/"
    chrome_path = '' # 初始化 chrome_path

    # 尝试查找 Chrome 的路径 (针对不同操作系统)
    # Windows
    if os.name == 'nt':
        # 常见的 Chrome 安装路径
        possible_paths = [
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe")
        ]
        for path in possible_paths:
            if os.path.exists(path):
                chrome_path = path
                break
    # macOS
    elif os.name == 'posix': # macOS 也属于 posix
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(mac_path):
            # 对于 macOS，通常直接使用 'open -a "Google Chrome" %s' 或者注册浏览器
            # 更简单的方式是直接让 webbrowser 模块尝试找到默认的浏览器或已注册的 Chrome
            # 如果需要强制指定 Chrome，可以取消下面这行注释并确保路径正确
            # chrome_path = mac_path # 这种方式不直接用于 webbrowser.register
            pass # 在 macOS 上，webbrowser 通常能自动处理或通过名称找到
    # Linux
    elif 'linux' in os.name.lower():
        # 常见的 Linux Chrome/Chromium 路径
        possible_paths = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                chrome_path = path
                break

    try:
        # 注册 Chrome 浏览器 (如果找到了特定路径)
        # 对于 macOS，通常不需要显式注册路径，webbrowser.get('chrome') 或 webbrowser.get('google-chrome') 可能有效
        # 如果 chrome_path 非空且不是 macOS 的特定应用包路径（macOS 通常通过名称处理）
        if chrome_path and os.name != 'posix': # 在 Windows/Linux 上使用路径
             webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
        elif os.name == 'posix': # macOS 特殊处理
            # 可以尝试 'google-chrome' 或 'chrome'，如果不行，用户可能需要手动设置默认浏览器
            # 或者使用 os.system(f'open -a "Google Chrome" "{url}"')
            pass

        browser = None
        try:
            if os.name == 'posix' and os.path.exists("/Applications/Google Chrome.app"):
                 # 在 macOS 上，尝试使用 'google-chrome' 或 'chrome' 名称
                 # 或者直接用 open 命令 (更可靠)
                browser_controller_name = 'google-chrome' # 或者 'chrome'
                try:
                    browser = webbrowser.get(browser_controller_name)
                except webbrowser.Error:
                    print(f"无法通过名称 '{browser_controller_name}' 获取 Chrome 浏览器控制器。")
                    print("请确保 Chrome 已安装或尝试其他方法。")
                    # 对于 macOS，使用 'open' 命令通常更可靠
                    print("将尝试使用 'open -a' 命令 (仅限 macOS)。")

            elif chrome_path : # Windows/Linux
                browser = webbrowser.get('chrome')
            else: # 如果未找到特定路径，尝试使用默认浏览器或系统已知的 Chrome
                print("未能自动定位 Chrome 浏览器路径。尝试使用系统默认或已注册的 Chrome。")
                try:
                    browser = webbrowser.get('chrome') # 尝试获取已注册的 'chrome'
                except webbrowser.Error:
                    try:
                        browser = webbrowser.get('google-chrome') # 尝试 'google-chrome'
                    except webbrowser.Error:
                         print("无法获取 Chrome 浏览器。将使用默认浏览器打开。")
                         browser = webbrowser.get() # 获取默认浏览器

        except webbrowser.Error as e:
            print(f"发生错误: {e}")
            print("无法获取指定的浏览器。请确保 Chrome 已正确安装并添加到系统路径中，或者它是您的默认浏览器。")
            print("将尝试使用默认浏览器打开。")
            browser = webbrowser.get() # 获取默认浏览器实例

        if not browser and os.name == 'posix' and not os.path.exists("/Applications/Google Chrome.app"):
            print("在 macOS 上未找到 Chrome 应用。请安装 Chrome。")
            return
        elif not browser and not chrome_path and os.name != 'posix':
            print("未找到 Chrome 浏览器路径，也无法通过名称获取。请检查安装。")
            return


        print(f"准备打开从 {start_num} 到 {end_num} 的网页...")
        for i in range(start_num, end_num + 1):
            url_to_open = f"{base_url}{i}"
            print(f"正在打开: {url_to_open}")
            if os.name == 'posix' and os.path.exists("/Applications/Google Chrome.app") and not (browser and hasattr(browser, 'open_new_tab')):
                # macOS 的后备方案，如果 webbrowser.get() 失败或返回的对象不理想
                os.system(f'open -a "Google Chrome" "{url_to_open}"')
            elif browser:
                browser.open_new_tab(url_to_open)
            else: # 最后的后备，如果 browser 对象仍然是 None
                print(f"无法使用特定浏览器对象打开，尝试 webbrowser.open_new_tab (可能使用默认浏览器): {url_to_open}")
                webbrowser.open_new_tab(url_to_open)


    except Exception as e:
        print(f"执行过程中发生错误: {e}")
        print("请检查您的 Chrome 安装路径或尝试将 Chrome 设置为默认浏览器。")

if __name__ == "__main__":
    while True:
        try:
            start_input = input("请输入起始数字 (例如 27): ")
            start_page = int(start_input)
            break
        except ValueError:
            print("输入无效，请输入一个整数。")

    while True:
        try:
            end_input = input(f"请输入结束数字 (例如 42，需大于等于 {start_page}): ")
            end_page = int(end_input)
            if end_page >= start_page:
                break
            else:
                print(f"结束数字必须大于或等于起始数字 ({start_page})。")
        except ValueError:
            print("输入无效，请输入一个整数。")

    open_urls_in_chrome(start_page, end_page)
    print("所有指定网页已尝试打开。")