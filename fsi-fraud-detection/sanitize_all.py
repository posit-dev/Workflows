"""
Comprehensive sanitization of all Python files
"""
import os
import re
from pathlib import Path

def sanitize_file(filepath):
    """Replace all hardcoded credentials with environment variables"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    changes = []
    
    # Replace all variations of Snowflake account
    patterns = [
        (r'duloftf-posit-software-pbc-staging', 'SNOWFLAKE_ACCOUNT'),
        (r'"duloftf-posit-software-pbc-staging"', 'os.getenv("SNOWFLAKE_ACCOUNT", "your-account-identifier")'),
        (r"'duloftf-posit-software-pbc-staging'", 'os.getenv("SNOWFLAKE_ACCOUNT", "your-account-identifier")'),
    ]
    
    for pattern, replacement in patterns:
        if pattern in content:
            if 'os.getenv' in replacement:
                content = content.replace(f'"{pattern}"', replacement)
                content = content.replace(f"'{pattern}'", replacement)
            changes.append(f"  - Replaced {pattern}")
    
    # Replace all variations of username
    username_patterns = [
        r'ASHLEIGH\.BYNUM\.POSIT\.CO',
        r'ASHLEIGH\.BYNUM@POSIT\.CO',
        r'ashleigh\.bynum\.posit\.co',
        r'ashleigh\.bynum@posit\.co',
    ]
    
    for pattern in username_patterns:
        # Case insensitive replacement
        content = re.sub(
            pattern,
            'os.getenv("SNOWFLAKE_USER", "your-username")',
            content,
            flags=re.IGNORECASE
        )
        # Also handle quoted versions
        content = re.sub(
            f'"{pattern}"',
            'os.getenv("SNOWFLAKE_USER", "your-username")',
            content,
            flags=re.IGNORECASE
        )
        content = re.sub(
            f"'{pattern}'",
            'os.getenv("SNOWFLAKE_USER", "your-username")',
            content,
            flags=re.IGNORECASE
        )
    
    # Replace hardcoded role
    content = re.sub(
        r'"role":\s*"SOLENG"',
        '"role": os.getenv("SNOWFLAKE_ROLE", "your-role")',
        content
    )
    content = re.sub(
        r"'role':\s*'SOLENG'",
        '"role": os.getenv("SNOWFLAKE_ROLE", "your-role")',
        content
    )
    
    # Replace hardcoded warehouse
    content = re.sub(
        r'"warehouse":\s*"DEFAULT_WH"',
        '"warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH")',
        content
    )
    
    # Ensure os is imported if we made changes
    if content != original_content:
        if 'import os' not in content:
            # Find the first import or the first non-comment line
            lines = content.split('\n')
            insert_pos = 0
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Skip docstrings and comments
                if stripped and not stripped.startswith('#') and '"""' not in stripped and "'''" not in stripped:
                    if stripped.startswith('import') or stripped.startswith('from'):
                        # Insert after existing imports
                        insert_pos = i + 1
                    else:
                        # Insert before first non-import line
                        insert_pos = i
                        break
            
            lines.insert(insert_pos, 'import os')
            content = '\n'.join(lines)
            changes.append("  - Added 'import os'")
    
    # Write back if changed
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✓ Sanitized: {filepath}")
        for change in changes:
            print(change)
        return True
    else:
        print(f"- No changes needed: {filepath}")
        return False

def main():
    """Sanitize all Python files in the project"""
    python_files = []
    
    # Find all Python files
    for root, dirs, files in os.walk('.'):
        # Skip venv and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'venv' and d != '__pycache__']
        
        for file in files:
            if file.endswith('.py') and file != 'sanitize_all.py':
                filepath = os.path.join(root, file)
                python_files.append(filepath)
    
    print(f"Found {len(python_files)} Python files to sanitize\n")
    print("=" * 70)
    
    changed = 0
    for filepath in python_files:
        if sanitize_file(filepath):
            changed += 1
        print()
    
    print("=" * 70)
    print(f"\n✓ Sanitized {changed} files")
    print(f"- {len(python_files) - changed} files unchanged")
    
    # Verify no credentials remain
    print("\n" + "=" * 70)
    print("Verification: Checking for remaining hardcoded credentials...")
    print("=" * 70)
    
    issues = []
    for filepath in python_files:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Check for any remaining credentials
        if 'duloftf' in content.lower():
            issues.append(f"{filepath}: Contains 'duloftf'")
        if 'ashleigh' in content.lower():
            issues.append(f"{filepath}: Contains 'ashleigh'")
        if 'SOLENG' in content and 'os.getenv' not in content:
            issues.append(f"{filepath}: Contains hardcoded 'SOLENG'")
    
    if issues:
        print("\n⚠ WARNING: Found remaining hardcoded values:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✓ All credentials successfully sanitized!")

if __name__ == "__main__":
    main()
