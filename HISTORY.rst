History
=======

1.0.0 (2022-12-30)
------------------

* Drop support for monkey-patching add callbacks at machine runtime.
* Fixed mypy complaining about incorrect type for ``StateMachine`` class.
* Added support for diagrams.


0.9.0 (2022-12-21)
------------------

* This is the last release supporting Python2.X series.
* Doctesting all documentation including README (with issues on examples fixed).
* Fix state value misjudged when state value is an "boolean False value" (tks @the5fire)
* Fix returning dict as result of transitions callback.
* State machine declarations now with final states.
* Args and kwargs now are passed to bounded transitions.


0.8.0 (2020-01-23)
------------------

* Add support for Python 3.7 and 3.8 (adding to test matrix).
* Update development requirements.
* State machine names should now be fully qualified for mixins, simple names are deprecated and
  will no longer be supported on a future version.
* Development: Adding mypy linter.
* Add support for State machine inheritance. Thanks @rschrader.
* Add support for reverse transitions: ``transition = state_a.from_(state_b)``.
  Thanks @romulorosa.
* Fix current state equal to destination on enter events. Thanks @robnils and @joshuacc1.
* Check: StateMachine now validates if it's states/transitions graph has only one component.
  Thanks @rafaelrds.

Breaking changes:

* Drop official support for Python 3.4 (removing from test matrix, code may still work).


0.7.1 (2019-01-18)
------------------

* Fix Django integration for registry loading statemachine modules on Django1.7+.


0.7.0 (2018-04-01)
------------------

* New event callbacks: `on_enter_<state>` and `on_exit_<state>`.

0.6.2 (2017-08-25)
------------------

* Fix README.


0.6.1 (2017-08-25)
------------------

* Fix deploy issues.


0.6.0 (2017-08-25)
------------------

* Auto-discovering `statemachine`/`statemachines` under a Django project when
  they are requested using the mixin/registry feature.

0.5.1 (2017-07-24)
------------------

* Fix bug on ``CombinedTransition._can_run`` not allowing transitions to run if there are more than
  two transitions combined.

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
