import os
import re
import json
import time
import shutil
import sys
import threading
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import pandas as pd
import concurrent.futures
import requests

# --- 辅助函数 ---
def load_config(default_url, default_path):
    """从JSON文件中加载配置。"""
    config_file = 'manga_downloader_config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return {'url': default_url, 'path': default_path}

def save_config(data):
    """将配置保存到JSON文件。"""
    with open('manga_downloader_config.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def sanitize_for_filename(name):
    """将字符串转换为安全的文件名。"""
    if not name: return "Untitled"
    return " ".join(re.sub(r'[<>:"/\\|?*]', '', name).replace(':', ' -').strip().rstrip('. ').split())

def parse_chapter_selection(selection_str, max_chapters):
    """解析用户输入的章节选择 (例如 '1, 3-5, 8')。"""
    selection_set = set()
    if selection_str.strip().lower() == 'all':
        return list(range(1, max_chapters + 1))
    for part in re.split(r'[,\s]+', selection_str):
        if not part: continue
        try:
            if '-' in part:
                start, end = map(int, part.split('-'))
                selection_set.update(range(min(start, end), max(start, end) + 1))
            else:
                selection_set.add(int(part))
        except ValueError:
            print(f"[!] 警告: 无效输入 '{part}'。")
    return sorted([num for num in selection_set if 1 <= num <= max_chapters])

def get_timed_input(prompt, timeout=30):
    """带超时的用户输入。"""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    result = [None]
    def _blocking_input(res):
        try: res[0] = sys.stdin.readline().strip()
        except Exception: pass
    input_thread = threading.Thread(target=_blocking_input, args=(result,))
    input_thread.daemon = True
    input_thread.start()
    input_thread.join(timeout)
    if input_thread.is_alive():
        print()
        return None
    return result[0]

def download_single_image(args):
    """使用 requests session 带重试功能下载单个图片。"""
    img_url, save_path, session, index, total, chapter_name = args
    if save_path.exists():
        return {'status': 'skipped', 'path': save_path}
    
    for attempt in range(3):
        try:
            response = session.get(img_url, stream=True, timeout=60)
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"    -> (Requests) 已下载: {save_path.name} ({index}/{total})")
            return {'status': 'success', 'path': save_path}
        except requests.exceptions.RequestException as e:
            if attempt == 2:
                print(f"    - [Requests失败] {save_path.name}: {e}")
            else:
                time.sleep(1)
    return {'status': 'failed', 'args': args}

