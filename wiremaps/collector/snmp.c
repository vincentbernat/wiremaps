/* Simple interface to libnetsnmp for twisted. Inspired by synchronous module
 * from snimpy (https://trac.luffy.cx/snimpy/)
 *
 * (c) Copyright 2008 Vincent Bernat <bernat@luffy.cx>
 *
 * Permission to use, copy, modify, and distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

#include <Python.h>
#include <net-snmp/net-snmp-config.h>
#include <net-snmp/net-snmp-includes.h>

/* Exceptions */
struct ErrorException {
	int error;
	char *name;
	PyObject *exception;
};
static PyObject *SnmpException;
static PyObject *SnmpNoSuchObject;
static PyObject *SnmpNoSuchInstance;
static PyObject *SnmpEndOfMibView;
static struct ErrorException SnmpErrorToException[] = {
	{ SNMP_ERR_TOOBIG, "SNMPTooBig" },
	{ SNMP_ERR_NOSUCHNAME, "SNMPNoSuchName" },
	{ SNMP_ERR_BADVALUE, "SNMPBadValue" },
	{ SNMP_ERR_READONLY,  "SNMPReadonly" },
	{ SNMP_ERR_GENERR, "SNMPGenerr" },
	{ SNMP_ERR_NOACCESS, "SNMPNoAccess" },
	{ SNMP_ERR_WRONGTYPE, "SNMPWrongType" },
	{ SNMP_ERR_WRONGLENGTH, "SNMPWrongLength" },
	{ SNMP_ERR_WRONGENCODING, "SNMPWrongEncoding" },
	{ SNMP_ERR_WRONGVALUE, "SNMPWrongValue" },
	{ SNMP_ERR_NOCREATION, "SNMPNoCreation" },
	{ SNMP_ERR_INCONSISTENTVALUE, "SNMPInconsistentValue" },
	{ SNMP_ERR_RESOURCEUNAVAILABLE, "SNMPResourceUnavailable" },
	{ SNMP_ERR_COMMITFAILED, "SNMPCommitFailed" },
	{ SNMP_ERR_UNDOFAILED, "SNMPUndoFailed" },
	{ SNMP_ERR_AUTHORIZATIONERROR, "SNMPAuthorizationError" },
	{ SNMP_ERR_NOTWRITABLE, "SNMPNotWritable" },
	{ SNMP_ERR_INCONSISTENTNAME, "SNMPInconsistentName" },
	{ -1, NULL },
};

static PyObject *DeferModule;
static PyObject *FailureModule;
static PyObject *reactor;
static PyObject *SnmpFds;
static PyObject *timeoutId;
static PyObject *timeoutFunction;

/* Types */
typedef struct {
	PyObject_HEAD
	struct snmp_session *ss;
	PyObject *defers;
} SnmpObject;

typedef struct {
	PyObject_HEAD
	int fd;
} SnmpReaderObject;
static PyTypeObject SnmpReaderType;

