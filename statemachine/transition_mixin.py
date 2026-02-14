from typing import Any
from typing import Callable
from typing import TypeVar

from .callbacks import CallbackGroup
from .i18n import _

T = TypeVar("T", bound=Callable)


class AddCallbacksMixin:
    def _add_callback(self, callback: T, grouper: CallbackGroup, is_event=False, **kwargs) -> T:
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> Any:
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return self._add_callback(args[0], CallbackGroup.ON, is_event=True)
        raise TypeError(
            _("{} only supports the decorator syntax to register callbacks.").format(
                type(self).__name__
            )
        )

    def before(self, f: Callable):
        """Adds a ``before`` :ref:`transition actions` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``before`` :ref:`transition actions` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, CallbackGroup.BEFORE)

    def after(self, f: Callable):
        """Adds a ``after`` :ref:`transition actions` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``after`` :ref:`transition actions` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, CallbackGroup.AFTER)

    def on(self, f: Callable):
        """Adds a ``on`` :ref:`transition actions` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``on`` :ref:`transition actions` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, CallbackGroup.ON)

    def cond(self, f: Callable):
        """Adds a ``cond`` :ref:`guards` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``cond`` :ref:`guards` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, CallbackGroup.COND, expected_value=True)

    def unless(self, f: Callable):
        """Adds a ``unless`` :ref:`guards` callback with expected value ``False`` to every
        :ref:`transition` in the :ref:`TransitionList` instance.

        Args:
            f: The ``unless`` :ref:`guards` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, CallbackGroup.COND, expected_value=False)

    def validators(self, f: Callable):
        """Adds a :ref:`validators` callback to the :ref:`TransitionList` instance.

        Args:
            f: The ``validators`` callback function to be added.
        Returns:
            The callback function.

        """
        return self._add_callback(f, CallbackGroup.VALIDATOR)
