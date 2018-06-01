"""
Holds utilities for dealing with a single span
"""

import struct
import sys
import typing
import asyncio
from . import stripe

class Span():
	"""
	Represents a cache span
	"""

	def __init__(self, file: str):
		"""
		Initializes the span, along with its header, and headers for any and
		all of its span blocks
		"""
		self.file = file
		self.blocks = []
		with open(file, 'rb') as spanFile:

			spanFile.seek(DiskHeader.OFFSET)

			try:
				self.header = DiskHeader(spanFile.read(DiskHeader.sizeof()))
			except ValueError:
				raise ValueError("%s does not appear to be a valid ATS cache!" % file)

			for spanblockNum in range(self.header.diskvolBlocks):
				spanblock = spanFile.read(stripe.SpanBlockHeader.sizeof)
				try:
					spanblock = stripe.Stripe(spanblock, file)
				except ValueError:
					fmt = "span header #%d seems to declare an invalid span!"
					print(fmt % (spanblockNum + 1), file=sys.stderr)
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
		return self.blocks.__iter__()

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


	def tryReadObject(self, key: str) -> str:
		"""
		Tries to fetch the object referred to by 'key' from the cache
		raises an IndexError if the object is not found in the cache.
		"""
		return NotImplemented


class DiskHeader():
	"""
	The Header for a valid 'disk' (span)
	"""
	# The format of the header -
	# 5 unsigned ints followed by an unsigned long long, all in native sizes.
	BASIC_FORMAT = "=IIIIIQ"

	# The magic number that identifies a cache
	MAGIC = 0xABCD1237

	# The standard offset (in bytes) of an ATS cache header from the start of a disk
	# (Presumably done to avoid colliding with a user's partition table?)
	OFFSET = 0x2000

	def __init__(self, raw_data: bytes):
		"""
		Initializes the DiskHeader object by attempting to parse the data in `raw_data`
		Raises ValueError if the data does not appear to contain a valid Disk Header.
		"""

		magic,\
		self.volumes,\
		self.free,\
		self.used,\
		self.diskvolBlocks,\
		self.blocks = struct.unpack(self.BASIC_FORMAT, raw_data)

		if magic != self.MAGIC:
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

	@classmethod
	def sizeof(cls) -> int:
		"""
		Returns the size (in bytes) of this object, as stored in the cache
		"""
		return struct.calcsize(cls.BASIC_FORMAT)
