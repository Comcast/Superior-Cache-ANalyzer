"""
This module contains miscellaneous utilities
"""

import os
import sys
import struct
import enum
import psutil

########################################################
###                                                  ###
###                   CONSTANTS                      ###
###                                                  ###
########################################################

# The size of a double word on this architecture.
# The type it's actually tring to represent is uint64\_t
UNSIGNED_LONG_LONG_SIZE = struct.calcsize("Q")

# The size of a pointer. Usually the same as `UNSIGNED_LONG_LONG_SIZE`.
POINTER_SIZE = struct.calcsize("P")

# Figuring this out was a massive pain
STORE_BLOCK_SIZE = 8192

# Span block sizes MUST be multiples of this value.
# So it's used to check validity of a span block
VOL_BLOCK_SIZE = 128 * (1024**2)


########################################################
###                                                  ###
###                 TYPES/CLASSES                    ###
###                                                  ###
########################################################

class CacheType(enum.IntEnum):
	"""
	Enumerated cache types
	"""
	NONE = 0
	HTTP = 1
	RTSP = 2

	def __str__(self) -> str:
		"""
		Returns the human-readable form of a cache type
		"""
		return str(self.name).lower()


########################################################
###                                                  ###
###                   FUNCTIONS                      ###
###                                                  ###
########################################################

def unpacklong(raw: bytes) -> int:
	"""
	Unpacks and returns an unsigned long long from the 'raw' data

	For some reason, the offset and length for DiskVolBlock information structs in DiskHeaders
	are written by first splitting them into high and low 32 bits, and writing each of these to
	disk. The upshot is that each 32 bits is written in the native byte order, but the double-word
	that represents the whole value is written high bits first then low bits, as though it were
	Big-Endian regardless of the host architecture's byte order.
	"""
	upper, lower = struct.unpack("II", raw)
	return ((16**8) * upper) + lower

def fileSize(fname: str) -> int:
	"""
	Returns the file size (in B) of the file specified by 'fname'.

	This works better than os.filesize because block devices under /dev/ typically have
	0 file size; this will get the size of the disk by opening it and seeing how far you
	have to go to get to the end of the file.
	"""
	fd = os.open(fname, os.O_RDONLY)
	try:
		return os.lseek(fd, 0, os.SEEK_END)
	except OSError as e:
		print(e, file=sys.stderr)
	finally:
		os.close(fd)

def align(alignMe: int, alignTo: int = STORE_BLOCK_SIZE) -> int:
	"""
	Aligns an offset `alignMe` to the storage size indicated by `alignTo`

	Returns `alignMe` unchanged if it is alreadly properly aligned.
	"""

	x = alignMe % alignTo

	return alignMe + (alignTo - x) if x else alignMe

def numProcs() -> int:
	"""
	Gets the number of processes currently running on the system.
	"""
	return len(psutil.pids())