static int
Snmp_updatereactor(void)
{
	int maxfd = 0, block = 0, fd, result, i;
	PyObject *keys, *key, *tmp;
	SnmpReaderObject *reader;
	fd_set fdset;
	struct timeval timeout;
	double to;

	FD_ZERO(&fdset);
	block = 1;		/* This means we don't have a timeout
				   planned. block will be reset to 0
				   if we need to setup a timeout. */
	snmp_select_info(&maxfd, &fdset, &timeout, &block);
	for (fd = 0; fd < maxfd; fd++) {
		if (FD_ISSET(fd, &fdset)) {
			result = PyDict_Contains(SnmpFds, PyInt_FromLong(fd));
			if (result == -1)
				return -1;
			if (!result) {
				/* Add this fd to the reactor */
				if ((reader = (SnmpReaderObject *)
					PyObject_CallObject((PyObject *)&SnmpReaderType,
					    NULL)) == NULL)
					return -1;
				reader->fd = fd;
				if ((key =
					PyInt_FromLong(fd)) == NULL) {
					Py_DECREF(reader);
					return -1;
				}
				if (PyDict_SetItem(SnmpFds, key, (PyObject*)reader) != 0) {
					Py_DECREF(reader);
					Py_DECREF(key);
					return -1;
				}
				Py_DECREF(key);
				if ((tmp = PyObject_CallMethod(reactor,
					    "addReader", "O", (PyObject*)reader)) ==
				    NULL) {
					Py_DECREF(reader);
					return -1;
				}
				Py_DECREF(tmp);
				Py_DECREF(reader);
			}
		}
	}
	if ((keys = PyDict_Keys(SnmpFds)) == NULL)
		return -1;
	for (i = 0; i < PyList_Size(keys); i++) {
		if ((key = PyList_GetItem(keys, i)) == NULL) {
			Py_DECREF(keys);
			return -1;
		}
		fd = PyInt_AsLong(key);
		if (PyErr_Occurred()) {
			Py_DECREF(keys);
			return -1;
		}
		if ((fd >= maxfd) || (!FD_ISSET(fd, &fdset))) {
			/* Delete this fd from the reactor */
			if ((reader = (SnmpReaderObject*)PyDict_GetItem(SnmpFds,
				    key)) == NULL) {
				Py_DECREF(keys);
				return -1;
			}
			if ((tmp = PyObject_CallMethod(reactor,
				    "removeReader", "O", (PyObject*)reader)) == NULL) {
				Py_DECREF(keys);
				return -1;
			}
			Py_DECREF(tmp);
			if (PyDict_DelItem(SnmpFds, key) == -1) {
				Py_DECREF(keys);
				return -1;
			}
		}
	}
	Py_DECREF(keys);
	/* Setup timeout */
	if (timeoutId) {
		if ((tmp = PyObject_CallMethod(timeoutId, "cancel", NULL)) == NULL) {
			/* Don't really know what to do. It seems better to
			 * raise an exception at this point. */
			Py_CLEAR(timeoutId);
			return -1;
		}
		Py_DECREF(tmp);
		Py_CLEAR(timeoutId);
	}
	if (!block) {
		to = (double)timeout.tv_sec +
		    (double)timeout.tv_usec/(double)1000000;
		if ((timeoutId = PyObject_CallMethod(reactor, "callLater", "dO",
			    to, timeoutFunction)) == NULL) {
			return -1;
		}
	}
	return 0;
}

static void
Snmp_dealloc(SnmpObject* self)
{
	if (self->ss)
		snmp_close(self->ss);
	Snmp_updatereactor();
	Py_XDECREF(self->defers);
	self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
Snmp_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	SnmpObject *self;

	self = (SnmpObject *)type->tp_alloc(type, 0);
	if (self != NULL) {
		self->ss = NULL;
		self->defers = NULL;
	}
	return (PyObject *)self;
}

static void
Snmp_raise_error(struct snmp_session *session)
{
	int liberr, snmperr;
	char *err;
	snmp_error(session, &liberr, &snmperr, &err);
	PyErr_Format(SnmpException, "%s", err);
	free(err);
}

static int
Snmp_init(SnmpObject *self, PyObject *args, PyObject *kwds)
{
	PyObject *host=NULL, *community=NULL;
	char *chost=NULL, *ccommunity=NULL;
	int version = 2;
	struct snmp_session session;

	static char *kwlist[] = {"ip", "community", "version", NULL};
		
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO|i", kwlist, 
		&host, &community, &version))
		return -1;

	snmp_sess_init(&session);
	if ((chost = PyString_AsString(host)) == NULL)
		return -1;
	switch (version) {
	case 1:
		session.version = SNMP_VERSION_1;
		break;
	case 2:
		session.version = SNMP_VERSION_2c;
		break;
	default:
		PyErr_Format(PyExc_ValueError, "invalid SNMP version: %d",
		    version);
		return -1;
	}
	if ((ccommunity = PyString_AsString(community)) == NULL)
		return -1;
	session.community_len = strlen(ccommunity);
	if ((session.community = (u_char*)strdup(ccommunity)) == NULL) {
		PyErr_NoMemory();
		return -1;
	}
	if ((session.peername = strdup(chost)) == NULL) {
		PyErr_NoMemory();
		return -1;
	}
	if ((self->ss = snmp_open(&session)) == NULL) {
		Snmp_raise_error(&session);
		free(session.community);
		free(session.peername);
		return -1;
	}
	if ((self->defers = PyDict_New()) == NULL)
		return -1;
	if (Snmp_updatereactor() == -1)
		return -1;
	return 0;
}

