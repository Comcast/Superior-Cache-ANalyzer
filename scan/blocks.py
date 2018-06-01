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
