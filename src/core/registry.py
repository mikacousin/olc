# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from olc.core.action import Action
    from olc.core.app import CoreApplication
    from olc.core.binding import TriggerBinding


class ActionRegistry:
    """Central registry for actions and their external triggers (Keys, MIDI, OSC)."""

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the ActionRegistry.

        Args:
            app: The core application instance.
        """
        self.app = app
        self._action_classes: dict[str, typing.Type[Action]] = {}
        self._actions: dict[str, Action] = {}
        self._bindings: dict[str, list[TriggerBinding]] = {}

    def register(self, action_class: typing.Type[Action]) -> None:
        """Register an action class by instantiating it and storing it.

        Args:
            action_class: The Action class to register.
        """
        action_name = action_class.name
        self._action_classes[action_name] = action_class
        self._actions[action_name] = action_class(self.app)

    def get(self, name: str) -> Action:
        """Get an action instance by name.

        Args:
            name: The action name.

        Returns:
            The Action instance.
        """
        if name not in self._actions:
            raise KeyError(f"Action '{name}' is not registered.")
        return self._actions[name]

    def execute(self, name: str, *args: object, **kwargs: object) -> object:
        """Execute an action by name and push it to history if reversible.

        Args:
            name: The unique action name.
            *args: Positional arguments to pass to execute().
            **kwargs: Keyword arguments to pass to execute().

        Returns:
            The return value of action.execute().
        """
        if name not in self._action_classes:
            raise KeyError(f"Action '{name}' is not registered.")

        action_class = self._action_classes[name]
        action = action_class(self.app)
        configure = getattr(action, "configure", None)
        if callable(configure):
            configure(*args, **kwargs)
        result = action.execute()

        if action.can_undo:
            self.app.history.push(action)

        self._actions[name] = action
        self.trigger_feedback(name)
        return result

    def register_binding(self, name: str, binding: TriggerBinding) -> None:
        """Bind an external trigger to an action.

        Args:
            name: The action name.
            binding: The trigger binding configuration.
        """
        if name not in self._bindings:
            self._bindings[name] = []
        self._bindings[name].append(binding)
        # Bind the app reference back to the binding
        binding.app = self.app

    def trigger_feedback(self, name: str) -> None:
        """Send state feedback to all triggers bound to this action.

        Args:
            name: The action name.
        """
        if name not in self._actions or name not in self._bindings:
            return

        state = self._actions[name].get_feedback_state()
        for binding in self._bindings[name]:
            try:
                binding.send_feedback(state)
            except Exception as err:  # pylint: disable=broad-exception-caught
                print(
                    f"[ActionRegistry] Error sending feedback for '{name}'"
                    f" on binding: {err}"
                )
