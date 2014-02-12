/* htmltext type and the htmlescape function  */

#include "Python.h"
#include "structmember.h"

typedef struct {
	PyObject_HEAD
	PyStringObject *s;
} htmltextObject;

static PyTypeObject htmltext_Type;

#define htmltextObject_Check(v)	((v)->ob_type == &htmltext_Type)

#define htmltext_STR(v) ((PyObject *)(((htmltextObject *)v)->s))

typedef struct {
	PyObject_HEAD
	PyObject *obj;
} QuoteWrapperObject;

static PyTypeObject QuoteWrapper_Type;

#define QuoteWrapper_Check(v)	((v)->ob_type == &QuoteWrapper_Type)


typedef struct {
	PyObject_HEAD
	PyObject *obj;
} DictWrapperObject;

static PyTypeObject DictWrapper_Type;

#define DictWrapper_Check(v)	((v)->ob_type == &DictWrapper_Type)


typedef struct {
	PyObject_HEAD
	int html;
	char *buf;
	size_t size;
	size_t pos;
} TemplateIO_Object;

static PyTypeObject TemplateIO_Type;

#define TemplateIO_Check(v)	((v)->ob_type == &TemplateIO_Type)


static PyObject *
type_error(const char *msg)
{
	PyErr_SetString(PyExc_TypeError, msg);
	return NULL;
}

static PyObject *
escape_string(PyObject *s)
{
	PyObject *new_s;
	char *ss, *new_ss;
	size_t i, j, extra_space, size, new_size;
	if (!PyString_Check(s))
		return type_error("str object required");
	ss = PyString_AS_STRING(s);
	size = PyString_GET_SIZE(s);
	extra_space = 0;
	for (i=0; i < size; i++) {
		switch (ss[i]) {
		case '&':
			extra_space += 4;
			break;
		case '<':
		case '>':
			extra_space += 3;
			break;
		case '"':
			extra_space += 5;
			break;
		}
	}
	if (extra_space == 0) {
		Py_INCREF(s);
		return (PyObject *)s;
	}
	new_size = size + extra_space;
	new_s = PyString_FromStringAndSize(NULL, new_size);
	if (new_s == NULL)
		return NULL;
	new_ss = PyString_AsString(new_s);
	for (i=0, j=0; i < size; i++) {
		switch (ss[i]) {
		case '&':
			new_ss[j++] = '&';
			new_ss[j++] = 'a';
			new_ss[j++] = 'm';
			new_ss[j++] = 'p';
			new_ss[j++] = ';';
			break;
		case '<':
			new_ss[j++] = '&';
			new_ss[j++] = 'l';
			new_ss[j++] = 't';
			new_ss[j++] = ';';
			break;
		case '>':
			new_ss[j++] = '&';
			new_ss[j++] = 'g';
			new_ss[j++] = 't';
			new_ss[j++] = ';';
			break;
		case '"':
			new_ss[j++] = '&';
			new_ss[j++] = 'q';
			new_ss[j++] = 'u';
			new_ss[j++] = 'o';
			new_ss[j++] = 't';
			new_ss[j++] = ';';
			break;
		default:
			new_ss[j++] = ss[i];
			break;
		}
	}
	assert (j == new_size);
	return (PyObject *)new_s;
}

static PyObject *
quote_wrapper_new(PyObject *o)
{
	QuoteWrapperObject *self;
	if (htmltextObject_Check(o) ||
	    PyInt_Check(o) ||
	    PyFloat_Check(o) ||
	    PyLong_Check(o)) {
		/* no need for wrapper */
		Py_INCREF(o);
		return o;
	}
	self = PyObject_New(QuoteWrapperObject, &QuoteWrapper_Type);
	if (self == NULL)
		return NULL;
	Py_INCREF(o);
	self->obj = o;
	return (PyObject *)self;
}

static void
quote_wrapper_dealloc(QuoteWrapperObject *self)
{
	Py_DECREF(self->obj);
	PyObject_Del(self);
}

static PyObject *
quote_wrapper_repr(QuoteWrapperObject *self)
{
	PyObject *qs;
	PyObject *s = PyObject_Repr(self->obj);
	if (s == NULL)
		return NULL;
	qs = escape_string(s);
	Py_DECREF(s);
	return qs;
}

