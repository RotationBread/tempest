import os
import sys
import ctypes
import threading
import tkinter as tk
from tkinter import ttk
from queue import Queue

# ------------------ ADMIN ------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, __file__, None, 1
    )
    sys.exit()

if not is_admin():
    relaunch_as_admin()

# ------------------ GLOBALS ------------------
file_count = 0
total_size = 0
current_path = ""
all_sizes = {}  # path -> size for folders and files
queue = Queue()

# ------------------ SCANNER ------------------
def scan(path):
    global file_count, total_size, current_path
    size = 0

    try:
        with os.scandir(path) as it:
            for entry in it:
                current_path = entry.path
                try:
                    if entry.is_file(follow_symlinks=False):
                        s = entry.stat().st_size
                        size += s
                        file_count += 1
                        total_size += s
                        all_sizes[entry.path] = s
                        queue.put(("file", entry.path, s))
                    elif entry.is_dir(follow_symlinks=False):
                        sub_size = scan(entry.path)
                        size += sub_size
                except:
                    continue
    except:
        return 0

    all_sizes[path] = size
    queue.put(("folder", path, size))
    return size

# ------------------ GUI ------------------
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Live Drive Size Viewer")
        self.root.geometry("1000x650")

        self.label = tk.Label(root, text="Ready", anchor="w", justify="left")
        self.label.pack(fill="x", padx=10, pady=5)

        self.tree = ttk.Treeview(root)
        self.tree.heading("#0", text="Name (Size)", anchor="w")
        self.tree.pack(fill="both", expand=True)

        self.start_btn = tk.Button(root, text="Start Scan", command=self.start)
        self.start_btn.pack(pady=5)

        self.nodes = {}      # path -> tree node
        self.nodes_inv = {}  # tree node -> path

        self.tree.bind("<<TreeviewOpen>>", self.on_open)

    def start(self):
        self.start_btn.config(state="disabled")
        # Insert root node immediately
        root_node = self.tree.insert("", "end", text="C:\\", open=True)
        self.nodes["C:\\"] = root_node
        self.nodes_inv[root_node] = "C:\\"

        # Add dummy child so root can expand
        self.tree.insert(root_node, "end", text="Loading...")

        threading.Thread(target=scan, args=("C:\\",), daemon=True).start()
        self.update_ui()

    def update_ui(self):
        global file_count, total_size, current_path
        self.label.config(
            text=f"Files: {file_count:,} | Size: {self.format_size(total_size)}\nCurrent: {current_path}"
        )

        while not queue.empty():
            item = queue.get()
            if item[0] == "folder":
                self.add_folder(item[1], item[2])
            elif item[0] == "file":
                self.add_file(item[1], item[2])

        self.root.after(100, self.update_ui)

    def add_folder(self, path, size):
        all_sizes[path] = size
        parent_path = os.path.dirname(path) or "C:\\"
        parent_node = self.nodes.get(parent_path)
        if parent_node is None:
            return

        name = os.path.basename(path) or path
        text = f"{name} ({self.format_size(size)})"

        if path in self.nodes:
            self.tree.item(self.nodes[path], text=text)
        else:
            node = self.tree.insert(parent_node, "end", text=text, open=False)
            self.nodes[path] = node
            self.nodes_inv[node] = path
            # Add dummy child so folder can expand
            self.tree.insert(node, "end", text="Loading...")

        self.sort_children(parent_node)

    def add_file(self, path, size):
        all_sizes[path] = size
        parent_path = os.path.dirname(path) or "C:\\"
        parent_node = self.nodes.get(parent_path)
        if parent_node is None:
            return

        name = os.path.basename(path)
        text = f"{name} ({self.format_size(size)})"

        node = self.tree.insert(parent_node, "end", text=text)
        self.nodes[path] = node
        self.nodes_inv[node] = path

        self.sort_children(parent_node)

    def on_open(self, event):
        node = self.tree.focus()
        path = self.nodes_inv.get(node)
        if not path:
            return

        # Remove dummy child if present
        for child in self.tree.get_children(node):
            if self.tree.item(child, "text") == "Loading...":
                self.tree.delete(child)

        # Insert actual children
        try:
            with os.scandir(path) as it:
                for entry in it:
                    full_path = entry.path
                    size = all_sizes.get(full_path, 0)
                    text = f"{entry.name} ({self.format_size(size)})"

                    if full_path in self.nodes:
                        self.tree.item(self.nodes[full_path], text=text)
                    else:
                        child_node = self.tree.insert(node, "end", text=text)
                        self.nodes[full_path] = child_node
                        self.nodes_inv[child_node] = full_path
                        if entry.is_dir(follow_symlinks=False):
                            self.tree.insert(child_node, "end", text="Loading...")
            self.sort_children(node)
        except:
            pass

    def sort_children(self, node):
        children = list(self.tree.get_children(node))
        children.sort(
            key=lambda n: all_sizes.get(self.nodes_inv.get(n, ""), 0),
            reverse=True
        )
        for index, child in enumerate(children):
            self.tree.move(child, node, index)

    def format_size(self, size):
        for unit in ['B','KB','MB','GB','TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024

# ------------------ RUN ------------------
root = tk.Tk()
app = App(root)
root.mainloop()