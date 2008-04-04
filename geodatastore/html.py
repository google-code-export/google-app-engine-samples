#!/usr/bin/python2.5
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""One-line documentation for html module.

A detailed description of html.
"""

__author__ = 'pamelafox@google.com (Pamela Fox)'

import wsgiref.handlers
import os

from google.appengine.ext.webapp import template
from google.appengine.ext import webapp
from google.appengine.api import users

class BasePage(webapp.RequestHandler):
  def get(self):
    self.render(self.getTemplateFilename(), self.getTemplateValues())

  def getTemplateValues(self):
    if users.GetCurrentUser():
      login_url = users.CreateLogoutURL(self.request.uri)
      login_linktext = 'Logout'
      login_name = users.GetCurrentUser().email()
    else:
      login_url = users.CreateLoginURL(self.request.uri)
      login_linktext = 'Login'
      login_name = 'Not logged in'

    template_values = {
      'login': {
        'url': login_url,
        'linktext': login_linktext,
        'name': login_name
      }
    }
    return template_values

  def getTemplateFilename(self):
    return "base.html"

  def render(self, filename, template_values):
    path = os.path.join(os.path.dirname(__file__), 'templates', filename)
    self.response.out.write(template.render(path, template_values))

##
# Page class for the personal view
class AdminPage(BasePage):
  ##
  # Returns a dictionary with values for the template
  def getTemplateValues(self):
    template_values = BasePage.getTemplateValues(self)
    return template_values

  ##
  # Returns the filename of the template to use when
  # rendering
  def getTemplateFilename(self): 
    return "admin.html"

##
# Page class for the personal view
class QueryPage(BasePage):
  ##
  # Returns a dictionary with values for the template
  def getTemplateValues(self):
    template_values = BasePage.getTemplateValues(self)
    return template_values

  ##
  # Returns the filename of the template to use when
  # rendering
  def getTemplateFilename(self): 
    return "query.html"

##
# Page class for the personal view
class MapDisplayPage(BasePage):
  ##
  # Returns a dictionary with values for the template
  def getTemplateValues(self):
    template_values = BasePage.getTemplateValues(self)
    return template_values

  ##
  # Returns the filename of the template to use when
  # rendering
  def getTemplateFilename(self): 
    return "mapdisplay.html"

application = webapp.WSGIApplication(
    [('/', AdminPage),
     ('/admin', AdminPage),
     ('/mapdisplay', MapDisplayPage),
     ('/query', QueryPage)],debug=True)
wsgiref.handlers.CGIHandler().run(application)
