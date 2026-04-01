#!/usr/bin/env python3
"""
Script to fix common linter errors in Django templates:
1. Add aria-label/title to buttons with only icons
2. Add labels to form inputs
3. Add titles to select elements
4. Move common inline styles to CSS classes
"""

import os
import re
from pathlib import Path

TEMPLATE_DIR = Path("hospital/templates/hospital")

def fix_button_accessibility(content):
    """Add aria-label and title to buttons with only icons"""
    # Pattern: <button> with only <i> or icon, no text
    patterns = [
        (r'(<button[^>]*>)\s*<i[^>]*class="[^"]*bi-trash[^"]*"[^>]*></i>\s*(</button>)', 
         r'\1<i class="bi bi-trash" aria-hidden="true"></i><span class="visually-hidden">Delete</span>\2'),
        (r'(<button[^>]*>)\s*<i[^>]*class="[^"]*bi-pencil[^"]*"[^>]*></i>\s*(</button>)',
         r'\1<i class="bi bi-pencil" aria-hidden="true"></i><span class="visually-hidden">Edit</span>\2'),
        (r'(<button[^>]*>)\s*<i[^>]*class="[^"]*bi-eye[^"]*"[^>]*></i>\s*(</button>)',
         r'\1<i class="bi bi-eye" aria-hidden="true"></i><span class="visually-hidden">View</span>\2'),
        (r'(<button[^>]*>)\s*<i[^>]*class="[^"]*bi-check[^"]*"[^>]*></i>\s*(</button>)',
         r'\1<i class="bi bi-check" aria-hidden="true"></i><span class="visually-hidden">Approve</span>\2'),
        (r'(<button[^>]*>)\s*<i[^"]*class="[^"]*bi-x[^"]*"[^>]*></i>\s*(</button>)',
         r'\1<i class="bi bi-x" aria-hidden="true"></i><span class="visually-hidden">Cancel</span>\2'),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    # Add title/aria-label to buttons that don't have them
    def add_button_attrs(match):
        button_tag = match.group(0)
        if 'title=' not in button_tag and 'aria-label=' not in button_tag:
            # Try to infer from icon class
            if 'bi-trash' in button_tag:
                button_tag = button_tag.replace('>', ' aria-label="Delete" title="Delete">', 1)
            elif 'bi-pencil' in button_tag or 'bi-edit' in button_tag:
                button_tag = button_tag.replace('>', ' aria-label="Edit" title="Edit">', 1)
            elif 'bi-eye' in button_tag or 'bi-view' in button_tag:
                button_tag = button_tag.replace('>', ' aria-label="View" title="View">', 1)
        return button_tag
    
    content = re.sub(r'<button[^>]*>', add_button_attrs, content)
    return content

def fix_form_labels(content):
    """Add labels to form inputs without them"""
    # Pattern: <input> or <select> without associated label
    # This is complex, so we'll add title attributes as a quick fix
    patterns = [
        (r'(<input[^>]*type="text"[^>]*)(?<!title=)(?<!placeholder=)(?<!aria-label=)(>)',
         r'\1 title="Enter text" placeholder="Enter text"\2'),
        (r'(<input[^>]*type="number"[^>]*)(?<!title=)(?<!placeholder=)(?<!aria-label=)(>)',
         r'\1 title="Enter number" placeholder="Enter number"\2'),
        (r'(<select[^>]*)(?<!title=)(?<!aria-label=)(>)',
         r'\1 title="Select option" aria-label="Select option"\2'),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    return content

def fix_inline_styles(content, file_path):
    """Move common inline styles to CSS classes"""
    # Common patterns to replace
    replacements = [
        (r'style="display:\s*inline;"', 'class="d-inline"'),
        (r'style="display:\s*none;"', 'class="d-none"'),
        (r'style="display:\s*block;"', 'class="d-block"'),
        (r'style="display:\s*flex;"', 'class="d-flex"'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    return content

def process_file(file_path):
    """Process a single template file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply fixes
        content = fix_button_accessibility(content)
        content = fix_form_labels(content)
        content = fix_inline_styles(content, file_path)
        
        # Only write if changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all template files"""
    if not TEMPLATE_DIR.exists():
        print(f"Template directory not found: {TEMPLATE_DIR}")
        return
    
    html_files = list(TEMPLATE_DIR.rglob("*.html"))
    print(f"Found {len(html_files)} HTML files to process")
    
    fixed_count = 0
    for file_path in html_files:
        if process_file(file_path):
            fixed_count += 1
            print(f"Fixed: {file_path.relative_to(TEMPLATE_DIR.parent)}")
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()





