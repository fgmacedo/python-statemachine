
# Integrations

## Django integration

When using `python-statemachine` to control the state of a Django's model,
we advice to keep the `StateMachine` definitions on their own modules.

So as circular references may occour, we and as a way to help you organize your
code, if you put statemachines on modules named as bellow inside installed
Django Apps packages, these `StateMachine` classes will be automatically
imported and registered.

Supported module names for auto-discovery:

- `statemachine.py`
- `statemachines.py`


```{note}
Your Django Model should include the [](mixins.md#machinemixin).
```

