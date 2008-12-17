#!/usr/bin/env python

import datetime
import hashlib
import os
import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp.util import login_required


class Contributor (db.Model):
  count = db.IntegerProperty(default=0)


class Suggestion(db.Model):
  suggestion = db.StringProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  when = db.StringProperty()
  
  
PAGESIZE = 5


def _unique_user(user):
  """
  Creates a unique string by using an increasing
  counter sharded per user. The resulting string
  is hashed to keep the users email address private.
  """
  email = user.email()
 
  def txn():
    contributor = Contributor.get_by_key_name(email)
    if contributor == None:
      contributor = Contributor(key_name=email) 
    contributor.count += 1
    contributor.put()
    return contributor.count

  count = db.run_in_transaction(txn)

  return hashlib.md5(email + '|' + str(count)).hexdigest()
  
def whenfromcreated(created):
  return created.isoformat()[0:19] + '|' + _unique_user(users.GetCurrentUser())

class SuggestionHandler(webapp.RequestHandler):

  @login_required
  def get(self):
    offset = self.request.get('offset')
    next = None
    if offset:
      suggestions = Suggestion.all().order('-when').filter('when <=', offset).fetch(PAGESIZE+1)
    else:
      suggestions = Suggestion.all().order('-when').fetch(PAGESIZE+1)
    if len(suggestions) == PAGESIZE+1:
      next = suggestions[-1].when
      suggestions = suggestions[:PAGESIZE]
      
    template_values = {'next': next, 'suggestions': suggestions}    
    template_file = os.path.join(os.path.dirname(__file__), 'suggestion.html')
    self.response.out.write(template.render(template_file, template_values))

  def post(self):
    now = datetime.datetime.now()
    when = whenfromcreated(now)
    #now.isoformat()[0:19] + '|' + _unique_user(users.GetCurrentUser())
    s = Suggestion(suggestion = self.request.get('suggestion'), when=when, created=now)
        
    s.put()
    self.redirect('/unique/')

class SuggestionPopulate(webapp.RequestHandler):
  def post(self):
    now = datetime.datetime.now()
    for i in range(6):
      s = Suggestion(suggestion = "Suggestion %d" % i, created = now, when = whenfromcreated(now))
      s.put()
    self.redirect('/unique/')
        


def main():
  application = webapp.WSGIApplication([
    ('/unique/pop/', SuggestionPopulate),
    ('/unique/', SuggestionHandler)
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
  