static PyObject *
quote_wrapper_str(QuoteWrapperObject *self)
{
	PyObject *qs;
	PyObject *s = PyObject_Str(self->obj);
	if (s == NULL)
		return NULL;
	qs = escape_string(s);
	Py_DECREF(s);
	return qs;
}

static PyObject *
dict_wrapper_new(PyObject *o)
{
	DictWrapperObject *self;
	self = PyObject_New(DictWrapperObject, &DictWrapper_Type);
	if (self == NULL)
		return NULL;
	Py_INCREF(o);
	self->obj = o;
	return (PyObject *)self;
}

static void
dict_wrapper_dealloc(DictWrapperObject *self)
{
	Py_DECREF(self->obj);
	PyObject_Del(self);
}

static PyObject *
dict_wrapper_subscript(DictWrapperObject *self, PyObject *key)
{
	PyObject *v, *w;;
	v = PyObject_GetItem(self->obj, key);
	if (v == NULL) {
		return NULL;
	}
	w = quote_wrapper_new(v); 
	Py_DECREF(v);
	return w;
}

static PyObject *
htmltext_from_string(PyObject *s)
{
	/* note, this takes a reference */
	PyObject *self;
	if (s == NULL)
		return NULL;
	assert (PyString_Check(s));
	self = PyType_GenericAlloc(&htmltext_Type, 0);
	if (self == NULL) {
		return NULL;
	}
	((htmltextObject *)self)->s = (PyStringObject *)s;
	return self;
}

static PyObject *
htmltext_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	htmltextObject *self;
	PyObject *s;
	static char *kwlist[] = {"s", 0};
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O:htmltext", kwlist,
					 &s))
		return NULL;
	s = PyObject_Str(s);
	if (s == NULL)
		return NULL;
	self = (htmltextObject *)type->tp_alloc(type, 0);
	if (self == NULL) {
		Py_DECREF(s);
		return NULL;
	}
	self->s = (PyStringObject *)s;
	return (PyObject *)self;
}

/* htmltext methods */

static void
htmltext_dealloc(htmltextObject *self)
{
	Py_DECREF(self->s);
	self->ob_type->tp_free((PyObject *)self);
}

static long
htmltext_hash(PyObject *self)
{
	return PyObject_Hash(htmltext_STR(self));
}

static PyObject *
htmltext_str(htmltextObject *self)
{
	Py_INCREF(self->s);
	return (PyObject *)self->s;
}

static PyObject *
htmltext_repr(htmltextObject *self)
{
	PyObject *sr, *rv;
	sr = PyObject_Repr((PyObject *)self->s);
	if (sr == NULL)
		return NULL;
	rv = PyString_FromFormat("<htmltext %s>", PyString_AsString(sr));
	Py_DECREF(sr);
	return rv;
}

static PyObject *
htmltext_richcompare(PyObject *a, PyObject *b, int op)
{
	PyObject *sa, *sb;
	if (PyString_Check(a)) {
		sa = a;
	} else if (htmltextObject_Check(a)) {
		sa = htmltext_STR(a);
	} else {
		goto fail;
	}
	if (PyString_Check(b)) {
		sb = b;
	} else if (htmltextObject_Check(b)) {
		sb = htmltext_STR(b);
	} else {
		goto fail;
	}
	return sa->ob_type->tp_richcompare(sa, sb, op);

fail:
	Py_INCREF(Py_NotImplemented);
	return Py_NotImplemented;
}

static long
htmltext_length(htmltextObject *self)
{
	return ((PyStringObject *)self->s)->ob_size;
}


static PyObject *
wrap_arg(PyObject *arg)
{
	PyObject *warg;
	if (htmltextObject_Check(arg)) {
		/* don't bother with wrapper object */
		warg = arg;
		Py_INCREF(arg);
	} else {
		warg = quote_wrapper_new(arg); 
	}
	return warg;
}