static PyObject*
Snmp_repr(SnmpObject *self)
{
	PyObject *peer = NULL, *community = NULL, *rpeer = NULL,
	    *rcommunity = NULL, *result;
	if ((peer = PyString_FromString(self->ss->peername)) == NULL)
		return NULL;
	if ((community = PyString_FromString((char*)self->ss->community)) == NULL)
		goto reprerror;
	if ((rpeer = PyObject_Repr(peer)) == NULL)
		goto reprerror;
	if ((rcommunity = PyObject_Repr(community)) == NULL)
		goto reprerror;
	result = PyString_FromFormat("%s(host=%s, community=%s, version=%d)",
	    self->ob_type->tp_name,
	    PyString_AsString(rpeer),
	    PyString_AsString(rcommunity),
	    (self->ss->version == SNMP_VERSION_1)?1:2);
	Py_DECREF(rpeer);
	Py_DECREF(peer);
	Py_DECREF(rcommunity);
	Py_DECREF(community);
	return result;
reprerror:
	Py_XDECREF(rpeer);
	Py_XDECREF(peer);
	Py_XDECREF(rcommunity);
	Py_XDECREF(community);
	return NULL;
}

static PyObject*
Snmp_oid2string(PyObject *resultvalue)
{
	PyObject *dot, *tmp, *tmp2, *list;
	int i;
	if ((list = PyTuple_New(PyTuple_Size(resultvalue))) == NULL)
		return NULL;
	for (i = 0; i < PyTuple_Size(resultvalue); i++) {
		if ((tmp = PyTuple_GetItem(resultvalue, i)) == NULL) {
			Py_DECREF(list);
			return NULL;
		}
		if ((tmp2 = PyObject_Str(tmp)) == NULL) {
			Py_DECREF(list);
			return NULL;
		}
		PyTuple_SetItem(list, i, tmp2);
		if (PyErr_Occurred()) {
			Py_DECREF(tmp2);
			Py_DECREF(list);
			return NULL;
		}
	}
	Py_DECREF(resultvalue);
	resultvalue = list;
	if ((dot = PyString_FromString(".")) == NULL)
		return NULL;
	if ((tmp = PyObject_CallMethod(dot,
		    "join", "(O)", resultvalue)) == NULL) {
		Py_DECREF(dot);
		return NULL;
	}
	Py_DECREF(resultvalue);
	Py_DECREF(dot);
	resultvalue = tmp;
	if ((tmp = PyTuple_Pack(1, resultvalue)) == NULL)
		return NULL;
	Py_DECREF(resultvalue);
	resultvalue = tmp;
	if ((tmp2 = PyString_FromString(".%s")) == NULL)
		return NULL;
	if ((tmp = PyString_Format(tmp2,
		    resultvalue)) == NULL) {
		Py_DECREF(tmp2);
		return NULL;
	}
	Py_DECREF(tmp2);
	Py_DECREF(resultvalue);
	return tmp;
}

static void
Snmp_invokeerrback(PyObject *defer)
{
	PyObject *type, *value, *traceback, *failure, *tmp;

	PyErr_Fetch(&type, &value, &traceback);
        if (!traceback)
                failure = PyObject_CallMethod(FailureModule,
		    "Failure", "OO", value, type);
	else
                failure = PyObject_CallMethod(FailureModule,
		    "Failure", "OOO", value, type, traceback);
	if (failure != NULL) {
		if ((tmp = PyObject_GetAttrString(defer, "errback")) != NULL) {
			Py_DECREF(PyObject_CallMethod(reactor, "callLater",
				"iOO", 0, tmp, failure));
			Py_DECREF(tmp);
		}
		Py_DECREF(failure);
	}
	Py_XDECREF(type);
	Py_XDECREF(value);
	Py_XDECREF(traceback);
}

