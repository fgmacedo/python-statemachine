"""
User workflow machine
=====================

This machine binds the events to the User model, the StateMachine is wrapped internally
in the `User` class.

Demonstrates that multiple state machines can be used in the same model.

And that logic can be reused with listeners.

"""

from dataclasses import dataclass
from enum import Enum

from statemachine import State
from statemachine import StateMachine
from statemachine.states import States


class UserStatus(str, Enum):
    signup_incomplete = "SIGNUP_INCOMPLETE"
    signup_complete = "SIGNUP_COMPLETE"
    signup_rejected = "SIGNUP_REJECTED"
    operational_enabled = "OPERATIONAL_ENABLED"
    operational_disabled = "OPERATIONAL_DISABLED"
    operational_rescinded = "OPERATIONAL_RESCINDED"


class UserExperience(str, Enum):
    basic = "BASIC"
    premium = "PREMIUM"


@dataclass
class User:
    name: str
    email: str
    status: UserStatus = UserStatus.signup_incomplete
    experience: UserExperience = UserExperience.basic

    verified: bool = False

    def __post_init__(self):
        self._status_sm = UserStatusMachine(
            self, state_field="status", listeners=[MachineChangeListenter()]
        )
        self._status_sm.bind_events_to(self)

        self._experience_sm = UserExperienceMachine(
            self, state_field="experience", listeners=[MachineChangeListenter()]
        )
        self._experience_sm.bind_events_to(self)


class MachineChangeListenter:
    def before_transition(self, event: str, state: State):
        print(f"Before {event} in {state}")

    def on_enter_state(self, state: State, event: str):
        print(f"Entering {state} from {event}")


class UserStatusMachine(StateMachine):
    _states = States.from_enum(
        UserStatus,
        initial=UserStatus.signup_incomplete,
        final=[
            UserStatus.operational_rescinded,
            UserStatus.signup_rejected,
        ],
    )

    signup = _states.signup_incomplete.to(_states.signup_complete)
    reject = _states.signup_rejected.from_(
        _states.signup_incomplete,
        _states.signup_complete,
    )
    enable = _states.signup_complete.to(_states.operational_enabled)
    disable = _states.operational_enabled.to(_states.operational_disabled)
    rescind = _states.operational_rescinded.from_(
        _states.operational_enabled,
        _states.operational_disabled,
    )

    def on_signup(self, token: str):
        if token == "":
            raise ValueError("Token is required")
        self.model.verified = True


class UserExperienceMachine(StateMachine):
    _states = States.from_enum(
        UserExperience,
        initial=UserExperience.basic,
    )

    upgrade = _states.basic.to(_states.premium)
    downgrade = _states.premium.to(_states.basic)


# %%
# Executing


def main():  # type: ignore[attr-defined]
    # By binding the events to the User model, the events can be fired directly from the model
    user = User(name="Frodo", email="frodo@lor.com")

    try:
        # Trying to signup with an empty token should raise an exception
        user.signup("")
    except Exception as e:
        print(e)

    assert user.verified is False

    user.signup("1234")

    assert user.status == UserStatus.signup_complete
    assert user.verified is True

    print(user.experience)
    user.upgrade()
    print(user.experience)


if __name__ == "__main__":
    main()
