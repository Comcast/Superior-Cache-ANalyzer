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
Holds structures relating to the configuration of a cache

Types:
	- type Cache: A simple type representing a single cache span (packaged with its size in Bytes)
	- type Settings: A simple type representing settings from the ats '\*.config' files
	- type Volume: A simple type representing a single cache volume, represented by its scheme and
	               absolute size (in Bytes)

Constants:
	- Settings RECORDS_CONFIG: Holds settings read in from 'records.config'
	- Dict[str, Cache] STORAGE_CONFIG: Holds specifications of cache files/devices as specified in
	                                   'storage.config'. Indexed by cache file/device name.
	- Dict[int, Volume] VOLUME_CONFIG: Holds volume information as specified in 'volume.config'.
	                                   Indexed by volume number (which starts at '1' for historic
	                                   reasons).
	- str PATH: The path to the directory where all '\*.config' files may be found.
"""

import typing
import os
from . import span, utils

# I just do these for static type analysis
Settings = typing.NewType('Settings', typing.Dict[str, typing.Union[str, int, float]])
Cache    = typing.NewType('Cache', typing.Tuple[int, span.Span])
Volume   = typing.NewType('Volume', typing.Tuple[utils.CacheType, int])
Loadavg  = typing.NewType('Loadavg', typing.Tuple[float, float, float])

# Dicts that hold the names and values of configuration options
RECORDS_CONFIG = {}
STORAGE_CONFIG = {}
VOLUME_CONFIG = {}

# The path to the directory where all '\*.config' files are located
PATH = ''

FIPS = False # Affects the length of INK_MD5 structures
MAX_LOADAVG = Loadavg((0, 0, 0)) # Affects read/writes

# The size of an MD5 hash on this system, which depends on compile-time conditions for ats
# so, it's possibly inaccurate.
def INK_MD5_SIZE() -> int:
	"""
	Returns the size of an INK_MD5 struct on this system.

	Depends on whether FIPS was enabled at compile time for ATS.

	>>> INK_MD5_SIZE()
	16

	>>> FIPS = True
	>>> INK_MD5_SIZE()
	32
	"""
	global FIPS
	sz = 32 if FIPS else 16
	utils.log("INK_MD5_SIZE:", sz)
	return sz

def setLoadAvg(loadavg: str) -> typing.Optional[Loadavg]:
	"""
	Sets the maximum-allowed loadavg, not to be exceeded during scan operations.

	If the system's loadavg already is at or exceeds `loadavg`, this function will
	complete successfully, but will return the current system loadavg to the caller.

	If `loadavg` is an incorrectly-formatted loadavg, raises a ValueError.
	"""
	global MAX_LOADAVG

	utils.log("setLoadAvg: setting to", loadavg)

	# This is broken on Windows
	#pylint: disable=E1101
	currentLoadavg = os.getloadavg()
	#pylint: enable=E1101

	utils.log("setLoadAvg: current loadavg is", currentLoadavg)

	MAX_LOADAVG = Loadavg(tuple(float(x) for x in loadavg.split(', ')))
	utils.log("setLoadAvg: MAX_LOADAVG is", MAX_LOADAVG)
	for i, val in enumerate(MAX_LOADAVG):
		if val < currentLoadavg[i]:
			return currentLoadavg
	return None

def allowedProcesses() -> int:
	"""
	Returns the number of sub-processes allowed to run without exceeding the system's loadavg limit.

	Can return zero, and if the system's maximum-allowed loadavg is not set, will return a number
	equal to `os.cpu_count()`. However, if the maximum loadavg _is_ set, this can return a number
	that is greater than the number of CPU cores, if the smallest difference between a number in the
	current loadavg and the corresponding number in the maximum loadavg is greater than the number
	of CPU cores (Note that this is unlikely).

	>>> import os
	>>> allowedProcesses() == os.cpu_count()
	True
	"""
	global MAX_LOADAVG

	if not any(MAX_LOADAVG):
		return os.cpu_count()

	# Each process could potentially spend the next 1, 5, or even 10 minutes waiting for disk I/O
	# or CPU time.
	#pylint: disable=E1101
	currentLoadavg = os.getloadavg()
	#pylint: enable=E1101

	maxAllowed = int(min((MAX_LOADAVG[i] - currentLoadavg[i] for i in range(3))))

	utils.log("allowedProcesses: maxAllowed is", maxAllowed)

	return max((0, maxAllowed))

class ConfigException(Exception):
	"""
	An exception raised when something goes wrong with reading ATS configuration.
	"""
	def __init__(self,
	             msg:str = "You must set `PATH` first! (try using `init`)",
	             err:Exception = None):
		"""
		Initializes the configuration exception

		Sets the string representation of this exception to the value given by `msg`,
		and will record any and all inner exceptions in `err`.
		"""
		super(ConfigException, self).__init__()
		self.msg = msg

		self.innerException = err

	def __str__(self) -> str:
		"""
		Implements `str(self)`
		"""
		return self.msg

	def __repr__(self) -> str:
		"""
		Implements `repr(self)`

		Also displays inner exceptions, if they exist
		"""
		if self.innerException:
			return "\n".join((self.msg, str(self.innerException)))
		return self.msg

def init(path: str):
	"""
	Initializes the configuration
	"""
	global PATH

	if not path.endswith('/'):
		path += '/'
	PATH = path

	utils.log("config.init: reading configuration files from", PATH)

	num = readRecordConfig()
	utils.log("config.init: records.config lines:", num)
	num = readStorageConfig()
	utils.log("config.init: storage.config cache definitions:", num)
	num = readVolumeConfig()
	utils.log("config.init: volume.config volume definitions:", num)

def totalCacheSizeAvailable() -> int:
	"""
	Returns the size in bytes of the entire cache (meaning accross all cache files/devices)
	"""
	global STORAGE_CONFIG

	return sum(cache[0] for cache in STORAGE_CONFIG.values())

def parseRecordConfig(contents: str) -> Settings:
	"""
	Parses the contents of a records.config file and returns the contained settings
	"""
	lines = contents.strip().split('\n')

	ret = {}
	for line in lines:
		line = line.strip()

		if line and line.startswith("CONFIG"):
			utils.log("config.parseRecordConfig: config line:", line)

			name, Type, value = [field for field in line.split(' ')[1:] if field]

			if name in ret:
				utils.log("config.parseRecordConfig: Double-definition of", name)

			# A decimal or hexidecimal integer
			if Type == "INT":
				# hex
				if value.startswith("0x"):
					value = int(value[2:], base=16)
				elif value.endswith('h'):
					value = int(value[:-1], base=16)
				# decimal
				else:
					value = int(value)
			elif Type == "FLOAT":
				value = float(value)

			ret[name] = value

	return ret

def readRecordConfig() -> int:
	"""
	Reads in the configuration options from the 'records.config' file

	Returns the number of settings read.
	Raises an OSError when the 'records.config' file cannot be read for any reason.
	Raises a ConfigException if `PATH` has not been set
	"""
	global PATH, RECORDS_CONFIG

	# Ensure 'PATH' is set
	if not PATH:
		raise ConfigException()

	fname = os.path.join(PATH, 'records.config')

	utils.log("readRecordConfig: opening file", fname, "for reading")

	# Read in the file as a list of lines, ignoring leading or trailing newlines
	with open(fname) as file:
		contents = file.read()


	# Clean out lines that are comments or only whitespace
	# lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]

	# Counts read values (can't just use `len(lines)` in case more than one file is read)
	num = 0

	records = parseRecordConfig(contents)

	RECORDS_CONFIG.update(records)

	return len(records)

def parseStorageConfig(contents: str) -> typing.Dict[str, Cache]:
	"""
	Parses the contents of a 'storage.config' file and returns a dictionary of cache file
	names to cache objects.
	"""
	global PATH

	contents, ret = contents.strip().split('\n'), {}

	for i,line in enumerate(contents):
		cache = line.strip()

		if cache.startswith('#'):
			continue

		# I'm currently ignoring everything except for the cache name, size will be
		# determined by examining the actual cache file.
		cache = cache.split(' ')[0]

		if os.path.isfile(cache):
			cache = os.path.abspath(cache)
		elif os.path.isdir(cache):
			cache = os.path.join(os.path.abspath(cache), 'cache.db')
			if not os.path.isfile(cache):
				raise OSError("line %d '%s' in storage.config specifies a directory "\
				              "which does not appear to contain a cache file!"%(line,i))

		# TODO: this doesn't work on Windows, should be checking for an alphabetic character
		# TODO: followed by `:\` on that system (ideally w/o regex)
		elif not cache.startswith(os.sep):
			try:
				sep = PATH.index('etc')
			except ValueError:
				utils.log_exc("config.parseStorageConfig:")
				try:
					sep = PATH.index('config')
				except ValueError:
					utils.log_exc("config.parseStorageConfig:")
					raise OSError("Couldn't find cache file specified on storage.config line %d '%s'"\
					                                                                      % (i, line))
			cache = os.path.abspath(os.path.join(PATH.split('etc')[0], cache))
		ret[cache] = (utils.fileSize(cache), span.Span(cache))

	return ret

def readStorageConfig() -> int:
	"""
	Reads in the cache files from the 'storage.config' file

	Returns the number of cache files/devices found in the config file.
	Will raise some kind of OSError if the file cannot be found/read.
	"""
	global PATH, STORAGE_CONFIG

	# Ensure `PATH` is set.
	if not PATH:
		raise ConfigException()

	fname = os.path.join(PATH, 'storage.config')
	utils.log("readStorageConfig: opening file", fname, "for reading")

	# Read in the file as a list of lines, discarding leading or trailing newlines
	with open(fname) as file:
		contents = file.read()

	caches = parseStorageConfig(contents)

	STORAGE_CONFIG.update(caches)

	return len(caches)

def parseVolumeConfig(contents: str) -> typing.Dict[int, Volume]:
	"""
	Parses the contents of a volume.config file and returns a dict of
	volume numbers to Volume objects
	"""
	global STORAGE_CONFIG

	contents, ret, totalPercent = contents.strip().split('\n'), {}, 0

	for line in contents:
		line = line.strip()

		if line.startswith('#') or "volume=" not in line:
			continue

		utils.log("parseVolumeConfig: volume definition:", line)

		position = line.index("volume=")
		volumeNo = line[position+7:line.index(' ', position)]
		volumeNo = int(volumeNo)

		if volumeNo in contents:
			raise ConfigException("Duplicate specifications of volume #%d!" % (volumeNo,))

		position = line.index("size=")

		try:
			size = line[position+5:line.index(' ', position)]
		except ValueError:
			# This likely means the line ends right after the size specification
			size = line[position+5:]

		size = size.lower() # For size suffixes

		# Now convert sizes to numbers
		if size.endswith('%'):
			utils.log("parseVolumeConfig: converting percent-based size in", line, "to absolute size")

			# We can't convert percent-based sizes to absolute sizes
			# if 'storage.config' has not been read (because we don't know the total)
			if not STORAGE_CONFIG:
				raise ConfigException(\
				    "You cannot allocate %s of a cache with no cache files/devices specified!")

			size = int(size[:-1])
			totalPercent += size
			if totalPercent > 100:
				raise ConfigException("Line '%s' in volume.config causes more than 100%% of space "\
				                      "to be used!" % (line,))

			size = int(size * totalCacheSizeAvailable() // 100)

		else:
			size = int(size) * 0x100000

		utils.log("parseVolumeConfig: real size (in Bytes) is", size)

		ret[volumeNo] = (utils.CacheType(1), size) # Currently assuming everything is an HTTP cache

	return ret


def readVolumeConfig() -> int:
	"""
	Reads in the volume information stored in the 'volume.config' file

	Returns the number of volumes specified.
	Raises a ConfigException if `PATH` is not set.
	Raises a ConfigException if a volume is double-specified.
	Raises a ConfigException if a volume's size is specified as a percent,
	    but no cache files/devices have been read in yet.
	Raises a ConfigException if more than 100% of a cache set is allocated.
	Raises some kind of OSError if the 'volume.config' file cannot be opened or read from.
	"""
	global PATH, VOLUME_CONFIG, STORAGE_CONFIG

	if not PATH:
		raise ConfigException()

	fname = os.path.join(PATH, 'volume.config')
	utils.log("readVolumeConfig: opening file", fname, "for reading")

	# Read in the file as a list of lines, discarding leading or trailing newlines
	with open(fname) as file:
		contents = file.read()

	volumeDefinitions = parseVolumeConfig(contents)

	VOLUME_CONFIG.update(volumeDefinitions)

	return len(volumeDefinitions)

def volumes() -> typing.Dict[int, Volume]:
	"""
	Returns a reference to the volumes defined by the configuration
	"""
	global VOLUME_CONFIG
	return VOLUME_CONFIG

def spans() -> typing.Dict[str, Cache]:
	"""
	Returns an index-able, sorted reference to the storage configuration

	This function will initialize all of the spans specified,
	if they have not already been initialized.

	Raises a ConfigException if 'records.config' has not been read
	(necessary to determine the proper average_object_size)
	"""
	global STORAGE_CONFIG, RECORDS_CONFIG

	# Ensure we know the average object size
	if not RECORDS_CONFIG:
		raise ConfigException("'records.config' MUST be read before attempting to read spans.")

	# If someone wants to get all the spans, we should ensure they are all initialized
	for file, cache in STORAGE_CONFIG.items():

		if cache[1] is None:
			utils.log("config.spans: initializing span at", file)

			# Ensure the proper average object size
			if not RECORDS_CONFIG:
				raise ConfigException("Cannot initialize spans without reading configuration!")

			STORAGE_CONFIG[file] = (cache[0], span.Span(cache[1]))

	return {f: (sz, sp) for f,(sz,sp) in sorted(STORAGE_CONFIG.items(), key=lambda x: x[0])}

def settings() -> Settings:
	"""
	Returns all the settings specified in the various '\*.config' files

	This does not return volumes or spans from 'volume.config' or 'storage.config'.
	"""
	global RECORDS_CONFIG
	return RECORDS_CONFIG

def getSetting(setting: str) -> typing.Union[str, int, float]:
	"""
	Gets a specific setting from the configuration.

	This function will attempt to resolve settings both with and
	without a stripped-out common prefix (e.g. 'proxy.config.')
	"""
	allSettings = settings()

	if setting in allSettings:
		return allSettings[setting]

	prefixedsetting = 'proxy.config.%s' % setting
	if prefixedsetting in allSettings:
		return allSettings[prefixedsetting]

	return "setting '%s' unset or invalid" % setting

utils.log("'config' module: Loaded")