static int
Snmp_handle(int operation, netsnmp_session *session, int reqid,
    netsnmp_pdu *response, void *magic)
{
	PyObject *key, *defer, *results = NULL, *resultvalue = NULL,
	    *resultoid = NULL, *tmp;
	struct ErrorException *e;
	struct variable_list *vars;
	int i;
	long long counter64;
	SnmpObject *self;

	if ((key = PyInt_FromLong(reqid)) == NULL)
		/* Unknown session, don't know what to do... */
		return 1;
	self = (SnmpObject *)magic;
	if ((defer = PyDict_GetItem(self->defers, key)) == NULL)
		return 1;
	Py_INCREF(defer);
	PyDict_DelItem(self->defers, key);
	Py_DECREF(key);
	/* We have our deferred object. We will be able to trigger callbacks and
	 * errbacks */
	if (operation == NETSNMP_CALLBACK_OP_RECEIVED_MESSAGE) {
		if (response->errstat != SNMP_ERR_NOERROR) {
			for (e = SnmpErrorToException; e->name; e++) {
				if (e->error == response->errstat) {
					PyErr_SetString(e->exception, snmp_errstring(e->error));
					goto fireexception;
				}
			}
			PyErr_Format(SnmpException, "unknown error %ld", response->errstat);
			goto fireexception;
		}
	} else {
		PyErr_SetString(SnmpException, "Timeout");
		goto fireexception;
	}
	if ((results = PyDict_New()) == NULL)
		goto fireexception;
	for (vars = response->variables; vars;
	     vars = vars->next_variable) {
	/* Let's handle the value */
		switch (vars->type) {
		case SNMP_NOSUCHOBJECT:
			PyErr_SetString(SnmpNoSuchObject, "No such object was found");
			goto fireexception;
		case SNMP_NOSUCHINSTANCE:
			PyErr_SetString(SnmpNoSuchInstance, "No such instance exists");
			goto fireexception;
		case SNMP_ENDOFMIBVIEW:
			if (PyDict_Size(results) == 0) {
				PyErr_SetString(SnmpEndOfMibView,
				    "End of MIB was reached");
				goto fireexception;
			} else
				continue;
		case ASN_INTEGER:
			resultvalue = PyLong_FromLong(*vars->val.integer);
			break;
		case ASN_UINTEGER:
		case ASN_TIMETICKS:
		case ASN_GAUGE:
		case ASN_COUNTER:
			resultvalue = PyLong_FromUnsignedLong(
				(unsigned long)*vars->val.integer);
			break;
		case ASN_OCTET_STR:
			resultvalue = PyString_FromStringAndSize(
				(char*)vars->val.string, vars->val_len);
			break;
		case ASN_BIT_STR:
			resultvalue = PyString_FromStringAndSize(
				(char*)vars->val.bitstring, vars->val_len);
			break;
		case ASN_OBJECT_ID:
			if ((resultvalue = PyTuple_New(
					vars->val_len/sizeof(oid))) == NULL)
				goto fireexception;
			for (i = 0; i < vars->val_len/sizeof(oid); i++) {
				if ((tmp = PyLong_FromLong(
						vars->val.objid[i])) == NULL)
					goto fireexception;
				PyTuple_SetItem(resultvalue, i, tmp);
			}
			if ((resultvalue = Snmp_oid2string(resultvalue)) == NULL)
				goto fireexception;
			break;
		case ASN_IPADDRESS:
			if (vars->val_len < 4) {
				PyErr_Format(SnmpException, "IP address is too short (%zd < 4)",
				    vars->val_len);
				goto fireexception;
			}
			resultvalue = PyString_FromFormat("%d.%d.%d.%d",
			    vars->val.string[0],
			    vars->val.string[1],
			    vars->val.string[2],
			    vars->val.string[3]);
			break;
		case ASN_COUNTER64:
#ifdef NETSNMP_WITH_OPAQUE_SPECIAL_TYPES
		case ASN_OPAQUE_U64:
		case ASN_OPAQUE_I64:
		case ASN_OPAQUE_COUNTER64:
#endif                          /* NETSNMP_WITH_OPAQUE_SPECIAL_TYPES */
			counter64 = ((unsigned long long)(vars->val.counter64->high) << 32) +
			    (unsigned long long)(vars->val.counter64->low);
			resultvalue = PyLong_FromUnsignedLongLong(counter64);
			break;
#ifdef NETSNMP_WITH_OPAQUE_SPECIAL_TYPES
		case ASN_OPAQUE_FLOAT:
			resultvalue = PyFloat_FromDouble(*vars->val.floatVal);
			break;
		case ASN_OPAQUE_DOUBLE:
			resultvalue = PyFloat_FromDouble(*vars->val.doubleVal);
			break;
#endif                          /* NETSNMP_WITH_OPAQUE_SPECIAL_TYPES */
		default:
			PyErr_Format(SnmpException, "unknown type returned (%d)",
			    vars->type);
			goto fireexception;
		}
		if (resultvalue == NULL) goto fireexception;

		/* And now, the OID */
		if ((resultoid = PyTuple_New(vars->name_length)) == NULL)
			goto fireexception;
		for (i = 0; i < vars->name_length; i++) {
			if ((tmp = PyLong_FromLong(vars->name[i])) == NULL)
				goto fireexception;
			PyTuple_SetItem(resultoid, i, tmp);
		}
		if ((resultoid = Snmp_oid2string(resultoid)) == NULL)
			goto fireexception;

		/* Put into dictionary */
		PyDict_SetItem(results, resultoid, resultvalue);
		Py_CLEAR(resultoid);
		Py_CLEAR(resultvalue);
	}
	if ((tmp = PyObject_GetAttrString(defer, "callback")) == NULL)
		goto fireexception;
	Py_DECREF(PyObject_CallMethod(reactor, "callLater", "iOO", 0, tmp, results));
	Py_DECREF(tmp);
	Py_DECREF(results);
	Py_DECREF(defer);
	Py_DECREF(self);
	return 1;

fireexception:
	Snmp_invokeerrback(defer);
	Py_XDECREF(results);
	Py_XDECREF(resultvalue);
	Py_XDECREF(resultoid);
	Py_DECREF(defer);
	Py_DECREF(self);
	return 1;
}

