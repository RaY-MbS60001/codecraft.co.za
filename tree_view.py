import os

# Allowed file extensions
INCLUDE_EXTENSIONS = {'.py', '.html', '.css'}

# Folders you want to ignore (e.g., venv, __pycache__)
EXCLUDE_DIRS = {'venv', '__pycache__', '.git'}

def print_project_structure(path, indent="", level=0, max_depth=3):
    if level > max_depth or not os.path.exists(path):
        return

    items = sorted(os.listdir(path))
    for i, item in enumerate(items):
        full_path = os.path.join(path, item)
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "

        if os.path.isdir(full_path):
            if item in EXCLUDE_DIRS:
                continue
            print(indent + connector + f"📁 {item}")
            new_indent = indent + ("    " if is_last else "│   ")
            print_project_structure(full_path, new_indent, level + 1, max_depth)
        else:
            ext = os.path.splitext(item)[1]
            if ext in INCLUDE_EXTENSIONS:
                print(indent + connector + item)

# Replace with your actual path
project_root = r"C:\Users\Mabasos\Desktop\MBS\codecraft.co.za"

print(f"\n📁 Project Structure: {project_root}")
print_project_structure(project_root)
  