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
import re
import wsgiref.handlers
from google.appengine.api import xmpp
from google.appengine.api.labs import taskqueue
from google.appengine.ext import webapp
from google.appengine.ext.webapp import xmpp_handlers
from models import Channel
from models import Log
from models import Person


class XmppController(xmpp_handlers.CommandHandler):
  """Handler class for all XMPP activity."""

  _CHANNEL_SIZE_LIMIT = 100  # Max people in a channel.
  _LIST_LIMIT = 20  # Max channels to show for /list command.
  _NAME_LIMIT = 20  # Max names to show for /name command.

  def Broadcast(self, channel, message, system=False, exclude_self=True):
    """Queues a broadcast message.

    Args:
      channel: The target channel.
      message: The message to broadcast.
      system: Whether this is a system message (i.e. not a chat).
      exclude_self: Whether to exclude self.person from the broadcast.
    """
    if system:
      lines = ['* ' + l for l in message.split('\n')]
      message = '\n'.join(lines)
    params = {
        'channel': channel.name,
        'message': message,
    }
    if exclude_self:
      params['skip'] = self.person.jid()
    taskqueue.Task(url='/task/broadcast', params=params).add('chats')

  def Log(self, channel, body, person=None, system=False):
    """Log a message.

    Args:
      channel: The channel object the message was sent to.
      body: The body of the message.
      person: The person who sent the message. Defaults to self.person.
      system: Whether this is a system log (i.e. not a chat).

    You should not use person and system at the same time.
    """
    if person and system:
      raise RuntimeError('You can\'t use person and system here')
    if not system:
      if not person: person = self.person
      log = Log(channel=channel.name,
                user=person.user.email(),
                body=body)
    else:
      log = Log(channel=channel.name,
                system=True,
                body=body)
    log.put()

  def help_command(self, msg):
    channel_rx = '/#' + Channel.CHANNEL_NAME_REGEX + '/'
    lines = (
        '* Supported commands:',
        '*   /help',
        '*   /join #<channel>',
        '*   /leave',
        '*   /list',
        '*   /names [#<channel>]',
        '*   /me <clause>',
        '* ',
        ('* Channels match the regex %s; don\'t forget the hash mark!' %
         channel_rx),
    )
    msg.reply('\n'.join(lines))

  def join_command(self, msg):
    m = re.match(r'^#(?P<channel>' + Channel.CHANNEL_NAME_REGEX + ')$',
                 msg.arg)
    if not m:
      msg.reply('* Bad /join syntax')
      return
    name = m.group('channel')
    if self.person.channel and (self.person.channel.name == name):
      msg.reply('* You\'re already in #%s!' % name)
      return

    # Leave the existing channel, and tell them about it.
    if self.person.channel:
      old = self.person.channel
      message = '%s has left %s' % (self.person, old)
      self.Broadcast(old, message, system=True)
      self.Log(old, message, system=True)
      self.person.channel = None
      taskqueue.Task(url='/task/update-channel-stats',
                     params={'channel': old.name}).add('stats')

    channel = Channel.ChannelByName(name, create=True)
    if channel.num_members >= self._CHANNEL_SIZE_LIMIT:
      msg.reply('* Sorry, too many people (%d) already in %s' %
                (channel.num_members, channel))
      return
    self.person.channel = channel
    self.person.put()
    msg.reply('* You have joined %s' % channel)
    message = '%s has joined %s' % (self.person, channel)
    self.Broadcast(channel, message, system=True)
    self.Log(channel, message, system=True)
    taskqueue.Task(url='/task/update-channel-stats',
                   params={'channel': channel.name}).add('stats')

  def leave_command(self, msg):
    if not self.person.channel:
      msg.reply('* Hey, you aren\'t in a channel!')
    else:
      message = '%s has left %s' % (self.person, self.person.channel)
      self.Broadcast(self.person.channel, message, system=True)
      self.Log(self.person.channel, message, system=True)

      name = self.person.channel.name
      self.person.channel = None
      self.person.put()
      msg.reply('* You have left #%s' % name)
      taskqueue.Task(url='/task/update-channel-stats',
                     params={'channel': name}).add('stats')

  def list_command(self, msg):
    """Handle /list commands."""
    lines = []
    q = Channel.all().order('-num_members').filter('num_members >', 0)
    channels = q.fetch(self._LIST_LIMIT + 1)
    if not len(channels):
      msg.reply('* No channels exist!')
      return
    if len(channels) <= self._LIST_LIMIT:
      # Show all, sorted by channel name.
      channels.sort(key=lambda c: c.name)
      lines.append('* All channels:')
    else:
      # Show the top N channels, sorted by num_members.
      channels.pop()
      lines.append('* More than %d channels; here are the most popular:' %
                   self._LIST_LIMIT)
    for c in channels:
      if c.num_members == 1:
        count = '1 person'
      else:
        count = '%d people' % c.num_members
      s = '* - %s (%s)' % (c, count)
      lines.append(s)
    msg.reply('\n'.join(lines))

  def names_command(self, msg):
    """Handle /names commands."""
    m = re.match(r'^(#(?P<channel>' + Channel.CHANNEL_NAME_REGEX + '))?$',
                 msg.arg)
    if not m:
      msg.reply('* Bad /names syntax')
      return
    if m.group('channel'):
      channel = Channel.ChannelByName(m.group('channel'), create=False)
      if not channel:
        msg.reply('* No such channel: #%s' % m.group('channel'))
        return
    else:
      channel = self.person.channel
      if not channel:
        msg.reply('* You either need to be in a channel, or specify one.')
        return
    q = Person.all().filter('channel =', channel)
    people = q.fetch(self._NAME_LIMIT + 1)
    if len(people) <= self._NAME_LIMIT:
      people = people[0:self._NAME_LIMIT]
      names = sorted([str(p) for p in people])
      msg.reply('* Members of %s: %s' % (channel, ' '.join(names)))
    else:
      msg.reply('* More than %d people in %s' % (self._NAME_LIMIT, channel))

  def me_command(self, msg):
    """Handle /me commands."""
    if not self.person.channel:
      msg.reply('* You need to be in a channel to do that.')
      return
    # Broadcast to everyone in the channel.
    txt = '%s *** %s %s' % (self.person.channel, self.person, msg.arg)
    self.Broadcast(self.person.channel, msg.body)
    self.Log(self.person.channel, msg.body)

  def text_message(self, msg):
    """Handle plain messages."""
    # Chat, but only if you're in a channel.
    channel = self.person.channel
    if channel:
      self.Broadcast(channel, u'%s <%s> %s' % (channel, self.person, msg.body))
      self.Log(channel, msg.body)
    else:
      msg.reply('* You need to be in a channel to chat.')

  def message_received(self, msg):
    """Handle all messages; overrides CommandHandlerMixin."""
    logging.debug('%s said "%s"', msg.sender, msg.body)

    match = re.match(r'^([^/]+)(/.*)?$', msg.sender)
    if not match:
      msg.reply('* Hey, you\'re using a weird JID!')
      return
    self.person = Person.PersonByEmail(match.group(1))
    if not self.person:
      msg.reply('* Sorry, who are you?')
      return

    super(XmppController, self).message_received(msg)


def main():
  app = webapp.WSGIApplication([
      ('/_ah/xmpp/message/chat/', XmppController),
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(app)


if __name__ == '__main__':
  main()
