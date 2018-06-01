"""
Provides a simple User Interface for the scanner.
"""

# `readline` doesn't work on Windows...
#pylint: disable=E0401
import readline
#pylint: enable=E0401
import typing
import sys
import re
import os
# from . import blocks
from . import config

# ANSI control sequence that clears the screen
CLEAR = "\033[H\033[J"

def byteSized(size: int) -> str:
	"""
	Takes a size (in bytes) given by 'size' and returns a human-readable measure of the same number
	"""
	if size < 999:
		return "%dB" % size
	if size / 0x400 < 999:
		return "%1.1fkB" % (size/0x400)
	if size / 0x100000 < 999:
		return "%1.1fMB" % (size/0x100000)
	return "%1.2fGB" % (size/0x40000000)

def setCompleter(words: typing.Set[str]):
	"""
	Sets tab completion to operate on the passed set `words`
	"""

	def complete(text: str, state: int) -> str:
		"""
		Gets the `state`th completion for `text`
		"""
		nonlocal words

		return [word for word in words if word.startswith(text)][state]

	readline.set_completer_delims(' \t\n;')
	readline.parse_and_bind("tab: complete")
	readline.set_completer(complete)

def getConfig():
	"""
	Gets the location of the storage.conf file from the user,
	then reads and parses it using the 'storage' module.
	"""
	global MENU_ENTRIES, CLEAR

	print("Enter the path to your '*.config' files")
	print("(or 'q' to go back to the previous menu)\n")
	choice = input("[/opt/trafficserver/etc/trafficserver]: ")

	print(CLEAR)

	if not choice:
		choice = '/opt/trafficserver/etc/trafficserver'
	if choice.lower() != 'q':
		try:
			config.init(choice)
		except FileNotFoundError as e:
			print("Configuration could not be read!\n%s\n" % e, file=sys.stderr)
		except ValueError as e:
			print("Error reading configuration file: %s" % e, file=sys.stderr)
		except OSError as e:
			print("Error in config file - cache not found: %s" % e, file=sys.stderr)
		else:
			del MENU_ENTRIES[0]
			MENU_ENTRIES.append(("Show Cache Setup", printCache))
			MENU_ENTRIES.append(("List Settings", printConfig))
			MENU_ENTRIES.append(("Search for Setting", searchSetting))
			MENU_ENTRIES.append(("List Stripes in a Span", listSpanStripes))
			MENU_ENTRIES.append(("View URLs of objects in a Span", listSpanURLs))
			MENU_ENTRIES.append(("View usage of a Span broken down by host", spanUsageByHost))
			MENU_ENTRIES.append(("Dump cache usage stats to file (Tabular YAML format)", dumpUsageToFile))

def printConfig():
	"""
	Prints the loaded configuration options
	"""

	print("From 'records.config':")

	for setting, value in config.settings().items():
		if isinstance(value, str):
			typename = "STRING"
		else:
			typename = type(value).__name__.upper()

		print("proxy.config.%s" % setting, typename, value)
	print()

def searchSetting():
	"""
	Search through settings for those matching a given search string.

	Regular expressions are allowed as input.
	"""
	global CLEAR

	settings = config.settings()

	setCompleter(settings.keys())

	while True:
		print("Enter the name of the setting you are searching for.")
		choice = input("(name or regex of setting, 'l' to list settings, or 'q' to go back): ")

		print(CLEAR)

		if choice.lower() == 'q':
			break
		elif choice.lower() == 'l':
			for setting in config.settings():
				print(setting)
			continue

		if choice in settings:
			print(choice, '=', settings[choice])
			break

		matches = []
		try:
			regex = re.compile(".*%s.*" % choice)
			matches = [(setting, settings[setting])\
			           for setting in settings\
			           if regex.match(setting) is not None]
		except re.error:
			print("Not a valid regex: '%s' !" % choice, file=sys.stderr)
		else:
			if matches:
				for match in matches:
					print(match[0], match[1], sep='\t')
				break
			print("No settings matched '%s'" % choice)
	print()

