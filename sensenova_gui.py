#!/usr/bin/env python3
"""SenseNova Auto Register — 纯黑白极简 GUI"""

import json
import queue
import sys
import threading
import time
import tkinter
import traceback
from pathlib import Path
from tkinter import Tk, Toplevel, StringVar, IntVar, messagebox, filedialog
from tkinter import ttk

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from sensenova.core.orchestrator import RegistrationOrchestrator
from sensenova.core.sms_client import SMSClient
from sensenova.utils.log import setup as setup_log
from sensenova.config import config as app_config

C = {
    "bg": "#080808", "panel": "#0e0e0e", "card": "#131313",
    "accent": "#ffffff", "accent2": "#d4d4d4", "text": "#e0e0e0",
    "muted": "#707070", "faint": "#404040", "border": "#262626",
    "hover": "#1c1c1c", "input_bg": "#111111", "input_border": "#333333",
    "log_bg": "#060606",
}
FONT = "Microsoft YaHei UI" if sys.platform == "win32" else "Segoe UI"
MONO = ("Cascadia Mono", 9) if sys.platform == "win32" else ("SF Mono", 10)


class SenseNovaGUI:

    def __init__(self):
        self.root = Tk()
        self.root.title("SenseNova")
        self.root.geometry("1080x700")
        self.root.minsize(920, 560)
        self.root.configure(bg=C["bg"])
        self._running = False
        self._stop_flag = threading.Event()
        self._msg_queue = queue.Queue()
        self._success = 0; self._fail = 0
        self._data_dir = PROJECT_ROOT / "data"
        self._build(); self._poll(); self._load(); self._load_results()

    # ================================================================
    def _build(self):
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self._sidebar(); self._main(); self._statusbar()

    def _sidebar(self):
        w = 292
        sb = tkinter.Frame(self.root, bg=C["panel"], width=w, height=700)
        sb.grid(row=0, column=0, sticky="ns"); sb.grid_propagate(False)
        h = tkinter.Frame(sb, bg=C["panel"]); h.pack(fill="x", padx=20, pady=(22,0))
        tkinter.Label(h, text="SenseNova", font=(FONT,15,"bold"),
            fg=C["accent"], bg=C["panel"]).pack(anchor="w")
        tkinter.Label(h, text="Auto Register", font=(FONT,10),
            fg=C["muted"], bg=C["panel"]).pack(anchor="w")
        tkinter.Frame(sb, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(14,10))
        cv = tkinter.Canvas(sb, bg=C["panel"], highlightthickness=0)
        sf = tkinter.Frame(cv, bg=C["panel"])
        sf.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=sf, anchor="nw", width=w-2)
        cv.pack(side="left", fill="both", expand=True)
        # --- SMS ---
        self._sec(sf, "SMS")
        c1 = self._card(sf)
        self._inp(c1,"URL","SMS_BASE_URL"); self._inp(c1,"Token","SMS_TOKEN",secret=True)
        self._inp(c1,"PID","SMS_PROJECT_ID")
        r1 = tkinter.Frame(c1, bg=C["card"]); r1.pack(fill="x", padx=14, pady=(2,8))
        self.pname_lbl = tkinter.Label(r1, text=" No project", font=(FONT,8),
            fg=C["faint"], bg=C["card"], anchor="w"); self.pname_lbl.pack(side="left")
        self._btns(c1,r1,"Search",self._search_project).pack(side="right")
        # --- Proxy ---
        self._sec(sf,"Proxy"); c2 = self._card(sf)
        self._inp(c2,"HTTP","HTTP_PROXY"); self._inp(c2,"HTTPS","HTTPS_PROXY")
        # --- Register ---
        self._sec(sf,"Register"); c3 = self._card(sf)
        self._inp(c3,"Ascription","SMS_ASCRIPTION",ph="1=mobile 2=unicom")
        self._inp(c3,"Paragraph","SMS_PARAGRAPH",ph="e.g. 170")
        self.count_var = IntVar(value=1); self._inp(c3,"Count",None,var=self.count_var)
        # --- Actions ---
        a = tkinter.Frame(sf, bg=C["panel"]); a.pack(fill="x", padx=20, pady=(18,14))
        self.start_btn = tkinter.Button(a, text="Start", font=(FONT,10,"bold"),
            bg=C["accent"], fg="#000", activebackground=C["accent2"],
            activeforeground="#000", relief="flat", cursor="hand2",
            padx=24, pady=7, border=0, command=self._start); self.start_btn.pack(side="left")
        self.stop_btn = tkinter.Button(a, text="Stop", font=(FONT,10),
            bg=C["card"], fg=C["text"], activebackground=C["hover"],
            relief="flat", cursor="hand2", padx=20, pady=7, border=0,
            command=self._stop, state="disabled"); self.stop_btn.pack(side="left", padx=(8,0))
        tkinter.Button(a, text="Save", font=(FONT,9), fg=C["muted"], bg=C["panel"],
            activeforeground=C["accent"], relief="flat", cursor="hand2", border=0,
            command=self._save).pack(side="right")
        self.root.bind("<MouseWheel>", lambda e: self._scroll(e, cv))

    def _sec(self,p,t):
        tkinter.Label(p, text=t, font=(FONT,8,"bold"),
            fg=C["muted"], bg=C["panel"]).pack(anchor="w", padx=20, pady=(16,5))
    def _card(self,p):
        f = tkinter.Frame(p, bg=C["card"]); f.pack(fill="x", padx=14, pady=(0,4)); return f

    def _inp(self,p,label, key=None, var=None, secret=False, ph=""):
        r = tkinter.Frame(p, bg=C["card"]); r.pack(fill="x", padx=14, pady=(7,0))
        tkinter.Label(r, text=label, font=(FONT,8), fg=C["muted"], bg=C["card"],
            width=9, anchor="w").pack(side="left")
        if var is None: var = StringVar()
        e = tkinter.Entry(r, textvariable=var, font=(FONT,9), bg=C["input_bg"],
            fg=C["text"], insertbackground=C["accent"], relief="flat",
            highlightthickness=1, highlightbackground=C["input_border"],
            highlightcolor=C["accent2"])
        if secret: e.configure(show="*")
        e.pack(fill="x", expand=True)
        if key: setattr(self, f"_k_{key}", var)
        if ph and isinstance(var, StringVar) and not var.get():
            var.set(ph); e.configure(fg=C["faint"])
            e.bind("<FocusIn>",  lambda ev, v=var, en=e: self._phi(v,en,ph))
            e.bind("<FocusOut>", lambda ev, v=var, en=e: self._pho(v,en,ph))
        return var

    @staticmethod
    def _phi(v,e,ph):
        if v.get() == ph: v.set(""); e.configure(fg=C["text"])
    @staticmethod
    def _pho(v,e,ph):
        if not v.get(): v.set(ph); e.configure(fg=C["faint"])
    def _btns(self,p,r,t,cmd):
        return tkinter.Button(r, text=t, font=(FONT,8), bg=C["card"],
            fg=C["muted"], activeforeground=C["accent"], relief="flat",
            cursor="hand2", border=0, command=cmd, padx=10, pady=1)
    def _scroll(self,e,cv):
        cv.yview_scroll(int(-1*(e.delta/120)),"units")

    # ================================================================
    def _main(self):
        m = tkinter.Frame(self.root, bg=C["bg"])
        m.grid(row=0, column=1, sticky="nsew")
        m.grid_columnconfigure(0, weight=1); m.grid_rowconfigure(1, weight=1)

        self.step_lbl = tkinter.Label(m, text="Ready", font=(FONT,10),
            fg=C["muted"], bg=C["bg"], anchor="w")
        self.step_lbl.grid(row=0, column=0, sticky="ew", padx=24, pady=(18,10))
        self.progress = ttk.Progressbar(m, mode="indeterminate", length=300)

        tkinter.Label(m, text="Log", font=(FONT,8,"bold"),
            fg=C["muted"], bg=C["bg"]).grid(row=0, column=0, sticky="e",
            padx=(0,24), pady=(18,0))

        lf = tkinter.Frame(m, bg=C["log_bg"])
        lf.grid(row=1, column=0, sticky="nsew", padx=24, pady=(2,6))
        self.log = tkinter.Text(lf, font=MONO, bg=C["log_bg"], fg=C["muted"],
            relief="flat", wrap="word", padx=12, pady=10,
            insertbackground=C["accent"], border=0, highlightthickness=0)
        self.log.pack(side="left", fill="both", expand=True)
        sb = tkinter.Scrollbar(lf, bg=C["bg"], troughcolor=C["bg"],
            activebackground=C["muted"], border=0)
        sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set); sb.configure(command=self.log.yview)
        for tag, fg in [("s","#fff"),("e","#666"),("m","#888"),("w","#555")]:
            self.log.tag_configure(tag, foreground=fg)

        tkinter.Label(m, text="Results", font=(FONT,8,"bold"),
            fg=C["muted"], bg=C["bg"]).grid(row=2, column=0, sticky="w",
            padx=24, pady=(4,3))

        cols = ("u","p","ph","key","t")
        self.tree = ttk.Treeview(m, columns=cols, show="headings", height=4)
        for c,t in zip(cols,["Username","Password","Phone","API Key","Time"]):
            self.tree.heading(c, text=t)
        for c,w in zip(cols, [130,130,110,260,140]): self.tree.column(c, width=w)
        style = ttk.Style(); style.theme_use("clam")
        style.configure("Treeview", background=C["card"], foreground=C["text"],
            fieldbackground=C["card"], borderwidth=0, font=(FONT,8))
        style.configure("Treeview.Heading", background=C["panel"],
            foreground=C["muted"], relief="flat", borderwidth=1,
            font=(FONT,8,"bold"), padding=(6,3))
        style.map("Treeview", background=[("selected", C["hover"])])
        style.map("Treeview.Heading", background=[("active", C["panel"])])
        self.tree.grid(row=3, column=0, sticky="ew", padx=24, pady=(0,6))

        ar = tkinter.Frame(m, bg=C["bg"])
        ar.grid(row=4, column=0, sticky="ew", padx=24, pady=(0,18))
        self._btn(ar,"Copy Key", self._copy_key).pack(side="left", padx=(0,6))
        self._btn(ar,"Copy All", self._copy_all).pack(side="left", padx=(0,6))
        self._btn(ar,"Delete",   self._delete).pack(side="left", padx=(0,6))
        self._btn(ar,"Refresh",  self._reload).pack(side="left", padx=(0,6))
        self._btn(ar,"Export",   self._export).pack(side="left")
        self._btn(ar,"Clear Log",self._clear_log).pack(side="right")

    def _btn(self,p,t,cmd):
        return tkinter.Button(p, text=t, font=(FONT,9), bg=C["card"],
            fg=C["text"], activeforeground=C["accent"], activebackground=C["hover"],
            relief="flat", cursor="hand2", border=0, padx=14, pady=4, command=cmd)

    def _statusbar(self):
        b = tkinter.Frame(self.root, bg=C["panel"], height=26)
        b.grid(row=1, column=0, columnspan=2, sticky="ew"); b.grid_propagate(False)
        self.stat_text = StringVar(value="Idle")
        tkinter.Label(b, textvariable=self.stat_text,
            font=(FONT,8), fg=C["muted"], bg=C["panel"]).pack(side="left", padx=16)
        self.stat_count = StringVar(value="Records: 0")
        tkinter.Label(b, textvariable=self.stat_count,
            font=(FONT,8), fg=C["muted"], bg=C["panel"]).pack(side="right", padx=16)

    # ================================================================
    def _load(self):
        self._k_SMS_BASE_URL.set(app_config.SMS_BASE_URL)
        self._k_SMS_TOKEN.set(app_config.SMS_TOKEN)
        self._k_SMS_PROJECT_ID.set(app_config.SMS_PROJECT_ID)
        self._k_HTTP_PROXY.set(app_config.HTTP_PROXY)
        self._k_HTTPS_PROXY.set(app_config.HTTPS_PROXY)
        self._k_SMS_ASCRIPTION.set(app_config.SMS_ASCRIPTION)
        self._k_SMS_PARAGRAPH.set(app_config.SMS_PARAGRAPH)
        self.count_var.set(app_config.REGISTER_COUNT)

    def _sync(self):
        app_config.SMS_BASE_URL    = self._k_SMS_BASE_URL.get().strip()
        app_config.SMS_TOKEN       = self._k_SMS_TOKEN.get().strip()
        app_config.SMS_PROJECT_ID  = self._k_SMS_PROJECT_ID.get().strip()
        app_config.HTTP_PROXY      = self._k_HTTP_PROXY.get().strip()
        app_config.HTTPS_PROXY     = self._k_HTTPS_PROXY.get().strip()
        app_config.SMS_ASCRIPTION  = self._k_SMS_ASCRIPTION.get().strip()
        app_config.SMS_PARAGRAPH   = self._k_SMS_PARAGRAPH.get().strip()
        app_config.REGISTER_COUNT  = self.count_var.get()

        # 清除 placeholder 值 (不能把 "1=mobile 2=unicom" 当真实值写入)
        for attr, ph in [("SMS_ASCRIPTION", "1=mobile 2=unicom"), ("SMS_PARAGRAPH", "e.g. 170")]:
            if getattr(app_config, attr, "") == ph:
                setattr(app_config, attr, "")

    def _save(self):
        self._sync(); app_config.save_to_file(); self._put("s","config saved")

    # ================================================================
    # Results: 每个账号存为独立 JSON: data/shangtang-{username}.json
    # ================================================================
    def _load_results(self):
        """从磁盘扫描所有 shangtang-*.json 并重建树 (保留已有行中不在磁盘的)"""
        if not self._data_dir.exists():
            return
        # 现有树中所有用户名
        tree_users = {self.tree.item(it)["values"][0] for it in self.tree.get_children()}
        # 磁盘中所有用户名
        disk_users = set()
        disk_data = {}
        for f in sorted(self._data_dir.glob("shangtang-*.json")):
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                u = r.get("username", "")
                if u:
                    disk_users.add(u)
                    disk_data[u] = (u, r.get("password",""), r.get("phone",""),
                                    r.get("api_key",""), r.get("create_time",""))
            except Exception:
                pass
        # 删除树中在磁盘已不存在的行
        for it in self.tree.get_children():
            if self.tree.item(it)["values"][0] not in disk_users:
                self.tree.delete(it)
        # 添加磁盘中有但树中没有的
        added = 0
        for u in sorted(disk_users):
            if u not in tree_users:
                self.tree.insert("", "end", values=disk_data[u])
                added += 1
        if added:
            self._put("m", f"loaded {added} new account(s)")
        self.stat_count.set(f"Records: {len(self.tree.get_children())}")

    def _tree_rows(self) -> list[dict]:
        """从树中提取完整字段, 保留磁盘上已有的额外字段 (不丢失 token 等)"""
        rows = []
        for it in self.tree.get_children():
            v = self.tree.item(it)["values"]
            uname = v[0]
            # 尝试从磁盘读取已有完整数据
            disk = {}
            try:
                p = self._data_dir / f"shangtang-{uname}.json"
                if p.exists():
                    disk = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
            # 合并: 磁盘数据为基础, 树中可见字段覆盖
            row = {
                "platform": disk.get("platform", "商汤科技"),
                "username": uname,
                "password": v[1],
                "tenant_code": disk.get("tenant_code", uname),
                "user_id": disk.get("user_id", ""),
                "phone": v[2],
                "access_token": disk.get("access_token", ""),
                "refresh_token": disk.get("refresh_token", ""),
                "api_key": v[3],
                "api_key_name": disk.get("api_key_name", ""),
                "create_time": v[4],
            }
            rows.append(row)
        return rows

    def _flush(self):
        """写回独立 JSON 文件 (只写不删)"""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        for r in self._tree_rows():
            p = self._data_dir / f"shangtang-{r['username']}.json"
            p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stat_count.set(f"Records: {len(self.tree.get_children())}")

    def _copy_key(self):
        s = self.tree.selection()
        if s:
            k = self.tree.item(s[0])["values"][3]
            self.root.clipboard_clear(); self.root.clipboard_append(k)
            self.stat_text.set(f"copied: {k[:25]}...")

    def _copy_all(self):
        items = self.tree.get_children()
        if not items: self.stat_text.set("nothing to copy"); return
        txt = "\n".join(self.tree.item(i)["values"][3] for i in items)
        self.root.clipboard_clear(); self.root.clipboard_append(txt)
        self._put("s", f"copied {len(items)} keys")
        self.stat_text.set(f"copied {len(items)} keys")

    def _delete(self):
        sels = self.tree.selection()
        if not sels: self.stat_text.set("select a row first"); return
        for it in sels:
            v = self.tree.item(it)["values"]
            self._put("m", f"deleted: {v[0]}")
            p = self._data_dir / f"shangtang-{v[0]}.json"
            try: p.unlink()
            except Exception: pass
            self.tree.delete(it)
        self.stat_count.set(f"Records: {len(self.tree.get_children())}")
        self.stat_text.set(f"deleted {len(sels)} row(s)")

    def _reload(self):
        """重新从磁盘扫描, 只合并新账号, 不删除树中已有行"""
        self._load_results()
        self._put("s", "reloaded from disk")

    def _export(self):
        items = self.tree.get_children()
        if not items: messagebox.showinfo("","no results"); return
        p = filedialog.asksaveasfilename(defaultextension=".json",
            filetypes=[("JSON","*.json")], initialfile="shangtang-export.json")
        if not p: return
        Path(p).write_text(json.dumps(self._tree_rows(),
            ensure_ascii=False, indent=2), encoding="utf-8")
        self._put("s", f"exported {len(items)} to {p}")

    # ================================================================
    def _search_project(self):
        self._sync()
        if not app_config.SMS_BASE_URL or not app_config.SMS_TOKEN:
            messagebox.showwarning("","fill api url and token first"); return
        d = Toplevel(self.root); d.title("Projects"); d.geometry("480x380")
        d.configure(bg=C["bg"]); d.transient(self.root); d.grab_set()
        tkinter.Label(d, text="Search projects", font=(FONT,11,"bold"),
            fg=C["accent"], bg=C["bg"]).pack(padx=20, pady=(16,6))
        sf = tkinter.Frame(d, bg=C["bg"]); sf.pack(fill="x", padx=20, pady=(0,8))
        qv = StringVar(value="商汤")
        tkinter.Entry(sf, textvariable=qv, font=(FONT,10), bg=C["input_bg"],
            fg=C["text"], insertbackground=C["accent"], relief="flat",
            highlightthickness=1, highlightbackground=C["input_border"],
            highlightcolor=C["accent2"], width=18).pack(side="left", padx=(0,8))
        tkinter.Button(sf, text="Search", font=(FONT,9), bg=C["accent"],
            fg="#000", relief="flat", cursor="hand2", border=0, padx=14, pady=3,
            command=lambda: self._do_search(qv.get(), tree)).pack(side="left")
        tf = tkinter.Frame(d, bg=C["card"])
        tf.pack(fill="both", expand=True, padx=20, pady=(0,8))
        tree = ttk.Treeview(tf, columns=("id","n","p"), show="headings", height=10)
        tree.heading("id",text="ID"); tree.column("id",width=60)
        tree.heading("n",text="Name"); tree.column("n",width=300)
        tree.heading("p",text="$"); tree.column("p",width=40)
        tree.pack(side="left", fill="both", expand=True)
        def select():
            s = tree.selection()
            if s:
                v = tree.item(s[0])["values"]
                self._k_SMS_PROJECT_ID.set(str(v[0]))
                self.pname_lbl.configure(text=f" {v[1]}"); self._save()
                d.destroy(); self._put("s", f"selected: {v[1]}")
        tkinter.Button(d, text="Select", font=(FONT,9), bg=C["accent"],
            fg="#000", relief="flat", cursor="hand2", border=0, padx=16,
            pady=4, command=select).pack(pady=(0,16))
        self._do_search("商汤", tree)

    def _do_search(self, kw, tree):
        tree.delete(*tree.get_children())
        try:
            import requests
            s = requests.Session()
            s.headers.update({"fcToken": app_config.SMS_TOKEN, "User-Agent": "Mozilla/5.0"})
            p = {"page": 1, "pagesize": 50}
            if len(kw) >= 3: p["project_name"] = kw
            r = s.get(f"{app_config.SMS_BASE_URL}/api/user/projects",
                params=p, proxies=app_config.proxies or None, timeout=15)
            d = r.json()
            if d.get("code") == 1:
                for x in d.get("data", []):
                    tree.insert("","end",values=(x["id"],x["project_name"],x.get("money","?")))
                self._put("m", f"found {len(d['data'])} projects")
            else: self._put("e", f"search failed: {d.get('msg')}")
        except Exception as e: self._put("e", str(e))

    # ================================================================
    def _start(self):
        if self._running: return
        self._sync(); app_config.save_to_file()
        if not app_config.SMS_PROJECT_ID:
            messagebox.showwarning("","select project first"); return
        self._running = True; self._stop_flag.clear()
        self._success = 0; self._fail = 0
        self.start_btn.configure(state="disabled", text="Running")
        self.stop_btn.configure(state="normal")
        self.progress.grid(row=0, column=0, sticky="ew", padx=24)
        self.progress.start(8)
        self.step_lbl.configure(text="Starting...")
        self._clear_log()
        self._msg_queue.put(("S", "Starting..."))
        threading.Thread(target=self._worker, daemon=True).start()

    def _stop(self):
        self._stop_flag.set(); self._put("w","stopping...")

    def _worker(self):
        try:
            px = app_config.proxies or None
            sms = SMSClient(
                base_url=app_config.SMS_BASE_URL, token=app_config.SMS_TOKEN,
                project_id=app_config.SMS_PROJECT_ID,
                ascription=app_config.SMS_ASCRIPTION,
                paragraph=app_config.SMS_PARAGRAPH, proxies=px)
            orch = RegistrationOrchestrator(sms)
            orch.on_event = lambda e,m: self._msg_queue.put(("ev",e,m))
            for i in range(app_config.REGISTER_COUNT):
                if self._stop_flag.is_set():
                    self._msg_queue.put(("L","w","stopped")); break
                self._msg_queue.put(("S", f"#{i+1}/{app_config.REGISTER_COUNT}"))
                try:
                    r = orch.run()
                    if r:
                        self._success += 1; self._msg_queue.put(("R",r))
                        self._msg_queue.put(("L","s",f"#{i+1} OK: {r['username']}"))
                    else:
                        self._fail += 1
                        self._msg_queue.put(("L","e",f"#{i+1} FAIL"))
                except Exception as e:
                    self._fail += 1
                    self._msg_queue.put(("L","e",f"#{i+1} error: {e}"))
                time.sleep(2)
        except Exception as e:
            self._msg_queue.put(("L","e",f"fatal: {e}\n{traceback.format_exc()}"))
        finally:
            self._msg_queue.put(("D",f"done: {self._success} ok / {self._fail} fail"))

    def _poll(self):
        try:
            while True:
                m = self._msg_queue.get_nowait(); t = m[0]
                if t == "L":   self._put(m[2], m[1])
                elif t == "S": self.step_lbl.configure(text=m[1]); self.stat_text.set(m[1])
                elif t == "ev":self._put({"done":"s"}.get(m[1],"m"), m[2])
                elif t == "R":
                    r = m[1]
                    self.tree.insert("","end",values=(
                        r["username"],r["password"],r["phone"],
                        r["api_key"],r["create_time"]))
                    self._flush(); self.tree.yview_moveto(1)
                elif t == "D":
                    self._running = False; self.progress.stop()
                    self.progress.grid_forget()
                    self.start_btn.configure(state="normal", text="Start")
                    self.stop_btn.configure(state="disabled")
                    self.step_lbl.configure(text=m[1])
                    self.stat_text.set("Idle"); self._put("s", m[1])
        except queue.Empty: pass
        self.root.after(100, self._poll)

    def _put(self, tag, text):
        self.log.insert("end", f"  {text}\n", tag); self.log.see("end")
    def _clear_log(self):
        self.log.delete("1.0","end")
    def run(self):
        self.root.mainloop()

def main():
    setup_log(); SenseNovaGUI().run()

if __name__ == "__main__":
    main()
