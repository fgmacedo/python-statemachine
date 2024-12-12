import traceback
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from statemachine import State
from statemachine import StateMachine
from statemachine.event import Event
from statemachine.io.scxml.processor import SCXMLProcessor

"""
Test cases as defined by W3C SCXML Test Suite

- https://www.w3.org/Voice/2013/scxml-irp/
- https://alexzhornyak.github.io/SCXML-tutorial/Tests/ecma/W3C/Mandatory/Auto/report__USCXML_2_0_0___msvc2015_32bit__Win7_1.html
- https://github.com/alexzhornyak/PyBlendSCXML/tree/master/w3c_tests
- https://github.com/jbeard4/SCION/wiki/Pseudocode-for-SCION-step-algorithm

"""  # noqa: E501


@dataclass(frozen=True, unsafe_hash=True, kw_only=True)
class DebugEvent:
    source: str
    event: str
    data: str
    target: str


@dataclass(frozen=True, unsafe_hash=True, kw_only=True)
class DebugListener:
    events: list[DebugEvent] = field(default_factory=list)

    def on_transition(self, event: Event, source: State, target: State, event_data):
        self.events.append(
            DebugEvent(
                source=f"{source and source.id}",
                event=f"{event and event.id}",
                data=f"{event_data.trigger_data.kwargs}",
                target=f"{target.id}",
            )
        )


@dataclass(kw_only=True)
class FailedMark:
    reason: str
    events: list[DebugEvent]
    is_assertion_error: bool
    exception: Exception
    logs: str
    configuration: list[str] = field(default_factory=list)

    @staticmethod
    def _get_header(report: str) -> str:
        header_end_index = report.find("---")
        return report[:header_end_index]

    def write_fail_markdown(self, testcase_path: Path):
        fail_file_path = testcase_path.with_suffix(".fail.md")
        if not self.is_assertion_error:
            exception_traceback = "".join(
                traceback.format_exception(
                    type(self.exception), self.exception, self.exception.__traceback__
                )
            )
        else:
            exception_traceback = "Assertion of the testcase failed."

        report = """# Testcase: {testcase_path.stem}

{reason}

Final configuration: `{configuration}`

---

## Logs
```py
{logs}
```

## "On transition" events
```py
{events}
```

## Traceback
```py
{exception_traceback}
```
""".format(
            testcase_path=testcase_path,
            reason=self.reason,
            configuration=self.configuration if self.configuration else "No configuration",
            logs=self.logs if self.logs else "No logs",
            events="\n".join(map(repr, self.events)) if self.events else "No events",
            exception_traceback=exception_traceback,
        )

        if fail_file_path.exists():
            last_report = fail_file_path.read_text()

            if self._get_header(report) == self._get_header(last_report):
                return

        with fail_file_path.open("w") as fail_file:
            fail_file.write(report)


def test_scxml_usecase(testcase_path: Path, caplog):
    # from statemachine.contrib.diagram import DotGraphMachine

    # DotGraphMachine(sm_class).get_graph().write_png(
    #     testcase_path.parent / f"{testcase_path.stem}.png"
    # )
    sm: "StateMachine | None" = None
    try:
        debug = DebugListener()
        processor = SCXMLProcessor()
        processor.parse_scxml_file(testcase_path)

        sm = processor.start(listeners=[debug])
        assert isinstance(sm, StateMachine)
        assert "pass" in {s.id for s in sm.configuration}, debug
    except Exception as e:
        # Import necessary module
        reason = f"{e.__class__.__name__}: {e.__class__.__doc__}"
        is_assertion_error = isinstance(e, AssertionError)
        fail_mark = FailedMark(
            reason=reason,
            is_assertion_error=is_assertion_error,
            events=debug.events,
            exception=e,
            logs=caplog.text,
            configuration=[s.id for s in sm.configuration] if sm else [],
        )
        fail_mark.write_fail_markdown(testcase_path)
        raise
