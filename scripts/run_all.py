import os
import sys
import traceback
import importlib
import json
from pathlib import Path


def sc_send(sendkey: str, title: str, desp: str = '', options: dict | None = None) -> dict:
    import requests
    import re
    if options is None:
        options = {}
    if sendkey.startswith('sctp'):
        match = re.match(r'sctp(\d+)t', sendkey)
        if match:
            num = match.group(1)
            url = f'https://{num}.push.ft07.com/send/{sendkey}.send'
        else:
            raise ValueError('Invalid sendkey format for sctp')
    else:
        url = f'https://sctapi.ftqq.com/{sendkey}.send'
    params = {
        'title': title,
        'desp': desp,
        **options
    }
    headers = {
        'Content-Type': 'application/json;charset=utf-8'
    }
    resp = requests.post(url, json=params, headers=headers, timeout=30)
    return resp.json() if resp.content else {"ok": False, "error": "empty response"}


def run_rainyun() -> tuple[bool, str]:
    try:
        rainyun_dir = Path(__file__).resolve().parents[1] / 'Rainyun'
        sys.path.append(str(rainyun_dir))
        ry = importlib.import_module('rainyun')
        # 切换工作目录，保证 rainyun 内部的相对路径可用
        cwd = os.getcwd()
        os.chdir(str(rainyun_dir))
        try:
            # 直接调用 main()，其内部会自行清理。若不中断视为成功。
            try:
                ry.main()
                return True, 'Rainyun: 执行完成'
            except SystemExit:
                # 若内部调用了 exit，按失败处理
                return False, 'Rainyun: 脚本调用 SystemExit'
        finally:
            os.chdir(cwd)
    except Exception as e:
        return False, f'Rainyun: 失败 - {e}\n{traceback.format_exc()}'


def run_ikuuu() -> tuple[bool, str]:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / 'iKuuu'))
        ik = importlib.import_module('iKuuu')
        client = ik.IKuuuClient()
        success = client.run()
        try:
            client.close()
        except Exception:
            pass
        return (True, 'iKuuu: 签到成功') if success else (False, 'iKuuu: 执行失败')
    except Exception as e:
        return False, f'iKuuu: 失败 - {e}\n{traceback.format_exc()}'


def run_lowendspirit() -> tuple[bool, str]:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / 'FreeVPS'))
        les = importlib.import_module('lowendspirit')
        bot = les.Lowendtalk()
        try:
            # 读取文章并发帖
            import tools as _tools
        except Exception:
            from FreeVPS import tools as _tools  # 兜底导入
        try:
            title, content = _tools.get_vps_article()
        except Exception:
            # 若获取失败，使用占位内容以便流程不中断
            title, content = 'Auto Post', 'Automated post by GitHub Actions.'
        bot.run_task(title, content)
        try:
            bot.tab.close()
        except Exception:
            pass
        # run_task 内部未显式返回，若能走到这里视为成功
        return True, 'LowEndSpirit: 发帖流程完成'
    except Exception as e:
        return False, f'LowEndSpirit: 失败 - {e}\n{traceback.format_exc()}'


def main() -> int:
    tasks = [
        ("Rainyun", run_rainyun),
        ("iKuuu", run_ikuuu),
        ("LowEndSpirit", run_lowendspirit),
    ]

    lines: list[str] = []
    all_success = True

    for name, fn in tasks:
        ok, msg = fn()
        prefix = '✅' if ok else '❌'
        lines.append(f'{prefix} {msg}')
        if not ok:
            all_success = False

    summary_title = '自动任务执行结果'
    summary_body = '\n\n'.join(lines)

    sendkey = os.getenv('SENDKEY', '').strip()
    if sendkey:
        try:
            sc_send(sendkey, summary_title, summary_body)
        except Exception:
            # 推送失败不影响退出码
            lines.append('⚠️ Server酱推送失败')
    else:
        lines.append('⚠️ 未配置 SENDKEY，跳过推送')

    print('\n'.join(lines))
    return 0 if all_success else 1


if __name__ == '__main__':
    raise SystemExit(main())