static PyObject*
Snmp_op(SnmpObject *self, PyObject *args, int op)
{
	PyObject *roid, *oids, *item, *deferred = NULL, *req = NULL;
	char *aoid, *next;
	oid poid[MAX_OID_LEN];
	struct snmp_pdu *pdu=NULL;
	int maxrepetitions = 10, norepeaters = 0;
	int i, oidlen, reqid;
	size_t arglen;

	if (op == SNMP_MSG_GETBULK) {
		if (!PyArg_ParseTuple(args, "O|ii",
			&roid, &maxrepetitions, &norepeaters))
			return NULL;
	} else {
		if (!PyArg_ParseTuple(args, "O", &roid))
			return NULL;
	}

	/* Turn the first argument into a tuple */
	if (!PyTuple_Check(roid) && !PyList_Check(roid) && !PyString_Check(roid)) {
		PyErr_SetString(PyExc_TypeError,
		    "argument should be a string, a list or a tuple");
		return NULL;
	}
	if (PyString_Check(roid)) {
		if ((oids = PyTuple_Pack(1, roid)) == NULL)
			return NULL;
	} else if (PyList_Check(roid)) {
		if ((oids = PyList_AsTuple(roid)) == NULL)
			return NULL;
	} else {
		oids = roid;
		Py_INCREF(oids);
	}
	
	Py_INCREF(self);
	arglen = PyTuple_Size(oids);
	pdu = snmp_pdu_create(op);
	if (op == SNMP_MSG_GETBULK) {
		pdu->max_repetitions = maxrepetitions;
		pdu->non_repeaters = norepeaters;
	}
	for (i = 0; i < arglen; i++) {
		if ((item = PyTuple_GetItem(oids, i)) == NULL)
			goto operror;
		if (!PyString_Check(item)) {
			PyErr_Format(PyExc_TypeError,
			    "element %d should be a string", i);
			goto operror;
		}
		aoid = PyString_AsString(item);
		oidlen = 0;
		while (aoid && (*aoid != '\0')) {
			if (aoid[0] == '.')
				aoid++;
			if (oidlen >= MAX_OID_LEN) {
				PyErr_Format(PyExc_ValueError,
				    "element %d is too large for OID", i);
				goto operror;
			}
			poid[oidlen++] = strtoull(aoid, &next, 10);
			if (aoid == next) {
				PyErr_Format(PyExc_TypeError,
				    "element %d is not a valid OID: %s", i, aoid);
				goto operror;
			}
			aoid = next;
		}
		snmp_add_null_var(pdu, poid, oidlen);
	}
	self->ss->callback = Snmp_handle;
	self->ss->callback_magic = self;
	if ((deferred = PyObject_CallMethod(DeferModule,
		    "Deferred", NULL)) == NULL)
		goto operror;
	if (!snmp_send(self->ss, pdu)) {
		Snmp_raise_error(self->ss);
		/* Instead of raising, we will fire errback */
		Snmp_invokeerrback(deferred);
		Py_DECREF(self);
		Py_DECREF(oids);
		snmp_free_pdu(pdu);
		return deferred;
	}
	reqid = pdu->reqid;
	pdu = NULL;		/* Avoid to free it when future errors occurs */

	/* We create a Deferred object and put it in a dictionary using
	 * pdu->reqid to be able to call its callbacks later. */
	if ((req = PyInt_FromLong(reqid)) == NULL)
		goto operror;
	if (PyDict_SetItem(self->defers, req, deferred) != 0) {
		Py_DECREF(req);
		goto operror;
	}
	Py_DECREF(req);
	if (Snmp_updatereactor() == -1)
		goto operror;
	Py_DECREF(oids);
	return deferred;
	
operror:
	Py_XDECREF(deferred);
	Py_DECREF(self);
	Py_DECREF(oids);
	snmp_free_pdu(pdu);
	return NULL;
}

