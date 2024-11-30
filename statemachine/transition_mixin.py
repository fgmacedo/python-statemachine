from typing import Callable

from .callbacks import CallbackGroup


class AddCallbacksMixin:
    def _add_callback(self, callback, grouper: CallbackGroup, is_event=False, **kwargs):
        raise NotImplementedError

    def __call__(self, f):
        return self._add_callback(f, CallbackGroup.ON, is_event=True)

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
