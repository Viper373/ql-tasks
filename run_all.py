# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/
# @FileName       :run_all.py
# @Time           :2025/9/13
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import os
import sys
import time
import traceback
import importlib
import subprocess
import signal
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable

import requests
from loguru import logger
from DrissionPage import ChromiumOptions, Chromium


# 常量定义
DEFAULT_CHROME_PORT = 9222
MAX_BROWSER_RETRIES = 3
BROWSER_CLEANUP_DELAY = 2
REQUEST_TIMEOUT = 30


class TaskOutputCollector:
    """任务输出信息收集器"""
    
    def __init__(self):
        self.outputs: List[Dict[str, Any]] = []
        self.current_task: Optional[str] = None
        self.current_outputs: List[Dict[str, Any]] = []
    
    def start_task(self, task_name: str) -> None:
        """开始收集任务输出"""
        self.current_task = task_name
        self.current_outputs = []
    
    def add_output(self, level: str, message: str) -> None:
        """添加输出信息"""
        if self.current_task:
            self.current_outputs.append({
                'level': level,
                'message': message,
                'timestamp': time.time()
            })
    
    def finish_task(self, success: bool, summary: str = "") -> None:
        """完成任务收集"""
        if self.current_task:
            self.outputs.append({
                'task_name': self.current_task,
                'success': success,
                'summary': summary,
                'details': self.current_outputs.copy()
            })
            self.current_task = None
            self.current_outputs = []
    
    def get_formatted_output(self) -> str:
        """获取格式化的输出信息"""
        result = [
            "## 🚀 AutoTasks 执行报告",
            ""
        ]
        
        for task in self.outputs:
            status_icon = "✅" if task['success'] else "❌"
            result.append(f"### {status_icon} {task['task_name']}")
            
            if task['summary']:
                result.append(f"**执行结果**: {task['summary']}")
                result.append("")
            
            # 添加详细信息
            if task['details']:
                result.append("**详细信息**:")
                for detail in task['details']:
                    icon_map = {
                        'success': '✅',
                        'info': 'ℹ️',
                        'warning': '⚠️',
                        'error': '❌'
                    }
                    icon = icon_map.get(detail['level'], 'ℹ️')
                    result.append(f"- {icon} {detail['message']}")
                result.append("")
            else:
                result.append("")
        
        # 添加总结
        success_count = sum(1 for task in self.outputs if task['success'])
        total_count = len(self.outputs)
        result.extend([
            "---",
            f"**总结**: {success_count}/{total_count} 个任务执行成功"
        ])
        
        return "\n".join(result)


# 全局输出收集器
output_collector = TaskOutputCollector()


class TaskLogger:
    """任务专用日志记录器，用于捕获任务输出"""
    
    def __init__(self, task_name: str):
        self.task_name = task_name
        self.original_logger = logger
    
    def info(self, message: str) -> None:
        """记录信息日志"""
        self.original_logger.info(message)
        output_collector.add_output('info', message)
    
    def success(self, message: str) -> None:
        """记录成功日志"""
        self.original_logger.success(message)
        output_collector.add_output('success', message)
    
    def warning(self, message: str) -> None:
        """记录警告日志"""
        self.original_logger.warning(message)
        output_collector.add_output('warning', message)
    
    def error(self, message: str) -> None:
        """记录错误日志"""
        self.original_logger.error(message)
        output_collector.add_output('error', message)


def show_banner() -> None:
    """显示程序横幅"""
    banner_lines = [
        "=" * 70,
        "🚀  AutoTasks 自动签到工具集 v1.0-DP by Viper373",
        "📦  支持雨云、iKuuu、Leaflow 自动签到",
        "🔗  Github: https://github.com/Viper373/AutoTasks",
        "=" * 70
    ]
    print("\n".join(banner_lines))


