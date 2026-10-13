"""Issue #649: ``run_graphviz`` errors that need no Graphviz installed."""

import subprocess
import sys

import pytest
from statemachine.contrib.diagram import main


class TestGraphvizWithoutDot:
    _QUALNAME = "tests.examples.traffic_light_machine.TrafficLightMachine"

    def test_run_graphviz_without_stderr_output(self, monkeypatch):
        from statemachine.contrib.diagram import GraphvizError
        from statemachine.contrib.diagram.graphviz import run_graphviz

        monkeypatch.setattr(
            "subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(args, 3, b"", b""),
        )

        with pytest.raises(GraphvizError, match=r"dot -Tpng failed with exit code 3\.$"):
            run_graphviz("digraph {}", "png")

    def test_run_graphviz_terminated_by_signal(self, monkeypatch):
        from statemachine.contrib.diagram import GraphvizError
        from statemachine.contrib.diagram.graphviz import run_graphviz

        monkeypatch.setattr(
            "subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(args, -9, b"", b"killed"),
        )

        with pytest.raises(GraphvizError, match=r"dot -Tsvg was terminated by signal 9\.\nkilled"):
            run_graphviz("digraph {}", "svg")

    def test_run_graphviz_without_dot_in_path(self, monkeypatch, tmp_path):
        from statemachine.contrib.diagram import GraphvizError
        from statemachine.contrib.diagram.graphviz import run_graphviz

        monkeypatch.setenv("PATH", str(tmp_path))

        with pytest.raises(GraphvizError, match="'dot' not found in PATH") as excinfo:
            run_graphviz("digraph {}", "svg")

        assert "graphviz.org/download" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, FileNotFoundError)

    @pytest.mark.skipif(sys.platform == "win32", reason="file mode bits are POSIX only")
    def test_run_graphviz_with_dot_that_cannot_run(self, monkeypatch, tmp_path):
        from statemachine.contrib.diagram import GraphvizError
        from statemachine.contrib.diagram.graphviz import run_graphviz

        (tmp_path / "dot").write_text("")
        monkeypatch.setenv("PATH", str(tmp_path))

        with pytest.raises(GraphvizError, match="'dot' could not be run: .*Permission denied"):
            run_graphviz("digraph {}", "svg")

    def test_graphviz_error_is_a_statemachine_error(self):
        from statemachine.contrib.diagram import GraphvizError
        from statemachine.exceptions import StateMachineError

        assert issubclass(GraphvizError, StateMachineError)

    def test_write_image_raw_writes_dot_source_without_running_dot(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATH", str(tmp_path))
        out = tmp_path / "sm.raw"

        main([self._QUALNAME, str(out)])

        assert out.read_text(encoding="utf-8").startswith("digraph TrafficLightMachine {")
