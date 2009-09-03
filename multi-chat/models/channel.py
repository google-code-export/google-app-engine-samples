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

import re
from google.appengine.api import memcache
from google.appengine.ext import db


class Channel(db.Model):
  name = db.StringProperty(required=True)

  # Recomputed asynchronously in controllers/task.py.
  num_members = db.IntegerProperty(default=0)

  # A valid channel name matches this regex; this doesn't include the leading
  # hash mark ("#").
  CHANNEL_NAME_REGEX = r'[-a-z0-9]+'

  MEMCACHE_TTL = 10*60  # Hold Channel objects for 10 minutes

  # 'name' is meant to be a unique channel attribute.
  def __cmp__(self, other):
    if not self or not other:
      return -1
    return cmp(self.name, other.name)

  def __hash__(self):
    return hash(self.name)

  def __str__(self):
    return '#' + self.name

  def MemcacheKey(self):
    """Return the memcache key for this channel."""
    return 'channel:' + self.name

  def put(self):
    memcache.delete(self.MemcacheKey())
    return super(Channel, self).put()

  def delete(self):
    memcache.delete(self.MemcacheKey())
    return super(Channel, self).delete()

  @property
  def people(self):
    return db.get(self.members)

  @staticmethod
  def ChannelByName(name, create=True):
    """Returns the channel matching the given name, or (optionally) create it."""
    if not re.match(Channel.CHANNEL_NAME_REGEX, name):
      raise RuntimeError('Illegal channel name: #%s' % name)

    key_name = 'channel:' + name
    channel = memcache.get(key_name)
    if channel: return channel

    if not create:
      channel = Channel.get_by_key_name(key_name)
    else:
      channel = Channel.get_or_insert(key_name, name=name)

    if channel:
      memcache.add(channel.MemcacheKey(), channel, Channel.MEMCACHE_TTL)
    return channel