static PyObject *
htmltext_format(htmltextObject *self, PyObject *args)
{
	/* wrap the format arguments with QuoteWrapperObject */
	int do_dict = 0;
	PyObject *rv, *wargs;
	if (args->ob_type->tp_as_mapping && !PyTuple_Check(args) &&
	    !PyString_Check(args)) {
		char *fmt = PyString_AS_STRING(htmltext_STR(self));
		size_t i, n = PyString_GET_SIZE(htmltext_STR(self));
		char last = 0;
		/* second check necessary since '%s' % {} => '{}' */
		for (i=0; i < n; i++) {
			if (last == '%' && fmt[i] == '(') {
				do_dict = 1;
				break;
			}
			last = fmt[i];
		}
	}
	if (do_dict) {
		wargs = dict_wrapper_new(args);
		if (wargs == NULL)
			return NULL;
	}
	else if (PyTuple_Check(args)) {
		long i, n = PyTuple_GET_SIZE(args);
		wargs = PyTuple_New(n);
		for (i=0; i < n; i++) {
			PyObject *wvalue = wrap_arg(PyTuple_GET_ITEM(args, i));
			if (wvalue == NULL) {
				Py_DECREF(wargs);
				return NULL;
			}
			PyTuple_SetItem(wargs, i, wvalue);
		}
	}
	else {
		wargs = wrap_arg(args);
		if (wargs == NULL) {
			return NULL;
		}
	}
	rv = PyString_Format((PyObject *)self->s, wargs);
	Py_DECREF(wargs);
	return htmltext_from_string(rv);
}

static PyObject *
htmltext_add(PyObject *v, PyObject *w)
{
	PyObject *qv, *qw;
	if (htmltextObject_Check(v) && htmltextObject_Check(w)) {
		qv = htmltext_STR(v);
		qw = htmltext_STR(w);
		Py_INCREF(qv);
		Py_INCREF(qw);
	}
	else if (PyString_Check(w)) {
		assert (htmltextObject_Check(v));
		qv = htmltext_STR(v);
		qw = escape_string(w);
		if (qw == NULL)
			return NULL;
		Py_INCREF(qv);
	}
	else if (PyString_Check(v)) {
		assert (htmltextObject_Check(w));
		qv = escape_string(v);
		if (qv == NULL)
			return NULL;
		qw = htmltext_STR(w);
		Py_INCREF(qw);
	}
	else {
		Py_INCREF(Py_NotImplemented);
		return Py_NotImplemented;
	}
	PyString_ConcatAndDel(&qv, qw);
	return htmltext_from_string(qv);
}

static PyObject *
htmltext_repeat(htmltextObject *self, int n)
{
	PyObject *s = PySequence_Repeat(htmltext_STR(self), n);
	if (s == NULL)
		return NULL;
	return htmltext_from_string(s);
}

static PyObject *
htmltext_join(PyObject *self, PyObject *args)
{
	long i;
	PyObject *qargs, *rv;
	if (!PySequence_Check(args)) {
		return type_error("argument must be a sequence");
	}
	qargs = PyList_New(PySequence_Size(args));
	if (qargs == NULL)
		return NULL;
	for (i=0; i < PySequence_Size(args); i++) {
		PyObject *value, *qvalue;
		value = PySequence_GetItem(args, i);
		if (value == NULL) {
			goto error;
		}
		if (htmltextObject_Check(value)) {
			qvalue = htmltext_STR(value);
			Py_INCREF(qvalue);
			Py_DECREF(value);
		}
		else if (PyString_Check(value)) {
			qvalue = escape_string(value);
			Py_DECREF(value);
		}
		else {
			Py_DECREF(value);
			type_error("join requires a list of strings");
			goto error;
		}
		if (PyList_SetItem(qargs, i, qvalue) < 0) {
			goto error;
		}
	}
	rv = _PyString_Join(htmltext_STR(self), qargs);
	Py_DECREF(qargs);
	return htmltext_from_string(rv);

error:
	Py_DECREF(qargs);
	return NULL;
}

static PyObject *
quote_arg(PyObject *s)
{
	PyObject *ss;
	if (PyString_Check(s)) {
		ss = escape_string(s);
		if (ss == NULL)
			return NULL;
	}
	else if (htmltextObject_Check(s)) {
		ss = htmltext_STR(s);
		Py_INCREF(ss);
	}
	else {
		return type_error("string object required");
	}
	return ss;
}

