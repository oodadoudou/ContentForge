#!/usr/bin/env python3
import sys
import os
import json
import httpx

# --- 使用說明 ---
# 1. 請先安裝必要的庫: pip install browser-cookie3 httpx
# 2. 運行此腳本前，請務必完全關閉 Google Chrome 瀏覽器。
# 3. 腳本會自動在當前目錄下創建或更新 bomtoontw-session 文件。
# ---

# 腳本設定
BOMTOON_DOMAIN = 'www.bomtoon.tw'
SESSION_COOKIE_NAME = '__Secure-next-auth.session-token'
SESSION_API_URL = f'https://{BOMTOON_DOMAIN}/api/auth/session'
SESSION_FILE_NAME = 'bomtoontw-session'

def find_session_token() -> str | None:
    """
    自動從 Chrome 瀏覽器中尋找並解密 Bomtoon 的 Session Token。
    """
    print(">> 步驟 1: 正在從 Chrome 尋找 Session Token...")
    try:
        import browser_cookie3
    except ImportError:
        print("!! 錯誤: 缺少 'browser_cookie3' 庫。請先執行 'pip install browser_cookie3' 安裝。")
        return None
        
    try:
        cj = browser_cookie3.chrome(domain_name=BOMTOON_DOMAIN)
        
        for cookie in cj:
            if cookie.name == SESSION_COOKIE_NAME:
                print(f"    - 成功找到 Session Token！")
                return cookie.value
                
        print("!! 錯誤: 在 Chrome 的 Cookie 中未找到指定的 Session Token。")
        print("   請確認您是否已在 Chrome 中登錄了 Bomtoon.tw。")
        return None

    except Exception as e:
        print(f"!! 讀取 Chrome Cookie 時發生錯誤: {e}")
        print("   請確認：")
        print("   1. Google Chrome 已經完全關閉 (在 Windows 工作管理員或 macOS Dock 中確認)。")
        print("   2. 您有權限讀取 Chrome 的用戶設定檔。")
        return None

def fetch_bearer_token_from_api(session_token: str) -> str | None:
    """
    使用 Session Token 直接請求認證 API，從返回的 JSON 中提取 Bearer Token。
    """
    print(">> 步驟 2: 正在直接請求認證 API 以獲取 Bearer Token...")
    if not session_token:
        print("!! 錯誤: 因缺少 Session Token，無法繼續。")
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    }
    cookies = {
        SESSION_COOKIE_NAME: session_token
    }

    try:
        with httpx.Client(cookies=cookies, headers=headers, follow_redirects=True, timeout=20.0) as client:
            print(f"    - 正在請求 API: {SESSION_API_URL}")
            response = client.get(SESSION_API_URL)
            response.raise_for_status()

        data = response.json()
        
        # *** 已修正 ***
        # 根據您提供的返回內容，修正 JSON 的解析路徑
        try:
            bearer_token = data['user']['accessToken']['token']
        except (KeyError, TypeError):
            # 如果結構不對或中間某個 key 不存在，則捕獲錯誤
            bearer_token = None

        if bearer_token:
            print(f"    - 成功從 API 提取 Bearer Token！")
            return bearer_token
        else:
            print("!! 錯誤: 在 API 返回的數據中，無法找到 'user' -> 'accessToken' -> 'token' 這個路徑。")
            print(f"   API 返回內容: {data}")
            print("   可能是 API 結構已變更，或您的 Session Token 已過期。")
            return None

    except httpx.HTTPStatusError as e:
        print(f"!! API 請求失敗，HTTP 狀態碼: {e.response.status_code}")
        print(f"   URL: {e.request.url}")
        print("   請確認您的網路連線和 Session Token 是否有效。")
        return None
    except json.JSONDecodeError:
        print("!! 錯誤: API 返回的不是有效的 JSON 格式。")
        print(f"   收到的內容: {response.text}")
        return None
    except Exception as e:
        print(f"!! 請求 API 時發生未知錯誤: {e}")
        return None


def main():
    """主執行函數"""
    print("============================================================")
    print("        Bomtoon.tw 憑證自動更新腳本 (token_update.py)")
    print("============================================================")
    
    session_token = find_session_token()
    if not session_token:
        sys.exit(1)

    bearer_token = fetch_bearer_token_from_api(session_token)
    if not bearer_token:
        sys.exit(1)
        
    print(f">> 步驟 3: 正在將憑證寫入 '{SESSION_FILE_NAME}'...")
    try:
        content = f"{session_token}\nBearer {bearer_token}\n"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, SESSION_FILE_NAME)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("\n🎉 全部完成！")
        print(f"憑證已成功保存至: {file_path}")

    except IOError as e:
        print(f"!! 寫入文件時發生錯誤: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()