#!/usr/bin/python2.4
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A simple example of matcher API."""

__author__ = 'bwydrowski@google.com (Bartek Wydrowski)'

import cgi
import sys
import time

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import matcher
from google.appengine.api import users
from google.appengine.ext import db


# these are defined at the bottom
HEADER1 = HEADER2 = FOOTER = None


class MatcherDocument(db.Model):
  """MatcherDocument is the class sent to the matcher.Match function."""
  field_text_a = db.StringProperty()
  field_text_b = db.StringProperty()
  field_int32_a = db.IntegerProperty()
  field_int32_b = db.IntegerProperty()
  field_float_a = db.FloatProperty()
  field_float_b = db.FloatProperty()


class SubscriptionInfo(db.Model):
  """SubscriptionInfo stores queries and hitcounts per subscription id."""
  subscription_id = db.StringProperty()
  hit_count = db.IntegerProperty()
  user_id = db.StringProperty()


class IncHitCounter(webapp.RequestHandler):
  """IncHitCounter handles match result events by incrementing hit count."""

  def post(self):
    sub_ids = self.request.get_all('id')
    doc = matcher.get_document(self.request)
    user_id = self.request.get('topic')
    assert isinstance(doc, MatcherDocument)
    for sub_id in sub_ids:
      subscription_info = db.GqlQuery('SELECT * FROM SubscriptionInfo WHERE' +
          ' subscription_id = :1 AND user_id = :2', sub_id, user_id).get()
      if not subscription_info: continue
      db.run_in_transaction(self.__Increment, subscription_info.key())

  def __Increment(self, key):
    if key:
      subscription_info = db.get(key)
    if not subscription_info:
      subscription_info = SubscriptionInfo()
    subscription_info.hit_count += 1
    db.put(subscription_info)


class MatcherDemo(webapp.RequestHandler):
  """This class is a UI for matcher to demonstrate its capabilities."""

  def get(self):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.url))
      return
    self.__Render(user)

  def post(self):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.url))
      return

    """Handler for match, subscribe or unsubscribe form button press."""
    # Match submit button was pressed
    if self.request.get('match') == 'Match':
      doc = MatcherDocument()
      doc.field_text_a = str(self.request.get('field_text_a'))
      doc.field_text_b = str(self.request.get('field_text_b'))
      doc.field_int32_a = int(self.request.get('field_int32_a'))
      doc.field_int32_b = int(self.request.get('field_int32_b'))
      doc.field_float_a = float(self.request.get('field_float_a'))
      doc.field_float_b = float(self.request.get('field_float_b'))
      matcher.match(doc, topic = user.user_id())

    # Subscribe submit button was pressed
    elif self.request.get('subscribe') == 'Subscribe':
      subscription_id = self.request.get('subscription_id')
      query = self.request.get('query')
      matcher.subscribe(MatcherDocument, query, subscription_id,
                        topic = user.user_id())
      self.__ResetSubscriptionInfo(subscription_id, user.user_id())

    # Unsubscribe submit button was pressed
    elif self.request.get('unsubscribe') == 'Unsubscribe':
      subscription_id = self.request.get('subscription_id')
      matcher.unsubscribe(MatcherDocument, subscription_id,
                          topic = user.user_id())
      self.__ResetSubscriptionInfo(subscription_id, user.user_id())

    self.__Render(user)

  def __GetSubscriptionInfo(self, subscription_id, user_id):
    sub_info = db.GqlQuery('SELECT * FROM SubscriptionInfo WHERE' +
        ' subscription_id = :1 AND user_id = :2',
        subscription_id, user_id).get()
    if sub_info: return sub_info.hit_count
    return 0

  def __ResetSubscriptionInfo(self, subscription_id, user_id):
    # Delete existing instance(s) of subscription
    subs = db.GqlQuery('SELECT * FROM SubscriptionInfo WHERE' +
        ' subscription_id = :1 AND user_id = :2',
        subscription_id, user_id).fetch(100)
    for sub in subs:
      sub.delete()
    # Insert new subscription instance
    sub_info = SubscriptionInfo()
    sub_info.subscription_id = subscription_id
    sub_info.hit_count = 0
    sub_info.user_id = user_id
    sub_info.put()

  def __Render(self, user):
    self.response.out.write(HEADER1)
    self.response.out.write("<h2>Matcher demo welcomes %s! "
                            "<a href=\"%s\">sign out</a></h2>" %
                            (user.nickname(), users.create_logout_url("/")))
    self.response.out.write(HEADER2)
    subscriptions = matcher.list_subscriptions(MatcherDocument,
                                               topic = user.user_id())
    subscription_prefix = 'subscription_'
    for subscription_suffix in ['a', 'b', 'c', 'd']:
      subscription_id = subscription_prefix + subscription_suffix
      query = ''
      expiration_time = 0
      state = 'UNREGISTERED'
      error = ''
      for sub in subscriptions:
        if sub[0] == subscription_id:
          state_code = 0
          (sub_id, query, expiration_time, state_code, error) = sub
          state = matcher.matcher_pb.SubscriptionRecord.State_Name(state_code)

      hit_count = self.__GetSubscriptionInfo(subscription_id, user.user_id())
      self.response.out.write("""
        <div class="form"><form action="/" method="POST">
          %s <input type="text" name="query" value="%s" size=128><br>
          Expiration time <input type="text" value="%s" disabled="disabled">
          State <input type="text" value="%s" disabled="disabled">
          Error <input type="text" value="%s" disabled="disabled"><br>
          Hits  <input type="text" value="%d" disabled="disabled"><br>
          <input type="submit" name="subscribe" value="Subscribe">
          <input type="submit" name="unsubscribe" value="Unsubscribe">
          <input type="hidden" name="subscription_id" value="%s">
        </form></div>""" % (subscription_id,
                            cgi.escape(query),
                            time.ctime(expiration_time),
                            state,
                            error,
                            hit_count,
                            subscription_id))
    self.response.out.write(FOOTER)


def main(argv):
  application = webapp.WSGIApplication([('/', MatcherDemo),
                                        ('/_ah/matcher', IncHitCounter)],
                                       debug=True)
  util.run_wsgi_app(application)


HEADER1 = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<title>Matcher demo</title>
<style type="text/css">
body {
  margin: 15px;
  font-family:sans-serif;
}
div.form {
  margin: 10px;
  padding: 10px;
  border: 1px solid Navy;
  width: auto;
  background-color: LightSteelBlue;
  font-family:sans-serif;
}
pre {
  margin-left: 1.0em;
  font-family: Courier New, Courier, mono;
  color: #09571b;
}
</style>
</head>
<body>
<div id="main">
<div id="body">
"""