static PyObject *
htmltext_call_method1(PyObject *self, PyObject *s, char *method)
{
	PyObject *ss, *rv;
	ss = quote_arg(s);
	if (ss == NULL)
		return NULL;
	rv = PyObject_CallMethod(htmltext_STR(self), method, "O", ss);
	Py_DECREF(ss);
	return rv;
}

static PyObject *
htmltext_startswith(PyObject *self, PyObject *s)
{
	return htmltext_call_method1(self, s, "startswith");
}

static PyObject *
htmltext_endswith(PyObject *self, PyObject *s)
{
	return htmltext_call_method1(self, s, "endswith");
}

static PyObject *
htmltext_replace(PyObject *self, PyObject *args)
{
	PyObject *old, *new, *q_old, *q_new, *rv;
	int maxsplit = -1;
	if (!PyArg_ParseTuple(args,"OO|i:replace", &old, &new, &maxsplit))
		return NULL;
	q_old = quote_arg(old);
	if (q_old == NULL)
		return NULL;
	q_new = quote_arg(new);
	if (q_new == NULL) {
		Py_DECREF(q_old);
		return NULL;
	}
	rv = PyObject_CallMethod(htmltext_STR(self), "replace", "OOi",
				 q_old, q_new, maxsplit);
	Py_DECREF(q_old);
	Py_DECREF(q_new);
	return htmltext_from_string(rv);
}


static PyObject *
htmltext_lower(PyObject *self)
{
	return htmltext_from_string(PyObject_CallMethod(htmltext_STR(self),
							"lower", ""));
}

static PyObject *
htmltext_upper(PyObject *self)
{
	return htmltext_from_string(PyObject_CallMethod(htmltext_STR(self),
							"upper", ""));
}

static PyObject *
htmltext_capitalize(PyObject *self)
{
	return htmltext_from_string(PyObject_CallMethod(htmltext_STR(self),
							"capitalize", ""));
}

static PyObject *
template_io_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	TemplateIO_Object *self;
	int html = 0;
	static char *kwlist[] = {"html", 0};
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|i:TemplateIO",
					 kwlist, &html))
		return NULL;
	self = (TemplateIO_Object *)type->tp_alloc(type, 0);
	if (self == NULL) {
		return NULL;
	}
	self->html = html != 0;
	self->buf = NULL;
	self->size = 0;
	self->pos = 0;
	return (PyObject *)self;
}

