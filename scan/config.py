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

	return 32 if FIPS else 16

def setLoadAvg(loadavg: str) -> typing.Optional[Loadavg]:
	"""
	Sets the maximum-allowed loadavg, not to be exceeded during scan operations.

	If the system's loadavg already is at or exceeds `loadavg`, this function will
	complete successfully, but will return the current system loadavg to the caller.

	If `loadavg` is an incorrectly-formatted loadavg, raises a ValueError.
	"""
	global MAX_LOADAVG

	# This is broken on Windows
	#pylint: disable=E1101
	currentLoadavg = os.getloadavg()
	#pylint: enable=E1101

	MAX_LOADAVG = Loadavg(tuple(float(x) for x in loadavg.split(', ')))
	for i, val in enumerate(MAX_LOADAVG):
		if val < currentLoadavg[i]:
			return currentLoadavg

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

	# Read in configs, throwing away return values cuz idc rn fam
	_ = readRecordConfig()
	_ = readStorageConfig()
	_ = readVolumeConfig()

def totalCacheSizeAvailable() -> int:
	"""
	Returns the size in bytes of the entire cache (meaning accross all cache files/devices)
	"""
	global STORAGE_CONFIG

	return sum(cache[0] for cache in STORAGE_CONFIG.values())

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

	# Read in the file as a list of lines, ignoring leading or trailing newlines
	with open(PATH+'records.config') as file:
		lines = file.read().strip().split('\n')


	# Clean out lines that are comments or only whitespace
	# lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]

	# Counts read values (can't just use `len(lines)` in case more than one file is read)
	num = 0

	for line in lines:

		line = line.strip()

		# Valid configuration lines begin with 'CONFIG'
		if line and line.startswith('CONFIG'):

			# reads in the space-separated parts of the config, ignoring extra whitespace
			# and throwing away the starting 'CONFIG'
			fields = [field for field in line.split(' ')[1:] if field]

			# Warn but don't fail when settings are redefined - keep most recent definition
			if fields[0] in RECORDS_CONFIG:
				print("WARNING: Redefinition of configuration option: %s" % fields[0])

			# Convert values to the correct type
			# (currently I only know of 'INT', 'FLOAT', and 'STRING' types)
			if fields[1] == 'INT':
				if fields[2].startswith('0x') or fields[2].endswith('h'):
					value = int(fields[2][2:], base=16)
				else:
					value = int(fields[2])
			elif fields[1] == 'FLOAT':
				value = float(fields[2])
			else:
				value = fields[2]

			# Place the value into the configuration.
			# This ignores the 'proxy.config.' that is prepended to every setting
			# (to save a little space)
			RECORDS_CONFIG[fields[0][13:]] = value

			num += 1

	return num

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

	# Read in the file as a list of lines, discarding leading or trailing newlines
	with open(PATH+'storage.config') as file:
		lines = [line.strip() for line in file.read().strip().split('\n')]

	# Obtains the storage file/device name on each non-comment, non-empty line.
	lines = [line.split(' ')[0] for line in lines if line and not line.startswith('#')]

	for cache in lines:
		STORAGE_CONFIG[cache] = (utils.fileSize(os.path.abspath(cache)), span.Span(cache))

	return len(lines)

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

	# Read in the file as a list of lines, discarding leading or trailing newlines
	with open(PATH+'volume.config') as file:
		lines = file.read().strip().split('\n')

	# Discard comments and empty lines, strip away leading and trailing whitespace on each line.
	lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]

	# Keeps track of percent-allocated space.
	totalPercent = 0

	# Keeps track of the number of volumes read
	num = 0

	for line in lines:
		try:
			volPos = line.index("volume=")
		except ValueError:
			# This means this line does not specify a volume
			continue

		num += 1

		# Parse volume number
		volumeNumber = int(line[volPos+7:line.index(' ', volPos)])
		if volumeNumber in VOLUME_CONFIG:
			raise ConfigException("Duplicates specification of volume #%d!" % volumeNumber)

		# Ignoring this, since only http is oficially supported
		scheme = utils.CacheType(1)

		# Parse size specification
		sizePos = line.index("size=")
		try:
			size = line[sizePos+5:line.index(' ', sizePos)]
		except ValueError:
			# This means the line ends immediately after size specification; with no space
			size = line[sizePos+5:]

		# Now convert sizes to numbers
		if size.endswith('%'):

			# We can't convert percent-based sizes to absolute sizes
			# if 'storage.config' has not been read
			if not STORAGE_CONFIG:
				raise ConfigException(\
				    "You cannot allocate %s of a cache with no cache files/devices specified!")

			# The percent as a number
			percentSize = int(size[:-1])

			# You can't allocate more than 100% of the available space
			totalPercent += percentSize
			if totalPercent > 100:
				raise ConfigException(\
				    "Volume #%d causes more than 100%% of available space to be allocated!"\
				    % volumeNumber)

			# Calculate absolute size in bytes, rounded down to the nearest VOL_BLOCK_SIZE
			size = int(size[:-1]) * totalCacheSizeAvailable() // 100
			size -= size % utils.VOL_BLOCK_SIZE

		# Absolute sizes are specified in MB
		else:
			size = int(size) * 0x100000

		VOLUME_CONFIG[volumeNumber] = (scheme, size)

	return num

def volumes() -> typing.Dict[int, Volume]:
	"""
	Returns a reference to the volumes defined by the configuration
	"""
	global VOLUME_CONFIG
	return VOLUME_CONFIG

def spans() -> typing.Dict[str, Cache]:
	"""
	Returns an index-able reference to the storage configuration

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

			# Ensure the proper average object size
			if not RECORDS_CONFIG:
				raise ConfigException("Cannot initialize spans without reading configuration!")

			STORAGE_CONFIG[file] = (cache[0], span.Span(cache[1]))

	return STORAGE_CONFIG

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
