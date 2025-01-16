# Copyright 2021 Patrick C. Tapping
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Note that everything inside the submodules is imported to this parent package.
This means it is possible to use syntax like ``from andor3 import Andor3`` instead of the full
import path such as ``from andor3.andor3 import Andor3``.
"""

__version__ = "0.3.4"

from . constants import *
from . utils import *
from . error import *
from . andor3 import *