class GlobalBrowserManager:
    """全局浏览器管理器"""
    
    def __init__(self, debug: bool = False):
        self.browser: Optional[Chromium] = None
        self.port = DEFAULT_CHROME_PORT
        self.debug = debug
        self._setup_browser(debug)
    
    def _kill_existing_chrome_processes(self) -> None:
        """清理可能存在的Chrome/Chromium进程"""
        try:
            # 使用ps查找Chrome/Chromium进程
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'chrome' in line.lower() or 'chromium' in line.lower():
                        if f'{self.port}' in line or '--remote-debugging-port' in line:
                            parts = line.split()
                            if len(parts) > 1:
                                try:
                                    pid = int(parts[1])
                                    os.kill(pid, signal.SIGTERM)
                                    logger.info(f"🔄 清理Chrome进程: {pid}")
                                    time.sleep(1)
                                except (ProcessLookupError, ValueError, IndexError):
                                    pass
            
            # 额外清理可能的Chrome进程
            subprocess.run(['pkill', '-f', f'chrome.*{self.port}'], 
                          capture_output=True, text=True)
            subprocess.run(['pkill', '-f', f'chromium.*{self.port}'], 
                          capture_output=True, text=True)
            
        except Exception as e:
            logger.debug(f"清理进程时出现异常: {e}")
    
    def _force_kill_port_processes(self) -> None:
        """强制清理占用端口的进程"""
        try:
            logger.info(f"🔨 强制清理端口 {self.port} 上的所有进程...")
            
            if os.name == 'posix':
                self._kill_posix_processes()
            else:
                self._kill_windows_processes()
            
            # 等待进程完全清理
            time.sleep(3)
            
        except Exception as e:
            logger.warning(f"强制清理进程时出现异常: {e}")
    
    def _kill_posix_processes(self) -> None:
        """Linux/macOS进程清理"""
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'chrome' in line.lower() or 'chromium' in line.lower():
                    if f'{self.port}' in line or '--remote-debugging-port' in line:
                        parts = line.split()
                        if len(parts) > 1:
                            try:
                                pid = int(parts[1])
                                # 先尝试SIGTERM
                                os.kill(pid, signal.SIGTERM)
                                time.sleep(1)
                                # 如果还存在，使用SIGKILL强制终止
                                try:
                                    os.kill(pid, 0)  # 检查进程是否还存在
                                    os.kill(pid, signal.SIGKILL)
                                    logger.info(f"🔨 强制终止进程: {pid}")
                                except ProcessLookupError:
                                    pass  # 进程已经不存在
                            except (ProcessLookupError, ValueError, IndexError):
                                pass
    
    def _kill_windows_processes(self) -> None:
        """Windows进程清理"""
        try:
            # 查找占用端口的进程
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if f':{self.port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            try:
                                pid = int(parts[-1])
                                # 强制终止进程
                                subprocess.run(['taskkill', '/PID', str(pid), '/F'], 
                                             capture_output=True, text=True)
                                logger.info(f"🔨 强制终止Windows进程: {pid}")
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            logger.debug(f"Windows端口清理失败: {e}")
    
    def _setup_browser(self, debug: bool) -> None:
        """设置并启动全局浏览器"""
        try:
            logger.info("🌐 正在启动全局浏览器...")
            
            # 创建浏览器选项
            co = ChromiumOptions()
            self._configure_browser_options(co, debug)
            
            # 启动浏览器（带重试机制）
            logger.info("🚀 正在启动浏览器进程...")
            self._start_browser_with_retry(co)
            
        except Exception as e:
            logger.exception(f"❌ 全局浏览器启动失败: {e}")
            self.browser = None
    
    def _configure_browser_options(self, co: ChromiumOptions, debug: bool) -> None:
        """配置浏览器选项"""
        # 基础选项
        browser_args = [
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-extensions',
            '--disable-plugins',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-web-security',
            f'--remote-debugging-port={self.port}'
        ]
        
        for arg in browser_args:
            co.set_argument(arg)
        
        # 根据debug模式设置headless
        if not debug:
            co.headless(True)
            co.set_argument('--headless=new')
        else:
            logger.info("🔧 Debug模式：浏览器将以有头模式运行")
        
        # 设置Chrome路径
        chrome_executable = os.getenv('CHROME_EXECUTABLE')
        if chrome_executable:
            co.set_browser_path(chrome_executable)
            logger.info(f"✅ 使用环境变量Chrome路径: {chrome_executable}")
        
        # 设置端口
        co.set_local_port(self.port)
        logger.info(f"🔌 使用固定端口: {self.port}")
        
        # Linux/macOS环境先清理旧进程
        if os.name == 'posix':
            self._kill_existing_chrome_processes()
    
    def _start_browser_with_retry(self, co: ChromiumOptions) -> None:
        """带重试机制的浏览器启动"""
        for retry in range(MAX_BROWSER_RETRIES):
            try:
                if retry > 0:
                    logger.info(f"🔄 重试 {retry + 1}/{MAX_BROWSER_RETRIES}，强制清理端口 {self.port}")
                    self._force_kill_port_processes()
                    time.sleep(BROWSER_CLEANUP_DELAY)
                
                self.browser = Chromium(co)
                logger.success("✅ 全局浏览器启动成功")
                break
            except Exception as e:
                if retry < MAX_BROWSER_RETRIES - 1:
                    logger.warning(f"⚠️ 浏览器启动失败 (尝试 {retry + 1}/{MAX_BROWSER_RETRIES}): {e}")
                    time.sleep(BROWSER_CLEANUP_DELAY)
                else:
                    raise e
    
    def get_browser(self) -> Optional[Chromium]:
        """获取浏览器实例"""
        return self.browser
    
    def cleanup(self) -> None:
        """清理浏览器资源"""
        if self.browser:
            try:
                logger.info("🧹 正在清理全局浏览器...")
                # 关闭所有标签页
                try:
                    tabs = self.browser.get_tabs()
                    for tab in tabs:
                        tab.close()
                except Exception:
                    pass
                # 关闭浏览器
                self.browser.quit()
                time.sleep(BROWSER_CLEANUP_DELAY)
                logger.info("✅ 全局浏览器已关闭")
            except Exception as e:
                logger.warning(f"⚠️ 关闭浏览器时出现异常: {e}")