static void
template_io_dealloc(TemplateIO_Object *self)
{
	if (self->size > 0)
		PyMem_Free(self->buf);
	self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
template_io_str(TemplateIO_Object *self)
{
	return PyString_FromStringAndSize(self->buf, self->pos);
}

static PyObject *
template_io_getvalue(TemplateIO_Object *self)
{
	if (self->html) {
		return htmltext_from_string(template_io_str(self));
	}
	else {
		return template_io_str(self);
	}
}

static PyObject *
template_io_repr(TemplateIO_Object *self)
{
	PyObject *s, *sr, *rv;
	s = template_io_str(self);
	if (s == NULL)
		return NULL;
	sr = PyObject_Repr(s);
	Py_DECREF(s);
	if (sr == NULL)
		return NULL;
	rv = PyString_FromFormat("<TemplateIO %s>", PyString_AsString(sr));
	Py_DECREF(sr);
	return rv;
}


static PyObject *
template_io_do_concat(TemplateIO_Object *self, char *s, size_t size)
{
	/* note this adds a reference to self */
	if (self->pos + size > self->size) {
		size_t new_size;
		char *new_buf;
		if (self->size > size)
			new_size = self->size * 2;
		else
			new_size = size * 2;
		new_buf = PyMem_Realloc(self->buf, new_size);
		if (new_buf == NULL)
			return NULL;
		self->buf = new_buf;
		self->size = new_size;
	}
	assert (self->pos + size <= self->size);
	memcpy(self->buf + self->pos, s, size);
	self->pos += size;
	Py_INCREF(self);
	return (PyObject *)self;
}
	

static PyObject *
template_io_iadd(TemplateIO_Object *self, PyObject *other)
{
	PyObject *rv;
	PyObject *s = NULL;
	if (!TemplateIO_Check(self))
		return type_error("TemplateIO object required");
	if (other == Py_None) {
		Py_INCREF(self);
		return (PyObject *)self;
	}
	else if (TemplateIO_Check(other)) {
		TemplateIO_Object *o = (TemplateIO_Object *)other;
		if (self->html && !o->html) {
			PyObject *ss = PyString_FromStringAndSize(o->buf,
								  o->pos);
			if (ss == NULL)
				return NULL;
			s = escape_string(ss);
			Py_DECREF(ss);
			goto concat_str;
		}
		rv = template_io_do_concat(self, o->buf, o->pos);
	}
	else if (htmltextObject_Check(other)) {
		PyStringObject *s = ((htmltextObject *)other)->s;
		rv = template_io_do_concat(self,
					   PyString_AS_STRING(s),
					   PyString_GET_SIZE(s));
	}
	else {
		if (self->html) {
			PyObject *ss = PyObject_Str(other);
			if (ss == NULL)
				return NULL;
			s = escape_string(ss);
			Py_DECREF(ss);
		} else {
			s = PyObject_Str(other);
		}
concat_str:
		if (s == NULL)
			return NULL;
		rv = template_io_do_concat(self, PyString_AS_STRING(s),
					   PyString_GET_SIZE(s));
		Py_XDECREF(s);
	}
	return rv;
}

static PyMethodDef htmltext_methods[] = {
	{"join", (PyCFunction)htmltext_join, METH_O, ""},
	{"startswith", (PyCFunction)htmltext_startswith, METH_O, ""},
	{"endswith", (PyCFunction)htmltext_endswith, METH_O, ""},
	{"replace", (PyCFunction)htmltext_replace, METH_VARARGS, ""},
	{"lower", (PyCFunction)htmltext_lower, METH_NOARGS, ""},
	{"upper", (PyCFunction)htmltext_upper, METH_NOARGS, ""},
	{"capitalize", (PyCFunction)htmltext_capitalize, METH_NOARGS, ""},
	{NULL, NULL}
};

static PyMemberDef htmltext_members[] = {
	{"s", T_OBJECT, offsetof(htmltextObject, s), READONLY, "the string"},
	{NULL},
};

static PySequenceMethods htmltext_as_sequence = {
	(inquiry)htmltext_length,	/*sq_length*/
	0,				/*sq_concat*/
	(intargfunc)htmltext_repeat,	/*sq_repeat*/
	0,				/*sq_item*/
	0,				/*sq_slice*/
	0,				/*sq_ass_item*/
	0,				/*sq_ass_slice*/
	0,				/*sq_contains*/
};

static PyNumberMethods htmltext_as_number = {
	(binaryfunc)htmltext_add, /*nb_add*/
	0, /*nb_subtract*/
	0, /*nb_multiply*/
	0, /*nb_divide*/
	(binaryfunc)htmltext_format, /*nb_remainder*/
	0, /*nb_divmod*/
	0, /*nb_power*/
	0, /*nb_negative*/
	0, /*nb_positive*/
	0, /*nb_absolute*/
	0, /*nb_nonzero*/
	0, /*nb_invert*/
	0, /*nb_lshift*/
	0, /*nb_rshift*/
	0, /*nb_and*/
	0, /*nb_xor*/
	0, /*nb_or*/
	0, /*nb_coerce*/
	0, /*nb_int*/
	0, /*nb_long*/
	0, /*nb_float*/
};

static PyTypeObject htmltext_Type = {
	PyObject_HEAD_INIT(NULL)
	0,			/*ob_size*/
	"htmltext",		/*tp_name*/
	sizeof(htmltextObject),	/*tp_basicsize*/
	0,			/*tp_itemsize*/
	/* methods */
	(destructor)htmltext_dealloc, /*tp_dealloc*/
	0,			/*tp_print*/
	0,			/*tp_getattr*/
	0,			/*tp_setattr*/
	0,			/*tp_compare*/
	(unaryfunc)htmltext_repr,/*tp_repr*/
	&htmltext_as_number,	/*tp_as_number*/
	&htmltext_as_sequence,	/*tp_as_sequence*/
	0,			/*tp_as_mapping*/
	htmltext_hash,		/*tp_hash*/
	0,			/*tp_call*/
	(unaryfunc)htmltext_str,/*tp_str*/
	PyObject_GenericGetAttr,/*tp_getattro*/
	0,			/*tp_setattro*/
	0,			/*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE \
		| Py_TPFLAGS_CHECKTYPES, /*tp_flags*/
	0,			/*tp_doc*/
	0,			/*tp_traverse*/
	0,			/*tp_clear*/
	htmltext_richcompare,	/*tp_richcompare*/
	0,			/*tp_weaklistoffset*/
	0,			/*tp_iter*/
	0,			/*tp_iternext*/
	htmltext_methods,	/*tp_methods*/
	htmltext_members,	/*tp_members*/
	0,			/*tp_getset*/
	0,			/*tp_base*/
	0,			/*tp_dict*/
	0,			/*tp_descr_get*/
	0,			/*tp_descr_set*/
	0,			/*tp_dictoffset*/
	0,			/*tp_init*/
	PyType_GenericAlloc,	/*tp_alloc*/
	htmltext_new,		/*tp_new*/
	_PyObject_Del,		/*tp_free*/
	0,			/*tp_is_gc*/
};

static PyNumberMethods quote_wrapper_as_number = {
	0, /*nb_add*/
	0, /*nb_subtract*/
	0, /*nb_multiply*/
	0, /*nb_divide*/
	0, /*nb_remainder*/
	0, /*nb_divmod*/
	0, /*nb_power*/
	0, /*nb_negative*/
	0, /*nb_positive*/
	0, /*nb_absolute*/
	0, /*nb_nonzero*/
	0, /*nb_invert*/
	0, /*nb_lshift*/
	0, /*nb_rshift*/
	0, /*nb_and*/
	0, /*nb_xor*/
	0, /*nb_or*/
	0, /*nb_coerce*/
	0, /*nb_int*/
	0, /*nb_long*/
	0, /*nb_float*/
};

static PyTypeObject QuoteWrapper_Type = {
	PyObject_HEAD_INIT(NULL)
	0,			/*ob_size*/
	"QuoteWrapper",		/*tp_name*/
	sizeof(QuoteWrapperObject),	/*tp_basicsize*/
	0,			/*tp_itemsize*/
	/* methods */
	(destructor)quote_wrapper_dealloc, /*tp_dealloc*/
	0,			/*tp_print*/
	0,			/*tp_getattr*/
	0,			/*tp_setattr*/
	0,			/*tp_compare*/
	(unaryfunc)quote_wrapper_repr,/*tp_repr*/
	&quote_wrapper_as_number,/*tp_as_number*/
	0,			/*tp_as_sequence*/
	0,			/*tp_as_mapping*/
	0,			/*tp_hash*/
	0,			/*tp_call*/
	(unaryfunc)quote_wrapper_str,  /*tp_str*/
};

static PyMappingMethods dict_wrapper_as_mapping = {
        0, /*mp_length*/
        (binaryfunc)dict_wrapper_subscript, /*mp_subscript*/
        0, /*mp_ass_subscript*/
};

static PyTypeObject DictWrapper_Type = {
	PyObject_HEAD_INIT(NULL)
	0,			/*ob_size*/
	"DictWrapper",		/*tp_name*/
	sizeof(DictWrapperObject),	/*tp_basicsize*/
	0,			/*tp_itemsize*/
	/* methods */
	(destructor)dict_wrapper_dealloc, /*tp_dealloc*/
	0,			/*tp_print*/
	0,			/*tp_getattr*/
	0,			/*tp_setattr*/
	0,			/*tp_compare*/
	0,			/*tp_repr*/
	0,			/*tp_as_number*/
	0,			/*tp_as_sequence*/
	&dict_wrapper_as_mapping,/*tp_as_mapping*/
};

static PyNumberMethods template_io_as_number = {
	0, /*nb_add*/
	0, /*nb_subtract*/
	0, /*nb_multiply*/
	0, /*nb_divide*/
	0, /*nb_remainder*/
	0, /*nb_divmod*/
	0, /*nb_power*/
	0, /*nb_negative*/
	0, /*nb_positive*/
	0, /*nb_absolute*/
	0, /*nb_nonzero*/
	0, /*nb_invert*/
	0, /*nb_lshift*/
	0, /*nb_rshift*/
	0, /*nb_and*/
	0, /*nb_xor*/
	0, /*nb_or*/
	0, /*nb_coerce*/
	0, /*nb_int*/
	0, /*nb_long*/
	0, /*nb_float*/
	0, /*nb_oct*/
	0, /*nb_hex*/
	(binaryfunc)template_io_iadd, /*nb_inplace_add*/
};

static PyMethodDef template_io_methods[] = {
	{"getvalue", (PyCFunction)template_io_getvalue, METH_NOARGS, ""},
	{NULL, NULL}
};

static PyTypeObject TemplateIO_Type = {
	PyObject_HEAD_INIT(NULL)
	0,			/*ob_size*/
	"TemplateIO",		/*tp_name*/
	sizeof(TemplateIO_Object),/*tp_basicsize*/
	0,			/*tp_itemsize*/
	/* methods */
	(destructor)template_io_dealloc, /*tp_dealloc*/
	0,			/*tp_print*/
	0,			/*tp_getattr*/
	0,			/*tp_setattr*/
	0,			/*tp_compare*/
	(unaryfunc)template_io_repr,/*tp_repr*/
	&template_io_as_number,	/*tp_as_number*/
	0,			/*tp_as_sequence*/
	0,			/*tp_as_mapping*/
	0,			/*tp_hash*/
	0,			/*tp_call*/
	(unaryfunc)template_io_str,/*tp_str*/
	PyObject_GenericGetAttr,/*tp_getattro*/
	0,			/*tp_setattro*/
	0,			/*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
	0,			/*tp_doc*/
	0,			/*tp_traverse*/
	0,			/*tp_clear*/
	0,			/*tp_richcompare*/
	0,			/*tp_weaklistoffset*/
	0,			/*tp_iter*/
	0,			/*tp_iternext*/
	template_io_methods,	/*tp_methods*/
	0,			/*tp_members*/
	0,			/*tp_getset*/
	0,			/*tp_base*/
	0,			/*tp_dict*/
	0,			/*tp_descr_get*/
	0,			/*tp_descr_set*/
	0,			/*tp_dictoffset*/
	0,			/*tp_init*/
	PyType_GenericAlloc,	/*tp_alloc*/
	template_io_new,	/*tp_new*/
	_PyObject_Del,		/*tp_free*/
	0,			/*tp_is_gc*/
};

/* --------------------------------------------------------------------- */

static PyObject *
html_escape(PyObject *self, PyObject *o)
{
	if (htmltextObject_Check(o)) {
		Py_INCREF(o);
		return o;
	}
	else {
		PyObject *rv;
		PyObject *s = PyObject_Str(o);
		if (s == NULL)
			return NULL;
		rv = escape_string(s);
		Py_DECREF(s);
		return htmltext_from_string(rv);
	}
}

static PyObject *
py_escape_string(PyObject *self, PyObject *o)
{
	PyObject *rv;
	if (!PyString_Check(o))
		return type_error("string required");
	rv = escape_string(o);
	return rv;
}

/* List of functions defined in the module */

static PyMethodDef htmltext_module_methods[] = {
	{"htmlescape",		(PyCFunction)html_escape, METH_O},
	{"_escape_string",	(PyCFunction)py_escape_string, METH_O},
	{NULL,			NULL}
};

static char module_doc[] = "htmltext string type";

void
init_c_htmltext(void)
{
	PyObject *m;

	/* Initialize the type of the new type object here; doing it here
	 * is required for portability to Windows without requiring C++. */
	htmltext_Type.ob_type = &PyType_Type;
	QuoteWrapper_Type.ob_type = &PyType_Type;
	TemplateIO_Type.ob_type = &PyType_Type;

	/* Create the module and add the functions */
	m = Py_InitModule4("_c_htmltext", htmltext_module_methods, module_doc,
			   NULL, PYTHON_API_VERSION);

	Py_INCREF((PyObject *)&htmltext_Type);
	Py_INCREF((PyObject *)&QuoteWrapper_Type);
	Py_INCREF((PyObject *)&TemplateIO_Type);
	PyModule_AddObject(m, "htmltext", (PyObject *)&htmltext_Type);
	PyModule_AddObject(m, "TemplateIO", (PyObject *)&TemplateIO_Type);
}
