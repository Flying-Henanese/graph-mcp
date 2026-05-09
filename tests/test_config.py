
import pytest
import yaml

from archimedes.config import load_config, scan_files


@pytest.fixture
def temp_project(tmp_path):
    # Create a mock project structure
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('main')")
    (src / "utils.py").write_text("print('utils')")

    internal = src / "internal"
    internal.mkdir()
    (internal / "secret.py").write_text("print('secret')")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("print('test')")

    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "lib.py").write_text("print('lib')")

    config = {
        "indexing": {
            "include": ["src/**/*.py"],
            "exclude": ["tests/**", "venv/**", "**/internal/**"]
        }
    }
    config_file = tmp_path / "archimedes.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    return tmp_path, config_file

def test_load_config(temp_project):
    tmp_path, config_file = temp_project
    config = load_config(str(config_file))
    assert "src/**/*.py" in config["include"]
    assert "tests/**" in config["exclude"]

def test_scan_files_with_excludes(temp_project):
    tmp_path, config_file = temp_project
    files = scan_files(str(tmp_path), str(config_file))

    file_names = [f.name for f in files]
    assert "main.py" in file_names
    assert "utils.py" in file_names
    assert "test_main.py" not in file_names
    assert "lib.py" not in file_names
    assert "secret.py" not in file_names

def test_scan_files_no_config(tmp_path):
    # Should use defaults
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("pass")

    files = scan_files(str(tmp_path), "non_existent.yaml")
    file_names = [f.name for f in files]
    assert "app.py" in file_names
