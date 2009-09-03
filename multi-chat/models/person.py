# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db
from channel import Channel


class Person(db.Model):
  user = db.UserProperty(required=True)
  channel = db.ReferenceProperty(Channel)

  MEMCACHE_TTL = 10*60  # Hold Person objects for 10 minutes

  # The 'user' attribute should be unique, so this is an accurate comparison.
  def __cmp__(self, other):
    if not self or not other:
      return -1
    return cmp(self.user, other.user)

  def __hash__(self):
    return hash(self.user.email())

  def __str__(self):
    return self.user.email().split('@')[0]

  def jid(self):
    return self.user.email()

  def MemcacheKey(self):
    """Return the memcache key for this person."""
    return 'person:' + self.user.email()

  def put(self):
    memcache.delete(self.MemcacheKey())
    return super(Person, self).put()

  @staticmethod
  def PersonByEmail(email):
    """Returns the person matching the given email address, or create them."""
    memcache_key = 'person:' + email
    p = memcache.get(memcache_key)
    if p:
      return p

    user = users.User(email=email)
    p = Person.all().filter('user =', user).get()
    if not p:
      p = Person(user=users.User(email=email))
      p.put()

    memcache.add(p.MemcacheKey(), p, Person.MEMCACHE_TTL)
    return p
