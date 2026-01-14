#!/bin/bash
# デプロイ前のビルドエラーチェックスクリプト

set -e

echo "🔍 デプロイ前ビルドエラーチェックを開始..."

# 1. 構文チェック
echo "📝 構文チェック中..."
python3 -m py_compile database_config.py app.py || {
    echo "❌ 構文エラーが検出されました"
    exit 1
}
echo "✅ 構文チェック: OK"

# 2. Python AST解析チェック
echo "🔬 AST解析チェック中..."
python3 << 'PYTHON_EOF'
import ast
import sys

def check_file(filename):
    try:
        with open(filename, 'r') as f:
            code = f.read()
        ast.parse(code)
        return True
    except SyntaxError as e:
        print(f"❌ {filename}: 構文エラー - {e}")
        return False

files = ['database_config.py', 'app.py']
all_ok = True
for f in files:
    if not check_file(f):
        all_ok = False

if not all_ok:
    sys.exit(1)
print("✅ AST解析チェック: OK")
PYTHON_EOF

# 3. 主要な関数定義チェック
echo "🔍 関数定義チェック中..."
python3 << 'PYTHON_EOF'
import ast
import sys

def check_function_definitions(filename):
    with open(filename, 'r') as f:
        code = f.read()
    tree = ast.parse(code)
    
    defined_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined_functions.add(node.name)
    
    return defined_functions

db_funcs = check_function_definitions('database_config.py')
app_funcs = check_function_definitions('app.py')

important_functions = {
    'database_config.py': ['_get_connection_pool', 'get_connection', '_execute_with_retry', 'connect', '__init__'],
    'app.py': ['create_app', 'check_database_health']
}

all_ok = True
for file, required in important_functions.items():
    funcs = db_funcs if 'database_config' in file else app_funcs
    missing = [f for f in required if f not in funcs]
    if missing:
        print(f"❌ {file}: 未定義の関数 - {', '.join(missing)}")
        all_ok = False

if not all_ok:
    sys.exit(1)
print("✅ 関数定義チェック: OK")
PYTHON_EOF

# 4. インポート文チェック
echo "📦 インポート文チェック中..."
python3 << 'PYTHON_EOF'
import ast
import sys

def check_imports(filename):
    with open(filename, 'r') as f:
        code = f.read()
    tree = ast.parse(code)
    
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
    
    return imports

db_imports = check_imports('database_config.py')
has_pool = any('pool' in imp for imp in db_imports)
has_contextmanager = any('contextmanager' in imp for imp in db_imports)

if not (has_pool and has_contextmanager):
    print(f"❌ database_config.py: 必要なインポートが不足 - pool={has_pool}, contextmanager={has_contextmanager}")
    sys.exit(1)
print("✅ インポート文チェック: OK")
PYTHON_EOF

echo ""
echo "✅ すべてのビルドエラーチェックが完了しました"
echo "🚀 デプロイ可能です"
