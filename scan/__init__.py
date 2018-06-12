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
SCAN - Superior Cache ANalyzer
Analyzes Apache Traffic Server on-disk caches
"""
import sys

__version__ = "2.2.6"

__author__ = "Brennan W. Fieck"

def main() -> int:
	"""
	Main routine
	"""

	import argparse

	parser = argparse.ArgumentParser(description="Superior Cache ANalyzer.",
	                                 epilog="Note that if `loadavg` is not specified, SCAN will"\
	                                 " set its 'ionice' to the lowest value possible to negate"\
	                                 " its impact on ATS operation.")
	parser.add_argument("-c",
	                    "--config-dir",
	                    help="Specify the directory in which to find config files.",
	                    type=str)

	parser.add_argument("-f",
	                    "--fips",
	                    help="If specified, SCAN will recognize that ATS was compiled with"\
	                    " `ENABLE_FIPS` (usually not the case; not well-supported)",
	                    action='store_const',
	                    const=True,
	                    default=False)

	parser.add_argument("-l",
	                    "--loadavg",
	                    help="If specified, sets the maximum loadavg, not to be exceeded by SCAN"\
	                    " operation. Note that if your system is already at or above this loadavg,"\
	                    " SCAN will be unable to run",
	                    type=str)

	parser.add_argument("-d",
	                    "--dump",
	                    help="Dump the cache's usage stats and exit.",
	                    nargs='?',
	                    type=str,
	                    default=False)

	parser.add_argument("--debug",
	                    help="Logs debug output to stderr.",
	                    action="store_const",
	                    const=True,
	                    default=False)

	parser.add_argument("-V",
	                    "--version",
	                    help="Prints version information and exits",
	                    action="store_const",
	                    const=True,
	                    default=False)

	args = parser.parse_args()

	if args.version:
		from platform import python_implementation as impl, python_version as ver
		print("Superior Cache ANalyzer (SCAN)", "v%s" % __version__)
		print("Running on", impl(), "v%s" % ver())
		return 0

	if __debug__ and not args.debug:
		# force optimization (will set __debug__ = False)
		from os import execl
		execl(sys.executable, sys.executable, '-OO', *sys.argv)

	from . import ui
	from . import config

	if args.fips:
		config.FIPS = True

	if args.loadavg:
		try:
			currentLoadAvg = config.setLoadAvg(args.loadavg)
			if currentLoadAvg is not None:
				print("System already at or above specified loadavg!", file=sys.stderr)
				print("(Specified: '%s'," % args.loadavg, "Current: '%s')" % (currentLoadAvg,),
				      file=sys.stderr)
				return 1
		except ValueError:
			if __debug__:
				from traceback import print_exc
				print_exc(file=sys.stderr)
			print("Invalid loadavg: '%s'" % args.l, file=sys.stderr)
			return 1

	# If loadavg is specified, we don't need to do this, because the assumption is that every process
	# could wait forever for I/O
	else:
		# Portable way to set our i/o priority to the lowest possible
		# That way it won't interfere with actual ATS cache read/writes
		import os
		import psutil
		try:
			p = psutil.Process(os.getpid())
			p.ionice(psutil.IOPRIO_CLASS_IDLE)
		except ValueError:
			if __debug__:
				from traceback import print_exc
				print_exc(file=sys.stderr)
			p.ionice(0) # Windows > Vista
		except (OSError, AttributeError) as e:
			if __debug__:
				from traceback import print_exc
				print_exc(file=sys.stderr)
			# either not Linux kernel v > 2.16.3+ or we're on BSD/OSX
			print("WARNING: ionice not supported on your system. May cause heavy I/O load!",
			      file=sys.stderr)
			print("(Info: %s)" % e, file=sys.stderr)

	if args.dump is None:
		confDir = args.config_dir if args.config_dir else "/opt/trafficserver/etc/trafficserver"
		try:
			config.init(config_dir)
			ui.nonInteractiveDump()
		except (OSError, FileNotFoundError, ValueError) as e:
			if __debug__:
				from traceback import print_exc
				print_exc(file=sys.stderr)
			print("Unable to scan cache: '%s'" % e, file=sys.stderr)
			return 1
		return 0
	elif args.dump:
		confDir = args.config_dir if args.config_dir else "/opt/trafficserver/etc/trafficserver"
		config.init(confDir)

		return ui.dumpSingleSpan(args.dump)


	try:
		if args.config_dir:
			ui.mainmenu(args.config_dir)
		else:
			ui.mainmenu()
	except (KeyboardInterrupt, EOFError):
		if __debug__:
			from traceback import print_exc
			print_exc(file=sys.stderr)
		print()
	return 0
