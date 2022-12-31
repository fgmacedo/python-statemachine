class CallableInstance(object):
    """
    Proxy that can override params by passing in kwargs and can run a callable.

    When a user wants to call a transition from the state machine, the instance
    of the state machine is only know at the __get__ method of the transition,
    since it's a property descriptor.

    To allow concurrency, we cannot store the current instance in the
    descriptor, as it permits only one instance to call a transition  at a
    time.

    The CallableInstance is a proxy that acts like the original object, but has
    a __call__ method that can run a lambda function.

    And you can customize/override any attr by defining **kwargs.
    """

    def __init__(self, target, func, **kwargs):
        self.__dict__["target"] = target
        self.__dict__["func"] = func
        self.__dict__["kwargs"] = kwargs
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def __getattr__(self, value):
        return getattr(self.target, value)

    def __setattr__(self, key, value):
        setattr(self.target, key, value)

    def __repr__(self):
        return "{}({}, func={!r}, **{!r})".format(
            type(self).__name__,
            repr(self.target),
            self.func,
            self.kwargs,
        )

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)
