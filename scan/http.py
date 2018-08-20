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
This module contains utilities related to the storage and manipulation of HTTP headers, requests
and responses
"""

import typing
import struct
import sys
import time

from . import utils

# A small object that contains header information for header information
# Don't ask me why.
HdrHeapObjImpl = typing.NamedTuple('HdrHeapObjImpl',
                 [('Type', int), ('length', int), ('flags', bytes)])

# This object for some reason holds information about a HDRHeap which
# contains it.
StrHeapDesc = typing.NamedTuple('StrHeapDesc',
              [('ptr', int), ('start', int), ('length', int), ('locked', bool)])



############################################
###                                      ###
###            URL OBJECTS               ###
###                                      ###
############################################

# An easy-to-access construct for abitrary URLs
URL = typing.NamedTuple('URL',
      [('protocol', str),
       ('user', str),
       ('passwd', str),
       ('host', str),
       ('port', int),
       ('path', str),
       ('params', typing.List[typing.Tuple[str, str]]),
       ('query', str)])

def URLtoString(url: URL) -> str:
	"""
	Implements `str(url)`.

	Attempts to concatenate the url parts into the form:
	`protocol://user:passwd@host:port/path` (query+params not implemented)
	"""
	ret =  [url.protocol, "://"]
	if url.user and url.passwd:
		ret += (url.user, ":", url.passwd, "@")
	elif url.user:
		ret += (url.user, "@")
	elif url.passwd:
		ret += (":", url.passwd, "@")
	ret.append(url.host)
	if url.port:
		ret += (":", str(url.port))
	if url.path:
		ret += ('/', url.path)

	return ''.join(ret)

# Too bad I need to support Python 3.4...
URL.__str__ = URLtoString




class HDRHeap():
	"""
	A small structure that holds a HdrHeap object.

	This will almost certainly be replaced by a named tuple at some point.
	"""

	# The basic format of a HdrHeap on disk.
	# There's lots of slop in this structure, dunno why.
	# BASIC_FORMAT = "IPPI?PIP"\
	#                "PPi?"\
	#                "PPi?"\
	#                "PPi?"\
	#                "i"

	# This is the format of a "read-only heap" object. For whatever reason,
	# every HDRHeap will have exactly three of these, written as a 21-byte string.
	RONLY_HEAP_FORMAT = "PPi?"

	# The "Magic number" of a HdrHeap object.
	MAGIC = 0xDCBAFEED

	def __init__(self, raw: bytes):
		"""
		Constructs a HdrHeap from its raw data
		"""

		try:
			raw = struct.unpack(type(self).BASIC_FORMAT(), raw)
		except struct.error as e:
			utils.log_exc("HDRHeap.__init__:")
			raise ValueError("Data not compatible with a HDRHeap! (%s)" % e)

		if raw[0] != self.MAGIC:
			raise ValueError("Bad magic number 0x%X" % raw[0])

		# For debugging purposes
		self.magic = raw[0]

		self.freeStart    = raw[1]
		self.dataStart    = raw[2]
		self.size         = raw[3]
		self.writeable    = raw[4]
		self.next         = raw[5]
		self.freeSize     = raw[6]
		self.rwheap       = raw[7]
		self.ronlyHeaps   = (StrHeapDesc(*raw[8:12]),
		                     StrHeapDesc(*raw[12:16]),
		                     StrHeapDesc(*raw[16:20]))
		self.lostStrSpace = raw[20]

	def __repr__(self) -> str:
		"""
		Implements `repr(self)`.
		"""

		ret = ["HDRHeap(freeStart=0x%X" % self.freeStart]
		ret.append("dataStart=0x%X" % self.dataStart)
		ret.append("size=%d" % self.size)
		ret.append("writeable=%s" % self.writeable)
		ret.append("next=0x%X" % self.next)
		ret.append("freeSize=%d" % self.freeSize)
		ret.append("rwheap=0x%X" % self.rwheap)
		ret.append("ronlyHeaps=%r" % (self.ronlyHeaps,))
		ret.append("lostStrSpace=%d)" % self.lostStrSpace)

		return ", ".join(ret)

	@classmethod
	def sizeof(cls):
		"""
		The size of a HdrHeap, as stored in the cache
		"""
		# The beginning of the Heap data is pointer-aligned
		return struct.calcsize(cls.BASIC_FORMAT())

	@classmethod
	def BASIC_FORMAT(cls) -> str:
		"""
		The process is a bit more involved than I initially thought.
		"""
		# The header stuff, then every read-only cache, then the final outer data member
		veryBasic = "IPPI?PIP"\
		            "PPi?"\
		            "PPi?"\
		            "PPi?"\
		            "i"

		veryBasicSize = struct.calcsize(veryBasic)

		# Usually, this'll output veryBasic + '4x', indicating 4B of alignment 'slop'.
		# Depends on the host OS and architecture, though.
		return "%s%dx"%(veryBasic, utils.align(veryBasicSize, struct.calcsize("P"))-veryBasicSize)

	def verify(self) -> bool:
		"""
		Verifies that a HdrHeap is valid.

		Returns `True` if it is, `False` otherwise.
		"""
		# Correct magic number
		if self.magic != type(self).MAGIC:
			return False

		# Objects stored on disk should not be writeable
		if self.writeable:
			return False

		# All of these should be zero:
		if any([self.freeStart,
		        self.next,
		        self.freeSize,
		        self.rwheap,
		        self.ronlyHeaps[0].ptr,
		        self.ronlyHeaps[1].start,
		        self.ronlyHeaps[2].start]):
			return False

		return True



############################################
###                                      ###
###           HTTPHdr OBJECTS            ###
###                                      ###
############################################

class HTTPHdr():
	"""An object which contains information about an HTTP Request or response."""

	__slots__ = ("mimeHdrHeap",
	             "mimeHdrImpl",
	             "httpHdr",
	             "urlHdrHeap",
	             "urlHdrImpl",
	             "mimeField",
	             "hostLength",
	             "port",
	             "targetCached",
	             "targetInURL",
	             "continue100",
	             "portInHeader",
	             "method",
	             "reason",
	             "URL",
	             "HdrObjImpls",
	             "heapHdr")

	def __init__(self, *args):
		"""
		Constructs the HTTPHdr class
		"""
		self.mimeHdrHeap,\
		self.mimeHdrImpl,\
		self.httpHdr,\
		self.urlHdrHeap,\
		self.urlHdrImpl,\
		self.mimeField,\
		self.hostLength,\
		self.port,\
		self.targetCached,\
		self.targetInURL,\
		self.continue100,\
		self.portInHeader = args

		# filled in later
		#This is one thing the compiler can actually optimize, since `(None,)` and `4` are constants
		self.method, self.reason, self.URL, self.heapHdr = (None,)*4
		self.HdrObjImpls = []

	def __str__(self) -> str:
		"""
		Implements `str(self)`
		"""
		ret = [self.method] if self.method else ([self.reason] if self.reason else [])
		ret.append(str(self.URL))

		return ' '.join(ret)




def unpackHdrHeapObjImpl(obj: bytes) -> HdrHeapObjImpl:
	"""
	Unpacks a HdrHeapObjImpl from the passed bytes.

	Note that this is not trivial, as the structure is implemented with non-byte-aligned bitfields
	in the ATS source.
	"""

	# This is technically not implementation-defined - The C11 standard says bytes are written as
	# any (usually largest) native data type capable of holding a member without exceeding its size
	# (internally in host byte-order). At this point, "if enough space remains, a bit-field that
	# immediately follows another bit-field in a structure shall be packed into adjacent bits of
	# the same unit." In the event that enough space does *not* remain, _then_ it's implementation-
	# defined. Plus, technically an implementation is not forced to use the largest data structure
	# that it can, but most do. Let's hope that's enough.
	t, l, f = struct.unpack("=B2sB", obj)
	flags = (0xF0 & f) >> 4
	l = struct.unpack("=H", l)[0] + ((f & 0xF) << 16)

	return HdrHeapObjImpl(t,l,flags)

def unpackHTTPImplHeap(heap: bytes, start: int, http: HTTPHdr) -> typing.List[int]:
	"""
	Unpacks an HTTPImplHeap from the passed raw bytes.

	Attemtps to discern a method or a reason by looking ahead into the heap.
	For this reason, it expects the entire heap to be passed, followed by an offset pointing to the
	beginning of the HTTPImpl.

	Returns the decoded reason/method followed by the actual fields of the HTTPImpl.
	"""
	polarity = struct.unpack("I", heap[start:start+struct.calcsize("I")])[0]

	if polarity == 1:
		# Request header
		fmt = "Ii4x%ds" % struct.calcsize("PPHhP")
		obj = list(struct.unpack(fmt, heap[start:start+struct.calcsize(fmt)]))
		for part in struct.unpack("PPHhP", obj.pop()):
			obj.append(part)

		#gets the actual method name
		http.method = heap[obj[3]:obj[3]+obj[4]].decode()

		return obj

	elif polarity == 2:
		# Response header
		fmt = "Ii4x%ds" % struct.calcsize("PHhP")
		obj = list(struct.unpack(fmt, heap[start:start+struct.calcsize(fmt)]))
		for part in struct.unpack("PHhP", obj.pop()):
			obj.append(part)

		# Gets the "reason" (?) name
		http.reason = heap[obj[2]:obj[2]+obj[3]].decode()

		return obj

	# Unkown/unsupported polarity.
	raise ValueError("Unknown Polarity: %d encountered in hdr heap obj" % polarity)

def unpackURLImplHeap(heap: bytes, start: int, http: HTTPHdr) -> typing.List[int]:
	"""
	Unpacks a URLImpl from the given raw byte heap.

	Attemtps to discern the actual URL by looking ahead into the heap.

	Returns the constructed URL, followed by the actual data member fields of the unpacked URLImpl.
	"""
	fmt = "10h%ds" % struct.calcsize("10PhHBB?")
	obj = list(struct.unpack(fmt, heap[start:start+struct.calcsize(fmt)]))
	for part in struct.unpack("10PhHBB?", obj.pop()):
		obj.append(part)

	lens = obj[:8]
	ptrs = obj[10:18]
	parts = []
	for i, ptr in enumerate(ptrs):
		if lens[i]:
			parts.append(heap[ptr:ptr+lens[i]].decode())
		else:
			parts.append(None)

	if parts[4]:
		parts[4] = int(parts[4])

	http.URL = URL(*(part if part else None for part in parts))

	return obj

def unpackMIMEFieldBlockImplHeap(heap: bytes, start: int, unused_http: object) -> typing.List[int]:
	"""
	Unpacks a MIMEFieldBlockImpl from the passed heap.

	Returns a list of the data member fields for the stored object.
	"""
	fmt = "IP"
	fmt += "3PhH4s"*16
	return list(struct.unpack(fmt, heap[start:start+struct.calcsize(fmt)]))

def unpackMIMEFieldImplHeap(heap: bytes, start: int, unused_http: object) -> typing.List[int]:
	"""
	Unpacks a MIMEFieldImpl from the given raw byte heap.

	Returns a list of the values of the data members of the stored object.
	"""
	fmt = "4xL4II4i?PIP"
	fmt += "3PhH4s"*16
	return list(struct.unpack(fmt, heap[start:start+struct.calcsize(fmt)]))

# This maps the types of HdrHeapObjImpl's to functions that unpack them.
UNPACK_FUNCS = {2: unpackURLImplHeap,
                3: unpackHTTPImplHeap,
                4: unpackMIMEFieldImplHeap,
                5: unpackMIMEFieldBlockImplHeap}


class Alternate():
	"""
	This class represents alternate cached versions of the same content

	Each contains similar information.
	"""

	# These are the magic numbers for cache alternates. I really don't know what is meant by
	# "Dead", but "Alive" means that the structure is 'unmarshaled', or stored as a struct in
	# the ats process's memory space. So it should never happen on disk. You'll notice that all
	# of them end in 'DEED' (not sure why the DEAD code isn't 0xDEADDEED, guess they don't like
	# the way double D's look), but the first four characters of the normal `MAGIC` and
	# `MAGIC_ALIVE` are reverses of one another. I'm not sure, but I think this is a joke about
	# host byte order endian-ness.
	MAGIC       = 0xDCBADEED
	MAGIC_ALIVE = 0xABCDDEED # This should literally never happen
	MAGIC_DEAD  = 0x0DEADEED

	# The number of "integral" fragment offsets, which are exactly like a regular fragment
	# offset except that... they're... integral?
	# This is a `static constexpr` member of an `HTTPCacheAlt` object in the ats source, which
	# ostensibly means it's subject to change at any point in the version future of ats.
	N_INTEGRAL_FRAG_OFFSETS = 4

	# The basic structure format of an Alternate.
	BASIC_FORMAT = "I10i"\
	               "6Pii4?"\
	               "6Pii4?"\
	               "lliP4LP"

	__slots__ = ("magic",
	             "writeable",
	             "unmarshalLen",
	             "ID",
	             "rid",
	             "objectKey",
	             "objectSize",
	             "request",
	             "response",
	             "requestTimestamp",
	             "responseTimestamp",
	             "fragOffsetCount",
	             "fragOffsetsPtr",
	             "integralFragOffsets",
	             "fragmentOffsets",
	             "requestHeaders",
	             "responseHeaders",)


	sizeof = utils.align(struct.calcsize(BASIC_FORMAT), struct.calcsize("L"))

	def __init__(self, basicData: typing.Tuple[int, ...]):
		"""
		Constructs the Alternate's basic structure from the passed 'basicData'.

		Note that this method expects that the raw bytes of the structure have already been
		unpacked.
		Also creates dummies for members not contained in the basic Data.
		"""

		# Magic Number (checked for validity)
		self.magic = basicData[0]
		if self.magic != self.__class__.MAGIC:
			if self.magic == self.__class__.MAGIC_ALIVE:
				print("Doc Alternate not marshalled (?!?!)", file=sys.stderr)
			elif self.magic == self.__class__.MAGIC_DEAD:
				print("Doc Alternate is dead... ?", file=sys.stderr)
			else:
				# Bad magic number; this isn't an Alternate
				raise ValueError("Data does not represent an Alternate! (0x%X)" % self.magic)


		# Basic Data
		self.writeable    = basicData[1] #int32_t
		self.unmarshalLen = basicData[2] #int32_t
		self.ID           = basicData[3] #int32_t
		self.rid          = basicData[4] #int32_t
		self.objectKey    = basicData[5:9] #int32_t[(sizeof(CryptoHash)/sizeof(int32_t))]
		self.objectSize   = basicData[9:11] #int32_t[2]

		# Request Header
		self.request = HTTPHdr(*(basicData[11:23])) #HTTPHdr

		# Response Header
		self.response = HTTPHdr(*(basicData[23:35])) #HTTPHdr

		# More Basic Data
		self.requestTimestamp     = basicData[35] #time_t
		self.responseTimestamp    = basicData[36] #time_t
		self.fragOffsetCount      = basicData[37] #int
		self.fragOffsetsPtr       = basicData[38]
		self.integralFragOffsets  = basicData[39:43] #uint64_t[4]

		# To be filled in later
		self.fragmentOffsets = []
		self.requestHeaders = None
		self.responseHeaders = None

	@property
	def fragOffsets(self):
		"""
		Renders an iterable of fragment offsets.

		This is mainly a convenience method which concatenates the integral
		and external frag offsets.
		"""
		return [x for x in self.integralFragOffsets] + [x for x in self.fragmentOffsets]

	def requestCtime(self) -> str:
		"""
		Gets a pretty-printed string representation of the request sent time.
		"""
		return time.ctime(self.requestTimestamp)

	def responseCtime(self) -> str:
		"""
		Gets a pretty-printed string representation of the response recieved time.
		"""
		return time.ctime(self.responseTimestamp)

	def requestURL(self) -> URL:
		"""
		Gets the url of the request made that generated this alternate.
		"""
		if self.request.URL:
			return self.request.URL
		try:
			beginning = self.requestHeaders[::-1].index('ptth') + 4
		except (IndexError, TypeError):
			utils.log_exc("Alternate.requestURL:")
			return "Unknown"

		return self.requestHeaders[-beginning:]

	def __repr__(self) -> str:
		"""
		Implements 'repr(self)'
		"""
		ret = ["Alternate(magic=0x%X" % self.magic]
		ret.append("writeable=%d" % self.writeable)
		ret.append("unmarshalLen=%d" % self.unmarshalLen)
		ret.append("ID=%d" % self.ID)
		ret.append("rid=%d" % self.rid)
		ret.append("objectKey=%r" % (self.objectKey,))
		ret.append("objectSize=%r" % (self.objectSize,))
		ret.append("request=%r" % self.request)
		ret.append("response=%r" % self.response)
		ret.append("requestTimestamp=%d" % self.requestTimestamp)
		ret.append("responseTimestamp=%d" % self.responseTimestamp)
		ret.append("%d frag offsets" % self.fragOffsetCount)
		ret.append("integralFragOffsets=%r)" % (self.integralFragOffsets,))

		return ", ".join(ret)

	def __str__(self) -> str:
		"""
		Implements `str(self)`
		"""
		ret = [str(self.requestURL())]
		ret.append("Requested:\t%s" % self.requestCtime())
		ret.append("Responded:\t%s" % self.responseCtime())

		return '\n'.join(ret)

	# This 'dangerous default value' is extremely helpful for recursive list construction
	#pylint: disable=W0102
	@classmethod
	def fromBuffer(cls,
	               raw: typing.Union[bytes, bytearray],
	               current: typing.List['Alternate']) -> typing.List['Alternate']:
		"""
		Reads the buffer passed in 'raw' for a list of Alternate objects, then returns them.

		Calls itself recursively, adding to the 'current' list on each call
		"""
		# Base Case
		if not raw:
			return current

		# Read in the constant-length stuff
		basicData = struct.unpack(cls.BASIC_FORMAT, raw[:cls.sizeof])

		# Create a new object to hold the latest Alternate being read in from 'raw'
		try:
			latest = cls(basicData)
		except ValueError:
			return current

		# The fragment table is only those fragments that lie outside the pre-allocated 'internal'
		# fragment table, so it's the fragOffsetCount less 4, but only if there actually are more
		# than 4 fragment offsets at all.
		numFrags = latest.fragOffsetCount - 4 if latest.fragOffsetCount > 4 else 0
		fragTblSize = numFrags * struct.calcsize('P')

		# Clearly I haven't figured out fragment tables yet, so my best plan is
		# to just bail when something goes wrong.
		if fragTblSize > 0:
			try:
				latest.fragmentOffsets = struct.unpack("%dP" % numFrags, raw[cls.sizeof:fragTblSize])
			except struct.error:
				utils.log("Alternate.fromBuffer: Fragment table construction error! Bailing...")
				utils.log_exc("Alternate.fromBuffer:")
				return current

		totalOffset = cls.sizeof + fragTblSize
		dataPos = totalOffset

		### Read in the Request HdrHeap
		try:

			latest.request.heapHdr = HDRHeap(raw[totalOffset : totalOffset+HDRHeap.sizeof()])

			totalOffset += latest.request.heapHdr.sizeof()

			latest.request.HdrObjImpls = unpackHeap(raw[dataPos:],
			                                        latest.request.heapHdr.sizeof(),
			                                        latest.request.heapHdr.size,
			                                        latest.request)

			### Read in the Response HdrHeap
			totalOffset = latest.response.mimeHdrHeap

			latest.response.heapHdr = HDRHeap(raw[totalOffset: totalOffset+HDRHeap.sizeof()])

			latest.response.HdrObjImpls = unpackHeap(raw[totalOffset:],
			                                         latest.response.heapHdr.sizeof(),
			                                         latest.response.heapHdr.size,
			                                         latest.response)

		except ValueError:
			return current

		# Actually, I DO know why this works. It's because I'm reading from the start of the
		# request heap data to the beginning of the response heap.
		requestHeaders = raw[dataPos:totalOffset]
		try:
			latest.requestHeaders = requestHeaders[:-5].decode()
		except UnicodeError:
			latest.requestHeaders = requestHeaders[:-5]

		try:
			theEnd = raw.index(struct.pack("I", cls.MAGIC), totalOffset)
		except ValueError:
			theEnd = -1

		responseHeaders = raw[latest.response.mimeHdrHeap + latest.response.heapHdr.size: theEnd]

		try:
			latest.responseHeaders = responseHeaders.decode()
		except UnicodeError:
			utils.log_exc("Alternate.fromBuffer:")
			latest.responseHeaders = responseHeaders

		if theEnd < 0:
			raw = b''
		else:
			raw = raw[theEnd:]

		current.append(latest)


		return cls.fromBuffer(raw, current)
		#pylint: enable=W0102

def unpackHeap(heap: bytes, offset: int, size: int, http: HTTPHdr) -> \
               typing.List[typing.Tuple[HdrHeapObjImpl, typing.List[int]]]:
	"""
	Unpacks a heap for the given HTTPHdr.

	This should allow transparent unpacking of request/response Header Heaps.
	"""
	global UNPACK_FUNCS

	ret = []

	while offset < size:
		try:
			newHdrObj = unpackHdrHeapObjImpl(heap[offset : offset+4])

			if newHdrObj.Type in UNPACK_FUNCS:
				ret.append((newHdrObj, UNPACK_FUNCS[newHdrObj.Type](heap, offset+4, http)))

			else:
				fmt = "%ds" % (newHdrObj.length-4)
				ret.append((newHdrObj,
				            struct.unpack(fmt, heap[offset+4:offset+4+struct.calcsize(fmt)])))


			offset = utils.align(offset + newHdrObj.length, utils.POINTER_SIZE)
		except (struct.error, UnicodeError):
			utils.log("http.unpackHeap: An error occurred processing -")
			utils.log_exc("http.unpackHeap:")
			try:
				utils.log("\tnewHdrObj:", newHdrObj)
			except NameError:
				pass
			utils.log("\toffset:", offset)
			utils.log("\tsize:", size)
			utils.log("\thttp:", http)
			utils.log("\tret:", ret)
			return ret

	return ret

utils.log("'http' module: Loaded")
utils.log("\\tHDRHEAP format:", HDRHeap.BASIC_FORMAT())
utils.log("\\tHDRHEAP size:", HDRHeap.sizeof())
utils.log("\\tAlternate (header) size:", Alternate.sizeof)
