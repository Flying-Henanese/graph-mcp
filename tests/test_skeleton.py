import pytest
from archimedes.skeleton import get_structural_code

def test_basic_function_stripping():
    code = """
def hello(name: str):
    print(f"Hello {name}")
    return True
"""
    skeleton = get_structural_code(code)
    assert "def hello(name: str):" in skeleton
    assert "pass" in skeleton
    assert "print" not in skeleton

def test_docstring_preservation():
    code = """
def api_call(url: str):
    \"\"\"Performs an API call.\"\"\"
    response = requests.get(url)
    return response.json()
"""
    skeleton = get_structural_code(code)
    assert "def api_call(url: str):" in skeleton
    assert '"""Performs an API call."""' in skeleton
    assert "pass" in skeleton
    assert "requests.get" not in skeleton

def test_async_function():
    code = """
async def fetch_data():
    await asyncio.sleep(1)
    return {"data": 123}
"""
    skeleton = get_structural_code(code)
    assert "async def fetch_data():" in skeleton
    assert "pass" in skeleton
    assert "await" not in skeleton

def test_class_definition():
    code = """
class MyService:
    \"\"\"Service class.\"\"\"
    def __init__(self, db):
        self.db = db
        
    async def get_user(self, user_id):
        return await self.db.find(user_id)
"""
    skeleton = get_structural_code(code)
    assert "class MyService:" in skeleton
    assert '"""Service class."""' in skeleton
    assert "def __init__(self, db):" in skeleton
    assert "async def get_user(self, user_id):" in skeleton
    assert "pass" in skeleton
    assert "self.db = db" not in skeleton

def test_syntax_error_handling():
    code = "def incomplete_func("
    skeleton = get_structural_code(code)
    assert "[Error] Unable to parse syntax" in skeleton

def test_nested_functions():
    code = """
def outer():
    def inner():
        print("inner")
    inner()
"""
    skeleton = get_structural_code(code)
    assert "def outer():" in skeleton
    assert "def inner():" in skeleton
    assert "pass" in skeleton
    assert "print" not in skeleton