def printCache():
	"""
	Prints the loaded cache spans and volumes
	"""

	print("Cache files:")
	for location, cache in config.spans().items():
		print(location, cache[1], byteSized(cache[0]), sep='\t')

	print("\nVolumes:")
	for number, vol in config.volumes().items():
		print("#%d" % number, vol[0], byteSized(vol[1]), sep='\t')

	print()

def listSpanStripes():
	"""
	Lists the span blocks in a user-specified span.
	"""
	global CLEAR

	caches = config.spans()
	setCompleter(caches.keys())

	while True:
		choice = input("Enter the span you wish to inspect\n"\
		               "(span, 'l' to list spans, or 'q' to go back): ")

		print(CLEAR)

		if choice.lower() == 'q':
			break

		elif choice in caches:
			for stripe in caches[choice][1]:
				print("%s stripe, created %s (version %s)" % (byteSized(len(stripe)),
				                                              stripe.ctime(),
				                                              stripe.version))
			_ = input("\nPress Enter to continue...")
			print(CLEAR)
			break


		elif choice.lower() == 'l':
			for location in config.spans():
				print(location)
			print()

		else:
			print("Please choose a valid cache file.")

def listSpanURLs() -> str:
	"""
	Prints out the urls for all objects stored in a span.
	"""
	global CLEAR

	spans = config.spans()
	spanFiles = {span for span in spans}

	setCompleter(spanFiles)

	while True:
		print("Choose a span for which to list URLs\n")

		choice = input("(span, 'l' to list spans, or 'q' to go back): ")

		print(CLEAR)

		if choice.lower() == 'l':
			print(*spanFiles, sep='\n')
			print()
		elif choice.lower() == 'q':
			return ''
		elif choice in spans:
			urls = {}
			for i, obj in enumerate(spans[choice][1].storedObjects()):
				if obj[0] not in urls:
					urls[obj[0]] = [byteSized(obj[1]), 0]
				urls[obj[0]][1] += 1

				# 127 is pretty arbitrary, but it should keep the numbers different enough that
				# nobody will suspect it's not updating on every iteration
				if i % 127 == 0:
					print("\033[K\033[H%d objects found so far..." % i)

			return '\n'.join("%s\t - %s - \tx%d" % (k, v[0], v[1]) for k, v in urls.items())\
			           if urls else "No URLs found!"
		else:
			print("Please enter a valid span.\n", file=sys.stderr)

def spanUsageByHost() -> str:
	"""
	Prints out the usage statistics for a span broken down by hostname.
	"""
	global CLEAR

	spans = config.spans()

	while True:
		print("Choose a span to analyze:\n")
		choice = input("(span, 'l' to list spans, or 'q' to go back): ")

		print(CLEAR)

		# List spans
		if choice.lower() == 'l':
			print(*(span for span in spans), sep='\n')
			print()

		# Quit to main menu
		elif choice.lower() == 'q':
			return ''

		elif choice in spans:
			hosts = {}

			fmt = "%s\t - %s - \t%1.2f%% of available space - \t%1.2f%% of used space"

			for i, (url, sz) in enumerate(spans[choice][1].storedObjects()):
				if url.host not in hosts:
					hosts[url.host] = 0
				hosts[url.host] += sz

				# print our progress
				if i % 127 == 0:
					print("\033[K\033[H%d objects found so far..." % i)

			print(CLEAR)

			total = sum(hosts.values())

			if hosts:
				return '\n'.join(fmt % (k, byteSized(v), v/spans[choice][0], 100*v/total)\
			    	   for k, v in hosts.items())
			return "No URLs found!"

