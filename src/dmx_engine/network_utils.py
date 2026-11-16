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
"""Common network utility functions shared across different backends."""

from __future__ import annotations

import ifaddr


def get_local_ips() -> list[str]:
    """Retrieve all active local IPv4 addresses on the host system."""
    ips = ["0.0.0.0", "127.0.0.1"]
    try:
        adapters = ifaddr.get_adapters()
        for adapter in adapters:
            for ip in adapter.ips:
                if ip.is_IPv4:
                    ip_str = str(ip.ip)
                    if ip_str not in ips:
                        ips.append(ip_str)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return ips
