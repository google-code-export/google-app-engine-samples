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

import logging
import wsgiref.handlers
from google.appengine.api import xmpp
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp
from models import Channel
from models import Person


class TaskController(webapp.RequestHandler):
  """Handler class for all tasks from the task queue."""

  _BROADCAST_BATCH = 5
  _STATS_BATCH = 50

  def Broadcast(self):
    channel = Channel.ChannelByName(self.request.get('channel'), create=False)
    if not channel: return  # channel became empty?
    message = self.request.get('message')
    skip_person = self.request.get('skip')
    if skip_person:
      skip_person = Person.PersonByEmail(skip_person)

    q = Person.all().filter('channel =', channel).order('__key__')
    start_at = self.request.get('start_at')
    if start_at:
      q.filter('__key__ >', db.Key(start_at))
    people = q.fetch(self._BROADCAST_BATCH)
    jids = []
    for p in people:
      if skip_person == p:
        continue
      jids.append(p.jid())
    if not jids:
      return
    try:
      xmpp.send_message(jids, message)
    except xmpp.InvalidJidError:
      logging.error('InvalidJidError caught. JIDs were [%s]',
          ', '.join(['"%s"' % x for x in jids]))
      raise

    # Add a task for the next batch.
    params = {
        'channel': channel.name,
        'message': message,
        'start_at': str(people[-1].key()),
    }
    if skip_person:
      params['skip'] = skip_person.jid()
    taskqueue.Task(url='/task/broadcast', params=params).add('chats')

  def UpdateChannelStats(self):
    """Recompute num_members for a channel."""
    channel = Channel.ChannelByName(self.request.get('channel'), create=False)
    if not channel: return  # channel became empty?
    num_members = int(self.request.get('num_members', '0'))

    q = Person.all(keys_only=True).filter('channel =', channel).order('__key__')
    start_at = self.request.get('start_at')
    if start_at:
      q.filter('__key__ >', db.Key(start_at))
    people = q.fetch(self._STATS_BATCH)
    if people:
      # More to go.
      num_members += len(people)
      params = {
          'channel': channel.name,
          'num_members': num_members,
          'start_at': str(people[-1]),
      }
      taskqueue.Task(url='/task/update-channel-stats',
                     params=params).add('stats')
      return
    # Finished
    channel.num_members = num_members
    channel.put()
    logging.debug('%s now has %d members.' % (channel, num_members))

  def get(self, op):
    """Trivial GET handler so some tasks can be triggered from a browser."""
    if op == 'update-channel-stats':
      self.UpdateChannelStats()

  def post(self, op):
    if op == 'broadcast':
      self.Broadcast()
    elif op == 'update-channel-stats':
      self.UpdateChannelStats()


def main():
  app = webapp.WSGIApplication([
      ('/task/(broadcast|update-channel-stats)', TaskController),
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(app)


if __name__ == '__main__':
  main()
