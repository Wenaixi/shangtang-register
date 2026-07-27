#!/usr/bin/env python3
"""
商汤自动注册工具 - GUI (tkinter)
精致的双栏布局: 左侧配置区, 右侧日志 + 结果区
"""

import json
import queue
import sys
import threading
import time
import traceback
from pathlib import Path
from tkinter import Tk, Toplevel, StringVar, IntVar, BooleanVar, messagebox, filedialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from sensenova.core.orchestrator import RegistrationOrchestrator
from sensenova.core.sms_client import SMSClient
from sensenova.utils.log import setup as setup_log
from sensenova.config import config as app_config


# ============================================================
# 样式常量
# ============================================================

COLORS = {
    "bg":           "#f5f6fa",
    "sidebar":      "#1e1e2e",
    "sidebar_text": "#cdd6f4",
    "sidebar_label":"#a6adc8",
    "card_bg":      "#ffffff",
    "accent":       "#6c5ce7",
    "accent_hover": "#5a4bd1",
    "success":      "#00b894",
    "danger":       "#e17055",
    "warning":      "#fdcb6e",
    "text":         "#2d3436",
    "text_muted":   "#636e72",
    "border":       "#e2e8f0",
    "input_bg":     "#f8f9fc",
    "log_bg":       "#1a1a2e",
    "log_fg":       "#00ff88",
}

FONT_FAMILY = "Microsoft YaHei UI" if sys.platform == "win32" else "Segoe UI"
MONO_FONT = ("Cascadia Code", 9) if sys.platform == "win32" else ("SF Mono", 10)


# ============================================================
# GUI Application
# ============================================================

