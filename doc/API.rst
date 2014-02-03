Wiremaps ReST API
=================

Wiremaps uses a ReST_ API_ to export the information it collected to a
frontend, like the web interface that is provided. This API is queried
using simple URL and returns JSON_.

.. _ReST: http://en.wikipedia.org/wiki/Representational_State_Transfer
.. _API: http://en.wikipedia.org/wiki/Api
.. _JSON: http://en.wikipedia.org/wiki/Json

General principles
------------------

All URL are prefixed by ``/api/X.Y`` where ``X.Y`` is the API version
we would like to use. Currently, only ``1.0`` is supported. Therefore,
all URL should be prefixed by ``/api/1.0``.

HTTP return codes follow web semantic:
 - 200: the request has been understood correctly and JSON code should
   follow
 - 304: requested data has not been modified since the last query
 - 301, 302: redirect, please follow it
 - 403: resource is forbidden
 - 404: resource has not been found
 - 500: internal error (usually, you get XHTML with explanations)

The application should be prepared to handle any return code. HTTP
body is usually JSON but the content type should be checked before
handling data. The content type for JSON is ``application/json``.

All URL should be suffixed by ``/``. Otherwise, a redirect will be
returned.

Time travelling
---------------

To go in the past, the URL should be prefixed by
``/api/1.0/past/YYYY-MM-DD HH:MM:SS`` instead of just ``/api/1.0``. In
this case, the request is executed as if the current date was the
specified one.

Getting the list of known equipments
------------------------------------

The list of known equipment can be grabbed using ``/equipment/``::

 $ curl -i http://localhost:8087/api/1.0/equipment/
 HTTP/1.1 200 OK
 Transfer-encoding: chunked
 Date: Sun, 11 Jul 2010 08:41:27 GMT
 Content-type: application/json; charset=UTF-8
 Server: TwistedWeb/2.4.0

 [["switch1.example.org", "192.168.110.15"],
  ["switch2.example.org", "192.168.110.16"],
  ["switch3.example.org", "192.168.110.17"]]

Getting the list of ports
-------------------------

The list of ports of an equipment can be grabbed using
``/equipment/<ip>/``::

 $ curl -i http://localhost:8087/api/1.0/equipment/192.168.110.15/
 HTTP/1.1 200 OK
 Transfer-encoding: chunked
 Date: Sun, 11 Jul 2010 08:42:40 GMT
 Content-type: application/json; charset=UTF-8
 Server: TwistedWeb/2.4.0

 [[1,"Port 1","ifc1 (Slot: 1 Port: 1)","up",100,"full",true],
  [2,"Port 2","ifc2 (Slot: 1 Port: 2)","down",1000,"full",true],
  [3,"Port 3","ifc3 (Slot: 1 Port: 3)","down",1000,"full",true],
  [4,"Port 4","ifc4 (Slot: 1 Port: 4)","down",1000,"full",true]]

For each port, the first element is the index of the port, the second
is the name, the third is the description, the fourth is the state (up
or down), the fifth is the speed, the sixth is the duplex and the last
one is the autonegociation. The last third ones can be ``null``.

Getting the description of an equipment
---------------------------------------

The description of the equipment can be grabbed using
``/equipment/<ip>/descr/``::

 $ curl -i http://localhost:8087/api/1.0/equipment/192.168.110.15/descr/
 HTTP/1.1 200 OK
 Transfer-encoding: chunked
 Date: Sun, 11 Jul 2010 08:47:59 GMT
 Content-type: application/json; charset=UTF-8
 Server: TwistedWeb/2.4.0

 [["Ethernet Routing Switch 5510-24T"]]

With version 1.1, you can also get the location with the same URL::

 $ curl -i http://localhost:8087/api/1.1/equipment/192.168.110.15/descr/
 HTTP/1.1 200 OK
 Transfer-encoding: chunked
 Date: Sun, 11 Jul 2010 08:47:59 GMT
 Content-type: application/json; charset=UTF-8
 Server: TwistedWeb/2.4.0

 [["Ethernet Routing Switch 5520-24T","B3/N33"]]

