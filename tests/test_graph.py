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
