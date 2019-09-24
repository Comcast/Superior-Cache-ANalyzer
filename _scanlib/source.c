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

#define CACHE_BLOCK_SHIFT 9
#define CACHE_BLOCK_SIZE (1 << CACHE_BLOCK_SHIFT)
#define SIZEOF_DIR 10
#define DOC_MAGIC 0x5F129B13
#define CORRUPT_MAGIC 0xDEADBABE

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
	unsigned char token:1;
	unsigned char pinned:1;
	unsigned char head:1;
	unsigned char phase:1;
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
	memcpy(w, bytes.buf, bytes.len);

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
	self->offset = (self->_raw_offset*CACHE_BLOCK_SIZE) - CACHE_BLOCK_SIZE;
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


///////////////////////
///                 ///
///       DOC       ///
///                 ///
///////////////////////
typedef struct {
	uint32_t magic;
	uint32_t length;
	uint64_t totalLength;
	uint64_t keys[4];
	uint32_t hlen;
	uint32_t docType:8;
	uint32_t versionMajor:8;
	uint32_t versionMinor:8;
	uint32_t unused:8;
	uint32_t syncSerial;
	uint32_t writeSerial;
	uint32_t pinned;
	uint32_t checksum;
} RawDoc;

typedef struct {
	PyObject_HEAD
	RawDoc;
	PyListObject* alternates;
	Py_buffer data;
} Doc;

/// Lifecycle hooks
static PyObject* Doc_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
	Doc* self = (Doc*)type->tp_alloc(type, 0);
	if (self == NULL) {
		return NULL;
	}

	self->alternates = (PyListObject*)PyList_New(0);
	if (self->alternates == NULL) {
		Py_DECREF(self);
		return NULL;
	}

	return (PyObject*)self;
}

static int Doc_init(Doc* self, PyObject* args, PyObject* kwargs) {
	Py_buffer bytes;
	if (!PyArg_ParseTuple(args, "y*:Doc", &bytes)) {
		return -1;
	}

	if (bytes.len != sizeof(RawDoc)) {
		PyErr_Format(PyExc_TypeError, "Incorrect number of bytes! (got %d, need %d)", bytes.len, sizeof(RawDoc));
		return -1;
	}

	memcpy(&(self->RawDoc), bytes.buf, bytes.len);
	if (self->magic != DOC_MAGIC) {
		if (self->magic == CORRUPT_MAGIC) {
			PyErr_FromString(PyExc_ValueError, "Doc is corrupt");
		} else {
			PyErr_Format(PyExc_ValueError, "Doc magic number 0x%x does not match expected DOC_MAGIC", self->magic);
		}
		return -1;
	}

	return 0;
}

static int Doc_dealloc(Doc* self) {
	Py_XDECREF(self->alternates);
	PyBuffer_Release(&(self->data));
	Py_TYPE(self)->tp_free((PyObject*)self);
	return 0;
}

/// Getters/Setters
static PyObject* Doc_getAlternates(Doc* self, void* closure) {
	Py_INCREF(self->alternates);
	return self->alternates;
}

/// Object Definition
static PyTypeObject DocType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name="Doc",
	.tp_doc="A single entry within a directory.\n\n"
	        "This structure is comparable to a ``Doc`` structure in the ATS source code. Each part,\n"
	        "or 'fragment' of an object is preceded on the cache by header data in this format.",
	.tp_basicsize = sizeof(Doc),
	.tp_itemsize = 0,
	.tp_flags = Py_TPFLAGS_DEFAULT,
	.tp_new = Doc_new,
	.tp_init = (initproc) Doc_init,
	.tp_dealloc = (destructor) Doc_dealloc,
	//.tp_getset = DirEntry_getsetters,
	//.tp_as_sequence = &DirEntry_as_sequence,
	//.tp_as_number = &DirEntry_as_number,
	//.tp_repr = DirEntry_repr,
	//.tp_str = DirEntry_str,
	//.tp_methods = DirEntry_methods,
};


////////////////////////
///                  ///
///      MODULE      ///
///                  ///
////////////////////////


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

	PyModule_AddIntConstant(m, "CACHE_BLOCK_SIZE", CACHE_BLOCK_SIZE);
	PyModule_AddIntConstant(m, "CACHE_BLOCK_SHIFT", CACHE_BLOCK_SHIFT);
	PyModule_AddIntConstant(m, "SIZEOF_DIR", SIZEOF_DIR);
	PyModule_AddIntConstant(m, "DOC_MAGIC", DOC_MAGIC);
	PyModule_AddIntConstant(m, "CORRUPT_MAGIC", CORRUPT_MAGIC);

	return m;
}
