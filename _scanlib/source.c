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
#include <stdbool.h>

// Dunno why this is done, nor why the macro definition isn't included in files that use it
// #define TSINLINE inline
// #include "iocore/cache/P_CacheDir.h"

PyDoc_STRVAR(_scanlib_doc,
"This module contains Apache TrafficServer data structure bindings to Python objects");

///////////////////////
///                 ///
///    DIR ENTRY    ///
///                 ///
///////////////////////

typedef struct {
	PyObject_HEAD
	off_t length;
	off_t _raw_offset;
	off_t offset;
	bool token;
	bool pinned;
	bool head;
	bool phase;
	uint16_t tag;
	uint16_t next;
} DirEntry;

/// Lifecycle hooks
static int DirEntry_init(DirEntry* self, PyObject* args, void* unused_kwargs) {
	Py_buffer bytes;
	if (!PyArg_ParseTuple(args, "y*:DirEntry", &bytes)) {
		return -1;
	}

	if (bytes.len != 10) {
		PyErr_SetString(PyExc_TypeError, "Must pass a 10-byte sequence to DirEntry()!");
		return -1;
	}

	uint16_t w[5];
	size_t wpos = 0;
	for (void* b = bytes.buf; (b-bytes.buf)/bytes.itemsize < bytes.len; b += sizeof(uint16_t)) {
		w[wpos] = *((uint16_t*)(b));
	}

	uint16_t big = (w[1]&0xC000) >> 14;
	uint16_t size = (w[1]&0x3F00) >> 10;
	self->length = ((off_t)(size) + 1) * ((off_t)(1) << ((off_t)(9) + ((off_t)(3) * (off_t)(big))));
	self->_raw_offset = ((off_t)(w[0])) + (((off_t)(w[1]&0x00FF)) << 16) + (((off_t)(w[4])) << 24);
	self->token = (w[2]&0x8000) == 0x8000;
	self->pinned = (w[2]&0x4000) == 0x4000;
	self->head = (w[2]&0x2000) == 0x2000;
	self->phase = (w[2]&0x1000) == 0x1000;
	self->tag = w[2]&0x0FFF;
	self->next = w[3];
	self->offset = (self->_raw_offset - 1) * 512;
	return 0;
}

/// Getters/Setters

static PyObject* DirEntry_getOffset(DirEntry* self, void* closure) {
	return PyLong_FromUnsignedLongLong((unsigned long long)(self->offset));
}

