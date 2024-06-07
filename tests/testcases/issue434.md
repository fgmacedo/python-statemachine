### Issue 434

A StateMachine that exercises the example given on issue
#[434](https://github.com/fgmacedo/python-statemachine/issues/434).


```py
>>> from time import sleep
>>> from statemachine import StateMachine, State

>>> class Model:
...     def __init__(self, data: dict):
...         self.data = data

>>> class DataCheckerMachine(StateMachine):
...     check_data = State(initial=True)
...     data_good = State(final=True)
...     data_bad = State(final=True)
...
...     MAX_CYCLE_COUNT = 10
...     cycle_count = 0
...
...     cycle = (
...         check_data.to(data_good, cond="data_looks_good")
...         | check_data.to(data_bad, cond="max_cycle_reached")
...         | check_data.to.itself(internal=True)
...     )
...
...     def data_looks_good(self):
...         return self.model.data.get("value") > 10.0
...
...     def max_cycle_reached(self):
...         return self.cycle_count > self.MAX_CYCLE_COUNT
...
...     def after_cycle(self, event: str, source: State, target: State):
...         print(f'Running {event} {self.cycle_count} from {source!s} to {target!s}.')
...         self.cycle_count += 1
...

```

Run until we reach the max cycle without success:

```py
>>> data = {"value": 1}
>>> sm1 = DataCheckerMachine(Model(data))
>>> cycle_rate = 0.1
>>> while not sm1.current_state.final:
...     sm1.cycle()
...     sleep(cycle_rate)
Running cycle 0 from Check data to Check data.
Running cycle 1 from Check data to Check data.
Running cycle 2 from Check data to Check data.
Running cycle 3 from Check data to Check data.
Running cycle 4 from Check data to Check data.
Running cycle 5 from Check data to Check data.
Running cycle 6 from Check data to Check data.
Running cycle 7 from Check data to Check data.
Running cycle 8 from Check data to Check data.
Running cycle 9 from Check data to Check data.
Running cycle 10 from Check data to Check data.
Running cycle 11 from Check data to Data bad.

```


Run simulating that the data turns good on the 5th iteration:

```py
>>> data = {"value": 1}
>>> sm2 = DataCheckerMachine(Model(data))
>>> cycle_rate = 0.1
>>> while not sm2.current_state.final:
...     sm2.cycle()
...     if sm2.cycle_count == 5:
...         print("Now data looks good!")
...         data["value"] = 20
...     sleep(cycle_rate)
Running cycle 0 from Check data to Check data.
Running cycle 1 from Check data to Check data.
Running cycle 2 from Check data to Check data.
Running cycle 3 from Check data to Check data.
Running cycle 4 from Check data to Check data.
Now data looks good!
Running cycle 5 from Check data to Data good.

```
