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
VOL_BLOCK_SIZE = 0x8000000


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

	Raises a ValueError if 'raw' is not of type 'bytes' or doesn't appear to represent a `long`.
	"""
	try:
		upper, lower = struct.unpack("II", raw)
	except struct.error as e:
		if __debug__:
			from traceback import print_exc
			print_exc(file=sys.stderr)
		raise ValueError("Couldn't convert '%r' to 'long': %s" % (raw, e))
	return ((16**8) * upper) + lower

def fileSize(fname: str) -> int:
	"""
	Returns the file size (in B) of the file specified by 'fname'.

	This works better than os.filesize because block devices under /dev/ typically have
	0 file size; this will get the size of the disk by opening it and seeing how far you
	have to go to get to the end of the file.
	"""
	global log
	log("fileSize: getting size of", fname)
	fd = os.open(fname, os.O_RDONLY)
	log("fileSize: fd of", fname, "is", fd)
	try:
		size = os.lseek(fd, 0, os.SEEK_END)
		log("fileSize: size of", fname, '(', fd, ") is", size)
		return os.lseek(fd, 0, os.SEEK_END)
	except OSError as e:
		print(e, file=sys.stderr)
		if __debug__:
			from traceback import print_exc
			print_exc(file=sys.stderr)
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
	global log
	num = len(psutil.pids())
	log("numProcs:", num)
	return len(psutil.pids())

if __debug__:
	from os import isatty

	if isatty(sys.stderr.fileno()):
		messageTemplate = "\033[38;2;174;129;255mDEBUG: %s\033[0m\n"
	else:
		messageTemplate = "DEBUG: %s\n"
	def log(*args: object):
		"""
		This will output debug info to stderr (but only if __debug__ is true)
		"""
		output = tuple(repr(arg) if not isinstance(arg, str) else arg for arg in args)
		sys.stderr.write(messageTemplate % (' '.join(output),))

	log("'utils' module: Loaded")
	log("\t\tUNSIGNED_LONG_LONG_SIZE:", UNSIGNED_LONG_LONG_SIZE)
	log("\t\tPOINTER_SIZE:", POINTER_SIZE)
else:
	def log(*unused_args):
		"""
		dummy function to which 'log' gets set if debug isn't enabled
		"""
		pass

# This may seem dumb, but it's necessary to allow importing it.
log = log
