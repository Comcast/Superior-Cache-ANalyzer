# Copyright 2018 Comcast Cable Communications Management, LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Utility functions dealing with blocks within a single span
"""

import hashlib
import typing
import struct
from . import stripe

# Currently, this isn't used
def dir_probe(key: str,\
              searchStripe: stripe.Stripe,\
              unused_last_collision: object=None) -> typing.Tuple[int, int]:
	"""
	Gets the segment and bucket indices of a key ('key') within a stripe ('d').
	"""
	cacheID = hashlib.md5()
	cacheID.update(key.encode())
	cacheID = cacheID.digest()

	segIndex = struct.unpack("!Q", cacheID[:8])[0] % (searchStripe.numSegs())

	# 4 Dirs in a bucket
	bucketIndex = struct.unpack("!Q", cacheID[8:])[0] %\
	                            (searchStripe.numBuckets() // searchStripe.numSegs())

	return segIndex, bucketIndex
