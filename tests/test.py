#!/usr/bin/env python3

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
This module contains a suite of unit tests for the SCAN utility
"""
#pylint: disable=W0212
import typing
import struct
import os
import sys
import argparse


try:
	from scan import utils, directory, span, config, stripe
except ImportError as e:
	print("Tests should be run from the project's root directory (or while it's installed)! (%s)" % e, file=sys.stderr)
	exit(1)

DISK_HEADER_SIZE = struct.calcsize("=5IQ")
SPAN_BLOCK_HEADER_SIZE = struct.calcsize("4IiII")
SPAN_BLOCK_HEADER_LENGTH = 0x4000 * utils.STORE_BLOCK_SIZE

# offset: 4294967296
# length: 4294967296
rawSpanBlockHeader = struct.pack("4IiII", 0, 1, 0, 1, 1, 1, 0)

rawDirEntry = struct.pack("HHHHH", 0xA000, 0, 0x2FFF, 0, 0)

def testSpan() -> typing.List[str]:
	"""
	Checks the loaded span against what it should be.
	"""
	results = []

	if not config.spans():
		return ["(Span): No spans loaded!"]

	s = config.spans()['storage/cache.db'][1]

	# Disk Header tests
	if s.header.sizeof != DISK_HEADER_SIZE:
		results.append("header size incorrect, is %d, should be %d" % \
		                                (s.header.sizeof, DISK_HEADER_SIZE))

	if s.header.volumes != 1:
		results.append("found %d volumes in header, expected 1" % (s.header.volumes,))

	if s.header.free:
		results.append("header.free was %d, should've been 0" % (s.header.free,))

	if s.header.used != 1:
		results.append("header.used was %d, should've been 1" % (s.header.used,))

	if s.header.diskvolBlocks != 1:
		results.append("found %d diskvol_blocks in header, should've been 1" % (s.header.diskvolBlocks,))

	if s.header.blocks != 0x7fff00000000:
		results.append("found 0x%X blocks in header, should've been 0x7fff00000000" % (s.header.blocks,))

	if len(s.header) != s.header.diskvolBlocks:
		results.append("header length should be equal to diskvolBlocks (was %d, expected %d)" %\
		                                                          (len(s.header), s.header.diskvolBlocks))

	# Actual span tests
	if len(s.blocks) != 1:
		results.append("found %d blocks, should've been 1" % (len(s.blocks),))

	if len(s) != len(s.blocks):
		results.append("length '%d' doesn't match number of blocks '%d'" % (len(s), len(s.blocks)))

	return ["(Span): %s" % r for r in results] + testStripe(s[0])


def testSpanBlockHeader(sbh: stripe.SpanBlockHeader) -> typing.List[str]:
	"""
	Tests various aspects of a stripe.

	Returns a list of the tests failed.
	"""
	results = []

	if sbh.sizeof != SPAN_BLOCK_HEADER_SIZE:
		results.append("sizeof returns %d, should be %d!" %\
		                          (sbh.sizeof, SPAN_BLOCK_HEADER_SIZE))

	if sbh.number:
		results.append("number was %d, should've been 0" % (sbh.number,))

	if sbh.offset != 0x4000:
		results.append("offset was 0x%X, should've been 0x4000" % (sbh.offset,))

	if sbh.length != 0x4000:
		results.append("length was 0x%X, should've been 0x4000" % (sbh.length,))

	if len(sbh) != SPAN_BLOCK_HEADER_LENGTH:
		results.append("len() was 0x%X, should've been 0x%X" % (len(sbh), SPAN_BLOCK_HEADER_LENGTH))

	if sbh.Type is not utils.CacheType.HTTP:
		results.append("type was %r, should've been CacheType.HTTP" % (sbh.Type,))

	if not sbh.free:
		results.append("reported it was unused, should have been used.")

	if sbh.avgObjSize != 8000:
		results.append("average object size was %d, should've been 8000" % (sbh.avgObjSize,))

	return ["(SpanBlockHeader): %s" % r for r in results]


def testDirEntry(dirent: directory.DirEntry = None) -> typing.List[str]:
	"""
	Tests various aspects of a DirEntry.

	Returns a list of the tests failed.
	"""
	results = []


	if dirent is None:
		dirent = directory.DirEntry(rawDirEntry)

	if dirent._offset != 0xA000:
		results.append("bad offset bits, expected 0xA000, got '0x%X'" % dirent._offset)

	if dirent.Offset != 0xA000 * config.INK_MD5_SIZE():
		results.append("bad offset, expected 0x%X, got '0x%X'" %\
		                 (0xA000*config.INK_MD5_SIZE(), dirent.Offset))

	if not dirent:
		results.append("__bool__ gave 'False' when 'True' was expected")

	if len(dirent) != 0x200:
		results.append("bad size, expected 512, got '%d" % len(dirent))

	if dirent.sizeof != 10:
		results.append("sizeof gave wrong size, expected 10, got '%d'" % dirent.sizeof)

	if dirent.next != 0:
		results.append("bad next value, expected 0 got '%d'" % dirent.next)

	if dirent.token:
		results.append("token was set, but shouldn't be")

	if dirent.pinned:
		results.append("pinned was set, but shouldn't be")

	if dirent.phase:
		results.append("phase was set, but shouldn't be")

	if not dirent.head:
		results.append("head was not set, but should be")

	return ["(DirEntry): %s" % r for r in results]

def testDoc(doc: directory.Doc = None) -> typing.List[str]:
	"""
	Tests various aspects of a Doc.

	Returns a list of the tests failed.
	"""
	# TODO - figure out what Doc is and test it here.
	return []

def testStripe(s: stripe.Stripe) -> typing.List[str]:
	"""
	Tests various aspects of a stripe

	Returns a list of the tests failed.
	"""

	results = []

	s.readDir()

	if s.writeCursor != 0x60000:
		results.append("write cursor at 0x%X, should've been at 0x60000" % (s.writeCursor,))

	if s.lastWritePos != 0x60000:
		results.append("last write position at 0x%X, should've been at 0x60000" % (s.lastWritePos,))

	if s.aggPos != 0x60000:
		results.append("agg. position at 0x%X, should've been at 0x60000" % (s.aggPos,))

	if s.generation:
		results.append("generation was %d, should've been 0" % (s.generation,))

	if s.phase:
		results.append("phase was %d, should've been 0" % (s.phase,))

	if s.cycle:
		results.append("cycle was %d, should've been 0" % (s.cycle,))

	if s.syncSerial:
		results.append("sync-serial was %d, should've been 0" % (s.syncSerial,))

	if s.writeSerial:
		results.append("write-serial was %d, should've been 0" % (s.writeSerial,))

	if s.dirty:
		results.append("dirty was %d, should've been 0" % (s.dirty,))

	if s.sectorSize != 0x1000:
		results.append("sector size was 0x%X, should've been 0x1000" % (s.sectorSize,))

	if s.unused:
		results.append("unused was %d, should've been 0" % (s.unused,))

	if s.numBuckets != 4182:
		results.append("contains %d buckets, but should have 4182" % (s.numBuckets,))

	if s.numSegs != 1:
		results.append("has %d segments, should be 1" % (s.numSegs,))

	if s.numDirEntries != 16728:
		results.append("contains %d DirEntrys, but should be 16728" % (s.numDirEntries,))

	if s.contentOffset != 0x60000:
		results.append("content starts at 0x%X, but should start at 0x60000" % (s.contentOffset,))

	if s.directoryOffset != 0x6000:
		results.append("directory (copy A) starts at 0x%X, but should start at 0x6000" % (s.directoryOffset,))


	return ["(Stripe): %s" % r for r in results] + testSpanBlockHeader(s.spanBlockHeader)

def main() -> int:
	"""
	Runs the tests and prints the failed tests to stdout followed by a count of passed/failed tests.

	Returns the number of failed tests.
	"""
	args = argparse.ArgumentParser(description="Testing Suite for the Superior Cache ANalyzer",
	                               epilog="NOTE: this test assumes that the cache is in the state defined "\
	                               "by scan.test.py, which is meant to run this test script through autest.")
	args.add_argument("--ats_configs",
	                  help="Specify the path to an ATS installation's config files to use for the tester."\
	                       " (if --ats_root is also specified, this should be relative to that)",
	                  type=str)
	args.add_argument("--ats_root",
	                  help="Specify the path to the root ATS installation (NOTE: Changes the pwd)",
	                  type=str)
	args = args.parse_args()

	if args.ats_root:
		os.chdir(args.ats_root)
		here = os.listdir()
		print(here)
		if 'config' in here:
			print(os.listdir("./config/"))
	if args.ats_configs:
		config.init(args.ats_configs)

	results = testSpan()

	for result in results:
		print(result)

	print("Failed %d tests." % len(results))

	return len(results)

if __name__ == '__main__':
	# Once tests are stable, will exit with `main`'s return value.
	exit(main())
