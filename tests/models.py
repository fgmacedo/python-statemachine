class MyModel:
    "A class that can be used to hold arbitrary key/value pairs as attributes."

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        super().__init__()

    def __repr__(self):
        return f"{type(self).__name__}({self.__dict__!r})"