static PyObject*
Snmp_get(PyObject *self, PyObject *args)
{
	return Snmp_op((SnmpObject*)self, args, SNMP_MSG_GET);
}

static PyObject*
Snmp_getnext(PyObject *self, PyObject *args)
{
	return Snmp_op((SnmpObject*)self, args, SNMP_MSG_GETNEXT);
}

static PyObject*
Snmp_getbulk(PyObject *self, PyObject *args)
{
	return Snmp_op((SnmpObject*)self, args, SNMP_MSG_GETBULK);
}

static PyObject*
Snmp_getip(SnmpObject *self, void *closure)
{
	return PyString_FromString(self->ss->peername);
}

static PyObject*
Snmp_getcommunity(SnmpObject *self, void *closure)
{
	return PyString_FromStringAndSize((char*)self->ss->community,
	    self->ss->community_len);
}

static int
Snmp_setcommunity(SnmpObject *self, PyObject *value, void *closure)
{
	char *newcommunity;
	ssize_t size;

	if (value == NULL) {
		PyErr_SetString(PyExc_TypeError, "cannot delete community");
		return -1;
	}
	if (!PyString_Check(value)) {
		PyErr_SetString(PyExc_TypeError, 
                    "community should be a string");
		return -1;
	}

	if (PyString_AsStringAndSize(value, &newcommunity, &size) == -1)
		return -1;

	free(self->ss->community);
	self->ss->community = (u_char*)strdup(newcommunity);
	self->ss->community_len = size;
	return 0;
}

static PyObject*
Snmp_getversion(SnmpObject *self, void *closure)
{
	switch (self->ss->version) {
	case SNMP_VERSION_1:
		return PyInt_FromLong(1);
	case SNMP_VERSION_2c:
		return PyInt_FromLong(2);
	}
	PyErr_Format(SnmpException, "Unkown SNMP version: %ld",
	    self->ss->version);
	return NULL;
}

static int
Snmp_setversion(SnmpObject *self, PyObject *value, void *closure)
{
	int version;

	if (value == NULL) {
		PyErr_SetString(PyExc_TypeError, "cannot delete version");
		return -1;
	}
	if (!PyInt_Check(value)) {
		PyErr_SetString(PyExc_TypeError, 
                    "version should be 1 or 2");
		return -1;
	}

	version = PyInt_AsLong(value);
	if (PyErr_Occurred())
		return -1;
	switch (version) {
	case 1:
		self->ss->version = SNMP_VERSION_1;
		break;
	case 2:
		self->ss->version = SNMP_VERSION_2c;
		break;
	default:
		PyErr_Format(PyExc_ValueError, "version should be 1 or 2, not %d",
		    version);
		return -1;
	}
	return 0;
}

static PyObject*
SnmpReader_repr(SnmpReaderObject *self)
{
	return PyString_FromFormat("<SnmpReader fd:%d>", self->fd);
}

