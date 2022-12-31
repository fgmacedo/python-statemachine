# coding: utf-8


class Model(object):
    def __init__(self):
        self.state = None

    def __repr__(self):
        return "Model(state={})".format(self.state)