# --- 主流程类 ---
class BakamhPipeline:
    def __init__(self):
        self.driver = None
        self.base_url = ''
        self.failed_downloads = []
        self.successful_chapters = set()
        self.screenshot_successes = []
        self.total_images_downloaded = 0
        self.total_images_skipped = 0

    def _init_driver(self):
        """初始化 undetected_chromedriver。"""
        if self.driver: return True
        print("[*] 正在初始化浏览器驱动...")
        try:
            options = uc.ChromeOptions()
            # options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--log-level=3')
            self.driver = uc.Chrome(options=options)
            print("[+] 浏览器驱动初始化成功。")
            return True
        except Exception as e:
            print(f"[!] 浏览器驱动初始化失败: {e}")
            return False

    def get_manga_title(self, url):
        """仅获取漫画标题用于检查缓存。"""
        if not self._init_driver(): return None
        print(f"[*] 正在访问: {url} 以获取标题...")
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ol.breadcrumb li:nth-last-child(2) a')))
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            manga_title = sanitize_for_filename(soup.select_one('ol.breadcrumb li:nth-last-child(2) a').text)
            parsed_url = urlparse(url)
            self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            print(f"[+] 获取到漫画标题: {manga_title}")
            return manga_title
        except Exception as e:
            print(f"[!] 无法从初始URL获取漫画标题: {e}")
            return None

    def get_online_chapter_list(self):
        """从当前已加载的页面获取基础章节列表。"""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        online_chapters = []
        seen_urls = set()
        options = soup.select('select.single-chapter-select option')
        options.reverse()
        for option in options:
            if 'data-redirect' in option.attrs:
                chapter_url = option['data-redirect']
                if chapter_url not in seen_urls:
                    online_chapters.append({
                        'name': sanitize_for_filename(option.get_text(strip=True)),
                        'url': chapter_url
                    })
                    seen_urls.add(chapter_url)
        return online_chapters
        
    def scan_chapter_details(self, chapters_to_scan):
        """扫描一系列章节以获取其图片数量。"""
        scanned_chapters = []
        print(f"[*] 开始扫描 {len(chapters_to_scan)} 个章节的详情...")
        for i, chapter_info in enumerate(chapters_to_scan):
            print(f"    -> 正在扫描章节 {i+1}/{len(chapters_to_scan)}: {chapter_info['name']}")
            try:
                self.driver.get(chapter_info['url'])
                WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'img.wp-manga-chapter-img')))
                chap_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                img_count = len(chap_soup.select('div.reading-content img.wp-manga-chapter-img'))
                chapter_info['imgs_count'] = img_count
                scanned_chapters.append(chapter_info)
            except Exception as e:
                print(f"      [!] 扫描失败，跳过此章节: {e}")
        return scanned_chapters

    def download_with_screenshot(self, args):
        """在新标签页中打开图片并截图保存。"""
        img_url, save_path, _, index, total, chapter_name = args
        try:
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self.driver.get(img_url)
            time.sleep(0.5)
            img_element = self.driver.find_element(By.TAG_NAME, "img")
            img_element.screenshot(str(save_path))
            print(f"    -> (截图) 已下载: {save_path.name} ({index}/{total})")
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return {'status': 'success'}
        except Exception as e:
            print(f"    - [截图失败] {save_path.name}: {e}")
            if len(self.driver.window_handles) > 1:
                self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return {'status': 'failed', 'url': img_url, 'chapter': chapter_name}

    def process_chapters(self, chapters_to_download, manga_path):
        """访问每个章节，优先使用requests下载，失败后自动切换到截图模式。"""
        if not self._init_driver(): return
        
        print("\n--- [阶段三] 处理并下载章节 ---")
        original_window = self.driver.current_window_handle

        for i, chapter in enumerate(chapters_to_download):
            chapter_name = f"{chapter['index']:03d} - {chapter['name']}"
            print(f"\n[*] 正在处理章节: {chapter_name} ({i+1}/{len(chapters_to_download)})")
            chapter_output_dir = manga_path / chapter_name
            chapter_output_dir.mkdir(exist_ok=True)
            
            expected_img_count = chapter.get('imgs_count', 0)
            if expected_img_count > 0:
                local_files = [f for f in chapter_output_dir.iterdir() if f.is_file()]
                if len(local_files) >= expected_img_count:
                    print(f"    [*] 检测到所有 {expected_img_count} 张图片均已存在，跳过此章节。")
                    self.successful_chapters.add(chapter_name)
                    self.total_images_skipped += len(local_files)
                    continue

            page_loaded = False
            for attempt in range(3):
                try:
                    self.driver.get(chapter['url'])
                    WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'img.wp-manga-chapter-img')))
                    page_loaded = True
                    break
                except Exception as e:
                    print(f"    [!] 加载页面失败 (尝试 {attempt + 1}/3): {e}")
                    if attempt < 2:
                        print("    [*] 5秒后重试...")
                        time.sleep(5)
            
            if not page_loaded:
                print(f"    [!] 无法加载章节页面，跳过此章节。")
                self.failed_downloads.append({'status': 'failed', 'url': chapter['url'], 'chapter': chapter_name})
                continue

            try:
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                browser_cookies = self.driver.get_cookies()
                session = requests.Session()
                for cookie in browser_cookies:
                    session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
                
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                    'Referer': chapter['url']
                })

                image_tags = soup.select('div.reading-content img.wp-manga-chapter-img')
                if not image_tags:
                    print("    [!] 警告: 此页面未找到图片。")
                    continue

                tasks = []
                for idx, img_tag in enumerate(image_tags):
                    img_src = img_tag.get('src', '').strip()
                    if not img_src: continue
                    img_src = urljoin(self.base_url, img_src)
                    file_ext = os.path.splitext(urlparse(img_src).path)[1] or '.webp'
                    img_filename = f"{idx+1:03d}{file_ext}"
                    save_path = chapter_output_dir / img_filename
                    tasks.append((img_src, save_path, session, idx + 1, len(image_tags), chapter_name))

                print(f"    [*] 发现 {len(tasks)} 张图片。优先使用并行下载...")
                failed_for_screenshot = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    results = executor.map(download_single_image, tasks)
                    for result in results:
                        if result.get('status') == 'failed':
                            failed_for_screenshot.append(result['args'])
                        elif result.get('status') == 'success':
                            self.total_images_downloaded += 1
                        elif result.get('status') == 'skipped':
                            self.total_images_skipped += 1
                
                if failed_for_screenshot:
                    print(f"    [*] {len(failed_for_screenshot)} 张图片下载失败，切换到截图模式进行补救...")
                    for task_args in failed_for_screenshot:
                        result = self.download_with_screenshot(task_args)
                        if result.get('status') == 'failed':
                            self.failed_downloads.append(result)
                        else:
                            self.total_images_downloaded += 1
                            self.screenshot_successes.append({'path': str(task_args[1]), 'chapter': chapter_name})
                
                if not any(f['chapter'] == chapter_name for f in self.failed_downloads):
                    self.successful_chapters.add(chapter_name)

            except Exception as e:
                print(f"    [!] 处理章节 {chapter_name} 失败: {e}")
                self.failed_downloads.append({'status': 'failed', 'url': chapter['url'], 'chapter': chapter_name})
            finally:
                self.driver.switch_to.window(original_window)

    def print_summary_report(self, manga_path):
        """打印最终报告，包括成功、失败详情和保存路径。"""
        print("\n" + "="*25 + " [最终任务报告] " + "="*25)
        print(f"\n[+] 漫画保存目录:\n    -> {manga_path.resolve()}")

        total_chapters_processed = len(self.successful_chapters) + len(set(f['chapter'] for f in self.failed_downloads))
        
        if total_chapters_processed == 0:
             print("\n[!] 未执行任何下载任务。")
             print("\n" + "="*68)
             return

        print(f"\n[✓] 成功处理 {len(self.successful_chapters)} 个章节。")
        print(f"    - 新下载图片: {self.total_images_downloaded} 张")
        print(f"    - 已存在并跳过: {self.total_images_skipped} 张")

        if self.screenshot_successes:
            print(f"\n  [!] {len(self.screenshot_successes)} 张图片通过截图模式补救成功:")
            from itertools import groupby
            sorted_screenshots = sorted(self.screenshot_successes, key=lambda x: x['chapter'])
            for chapter_name, group in groupby(sorted_screenshots, key=lambda x: x['chapter']):
                print(f"      - 章节 [{chapter_name}]:")
                for success in group:
                    print(f"        - {Path(success['path']).name}")
        
        if self.failed_downloads:
            print(f"\n[✗] {len(self.failed_downloads)} 个项目最终下载失败:")
            from itertools import groupby
            sorted_failures = sorted(self.failed_downloads, key=lambda x: x['chapter'])
            for chapter_name, group in groupby(sorted_failures, key=lambda x: x['chapter']):
                print(f"      - 章节 [{chapter_name}]:")
                for failure in group:
                    print(f"        - URL: {failure['url']}")
        elif self.total_images_downloaded > 0 or self.total_images_skipped > 0:
            print("\n[🎉] 所有图片均已成功下载！")

        print("\n" + "="*68)

    def close(self):
        """关闭 Selenium WebDriver。"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n[*] 浏览器驱动已关闭。")
            except Exception:
                print("\n[*] 浏览器驱动可能已经关闭。")

def main():
    print("--- bakamh.com 漫画下载器 (v2.8 - 终极版) ---")
    config = load_config("https://bakamh.com/manga/%e6%b7%b1%e6%b8%8a-3/c-1/", "./manga_downloads")
    
    initial_url = input(f"1. 输入任意章节URL [{config.get('url')}]: ").strip() or config.get('url')
    output_path = Path(input(f"2. 输入下载根目录 [{config.get('path')}]: ").strip() or config.get('path'))

    if not (initial_url and str(output_path)):
        print("[!] URL和路径不能为空。")
        return
    
    save_config({'url': initial_url, 'path': str(output_path)})
    
    pipeline = BakamhPipeline()
    manga_path = None
    try:
        manga_title = pipeline.get_manga_title(initial_url)
        if not manga_title:
            print("[!] 无法获取漫画标题，程序终止。")
            return

        manga_path = output_path / manga_title
        json_path = manga_path / f"{manga_title}_chapters.json"
        manga_path.mkdir(parents=True, exist_ok=True)
        
        chapters = []
        if json_path.exists():
            print(f"[i] 发现本地章节缓存文件: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                local_chapters = json.load(f)
            
            print("[*] 正在检查网站有无更新...")
            online_chapters_basic = pipeline.get_online_chapter_list()
            
            if len(online_chapters_basic) <= len(local_chapters):
                print("[+] 本地缓存已是最新，将从缓存加载。")
                chapters = local_chapters
            else:
                print(f"[!] 发现新章节！将更新本地缓存。")
                local_urls = {ch['url'] for ch in local_chapters}
                new_chapters_to_scan = [ch for ch in online_chapters_basic if ch['url'] not in local_urls]
                
                scanned_new_chapters = pipeline.scan_chapter_details(new_chapters_to_scan)
                chapters = local_chapters + scanned_new_chapters
                for i, c in enumerate(chapters):
                    c['index'] = i + 1
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(chapters, f, indent=4, ensure_ascii=False)
                print(f"[+] 章节列表已更新并保存至: {json_path}")

        else:
            print("[!] 未发现本地章节缓存。将从网站扫描获取。")
            online_chapters_basic = pipeline.get_online_chapter_list()
            chapters = pipeline.scan_chapter_details(online_chapters_basic)
            if chapters:
                for i, c in enumerate(chapters):
                    c['index'] = i + 1
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(chapters, f, indent=4, ensure_ascii=False)
                print(f"[+] 章节列表及图片数量已保存至: {json_path}")

        if not chapters:
            print("[!] 无法获取或加载章节列表，程序终止。")
            return

        print("\n--- [阶段二] 请选择要下载的章节 ---")
        display_df = pd.DataFrame([{"Index": c['index'], "Chapter Name": c['name'], "Images": c.get('imgs_count', 'N/A')} for c in chapters])
        print(display_df.to_string(index=False))
        
        selection_str = get_timed_input("\n输入章节序号 (例如: 1, 3-5, all) [回车默认下载全部]: ", 30) or 'all'
        selected_indices = parse_chapter_selection(selection_str, len(chapters))
        if not selected_indices:
            print("[!] 未选择有效章节，程序终止。")
            return
        
        chapters_to_download = [chapters[i-1] for i in selected_indices]
        
        pipeline.process_chapters(chapters_to_download, manga_path)
        
    except Exception as e:
        import traceback
        print(f"\n[!!!] 发生意外错误: {e}")
        traceback.print_exc()
    finally:
        pipeline.close()
        if manga_path:
            pipeline.print_summary_report(manga_path)
        print("\n--- 脚本执行完毕 ---")

if __name__ == '__main__':
    main()
