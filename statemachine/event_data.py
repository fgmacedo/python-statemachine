class EventData(object):
    def __init__(self, machine, event, *args, **kwargs):
        self.machine = machine
        self.event = event
        self.source = kwargs.get("source", None)
        self.state = kwargs.get("state", None)
        self.model = kwargs.get("model", None)
        self.transition = kwargs.get("transition", None)
        self.executed = False

        # runtime and error
        self.args = args
        self.kwargs = kwargs
        self.error = None
        self.result = None

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.__dict__)

    @property
    def extended_kwargs(self):
        kwargs = self.kwargs.copy()
        kwargs["event_data"] = self
        kwargs["event"] = self.event
        kwargs["source"] = self.source
        kwargs["state"] = self.state
        kwargs["model"] = self.model
        kwargs["transition"] = self.transition
        return kwargs
