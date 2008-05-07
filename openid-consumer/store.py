#!/usr/bin/python
#
# Copyright 2007, Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An OpenIDStore implementation that uses the datastore as its backing store.
Stores associations, nonces, and authentication tokens.

OpenIDStore is an interface from JanRain's OpenID python library:
  http://openidenabled.com/python-openid/

For more, see openid/store/interface.py in that library.
"""

import datetime

from openid.association import Association
from openid.store.interface import OpenIDStore
from google.appengine.ext import db


class Association(db.Model):
  """An association with another OpenID server, either a consumer or a provider.
  """
  url = db.LinkProperty()
  handle = db.StringProperty()
  association = db.TextProperty()


class Nonce(db.Model):
  """An OpenID nonce.
  """
  nonce = db.StringProperty()
  created = db.DateTimeProperty()


class DatastoreStore(OpenIDStore):
  """An OpenIDStore implementation that uses the datastore. See
  openid/store/interface.py for in-depth descriptions of the methods.

  They follow the OpenID python library's style, not Google's style, since
  they override methods defined in the OpenIDStore class.
  """

  def storeAssociation(self, server_url, association):
    """
    This method puts a C{L{Association <openid.association.Association>}}
    object into storage, retrievable by server URL and handle.
    """
    assoc = Association(url=server_url,
                        handle=association.handle,
                        association=association.serialize())
    assoc.put()

  def getAssociation(self, server_url, handle=None):
    """
    This method returns an C{L{Association <openid.association.Association>}}
    object from storage that matches the server URL and, if specified, handle.
    It returns C{None} if no such association is found or if the matching
    association is expired.

    If no handle is specified, the store may return any association which
    matches the server URL. If multiple associations are valid, the
    recommended return value for this method is the one that will remain valid
    for the longest duration.
    """
    query = Association.all().filter('url', server_url)
    if handle:
      query.filter('handle', handle)

    results = query.fetch(1)
    if results:
      association = Association.deserialize(results[0].association)
      if association.getExpiresIn() > 0:
        # hasn't expired yet
        return association

    return None

  def removeAssociation(self, server_url, handle):
    """
    This method removes the matching association if it's found, and returns
    whether the association was removed or not.
    """
    query = Association.gql('WHERE url = :1 AND handle = :2',
                            server_url, handle)
    return self._delete_first(query)

  def storeNonce(self, nonce):
    """
    Stores a nonce. This is used by the consumer to prevent replay attacks.
    """
    nonce = Nonce(nonce=nonce, created=datetime.datetime.now())
    nonce.put()

  def useNonce(self, nonce):
    """
    This method is called when the library is attempting to use a nonce. If
    the nonce is in the store, this method removes it and returns a value
    which evaluates as true. Otherwise it returns a value which evaluates as
    false.

    This method is allowed and encouraged to treat nonces older than some
    period (a very conservative window would be 6 hours, for example) as no
    longer existing, and return False and remove them.
    """
    query = Nonce.gql('WHERE nonce = :1 AND created >= :2',
                      nonce,
                      datetime.datetime.now() - datetime.timedelta(hours=6))
    return self._delete_first(query)

  def getAuthKey(self):
    """
    This method returns a key used to sign the tokens, to ensure that they
    haven't been tampered with in transit. It should return the same key every
    time it is called. The key returned should be C{L{AUTH_KEY_LEN}} bytes
    long.
    """
    auth_key = 'My Insecure Auth Key'
    assert len(auth_key) == self.AUTH_KEY_LEN
    return auth_key

  def _delete_first(self, query):
    """Deletes the first result for the given query.

    Returns True if an entity was deleted, false if no entity could be deleted
    or if the query returned no results.
    """
    results = query.fetch(1)

    if results:
      try:
        results[0].delete()
        return True
      except db.Error:
        return False
    else:
      return False
