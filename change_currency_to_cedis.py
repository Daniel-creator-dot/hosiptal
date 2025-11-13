"""
Change All Currency Symbols to Ghana Cedis (GH₵)
Updates all templates and Python files
"""

import os
import re

def replace_dollar_with_cedis(file_path):
    """Replace $ with GH₵ in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace ${{ with GHS {{ for template variables
        content = re.sub(r'\$\{\{', 'GHS {{', content)
        
        # Replace ${...} in f-strings with GHS {...}
        content = re.sub(r'f["\'].*?\$\{', lambda m: m.group(0).replace('${', 'GHS {'), content)
        
        # Replace standalone $ in strings
        content = re.sub(r'(["\'])(\s*)\$(\s*)', r'\1\2GHS \3', content)
        
        # Replace in print statements
        content = re.sub(r'print\([^)]*\$([0-9,.])', lambda m: m.group(0).replace('$', 'GHS '), content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def process_directory(directory):
    """Process all HTML and Python files in directory"""
    changed_files = []
    
    for root, dirs, files in os.walk(directory):
        # Skip migrations and static files
        if 'migrations' in root or 'static' in root or '__pycache__' in root:
            continue
        
        for file in files:
            if file.endswith(('.html', '.py', '.txt')):
                file_path = os.path.join(root, file)
                if replace_dollar_with_cedis(file_path):
                    changed_files.append(file_path)
    
    return changed_files


def main():
    print("="*70)
    print("CHANGING ALL CURRENCY TO GHANA CEDIS (GHS)")
    print("="*70)
    print()
    
    # Process hospital app
    hospital_dir = os.path.join(os.path.dirname(__file__), 'hospital')
    
    print("Processing templates and views...")
    changed_files = process_directory(hospital_dir)
    
    print()
    print(f"Modified {len(changed_files)} files")
    print()
    
    if changed_files:
        print("Changed files:")
        for file in changed_files[:20]:  # Show first 20
            print(f"  - {os.path.basename(file)}")
        if len(changed_files) > 20:
            print(f"  ... and {len(changed_files) - 20} more")
    
    print()
    print("="*70)
    print("CURRENCY CHANGED TO GHANA CEDIS!")
    print("="*70)
    print()
    print("All currency symbols changed to GHS (Ghana Cedis)")
    print()
    print("Refresh your browser to see GHS everywhere!")
    print()


if __name__ == '__main__':
    main()

