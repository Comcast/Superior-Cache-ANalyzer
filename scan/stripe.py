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
Contains data structures that represent stipe objects and sub-objects.
"""

import struct
import typing
import time
import asyncio
import io
import multiprocessing
import numpy as np
from . import directory, utils
#uncommentif PYTHON_MAJOR_VERSION > 5
#from . import config
#endif


class SpanBlockHeader():
	"""
	The header for a single span block (or 'stripe')

	Instance Variables:
	 - number: int -- The number of this stripe within the span to which it belongs.
	 - offset: int -- The offset within the span at which the stripe content may be found
	 - length: int -- The length of this stripe in Bytes
	 - Type: utils.CacheType -- The cache type of this stripe (currently only HTTP is supported)
	 - free: bool -- Whether or not this span is in use.
	"""

	########################################################
	###                                                  ###
	###                  STATIC CONSTANTS                ###
	###                                                  ###
	########################################################

	# The format of a span block header:
	# two unsigned long longs, one signed int, and two unsigned ints
	BASIC_FORMAT = "QQiI"
	# those last two 'I's are bitfields (3b and 1b, respectively),
	# so they get packed in a special way.


	sizeof = struct.calcsize(BASIC_FORMAT)

	########################################################
	###                                                  ###
	###              DATA MODEL OVERRIDES                ###
	###                                                  ###
	########################################################


	def __init__(self, raw_data: typing.Union[bytes, typing.Tuple[int,int,int,int]]):
		"""
		Initializes the header

		raw_data: bytes -- The raw header data.
		raises: struct.error -- if unpacking fails.
		"""
		utils.log("SpanBlockHeader.__init__: raw_data:", raw_data)
		if isinstance(raw_data, bytes):
			self.offset,\
			self.length,\
			self.number,\
			typeFree = struct.unpack(self.BASIC_FORMAT, raw_data)


		# This assumes that raw_data is a tuple of 4 integers.
		else:
			self.offset,\
			self.length,\
			self.number,\
			typeFree = raw_data

		self.Type = utils.CacheType(typeFree & 0x07)
		self.free = (typeFree & 0x08) == 0x08

		# This currently isn't working (it's off by 2 and idk why)
		# if self.length % self.VOL_BLOCK_SIZE:
		# 	raise ValueError

		# Sets the average object size according to the ATS configuration (defaults to 8000)
		from . import config # Ugly, but avoids a python 3.4-specific circular import problem
		self.avgObjSize = 8000
		configuration = config.settings()
		if 'cache.min_average_object_size' in configuration:
			self.avgObjSize = configuration['cache.min_average_object_size']

	def __bool__(self) -> bool:
		"""
		Implements `bool(self)`

		returns: bool -- `True` if the block is in use, else `False`
		"""
		return not self.free

	def __len__(self) -> int:
		"""
		Implements 'len(self)'

		returns: int -- the length of the span block (in bytes) to which this header **refers**,
		**NOT** the length of the header itself.
		"""
		return self.length * utils.STORE_BLOCK_SIZE

	def __str__(self) -> str:
		"""
		Implements `str(self)`

		returns: str -- the span block type and number.
		"""
		return "%s: #%d" % (self.Type, self.number)

	def __repr__(self) -> str:
		"""
		Implements `repr(self)`

		returns: str -- a verbose string showing all of the span block header's relevant information.
		"""
		ret = "SpanBlockHeader(number=%d, offset=0x%X, length=%d, Type=%s, free=%s, avgObjSize=%d)"
		return ret % (self.number, self.offset, self.length, self.Type, self.free, self.avgObjSize)


class Stripe():
	"""
	The intersection of a cache span and a cache volume.
	"""

	########################################################
	###                                                  ###
	###                  STATIC CONSTANTS                ###
	###                                                  ###
	########################################################

	MAGIC = 0xF1D0F00D

	BASIC_FORMAT = "Ihhl3Q8I"

	sizeof = struct.calcsize(BASIC_FORMAT)

	########################################################
	###                                                  ###
	###              INSTANCE DATA MEMBERS               ###
	###                                                  ###
	########################################################

	@property
	@asyncio.coroutine
	def segments(self) -> typing.Generator[directory.Segment, None, None]:
		"""
		This generator renders stripes iterable over their segments.

		Yields successive segments from the stripe, using 'getSegment' to
		obtain values.
		"""
		for seg in range(self.numSegs):
			yield self.getSegment(seg)

	@property
	@asyncio.coroutine
	def buckets(self) -> typing.Generator[directory.Bucket, None, None]:
		"""
		This generator method renders stripes iterable over their buckets.

		Yields successive buckets from the stripe, using 'getBucket' to obtain
		values.
		"""

		for i in range(self.numSegs):
			for j in range(self.numBuckets // self.numSegs):
				yield self.getBucket(i, j)

	@property
	@asyncio.coroutine
	def heads(self) -> typing.Generator[directory.DirEntry, None, None]:
		"""
		An iterable of the 'head' DirEntrys in this stripe.

		Yields successive 'head's from the stripe.
		Unusable if `self.read` has not been called.
		Only yields `DirEntry`s determined to be "phase-valid" (see `scan.directory.DirEntry.valid`)
		Raises an IndexError if the directory is corrupt
		"""
		# Selects for non-zero offsets
		heads = self.directory[\
		                          self.directory[:,0] + \
		                          (self.directory[:,1] & 0xFF) + \
		                          self.directory[:,4] \
		                      > 0]

		# Selects for in-phase heads
		if self.phase:
			yield from heads[heads[:,2] & 0x3000 == 0x3000]
		else:
			yield from heads[(heads[:,2] & 0x3000) ^ 0x2000 == 0]

	@property
	@asyncio.coroutine
	def firstDocs(self) -> typing.Generator[directory.Doc, None, None]:
		"""
		This generator method renders stripes iterable over their 'first Docs'

		Note that this method does *not* call `self.fetch` to obtain each `Doc`,
		so as to avoid the overhead of opening and closing the file multiple
		times, nor does it call `self.fetchWithFile` to facilitate possible
		threaded reads in the future, as well as to avoid function call overhead.

		Yields successive 'first' Docs from the stripe, reading
		in values as needed.
		Raises an OSError if the stripe's file cannot be read from.
		Captures Exceptions raised during Doc construction, and prints summaries
		if running without optimization.
		"""

		# Passes in here are necessary because `assert` statements may not exist when run with
		# -OO, so without them it could throw a SyntaxError with the message "Expected indented
		# block".
		#pylint: disable=W0107
		with io.open(self.file, 'rb') as f:
			for d in self.heads:
				buffer = bytearray(directory.dirSize(d))

				f.seek(self.contentOffset + directory.dirOffset(d))

				# read in the entire structure at once
				f.readinto(buffer)

				doc = directory.Doc.from_buffer(buffer[:directory.Doc.sizeof])

				if doc.magic == directory.Doc.MAGIC and doc.hlen > 0:
					try:
						doc.setInfo(buffer[directory.Doc.sizeof : doc.hlen])
						doc.setData(buffer[directory.Doc.sizeof + doc.hlen : len(doc)])
					except struct.error as e:
						utils.log("Stripe.firstDocs: Error reading doc pointed to by", d,":", e)
						utils.log_exc("Stripe.firstDocs:")
						pass
					else:
						yield doc
				elif doc.magic == directory.Doc.CORRUPT_MAGIC:
					assert not print("Corrupt Doc pointed to by %s: '%s'" % (d, doc))
					pass
		#pylint: enable=W0107

	########################################################
	###                                                  ###
	###              DATA MODEL OVERRIDES                ###
	###                                                  ###
	########################################################

	def __init__(self, raw_header:typing.Union[bytes, typing.Tuple[int,int,int,int,int]], file:str):
		"""
		Constructs the stripe header from the data provided in 'raw_header'.

		Note that the free-list, directory and footer should be omitted.
		"""
		utils.log("Stripe.__init__: raw_header:", raw_header)
		self.spanBlockHeader = SpanBlockHeader(raw_header)
		utils.log("Stripe.__init__: spanBlockHeader:", self.spanBlockHeader)

		# holds the file of this stripe to avoid referencing the span on every read
		self.file = file

		# placeholders for things that will be read in/calculated on-demand
		self.version = "Unknown"
		self.createTime = -1
		self.writeCursor = -1
		self.lastWritePos = -1
		self.aggPos = -1
		self.generation = -1
		self.phase = -1
		self.cycle = -1
		self.syncSerial = -1
		self.writeSerial = -1
		self.dirty = -1
		self.sectorSize = -1
		self.unused = -1
		self.numBuckets = -1
		self.numSegs = -1
		self.numDirEntries = -1
		self.contentOffset = -1
		self.directoryOffset = -1
		self.validityLimit = -1

		# This will hold a memory map of the stripe's directory
		self.directory = None

		# Caches the urls stored in a stripe.
		self.objs = []

	def __repr__(self) -> str:
		"""
		Implements 'repr(self)'

		Assumes a stripe's data has been read in if and only if its creation time is non-negative.
		"""
		# Data has not yet been read in
		if self.createTime < 0:
			return "Stripe(header=%r, file=%s)" % (self.spanBlockHeader, self.file)

		# Data has been read in
		ret = ["Stripe(header=%r" % self.spanBlockHeader]
		ret.append("file=%s" % self.file)
		ret.append("version=%s" % self.version)
		ret.append("createTime=%f" % self.createTime)
		ret.append("writeCursor=%d" % self.writeCursor)
		ret.append("lastWritePos=%d" % self.lastWritePos)
		ret.append("aggPos=%d" % self.aggPos)
		ret.append("generation=%d" % self.generation)
		ret.append("phase=%d" % self.phase)
		ret.append("cycle=%d" % self.cycle)
		ret.append("syncSerial=%d" % self.syncSerial)
		ret.append("writeSerial=%d" % self.writeSerial)
		ret.append("dirty=%d" % self.dirty)
		ret.append("sectorSize=%d" % self.sectorSize)
		ret.append("unused=%d" % self.unused)
		ret.append("numBuckets=%d" % self.numBuckets)
		ret.append("numSegs=%d" % self.numSegs)
		ret.append("numDirEntries=%d" % self.numDirEntries)
		ret.append("contentOffset=0x%X" % self.contentOffset)
		ret.append("directoryOffset=0x%X" % self.directoryOffset)
		ret.append("%d cached objects)" % len(self.objs))

		return ", ".join(ret)

	def __str__(self) -> str:
		"""
		Implements 'str(self)'
		"""
		if self.createTime > 0:
			return "%s\t%s\t%d" % (self.spanBlockHeader,
			                       self.ctime(),
			                       len(self.spanBlockHeader))
		return "%s\tUNREAD (use 'Stripe.read')\t%dB" % (self.spanBlockHeader,
		                                               len(self.spanBlockHeader))

	def __len__(self) -> int:
		"""
		Returns the size in bytes of this span in the cache
		"""
		return len(self.spanBlockHeader)

	def __getitem__(self,
	                indicies: typing.Union[int,
	                                       typing.Tuple[int, int],
	                                       typing.Tuple[int, int, int]]
	                ) -> typing.Union[directory.Segment, directory.Bucket, directory.DirEntry]:
		"""
		Implements self[item], self[itema, itemb], self[itema, itemb, itemc]
		(and by extension: self[itema][itemb] and self[itema][itemb][itemc])

		Returns a list of buckets in a segment (if given one index),
		or a single bucket of 4 dirs (if given two indicies)
		"""
		# Fetch a single segment as a list of buckets
		if isinstance(indicies, int):
			return self.getSegment(indicies)

		# Fetch a single bucket as a tuple of Dirs
		elif isinstance(indicies, tuple) and all(isinstance(i, int) for i in indicies):
			if len(indicies) in { 2, 3 }:
				bucket = self.getBucket(*(indicies[:2]))
				if len(indicies) == 2:
					return bucket
				elif len(indicies) == 3:
					return bucket[indicies[2]]


		# Malformed selector
		raise IndexError("Index of a Stripe should be one, two or three integers!")


	########################################################
	###                                                  ###
	###                 INSTANCE METHODS                 ###
	###                                                  ###
	########################################################

	def read(self):
		"""
		Reads in the data of the stripe from the file init'ed from

		This is not done from the initializer, because it's not always necessary to walk
		through a stripe's directory in order for it to be useful. However, this method
		MUST be called prior to fetching either `DirEntry`s or `Doc`s out of the stripe.
		"""
		utils.log("Stripe.read: reading in metadata for", self)

		with io.open(self.file, 'rb') as infile:

			raw_header_A = bytearray(self.sizeof)
			infile.seek(self.spanBlockHeader.offset)
			infile.readinto(raw_header_A)

			# Now I need to determine the size of the metadata. Currently, the only way
			# to know this for sure is to  either seek across the disk, one store block at
			# a time, or use this iterative approach. I opted for this, because it's cleaner
			# and in all likelihood faster for non-RAM devices.
			# This will likely change in cache version 25.0, but until then...
			self.numBuckets,\
			self.numSegs,\
			self.contentOffset = SORdirSize(self.spanBlockHeader.offset, len(self))

			self.directoryOffset= utils.align(self.spanBlockHeader.offset+self.sizeof+2*self.numSegs)

			# The SOR method gets me the buckets _per segment_
			self.numBuckets *= self.numSegs
			self.numDirEntries = 4 * self.numBuckets

			# Now we need to check the copy B data to see if it's newer - otherwise what we're
			# looking at isn't up-to-date.
			offsetB = utils.align(self.directoryOffset + 10*self.numDirEntries) + self.sizeof
			offsetB = utils.align(offsetB)
			utils.log("Stripe.read: offset calculated for copy B metadata:", hex(offsetB))
			infile.seek(offsetB)
			raw_header_B = bytearray(self.sizeof)
			infile.readinto(raw_header_B)


		A = struct.unpack(self.BASIC_FORMAT, raw_header_A)
		utils.log("Stripe.read: raw header for copy A:", A)
		B = struct.unpack(self.BASIC_FORMAT, raw_header_B)
		utils.log("Stripe.read: raw header for copy B:", B)

		del raw_header_A, raw_header_B

		# Whichever metadata copy has a greater sync_serial value is more up-to-date, so if that's
		# copy B some things need to be updated. However, for large stripes there's an error in the
		# calculations for the offset of B, so we first ensure that it contains a valid magic number.
		if B[0] == this.MAGIC and B[10] > A[10]:
			self.spanBlockHeader.offset = offsetB
			self.directoryOffset = utils.align(offsetB + self.sizeof+2*self.numSegs)
			data = B
			del A
		else:
			data = A
			del B

		magic = data[0]
		if magic != self.MAGIC:
			utils.log("Stripe.read: Bad MAGIC Value:", hex(magic))
			raise ValueError("Stripe does not appear to valid!")

		self.version      = "%d.%d" % (data[1], data[2])
		self.createTime   = data[3]
		self.writeCursor  = data[4]
		self.lastWritePos = data[5]
		self.aggPos       = data[6]
		self.generation   = data[7]
		self.phase        = data[8] != 0 #This is orders of magnitude faster than `bool(data[8])`
		self.cycle        = data[9]
		self.syncSerial   = data[10]
		self.writeSerial  = data[11]
		self.dirty        = data[12]
		self.sectorSize   = data[13]
		self.unused       = data[14]

		# This is used to determine the validity of a DirEntry
		self.validityLimit = self.aggPos - self.contentOffset
		if self.phase:
			self.validityLimit += self.writeCursor
		self.validityLimit //= 0x200

		utils.log("Stripe.read: Finished reading metadata for", self)

	def readDir(self):
		"""
		Reads in the entire directory. Not for the faint of heart.

		I *highly* recommend that if this is used, you later do `self.directory.clear()`
		so that memory usage doesn't get out of control.
		Note that you *MUST* have called `self.read()` prior to the calling of this method.
		"""
		utils.log("Stripe.readDir: reading in directory for", self)
		with io.open(self.file, 'rb', self.numDirEntries * 10) as infile:
			infile.seek(self.directoryOffset)

			self.directory = np.fromfile(infile,
			                             dtype=directory.npDirEntry,
			                             count=self.numDirEntries).view(dtype='u2')\
			                                                      .reshape(self.numDirEntries, 5)

	def getSegment(self, index: int) -> directory.Segment:
		"""
		Gets the 'index'th segment of this stripe's directory, as a list of Buckets.

		Think very carefully about whether or not this really what you want. For the vast
		majority of applications, it's probably better to look for a specific Bucket instead,
		since loading an entire segment into memory can be extremely expensive, both in terms
		of speed and memory usage.
		"""
		seglen = self.numDirEntries // self.numSegs
		index *= seglen
		return [directory.DirEntry(bytearray(d)) for d in self.directory[index : index + seglen]]

	def getBucket(self, segment: int, bucket: int) -> directory.Bucket:
		"""
		Fetches the 'bucket'th bucket from the 'segment'th segment.

		This method is provided for consistency's sake; I wouldn't really
		expect anyone to use it.
		Only fetches valid directory entries - any directory with an offset
		of 0 is returned as None to save space.
		"""
		index = 4*((segment * self.numSegs // self.numBuckets) + bucket)

		return [directory.DirEntry(bytearray(d)) for d in self.directory[index : index + 4]]

	def ctime(self) -> str:
		"""
		Pretty-prints the creation time of the stripe
		"""
		return time.ctime(self.createTime)

	#pylint: disable=R0201,W0613,W0104,E0102
	@typing.overload
	def fetch(self, segIndex: int, bucketIndex: int, dirIndex: int) -> directory.Doc:
		"""
		Fetches the Doc pointed to by the Dir at the indicated indices.
		"""
		...

	@typing.overload
	def fetch(self, dent: directory.DirEntry, unused_bidx =None, unused_didx =None)->directory.Doc:
		"""
		Fetches the Doc to which a specific Directory Entry refers
		"""
		...
	#pylint: enable=R0201,W0613,W0104

	def fetch(self, arg0, arg1=None, arg2=None) -> directory.Doc:
		"""
		Fetches the Doc to which a specific Directory Entry refers.

		Will fetch using either a `DirEntry` object or a tuple of indicies that specify a `DirEntry`.
		If the first argument is a `DirEntry`, the other two are ignored and either a `Doc` object is
		returned if the read was successful, or a `ValueError` is raised if the read fails (which can
		happen for currently unknown reasons, esp. in RAM device caches).
		If all three arguments are `int`s, then the `DirEntry` is first plucked from `self.directory`,
		and the `Doc` is subsequently read in (returning the `Doc` if successful, raising a `ValueError`
		otherwise), or an `IndexError` will be raised if the directory has not yet been read in (see
		`self.read`) or a `ValueError` will be raise if the directory *has* been read in, but the
		`DirEntry` specified by the indicies does not point to a valid location.

		If not in debug mode, instead of raising exceptions, this method will return `None`
		"""

		# Set the DirEntry we're using according to the arguments
		if isinstance(arg0, directory.DirEntry):
			dirent = arg0
		elif isinstance(arg0, int) and isinstance(arg1, int) and isinstance(arg2, int):
			try:
				dirent = self.directory[arg0, arg1, arg2]
			except IndexError:
				utils.log_exc("Stripe.fetch:")
				return None
		else:
			utils.log("Stripe.fetch: Bad arguments:", self, arg0, arg1, arg2)
			raise TypeError("'stripe.fetch' expects either one DirEntry or three integers!")


		# If the dirent isn't valid, we're already done
		if not dirent:
			utils.log("Stripe.fetch: Directory Entry specified by", arg0, arg1, arg2, "is not valid!")
			utils.log("Stripe.fetch: (Offending DirEntry: %r)" % (dirent,))
			return None


		# Now read in the actual doc information
		docbuff = bytearray(len(dirent))
		with io.open(self.file, 'rb') as infile:

			infile.seek(self.contentOffset + dirent.Offset)
			infile.readinto(docbuff)

		newDoc = directory.Doc.from_buffer(docbuff[:directory.Doc.sizeof])
		if newDoc.magic != directory.Doc.MAGIC:
			utils.log("Stripe.fetch: DirEntry does not point to a valid Doc! (",arg0,"->",newDoc,")")
			return None

		newDoc.setInfo(docbuff[directory.Doc.sizeof:newDoc.hlen])
		newDoc.setData(docbuff[directory.Doc.sizeof+newDoc.hlen : len(newDoc)])

		return newDoc
	#pylint: enable=E0102

	def fetchWithFile(self, d: directory.DirEntry, strict: bool = False) -> directory.Doc:
		"""
		Fetches a Doc from the specified DirEntry, using an open file descriptor.

		This should cut down quite a bit on unnecessary disk I/O.
		Note that this expects self.file to be an open file handle.
		Will restore the file's stream position before returning.

		If `strict` is `True`, then this will not fetch data for docs with hlen == 0, and in that
		case will return `None`

		Raises an `AttributeError` if self.file isn't an open file handle.
		Returns the constructed Doc read from the file, with initialized alternates if present.
		"""
		#store stream position to restore later
		oldpos = self.file.tell()

		# seek to the object
		self.file.seek(self.contentOffset + d.Offset)

		docbuff = bytearray(len(d))

		# Read the entire thing at once (faster than incremental reads)
		self.file.readinto(docbuff)

		# Separate he doc header bytes from the rest
		dhead = docbuff[ : directory.Doc.sizeof]

		# Attempt doc header construction
		try:
			doc = directory.Doc.from_buffer(dhead)
		except ValueError:
			utils.log_exc("Stripe.fetchWithFile:")
			return None
		finally:
			# restore stream position
			self.file.seek(oldpos)

		docbuff = docbuff[doc.sizeof() : len(doc)]

		if doc.hlen > 0:
			doc.setInfo(docbuff[ : doc.hlen])
		elif strict:
			return None

		doc.setData(docbuff[doc.hlen : ])

		return doc

	def index(self, dirent: directory.DirEntry) -> typing.Tuple[int, int, int]:
		"""
		Finds the indicies of the passed dirent within this stripe.

		Returns the segment index, bucket index and directory index as a tuple (in that order).
		Intended behaviour is such that `self.index(self[i, j, k])` returns `(i, j, k)`
		Will raise an error only AFTER iterating across the entire (read) directory if `dirent`
		is some object other than a `directory.Direntry`.
		"""
		for i, d in enumerate(self.directory):
			if d is dirent:
				segLocalIndex, seg = divmod(i, self.numSegs)
				entry, bucket = divmod(segLocalIndex, 4)
				return seg, bucket, entry
		raise IndexError("DirEntry could not be located in stripe!")

	@asyncio.coroutine
	def storedObjects(self) -> typing.Generator[typing.Tuple[str, int], None, None]:
		"""
		Fetches the urls of all objects stored in the stripe.
		"""
		# This assumes that the last time objects were read, they were read to completion.
		# If that's not the case, then this *cannot* accurately report what is stored in the
		# cache. If you aren't sure, do `self.objs.clear()` first.
		if self.objs:
			yield from self.objs
		else:
			for doc in self.firstDocs:
				# not strictly accurate, but should be close, and I don't wanna fetch all of the
				# earliest docs for every alternate.
				sz = doc.totalLength
				for a in doc.alternates:
					url = a.requestURL()
					self.objs.append((url, sz))
					yield url, sz



	########################################################
	###                                                  ###
	###           Parallel Reads (EXPERIMENTAL)          ###
	###                                                  ###
	########################################################
	def parallelObjs(self, q: multiprocessing.Queue, dirPart: np.ndarray):
		"""
		Renders the objects pointed to from `DirEntry`s in the given `dirPart`.

		Rather than generate or return these objects, this method will assume that it is being
		run in a sub-process (or thread) and will push these values into the given Queue, `q`.

		When the assigned part of the directory has been exhausted, this method will put the special
		`None` value into the Queue, signaling its termination.
		"""
		fd = io.open(self.file, 'rb')
		ds, dm, cm = directory.Doc.sizeof, directory.Doc.MAGIC, directory.Doc.CORRUPT_MAGIC
		try:
			for d in dirPart:
				docbuff = bytearray(directory.dirSize(d))
				fd.seek(self.contentOffset + directory.dirOffset(d))
				fd.readinto(docbuff)

				doc = directory.Doc.from_buffer(docbuff[:ds])

				if doc.magic == dm and doc.hlen > 0:
					try:
						doc.setInfo(docbuff[ds : doc.hlen])
						doc.setData(docbuff[ds + doc.hlen : len(doc)])
					except struct.error as e:
						utils.log("Stripe.parallelObjs: Error reading doc pointed to by", d, ':', e)
						utils.log_exc("Stripe.parallelObjs:")
					else:
						sz = doc.totalLength
						for a in doc.alternates:
							url = a.requestURL()
							q.put((url, sz))
				elif doc.magic == cm:
					utils.log("Stripe.parallelObjs: Corrupt Doc pointed to by", d, ':', doc)
		finally:
			fd.close()
			q.put(None)


	def parallelStoredObjects(self):
		"""
		Yields from a list of objects stored in the stripe.

		This method aims to do exactly the same thing as self.storedObjects, but by doing reads in
		parallel.
		It does, however, respect the configuration's maximum-allowed loadavg and will only use
		subprocesses if the configuration reports that this is permissible. If not, it will fall
		back on `self.storedObjects`.
		"""

		# Yield cached objects if they exist.
		if self.objs:
			yield from self.objs
			return

		from . import config

		# This will eventually change to respect the system loadavg
		numprocs = config.allowedProcesses()
		if not numprocs:
			yield from self.storedObjects()
			return


		# I'm going to just ignore things that are out-of-phase for now
		heads = self.directory[\
		                          self.directory[:,0] + \
		                          self.directory[:,4] + \
		                          (self.directory[:,1] & 0xFF)\
		                      > 0]

		# Sometimes, nothing is cached
		if not heads.any():
			return

		if self.phase:
			heads = heads[heads[:,2] & 0x3000 == 0x3000]
		else:
			heads = heads[(heads[:,2] & 0x3000) ^ 0x2000 == 0]

		sliceSize = len(heads) // numprocs

		# If there's fewer heads than available processes, then we can probably get away
		# with unthreaded reads.
		if not sliceSize:
			utils.log("Stripe.parallelStoredObjects: Only need to process",
			          len(heads),
			          "heads - doing single-process yield.")
			yield from self.storedObjects()
			return

		utils.log("Stripe.parallelStoredObjects: splitting job for",
		          len(heads),
		          "heads into",
		          numprocs,
		          "processes")

		m = multiprocessing.Manager()
		q = m.Queue()

		# I pre-slice the directory partly to avoid issues when len(self.directory) % numprocs > 0
		# and partly to handle passing the Queue to the child processes.
		slicedDir = [(q, heads[i:i+sliceSize]) for i in range(0, (numprocs-1)*sliceSize, sliceSize)]
		slicedDir.append((q, heads[(numprocs - 1) * sliceSize:]))

		pool = multiprocessing.Pool(processes=numprocs)

		pool.starmap_async(self.parallelObjs, slicedDir, error_callback=print)
		pool.close()

		try:
			count = 1
			while count < numprocs:
				val = q.get()
				if val is None:
					count += 1
				else:
					self.objs.append(val)
					yield val
		finally:
			pool.join()




def SORdirSize(start: int, length: int) -> typing.Tuple[int, int, int]:
	"""
	This function uses the Successive Over-Relaxation technique to find the
	content offset, segment count, and bucket count of a stripe.

	Returns (in order): the bucket count (per segment), the segment count, and
	the content offset of the stripe with the given starting offset and length.
	"""
	#if PYTHON_MAJOR_VERSION < 6
	from . import config
	avgObjSize = 8000
	configuration = config.settings()
	if 'cache.min_average_object_size' in configuration:
		avgObjSize = configuration['cache.min_average_object_size']
	#endif
	#uncommentif PYTHON_MAJOR_VERSION > 5
	#avgObjSetting = 'cache.min_average_object_size'
	#configuration = config.settings()
	#avgObjSize = 8000 if avgObjSetting not in configuration else configuration[avgObjSetting]
	#endif

	def singleStep(buckets: int, segs: int, content: int) -> typing.Tuple[int, int, int]:
		"""
		Represents a single step in the iterative Successive Over-Relaxation
		"""
		nonlocal length, start, avgObjSize

		buckets = (length - content + start) // (4 * avgObjSize)

		segs = -(-buckets // 0x4000)

		buckets = -(-buckets // segs)

		content = start + 16384 * ( -(-(34 + segs) // 4096) - (-5 * buckets * segs // 1024) + 1 )

		return buckets, segs, content


	# I'm told three times is sufficient for this. Don't ask me.
	return singleStep(*singleStep(*singleStep(0, 0, start)))

utils.log("'stripe' module: Loaded")
utils.log("\t\tSpan Block Header size:", SpanBlockHeader.sizeof)
utils.log("\t\tStripe (metadata) size:", Stripe.sizeof)