def dumpUsageToFile():
	"""
	Dumps all usage information to a file.

	So far, operates on all spans sequentially. Should
	eventually do all simultaneously, but w/e.
	"""
	global CLEAR

	while True:
		choice = input("Enter a file name to save to (or 'q' to go back): ")

		print(CLEAR)

		if choice.lower() == 'q':
			break

		if not choice.endswith(".tyaml") and not choice.endswith(".tyml"):
			choice += ".tyaml"

		if os.path.exists(choice):
			print("File already exists!", file=sys.stderr)
		else:
			try:
				with open(choice, 'w') as f:
					f.write("%TYAML 1.1\n---\n")
					for file, (_, s) in sorted(config.spans().items()):
						print("Working on %s..." % file)
						f.write(file)
						f.write(':')
						objs = {}
						for obj in s.storedObjects():
							if obj[0] not in objs:
								objs[obj[0]] = [obj[1], 0]
							objs[obj[0]][1] += 1
						if objs:
							f.write('\n')
							for obj, val in objs.items():
								f.write("\t%s:\n\t\tsize: %d\n\t\tnum: %d\n" % (obj, val[0], val[1]))
						else:
							f.write(" None\n")
						print(CLEAR)
				return "Done!"
			except OSError as e:
				print("Could not write to '%s'! (%s)" % (choice, e), file=sys.stderr)
			except ValueError as e:
				print("Error!:", e, file=sys.stderr)

def nonInteractiveDump():
	"""
	Dumps the usage stats to stdout without any user input.

	On success, writes output to stdout in TYAML format.
	Coallesces errors generated by external functions to `OSError` for easy catch in the caller.
	"""
	try:
		config.init('/opt/trafficserver/etc/trafficserver')
	except FileNotFoundError as e:
		raise OSError("Configuration could not be read! '%s'" % e)
	except ValueError as e:
		raise OSError("Error reading configuration file: '%s'" % e)
	except OSError as e:
		raise OSError("Error in config file - cache not found: '%s'" % e)

	# I'm not going to print until a span is fully scanned, to avoid partial outputs when errors occur
	# and to minimize I/O overhead
	buffer = ["%TYAML", "---"]

	# Supposedly, local var lookup is much faster than global, so this should boost performance
	append = buffer.append
	clear = buffer.clear
	output = lambda x: print(*x, sep='\n')
	bs = byteSized

	try:

		for file, (_, s) in sorted(config.spans().items()):
			append("%s:" % file)
			for url, sz in s.storedObjects():
				append("\t%s: %s" % (url, bs(sz)))
			output(buffer)
			clear()
	except KeyboardInterrupt:
		# Terminate gracefully when requested.
		print("Warning, job terminated early! Quitting...", file=sys.stderr)
		if buffer:
			output(buffer)

def dumpSingleSpan(spanFile: str) -> int:
	"""
	Dumps usage stats for a single cache span.

	Returns an exit code based on the success or failure of the dump
	"""
	spans = config.spans()
	if spanFile not in spans:
		print("Error: '%s' is not a cache span!" % spanFile, file=sys.stderr)
		return 1

	print("%TYAML 1.1")
	print("---")
	print(spanFile, ':', sep='')

	bs = byteSized
	try:
		for url, sz in spans[spanFile][1].storedObjects():
			print("\t%s: %s" % (url, bs(sz)))
	except KeyboardInterrupt:
		print("Warning, job terminated early! Quitting...", file=sys.stderr)
		return 2
	return 0

MENU_ENTRIES = [("Read Storage config", getConfig)]

def mainmenu():
	"""
	The UI's main menu, which executes ui and library functions based on user input
	"""
	global CLEAR, MENU_ENTRIES

	print(CLEAR)

	while True:
		# Sets up tab completion for the Main Menu
		# setCompleter({entry[0] for entry in MENU_ENTRIES})
		print("Choose an option (or option number)\n")
		for index, entry in enumerate(MENU_ENTRIES):
			print("[%d] %s" % (index+1, entry[0]))
		print()

		choice = input("(option, or use ^C or ^D to quit): ")

		# ANSI sequence that clears the screen
		print(CLEAR)

		try:
			choice = int(choice)-1
			if choice in range(len(MENU_ENTRIES)):
				output = MENU_ENTRIES[choice][1]()
				if output:
					print(output)
			else:
				raise ValueError()
		except ValueError:
			print("Please enter a valid option number")
