#!/usr/bin/env python3
"""
Enhanced script to move inline styles to CSS classes
Fixes common inline style patterns by converting them to Bootstrap or custom classes
"""

import os
import re
from pathlib import Path

TEMPLATE_DIR = Path("hospital/templates/hospital")
CSS_FILE = Path("hospital/static/hospital/css/common_styles.css")

# Common inline style patterns to replace
STYLE_REPLACEMENTS = [
    # Width patterns
    (r'style="width:\s*auto;"', 'class="width-auto"'),
    (r'style="width:\s*180px;"', 'class="width-180"'),
    (r'style="width:\s*100px;"', 'class="width-100"'),
    
    # Height patterns
    (r'style="height:\s*6px;"', 'class="height-6"'),
    
    # Display patterns (already handled but ensure coverage)
    (r'style="display:\s*inline-block;"', 'class="d-inline-block"'),
    (r'style="display:\s*inline-block;\s*width:\s*auto;"', 'class="d-inline-block width-auto"'),
    
    # Common color/background patterns
    (r'style="background:\s*linear-gradient\(135deg,\s*#667EEA\s*0%,\s*#764BA2\s*100%\);\s*color:\s*white;"', 'class="encounter-overview-gradient"'),
    
    # Remove empty style attributes
    (r'\s*style=""', ''),
    (r'\s*style="\s*"', ''),
]

def add_css_classes():
    """Add common CSS classes to the CSS file if they don't exist"""
    if not CSS_FILE.exists():
        return
    
    with open(CSS_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_classes = """
/* Width utilities */
.width-auto {
    width: auto;
}

.width-180 {
    width: 180px;
}

.width-100 {
    width: 100px;
}

/* Height utilities */
.height-6 {
    height: 6px;
}
"""
    
    if 'width-auto' not in content:
        with open(CSS_FILE, 'a', encoding='utf-8') as f:
            f.write(new_classes)

def fix_inline_styles(content, file_path):
    """Move common inline styles to CSS classes"""
    original_content = content
    
    # Apply replacements
    for pattern, replacement in STYLE_REPLACEMENTS:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    # Fix style attributes with multiple properties - extract to classes where possible
    # This is more complex, so we'll handle common cases
    
    # Remove style="width: auto;" from date inputs (we'll use class instead)
    content = re.sub(
        r'(<input[^>]*type="date"[^>]*)\s+style="width:\s*auto;"([^>]*>)',
        r'\1 class="date-input-inline"\2',
        content,
        flags=re.IGNORECASE
    )
    
    # Combine class attributes if we added one
    content = re.sub(
        r'class="([^"]*)"\s+class="([^"]*)"',
        r'class="\1 \2"',
        content
    )
    
    return content

def process_file(file_path):
    """Process a single template file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply fixes
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
    
    # Add CSS classes first
    add_css_classes()
    
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





