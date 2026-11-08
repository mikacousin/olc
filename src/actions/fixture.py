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
"""Actions for managing FixtureDefinitions in the Fixture Library."""

from __future__ import annotations

import typing
from typing import Optional

from olc.core.action import Action
from olc.devices.fixture import (
    FixtureDefinition,
    delete_user_fixture,
    save_user_fixture,
)
from olc.devices.gdtf import GdtfImporter

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def _update_dmx_and_send(app: CoreApplication) -> None:
    backend = getattr(app, "backend", None)
    backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
    if backend_dmx is not None and type(backend_dmx).__name__ == "Dmx":
        backend_dmx.set_levels()
        backend_dmx.send()


class FixtureUpsertAction(Action):
    """Action to create or update a FixtureDefinition."""

    name = "fixture.upsert"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.new_definition: Optional[FixtureDefinition] = None
        self.old_manufacturer: Optional[str] = None
        self.old_model: Optional[str] = None
        self.previous_definition: Optional[FixtureDefinition] = None
        self.was_present: bool = False
        self.synced_device_ids: list[int] = []

    def configure(
        self,
        definition: FixtureDefinition,
        old_manufacturer: Optional[str] = None,
        old_model: Optional[str] = None,
    ) -> None:
        """Configure the fixture definition to save/update."""
        self.new_definition = definition
        self.old_manufacturer = old_manufacturer
        self.old_model = old_model

    def execute(self) -> None:
        """Execute creation or modification of a FixtureDefinition."""
        if self.new_definition is None:
            self.can_undo = False
            return

        library = getattr(self.app.lightshow, "fixture_library", None)
        if library is None:
            self.can_undo = False
            return

        lookup_m = self.old_manufacturer or self.new_definition.manufacturer
        lookup_mod = self.old_model or self.new_definition.model

        try:
            existing = library.get(lookup_m, lookup_mod)
            if existing.is_builtin:
                raise ValueError(
                    f"Built-in fixture '{existing.full_name}' is read-only. "
                    "Use 'Duplicate' to create a custom profile."
                )
            self.previous_definition = existing
            self.was_present = True
        except KeyError:
            self.previous_definition = None
            self.was_present = False

        # If renaming manufacturer/model, remove old entry and disk file
        if self.old_manufacturer or self.old_model:
            if (
                self.old_manufacturer != self.new_definition.manufacturer
                or self.old_model != self.new_definition.model
            ):
                try:
                    library.unregister(lookup_m, lookup_mod)
                    delete_user_fixture(lookup_m, lookup_mod)
                except Exception:
                    pass

        # Register new definition in memory and persist on user disk
        library.register(self.new_definition)
        save_user_fixture(self.new_definition)

        # Synchronize patched devices
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is not None and hasattr(patch, "sync_devices_with_definition"):
            self.synced_device_ids = patch.sync_devices_with_definition(
                self.new_definition,
                old_manufacturer=self.old_manufacturer,
                old_model=self.old_model,
            )

        _update_dmx_and_send(self.app)
        self.app.emit("fixture_library.changed")
        self.app.emit("patch.changed")
        if self.synced_device_ids:
            self.app.emit("device.parameters_changed", self.synced_device_ids)

    def undo(self) -> None:
        """Undo definition changes and restore previous device states."""
        if self.new_definition is None:
            return
        library = getattr(self.app.lightshow, "fixture_library", None)
        if library is None:
            return

        # Remove the modified definition
        try:
            library.unregister(
                self.new_definition.manufacturer, self.new_definition.model
            )
            delete_user_fixture(
                self.new_definition.manufacturer, self.new_definition.model
            )
        except Exception:
            pass

        # Restore previous if it was present
        if self.was_present and self.previous_definition is not None:
            library.register(self.previous_definition)
            save_user_fixture(self.previous_definition)
            patch = getattr(self.app.lightshow, "patch", None)
            if patch is not None and hasattr(patch, "sync_devices_with_definition"):
                patch.sync_devices_with_definition(
                    self.previous_definition,
                    old_manufacturer=self.new_definition.manufacturer,
                    old_model=self.new_definition.model,
                )

        _update_dmx_and_send(self.app)
        self.app.emit("fixture_library.changed")
        self.app.emit("patch.changed")
        if self.synced_device_ids:
            self.app.emit("device.parameters_changed", self.synced_device_ids)


class FixtureDeleteAction(Action):
    """Action to delete a user FixtureDefinition."""

    name = "fixture.delete"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.manufacturer: str = ""
        self.model: str = ""
        self.deleted_definition: Optional[FixtureDefinition] = None

    def configure(self, manufacturer: str, model: str) -> None:
        """Configure target fixture to delete."""
        self.manufacturer = str(manufacturer).strip()
        self.model = str(model).strip()

    def execute(self) -> None:
        """Execute fixture deletion."""
        library = getattr(self.app.lightshow, "fixture_library", None)
        if library is None:
            self.can_undo = False
            return

        patch = getattr(self.app.lightshow, "patch", None)
        if patch is not None and hasattr(patch, "count_devices_using_definition"):
            count = patch.count_devices_using_definition(self.manufacturer, self.model)
            if count > 0:
                raise ValueError(
                    f"Cannot delete '{self.manufacturer} {self.model}': "
                    f"in use by {count} patched device(s)."
                )

        try:
            defn = library.get(self.manufacturer, self.model)
            if defn.is_builtin:
                raise ValueError(f"Cannot delete built-in fixture '{defn.full_name}'.")
            self.deleted_definition = defn
            library.unregister(self.manufacturer, self.model)
            delete_user_fixture(self.manufacturer, self.model)
        except Exception:
            self.can_undo = False
            raise

        self.app.emit("fixture_library.changed")

    def undo(self) -> None:
        """Restore deleted definition."""
        if self.deleted_definition is None:
            return
        library = getattr(self.app.lightshow, "fixture_library", None)
        if library is None:
            return
        library.register(self.deleted_definition)
        save_user_fixture(self.deleted_definition)
        self.app.emit("fixture_library.changed")


class FixtureImportGdtfAction(Action):
    """Action to import a .gdtf file into the Fixture Library."""

    name = "fixture.import_gdtf"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.file_path: str = ""
        self.imported_definition: Optional[FixtureDefinition] = None
        self.was_existing: Optional[FixtureDefinition] = None

    def configure(self, file_path: str) -> None:
        """Configure the .gdtf file path to import."""
        self.file_path = str(file_path).strip()

    def execute(self) -> None:
        """Import the .gdtf file and register it."""
        library = getattr(self.app.lightshow, "fixture_library", None)
        if library is None or not self.file_path:
            self.can_undo = False
            return

        importer = GdtfImporter()
        defn = importer.load(self.file_path)
        defn.is_builtin = False

        try:
            self.was_existing = library.get(defn.manufacturer, defn.model)
        except KeyError:
            self.was_existing = None

        self.imported_definition = defn
        library.register(defn)
        save_user_fixture(defn)
        self.app.emit("fixture_library.changed")

    def undo(self) -> None:
        """Revert imported definition."""
        if self.imported_definition is None:
            return
        library = getattr(self.app.lightshow, "fixture_library", None)
        if library is None:
            return

        try:
            library.unregister(
                self.imported_definition.manufacturer, self.imported_definition.model
            )
            delete_user_fixture(
                self.imported_definition.manufacturer, self.imported_definition.model
            )
        except Exception:
            pass

        if self.was_existing is not None:
            library.register(self.was_existing)
            save_user_fixture(self.was_existing)

        self.app.emit("fixture_library.changed")
