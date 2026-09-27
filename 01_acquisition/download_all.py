#!/usr/bin/env python3
"""
一键下载所有已购漫画 (Bomtoon.tw)

流程：
  1. 自动更新登录凭证 (调用 update_token.py 逻辑)
  2. 扫描所有已购漫画 (调用 bomtoontwext.py list-comic)
  3. 交互式询问下载目录 (默认: 上次使用的目录 / settings.json 里的 default_work_dir)
  4. 逐部执行 bomtoontwext.py dl-all
  5. 已存在的文件自动跳过，可安全断点续跑

用法:
  python download_all.py                 # 交互模式
  python download_all.py -o <dir>        # 指定目录直接开跑
  python download_all.py --no-token      # 跳过凭证刷新
  python download_all.py --dry-run       # 只显示将要下载的漫画列表
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SESSION_FILE = SCRIPT_DIR / 'bomtoontw-session'
UPDATE_TOKEN_PY = SCRIPT_DIR / 'update_token.py'
BOMTOON_PY = SCRIPT_DIR / 'bomtoontwext.py'
STATE_FILE = SCRIPT_DIR / '.download_all_state.json'

sys.path.append(str(PROJECT_ROOT))
try:
    from shared_utils import utils as cf_utils
except Exception:
    cf_utils = None


def hr(title=''):
    line = '=' * 60
    print('\n' + line)
    if title:
        print(f'  {title}')
        print(line)


def load_last_dir():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8')).get('last_dir')
        except Exception:
            return None
    return None


def save_last_dir(d):
    try:
        STATE_FILE.write_text(json.dumps({'last_dir': str(d)}, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def default_download_dir():
    d = load_last_dir()
    if d:
        return d
    if cf_utils:
        try:
            s = cf_utils.load_settings()
            if s.get('default_work_dir'):
                return s['default_work_dir']
        except Exception:
            pass
    return str(Path.home() / 'Downloads')


def run_update_token():
    hr('步骤 1/3: 自动更新登录凭证')
    print('提示: 请先【完全关闭】所有 Chrome 窗口，然后按回车继续 (或输入 s 跳过)。')
    ans = input('> ').strip().lower()
    if ans == 's':
        print('已跳过凭证更新。')
        return SESSION_FILE.exists()
    r = subprocess.run([sys.executable, str(UPDATE_TOKEN_PY)], cwd=str(SCRIPT_DIR))
    if r.returncode != 0:
        print('⚠️  凭证更新失败。')
        if SESSION_FILE.exists():
            print(f'  但检测到已存在的 {SESSION_FILE.name}，可尝试继续使用旧凭证。')
            ans = input('是否用旧凭证继续？[Y/n] ').strip().lower()
            return ans in ('', 'y', 'yes')
        return False
    return True


def list_comics():
    hr('步骤 2/3: 扫描已购漫画列表')
    if not SESSION_FILE.exists():
        print(f'❌ 未找到凭证文件 {SESSION_FILE}，请先运行凭证更新。')
        return []
    r = subprocess.run(
        [sys.executable, str(BOMTOON_PY), 'list-comic'],
        cwd=str(SCRIPT_DIR), capture_output=True, text=True
    )
    if r.returncode != 0:
        print('❌ list-comic 执行失败:')
        print(r.stderr or r.stdout)
        return []
    comics = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        cid = parts[0]
        title = parts[1] if len(parts) > 1 else cid
        comics.append((cid, title))
    return comics


def prompt_output_dir(cli_dir):
    if cli_dir:
        p = Path(cli_dir).expanduser()
        if not p.is_dir():
            print(f'❌ 目录不存在: {p}')
            sys.exit(1)
        return str(p)
    default = default_download_dir()
    while True:
        raw = input(f'\n? 请输入下载保存的目录 [默认: {default}]: ').strip()
        target = raw or default
        p = Path(target).expanduser()
        if p.is_dir():
            return str(p)
        ans = input(f'目录 "{p}" 不存在，是否创建？[Y/n] ').strip().lower()
        if ans in ('', 'y', 'yes'):
            try:
                p.mkdir(parents=True, exist_ok=True)
                return str(p)
            except Exception as e:
                print(f'❌ 创建失败: {e}')


def download_all(comics, output_dir):
    hr(f'步骤 3/3: 开始下载 {len(comics)} 部漫画 到 {output_dir}')
    results = []
    for i, (cid, title) in enumerate(comics, 1):
        print(f'\n[{i}/{len(comics)}] ▶ {cid}  {title}')
        try:
            r = subprocess.run(
                [sys.executable, str(BOMTOON_PY), 'dl-all', '-o', output_dir, cid],
                cwd=str(SCRIPT_DIR)
            )
            results.append((cid, title, r.returncode))
        except KeyboardInterrupt:
            print('\n⚠️  收到中断信号，停止后续任务。')
            results.append((cid, title, -1))
            break
    hr('下载汇总')
    ok = sum(1 for _, _, c in results if c == 0)
    print(f'成功: {ok} / {len(results)}')
    for cid, title, c in results:
        flag = '✅' if c == 0 else ('⏸' if c == -1 else '❌')
        print(f'  {flag} [{c:>3}] {cid}  {title}')


def main():
    ap = argparse.ArgumentParser(description='一键下载所有已购 Bomtoon 漫画')
    ap.add_argument('-o', '--output', help='下载保存目录 (跳过交互提示)')
    ap.add_argument('--no-token', action='store_true', help='跳过凭证刷新，直接用现有 session 文件')
    ap.add_argument('--dry-run', action='store_true', help='只列出将下载的漫画，不真正下载')
    args = ap.parse_args()

    print('=' * 60)
    print('        Bomtoon.tw 一键全量下载脚本')
    print('=' * 60)

    if not args.no_token:
        if not run_update_token():
            print('❌ 无有效凭证，退出。')
            sys.exit(1)
    else:
        if not SESSION_FILE.exists():
            print(f'❌ --no-token 模式下需要已存在的 {SESSION_FILE.name}')
            sys.exit(1)

    comics = list_comics()
    if not comics:
        print('❌ 未获取到任何已购漫画，可能是凭证失效。')
        sys.exit(1)
    print(f'共获取到 {len(comics)} 部已购漫画:')
    for i, (cid, title) in enumerate(comics, 1):
        print(f'  {i:>2}. [{cid}] {title}')

    if args.dry_run:
        print('\n(--dry-run) 未执行下载。')
        return

    output_dir = prompt_output_dir(args.output)
    save_last_dir(output_dir)

    if not args.output:
        ans = input(f'\n即将下载 {len(comics)} 部漫画到\n  {output_dir}\n确认开始？[Y/n] ').strip().lower()
        if ans not in ('', 'y', 'yes'):
            print('已取消。')
            return

    download_all(comics, output_dir)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n操作被用户中断。')
        sys.exit(130)