# 全局浏览器管理器实例
browser_manager: Optional[GlobalBrowserManager] = None


def sc_send(sendkey: str, title: str, desp: str = '', options: Optional[dict] = None) -> dict:
    """发送Server酱推送消息"""
    if options is None:
        options = {}
    
    # 构建URL
    if sendkey.startswith('sctp'):
        match = re.match(r'sctp(\d+)t', sendkey)
        if match:
            num = match.group(1)
            url = f'https://{num}.push.ft07.com/send/{sendkey}.send'
        else:
            raise ValueError('Invalid sendkey format for sctp')
    else:
        url = f'https://sctapi.ftqq.com/{sendkey}.send'
    
    # 构建请求参数
    params = {
        'title': title,
        'desp': desp,
        **options
    }
    headers = {
        'Content-Type': 'application/json;charset=utf-8'
    }
    
    # 发送请求
    resp = requests.post(url, json=params, headers=headers, timeout=REQUEST_TIMEOUT)
    return resp.json() if resp.content else {"ok": False, "error": "empty response"}


def _run_task_with_browser(task_name: str, module_name: str, class_name: str, 
                        init_method: str = '__init__', run_method: str = 'run') -> Tuple[bool, str]:
    """通用任务执行函数，使用全局浏览器"""
    output_collector.start_task(task_name)
    try:
        # 清理模块缓存
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # 导入模块
        module_dir = Path(__file__).resolve().parent / module_name
        sys.path.append(str(module_dir))
        module = importlib.import_module(module_name)
        
        # 创建实例
        task_class = getattr(module, class_name)
        instance = task_class(debug=browser_manager.debug, output_collector=output_collector)
        
        # 设置浏览器
        if hasattr(instance, 'browser'):
            instance.browser = browser_manager.get_browser()
        if hasattr(instance, 'page'):
            instance.page = instance.browser.latest_tab
        if hasattr(instance, 'tab'):
            instance.tab = instance.browser.latest_tab
        
        # 初始化
        if hasattr(instance, init_method):
            getattr(instance, init_method)()
        
        # 添加任务开始信息
        output_collector.add_output('info', f'开始执行{task_name}任务')
        
        # 执行任务
        if hasattr(instance, run_method):
            result = getattr(instance, run_method)()
            if isinstance(result, bool):
                success = result
            else:
                success = True
        else:
            success = True
        
        if success:
            output_collector.add_output('success', f'{task_name}任务执行成功')
            output_collector.finish_task(True, f"{task_name}任务执行成功")
            return True, f'{task_name}: 执行成功'
        else:
            output_collector.add_output('error', f'{task_name}任务执行失败')
            output_collector.finish_task(False, f"{task_name}任务执行失败")
            return False, f'{task_name}: 执行失败'
            
    except Exception as e:
        output_collector.add_output('error', f'{task_name}: 失败 - {e}')
        output_collector.finish_task(False, f"{task_name}任务异常: {e}")
        return False, f'{task_name}: 失败 - {e}\n{traceback.format_exc()}'


