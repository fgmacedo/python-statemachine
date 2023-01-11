# coding: utf-8
from .exceptions import AttrNotFound
from .exceptions import InvalidDefinition
from .utils import ensure_iterable
from .utils import ugettext as _


class CallbackWrapper(object):
    """A thin wrapper that ensures the targef callback is a proper callable.

    At first, `func` can be a string or a callable, and even if it's already
    a callable, his signature can mismatch.

    After instantiation, `.setup(resolver)` must be called before any real
    call is performed, to allow the proper callback resolution.
    """

    def __init__(self, func, suppress_errors=False):
        self.func = func
        self.suppress_errors = suppress_errors
        self._callback = None

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.func)

    def __eq__(self, other):
        return self.func == getattr(other, "func", other)

    def __hash__(self):
        return id(self)

    def _update_func(self, func):
        self.func = func

    def setup(self, resolver):
        """
        Resolves the `func` into a usable callable.

        Args:
            resolver (callable): A method responsible to build and return a valid callable that
                can receive arbitrary parameters like `*args, **kwargs`.
        """
        try:
            self._callback = resolver(self.func)
            return True
        except AttrNotFound:
            if not self.suppress_errors:
                raise
            return False

    def __call__(self, *args, **kwargs):
        if self._callback is None:
            raise InvalidDefinition(
                _("Callback {!r} not property configured.").format(self)
            )
        return self._callback(*args, **kwargs)


class ConditionWrapper(CallbackWrapper):
    def __init__(self, func, suppress_errors=False, expected_value=True):
        super(ConditionWrapper, self).__init__(func, suppress_errors)
        self.expected_value = expected_value

    def __call__(self, *args, **kwargs):
        return (
            super(ConditionWrapper, self).__call__(*args, **kwargs)
            == self.expected_value
        )


class Callbacks(object):
    def __init__(self, resolver=None, factory=CallbackWrapper):
        self.items = []
        self._resolver = resolver
        self.factory = factory

    def __repr__(self):
        return "{}({!r}, factory={!r})".format(
            type(self).__name__, self.items, self.factory
        )

    def setup(self, resolver):
        """Validate configuracions"""
        self._resolver = resolver
        self.items = [
            callback for callback in self.items if callback.setup(self._resolver)
        ]

    def _add_unbounded_callback(self, func, is_event=False, transitions=None):
        """This list was a targed for adding a func using decorator
        `@<state|event>[.on|before|after|enter|exit]` syntax.

        If we assign ``func`` directly as callable on the ``items`` list,
        this will result in an `unbounded method error`, with `func` expecting a parameter
        ``self`` not defined.

        The implemented solution is to resolve the colision giving the func a reference method.
        To update It's callback when the name is resolved on the
        :func:`StateMachineMetaclass.add_from_attributes`.
        If the ``func`` is bounded It will be used directly, if not, it's ref will be replaced
        by the given attr name and on `statemachine._setup()` the dynamic name will be resolved
        properly.

        Args:
            func (callable): The decorated method to add on the transitions occurs.
            is_event (bool): If the func is also an event, we'll create a trigger and link the
                event name to the transitions.
            transitions (TransitionList): If ``is_event``, the transitions to be attached to the
                event.

        """
        callback = self._add(func)
        if not getattr(func, "_callbacks_to_update", None):
            func._callbacks_to_update = set()
        func._callbacks_to_update.add(callback._update_func)
        func._is_event = is_event
        func._transitions = transitions

        return func

    def __call__(self, callback):
        return self._add_unbounded_callback(callback)

    def __iter__(self):
        return iter(self.items)

    def clear(self):
        self.items = []

    def call(self, *args, **kwargs):
        return [callback(*args, **kwargs) for callback in self.items]

    def _add(self, func, resolver=None, prepend=False, **kwargs):
        if func in self.items:
            return

        resolver = resolver or self._resolver

        callback = self.factory(func, **kwargs)
        if resolver is not None and not callback.setup(resolver):
            return

        if prepend:
            self.items.insert(0, callback)
        else:
            self.items.append(callback)
        return callback

    def add(self, callbacks, **kwargs):
        if callbacks is None:
            return self

        unprepared = ensure_iterable(callbacks)
        for func in unprepared:
            self._add(func, **kwargs)

        return self