static PyObject* DirEntry_getToken(DirEntry* self, void* closure) {
	if (self->token) {
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

static PyObject* DirEntry_getPinned(DirEntry* self, void* closure) {
	if (self->pinned) {
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

static PyObject* DirEntry_getHead(DirEntry* self, void* closure) {
	if (self->head) {
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

static PyObject* DirEntry_getPhase(DirEntry* self, void* closure) {
	if (self->phase) {
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

static PyObject* DirEntry_getLength(DirEntry* self, void* closure) {
	return PyLong_FromUnsignedLongLong((unsigned long long)(self->length));
}

static PyObject* DirEntry_getRawOffset(DirEntry* self, void* closure) {
	return PyLong_FromUnsignedLongLong((unsigned long long)(self->_raw_offset));
}

static PyObject* DirEntry_getTag(DirEntry* self, void* closure) {
	return PyLong_FromUnsignedLongLong((unsigned long long)(self->tag));
}

static PyObject* DirEntry_getNext(DirEntry* self, void* closure) {
	return PyLong_FromUnsignedLongLong((unsigned long long)(self->next));
}

static PyGetSetDef DirEntry_getsetters[] = {
	{"offset", (getter)DirEntry_getOffset, NULL, "The raw offset value stored in the stripe directory. This is an offset in 'Cache Blocks'\n"
	                                             "from the stripe's content, so its value is not very meaningful, you should use the ``Offset``\n"
	                                             "property for most practical purposes. For directories not in use, this has the special ``0`` value."},
	{"token", (getter)DirEntry_getToken, NULL, "'Flag: Unknown' - The ATS docs. So, yeah."},
	{"pinned", (getter)DirEntry_getPinned, NULL, "A 'pinned' object is kept in the cache when, under normal circumstances,\n"
	                                             "it would otherwise be overwritten. This is done via the 'evacuation' process, which is\n"
	                                             "highly complex, but roughly boils down to moving things away from an impending write cursor."},
	{"head", (getter)DirEntry_getHead, NULL, "When ``True``, this ``DirEntry`` points to a ``Doc`` that has header"
	                                         "information. Specifically, this means this ``DirEntry`` points to the first fragment\n"
	                                         "for a certain object, and the ``Doc`` there has ``hlen > 0``. This isn't *necessarily*\n"
	                                         "the same thing as a 'first Doc', as it could be either that or an 'earliest Doc'."},
	{"phase", (getter)DirEntry_getPhase, NULL, "I personally have no idea what the meaning of this flag is. The ATS docs\n"
	                                           "have this to say: 'Phase of the ``Doc`` (for dir valid check)'. So there you go."},
	{"length", (getter)DirEntry_getLength, NULL, "The approximate length (in bytes) of the `Doc` referred to by a specific\n"
	                                             "``DirEntry``. This is used in ATS to quickly read the object without needing to\n"
	                                             "immediately parse it; as such, it is guaranteed to be greater-than or equal to the\n"
	                                             "actual length of the ``Doc``."},
	{"next", (getter)DirEntry_getNext, NULL, "The segment-relative index of the next ``Dir`` for this object. If it's ``0``,\n"
	                                         "then this is the last ``Dir``."},
	{"_offset", (getter)DirEntry_getRawOffset, NULL, "The raw offset value stored in the stripe directory. This is an offset in\n"
	                                                 "'Cache Blocks' from the stripe's content, so its value is not very\n"
	                                                 "meaningful, you should use the ``offset`` property for most practical\n"
	                                                 "purposes. For directories not in use, this has the special ``0`` value."},
	{"tag", (getter)DirEntry_getTag, NULL, "The numeric representation of a 'partial key used for fast collision checks'. Whatever that means."},
	{NULL}
};

/// Methods
// Implements __len__
static Py_ssize_t DirEntry_length(DirEntry* self) {
	return (ssize_t)(self->length);
}

static PyObject* DirEntry_repr(DirEntry* self) {
	return PyUnicode_FromFormat("DirEntry(length=%u, offset=0x%x, next=%d, phase=%s, head=%s, pinned=%s, token=%s, tag=0x%x)",
		                      (unsigned int)(self->length), self->offset, self->next, self->phase?"True":"False", self->head?"True":"False", self->pinned?"True":"False", self->token?"True":"False", self->tag);
}

static PyObject* DirEntry_str(DirEntry* self) {
	return PyUnicode_FromFormat("%lluB -> 0x%x", (unsigned long long)(self->length), self->offset);
}

static int DirEntry_bool(DirEntry* self) {
	return self->_raw_offset > 0 ? 1 : 0;
}

static PySequenceMethods DirEntry_as_sequence = {
	(lenfunc) DirEntry_length,
	NULL,
	NULL,
	NULL,
	NULL,
	NULL,
	NULL,
};

static PyNumberMethods DirEntry_as_number = {
	NULL,              /*nb_add*/
	NULL,              /*nb_subtract*/
	NULL,              /*nb_multiply*/
	NULL,              /*nb_remainder*/
	NULL,           /*nb_divmod*/
	NULL,              /*nb_power*/
	NULL,              /*nb_negative*/
	NULL,              /*nb_positive*/
	NULL,              /*nb_absolute*/
	(inquiry) DirEntry_bool,    /*nb_bool*/
	NULL,           /*nb_invert*/
	NULL,           /*nb_lshift*/
	NULL,           /*nb_rshift*/
	NULL,              /*nb_and*/
	NULL,              /*nb_xor*/
	NULL,               /*nb_or*/
	NULL,              /*nb_int*/
	NULL,                      /*nb_reserved*/
	NULL,            /*nb_float*/
	NULL,             /*nb_inplace_add*/
	NULL,             /*nb_inplace_subtract*/
	NULL,             /*nb_inplace_multiply*/
	NULL,             /*nb_inplace_remainder*/
	NULL,             /*nb_inplace_power*/
	NULL,          /*nb_inplace_lshift*/
	NULL,          /*nb_inplace_rshift*/
	NULL,             /*nb_inplace_and*/
	NULL,             /*nb_inplace_xor*/
	NULL,              /*nb_inplace_or*/
	NULL,        /*nb_floor_divide*/
	NULL,         /*nb_true_divide*/
	NULL,       /*nb_inplace_floor_divide*/
	NULL,        /*nb_inplace_true_divide*/
	NULL,            /*nb_index*/
	NULL,           /*nb_matrix_multiply*/
	NULL,          /*nb_inplace_matrix_multiply*/
};


/// Object Definition

static PyTypeObject DirEntryType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name="DirEntry",
	.tp_doc="Represents a single directory entry.\n\n"
"A ``DirEntry`` in SCAN is comparable to a ``Dir`` in the ATS cache code. In fact, it carries all\n"
"of the same information.\n"
"Both a ``Dir`` and (equivalently) a ``DirEntry`` represent all of the information required to find\n"
"and begin reading in the first piece (fragment) of a ``Doc``.",
	.tp_basicsize = sizeof(DirEntry),
	.tp_itemsize = 0,
	.tp_flags = Py_TPFLAGS_DEFAULT,
	.tp_new = PyType_GenericNew,
	.tp_init = (initproc) DirEntry_init,
	.tp_getset = DirEntry_getsetters,
	.tp_as_sequence = &DirEntry_as_sequence,
	.tp_as_number = &DirEntry_as_number,
	.tp_repr = DirEntry_repr,
	.tp_str = DirEntry_str,
	//.tp_methods = DirEntry_methods,
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
