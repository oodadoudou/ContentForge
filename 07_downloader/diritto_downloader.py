import os
import time
import json
import zipfile
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 脚本核心代码 ---

def load_settings():
    """从项目根目录的 shared_assets/settings.json 加载配置"""
    settings_path = ""
    try:
        # 修正路径：从当前脚本位置向上一级以定位项目根目录
        script_path = os.path.abspath(__file__)
        # script_dir is .../07_downloader
        script_dir = os.path.dirname(script_path)
        # project_root is .../ContentForge
        project_root = os.path.dirname(script_dir)
        
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        
        print(f"[信息] 正在从以下路径加载配置文件: {settings_path}")

        if not os.path.exists(settings_path):
            raise FileNotFoundError

        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        return settings
    except FileNotFoundError:
        print(f"⚠️ 警告: 未在 '{settings_path}' 找到 settings.json 配置文件。将使用默认下载路径。")
        return {}
    except json.JSONDecodeError:
        print("❌ 错误: settings.json 文件格式不正确。")
        return {}

def setup_driver():
    """配置并连接到已经打开的 Chrome 浏览器实例"""
    print("正在尝试连接到已启动的 Chrome 浏览器...")
    print("请确保您已按照说明使用 --remote-debugging-port=9222 启动了 Chrome。")
    
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    try:
        driver = webdriver.Chrome(options=options)
        print("✅ 成功连接到浏览器！")
        return driver
    except Exception as e:
        print(f"❌ 连接浏览器失败: {e}")
        print("请确认：")
        print("1. Chrome 浏览器是否已通过命令行启动，并带有 '--remote-debugging-port=9222' 参数？")
        print("2. 是否没有其他 Chrome 窗口（请完全退出 Chrome 后再按指令启动）？")
        return None

def scrape_novel(driver, novel_url, download_path):
    """抓取小说内容并返回章节数据"""
    print(f"正在访问小说目录页: {novel_url}")
    driver.get(novel_url)
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 获取小说标题
        novel_title_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'p[class*="e1h0h8dc1"]')))
        novel_title = novel_title_element.text.strip().replace('/', '_').replace('\\', '_')
        print(f"📘 小说标题: {novel_title}")

        # 等待章节列表加载
        print("正在获取章节列表...")
        chapter_links_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a[href*="/episodes/"]')))
        chapter_urls = [elem.get_attribute('href') for elem in chapter_links_elements]
        unique_chapter_urls = sorted(list(set(chapter_urls)), key=chapter_urls.index)
        
        print(f"共找到 {len(unique_chapter_urls)} 个章节。")

        temp_dir = os.path.join(download_path, f"{novel_title}_chapters")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        print(f"临时文件将保存在: {temp_dir}")

        for i, url in enumerate(unique_chapter_urls):
            print(f"\n--- 正在抓取第 {i + 1} / {len(unique_chapter_urls)} 章 ---")
            print(f"URL: {url}")
            driver.get(url)
            
            try:
                chapter_title_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'span[class*="e14fx9ai3"]')))
                chapter_title = chapter_title_element.text.strip()

                content_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.tiptap.ProseMirror p')))
                content = "\n\n".join([p.text for p in content_elements if p.text.strip()])
                
                if not content:
                    print("⚠️ 警告: 未能抓取到有效内容，可能为空白章节。")
                    content = "[本章内容为空或抓取失败]"

                sanitized_title = chapter_title.replace('/', '_').replace('\\', '_').replace(':', '：')
                file_name = f"{str(i + 1).zfill(4)}_{sanitized_title}.txt"
                file_path = os.path.join(temp_dir, file_name)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"章節標題: {chapter_title}\n\n")
                    f.write(content)
                
                print(f"✅ 已保存: {file_name}")

            except Exception as e:
                print(f"❌ 抓取本章失败: {e}")
                file_name = f"{str(i + 1).zfill(4)}_抓取失败.txt"
                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"无法抓取此章节内容。\nURL: {url}")

            time.sleep(2)

        return novel_title, temp_dir

    except Exception as e:
        print(f"❌ 抓取小说时发生严重错误: {e}")
        return None, None

def create_zip(novel_title, source_dir, download_path):
    """将文件夹中的所有文件打包成 ZIP"""
    zip_filename = os.path.join(download_path, f"{novel_title}.zip")
    print(f"\n正在创建 ZIP 文件: {zip_filename}")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)
    
    shutil.rmtree(source_dir)
    print(f"✅ ZIP 文件创建成功！临时文件已清理。")
    print(f"您的小说已保存至: {os.path.abspath(zip_filename)}")


if __name__ == "__main__":
    # 加载配置
    settings = load_settings()
    # 读取 'default_work_dir' 键
    default_download_path = settings.get("default_work_dir", os.path.join(os.path.expanduser("~"), "Downloads"))

    # 打印出最终使用的下载路径
    print(f"[信息] 当前下载路径设置为: {default_download_path}")

    # 让用户输入 URL
    novel_url_input = input("请输入Diritto小说目录页的 URL: ").strip()
    if not novel_url_input.startswith("http"):
        print("❌ 错误: 您输入的 URL 格式不正确。")
    else:
        # 确保下载目录存在
        if not os.path.exists(default_download_path):
            os.makedirs(default_download_path)
            print(f"已创建下载目录: {default_download_path}")

        driver = setup_driver()
        if driver:
            try:
                novel_title, chapters_dir = scrape_novel(driver, novel_url_input, default_download_path)
                if novel_title and chapters_dir:
                    create_zip(novel_title, chapters_dir, default_download_path)
            finally:
                print("\n脚本执行完毕。您可以手动关闭浏览器。")
