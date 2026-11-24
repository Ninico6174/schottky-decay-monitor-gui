import os
import re
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.ticker import FormatStrFormatter
import matplotlib.dates as mdates
from mpl_toolkits.axes_grid1 import make_axes_locatable

# --- 全局字体与负号设置 ---
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']
plt.rcParams['font.size'] = 18
plt.rcParams['axes.unicode_minus'] = False


def extract_time_from_filename(filename: str):
    """
    尝试从文件名中匹配类似 2026-04-07T22-49-47 或 2026-04-07_22-49-47 的时间格式
    """
    pattern = r"(\d{4})-(\d{2})-(\d{2})[T_\s](\d{2})-(\d{2})-(\d{2})"
    match = re.search(pattern, filename)
    if match:
        year, month, day, hour, minute, second = match.groups()
        return f"{year}-{month}-{day} {hour}:{minute}:{second}"
    return None


def strip_reconstruct_prefix(filename: str) -> str:
    """去掉 filename 前缀 'reconstruct_'，得到实际 .npz 文件名"""
    name = str(filename).strip()
    if name.startswith("reconstruct_"):
        return name[len("reconstruct_"):]
    return name


class SchottkyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Schottky 数据分析与瀑布图交互工具")
        self.root.geometry("780x630")
        self.root.attributes('-topmost', True)

        # 数据与路径状态
        self.initial_dir = r"D:\Schottky\test"
        self.npz_dir = self.initial_dir
        self.current_npz_path = ""

        # CSV 相关状态
        self.csv_path = ""
        self.df_csv: pd.DataFrame | None = None
        self.mode = "folder"  # "csv" 或 "folder"

        # 导航列表
        self.items: list[dict] = []
        self.current_index: int = -1

        # 记录已打开的 matplotlib Figure，便于切换时按需关闭
        self.open_figs: list[plt.Figure] = []

        self._build_ui()
        if os.path.isdir(self.npz_dir):
            self._load_folder_items(self.npz_dir, show_warning=False)

    def _build_ui(self):
        # 标题
        lbl_title = tk.Label(
            self.root, text="NPZ 瀑布图交互绘制工具 (CSV / 文件夹联动)",
            font=("Helvetica", 14, "bold")
        )
        lbl_title.pack(pady=(10, 6))

        # --- 区域 1：数据源导入 ---
        frame_source = tk.LabelFrame(self.root, text="1. 数据源选择", padx=10, pady=8)
        frame_source.pack(fill="x", padx=14, pady=4)

        btn_csv = tk.Button(
            frame_source, text="导入 CSV 文件", command=self.select_csv,
            bg="#2196F3", fg="white", width=14
        )
        btn_csv.grid(row=0, column=0, padx=5, pady=4)

        btn_clear_csv = tk.Button(
            frame_source, text="清除 CSV (切回文件夹)", command=self.clear_csv,
            bg="#757575", fg="white", width=18
        )
        btn_clear_csv.grid(row=0, column=1, padx=5, pady=4)

        btn_folder = tk.Button(
            frame_source, text="选择 NPZ 文件夹", command=self.select_folder,
            bg="#4CAF50", fg="white", width=14
        )
        btn_folder.grid(row=0, column=2, padx=5, pady=4)

        btn_npz = tk.Button(
            frame_source, text="单选 .npz 文件", command=self.select_single_npz,
            bg="#009688", fg="white", width=14
        )
        btn_npz.grid(row=0, column=3, padx=5, pady=4)

        self.lbl_source_status = tk.Label(
            frame_source, text=f"当前模式：文件夹模式 | 目录：{self.npz_dir}",
            fg="#333333", anchor="w", justify="left"
        )
        self.lbl_source_status.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(4, 0))

        # --- 区域 2：CSV 筛选与切换 ---
        frame_nav = tk.LabelFrame(self.root, text="2. 筛选与切换（下一张 / 指定下一张）", padx=10, pady=8)
        frame_nav.pack(fill="x", padx=14, pady=4)

        tk.Label(frame_nav, text="Ion:").grid(row=0, column=0, padx=(4, 2), pady=4, sticky="e")
        self.combo_ion = ttk.Combobox(frame_nav, width=18, state="disabled")
        self.combo_ion.grid(row=0, column=1, padx=4, pady=4)
        self.combo_ion.bind("<<ComboboxSelected>>", self._on_filter_changed)

        tk.Label(frame_nav, text="Harmonic:").grid(row=0, column=2, padx=(8, 2), pady=4, sticky="e")
        self.combo_harmonic = ttk.Combobox(frame_nav, width=14, state="disabled")
        self.combo_harmonic.grid(row=0, column=3, padx=4, pady=4)
        self.combo_harmonic.bind("<<ComboboxSelected>>", self._on_filter_changed)

        btn_reset_filter = tk.Button(
            frame_nav, text="重置筛选", command=self._reset_csv_filters, width=10
        )
        btn_reset_filter.grid(row=0, column=4, padx=6, pady=4)

        tk.Label(frame_nav, text="指定条目/文件:").grid(row=1, column=0, padx=(4, 2), pady=4, sticky="e")
        self.combo_items = ttk.Combobox(frame_nav, width=48, state="readonly")
        self.combo_items.grid(row=1, column=1, columnspan=3, padx=4, pady=4, sticky="we")
        self.combo_items.bind("<<ComboboxSelected>>", self._on_item_combo_selected)

        btn_pick_next = tk.Button(
            frame_nav, text="选择指定下一张...", command=self.pick_specific_next_dialog,
            bg="#FF9800", fg="white", width=16
        )
        btn_pick_next.grid(row=1, column=4, padx=6, pady=4)

        btn_prev = tk.Button(
            frame_nav, text="<< 上一张", command=self.prev_item, width=13
        )
        btn_prev.grid(row=2, column=0, columnspan=2, padx=5, pady=6, sticky="e")

        btn_next = tk.Button(
            frame_nav, text="下一张 >>", command=self.next_item,
            bg="#3F51B5", fg="white", width=13
        )
        btn_next.grid(row=2, column=2, padx=5, pady=6)

        self.chk_auto_plot_var = tk.BooleanVar(value=True)
        chk_auto_plot = tk.Checkbutton(
            frame_nav, text="切换后自动绘图", variable=self.chk_auto_plot_var
        )
        chk_auto_plot.grid(row=2, column=3, padx=4, pady=6, sticky="w")

        # 默认不勾选 -> 切换时自动关闭先前图像窗口；勾选后保留历史图像窗口
        self.chk_keep_figs_var = tk.BooleanVar(value=False)
        chk_keep_figs = tk.Checkbutton(
            frame_nav, text="保留历史图像窗口", variable=self.chk_keep_figs_var
        )
        chk_keep_figs.grid(row=2, column=4, padx=4, pady=6, sticky="w")

        self.lbl_nav_info = tk.Label(frame_nav, text="当前无可用条目", fg="#555555", anchor="w")
        self.lbl_nav_info.grid(row=3, column=0, columnspan=5, sticky="w", padx=5)

        # --- 区域 3：绘图参数配置 ---
        frame_config = tk.LabelFrame(self.root, text="3. 绘图参数设置", padx=10, pady=8)
        frame_config.pack(fill="x", padx=14, pady=4)

        tk.Label(frame_config, text="频率下限 (MHz):").grid(row=0, column=0, padx=5, pady=4, sticky="e")
        self.entry_fmin = tk.Entry(frame_config, width=16)
        self.entry_fmin.insert(0, "309.860")
        self.entry_fmin.grid(row=0, column=1, padx=5, pady=4)

        tk.Label(frame_config, text="频率上限 (MHz):").grid(row=0, column=2, padx=5, pady=4, sticky="e")
        self.entry_fmax = tk.Entry(frame_config, width=16)
        self.entry_fmax.insert(0, "309.865")
        self.entry_fmax.grid(row=0, column=3, padx=5, pady=4)

        tk.Label(frame_config, text="初始时间 (Start Time):").grid(row=1, column=0, padx=5, pady=4, sticky="e")
        self.entry_time = tk.Entry(frame_config, width=22)
        self.entry_time.insert(0, "2026-04-08 02:21:56")
        self.entry_time.grid(row=1, column=1, columnspan=2, padx=5, pady=4, sticky="w")

        self.lbl_time_note = tk.Label(frame_config, text="提示：导入 CSV 后默认取 peak_pos ± 5 kHz", fg="gray")
        self.lbl_time_note.grid(row=1, column=2, columnspan=2, padx=5, pady=4, sticky="e")

        self.lbl_file_status = tk.Label(
            frame_config, text="当前未选中 .npz 文件", fg="red", anchor="w"
        )
        self.lbl_file_status.grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=(4, 0))

        # --- 区域 4：主操作按钮 ---
        frame_buttons = tk.Frame(self.root)
        frame_buttons.pack(pady=12)

        btn_plot = tk.Button(
            frame_buttons, text="开始绘图", command=self.plot_data,
            width=14, height=1, bg="#008CBA", fg="white", font=("Helvetica", 11, "bold")
        )
        btn_plot.grid(row=0, column=0, padx=12)

        btn_exit = tk.Button(
            frame_buttons, text="退出程序", command=self.root.destroy,
            width=14, height=1, bg="#f44336", fg="white", font=("Helvetica", 11, "bold")
        )
        btn_exit.grid(row=0, column=1, padx=12)

    def _close_previous_figs_if_needed(self):
        """若未勾选“保留历史图像窗口”，则关闭之前由本工具打开的图像窗口"""
        if self.chk_keep_figs_var.get():
            return

        remaining = []
        for fig in self.open_figs:
            try:
                if plt.fignum_exists(fig.number):
                    plt.close(fig)
            except Exception:
                pass
        self.open_figs = remaining

    # ==================== 数据源与列表管理 ====================
    def select_csv(self):
        path = filedialog.askopenfilename(
            initialdir=self.initial_dir,
            title="请选择 CSV 数据文件",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            df = pd.read_csv(path)
        except Exception as e:
            messagebox.showerror("错误", f"读取 CSV 失败:\n{e}")
            return

        required_cols = {"filename"}
        if not required_cols.issubset(set(df.columns)):
            messagebox.showerror("错误", f"CSV 缺少必要列: {required_cols - set(df.columns)}")
            return

        self.csv_path = path
        self.initial_dir = os.path.dirname(path)
        self.df_csv = df
        self.mode = "csv"

        if "ion" in df.columns:
            ions = ["全部 (ALL)"] + sorted(df["ion"].dropna().astype(str).unique().tolist())
            self.combo_ion.config(state="readonly", values=ions)
            self.combo_ion.set("全部 (ALL)")
        else:
            self.combo_ion.config(state="disabled", values=[])
            self.combo_ion.set("")

        if "harmonic" in df.columns:
            harm_vals = df["harmonic"].dropna().tolist()
            formatted_harm = []
            for v in harm_vals:
                try:
                    fv = float(v)
                    formatted_harm.append(str(int(fv)) if fv.is_integer() else str(fv))
                except Exception:
                    formatted_harm.append(str(v))
            harmonics = ["全部 (ALL)"] + sorted(
                set(formatted_harm),
                key=lambda x: (float(x) if x.replace('.', '', 1).isdigit() else 1e18, x)
            )
            self.combo_harmonic.config(state="readonly", values=harmonics)
            self.combo_harmonic.set("全部 (ALL)")
        else:
            self.combo_harmonic.config(state="disabled", values=[])
            self.combo_harmonic.set("")

        self.lbl_source_status.config(
            text=f"当前模式：CSV 模式 | CSV：{os.path.basename(path)} | NPZ 目录：{self.npz_dir}",
            fg="#1565C0"
        )
        self._apply_csv_filters()

    def clear_csv(self):
        self.csv_path = ""
        self.df_csv = None
        self.mode = "folder"
        self.combo_ion.set("")
        self.combo_ion.config(state="disabled", values=[])
        self.combo_harmonic.set("")
        self.combo_harmonic.config(state="disabled", values=[])
        self.lbl_source_status.config(
            text=f"当前模式：文件夹模式 | 目录：{self.npz_dir}",
            fg="#333333"
        )
        self._load_folder_items(self.npz_dir, show_warning=False)

    def select_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.npz_dir if os.path.isdir(self.npz_dir) else self.initial_dir,
            title="请选择存放 .npz 文件的文件夹"
        )
        if not folder:
            return
        self.npz_dir = folder
        self.initial_dir = folder

        if self.mode == "csv" and self.df_csv is not None:
            self.lbl_source_status.config(
                text=f"当前模式：CSV 模式 | CSV：{os.path.basename(self.csv_path)} | NPZ 目录：{self.npz_dir}",
                fg="#1565C0"
            )
            self._apply_csv_filters()
        else:
            self.mode = "folder"
            self.lbl_source_status.config(
                text=f"当前模式：文件夹模式 | 目录：{self.npz_dir}",
                fg="#333333"
            )
            self._load_folder_items(self.npz_dir, show_warning=True)

    def select_single_npz(self):
        path = filedialog.askopenfilename(
            initialdir=self.npz_dir if os.path.isdir(self.npz_dir) else self.initial_dir,
            title="请选择要显示的 .npz 文件",
            filetypes=[("NPZ files", "*.npz"), ("All files", "*.*")]
        )
        if not path:
            return

        folder = os.path.dirname(path)
        self.npz_dir = folder
        self.initial_dir = folder

        if self.mode != "csv":
            self._load_folder_items(folder, show_warning=False)
            for idx, item in enumerate(self.items):
                if os.path.abspath(item["npz_path"]) == os.path.abspath(path):
                    self._activate_index(idx, auto_plot=False)
                    return

        self._set_active_target(
            npz_path=path,
            peak_pos_hz=None,
            extra_note="手动单选 .npz 文件"
        )

    def _load_folder_items(self, folder: str, show_warning: bool = True):
        if not os.path.isdir(folder):
            self.items = []
            self.current_index = -1
            self._refresh_item_combo()
            if show_warning:
                messagebox.showwarning("警告", f"文件夹不存在：\n{folder}")
            return

        npz_files = sorted(
            [f for f in os.listdir(folder) if f.lower().endswith(".npz")]
        )
        self.items = [
            {
                "label": f"[{i+1}] {fname}",
                "npz_path": os.path.join(folder, fname),
                "peak_pos_hz": None,
                "ion": None,
                "harmonic": None,
            }
            for i, fname in enumerate(npz_files)
        ]
        self._refresh_item_combo()

        if self.items:
            self._activate_index(0, auto_plot=False)
        else:
            self.current_index = -1
            self.lbl_nav_info.config(text="当前文件夹下未找到 .npz 文件", fg="orange")
            if show_warning:
                messagebox.showwarning("提示", "所选文件夹中没有找到 .npz 文件。")

    def _reset_csv_filters(self):
        if self.mode != "csv" or self.df_csv is None:
            return
        if "ion" in self.df_csv.columns:
            self.combo_ion.set("全部 (ALL)")
        if "harmonic" in self.df_csv.columns:
            self.combo_harmonic.set("全部 (ALL)")
        self._apply_csv_filters()

    def _on_filter_changed(self, event=None):
        if self.mode == "csv" and self.df_csv is not None:
            self._apply_csv_filters()

    def _apply_csv_filters(self):
        if self.df_csv is None:
            return
        sub = self.df_csv.copy()

        selected_ion = self.combo_ion.get()
        if "ion" in sub.columns and selected_ion and selected_ion != "全部 (ALL)":
            sub = sub[sub["ion"].astype(str) == selected_ion]

        selected_harm = self.combo_harmonic.get()
        if "harmonic" in sub.columns and selected_harm and selected_harm != "全部 (ALL)":
            def _harm_match(val):
                if pd.isna(val):
                    return False
                try:
                    fv = float(val)
                    s = str(int(fv)) if fv.is_integer() else str(fv)
                except Exception:
                    s = str(val)
                return s == selected_harm
            sub = sub[sub["harmonic"].apply(_harm_match)]

        new_items = []
        for row_idx, row in sub.iterrows():
            raw_fn = str(row["filename"])
            clean_fn = strip_reconstruct_prefix(raw_fn)
            npz_full = os.path.join(self.npz_dir, clean_fn)

            peak_hz = None
            if "peak_pos" in row and pd.notna(row["peak_pos"]):
                try:
                    peak_hz = float(row["peak_pos"])
                except Exception:
                    peak_hz = None

            ion_str = str(row["ion"]) if ("ion" in row and pd.notna(row["ion"])) else "-"
            harm_str = "-"
            if "harmonic" in row and pd.notna(row["harmonic"]):
                try:
                    fv = float(row["harmonic"])
                    harm_str = str(int(fv)) if fv.is_integer() else str(fv)
                except Exception:
                    harm_str = str(row["harmonic"])

            peak_mhz_str = f"{peak_hz / 1e6:.6f}MHz" if peak_hz is not None else "NoPeak"
            label = f"#{row_idx} | ion={ion_str} | h={harm_str} | {peak_mhz_str} | {clean_fn}"
            new_items.append({
                "label": label,
                "npz_path": npz_full,
                "peak_pos_hz": peak_hz,
                "ion": ion_str,
                "harmonic": harm_str,
            })

        self.items = new_items
        self._refresh_item_combo()

        if self.items:
            self._activate_index(0, auto_plot=False)
        else:
            self.current_index = -1
            self.lbl_nav_info.config(text="当前筛选条件下无匹配记录", fg="orange")

    def _refresh_item_combo(self):
        labels = [it["label"] for it in self.items]
        self.combo_items.config(values=labels)
        if self.items and 0 <= self.current_index < len(self.items):
            self.combo_items.current(self.current_index)
        else:
            self.combo_items.set("")

    def _on_item_combo_selected(self, event=None):
        idx = self.combo_items.current()
        if 0 <= idx < len(self.items):
            self._activate_index(idx, auto_plot=self.chk_auto_plot_var.get(), is_navigation=True)

    def _activate_index(self, idx: int, auto_plot: bool = False, is_navigation: bool = False):
        if not (0 <= idx < len(self.items)):
            return
        if is_navigation:
            self._close_previous_figs_if_needed()

        self.current_index = idx
        self.combo_items.current(idx)
        item = self.items[idx]

        self.lbl_nav_info.config(
            text=f"进度: {idx + 1} / {len(self.items)}  |  {item['label']}",
            fg="#1B5E20"
        )

        self._set_active_target(
            npz_path=item["npz_path"],
            peak_pos_hz=item["peak_pos_hz"],
            extra_note=f"CSV 条目 #{idx + 1}/{len(self.items)}"
        )

        if auto_plot:
            self.plot_data(_already_closed_prev=is_navigation)

    def _set_active_target(self, npz_path: str, peak_pos_hz: float | None, extra_note: str = ""):
        self.current_npz_path = npz_path
        filename = os.path.basename(npz_path)

        exists = os.path.isfile(npz_path)
        if exists:
            self.lbl_file_status.config(
                text=f"已就绪 ({extra_note}): {filename}", fg="green"
            )
        else:
            self.lbl_file_status.config(
                text=f"文件不存在 ({extra_note}): {npz_path}", fg="red"
            )

        if peak_pos_hz is not None and not np.isnan(peak_pos_hz):
            f_center_mhz = peak_pos_hz / 1e6
            f_min_mhz = f_center_mhz - 0.005
            f_max_mhz = f_center_mhz + 0.005
            self.entry_fmin.delete(0, tk.END)
            self.entry_fmin.insert(0, f"{f_min_mhz:.6f}")
            self.entry_fmax.delete(0, tk.END)
            self.entry_fmax.insert(0, f"{f_max_mhz:.6f}")

        extracted_time = extract_time_from_filename(filename)
        self.entry_time.delete(0, tk.END)
        if extracted_time:
            self.entry_time.insert(0, extracted_time)
            self.lbl_time_note.config(text="自动从文件名中读取时间成功", fg="green")
        else:
            self.entry_time.insert(0, "2026-04-08 02:21:56")
            self.lbl_time_note.config(text="未匹配到时间，请手动确认/输入", fg="orange")

    def prev_item(self):
        if not self.items:
            messagebox.showwarning("提示", "当前没有可切换的条目或文件。")
            return
        new_idx = (self.current_index - 1) % len(self.items)
        self._activate_index(new_idx, auto_plot=self.chk_auto_plot_var.get(), is_navigation=True)

    def next_item(self):
        if not self.items:
            messagebox.showwarning("提示", "当前没有可切换的条目或文件。")
            return
        new_idx = (self.current_index + 1) % len(self.items)
        self._activate_index(new_idx, auto_plot=self.chk_auto_plot_var.get(), is_navigation=True)

    def pick_specific_next_dialog(self):
        if not self.items:
            messagebox.showwarning("提示", "当前没有可选择的条目或文件。")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("选择指定下一张 / 目标条目")
        dlg.geometry("680x420")
        dlg.attributes('-topmost', True)
        dlg.grab_set()

        tk.Label(
            dlg, text="双击或选中条目后点击“确认跳转”（默认定位到当前条目之后）：",
            anchor="w"
        ).pack(fill="x", padx=10, pady=(10, 4))

        frame_list = tk.Frame(dlg)
        frame_list.pack(fill="both", expand=True, padx=10, pady=4)

        scrollbar = tk.Scrollbar(frame_list)
        scrollbar.pack(side="right", fill="y")

        listbox = tk.Listbox(
            frame_list, yscrollcommand=scrollbar.set, font=("Consolas", 10), selectmode=tk.SINGLE
        )
        scrollbar.config(command=listbox.yview)

        for idx, it in enumerate(self.items):
            prefix = "▶ " if idx == self.current_index else "  "
            listbox.insert(tk.END, f"{prefix}{it['label']}")

        listbox.pack(side="left", fill="both", expand=True)

        default_target = min(self.current_index + 1, len(self.items) - 1) if self.current_index >= 0 else 0
        listbox.selection_set(default_target)
        listbox.see(default_target)

        def confirm_choice(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            chosen_idx = sel[0]
            dlg.destroy()
            self._activate_index(chosen_idx, auto_plot=self.chk_auto_plot_var.get(), is_navigation=True)

        listbox.bind("<Double-Button-1>", confirm_choice)

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="确认跳转", command=confirm_choice, bg="#4CAF50", fg="white", width=12).pack(side="left", padx=8)
        tk.Button(btn_frame, text="取消", command=dlg.destroy, width=12).pack(side="left", padx=8)

    # ==================== 核心绘图函数 ====================
    def plot_data(self, _already_closed_prev: bool = False):
        if not self.current_npz_path:
            messagebox.showwarning("警告", "请先选择或加载一个 .npz 文件！")
            return

        if not os.path.isfile(self.current_npz_path):
            messagebox.showerror("错误", f"找不到对应的 .npz 文件：\n{self.current_npz_path}")
            return

        try:
            f_min = float(self.entry_fmin.get())
            f_max = float(self.entry_fmax.get())
        except ValueError:
            messagebox.showerror("错误", "请输入正确的频率数值（浮点数）！")
            return

        if f_min >= f_max:
            messagebox.showwarning("警告", "频率下限应小于频率上限！")
            return

        timestamp_start = self.entry_time.get().strip()
        try:
            start_dt = datetime.strptime(timestamp_start, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            messagebox.showerror("错误", "时间格式不正确！请使用 YYYY-MM-DD HH:MM:SS 格式")
            return

        # --- 1. 加载数据 ---
        try:
            data = np.load(self.current_npz_path)
            raw_frequencies = data['frequencies'] / 1e6
            psd_arrays = data['psd_arrays']
            times = data['times']

            if raw_frequencies.shape[0] == psd_arrays.shape[1] + 1:
                frequencies = (raw_frequencies[:-1] + raw_frequencies[1:]) / 2.0
            else:
                frequencies = raw_frequencies
        except Exception as e:
            messagebox.showerror("错误", f"文件读取失败:\n{e}")
            return

        # --- 2. 局部切片与过滤 ---
        freq_mask = (frequencies >= f_min) & (frequencies <= f_max)
        plot_freqs = frequencies[freq_mask]

        if len(plot_freqs) == 0:
            messagebox.showwarning("警告", "所选频率范围内没有数据，请重新设置 f_min 和 f_max！")
            return

        plot_psd = psd_arrays[:, freq_mask]

        # 若非切换触发的直接点击“开始绘图”，也按“保留历史图像窗口”开关决定是否先关闭旧图
        if not _already_closed_prev:
            self._close_previous_figs_if_needed()

        # --- 3. 创建双子图布局 (上下对齐，共享 X 轴) ---
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=(10, 8),
            sharex=True,
            gridspec_kw={'height_ratios': [3, 1]}
        )
        self.open_figs = [f for f in self.open_figs if plt.fignum_exists(f.number)]
        self.open_figs.append(fig)

        y_min = mdates.date2num(start_dt + timedelta(seconds=float(times[0])))
        y_max = mdates.date2num(start_dt + timedelta(seconds=float(times[-1])))
        x_min = plot_freqs.min()
        x_max = plot_freqs.max()

        im = ax1.imshow(
            plot_psd,
            cmap='viridis',
            norm=colors.LogNorm(vmin=plot_psd.min() + 1e-20, vmax=plot_psd.max()),
            aspect='auto',
            origin='lower',
            extent=[x_min, x_max, y_min, y_max],
            rasterized=True
        )

        def time_formatter(x, pos):
            dt = mdates.num2date(x)
            return dt.strftime('%H:%M:%S.%f')[:-5]

        ax1.yaxis.set_major_formatter(plt.FuncFormatter(time_formatter))
        ax1.set_ylabel("Time (HH:MM:SS)")

        filename = os.path.basename(self.current_npz_path)
        title_text = f"File: {filename}"
        if 0 <= self.current_index < len(self.items) and self.mode == "csv":
            it = self.items[self.current_index]
            title_text += f" | ion={it['ion']}, h={it['harmonic']}"
        ax1.set_title(title_text, fontsize=13, pad=10)

        avg_psd = np.mean(plot_psd, axis=0)

        ax2.plot(plot_freqs, avg_psd, color='navy', linewidth=1.5, label='Mean PSD')
        ax2.set_yscale('log')
        ax2.set_xlabel("Frequency (MHz)")
        ax2.set_ylabel(r"PSD (V$^2$/Hz)")
        ax2.grid(True, which="both", ls="--", alpha=0.5)

        ax2.set_xlim(f_min, f_max)
        ax2.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))

        plt.setp(ax1.get_xticklabels(), visible=False)

        divider1 = make_axes_locatable(ax1)
        cax1 = divider1.append_axes("right", size="3%", pad=0.15)
        cbar = fig.colorbar(im, cax=cax1)
        cbar.set_label(r"PSD (V$^2$/Hz)")

        divider2 = make_axes_locatable(ax2)
        cax2 = divider2.append_axes("right", size="3%", pad=0.15)
        cax2.axis('off')

        fig.tight_layout()
        plt.subplots_adjust(hspace=0.08)

        plt.show()


if __name__ == "__main__":
    root = tk.Tk()
    app = SchottkyGUI(root)
    root.mainloop()