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
This module contains data structures and utilities that handle Directory entries
"""

import struct
import typing
import ctypes
import numpy as np
from . import utils

#uncommentif PYTHON_MAJOR_VERSION > 5
#from . import http, config
#endif

npDirEntry = np.dtype('u2,u2,u2,u2,u2')

def dirOffset(d: typing.List[int]) -> int:
	"""
	Returns the actual file-relative offset of the content pointed at
	by the tuple of uint16_ts `d` that represents the DirEntry in question
	"""
	offset = d[0] + ((d[1] & 0xFF) << 16) + (d[4] << 24)
	return (offset - 1) * 0x200

def dirSize(d: typing.List[int]) -> int:
	"""
	Returns the approximate size of the object to which the DirEntry
	represented by the list of uint16_ts `d` points.
	"""
	big, size = (d[1] & 0xC000) >> 14, (d[1] & 0x3F00) >> 10
	return (size + 1) * (1 << (9 + 3*big))

class DirEntry():
	"""
	Represents a single directory entry.

	A `DirEntry` in SCAN is comparable to a `Dir` in the ATS cache code. In fact, it carries all
	of the same information.
	Both a `Dir` and (equivalently) a `DirEntry` represent all of the information required to find
	and begin reading in the first piece (fragment) of a `Doc`.

	Instance Members:
		\* head - bool - When `True`, this `DirEntry` points to a `Doc` that has header information.
		                Specifically, this means this `DirEntry` points to the
		                "first fragment" for a certain object, and the `Doc` there has `hlen > 0`.
		                This isn't _necessarily_ the same thing as a "first Doc", as it could be
		                either that or an "earliest Doc".
		\* length - int - The approximate length (in bytes) of the `Doc` referred to by a specific
		               `DirEntry`. This is used in ATS to quickly read the object without
		               needing to immediately parse it; as such, it is guaranteed to be greater-
		               than or equal to the actual length of the `Doc`.
		\* next - int - The segment-relative index of the next `Dir` for this object. If it's `0`,
		               then this is the last `Dir`.
		\* phase - bool - I personally have no idea what the meaning of this flag is. The ATS docs
		                 have this to say: "Phase of the `Doc` (for dir valid check)". So there you
		                 go.
		\* pinned - bool - A "pinned" object is kept in the cache when, under normal circumstances,
		                  it would otherwise be overwritten. This is done via the "evacuation"
		                  process, which is highly complex, but roughly boils down to moving things
		                  away from an impending write cursor.
		\* tag - int - The numeric representation of a "partial key used for fast collision checks".
		            Whatever that means.
		\* token - bool - "Flag: Unknown" _- The ATS Docs_. So, yeah.
		\* _offset - int - The raw offset value stored in the stripe directory. This is an offset in
		                "Cache Blocks" from the stripe's content, so its value is not very
		                meaningful, you should use the `Offset` property for most practical
		                purposes. For directories not in use, this has the special `0` value.

	Data model overrides:
		\* `bool(DirEntry)` - bool - Tells whether the `DirEntry` instance is valid and in-use.
		\* `len(DirEntry)` - int - Returns the approximate length of the `Doc` to which a `DirEntry`
		                          instance points.
		\* `repr(DirEntry)` - str - Gives the `DirEntry` instance in a string representation.
		\* `str(DirEntry)` - str - Gives a short, print-ready string describing the `DirEntry`
		                          instance.
	"""

	# `Dir`s are densly-packed structures, they are typically indexed into as half-words (uint16_t,
	# specifically) and have the basic structure:
	# oo,oo,bs,oo;tt,mt,nn,nn;hh,hh
	# where the characters have the following meanings:
	# o - offset bits (24)
	# b - 'big' size multiplier bits (2)
	# s - 'size' base size bits (6)
	# t - 'tag' bits (12)
	# m - multi-purpose bits in the order t,n,h,p (4)
		# p - phase bit
		# h - head bit
		# n - pinned bit
		# t - token bit
	# n - bits pointing to next `Dir` in bucket (16)
	# h - high offset bits (16)
	BASIC_FORMAT = "HHHHH"

	sizeof = struct.calcsize(BASIC_FORMAT)

	# For some inscrutable reason, the size of a "cache block" is double-defined in the ats source
	# code, firstly through this "CACHE_BLOCK_SHIFT" term and then immediately afterward the macro
	# "CACHE_BLOCK_SIZE" is assigned the expansion: `1 << CACHE_BLOCK_SHIFT`. I can only surmise
	# this is done out of sheer contempt for front-loading any amount of work using
	# `constexpr`s and a bizarre lack of faith in the compiler to figure out what ought to be in
	# the .bss section. As well as - obviously - general distaste for anyone who would dare try
	# to figure out how all of this works.
	CACHE_BLOCK_SHIFT = 9

	def __init__(self, raw: bytes):
		"""
		Initializes the directory entry from the raw data passed in 'raw'

		This is done primarily by doing bitshifts on the data read in as half-words (`uint16_t`)

		Raises a ValueError if the magic number is wrong.
		"""
		if len(raw) != struct.calcsize(type(self).BASIC_FORMAT):
			raise ValueError("Not enough bytes to be a directory entry!")


		# 'w' here is used for historical reasons;
		# in the ATS source code, `w` is the name of the uint16_t array that holds a `Dir` struct's
		# data.
		w = struct.unpack(type(self).BASIC_FORMAT, raw)

		big, size = (w[1] & 0xC000) >> 14, (w[1] & 0x3F00) >> 10
		off = w[0] + ((w[1] & 0x00FF) << 16) + (w[4] << 24)

		# This makes object initialization much faster.
		self.__dict__ = {"length"  : (size + 1) * (1 << (9 + (3*big))),
		                 "_offset" : off,
		                 "token"   : w[2] & 0x8000 == 0x8000,
		                 "pinned"  : w[2] & 0x4000 == 0x4000,
		                 "head"    : w[2] & 0x2000 == 0x2000,
		                 "phase"   : w[2] & 0x1000 == 0x1000,
		                 "tag"     : w[2] & 0x0FFF,
		                 "next"    : w[3],
		                 "Offset"  : (off - 1) * 512}

	# Pylint hates it when you directly set an instance's `__dict__`
	#pylint: disable=E1101
	def __len__(self) -> int:
		"""
		Implements `len(self)`

		The length is calculated at object initialization, so no work is done here.

		Returns the size of the directory entry this object refers to
		*NOT* the size of this struct itself.
		"""
		return self.length

	def __repr__(self) -> str:
		"""
		Implements `repr(self)`.

		Only considers the length and offset of this DirEntry, as that's enough information
		to find and read the Doc to which it refers.

		Returns a string representing this DirEntry
		"""
		ret = "DirEntry(length=%d,"\
		              " offset=0x%X,"\
		              " next=%d,"\
		              " phase=%s,"\
		              " head=%s,"\
		              " pinned=%s,"\
		              " token=%s,"\
		              " tag=0x%X)"

		return ret % (self.length,
		              self.Offset,
		              self.next,
		              self.phase,
		              self.head,
		              self.pinned,
		              self.token,
		              self.tag)

	def __str__(self) -> str:
		"""
		Implements `str(self)`

		This is essentially just a shorter version of __repr__.

		Returns a short string representative of a DirEntry instance.
		"""
		return "%dB -> 0x%X" % (len(self), self.Offset)

	def __bool__(self) -> bool:
		"""
		Implements `bool(self)`.

		Has the meaning "is this a valid Dir?"

		Returns `True` if the directory entry is valid (has offset > 0)
		"""
		return self._offset > 0

	def __eq__(self, other: 'DirEntry') -> bool:
		"""
		Implements `self == other`

		Tests only that they point at the same offset and have the same tag and flags.
		That is, does *not* test that they have the same 'next' or the same length.
		Also ignores the 'token' flag.
		"""
		# References to the same object are equal (and that's a fast check)
		if other is self:
			return True

		# A DirEntry cannot be equal to something that is not a DirEntry
		if not isinstance(other, type(self)):
			return False

		# Getters are for suckers
		#pylint: disable=W0212
		return other._offset == self._offset and\
		       other.tag     == self.tag     and\
		       other.head    == self.head    and\
		       other.pinned  == self.pinned  and\
		       other.phase   == self.phase
		#pylint: enable=W0212

	def valid(self, stripe: 'stripe.Stripe') -> bool:
		"""
		Tests for validity.

		The test depends on the Dir's phase relative to the phase of the containing stripe.
		Note that this assumes that the stripe's header has already been read in. If not,
		then this has no meaning.
		"""
		if self.phase == stripe.phase:
			return self._offset - 1 < stripe.validityLimit

		return self._offset - 1 >= stripe.validityLimit
	#pylint: enable=E1101


class Doc(ctypes.Structure):
	"""
	A single entry within a directory.

	This structure is comparable to a `Doc` structure in the ATS source code. Each part,
	or "fragment" of an object is preceded on the cache by header data in this format.

	Instance members:
		* alternates - int - A list of `Alternates` for the object contained in this `Doc`. If the
		                     `hlen` of this `Doc` is `0` (indicating the lack of metadata), then
		                     this list will be empty.
		* checksum - int - According to the ATS docs: "Unknown".
		* data - bytes - The raw data of the `Doc`, as read in directly from disk. Its length is
		                 equal to `length - hlen - Doc.sizeof()`. If the length of this data is
		                 equal to `totalLength`, then this data represents the entire object.
		* doc_type - int - A somewhat useless value that should only ever indicate that this is
		                   an HTTP object.
		* hlen - int - The length (in bytes) of the header data for this "fragment". This should
		               only be non-zero if this `Doc` is an "earliest Doc" or a "first Doc".
		* keys - bytes - The md5 hashes that correspond to the first key that corresponds to this
		                 and the key that corresponds to this fragment of the object. If `hlen > 0`
		                 it is expected that these be the same. The length of this depends on if
		                 ATS was compiled with `ENABLE_FIPS`. A `Dir` can be determined from a key
		                 using the `dir_probe` function.
		* length - int - The length of this entire fragment, including the metadata (if any), as
		                 well as the data of the `Doc` header.
		* pinned - int - This value somehow acts as both a flag to show that the `Doc` is pinned,
		                 as well as some sort of "timer" for how long it ought to be pinned.
		* sync_serial - int - According to the ATS docs: "Unknown".
		* totalLength - int - The length of the entire object data associated with this `Doc`.
		                      Because an object can be spread across multiple "fragments", this
		                      can be larger than the `length`. This number does not take into
		                      account the metadata or the length of the `Doc` header of any and
		                      all `Doc`s used to store the object.
		* version - int - The version of the cache software used to store the `Doc`. SCAN *only*
		                  supports version 24.0+. May the gods help you if you're using this on a
		                  v23 cache (the version numbers start at 23, because of course they do),
		                  because SCAN will break in half.
		* write_serial - int - According to the ATS docs: "Unknown".
	"""

	MAGIC = 0x5F129B13
	CORRUPT_MAGIC = 0xDEADBABE

	_fields_ = [('magic', ctypes.c_uint32),
	            ('length', ctypes.c_uint32),
	            ('totalLength', ctypes.c_uint64),
	            ('keys', ctypes.c_uint64*4),
	            ('hlen', ctypes.c_uint32),
	            ('docType', ctypes.c_uint32, 8),
	            ('versionMajor', ctypes.c_uint32, 8),
	            ('versionMinor', ctypes.c_uint32, 8),
	            ('unused', ctypes.c_uint32, 8),
	            ('syncSerial', ctypes.c_uint32),
	            ('writeSerial', ctypes.c_uint32),
	            ('pinned', ctypes.c_uint32),
	            ('checksum', ctypes.c_uint32)]

	alternates = []
	data = b''

	# def __init__(self, raw: bytes):
	# 	"""
	# 	Initializes a doc from the raw bytes in the 'raw' buffer
	# 	"""
	# 	# I'm slicing this so that in the future, if I decide to read the whole Doc in at once,
	# 	# this method will be unaffected.
	# 	try:
	# 		data = struct.unpack(self.__class__.BASIC_FORMAT(), raw)
	# 	except struct.error as e:
	# 		raise ValueError("Data could not be interpreted as a `Doc`: %s" % e)

	# 	# Check the magic number
	# 	if self.MAGIC != data[0]:
	# 		if data[0] == self.CORRUPT_MAGIC:
	# 			raise ValueError("`Doc` is corrupt!")
	# 		raise ValueError("Raw data does not represent a `Doc`!")

	# 	self.length = data[1]
	# 	self.totalLength = data[2]
	# 	self.keys = data[3]
	# 	self.hlen = data[4]
	# 	self.docType = data[5]
	# 	self.version = "%d.%d" % (data[6], data[7])
	# 	self.syncSerial = data[8]
	# 	self.writeSerial = data[9]
	# 	self.pinned = data[10]
	# 	self.checksum = data[11]

	# 	# Uninitialized data and metadata sections
	# 	self.alternates = []
	# 	self.data = b''

	# @classmethod
	# def sizeof(cls: type) -> int:
	# 	"""
	# 	Returns the size (in bytes) of a Doc structure
	# 	"""
	# 	return struct.calcsize("II5QI4BIIII")

	sizeof = struct.calcsize("II5QI4BIIII")

	# Yet another dirty hack to maintain compatibility with a deprecated version of a
	# programming language that hasn't released breaking changes since December 2008.
	# Yay CentOS!
	# @classmethod
	# def BASIC_FORMAT(cls: type) -> str:
	# 	"""
	# 	The structure of a `Doc` object depends on whether or not `FIPS` was
	# 	enabled at the compile time of ATS.
	# 	"""
	# 	#if PYTHON_MAJOR_VERSION < 6
	# 	from . import config
	# 	#endif
	# 	return "IIQ%dsI4BIIII" % (2*config.INK_MD5_SIZE())

	def version(self):
		"""
		Returns the version of this object as a string in the format
		"Major.Minor"
		"""
		return "%d.%d" % (self.versionMajor, self.versionMinor)


	def setInfo(self, info: bytes):
		"""
		Sets the CacheHttpInfo vector data of this class.
		"""
		#if PYTHON_MAJOR_VERSION < 6
		from . import http
		#endif
		self.alternates = http.Alternate.fromBuffer(info, [])

	def setData(self, data: bytes):
		"""
		Sets the content data of this 'Doc' based on the 'data' bytes.
		"""
		self.data = data

	def urls(self) -> typing.List[str]:
		"""
		Fetches the urls associated with this `Doc`'s `Alternate`s.
		"""
		utils.log("Doc.urls: returning urls for", self)
		return [a.requestURL() for a in self.alternates]

	def __len__(self) -> int:
		"""
		Implements `len(self)`

		Returns the LENGTH of the document, including including the header length, fragment table,
		and this structure. (Not to be confused with the TOTAL LENGTH)
		"""
		return self.length

	def __repr__(self) -> str:
		"""
		Implements `repr(self)`

		An in-depth representation of the Doc
		"""
		ret = ["Doc(length=%d," % self.length]
		ret.append("totalLength=%d," % self.totalLength)
		ret.append("keys=%r," % self.keys)
		ret.append("hlen=%d," % self.hlen)
		ret.append("docType=%d," % self.docType)
		ret.append("version=%s," % self.version())
		ret.append("syncSerial=%d," % self.syncSerial)
		ret.append("writeSerial=%d," % self.writeSerial)
		ret.append("pinned=%d," % self.pinned)
		ret.append("checksum=%d," % self.checksum)
		ret.append("%d alternates," % len(self.alternates))
		ret.append("%dB of data)" % len(self.data))

		return ' '.join(ret)


# Segment/Bucket types for type-hinting ease
Bucket = typing.NewType('Bucket', typing.Tuple[DirEntry, DirEntry, DirEntry, DirEntry])
Segment = typing.NewType('Segment', typing.Dict[int, Bucket])

utils.log("'directory' module: Loaded")
utils.log("\t\tDirEntry size:", DirEntry.sizeof)
utils.log("\t\tDoc size:", Doc.sizeof)