Get VLAN
--------

You can get an HTML table with the list of VLAN and associated port in
a user-friendly format with ``/equipment/<ip>/vlans/``::

 $ curl -i http://localhost:8087/api/1.0/equipment/192.168.110.15/vlans/
 HTTP/1.1 200 OK
 Transfer-encoding: chunked
 Date: Sun, 11 Jul 2010 08:50:00 GMT
 Content-type: text/html; charset=UTF-8
 Server: TwistedWeb/2.4.0

 <table class="vlan">
 <thead><td>VID</td><td>Name</td><td>Ports</td></thead>
 <tr class="even"><td><a href="api/1.0/search/147/">147</a></td>
  <td>FAI</td><td>Port 1</td></tr>
 <tr class="odd"><td><a href="api/1.0/search/243/">243</a></td>
  <td>OOB</td><td>Port 1, Port 20-22</td></tr>
 <tr class="even"><td><a href="api/1.0/search/2012/">2012</a></td>
   <td>Admin</td><td>Port 1</td></tr>
 <tr class="odd"><td><a href="api/1.0/search/4094/">4094</a></td>
  <td>Trash</td><td>Port 2-19, Port 23-24</td></tr></table> 

Please note that this URL does not return JSON data!

Getting information about one port
----------------------------------

To get information about one port, use ``/equipment/<ip>/<port>/``
where ``<port>`` is the index of the port::

 $ curl -i http://localhost:8087/api/1.0/equipment/192.168.110.15/1/
 HTTP/1.1 200 OK
 Transfer-encoding: chunked
 Date: Sun, 11 Jul 2010 08:53:43 GMT
 Content-type: application/json; charset=UTF-8
 Server: TwistedWeb/2.4.0

 [["MAC","<a href=\"api/1.0/search/00:14:0e:15:18:19/\">00:14:0e:15:18:19</a>",
   "00:14:0e:15:18:19"],
  ["Speed / Speed","100 Mbit/s",100],
  ["Speed / Duplex","full",null],
  ["Speed / Autoneg","enabled",true],
  ["LLDP  / Host",
   "<a href=\"api/1.0/equipment/switch4.example.org/\">switch4.example.org</a>",
   "switch4.example.org"]]

You get a list of information related to the port. Each element of
information is a tuple:
 1. the name of the element
 2. an XHTML representation of the value of the element
 3. a simple representation of the element

The simple representation should be used to allow sorting or
parsing. The user should be presented with the XHTML representation.

Refreshing
----------

To force Wiremaps to retrieve new information, you can use the
following two URL:
 - ``/equipment/refresh/`` to refresh all information for all equipments and
   discover new equipments
 - ``/equipment/<ip>/refresh/`` to refresh the information related to
   the equipment whose IP is given.

Images
------

Wiremaps allows to get a PNG image representing the equipment whose
OID, name or IP is provided. The accepted URL are:
 - ``/images/<name>/``
 - ``/images/<oid>/``
 - ``/images/<ip>/``

Using any of the URL above will provide a PNG representation of the
equipment or a 404 if no PNG can be provided.

Search and completion
---------------------

Collected information can be searched using ``/search/<query>/`` where
``<query>`` can be:
 - a MAC address (6 hexadecimal bytes separated by ``:``)
 - an IPv4 address
 - a VLAN (a number)
 - a hostname (anything else)

A list of XHTML element is returned summarizing what has been
found. This list should be turned to an XHTML unordered list before
being presented to the user. It contains links to trigger other
queries.

To allow autocompletion, most strings can be autocompleted using
``/complete/<query>/`` where ``<query>`` is the beginning of a MAC
address, an IPv4 address, a VLAN or a hostname. A list of possible
terms is returned.
