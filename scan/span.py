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
Holds utilities for dealing with a single span
"""

import struct
import sys
import typing
import asyncio
from . import stripe, utils

class Span():
	"""
	Represents a cache span
	"""

	def __init__(self, file: str):
		"""
		Initializes the span, along with its header, and headers for any and
		all of its span blocks
		"""
		utils.log("Span: initializing from", file)
		self.file = file
		self.blocks = []
		with open(file, 'rb') as spanFile:

			spanFile.seek(DiskHeader.OFFSET)

			try:
				self.header = DiskHeader(spanFile.read(DiskHeader.sizeof))
			except ValueError as e:
				utils.log_exc("Span.__init__:")
				raise ValueError("%s does not appear to be a valid ATS cache! (%s)" % (file, e))

			sbhHeaderFormat = stripe.SpanBlockHeader.BASIC_FORMAT*self.header.diskvolBlocks
			buffer = bytearray(struct.calcsize(sbhHeaderFormat))

			try:
				spanFile.readinto(buffer)
			except (OSError, IOError) as e:
				utils.log_exc("Span.__init__:")
				print("Error reading span file '%s': '%s'", file, e)

			try:
				spanBlockHeaders = struct.unpack(sbhHeaderFormat, buffer)
			except struct.error as e:
				utils.log_exc("Span.__init__:")
				raise ValueError("Malformed DiskHeader object in cache file '%s'" % (file,))

			for i in range(0, len(spanBlockHeaders), 4):
				try:
					spanblock = stripe.Stripe(spanBlockHeaders[i:i+4], file)
				except ValueError:
					utils.log_exc("Span.__init__: stripe construction:")
					print("stripe header seems to declare an invalid stripe!", file=sys.stderr)
				else:
					spanblock.read()
					self.blocks.append(spanblock)

	def __str__(self) -> str:
		"""
		Returns a string representation of a span
		(which currently is the same as the string representation of its header)
		"""
		return str(self.header)

	def __repr__(self) -> str:
		"""
		Returns a verbose string containing the defining information about a span
		"""
		return "Span(file=%s, header=%r)" % (self.file, self.header)

	def __iter__(self) -> 'dict_keyiterator':
		"""
		Makes the span iterable (which iterates over each block in the span)
		"""
		return iter(self.blocks)

	def __getitem__(self, item: int) -> stripe.Stripe:
		"""
		Allows indexing into the Span to fetch each span block
		"""
		return self.blocks[item]

	def __len__(self) -> int:
		"""
		Returns the length of the span (i.e. the number of span blocks)
		"""
		return len(self.blocks)

	def __bool__(self) -> bool:
		"""
		Boolean coercion for Spans

		A span is True-y if it contains at least one stripe, otherwise it's False-y
		"""
		return len(self) > 0

	@asyncio.coroutine
	def storedObjects(self) -> typing.Generator[typing.Tuple[str, int], None, None]:
		"""
		Gets a list of all the urls stored in all of the stripes in this span.

		For each stripe, the directory will end in the same state in which it began.
		That is, even though `readDir` must be called if it has not been already,
		the stripe's directory will be reset to `None` afterward if it was before.
		"""
		cleanUp = False
		for block in self.blocks:
			if block.directory is None:
				block.readDir()
				cleanUp = True
			yield from block.parallelStoredObjects()

			# Directories can use up huge amounts of space
			if cleanUp:
				cleanUp, block.directory = False, None


	# def tryReadObject(self, key: str) -> str:
	# 	"""
	# 	Tries to fetch the object referred to by 'key' from the cache
	# 	raises an IndexError if the object is not found in the cache.
	# 	"""
	# 	return NotImplemented


class DiskHeader():
	"""
	The Header for a valid 'disk' (span)
	"""
	# The format of the header -
	# 5 unsigned ints followed by an unsigned long long, all in native sizes.
	BASIC_FORMAT = "5IQ"

	# The magic number that identifies a cache
	MAGIC = 0xABCD1237

	# The standard offset (in bytes) of an ATS cache header from the start of a disk
	# (Presumably done to avoid colliding with a user's partition table?)
	OFFSET = 0x2000

	sizeof = struct.calcsize(BASIC_FORMAT)

	def __init__(self, raw_data: bytes):
		"""
		Initializes the DiskHeader object by attempting to parse the data in `raw_data`
		Raises ValueError if the data does not appear to contain a valid Disk Header.
		"""

		try:
			magic,\
			self.volumes,\
			self.free,\
			self.used,\
			self.diskvolBlocks,\
			self.blocks = struct.unpack(self.BASIC_FORMAT, raw_data)
		except struct.error:
			utils.log("DiskHeader.__init__: raw_data:", raw_data)
			utils.log_exc("DiskHeader.__init__:")
			raise ValueError("Malformed Disk Header!")

		utils.log("DiskHeader.__init__: Initialized DiskHeader:", self)

		if magic != self.MAGIC:
			utils.log("DiskHeader.__init__: Bad MAGIC:", magic)
			raise ValueError("Invalid or corrupt disk header!")

	def __len__(self) -> int:
		"""
		Returns the number of span blocks indicated by the header,
		*NOT* the length of the header itself.
		"""
		return self.diskvolBlocks

	def __str__(self) -> str:
		"""
		Returns a simple string representing this disk header
		"""
		return "Span of %d stripe%s" % (self.volumes, '' if self.diskvolBlocks == 1 else 's')

	def __repr__(self) -> str:
		"""
		Returns a verbose string showing detailed information about the header
		"""
		ret = "DiskHeader(volumes=%d, free=%d, used=%d, diskvol_blocks=%d, blocks=%d)"
		return ret % (self.volumes, self.free, self.used, self.diskvolBlocks, self.blocks)

utils.log("'span' module: Loaded")
utils.log("\t\tDiskHeader size:", DiskHeader.sizeof)
