"""
Persistent domain model
=======================

An example originated from a question: "How to save state to disk?". There are many ways to
implement this, but you can get an insight of one possibility. This example implements a custom
domain model that persists it's state using a generic strategy that can be extended to any storage
format.

Original `issue <https://github.com/fgmacedo/python-statemachine/issues/358>`_.


Resource management state machine
---------------------------------

Given a simple on/off machine for resource management.

"""

import tempfile
from abc import ABC
from abc import abstractmethod

from statemachine import State
from statemachine import StateMachine


class ResourceManagement(StateMachine):
    power_off = State(initial=True)
    power_on = State()

    turn_on = power_off.to(power_on)
    shutdown = power_on.to(power_off)


# %%
# Abstract model with persistency protocol
# ----------------------------------------
#
# Abstract Base Class for persistent models.
# Subclasses should implement concrete strategies for:
#
# - `_read_state`: Read the state from the concrete persistent layer.
# - `_write_state`: Write the state from the concrete persistent layer.


class AbstractPersistentModel(ABC):
    """Abstract Base Class for persistent models.

    Subclasses should implement concrete strategies for:

    - `_read_state`: Read the state from the concrete persistent layer.
    - `_write_state`: Write the state from the concrete persistent layer.
    """

    def __init__(self):
        self._state = None

    def __repr__(self):
        return f"{type(self).__name__}(state={self.state})"

    @property
    def state(self):
        if self._state is None:
            self._state = self._read_state()
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        self._write_state(value)

    @abstractmethod
    def _read_state(self): ...

    @abstractmethod
    def _write_state(self, value): ...


# %%
# FilePersistentModel: Concrete model strategy
# --------------------------------------------
#
# A concrete implementation of the generic storage protocol above, that reads and writes to a file
# in plain text.


class FilePersistentModel(AbstractPersistentModel):
    """A concrete implementation of a storage strategy for a Model
    that reads and writes to a file.
    """

    def __init__(self, file):
        super().__init__()
        self.file = file

    def _read_state(self):
        self.file.seek(0)
        state = self.file.read().strip()
        return state if state != "" else None

    def _write_state(self, value):
        self.file.seek(0)
        self.file.truncate(0)
        self.file.write(value)


# %%
# Given a temporary file to store our state.

state_file = tempfile.TemporaryFile(mode="r+")

# %%
# Let's create instances and test the persistence.

model = FilePersistentModel(file=state_file)
sm = ResourceManagement(model=model)

print(f"Initial state: {sm.current_state.id}")

sm.send("turn_on")

print(f"State after transition: {sm.current_state.id}")

# %%
# Remove the instances from memory.

del sm
del model

# %%
# Restore the previous state from disk.

model = FilePersistentModel(file=state_file)
sm = ResourceManagement(model=model)

print(f"State restored from file system: {sm.current_state.id}")

# %%
# Closing the file (the temporary file will be removed).

state_file.close()
