"""
scripts/export_codebase.py - Export the entire codebase to a single Markdown file.

This script wipes the old `codebase.md` and rebuilds it by scanning all 
relevant source files. This makes it easy to copy-paste your entire project 
context into an LLM (like ChatGPT) for review.

Usage:
    python scripts/export_codebase.py
"""

import os
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "codebase.md"

# Directories to ignore
IGNORE_DIRS = {
    ".git", 
    "venv", 
    ".venv", 
    "env", 
    "__pycache__", 
    "data", 
    "outputs", 
    ".ipynb_checkpoints",
    "node_modules"
}

# File extensions to include (ignores images, big datasets, compiled files)
ALLOWED_EXTENSIONS = {
    ".py", 
    ".md", 
    ".txt", 
    ".json", 
    ".yaml", 
    ".yml", 
    ".jsx", 
    ".js", 
    ".html", 
    ".css"
}

# Specific files to ignore even if they match extensions
IGNORE_FILES = {
    "codebase.md",           # Don't include the output file itself!
    "package-lock.json",     # Too large and noisy
}


def build_codebase_md():
    print(f"Scanning repository: {REPO_ROOT}")
    
    # Open the output file in write mode (this clears the old content)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("# VectorDrugMatch - Full Codebase Export\n\n")
        out.write("This document contains all source code and documentation for the project.\n\n")
        
        file_count = 0
        total_lines = 0
        
        # Walk through the directory tree
        for root, dirs, files in os.walk(REPO_ROOT):
            # Modifying `dirs` in-place tells os.walk to skip those directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in sorted(files):
                file_path = Path(root) / file
                
                # Check exclusion rules
                if file in IGNORE_FILES:
                    continue
                if file_path.suffix not in ALLOWED_EXTENSIONS:
                    continue
                    
                # Calculate relative path for display
                rel_path = file_path.relative_to(REPO_ROOT)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    # Determine markdown syntax highlighting language
                    ext = file_path.suffix.lower()
                    lang = ext[1:] if ext else "text"
                    if ext == ".py": lang = "python"
                    elif ext == ".md": lang = "markdown"
                    elif ext == ".js": lang = "javascript"
                    
                    # Write to output file
                    out.write(f"## File: `{rel_path}`\n\n")
                    out.write(f"```{lang}\n")
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
                    out.write("```\n\n")
                    
                    file_count += 1
                    total_lines += content.count('\n') + 1
                    print(f"  Added: {rel_path}")
                    
                except Exception as e:
                    print(f"  [WARNING] Skipped {rel_path} (Error reading: {e})")

    print("\n" + "="*50)
    print(f"Export Complete!")
    print(f"Files exported: {file_count}")
    print(f"Total lines:    {total_lines:,}")
    print(f"Output saved to: {OUTPUT_FILE.relative_to(REPO_ROOT)}")
    print("="*50)


if __name__ == "__main__":
    build_codebase_md()
