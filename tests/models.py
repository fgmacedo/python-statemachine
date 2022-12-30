class MyModel(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.__dict__)
