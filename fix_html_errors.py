#!/usr/bin/env python3
"""
Script to fix common HTML accessibility errors in Django templates
"""
import os
import re
from pathlib import Path

# Common fixes
FIXES = [
    # Fix select elements without title/aria-label
    (
        r'<select([^>]*?)(?<!title="[^"]*")(?<!aria-label="[^"]*")>',
        lambda m: add_accessible_name_to_select(m)
    ),
    # Fix input elements without labels (add aria-label if no label found)
    (
        r'<input([^>]*?name="([^"]+)"[^>]*?)(?<!aria-label="[^"]*")(?<!title="[^"]*")>',
        lambda m: add_aria_label_to_input(m)
    ),
]

def add_accessible_name_to_select(match):
    """Add title and aria-label to select element"""
    attrs = match.group(1)
    # Extract id or name for label
    id_match = re.search(r'id="([^"]+)"', attrs)
    name_match = re.search(r'name="([^"]+)"', attrs)
    
    label_text = "Select option"
    if id_match:
        label_text = f"Select {id_match.group(1).replace('_', ' ').replace('-', ' ').title()}"
    elif name_match:
        label_text = f"Select {name_match.group(1).replace('_', ' ').replace('-', ' ').title()}"
    
    if 'title=' not in attrs and 'aria-label=' not in attrs:
        return f'<select{attrs} title="{label_text}" aria-label="{label_text}">'
    return match.group(0)

def add_aria_label_to_input(match):
    """Add aria-label to input element"""
    attrs = match.group(1)
    name = match.group(2)
    
    # Skip if it's a hidden input or already has label
    if 'type="hidden"' in attrs or 'type="checkbox"' in attrs:
        return match.group(0)
    
    label_text = name.replace('_', ' ').replace('-', ' ').title()
    
    if 'aria-label=' not in attrs and 'title=' not in attrs:
        return f'<input{attrs} aria-label="{label_text}">'
    return match.group(0)

def fix_template_file(file_path):
    """Fix HTML errors in a template file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix select elements
        content = re.sub(
            r'<select([^>]*?)(?<!title="[^"]*")(?<!aria-label="[^"]*")>',
            lambda m: add_accessible_name_to_select(m),
            content
        )
        
        # Fix input elements (be careful with this one)
        # Only fix inputs that clearly need labels
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
    return False

def main():
    """Main function"""
    templates_dir = Path('hospital/templates')
    
    if not templates_dir.exists():
        print("Templates directory not found!")
        return
    
    fixed_count = 0
    for template_file in templates_dir.rglob('*.html'):
        if fix_template_file(template_file):
            print(f"Fixed: {template_file}")
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} template files")

if __name__ == '__main__':
    main()