static PyObject*
SnmpReader_doRead(SnmpReaderObject *self)
{
	fd_set fdset;
	FD_ZERO(&fdset);
	FD_SET(self->fd, &fdset);
	snmp_read(&fdset);
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
SnmpReader_fileno(SnmpReaderObject *self)
{
	return PyInt_FromLong(self->fd);
}

static PyObject*
SnmpReader_connectionLost(PyObject *self, PyObject *args)
{
	PyObject *fd;
	if ((fd = PyInt_FromLong(((SnmpReaderObject*)self)->fd)) == NULL)
		return NULL;
	if (PyDict_DelItem(SnmpFds, fd) == -1) {
		Py_DECREF(fd);
		return NULL;
	}
	Py_DECREF(fd);
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
SnmpReader_logPrefix(SnmpReaderObject *self)
{
	return PyString_FromString("SnmpReader");
}

static PyObject*
SnmpModule_timeout(PyObject *self)
{
	Py_CLEAR(timeoutId);
	snmp_timeout();
	if (Snmp_updatereactor() == -1)
		return NULL;
	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef SnmpModule_methods[] = {
	{"timeout", (PyCFunction)SnmpModule_timeout,
	 METH_NOARGS, "Handle SNMP timeout"},
	{NULL}
};

static PyMethodDef Snmp_methods[] = {
	{"get", Snmp_get,
	 METH_VARARGS, "Retrieve an OID value using GET"},
	{"getnext", Snmp_getnext,
	 METH_VARARGS, "Retrieve an OID value using GETNEXT"},
	{"getbulk", Snmp_getbulk,
	 METH_VARARGS, "Retrieve an OID value using GETBULK"},
	{NULL}  /* Sentinel */
};

static PyGetSetDef Snmp_getseters[] = {
    {"ip", (getter)Snmp_getip, NULL, "ip", NULL},
    {"community",
     (getter)Snmp_getcommunity, (setter)Snmp_setcommunity,
     "community", NULL},
    {"version",
     (getter)Snmp_getversion, (setter)Snmp_setversion,
     "version", NULL},
    {NULL}  /* Sentinel */
};


static PyMethodDef SnmpReader_methods[] = {
	{"doRead", (PyCFunction)SnmpReader_doRead,
	 METH_NOARGS, "some data available for reading"},
	{"fileno", (PyCFunction)SnmpReader_fileno,
	 METH_NOARGS, "get file descriptor"},
	{"connectionLost", SnmpReader_connectionLost,
	 METH_VARARGS, "call when connection is lost"},
	{"logPrefix", (PyCFunction)SnmpReader_logPrefix,
	 METH_NOARGS, "log prefix"},
	{NULL}  /* Sentinel */
};

static PyTypeObject SnmpType = {
	PyObject_HEAD_INIT(NULL)
	0,			   /*ob_size*/
	"snmp.AgentProxy",	   /*tp_name*/
	sizeof(SnmpObject),	   /*tp_basicsize*/
	0,                         /*tp_itemsize*/
	(destructor)Snmp_dealloc,  /*tp_dealloc*/
	0,                         /*tp_print*/
	0,                         /*tp_getattr*/
	0,                         /*tp_setattr*/
	0,                         /*tp_compare*/
	(reprfunc)Snmp_repr,	   /*tp_repr*/
	0,                         /*tp_as_number*/
	0,                         /*tp_as_sequence*/
	0,                         /*tp_as_mapping*/
	0,                         /*tp_hash */
	0,                         /*tp_call*/
	0,			   /*tp_str*/
	0,                         /*tp_getattro*/
	0,                         /*tp_setattro*/
	0,                         /*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT |
	Py_TPFLAGS_BASETYPE,	   /*tp_flags*/
	"SNMP session",            /*tp_doc*/
	0,			   /* tp_traverse */
	0,			   /* tp_clear */
	0,			   /* tp_richcompare */
	0,			   /* tp_weaklistoffset */
	0,			   /* tp_iter */
	0,			   /* tp_iternext */
	Snmp_methods,		   /* tp_methods */
	0,			   /* tp_members */
	Snmp_getseters,		   /* tp_getset */
	0,                         /* tp_base */
	0,                         /* tp_dict */
	0,                         /* tp_descr_get */
	0,                         /* tp_descr_set */
	0,                         /* tp_dictoffset */
	(initproc)Snmp_init,	   /* tp_init */
	0,                         /* tp_alloc */
	Snmp_new,		   /* tp_new */
};

static PyTypeObject SnmpReaderType = {
	PyObject_HEAD_INIT(NULL)
	0,			   /*ob_size*/
	"snmp.SnmpReader",	   /*tp_name*/
	sizeof(SnmpReaderObject),  /*tp_basicsize*/
	0,                         /*tp_itemsize*/
	0,			   /*tp_dealloc*/
	0,                         /*tp_print*/
	0,                         /*tp_getattr*/
	0,                         /*tp_setattr*/
	0,                         /*tp_compare*/
	(reprfunc)SnmpReader_repr, /*tp_repr*/
	0,                         /*tp_as_number*/
	0,                         /*tp_as_sequence*/
	0,                         /*tp_as_mapping*/
	0,                         /*tp_hash */
	0,                         /*tp_call*/
	0,			   /*tp_str*/
	0,                         /*tp_getattro*/
	0,                         /*tp_setattro*/
	0,                         /*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT |
	Py_TPFLAGS_BASETYPE,	   /*tp_flags*/
	"SNMP reader object",	   /*tp_doc*/
	0,			   /* tp_traverse */
	0,			   /* tp_clear */
	0,			   /* tp_richcompare */
	0,			   /* tp_weaklistoffset */
	0,			   /* tp_iter */
	0,			   /* tp_iternext */
	SnmpReader_methods,	   /* tp_methods */
};

PyDoc_STRVAR(module_doc,
    "simple interface for twisted to libnetsnmp");

PyMODINIT_FUNC
initsnmp(void)
{
	PyObject *m, *exc;
	char *name;
	struct ErrorException *e;
	netsnmp_log_handler *logh;

	if (PyType_Ready(&SnmpType) < 0) return;
	SnmpReaderType.tp_new = PyType_GenericNew;
	if (PyType_Ready(&SnmpReaderType) < 0) return;

	m = Py_InitModule3("snmp", SnmpModule_methods, module_doc);
	if (m == NULL)
		return;

	/* Exception registration */
#define ADDEXCEPTION(var, name, parent)					\
	if (var == NULL) {						\
	    var = PyErr_NewException("snmp." name, parent, NULL);	\
	    if (var == NULL)						\
		    return;						\
	}								\
	Py_INCREF(var);							\
	PyModule_AddObject(m, name, var)
	ADDEXCEPTION(SnmpException, "SNMPException", NULL);
	ADDEXCEPTION(SnmpNoSuchObject, "SNMPNoSuchObject", SnmpException);
	ADDEXCEPTION(SnmpNoSuchInstance, "SNMPNoSuchInstance", SnmpException);
	ADDEXCEPTION(SnmpEndOfMibView, "SNMPEndOfMibView", SnmpException);
	for (e = SnmpErrorToException; e->name; e++) {
		if (!e->exception) {
			if (asprintf(&name, "snmp.%s", e->name) == -1) {
				PyErr_NoMemory();
				return;
			}
			exc = PyErr_NewException(name, SnmpException, NULL);
			free(name);
			if (exc == NULL) return;
			e->exception = exc;
		}
		Py_INCREF(e->exception);
		PyModule_AddObject(m, e->name, e->exception);
	}

	Py_INCREF(&SnmpType);
	PyModule_AddObject(m, "AgentProxy", (PyObject *)&SnmpType);

	if (DeferModule == NULL)
		if ((DeferModule =
			PyImport_ImportModule("twisted.internet.defer")) == NULL)
			return;
	if (FailureModule == NULL)
		if ((FailureModule =
			PyImport_ImportModule("twisted.python.failure")) == NULL)
			return;
	if (reactor == NULL)
		if ((reactor =
			PyImport_ImportModule("twisted.internet.reactor")) == NULL)
			return;
	if (SnmpFds == NULL)
		if ((SnmpFds = PyDict_New()) == NULL)
			return;
	if (timeoutFunction == NULL)
		if ((timeoutFunction = Py_FindMethod(SnmpModule_methods,
			    m, "timeout")) == NULL)
			return;

	/* Try to load as less MIB as possible */
	unsetenv("MIBS");
	setenv("MIBDIRS", "/dev/null", 1);
	/* Disable any logging */
	snmp_disable_log();
        logh = netsnmp_register_loghandler(NETSNMP_LOGHANDLER_NONE, LOG_DEBUG);
	/* Init SNMP */
	init_snmp("snmp");
}
