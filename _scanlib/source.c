// Copyright 2018 Comcast Cable Communications Management, LLC

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

// http://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <Python.h>
#include <structmember.h>

// Dunno why this is done, nor why the macro definition isn't included in files that use it
// #define TSINLINE inline
// #include "iocore/cache/P_CacheDir.h"

PyDoc_STRVAR(_scanlib_doc,
"This module contains Apache TrafficServer data structure bindings to Python objects");

typedef struct {
	PyObject_HEAD
	uint16_t w[5];
} DirEntry;

static PyObject* DirEntry_getOffset(DirEntry* self, void* closure) {
	uint64_t val = (uint64_t)self->w[0] | (((uint64_t)self->w[1] & 0xFF) << 16) | (((uint64_t)self->w[4]) << 24);
	if (val == 0) {
		return PyLong_FromLong(0);
	}
	val = (val -1) * 512;
	return PyLong_FromUnsignedLongLong((unsigned long long)(val));
}

static int DirEntry_setOffset(DirEntry* self, PyObject* val, void* closure) {
	PyObject* tmp;
	if (val == NULL) {
		PyErr_SetString(PyExc_TypeError, "Cannot delete the 'offset' property");
		return -1;
	}

	if (!PyLong_Check(val)) {
		PyErr_SetString(PyExc_TypeError, "Offset must be an 'int'");
		return -1;
	}

	uint64_t value = PyLong_AsUnsignedLongLong(val);
	value /= 512;
	value += 1;
	self->w[0] = (uint16_t)(value);
	self->w[1] = (uint16_t)(((value >> 16) & 0xFF) | (self->w[1] & 0xFF00));
	self->w[4] = (uint16_t)(value >> 24);
	return 0;
}

static PyGetSetDef DirEntry_getsetters[] = {
	{"offset", (getter)DirEntry_getOffset, (setter)DirEntry_setOffset, "The raw offset value stored in the stripe directory. This is an offset in 'Cache Blocks'\n"
	                                                                   "from the stripe's content, so its value is not very meaningful, you should use the ``Offset``\n"
	                                                                   "property for most practical purposes. For directories not in use, this has the special ``0`` value."},
	{NULL}
};

static PyTypeObject DirEntryType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name="DirEntry",
	.tp_doc="Represents a single directory entry.\n\n"
"A ``DirEntry`` in SCAN is comparable to a ``Dir`` in the ATS cache code. In fact, it carries all\n"
"of the same information.\n"
"Both a ``Dir`` and (equivalently) a ``DirEntry`` represent all of the information required to find\n"
"and begin reading in the first piece (fragment) of a ``Doc``.\n\n"
"	Instance Members:\n"
"		* head - bool - When ``True``, this ``DirEntry`` points to a ``Doc`` that has header\n"
"			information. Specifically, this means this `DirEntry` points to the first fragment\n"
"			for a certain object, and the ``Doc`` there has ``hlen > 0``. This isn't *necessarily*\n"
"			the same thing as a \"first Doc\", as it could be either that or an \"earliest Doc\".\n"
"		* length - int - The approximate length (in bytes) of the `Doc` referred to by a specific\n"
"			``DirEntry``. This is used in ATS to quickly read the object without needing to\n"
"			immediately parse it; as such, it is guaranteed to be greater-than or equal to the\n"
"			actual length of the ``Doc``.\n"
"		* next - int - The segment-relative index of the next `Dir` for this object. If it's ``0``,\n"
"			then this is the last ``Dir``.\n"
"		* phase - bool - I personally have no idea what the meaning of this flag is. The ATS docs\n"
"			have this to say: \"Phase of the ``Doc`` (for dir valid check)\". So there you go.\n"
"		* pinned - bool - A \"pinned\" object is kept in the cache when, under normal circumstances,\n"
"			it would otherwise be overwritten. This is done via the \"evacuation\" process, which is\n"
"			highly complex, but roughly boils down to moving things away from an impending write cursor.\n"
"		* tag - int - The numeric representation of a \"partial key used for fast collision checks\".\n"
"			Whatever that means.\n"
"		* token - bool - \"Flag: Unknown\" - The ATS Docs_ So, yeah.\n"
"	Data model overrides:\n"
"		* ``bool(DirEntry)`` - bool - Tells whether the ``DirEntry`` instance is valid and in-use.\n"
"		* ``len(DirEntry)`` - int - Returns the approximate length of the `Doc` to which a ``DirEntry``\n"
"			instance points.\n"
"		* ``repr(DirEntry)`` - str - Gives the ``DirEntry`` instance in a string representation.\n"
"		* ``str(DirEntry)`` - str - Gives a short, print-ready string describing the ``DirEntry``\n"
"			instance.\n",
	.tp_basicsize = sizeof(DirEntry),
	.tp_itemsize = 0,
	.tp_flags = Py_TPFLAGS_DEFAULT,
	.tp_new = PyType_GenericNew,
	.tp_getset = DirEntry_getsetters,
};


static struct PyModuleDef _scanlib_module = {
	PyModuleDef_HEAD_INIT,
	.m_name="_scanlib",
	.m_doc=_scanlib_doc,
	.m_size=-1,
};

PyMODINIT_FUNC PyInit__scanlib(void) {
	PyObject *m;
	if (PyType_Ready(&DirEntryType) < 0) {
		return NULL;
	}

	m = PyModule_Create(&_scanlib_module);
	if (m == NULL) {
		return NULL;
	}

	Py_INCREF(&DirEntryType);
	if (PyModule_AddObject(m, "DirEntry", (PyObject*) &DirEntryType) < 0) {
		Py_DECREF(&DirEntryType);
		Py_DECREF(m);
		return NULL;
	}

	return m;
}
