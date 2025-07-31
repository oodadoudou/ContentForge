import os
import sys
import time
import json
import shutil
import traceback
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 脚本核心代码 ---

def load_default_download_path():
    """
    从共享设置文件中读取默认工作目录，如果失败则返回用户下载文件夹。
    """
    try:
        # 兼容打包后的程序 (例如 PyInstaller)
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
        # 正常脚本执行时，假定脚本位于 'scripts' 等子目录中
        else:
            # 上溯两级目录找到项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        
        if os.path.exists(settings_path):
            print(f"[信息] 找到配置文件: {settings_path}")
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            
            # 验证路径是否为有效目录
            if default_dir and os.path.isdir(default_dir):
                return default_dir
            elif default_dir:
                print(f"⚠️ 警告: 配置文件中的路径 '{default_dir}' 无效。将使用后备路径。")

    except Exception as e:
        print(f"⚠️ 警告: 读取配置文件时出错 ({e})。将使用后备路径。")

    # 如果以上任何步骤失败，则回退到系统默认的下载文件夹
    return os.path.join(os.path.expanduser("~"), "Downloads")


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

def process_book(driver, start_url, download_path):
    """
    处理单本书籍的完整下载流程，采用从主页开始并滚动加载的策略。
    """
    stats = {'skipped': 0, 'successful': 0, 'failed': 0, 'failed_items': []}
    
    try:
        # 1. 确定书籍的主页URL
        is_chapter_url = "/episodes/" in start_url
        base_url = start_url.split('/episodes/')[0] if is_chapter_url else start_url.split('?')[0]
        base_url = base_url.rstrip('/')

        print(f"正在访问书籍主页: {base_url}")
        driver.get(base_url)
        wait = WebDriverWait(driver, 45)  # 增加超时时间到45秒
        
        # 2. 获取小说标题
        print("正在等待页面加载并获取小说标题...")
        
        # 尝试多个可能的标题选择器
        title_selectors = [
            'p[class*="e1fhqjtj1"]',    # 原始选择器
            'h1[class*="title"]',       # 备用选择器1
            'h1',                       # 通用h1选择器
            'h2[class*="title"]',       # 备用选择器2
            '[class*="title"]',         # 任何包含title的class
            '.title'                    # 通用title类
        ]
        
        novel_title = None
        for selector in title_selectors:
            try:
                novel_title_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                novel_title = novel_title_element.text.strip().replace('/', '_').replace('\\', '_')
                if novel_title:  # 确保标题不为空
                    print(f"✅ 找到小说标题，使用选择器: {selector}")
                    break
            except (TimeoutException, Exception):
                print(f"⚠️ 选择器 {selector} 未找到标题，尝试下一个...")
                continue
        
        if not novel_title:
            print("⚠️ 警告: 未能获取小说标题，使用默认名称")
            novel_title = "未知小说"
            
        print(f"📘 小说标题: {novel_title}")

        # 3. 滚动到底部以加载所有章节
        print("正在获取章节列表 (滚动加载)...")
        
        # 使用多个可能的选择器来查找章节容器
        chapter_container_selectors = [
            'div[class*="eihlkz80"]',  # 原始选择器
            'div[class*="ese98wi3"]',  # 备用选择器1
            'div[class*="episode"]',   # 备用选择器2
            'div[data-testid*="episode"]',  # 备用选择器3
            'div[class*="chapter"]',   # 备用选择器4
            'div[class*="list"]'       # 备用选择器5
        ]
        
        chapter_container_found = False
        for selector in chapter_container_selectors:
            try:
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                print(f"✅ 找到章节容器，使用选择器: {selector}")
                chapter_container_found = True
                break
            except TimeoutException:
                print(f"⚠️ 选择器 {selector} 未找到元素，尝试下一个...")
                continue
        
        if not chapter_container_found:
            print("❌ 警告: 未能找到章节容器，但继续尝试滚动加载...")
        
        # 滚动加载策略，增加尝试次数限制
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10
        
        while scroll_attempts < max_scroll_attempts:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)  # 增加等待时间
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("✅ 已滚动到底部，加载完成。")
                break
            last_height = new_height
            scroll_attempts += 1
            print(f"  滚动中... ({scroll_attempts}/{max_scroll_attempts})")
        
        if scroll_attempts >= max_scroll_attempts:
            print("⚠️ 达到最大滚动尝试次数，停止滚动。")
        
        # 4. 获取所有章节链接
        # 尝试多个可能的章节列表容器选择器
        chapter_list_selectors = [
            'div[class*="ese98wi3"]',  # 原始选择器
            'div[class*="eihlkz80"]',  # 备用选择器1
            'div[class*="episode"]',   # 备用选择器2
            'div[class*="chapter"]',   # 备用选择器3
            'div[class*="list"]',      # 备用选择器4
            'main',                    # 通用容器选择器
            'body'                     # 最后的兜底选择器
        ]
        
        chapter_list_container = None
        for selector in chapter_list_selectors:
            try:
                chapter_list_container = driver.find_element(By.CSS_SELECTOR, selector)
                print(f"✅ 找到章节列表容器，使用选择器: {selector}")
                break
            except Exception:
                print(f"⚠️ 选择器 {selector} 未找到章节列表容器，尝试下一个...")
                continue
        
        if chapter_list_container is None:
            print("❌ 错误: 未能找到任何章节列表容器。")
            return None, None, stats
        
        # 尝试多个可能的章节链接选择器
        chapter_link_selectors = [
            'a[href*="/episodes/"]',     # 原始选择器
            'a[href*="episode"]',        # 备用选择器1
            'a[href*="chapter"]',        # 备用选择器2
            'a[class*="episode"]',       # 备用选择器3
            'a[class*="chapter"]'        # 备用选择器4
        ]
        
        full_url_list = []
        for selector in chapter_link_selectors:
            try:
                chapter_links_elements = chapter_list_container.find_elements(By.CSS_SELECTOR, selector)
                if chapter_links_elements:
                    urls = [elem.get_attribute('href') for elem in chapter_links_elements if elem.get_attribute('href')]
                    full_url_list = sorted(list(set(urls)))
                    print(f"✅ 找到章节链接，使用选择器: {selector}")
                    break
            except Exception:
                print(f"⚠️ 选择器 {selector} 未找到章节链接，尝试下一个...")
                continue

        if not full_url_list:
            print("❌ 错误: 未能找到任何章节链接。")
            return None, None, stats
            
        print(f"共找到 {len(full_url_list)} 个章节。")

        # 5. 确定下载起点
        start_index = 0
        if is_chapter_url:
            try:
                clean_start_url = start_url.split('?')[0].rstrip('/')
                clean_full_url_list = [url.split('?')[0].rstrip('/') for url in full_url_list]
                start_index = clean_full_url_list.index(clean_start_url)
                print(f"✅ 找到下载起点，将从第 {start_index + 1} 章开始处理。")
            except ValueError:
                print(f"⚠️ 警告: 您输入的章节URL {start_url} 未在最终的目录列表中找到。将从第一章开始处理。")
        
        # 创建以小说名命名的主目录
        book_dir = os.path.join(download_path, novel_title)
        os.makedirs(book_dir, exist_ok=True)
        print(f"所有文件将保存在: {book_dir}")
        
        # 6. 循环下载每个章节，并加入重试逻辑
        for i, url in enumerate(full_url_list[start_index:], start=start_index):
            chapter_number = i + 1
            print(f"\n--- 正在处理《{novel_title}》- 第 {chapter_number} / {len(full_url_list)} 章 ---")
            
            chapter_prefix = f"{str(chapter_number).zfill(4)}_"
            
            # 在新的 book_dir 中检查文件
            # 检查主目录和 chapters 子目录中是否已存在
            chapters_subdir = os.path.join(book_dir, "chapters")
            existing_in_main = [f for f in os.listdir(book_dir) if f.startswith(chapter_prefix) and os.path.isfile(os.path.join(book_dir, f))]
            existing_in_sub = []
            if os.path.exists(chapters_subdir):
                existing_in_sub = [f for f in os.listdir(chapters_subdir) if f.startswith(chapter_prefix)]

            if existing_in_main or existing_in_sub:
                existing_file_name = (existing_in_main + existing_in_sub)[0]
                print(f"✅ 检测到文件 '{existing_file_name}'，本章已下载，将跳过。")
                stats['skipped'] += 1
                continue

            retries = 0
            MAX_RETRIES = 3
            download_successful = False
            
            while retries < MAX_RETRIES and not download_successful:
                try:
                    if retries > 0:
                        print(f"  - 第 {retries} 次重试... URL: {url}")
                    else:
                        print(f"  - URL: {url}")
                        
                    driver.get(url)

                    # 尝试多个可能的章节标题选择器
                    chapter_title_selectors = [
                        'span[class*="e14fx9ai3"]',  # 原始选择器
                        'h1[class*="title"]',        # 备用选择器1
                        'h1',                        # 通用h1选择器
                        'h2',                        # 备用h2选择器
                        '[class*="title"]'           # 任何包含title的class
                    ]
                    
                    chapter_title = None
                    for selector in chapter_title_selectors:
                        try:
                            chapter_title_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                            chapter_title = chapter_title_element.text.strip()
                            if chapter_title:  # 确保标题不为空
                                break
                        except (TimeoutException, Exception):
                            continue
                    
                    if not chapter_title:
                        chapter_title = f"第{chapter_number}章"
                        print(f"  ⚠️ 无法获取章节标题，使用默认: {chapter_title}")
                    
                    # 尝试多个可能的内容选择器
                    content_selectors = [
                        '.tiptap.ProseMirror',       # 原始选择器
                        '.content',                  # 通用内容选择器
                        '[class*="content"]',        # 任何包含content的class
                        '.ProseMirror',              # ProseMirror编辑器
                        '[class*="text"]',           # 任何包含text的class
                        'article'                    # article标签
                    ]
                    
                    content = None
                    for selector in content_selectors:
                        try:
                            content_container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                            content_elements = content_container.find_elements(By.CSS_SELECTOR, 'p')
                            if content_elements:
                                content = "\n\n".join([p.text for p in content_elements if p.text.strip()])
                                if content.strip():  # 确保内容不为空
                                    break
                        except (TimeoutException, Exception):
                            continue
                    
                    if not content or not content.strip():
                        raise ValueError("获取到的内容为空，可能页面结构已变化。")

                    sanitized_title = chapter_title.replace('/', '_').replace('\\', '_').replace(':', '：')
                    file_name = f"{chapter_prefix}{sanitized_title}.txt"
                    file_path = os.path.join(book_dir, file_name)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"{chapter_title}\n\n")
                        f.write(content)
                    
                    print(f"  ✅ 已保存: {file_name}")
                    stats['successful'] += 1
                    download_successful = True

                except Exception as e:
                    retries += 1
                    error_msg = str(e)
                    print(f"  - 抓取本章时出错 (尝试 {retries}/{MAX_RETRIES}): {error_msg}")
                    
                    # 如果是TimeoutException，提供更详细的调试信息
                    if "TimeoutException" in error_msg or "timeout" in error_msg.lower():
                        print(f"  - 超时错误，可能是页面加载过慢或元素选择器已变化")
                        print(f"  - 当前页面URL: {driver.current_url}")
                        try:
                            page_source_preview = driver.page_source[:500]
                            print(f"  - 页面源码预览: {page_source_preview}...")
                        except:
                            print("  - 无法获取页面源码预览")
                    
                    if retries < MAX_RETRIES:
                        time.sleep(5)  # 增加重试间隔
                    else:
                        print(f"  ❌ 抓取本章失败，已达到最大重试次数。")
                        stats['failed'] += 1
                        stats['failed_items'].append({'url': url, 'error': error_msg})

            time.sleep(2)
            
        return novel_title, book_dir, stats

    except Exception as e:
        print(f"❌ 在处理书籍 {start_url} 时发生严重错误: {e}")
        traceback.print_exc()
        return None, None, stats

