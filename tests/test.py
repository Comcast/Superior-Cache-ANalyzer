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

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


try:
	from scan import utils, directory, span, config, stripe
except ImportError as e:
	print("Tests should be run from the project's root directory! (%s)" % e, file=sys.stderr)
	exit(1)

# offset: 4294967296
# length: 4294967296
rawSpanBlockHeader = struct.pack("4IiII", 0, 1, 0, 1, 1, 1, 0)

rawDirEntry = struct.pack("HHHHH", 0xA000, 0, 0x2FFF, 0, 0)


def testSpanBlockHeader(sbh: stripe.SpanBlockHeader = None) -> typing.List[str]:
	"""
	Tests various aspects of a stripe.

	Returns a list of the tests failed.
	"""
	results = []

	if not sbh:
		sbh = stripe.SpanBlockHeader(rawSpanBlockHeader)

	if sbh.sizeof != struct.calcsize("4IiII"):
		results.append("sizeof returns %d, should be %d!" %\
		                                   (sbh.sizeof, struct.calcsize("4IiII")))

	if not sbh:
		results.append("reported it was unused, should have been used.")

	if sbh.offset != 4294967296:
		results.append("bad offset, expected 4294967296 got %d" % sbh.offset)

	if sbh.Type != utils.CacheType.HTTP:
		results.append("type incorrect, expected 'http' got '%s'" % sbh.Type)

	if len(sbh) != 4294967296:
		results.append("bad length, expected 4294967296 got %d" % len(sbh))

	if sbh.number != 1:
		results.append("number incorrect, expected 1 got %d" % sbh.number)

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

def testStripe() -> typing.List[str]:
	"""
	Tests various aspects of a stripe

	Returns a list of the tests failed.
	"""
	s = stripe.Stripe(rawSpanBlockHeader, "tests/test.db")

	results = testSpanBlockHeader(s.spanBlockHeader)

	s.read()

	return ["(Stripe): %s" % r for r in results]

def main() -> int:
	"""
	Runs the tests and prints the failed tests to stdout followed by a count of passed/failed tests.

	Returns the number of failed tests.
	"""
	results = testSpanBlockHeader()
	results += testDirEntry()
	results += testDoc()

	for result in results:
		print(result)

	print("Failed %d tests." % len(results))

	return len(results)

if __name__ == '__main__':
	# Once tests are stable, will exit with `main`'s return value.
	_ = main()
	exit(0)