def run_rainyun() -> Tuple[bool, str]:
    output_collector.start_task("Rainyun")
    try:
        rainyun_dir = Path(__file__).resolve().parent / 'Rainyun'
        sys.path.append(str(rainyun_dir))
        ry = importlib.import_module('rainyun')
        
        # 切换工作目录，保证 rainyun 内部的相对路径可用
        cwd = os.getcwd()
        os.chdir(str(rainyun_dir))
        
        try:
            # 创建雨云签到器实例，传入全局浏览器和debug参数
            signer = ry.RainyunSigner(debug=browser_manager.debug, output_collector=output_collector)
            signer.browser = browser_manager.get_browser()
            signer.page = signer.browser.latest_tab
            signer.init_browser()
            
            # 添加一些关键信息到输出收集器
            output_collector.add_output('info', '开始执行雨云签到任务')
            
            # 执行签到任务
            signer.run()
            
            # 尝试获取签到后的积分信息
            try:
                points_element = signer.page.ele('xpath://*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3')
                if points_element:
                    current_points = int(''.join(re.findall(r'\d+', points_element.text))) if points_element.text else 0
                    output_collector.add_output('success', f'当前积分: {current_points} | 约为 {current_points / 2000:.2f} 元')
            except Exception:
                pass  # 如果获取积分失败，不影响整体流程
            
            output_collector.finish_task(True, "雨云签到任务执行完成")
            return True, 'Rainyun: 执行完成'
        finally:
            os.chdir(cwd)
    except Exception as e:
        output_collector.add_output('error', f'Rainyun: 失败 - {e}')
        output_collector.finish_task(False, f"雨云签到任务失败: {e}")
        return False, f'Rainyun: 失败 - {e}\n{traceback.format_exc()}'


def run_ikuuu() -> Tuple[bool, str]:
    output_collector.start_task("iKuuu")
    try:
        # 清理模块缓存
        if 'iKuuu' in sys.modules:
            del sys.modules['iKuuu']
        
        sys.path.append(str(Path(__file__).resolve().parent / 'iKuuu'))
        ik = importlib.import_module('iKuuu')
        client = ik.IKuuuClient(debug=browser_manager.debug, output_collector=output_collector)
        # 使用全局浏览器
        client.browser = browser_manager.get_browser()
        client.tab = client.browser.latest_tab
        client.start()  # 调用start方法初始化
        
        output_collector.add_output('info', '开始执行iKuuu签到任务')
        success = client.run()
        
        if success:
            output_collector.add_output('success', 'iKuuu签到任务执行成功')
            output_collector.finish_task(True, "iKuuu签到任务执行成功")
            return True, 'iKuuu: 签到成功'
        else:
            output_collector.add_output('error', 'iKuuu签到任务执行失败')
            output_collector.finish_task(False, "iKuuu签到任务执行失败")
            return False, 'iKuuu: 执行失败'
    except Exception as e:
        output_collector.add_output('error', f'iKuuu: 失败 - {e}')
        output_collector.finish_task(False, f"iKuuu签到任务异常: {e}")
        return False, f'iKuuu: 失败 - {e}\n{traceback.format_exc()}'


