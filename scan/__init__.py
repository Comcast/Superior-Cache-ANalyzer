"""
SCAN - Superior Cache ANalyzer
Analyzes Apache Traffic Server on-disk caches
"""
import sys

__version__ = "2.2.1"

__author__ = "Brennan W. Fieck"

def main() -> int:
	"""
	Main routine
	"""

	# force optimization (assert statements are left out when '-O' is specified.)
	try:
		assert False
	except AssertionError:
		from os import execl
		execl(sys.executable, sys.executable, '-OO', *sys.argv)


	from . import ui
	from . import config
	import argparse

	parser = argparse.ArgumentParser(description="Superior Cache ANalyzer.",
	                                 epilog="Note that if `loadavg` is not specified, SCAN will"\
	                                 " set its 'ionice' to the lowest value possible to negate"\
	                                 " its impact on ATS operation.")
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
		except OSError as e:
			# Only supported on Linux kernel v > 2.16.3+ and Windows > Vista
			print("WARNING: ionice not supported on your system. May cause heavy I/O load!",
			      file=sys.stderr)
			print("(Info: %s)" % e, file=sys.stderr)

	if args.dump is None:
		try:
			ui.nonInteractiveDump()
		except OSError as e:
			print("Unable to scan cache: '%s'" % e, file=sys.stderr)
			return 1
		return 0
	elif args.dump:
		config.init('/opt/trafficserver/etc/trafficserver/')

		return ui.dumpSingleSpan(args.dump)


	try:
		ui.mainmenu()
	except (KeyboardInterrupt, EOFError):
		print()
	return 0
