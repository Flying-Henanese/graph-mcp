from archimedes.graph import build_project_graph, graph_to_json


def test_build_project_graph(tmp_path):
    # Setup a mock project
    src = tmp_path / "src"
    src.mkdir()

    # Base module
    base_file = src / "base.py"
    base_file.write_text("""
class BaseParser:
    pass
""")

    # Logger module
    logger_file = src / "logger.py"
    logger_file.write_text("""
def get_logger():
    pass
LOGGER_VERSION = "1.0"
""")

    # Main parser module
    parser_file = src / "parser.py"
    parser_file.write_text("""
import sys
from src.base import BaseParser
from src.logger import get_logger

class PDFParser(BaseParser):
    def process(self):
        log = get_logger()
        pass
""")

    files = [base_file, logger_file, parser_file]

    graph = build_project_graph(files, tmp_path)

    # 3 nodes should exist
    assert len(graph.node_indices()) == 3

    json_data = graph_to_json(graph)
    nodes = json_data["nodes"]
    edges = json_data["edges"]

    # Check Nodes and Exports
    parser_node = next(n for n in nodes if n["id"] == "src.parser")
    assert "PDFParser" in parser_node["exports"]["classes"]
    assert "process" in parser_node["exports"]["functions"]

    logger_node = next(n for n in nodes if n["id"] == "src.logger")
    assert "get_logger" in logger_node["exports"]["functions"]
    assert "LOGGER_VERSION" in logger_node["exports"]["variables"]

    # Check Edges
    assert len(edges) == 2

    # src.parser -> src.base
    edge_to_base = next(
        e for e in edges if e["source"] == "src.parser" and e["target"] == "src.base"
    )
    assert "BaseParser" in edge_to_base["data"]["interactions"][0]["imported_entities"]

    # src.parser -> src.logger
    edge_to_logger = next(
        e for e in edges if e["source"] == "src.parser" and e["target"] == "src.logger"
    )
    assert "get_logger" in edge_to_logger["data"]["interactions"][0]["imported_entities"]


def test_build_project_graph_resolves_relative_imports_and_packages(tmp_path):
    src = tmp_path / "src"
    src.mkdir()

    package = src / "pkg"
    package.mkdir()

    init_file = package / "__init__.py"
    init_file.write_text("PACKAGE_NAME = 'pkg'\n", encoding="utf-8")

    base_file = package / "base.py"
    base_file.write_text("class Base:\n    pass\n", encoding="utf-8")

    utils_file = package / "utils.py"
    utils_file.write_text("def helper():\n    pass\n", encoding="utf-8")

    consumer_file = package / "consumer.py"
    consumer_file.write_text(
        """
from .base import Base
from . import utils
from src.pkg.base import Base as BaseAgain
""",
        encoding="utf-8",
    )

    graph = build_project_graph(
        [init_file, base_file, utils_file, consumer_file],
        tmp_path,
    )

    json_data = graph_to_json(graph)
    nodes = json_data["nodes"]
    edges = json_data["edges"]

    assert {node["id"] for node in nodes} == {
        "src.pkg",
        "src.pkg.base",
        "src.pkg.consumer",
        "src.pkg.utils",
    }

    edge_to_base = next(
        e for e in edges if e["source"] == "src.pkg.consumer" and e["target"] == "src.pkg.base"
    )
    assert len(edge_to_base["data"]["interactions"]) == 2
    assert edge_to_base["data"]["interactions"][0]["callee"] == "src.pkg.base"
    assert "Base" in edge_to_base["data"]["interactions"][0]["imported_entities"]

    edge_to_utils = next(
        e for e in edges if e["source"] == "src.pkg.consumer" and e["target"] == "src.pkg.utils"
    )
    assert edge_to_utils["data"]["interactions"][0]["imported_entities"] == ["utils"]


def test_build_project_graph_resolves_src_layout_import_aliases(tmp_path):
    src = tmp_path / "src"
    package = src / "archimedes"
    package.mkdir(parents=True)

    init_file = package / "__init__.py"
    init_file.write_text("", encoding="utf-8")

    state_file = package / "state.py"
    state_file.write_text("state = object()\n", encoding="utf-8")

    server_file = package / "server.py"
    server_file.write_text(
        """
from archimedes.state import state
""",
        encoding="utf-8",
    )

    graph = build_project_graph([init_file, state_file, server_file], tmp_path)
    edges = graph_to_json(graph)["edges"]

    edge_to_state = next(
        e
        for e in edges
        if e["source"] == "src.archimedes.server" and e["target"] == "src.archimedes.state"
    )
    assert edge_to_state["data"]["interactions"][0]["callee"] == "src.archimedes.state"
    assert edge_to_state["data"]["interactions"][0]["imported_entities"] == ["state"]
