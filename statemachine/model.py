class Model:
    def __init__(self):
        self.state = None
        """Holds the current :ref:`state` value of the :ref:`StateMachine`."""

    def __repr__(self):
        return f"Model(state={self.state})"
