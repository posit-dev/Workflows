"""
Sanitize Python files to remove hardcoded credentials
"""
import os
import re
from pathlib import Path

def sanitize_file(filepath):
    """Replace hardcoded credentials with environment variables"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace hardcoded Snowflake account
    content = re.sub(
        r'"account":\s*"duloftf-posit-software-pbc-staging"',
        '"account": os.getenv("SNOWFLAKE_ACCOUNT", "your-account-identifier")',
        content
    )
    
    # Replace hardcoded username
    content = re.sub(
        r'"user":\s*"ASHLEIGH\.BYNUM\.POSIT\.CO"',
        '"user": os.getenv("SNOWFLAKE_USER", "your-username")',
        content
    )
    
    # Replace hardcoded warehouse
    content = re.sub(
        r'"warehouse":\s*"DEFAULT_WH"',
        '"warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH")',
        content
    )
    
    # Replace hardcoded role
    content = re.sub(
        r'"role":\s*"SOLENG"',
        '"role": os.getenv("SNOWFLAKE_ROLE", "your-role")',
        content
    )
    
    # Ensure os is imported
    if 'import os' not in content and content != original_content:
        # Add import at the top after docstring
        lines = content.split('\n')
        insert_pos = 0
        in_docstring = False
        
        for i, line in enumerate(lines):
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
            if not in_docstring and line.strip() and not line.strip().startswith('#'):
                if not line.startswith('import') and not line.startswith('from'):
                    insert_pos = i
                    break
        
        if insert_pos > 0:
            lines.insert(insert_pos, 'import os')
            content = '\n'.join(lines)
    
    # Write back if changed
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✓ Sanitized: {filepath}")
        return True
    else:
        print(f"- No changes: {filepath}")
        return False

def main():
    """Sanitize all Python files in the project"""
    python_files = []
    
    # Find all Python files
    for root, dirs, files in os.walk('.'):
        # Skip venv and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'venv']
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                python_files.append(filepath)
    
    print(f"Found {len(python_files)} Python files to sanitize\n")
    
    changed = 0
    for filepath in python_files:
        if sanitize_file(filepath):
            changed += 1
    
    print(f"\n✓ Sanitized {changed} files")
    print(f"- {len(python_files) - changed} files unchanged")

if __name__ == "__main__":
    main()