def merge_chapters(novel_title, book_dir):
    """将文件夹中所有TXT文件按顺序合并，然后将分卷移动到子目录。小于3KB的文件将被跳过合并。"""
    merged_filename = os.path.join(book_dir, f"{novel_title}.txt")
    print(f"\n🔄 开始合并所有章节到一个文件: {merged_filename}")
    
    try:
        if not os.path.exists(book_dir):
            print(f"⚠️ 警告: 目录 {book_dir} 不存在，无法合并。")
            return
        
        # 获取所有原始的 txt 文件
        all_txt_files = sorted([f for f in os.listdir(book_dir) if f.endswith('.txt') and os.path.isfile(os.path.join(book_dir, f))])

        if not all_txt_files:
            print("⚠️ 警告: 未找到可供合并的章节文件。")
            return

        # 筛选出大于等于3KB的文件用于合并
        files_to_merge = []
        for filename in all_txt_files:
            file_path = os.path.join(book_dir, filename)
            # 修改：将判断条件从 800 字节改为 3 KB (3 * 1024 bytes)
            if os.path.getsize(file_path) < 3 * 1024:
                print(f"  - [跳过合并] 文件 '{filename}' 小于 3 KB，视为非正文内容。")
            else:
                files_to_merge.append(filename)

        if not files_to_merge:
            print("⚠️ 警告: 筛选后没有符合大小要求的章节文件可供合并。")
        else:
            with open(merged_filename, 'w', encoding='utf-8') as outfile:
                for i, filename in enumerate(files_to_merge):
                    file_path = os.path.join(book_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                    
                    if i < len(files_to_merge) - 1:
                        outfile.write("\n\n\n==========\n\n\n")
            
            print(f"✅ 合并完成！小说已保存至: {os.path.abspath(merged_filename)}")
        
        # 将所有原始的 txt 文件移动到 chapters 子目录
        chapters_subdir = os.path.join(book_dir, "chapters")
        os.makedirs(chapters_subdir, exist_ok=True)
        
        for filename in all_txt_files:
            src_path = os.path.join(book_dir, filename)
            dest_path = os.path.join(chapters_subdir, filename)
            if os.path.exists(src_path) and src_path != merged_filename:
                shutil.move(src_path, dest_path)

        print(f"📂 章节分卷文件已移动到子目录: {os.path.abspath(chapters_subdir)}")
        
    except Exception as e:
        print(f"❌ 合并或移动文件时发生错误: {e}")

def print_book_report(stats, novel_title):
    """打印单本书籍的执行报告"""
    print("\n" + "="*40)
    print(f"📋 单本报告: {novel_title or '未知书籍'}")
    print("="*40)
    print(f"✅ 成功下载: {stats['successful']} 章")
    print(f"⏭️ 跳过下载: {stats['skipped']} 章 (已存在)")
    print(f"❌ 下载失败: {stats['failed']} 章")
    
    if stats['failed_items']:
        print("\n--- 失败项目详情 ---")
        for item in stats['failed_items']:
            print(f"  - URL: {item['url']}")
    print("="*40)

def print_total_report(all_book_stats):
    """打印所有任务的总报告"""
    total_stats = {
        'books_processed': len(all_book_stats),
        'books_completed_successfully': 0,
        'books_with_failures': 0,
        'total_successful': 0,
        'total_skipped': 0,
        'total_failed': 0,
    }

    for stats in all_book_stats:
        total_stats['total_successful'] += stats['successful']
        total_stats['total_skipped'] += stats['skipped']
        total_stats['total_failed'] += stats['failed']
        if stats['failed'] > 0:
            total_stats['books_with_failures'] += 1
        else:
            total_stats['books_completed_successfully'] += 1

    print("\n" + "#"*50)
    print("📊 所有任务总报告")
    print("#"*50)
    print(f"处理书籍总数: {total_stats['books_processed']}")
    print(f"✅ 完美完成的书籍: {total_stats['books_completed_successfully']}")
    print(f"⚠️ 部分失败的书籍: {total_stats['books_with_failures']}")
    print("-" * 20)
    print(f"总计成功下载章节: {total_stats['total_successful']}")
    print(f"总计跳过章节: {total_stats['total_skipped']}")
    print(f"总计失败章节: {total_stats['total_failed']}")
    print("#"*50)


if __name__ == "__main__":
    default_download_path = load_default_download_path()
    print(f"[信息] 当前下载路径设置为: {default_download_path}")
    
    print("\n请输入一个或多个Diritto小说URL (可分多行粘贴, 输入完成后按两次回车结束):")
    lines = []
    while True:
        try:
            line = input()
            if not line:
                break
            lines.append(line)
        except EOFError:
            break
    
    urls_input = " ".join(lines)
    url_list = [url for url in urls_input.split() if url.startswith("http")]

    if not url_list:
        print("❌ 错误: 未输入有效的URL。")
    else:
        if not os.path.exists(default_download_path):
            os.makedirs(default_download_path)
            print(f"已创建下载目录: {default_download_path}")
        
        driver = setup_driver()
        if driver:
            all_book_stats = []
            try:
                # --- 顺序处理书籍 ---
                for i, novel_url in enumerate(url_list):
                    print("\n" + "#"*60)
                    print(f"# 开始处理第 {i + 1} / {len(url_list)} 本书: {novel_url}")
                    print("#"*60 + "\n")

                    novel_title, book_dir, book_stats = process_book(driver, novel_url, default_download_path)
                    
                    if book_stats:
                        all_book_stats.append(book_stats)
                        print_book_report(book_stats, novel_title)

                    if novel_title and book_dir:
                        if book_stats and book_stats['failed'] > 0:
                            print(f"\n⚠️《{novel_title}》检测到下载失败的项目，已跳过文件合并。")
                            print(f"源文件保留在目录中: {os.path.abspath(book_dir)}")
                        else:
                            merge_chapters(novel_title, book_dir)
            finally:
                if all_book_stats:
                    print_total_report(all_book_stats)
                print("\n所有任务执行完毕。您可以手动关闭浏览器。")
