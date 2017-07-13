History
=======

0.5.0 (2017-07-13)
------------------

* Custom exceptions.
* Duplicated definition of ``on_execute`` callback is not allowed.
* Fix bug on ``StateMachine.on_<transition.identifier>`` being called with extra ``self`` param.

0.4.2 (2017-07-10)
------------------

* Python 3.6 support.
* Drop official support for Python 3.3.
* `Transition` can be used as decorator for `on_execute` callback definition.
* `Transition` can point to multiple destination states.


0.3.0 (2017-03-22)
------------------

* README getting started section.
* Tests to state machine without model.


0.2.0 (2017-03-22)
------------------

* ``State`` can hold a value that will be assigned to the model as the state value.
* Travis-CI integration.
* RTD integration.


0.1.0 (2017-03-21)
------------------

* First release on PyPI.
