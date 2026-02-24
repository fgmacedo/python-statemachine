"""
AI Shell -- coding assistant
=============================

A feature-rich coding assistant powered by python-statemachine.

A standalone interactive CLI that uses the OpenAI SDK for LLM calls with
tool_use. Demonstrates **parallel states**, **compound states**,
**HistoryState**, **eventless transitions**, **In() guards**,
**done.state**, **error.execution**, **invoke**, and **raise_()** — all
working together in a practical application.

.. warning::

    This example grants an LLM the ability to read files, list directories,
    and execute shell commands — which can be very useful for exploring a
    codebase, running tests, or automating tasks. However, the actual behavior
    depends on the prompts you send and the model you use, and unintended
    actions (e.g., deleting files or exposing credentials) are possible.

    **Use at your own risk.** This code is provided for educational and
    demonstration purposes only. The authors and contributors of
    python-statemachine accept no liability for any damage or data loss.
    Consider running it in an isolated environment (e.g., a container or
    virtual machine) and avoid using elevated privileges.

Usage::

    # Standalone (installs deps from PyPI)
    OPENAI_API_KEY=sk-... uv run examples/ai_shell.py

    # From the repo (uses local statemachine)
    OPENAI_API_KEY=sk-... uv run --with openai python examples/ai_shell.py

    # Debug mode — shows engine macro/micro step log on stderr
    OPENAI_API_KEY=sk-... uv run --with openai python examples/ai_shell.py -v

"""
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "openai",
#     "python-statemachine",
# ]
# ///

import itertools
import json
import logging
import os
import random
import subprocess
import sys
import threading

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart

if "-v" in sys.argv or "--verbose" in sys.argv:
    logging.basicConfig(level=logging.DEBUG, format="%(name)s  %(message)s", stream=sys.stderr)

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file at the given path. "
                "Returns the file contents (truncated to 10 000 characters)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path. Defaults to '.' (current directory).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command and return its stdout and stderr. "
                "Commands are executed with a 30-second timeout."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                },
                "required": ["command"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a helpful coding assistant. You can read files, list directory contents, "
    "and run shell commands to help the user with their tasks. Be concise and practical. "
    "You also have tools to introspect the state machine that powers this shell — use them "
    "when the user asks about the current state, allowed transitions, or other metadata."
)

MAX_FILE_CHARS = 10_000
COMMAND_TIMEOUT = 30
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Spinner animation
# ---------------------------------------------------------------------------

SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

SPINNER_MESSAGES = [
    "thinking...",
    "contemplating...",
    "cooking something up...",
    "making something special...",
    "crunching the data...",
    "pondering...",
    "culminating...",
    "brewing ideas...",
    "connecting the dots...",
    "almost there...",
]


