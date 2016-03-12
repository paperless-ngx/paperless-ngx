.. _api:

The REST API
############

Paperless makes use of the `Django REST Framework`_ standard API interface
because of its inherent awesomeness.  Conveniently, the system is also
self-documenting, so to learn more about the access points, schema, what's
accepted and what isn't, you need only visit ``/api`` on your local Paperless
installation.

.. _Django REST Framework: http://django-rest-framework.org/


.. _api-uploading:

Uploading
---------

File uploads in an API are hard and so far as I've been able to tell, there's
no standard way of accepting them, so rather than crowbar file uploads into the
REST API and endure that headache, I've left that process to a simple HTTP
POST, documented on the :ref:`consumption page <consumption-http>`.