HEADER2 = """
This demo allows you to experiment with the Matcher Appengine API using
a small number subscriptions and a simple document.
You can enter queries into the subscription_* fields and press the 'Subscribe'
button to register them.
Then enter some values into the document that may match these subscriptions
and press the 'Match' button. Subscriptions that match will have their hit count
incremented once the match results arrive from the task queue.
Press the refresh button to see the latest counts.
<div class="form">
<form action="/" method="POST">
<table>
<tr><td>field_text_a:</td>
    <td><TEXTAREA name="field_text_a" rows="4" cols="80"></TEXTAREA></td>
</tr>
<tr><td>field_text_b:</td>
    <td><TEXTAREA name="field_text_b" rows="4" cols="80"></TEXTAREA></td>
</tr>
<tr><td>field_int32_a:</td>
    <td><input type="text" name="field_int32_a" size=16 value="0"></td>
</tr>
<tr><td>field_int32_b:</td>
    <td><input type="text" name="field_int32_b" size=16 value="0"></td>
</tr>
<tr><td>field_float_a:</td>
    <td><input type="text" name="field_float_a" size=16 value="0.0"></td>
</tr>
<tr><td>field_float_b:</td>
    <td><input type="text" name="field_float_b" size=16 value="0.0"></td>
</tr>
<tr><td><input type="submit" name="match" value="Match"></td>
</tr>
</table>
</form>
</div>
<form>
<input type=button value="Refresh subscription state"
 onClick="window.location.reload()">
</form>
"""

FOOTER = """
</div></div>
<div>
<h2>Subscription query language summary</h2>
<h3>Numeric comparison operators</h3>
The > >=, =, <= and < numeric operators are available. For example: <br>
<pre>field_int32_a > 20</pre>

<h3>Text operators</h3>
Text fields can be matched for the occurance of a word or phrase anywhere in the
content of the field. For example:
<pre>field_text_a:horse</pre>
<pre>field_text_a:"horse riding"</pre>

<h3>Logical operators</h3>
Predicates can be combined with the NOT, OR and AND operators.
They can also be grouped using parantheses.
For example: <br>
<pre>field_int32_a > 20 AND field_int32_b = 10</pre>
<pre>(field_int32_a > 20 AND field_int32_b = 10) OR field_text_a:fox</pre>
</div>
</body>
</html>
"""

if __name__ == '__main__':
  main(sys.argv)