class Spinner:
    """Animated terminal spinner shown while the LLM is working."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread: "threading.Thread | None" = None

    def __enter__(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run(self):
        messages = SPINNER_MESSAGES[:]
        random.shuffle(messages)
        msg_cycle = itertools.cycle(messages)
        char_cycle = itertools.cycle(SPINNER_CHARS)
        msg = next(msg_cycle)
        tick = 0
        while not self._stop.wait(timeout=0.08):
            char = next(char_cycle)
            if tick > 0 and tick % 30 == 0:
                msg = next(msg_cycle)
            line = f"  {char} {msg}"
            print(f"\r{line:<50}", end="", flush=True)
            tick += 1
        print(f"\r{'':50}\r", end="", flush=True)


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _tool_read_file(input_data: dict) -> str:
    path = input_data["path"]
    try:
        with open(path) as f:
            content = f.read(MAX_FILE_CHARS + 1)
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n... (truncated)"
        return content
    except OSError as e:
        return f"Error reading file: {e}"


def _tool_list_files(input_data: dict) -> str:
    path = input_data.get("path", ".")
    try:
        entries = sorted(os.listdir(path))
        return "\n".join(entries)
    except OSError as e:
        return f"Error listing directory: {e}"


def _tool_run_command(input_data: dict) -> str:
    command = input_data["command"]
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("" if not output else "\n") + f"stderr: {result.stderr}"
        if result.returncode != 0:
            output += f"\n(exit code {result.returncode})"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {COMMAND_TIMEOUT}s"
    except OSError as e:
        return f"Error running command: {e}"


TOOL_HANDLERS = {
    "read_file": _tool_read_file,
    "list_files": _tool_list_files,
    "run_command": _tool_run_command,
}


# ---------------------------------------------------------------------------
# State machine introspection tools
# ---------------------------------------------------------------------------


def _tool_sm_configuration(sm, input_data: dict) -> str:
    states = sorted(sm.configuration_values)
    return json.dumps({"active_states": states})


def _tool_sm_enabled_events(sm, input_data: dict) -> str:
    events = sorted({e.name for e in sm.enabled_events()})
    return json.dumps({"enabled_events": events})


def _tool_sm_macrostep_count(sm, input_data: dict) -> str:
    return json.dumps({"macrostep_count": sm._engine._macrostep_count})


def _tool_sm_states(sm, input_data: dict) -> str:
    all_states = sorted(sm.states_map.keys())
    return json.dumps({"all_states": all_states})


SM_TOOL_HANDLERS = {
    "sm_configuration": _tool_sm_configuration,
    "sm_enabled_events": _tool_sm_enabled_events,
    "sm_macrostep_count": _tool_sm_macrostep_count,
    "sm_states": _tool_sm_states,
}

SM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sm_configuration",
            "description": (
                "Get the current active states (configuration) of the state machine. "
                "Returns which states are currently active."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sm_enabled_events",
            "description": (
                "List events (transitions) that can be triggered from the current "
                "state machine configuration, considering guard conditions."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sm_macrostep_count",
            "description": (
                "Get the current macrostep counter of the state machine engine. "
                "A macrostep is the full processing cycle for one external event."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sm_states",
            "description": (
                "List all states defined in the state machine, including nested states "
                "inside compound and parallel states."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def execute_tool(name: str, input_data: dict, sm=None) -> str:
    sm_handler = SM_TOOL_HANDLERS.get(name)
    if sm_handler is not None:
        return sm_handler(sm, input_data)
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    return handler(input_data)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

GOODBYE_WORDS = {"bye", "exit", "quit"}


class AIShell(StateChart):
    """An agentic coding assistant as a StateChart.

    Demonstrates parallel states, compound states, HistoryState, eventless
    transitions, In() guards, done.state, error.execution, invoke, and
    raise_() — all in a practical application.

    States::

        session (Parallel)
        ├── conversation (Compound)
        │   ├── idle (initial)
        │   ├── processing (Compound)
        │   │   ├── thinking (initial, invoke) ← API call + spinner
        │   │   ├── using_tool (invoke) ← tool execution
        │   │   ├── done (final)
        │   │   └── h = HistoryState(deep) ← for error retry
        │   ├── responding
        │   ├── recovering ← error.execution handler
        │   └── conversation_ended (final)
        └── context_tracker (Compound)
            ├── fresh (initial)
            ├── active (≥4 messages)
            ├── deep (≥20 messages, shows warning)
            └── tracker_done (final)

    """

    catch_errors_as_events = True

    # --- Top-level parallel state: two independent regions ---

    class session(State.Parallel):
        class conversation(State.Compound):
            idle = State("Idle", initial=True)

            class processing(State.Compound):
                thinking = State("Thinking", initial=True)
                using_tool = State("Using Tool")
                done = State("Done", final=True)
                h = HistoryState(type="deep")

                # Invoke results route automatically
                done_invoke_thinking = thinking.to(
                    using_tool, cond="has_tool_calls"
                ) | thinking.to(done)
                done_invoke_using_tool = using_tool.to(thinking)

            responding = State("Responding")
            recovering = State("Recovering")
            conversation_ended = State("Ended", final=True)

            # Named events
            user_message = idle.to(processing, cond="is_not_goodbye") | idle.to(
                conversation_ended, cond="is_goodbye"
            )
            done_state_processing = processing.to(responding)
            error_execution = processing.to(recovering)

            # Eventless transitions
            responding.to(idle)
            recovering.to(processing.h, cond="can_retry")
            recovering.to(idle, cond="cannot_retry")

        class context_tracker(State.Compound):
            fresh = State("Fresh", initial=True)
            active = State("Active")
            deep = State("Deep")
            tracker_done = State(final=True)

            # Eventless: track conversation depth
            fresh.to(active, cond="is_active_context")
            active.to(deep, cond="is_deep_context")

            # Eventless + In() guard: follow conversation end
            fresh.to(tracker_done, cond="In('conversation_ended')")
            active.to(tracker_done, cond="In('conversation_ended')")
            deep.to(tracker_done, cond="In('conversation_ended')")

    # --- Initialization ---

    def __init__(self):
        from openai import OpenAI  # type: ignore[import-not-found]

        self.client = OpenAI()
        self.messages: list = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._last_text: str = ""
        self._retries: int = 0
        self._ready = threading.Event()
        super().__init__()

    # --- Guards ---

    def is_goodbye(self, text="", **kwargs) -> bool:
        return text.strip().lower() in GOODBYE_WORDS

    def is_not_goodbye(self, text="", **kwargs) -> bool:
        return not self.is_goodbye(text=text)

    def can_retry(self, **kwargs) -> bool:
        return self._retries < MAX_RETRIES

    def cannot_retry(self, **kwargs) -> bool:
        return not self.can_retry()

    def is_active_context(self, **kwargs) -> bool:
        return len(self.messages) >= 5

    def is_deep_context(self, **kwargs) -> bool:
        return len(self.messages) >= 20

    # --- Callbacks ---

    def on_user_message(self, text, **kwargs):
        """Append the user's message to conversation history."""
        self.messages.append({"role": "user", "content": text})

    def has_tool_calls(self, data=None, **kwargs) -> bool:
        """Guard: check if the API response contains tool calls."""
        return bool(getattr(data, "tool_calls", None))

    def on_invoke_thinking(self, **kwargs):
        """Call the OpenAI API with a spinner animation. Returns the message."""
        with Spinner():
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.messages,
                tools=TOOLS + SM_TOOLS,
            )

        message = response.choices[0].message
        self.messages.append(message)

        if not message.tool_calls:
            self._last_text = message.content or ""

        return message

    def on_invoke_using_tool(self, data, **kwargs):
        """Execute tool calls from the API response."""
        for call in data.tool_calls:
            args = json.loads(call.function.arguments)
            print(f"  [tool] {call.function.name}({json.dumps(args)})")
            result = execute_tool(call.function.name, args, sm=self)
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

    def on_enter_responding(self, **kwargs):
        """Print the assistant's text response."""
        if self._last_text:
            print(f"\n{self._last_text}")
            self._last_text = ""

    def on_enter_idle(self, **kwargs):
        """Reset retry counter and signal readiness when returning to idle."""
        self._retries = 0
        self._ready.set()

    def on_enter_recovering(self, **kwargs):
        """Handle API errors with retry logic (via error.execution)."""
        self._retries += 1
        if self._retries < MAX_RETRIES:
            print(f"\n  [error] API call failed, retrying ({self._retries}/{MAX_RETRIES})...")
        else:
            print(f"\n  [error] API call failed after {MAX_RETRIES} attempts. Giving up.")

    def on_enter_deep(self, **kwargs):
        """Warn when conversation context is getting long."""
        print("  [context] Conversation is getting long — responses may degrade.")

    def on_enter_conversation_ended(self, **kwargs):
        print("\nGoodbye!")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def _check_openai():
    """Return True if the openai package is available."""
    try:
        import openai  # noqa: F401

        return True
    except ImportError:
        return False


def main():
    if not _check_openai():
        print("This example requires the 'openai' package.")
        print("Install it with: pip install openai")
        return

    print("AI Shell")
    print("A coding assistant powered by python-statemachine + OpenAI.")
    print("Type 'bye', 'exit', or 'quit' to end. Ctrl+C to interrupt.")
    if "-v" in sys.argv or "--verbose" in sys.argv:
        print("Debug mode enabled — engine log is written to stderr.\n")
    else:
        print("Tip: run with -v to see engine macro/micro step debug log.\n")

    try:
        sm = AIShell()
    except Exception as e:
        sys.exit(f"Error initializing: {e}")

    while not sm.is_terminated:
        sm._ready.wait()
        sm._ready.clear()
        try:
            text = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.strip():
            sm.send("user_message", text=text)


if __name__ == "__main__" and "sphinx" not in sys.modules:  # pragma: no cover
    main()