class SenseNovaGUI:
    """商汤自动注册 GUI"""

    def __init__(self):
        self.root = Tk()
        self.root.title("SenseNova 商汤自动注册工具")
        self.root.geometry("1100x720")
        self.root.minsize(960, 600)
        self.root.configure(bg=COLORS["bg"])

        # 任务状态
        self._running = False
        self._stop_flag = threading.Event()
        self._msg_queue = queue.Queue()
        self._result_queue = queue.Queue()

        # 当前项目列表缓存
        self._projects_cache: list = []

        self._build_ui()
        self._poll_queue()
        self._load_config_to_ui()

    # ================================================================
    # UI Construction
    # ================================================================

    def _build_ui(self):
        """构建完整界面"""
        self._make_sidebar()
        self._make_main_area()
        self._make_statusbar()

    def _make_sidebar(self):
        """左侧配置面板"""
        sidebar = tkinter.Frame(self.root, bg=COLORS["sidebar"], width=320)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # 标题
        title = tkinter.Label(
            sidebar, text="SenseNova\nAuto Register",
            font=(FONT_FAMILY, 16, "bold"),
            fg=COLORS["accent"], bg=COLORS["sidebar"], justify="left",
        )
        title.pack(anchor="w", padx=20, pady=(20, 5))

        tkinter.Label(
            sidebar, text="商汤科技自动注册工具",
            font=(FONT_FAMILY, 9), fg=COLORS["sidebar_label"], bg=COLORS["sidebar"],
        ).pack(anchor="w", padx=20, pady=(0, 20))

        # 滚动区域
        canvas = tkinter.Canvas(sidebar, bg=COLORS["sidebar"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=canvas.yview)
        scroll_frame = tkinter.Frame(canvas, bg=COLORS["sidebar"])

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=300)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0))
        scrollbar.pack(side="right", fill="y")

        # --- 接码平台 ---
        self._section_label(scroll_frame, "接码平台")
        card = self._card(scroll_frame)
        self.sms_url_var = self._field(card, "API 地址", "SMS_BASE_URL")
        self.sms_token_var = self._field(card, "fcToken", "SMS_TOKEN", show="*")
        self.sms_project_var = self._field(card, "项目 ID", "SMS_PROJECT_ID")

        # 项目搜索按钮
        btn_frame = tkinter.Frame(card, bg=COLORS["card_bg"])
        btn_frame.pack(fill="x", padx=12, pady=(0, 8))
        self._btn(btn_frame, "搜索项目", self._search_project, width=14).pack(side="right")

        # 项目名 Label
        self.project_name_label = tkinter.Label(
            card, text="未选择项目", font=(FONT_FAMILY, 9),
            fg=COLORS["text_muted"], bg=COLORS["card_bg"], anchor="w",
        )
        self.project_name_label.pack(fill="x", padx=14, pady=(0, 8))

        # --- 代理 ---
        self._section_label(scroll_frame, "网络代理")
        card2 = self._card(scroll_frame)
        self.proxy_http_var = self._field(card2, "HTTP 代理", "HTTP_PROXY")
        self.proxy_https_var = self._field(card2, "HTTPS 代理", "HTTPS_PROXY")

        # --- 注册设置 ---
        self._section_label(scroll_frame, "注册设置")
        card3 = self._card(scroll_frame)
        self.ascription_var = self._field(card3, "卡号类型", "SMS_ASCRIPTION",
                                           placeholder="1=移动 2=联通 留空=不限")
        self.count_var = IntVar(value=1)
        self._field(card3, "注册数量", None, var=self.count_var)

        # --- 操作按钮 ---
        btn_area = tkinter.Frame(scroll_frame, bg=COLORS["sidebar"])
        btn_area.pack(fill="x", padx=10, pady=(15, 10))
        self.start_btn = tkinter.Button(
            btn_area, text="开始注册", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["accent"], fg="white", activebackground=COLORS["accent_hover"],
            activeforeground="white", relief="flat", cursor="hand2",
            padx=20, pady=8, border=0, command=self._start_register,
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = tkinter.Button(
            btn_area, text="停止", font=(FONT_FAMILY, 10),
            bg=COLORS["danger"], fg="white", relief="flat", cursor="hand2",
            padx=16, pady=8, border=0, command=self._stop_register, state="disabled",
        )
        self.stop_btn.pack(side="left")

        tkinter.Button(
            btn_area, text="保存配置", font=(FONT_FAMILY, 9),
            fg=COLORS["sidebar_text"], bg=COLORS["sidebar"],
            relief="flat", cursor="hand2", command=self._save_config,
        ).pack(side="right")

        # 让 sidebar 可滚
        self.root.bind("<MouseWheel>", lambda e: self._on_scroll(e, canvas))

    def _section_label(self, parent, text):
        tkinter.Label(
            parent, text=text,
            font=(FONT_FAMILY, 8, "bold"), fg=COLORS["sidebar_label"],
            bg=COLORS["sidebar"],
        ).pack(anchor="w", padx=20, pady=(14, 4))

    def _card(self, parent):
        f = tkinter.Frame(parent, bg=COLORS["card_bg"], highlightthickness=1,
                         highlightbackground=COLORS["border"], highlightcolor=COLORS["border"])
        f.pack(fill="x", padx=10, pady=(0, 2))
        return f

    def _field(self, parent, label, config_key=None, var=None, show=None, placeholder=""):
        row = tkinter.Frame(parent, bg=COLORS["card_bg"])
        row.pack(fill="x", padx=12, pady=(6, 0))
        tkinter.Label(
            row, text=label, font=(FONT_FAMILY, 8),
            fg=COLORS["text_muted"], bg=COLORS["card_bg"], width=9, anchor="w",
        ).pack(side="left")
        if var is None:
            var = StringVar()
        entry = tkinter.Entry(
            row, textvariable=var, font=(FONT_FAMILY, 9),
            bg=COLORS["input_bg"], relief="flat", highlightthickness=1,
            highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"],
        )
        if show:
            entry.configure(show=show)
        if placeholder and isinstance(var, StringVar) and not var.get():
            var.set(placeholder)
            entry.configure(fg=COLORS["text_muted"])
            entry.bind("<FocusIn>", lambda e: self._on_focus_in(var, entry, placeholder))
            entry.bind("<FocusOut>", lambda e: self._on_focus_out(var, entry, placeholder))
        entry.pack(fill="x", expand=True)
        if config_key:
            setattr(self, f"_cfg_{config_key}", var)
        return var

    def _btn(self, parent, text, command, width=10):
        return tkinter.Button(
            parent, text=text, font=(FONT_FAMILY, 9),
            bg=COLORS["accent"], fg="white", activebackground=COLORS["accent_hover"],
            activeforeground="white", relief="flat", cursor="hand2",
            padx=8, pady=2, border=0, command=command, width=width,
        )

    @staticmethod
    def _on_focus_in(var, entry, placeholder):
        if var.get() == placeholder:
            var.set("")
            entry.configure(fg="black")

    @staticmethod
    def _on_focus_out(var, entry, placeholder):
        if not var.get():
            var.set(placeholder)
            entry.configure(fg=COLORS["text_muted"])

    def _on_scroll(self, event, canvas):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ================================================================
    # Main Area
    # ================================================================

    def _make_main_area(self):
        main = tkinter.Frame(self.root, bg=COLORS["bg"])
        main.pack(side="left", fill="both", expand=True, padx=(0, 0))

        # 顶部进度条
        self.progress_frame = tkinter.Frame(main, bg=COLORS["bg"])
        self.progress_frame.pack(fill="x", padx=20, pady=(16, 0))

        self.step_label = tkinter.Label(
            self.progress_frame, text="就绪，等待开始...",
            font=(FONT_FAMILY, 11), fg=COLORS["text"], bg=COLORS["bg"],
        )
        self.step_label.pack(anchor="w")

        self.progress = ttk.Progressbar(
            self.progress_frame, mode="indeterminate", length=400,
        )

        # 日志区
        log_label = tkinter.Label(
            main, text="运行日志", font=(FONT_FAMILY, 9, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["bg"],
        )
        log_label.pack(anchor="w", padx=20, pady=(14, 4))

        log_frame = tkinter.Frame(main, bg=COLORS["log_bg"], highlightthickness=1,
                                 highlightbackground=COLORS["border"])
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        self.log_text = tkinter.Text(
            log_frame, font=MONO_FONT, bg=COLORS["log_bg"], fg=COLORS["log_fg"],
            relief="flat", wrap="word", padx=10, pady=8,
            insertbackground=COLORS["log_fg"],
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        # 配置 tag 样式
        self.log_text.tag_configure("info", foreground="#00cec9")
        self.log_text.tag_configure("success", foreground="#00b894")
        self.log_text.tag_configure("error", foreground="#e17055")
        self.log_text.tag_configure("warning", foreground="#fdcb6e")
        self.log_text.tag_configure("step", foreground="#a29bfe", font=(MONO_FONT[0], MONO_FONT[1], "bold"))

        # 结果区
        result_label = tkinter.Label(
            main, text="注册结果", font=(FONT_FAMILY, 9, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["bg"],
        )
        result_label.pack(anchor="w", padx=20, pady=(4, 4))

        tree_frame = tkinter.Frame(main, bg=COLORS["card_bg"], highlightthickness=1,
                                  highlightbackground=COLORS["border"])
        tree_frame.pack(fill="x", padx=20, pady=(0, 16))

        columns = ("username", "password", "phone", "api_key", "time")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=5,
        )
        self.tree.heading("username", text="用户名")
        self.tree.heading("password", text="密码")
        self.tree.heading("phone", text="手机号")
        self.tree.heading("api_key", text="API Key")
        self.tree.heading("time", text="时间")
        self.tree.column("username", width=140)
        self.tree.column("password", width=140)
        self.tree.column("phone", width=120)
        self.tree.column("api_key", width=280)
        self.tree.column("time", width=140)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # 结果操作按钮
        btn_row = tkinter.Frame(main, bg=COLORS["bg"])
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        self._btn(btn_row, "复制 API Key", self._copy_api_key, width=14).pack(side="left", padx=(0, 8))
        self._btn(btn_row, "导出 JSON", self._export_results, width=14).pack(side="left", padx=(0, 8))
        self._btn(btn_row, "清空日志", self._clear_log, width=10).pack(side="right")

    def _make_statusbar(self):
        bar = tkinter.Frame(self.root, bg=COLORS["sidebar"], height=28)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)
        self.status_var = StringVar(value="就绪")
        tkinter.Label(
            bar, textvariable=self.status_var, font=(FONT_FAMILY, 8),
            fg=COLORS["sidebar_label"], bg=COLORS["sidebar"],
        ).pack(side="left", padx=14)
        self.stat_count = StringVar(value="成功: 0 | 失败: 0")
        tkinter.Label(
            bar, textvariable=self.stat_count, font=(FONT_FAMILY, 8),
            fg=COLORS["sidebar_label"], bg=COLORS["sidebar"],
        ).pack(side="right", padx=14)

    # ================================================================
    # Logic
    # ================================================================

    def _load_config_to_ui(self):
        """.env -> UI"""
        self._cfg_SMS_BASE_URL.set(app_config.SMS_BASE_URL)
        self._cfg_SMS_TOKEN.set(app_config.SMS_TOKEN)
        self._cfg_SMS_PROJECT_ID.set(app_config.SMS_PROJECT_ID)
        self._cfg_HTTP_PROXY.set(app_config.HTTP_PROXY)
        self._cfg_HTTPS_PROXY.set(app_config.HTTPS_PROXY)
        self._cfg_SMS_ASCRIPTION.set(app_config.SMS_ASCRIPTION)
        self.count_var.set(app_config.REGISTER_COUNT)

    def _ui_to_config(self):
        """UI -> .env"""
        app_config.SMS_BASE_URL = self._cfg_SMS_BASE_URL.get().strip()
        app_config.SMS_TOKEN = self._cfg_SMS_TOKEN.get().strip()
        app_config.SMS_PROJECT_ID = self._cfg_SMS_PROJECT_ID.get().strip()
        app_config.HTTP_PROXY = self._cfg_HTTP_PROXY.get().strip()
        app_config.HTTPS_PROXY = self._cfg_HTTPS_PROXY.get().strip()
        app_config.SMS_ASCRIPTION = self._cfg_SMS_ASCRIPTION.get().strip()
        app_config.REGISTER_COUNT = self.count_var.get()

    def _save_config(self):
        self._ui_to_config()
        app_config.save_to_file()
        self._log("配置已保存到 .env", "success")
        self.status_var.set("配置已保存")

    def _search_project(self):
        """搜索接码平台项目"""
        self._ui_to_config()
        url = app_config.SMS_BASE_URL
        token = app_config.SMS_TOKEN
        if not url or not token:
            messagebox.showwarning("提示", "请先填写 API 地址和 fcToken")
            return

        dialog = Toplevel(self.root)
        dialog.title("搜索项目")
        dialog.geometry("500x400")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        tkinter.Label(
            dialog, text="搜索接码平台项目", font=(FONT_FAMILY, 12, "bold"),
            fg=COLORS["text"], bg=COLORS["bg"],
        ).pack(padx=20, pady=(16, 4))

        search_frame = tkinter.Frame(dialog, bg=COLORS["bg"])
        search_frame.pack(fill="x", padx=20, pady=(0, 8))
        tkinter.Label(
            search_frame, text="关键词:", font=(FONT_FAMILY, 9),
            bg=COLORS["bg"],
        ).pack(side="left")
        search_var = StringVar(value="商汤")
        tkinter.Entry(
            search_frame, textvariable=search_var, font=(FONT_FAMILY, 10),
            relief="flat", highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"], width=20,
        ).pack(side="left", padx=(8, 8))
        tkinter.Button(
            search_frame, text="搜索", font=(FONT_FAMILY, 9),
            bg=COLORS["accent"], fg="white", relief="flat", cursor="hand2",
            command=lambda: self._do_search(search_var.get(), tree),
        ).pack(side="left")

        # 结果列表
        tree_frame = tkinter.Frame(dialog, bg=COLORS["card_bg"], highlightthickness=1,
                                  highlightbackground=COLORS["border"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        columns = ("id", "name", "price")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)
        tree.heading("id", text="ID")
        tree.heading("name", text="项目名")
        tree.heading("price", text="价格")
        tree.column("id", width=80)
        tree.column("name", width=280)
        tree.column("price", width=60)
        tree.pack(side="left", fill="both", expand=True)
        ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview).pack(side="right", fill="y")
        tree.configure(yscrollcommand=tkinter.Scrollbar(tree_frame, orient="vertical").set)

        # 选择按钮
        def select():
            sel = tree.selection()
            if sel:
                item = tree.item(sel[0])
                vals = item["values"]
                self._cfg_SMS_PROJECT_ID.set(str(vals[0]))
                self.project_name_label.configure(text=f"{vals[1]} (ID={vals[0]})")
                self._save_config()
                dialog.destroy()
                self._log(f"已选择项目: {vals[1]} (ID={vals[0]})", "success")

        self._btn(dialog, "选择此项目", select, width=14).pack(pady=(0, 16))

        # 初始搜索
        self._do_search("商汤", tree)

    def _do_search(self, keyword, tree):
        """执行项目搜索"""
        tree.delete(*tree.get_children())
        try:
            proxies = app_config.proxies or None
            import requests
            s = requests.Session()
            s.headers.update({
                "fcToken": app_config.SMS_TOKEN,
                "User-Agent": "Mozilla/5.0",
            })
            params = {"page": 1, "pagesize": 50}
            if len(keyword) >= 3:
                params["project_name"] = keyword
            resp = s.get(
                f"{app_config.SMS_BASE_URL}/api/user/projects",
                params=params, proxies=proxies, timeout=15,
            )
            data = resp.json()
            if data.get("code") == 1:
                projects = data.get("data", [])
                for p in projects:
                    tree.insert("", "end", values=(p["id"], p["project_name"], p.get("money", "?")))
                self._log(f"找到 {len(projects)} 个项目", "info")
            else:
                self._log(f"搜索失败: {data.get('msg')}", "error")
        except Exception as e:
            self._log(f"搜索异常: {e}", "error")

    def _start_register(self):
        if self._running:
            return
        self._ui_to_config()
        app_config.save_to_file()

        if not app_config.SMS_PROJECT_ID:
            messagebox.showwarning("提示", "请先选择项目")
            return

        self._running = True
        self._stop_flag.clear()
        self._success = 0
        self._fail = 0

        self.start_btn.configure(state="disabled", text="运行中...")
        self.stop_btn.configure(state="normal")
        self.progress.pack(fill="x", pady=(4, 0))
        self.progress.start(8)
        self.step_label.configure(text="正在启动...")
        self.tree.delete(*self.tree.get_children())
        self._clear_log()

        thread = threading.Thread(target=self._register_worker, daemon=True)
        thread.start()

    def _stop_register(self):
        self._stop_flag.set()
        self.status_var.set("正在停止...")
        self._log("用户请求停止", "warning")

    def _register_worker(self):
        """后台注册线程"""
        try:
            proxies = app_config.proxies or None

            sms = SMSClient(
                base_url=app_config.SMS_BASE_URL,
                token=app_config.SMS_TOKEN,
                project_id=app_config.SMS_PROJECT_ID,
                ascription=app_config.SMS_ASCRIPTION,
                proxies=proxies,
            )

            orch = RegistrationOrchestrator(sms)
            orch.on_event = lambda evt, msg: self._msg_queue.put(("event", evt, msg))

            total = app_config.REGISTER_COUNT
            for i in range(total):
                if self._stop_flag.is_set():
                    self._msg_queue.put(("log", "warning", "用户停止"))
                    break

                self._msg_queue.put(("status", f"第 {i+1}/{total} 次注册"))
                self._msg_queue.put(("step", f"开始第 {i+1} 次注册 ({i+1}/{total})"))

                try:
                    result = orch.run()
                    if result:
                        self._success += 1
                        self._msg_queue.put(("result", result))
                        self._msg_queue.put(("log", "success",
                            f"--- 第 {i+1} 次成功: {result['username']} | {result['api_key'][:25]}..."))
                    else:
                        self._fail += 1
                        self._msg_queue.put(("log", "error", f"--- 第 {i+1} 次失败"))
                except Exception as e:
                    self._fail += 1
                    self._msg_queue.put(("log", "error", f"第 {i+1} 次异常: {e}"))

                if i < total - 1 and not self._stop_flag.is_set():
                    time.sleep(3)

        except Exception as e:
            self._msg_queue.put(("log", "error", f"致命错误: {e}\n{traceback.format_exc()}"))
        finally:
            self._msg_queue.put(("done", f"完成: 成功 {self._success} | 失败 {self._fail}"))

    def _poll_queue(self):
        """轮询消息队列，更新 UI"""
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                typ = msg[0]
                if typ == "log":
                    self._log(msg[2], msg[1])
                elif typ == "step":
                    self.step_label.configure(text=msg[1])
                elif typ == "status":
                    self.status_var.set(msg[1])
                elif typ == "event":
                    _, evt, text = msg
                    tag = {"step": "step", "done": "success", "info": "info"}.get(evt, "info")
                    self._log(text, tag)
                elif typ == "result":
                    r = msg[1]
                    self.tree.insert("", "end", values=(
                        r["username"], r["password"], r["phone"],
                        r["api_key"], r["create_time"],
                    ))
                    # 滚动到底部
                    self.tree.yview_moveto(1)
                elif typ == "done":
                    self._running = False
                    self.progress.stop()
                    self.progress.pack_forget()
                    self.start_btn.configure(state="normal", text="开始注册")
                    self.stop_btn.configure(state="disabled")
                    self.step_label.configure(text=msg[1])
                    self.status_var.set(msg[1])
                    self.stat_count.set(f"成功: {self._success} | 失败: {self._fail}")
                    self._log(msg[1], "success")
        except queue.Empty:
            pass

        self.root.after(100, self._poll_queue)

    def _log(self, text, tag="info"):
        self.log_text.insert("end", f"{text}\n", tag)
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.delete("1.0", "end")

    def _copy_api_key(self):
        sel = self.tree.selection()
        if sel:
            api_key = self.tree.item(sel[0])["values"][3]
            self.root.clipboard_clear()
            self.root.clipboard_append(api_key)
            self.status_var.set(f"已复制: {api_key[:20]}...")

    def _export_results(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showinfo("提示", "暂无结果可导出")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="accounts.json",
        )
        if not path:
            return
        results = []
        for item in items:
            vals = self.tree.item(item)["values"]
            results.append({
                "username": vals[0], "password": vals[1],
                "phone": vals[2], "api_key": vals[3], "time": vals[4],
            })
        Path(path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        self._log(f"已导出 {len(results)} 条结果到 {path}", "success")

    # ================================================================
    # Run
    # ================================================================

    def run(self):
        self.root.mainloop()


# ================================================================
# Entry Point
# ================================================================

def main():
    # 初始化日志
    setup_log()
    app = SenseNovaGUI()
    app.run()


if __name__ == "__main__":
    main()
