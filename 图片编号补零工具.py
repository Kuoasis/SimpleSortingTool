"""Windows 图片编号补零工具（无需安装第三方库）。"""

from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


IMAGE_TYPES = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic"
}
NUMBER_ONLY = re.compile(r"^\d+$")


class RenumberApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("图片编号补零工具")
        self.geometry("720x510")
        self.minsize(620, 400)
        self.files: list[Path] = []
        self.plan: list[tuple[Path, Path]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="图片编号补零", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="选择文件名为纯数字的图片（如 1.jpg、10.png）。工具按数值排序，并按最大编号的位数补零。",
            wraplength=670,
        ).pack(anchor="w", pady=(5, 12))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 10))
        ttk.Button(buttons, text="选择图片…", command=self.choose_files).pack(side="left")
        ttk.Button(buttons, text="清空", command=self.clear).pack(side="left", padx=8)
        self.rename_button = ttk.Button(buttons, text="确认重命名", command=self.rename, state="disabled")
        self.rename_button.pack(side="right")

        self.summary = ttk.Label(frame, text="尚未选择文件")
        self.summary.pack(anchor="w", pady=(0, 6))

        columns = ("old", "new")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="none")
        self.table.heading("old", text="当前文件名（按数值排序）")
        self.table.heading("new", text="将改为")
        self.table.column("old", width=340, anchor="w")
        self.table.column("new", width=280, anchor="w")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(
            frame,
            text="提示：会先改为临时文件名，再改为目标名，以避免 1.jpg 与 01.jpg 互相占用。",
            foreground="#555555",
            wraplength=670,
        ).pack(anchor="w", pady=(10, 0))

    def choose_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="选择需要编号补零的图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tif *.tiff *.heic"), ("所有文件", "*.*")],
        )
        if not selected:
            return
        paths = [Path(name) for name in selected]
        invalid_type = [p.name for p in paths if p.suffix.lower() not in IMAGE_TYPES]
        invalid_name = [p.name for p in paths if not NUMBER_ONLY.fullmatch(p.stem)]
        if invalid_type or invalid_name:
            details = []
            if invalid_type:
                details.append("不是支持的图片：" + "、".join(invalid_type[:5]))
            if invalid_name:
                details.append("文件名不是纯数字：" + "、".join(invalid_name[:5]))
            messagebox.showerror("无法生成预览", "\n".join(details) + "\n\n请只选择名称如 1.jpg、10.png 的图片。")
            return
        if len(set(paths)) != len(paths):
            messagebox.showerror("重复选择", "同一文件被重复选择。")
            return
        self.files = paths
        self.make_plan()

    def make_plan(self) -> None:
        # 数值相同而扩展名不同会形成相同的目标主名，但不会冲突；同扩展名则不能安全改名。
        ordered = sorted(self.files, key=lambda p: (int(p.stem), p.suffix.lower(), p.name.lower()))
        maximum = max(int(p.stem) for p in ordered)
        width = max(1, len(str(maximum)))
        self.plan = [(source, source.with_name(f"{int(source.stem):0{width}d}{source.suffix}")) for source in ordered]
        self.refresh_table(width, maximum)

    def refresh_table(self, width: int, maximum: int) -> None:
        self.table.delete(*self.table.get_children())
        for source, target in self.plan:
            self.table.insert("", "end", values=(source.name, target.name))
        unchanged = sum(source == target for source, target in self.plan)
        self.summary.configure(text=f"已选择 {len(self.plan)} 张图片；最大编号为 {maximum}，使用 {width} 位编号（其中 {unchanged} 个无需改名）")
        self.rename_button.configure(state="normal" if any(a != b for a, b in self.plan) else "disabled")

    def clear(self) -> None:
        self.files, self.plan = [], []
        self.table.delete(*self.table.get_children())
        self.summary.configure(text="尚未选择文件")
        self.rename_button.configure(state="disabled")

    def rename(self) -> None:
        changed = [(source, target) for source, target in self.plan if source != target]
        if not changed:
            return
        selected_set = {source for source, _ in changed}
        # Windows 文件名不区分大小写；若目标已被非本次文件占用，绝不覆盖。
        conflicts = [target.name for _, target in changed if target.exists() and target not in selected_set]
        duplicate_targets = len({str(t).lower() for _, t in self.plan}) != len(self.plan)
        if conflicts or duplicate_targets:
            text = "目标文件名重复。" if duplicate_targets else "已有未选中文件占用了目标名称：\n" + "\n".join(conflicts[:8])
            messagebox.showerror("无法安全重命名", text + "\n\n请调整选择范围后再试。")
            return
        if not messagebox.askyesno("确认重命名", f"将重命名 {len(changed)} 个文件。\n此操作会直接修改原文件名，是否继续？"):
            return

        temporary: list[tuple[Path, Path, Path]] = []
        try:
            for source, target in changed:
                temp = source.with_name(f".__number_pad_{uuid.uuid4().hex}{source.suffix}")
                os.rename(source, temp)
                temporary.append((source, temp, target))
            for _, temp, target in temporary:
                os.rename(temp, target)
        except OSError as exc:
            # 尽最大努力恢复尚未完成的临时名，避免工具造成文件丢失。
            for source, temp, target in reversed(temporary):
                try:
                    if temp.exists():
                        os.rename(temp, source)
                    elif target.exists() and not source.exists():
                        os.rename(target, source)
                except OSError:
                    pass
            messagebox.showerror("重命名失败", f"操作未完成，已尝试恢复原名称。\n\n{exc}")
            return
        self.files = [target for _, target in self.plan]
        self.make_plan()
        messagebox.showinfo("完成", f"已成功重命名 {len(changed)} 个图片文件。")


if __name__ == "__main__":
    try:
        RenumberApp().mainloop()
    except Exception as error:
        messagebox.showerror("程序错误", str(error))
        raise
