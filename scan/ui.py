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
Provides a simple User Interface for the scanner.
"""

import typing
import sys
import re
import os
try:
	import readline
except ImportError:
	try:
		import pyreadline as readline
	except ImportError:
		print("Scan was not properly installed on your system!", file=sys.stderr)
		print("Please see the install instructions and/or file an issue at"\
		      " https://github.com/Comcast/Superior-Cache-ANalyzer", file=sys.stderr)
import glob

from . import config, utils

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

	matches = []

	def complete(text: str, state: int) -> str:
		"""
		Gets the `state`th completion for `text`
		"""
		nonlocal matches, words

		if state == 0:
			if text:
				matches = [word for word in words if word.startswith(text)]
			else:
				matches = [word for word in words]

		return matches[state]

	readline.set_completer_delims(' \t\n;')
	readline.parse_and_bind("tab: complete")
	readline.set_completer(complete)

def setGlobCompleter():
	"""
	Sets tab completion to operate on the filesystem
	"""

	complete = lambda t,s: [x for x in glob.glob(t+"*")][s] if t else None

	readline.set_completer(complete)
	readline.set_completer_delims(' \t\n;')
	readline.parse_and_bind("tab: complete")

def loadConfig(confDir: str):
	"""
	Attempts to load the configuration from 'confDir'.
	"""
	global MENU_ENTRIES, CLEAR

	utils.log('ui.loadConfig: attempting to read config from', confDir)

	if not os.path.isdir(confDir):
		out = "Couldn't load configuration directory: '%s' - doesn't exist or is not a directory."
		print(out % (confDir,), file = sys.stderr)
		return

	try:
		config.init(confDir)
	except FileNotFoundError as e:
		utils.log_exc("ui.loadConfig:")
		print("Configuration could not be read!\n%s\n" % e, file=sys.stderr)
	except ValueError as e:
		utils.log_exc("ui.loadConfig:")
		print("Error reading configuration file: %s" % e, file=sys.stderr)
	except OSError as e:
		utils.log_exc("ui.loadConfig:")
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
		print(CLEAR)


def getConfig():
	"""
	Gets the location of the storage.conf file from the user,
	then reads and parses it using the 'storage' module.
	"""
	global MENU_ENTRIES, CLEAR

	setGlobCompleter()

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
			utils.log_exc("ui.getConfig:")
			print("Configuration could not be read!\n%s\n" % e, file=sys.stderr)
		except ValueError as e:
			utils.log_exc("ui.getConfig:")
			print("Error reading configuration file: %s" % e, file=sys.stderr)
		except OSError as e:
			utils.log_exc("ui.getConfig:")
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
			s = caches[choice][1]
			if s:
				for stripe in s:
					print("%s stripe, created %s (version %s)" % (byteSized(len(stripe)),
					                                              stripe.ctime(),
					                                              stripe.version))
				_ = input("\nPress Enter to continue...")
				print(CLEAR)
			else:
				print("No stripes found!")
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
	setCompleter(spans.keys())

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
				utils.log_exc("ui.dumpUsageToFile:")
				print("Could not write to '%s'! (%s)" % (choice, e), file=sys.stderr)
			except ValueError as e:
				utils.log_exc("ui.dumpUsageToFile:")
				print("Error!:", e, file=sys.stderr)

def nonInteractiveDump():
	"""
	Dumps the usage stats to stdout without any user input.

	On success, writes output to stdout in TYAML format.
	Coallesces errors generated by external functions to `OSError` for easy catch in the caller.
	"""

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

def spanUsageByHostDump(c: config.Cache) -> str:
	"""
	Returns a Tabular YAML-formatted representation of the cache `c`'s usage, broken down
	by host.

	Does NOT include the TYAML header.
	Uses no base indentation level.
	"""
	hosts = {}
	fmt = "%s:\n\t\tDocs: %d\n\t\tTotalSize: %s\n\t\tPercentOfAvailableSpace: "\
	      "%1.2f%%\n\t\tPercentOfUsedSpace: %1.2f%%"

	for url, sz in c[1].storedObjects():
		if url.host not in hosts:
			hosts[url.host] = [0, 0]
		hosts[url.host][0] += 1
		hosts[url.host][1] += sz

	total = sum(s for _,s in hosts.values())

	hosts = [fmt % (h, n, byteSized(s), 100.0*s/c[0], 100.0*s/total)\
	         for h,(n,s) in\
	         sorted(hosts.items(), key=lambda x: x[1][1], reverse=True)]

	return '\n'.join(hosts)


def breakDownDump(spanFile: str = None):
	"""
	Dumps a breakdown of cache usage by host to stdout.

	If `spanFile` is given, it is the only span for which stats are dumped, else, stats are dumped
	for each span in the cache.
	"""
	spans = config.spans()
	if spanFile:
		utils.log("ui.breakDownDump: Dumping usage breakdown for", spanFile)
		if spanFile not in spans:
			print("Error: '%s' is not a cache span!" % (spanFile,), file=sys.stderr)
			return 1
		print("%TYAML 1.1\n---")
		print(spanUsageByHostDump(spans[spanFile]))
		return 0

	utils.log("ui.breakDownDump: Dumping usage breakdown for entire cache")

	print("%TYAML\n---")
	try:
		for s in spans:
			print(s, ':\n\t', sep='', end='')
			print(spanUsageByHostDump(spans[s]).replace('\n', "\n\t"))
	except KeyboardInterrupt:
		print("Warning, job terminated early! Quitting...", file=sys.stderr)
		return 2
	return 0


MENU_ENTRIES = [("Read Storage config", getConfig)]

def mainmenu(confDir: str = None):
	"""
	The UI's main menu, which executes ui and library functions based on user input
	"""
	global CLEAR, MENU_ENTRIES

	print(CLEAR)

	if confDir:
		loadConfig(confDir)

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
			utils.log_exc("ui.mainmenu:")
			print("Please enter a valid option number")