def run_leaflow() -> Tuple[bool, str]:
    output_collector.start_task("Leaflow")
    try:
        # 清理模块缓存
        if 'leaflow' in sys.modules:
            del sys.modules['leaflow']
        
        leaflow_dir = Path(__file__).resolve().parent / 'leaflow'
        sys.path.append(str(leaflow_dir))
        leaflow = importlib.import_module('leaflow')
        signer = leaflow.LeaflowSigner(debug=browser_manager.debug, output_collector=output_collector)
        
        output_collector.add_output('info', '开始执行Leaflow签到任务')
        signer.run()
        
        output_collector.add_output('success', 'Leaflow签到任务执行完成')
        output_collector.finish_task(True, "Leaflow签到任务执行完成")
        return True, 'Leaflow: 执行完成'
    except Exception as e:
        output_collector.add_output('error', f'Leaflow: 失败 - {e}')
        output_collector.finish_task(False, f"Leaflow签到任务失败: {e}")
        return False, f'Leaflow: 失败 - {e}\n{traceback.format_exc()}'


def main(debug: bool = False) -> int:
    """主函数"""
    global browser_manager
    
    show_banner()
    
    # 根据操作系统和debug参数决定是否无头
    actual_debug = _determine_debug_mode(debug)
    
    # 初始化全局浏览器管理器
    logger.info("🌐 初始化全局浏览器管理器...")
    browser_manager = GlobalBrowserManager(debug=actual_debug)
    
    if not browser_manager.get_browser():
        logger.warning("❌ 全局浏览器启动失败，无法继续执行任务")
        return 1
    
    try:
        # 执行任务
        return _execute_tasks()
    finally:
        # 清理全局浏览器
        if browser_manager:
            browser_manager.cleanup()


def _determine_debug_mode(debug: bool) -> bool:
    """确定实际的debug模式"""
    if os.name == 'posix':
        # Linux/macOS: 始终无头模式
        logger.info("🐧 Linux环境：强制使用无头模式")
        return False
    else:
        # Windows: 根据debug参数决定
        logger.info(f"🪟 Windows环境：Debug模式 {'开启' if debug else '关闭'}")
        return debug


def _execute_tasks() -> int:
    """执行所有任务"""
    # 根据环境变量决定是否执行各任务
    tasks: List[Tuple[str, Callable[[], Tuple[bool, str]], bool]] = [
        ("Rainyun", run_rainyun, bool(os.getenv('RAINYUN_USERNAME') and os.getenv('RAINYUN_PASSWORD'))),
        ("iKuuu", run_ikuuu, bool(os.getenv('IKUUU_USERNAME') and os.getenv('IKUUU_PASSWORD'))),
        ("Leaflow", run_leaflow, bool(os.getenv('LEAFLOW_COOKIE'))),
    ]

    lines: List[str] = []
    all_success = True

    for name, fn, enabled in tasks:
        if not enabled:
            lines.append(f'⏭️ 跳过 {name}: 未配置所需环境变量')
            continue
        ok, msg = fn()
        prefix = '✅' if ok else '❌'
        lines.append(f'{prefix} {msg}')
        if not ok:
            all_success = False

    # 发送推送通知
    _send_notification(lines)
    
    logger.info('\n'.join(lines))
    return 0 if all_success else 1


def _send_notification(lines: List[str]) -> None:
    """发送推送通知"""
    summary_title = '🚀 AutoTasks 自动任务执行结果'
    summary_body = output_collector.get_formatted_output()

    sendkey = os.getenv('SENDKEY', '').strip()
    if sendkey:
        try:
            sc_send(sendkey, summary_title, summary_body)
            logger.info("📤 Server酱推送成功")
        except Exception as e:
            # 推送失败不影响退出码
            logger.warning(f"⚠️ Server酱推送失败: {e}")
            lines.append('⚠️ Server酱推送失败')
    else:
        logger.info("⚠️ 未配置 SENDKEY，跳过推送")
        lines.append('⚠️ 未配置 SENDKEY，跳过推送')


if __name__ == '__main__':
    os.environ['RAINYUN_USERNAME'] = 'Viper373'
    os.environ['RAINYUN_PASSWORD'] = 'ShadowZed666'
    os.environ['IKUUU_USERNAME'] = 'viper3731217@gmail.com'
    os.environ['IKUUU_PASSWORD'] = 'ShadowZed666'
    os.environ['LEAFLOW_COOKIE'] = '90838baa3b402e8f6b377a65e62fcf14'
    os.environ['CHROME_EXECUTABLE'] = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    
    # 在这里控制debug模式：True=有头模式(仅Windows)，False=无头模式
    raise SystemExit(main(debug=True))
