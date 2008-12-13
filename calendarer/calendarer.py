import os
import datetime
import logging
from google.appengine.ext.webapp import template
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import users
import atom
import gdata.service
import gdata.auth
import gdata.alt.appengine
import gdata.calendar
import gdata.calendar.service


__author__ = 'j.s@google.com (Jeff Scudder)'


port = os.environ['SERVER_PORT']
if port and port != '80':
  HOST_NAME = '%s:%s' % (os.environ['SERVER_NAME'], port)
else:
  HOST_NAME = os.environ['SERVER_NAME']


class Event(db.Model):
  title = db.StringProperty(required=True)
  description = db.TextProperty()
  time = db.DateTimeProperty()
  location = db.TextProperty()
  creator = db.UserProperty()
  edit_link = db.TextProperty()
  gcal_event_link = db.TextProperty()
  gcal_event_xml = db.TextProperty()


class Attendee(db.Model):
  email = db.StringProperty()
  event = db.ReferenceProperty(Event)


class BasePage(webapp.RequestHandler):
  title = ''
  
  def write_page_header(self):
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write('<html><head><title>%s</title>'
    '<link href="static/invitations.css" rel="stylesheet" type="text/css"/>'
    '</head><body><div id="main">' % (
        self.title,))
    self.write_signin_links()
  
  def write_signin_links(self):
    if users.get_current_user():
      template_values = {
          'signed_in': True,
          'user_link': users.create_logout_url('/')}
    else:
      template_values = {
          'signed_in': False,
          'user_link': users.create_login_url('/events')}
    path = os.path.join(os.path.dirname(__file__), 'templates')
    path = os.path.join(path, 'signin.html')
    self.response.out.write(template.render(path, template_values))
  
  def write_page_footer(self):
    self.response.out.write('</div></body></html>')


class StartPage(BasePage):
  title = 'Welcome!'

  def get(self):
    self.write_page_header()
    template_values = {'sign_in': users.create_login_url('/events')}
    path = os.path.join(os.path.dirname(__file__), 'templates')
    path = os.path.join(path, 'start.html')
    self.response.out.write(template.render(path, template_values))
    self.write_page_footer()


class EventsPage(BasePage):
  title = 'Your events.'
  
  def __init__(self):
    # Create a Google Calendar client to talk to the Google Calendar service.
    self.calendar_client = gdata.calendar.service.CalendarService()
    # Modify the client to search for auth tokens in the datastore and use
    # urlfetch instead of httplib to make HTTP requests to Google Calendar.
    gdata.alt.appengine.run_on_appengine(self.calendar_client)

  def get(self):
    """Displays the events the user has created or is invited to."""
    self.write_page_header()
    
    # Find all events which this user has created, and find events which this
    # user has been invited to.
    invited_events = []
    owned_events = []
    token_request_url = None
    
    # Find an AuthSub token in the current URL if we arrived at this page from
    # an AuthSub redirect.
    auth_token = gdata.auth.extract_auth_sub_token_from_url(self.request.uri)
    if auth_token:
      self.calendar_client.SetAuthSubToken(
          self.calendar_client.upgrade_to_session_token(auth_token))
    
    # Check to see if the app has permission to write to the user's 
    # Google Calendar.
    if not isinstance(self.calendar_client.token_store.find_token(
            'http://www.google.com/calendar/feeds/'),
        gdata.auth.AuthSubToken):
      token_request_url = gdata.auth.generate_auth_sub_url(self.request.uri,
         ('http://www.google.com/calendar/feeds/',))


    query_time = self.request.get('start_time')
    # TODO handle times provided in the URL.
    if not query_time:
      query_time = datetime.datetime.now()
    
    # Find the events which were created by this user, and those which the user
    # is invited to.
    if users.get_current_user():
      owned_query = Event.gql('WHERE creator = :1 ORDER BY time', 
          users.get_current_user())
      owned_events = owned_query.fetch(5)
      
      invited_query = Attendee.gql('WHERE email = :1', 
          users.get_current_user().email())
      for invitation in invited_query.fetch(5):
        try:
          invited_events.append(invitation.event)
        except db.Error, message:
          if message[0] == 'ReferenceProperty failed to be resolved':
            # The invitee has an invitation to an event which no longer exists.
            pass
          else:
            raise

    template_values = {
        'token_request_url': token_request_url,
        'owned_events': owned_events,
        'invited_events': invited_events,}
    
    # Display the events.
    path = os.path.join(os.path.dirname(__file__), 'templates')
    path = os.path.join(path, 'events.html')
    self.response.out.write(template.render(path, template_values))
    self.write_page_footer()
  
  def post(self):
    """Adds an event to Google Calendar."""
    event_id = self.request.get('event_id')
    
    # Fetch the event from the datastore and make sure that the current user
    # is an owner since only event owners are allowed to create a calendar 
    # event.
    event = Event.get_by_id(long(event_id))
    
    if users.get_current_user() == event.creator:
      # Create a new Google Calendar event.
      event_entry = gdata.calendar.CalendarEventEntry()
      event_entry.title = atom.Title(text=event.title)
      event_entry.content = atom.Content(text=event.description)
      start_time = '%s.000Z' % event.time.isoformat()
      event_entry.when.append(gdata.calendar.When(start_time=start_time))
      event_entry.where.append(
          gdata.calendar.Where(value_string=event.location))
      # Add a who element for each attendee.
      attendee_list = event.attendee_set
      if attendee_list:
        for attendee in attendee_list:
          new_attendee = gdata.calendar.Who()
          new_attendee.email = attendee.email
          event_entry.who.append(new_attendee)
      
      # Send the event information to Google Calendar and receive a 
      # Google Calendar event.
      try:
        cal_event = self.calendar_client.InsertEvent(event_entry, 
            'http://www.google.com/calendar/feeds/default/private/full')
        edit_link = cal_event.GetEditLink()
        if edit_link and edit_link.href:
          # Add the edit link to the Calendar event to use for making changes.
          event.edit_link = edit_link.href
        alternate_link = cal_event.GetHtmlLink()
        if alternate_link and alternate_link.href:
          # Add a link to the event in the Google Calendar HTML web UI.
          event.gcal_event_link = alternate_link.href
          event.gcal_event_xml = str(cal_event)
        event.put()
      # If adding the event to Google Calendar failed due to a bad auth token,
      # remove the user's auth tokens from the datastore so that they can 
      # request a new one. 
      except gdata.service.RequestError, request_exception:
        request_error = request_exception[0]
        if request_error['status'] == 401 or request_error['status'] == 403:
          gdata.alt.appengine.save_auth_tokens({})
        # If the request failure was not due to a bad auth token, reraise the
        # exception for handling elsewhere.
        else:
          raise
    else:
      self.response.out.write('I\'m sorry, you don\'t have permission to add'
                              ' this event to Google Calendar.')
    
    # Display the list of events also as if this were a get.
    self.get()


class EditEvent(EventsPage):

  def get(self):
    self.write_page_header()
    event_id = self.request.get('event_id')
    template_values = {'event_id': event_id, 
                       'event': Event.get_by_id(int(event_id))}
    path = os.path.join(os.path.dirname(__file__), 'templates')
    path = os.path.join(path, 'edit.html')
    self.response.out.write(template.render(path, template_values))
    self.write_page_footer()

  def post(self):
    """Changes the details of an event and updates Google Calendar."""
    self.write_page_header()
    event_id = self.request.get('event_id')
    if event_id:
      event = Event.get_by_id(int(event_id))
      if event and users.get_current_user() == event.creator:
        # If this Event is in Google Calendar, send an update to Google Calendar
        if event.edit_link and event.gcal_event_xml:
          # Reconstruct the Calendar entry, and update the information.
          cal_event = gdata.calendar.CalendarEventEntryFromString(
              str(event.gcal_event_xml))
          # Modify the event's Google Calendar entry
          cal_event.title = atom.Title(text=self.request.get('name'))
          cal_event.content = atom.Content(text=self.request.get('description'))
          start_time = '%s.000Z' % datetime.datetime.strptime(
              self.request.get('datetimestamp'), '%d/%m/%Y %H:%M').isoformat()
          cal_event.when = [gdata.calendar.When(start_time=start_time)]
          cal_event.where = [gdata.calendar.Where(
              value_string=self.request.get('location'))]
          # Add a who element for each attendee.
          if self.request.get('attendees'):
            attendee_list = self.request.get('attendees').split(',')
            if attendee_list:
              cal_event.who = []
              for attendee in attendee_list:
                cal_event.who.append(gdata.calendar.Who(email=attendee))
          # Send the updated Google Calendar entry to the Google server.
          try:
            updated_entry = self.calendar_client.UpdateEvent(str(event.edit_link), 
                                                        cal_event)
            # Change the properties of the Event object.
            event.edit_link = updated_entry.GetEditLink().href
            event.gcal_event_xml = str(updated_entry)
            event.title = self.request.get('name')
            event.time = datetime.datetime.strptime(
                self.request.get('datetimestamp'), '%d/%m/%Y %H:%M')
            event.description = self.request.get('description')
            event.location = self.request.get('location')
            # TODO: update the attendees list.
            event.put()
            self.response.out.write('Done')
          except gdata.service.RequestError, request_exception:
            request_error = request_exception[0]
            # If the update failed because someone changed the Google Calendar
            # event since creation, update the event and ask the user to
            # repeat the edit.
            if request_error['status'] == 409:
              # Get the updated event information from Google Calendar.
              updated_entry = gdata.calendar.CalendarEventEntryFromString(
                  request_error['body'])
              # Change the properties of the Event object so that the next edit
              # will begin with the new values.
              event.edit_link = updated_entry.GetEditLink().href
              event.gcal_event_xml = request_error['body']
              event.title = updated_entry.title.text
              # TODO: adjust the time
              logging.debug('New calendar time is: %s' % updated_entry.when[0].start_time)
              event.description = updated_entry.content.text
              event.location = updated_entry.where[0].value_string
              # TODO: update the attendees
              event.put()
              self.response.out.write('Could not update because the event '
                                      'has been edited in Google Calendar. '
                                      'Event details have now been updated '
                                      'with the latest values from Google '
                                      'Calendar. Try again.')
            # If the request failure was not due to an optimistic concurrency
            # conflict reraise exception for handling elsewhere.
            else:
              raise
        else:
          # This event is not in Google Calendar, so just update the datastore.
          event.title = self.request.get('name')
          # Take the time string passing in by JavaScript in the
          # form and convert to a datetime object.
          event.time = datetime.datetime.strptime(
              self.request.get('datetimestamp'), '%d/%m/%Y %H:%M')
          event.description = self.request.get('description')
          event.location = self.request.get('location')
          event.put()
          # TODO: edit the attendees.
    self.write_page_footer()


class DeleteEvent(EventsPage):

  def get(self):
    self.write_page_header()
    event_id = self.request.get('event_id')
    self.response.out.write('Are you sure?')
    self.response.out.write('<form action="/delete_event" method="post">'
        '<input type="hidden" name="event_id" value="%s"/>'
        '<input type="submit" value="Yes, Delete this event."/></form>' % (
            event_id))
    self.write_page_footer()

  def post(self):
    logging.debug('Deleting the event!: %s' % self.request.get('event_id'))
    self.write_page_header()
    event_id = self.request.get('event_id')
    if event_id:
      event = Event.get_by_id(int(event_id))
      if event and users.get_current_user() == event.creator:
        # If we have an edit link, delete the event from Google Calendar.
        if event.edit_link:
          self.calendar_client.DeleteEvent(str(event.edit_link))
        # Delete the event object from the datastore.
        event.delete()
    self.response.out.write('Deleted event number %s' % event_id)
    self.write_page_footer()


class CreateEvent(BasePage):
  title = 'Create!'
  
  def get(self):
    """Show the event creation form"""
    self.write_page_header()
    template_values = {}
    path = os.path.join(os.path.dirname(__file__), 'templates')
    path = os.path.join(path, 'create.html')
    self.response.out.write(template.render(path, template_values))
    self.write_page_footer()
  
  def post(self):
    """Create an event and store it in the datastore.
    
    This event does not exist in Google Calendar. The event creator can add it
    to Google Calendar on the 'events' page.
    """
    self.write_page_header()
    
    # Create an event in the datastore.
    new_event = Event(title=self.request.get('name'), 
                      creator=users.get_current_user(),
                      # Take the time string passing in by JavaScript in the
                      # form and convert to a datetime object.
                      time=datetime.datetime.strptime(
                          self.request.get('datetimestamp'), '%d/%m/%Y %H:%M'),
                      description=self.request.get('description'),
                      location=self.request.get('location'))
    new_event.put()
    
    # Associate each of the attendees with the event in the datastore.
    attendee_list = []
    if self.request.get('attendees'):
      attendee_list = self.request.get('attendees').split(',')
      if attendee_list:
        # TODO: perform one put with a list of Attendee objects.
        for attendee in attendee_list:
          new_attendee = Attendee(email=attendee.strip(), event=new_event)
          new_attendee.put()
          
    template_values = {
        'name': new_event.title,
        'description': new_event.description,
        'time': new_event.time.strftime('%x %X %Z'),
        'location': new_event.location
        }
    path = os.path.join(os.path.dirname(__file__), 'templates')
    path = os.path.join(path, 'created.html')
    self.response.out.write(template.render(path, template_values))
    self.write_page_footer()


application = webapp.WSGIApplication([('/', StartPage),
                                      ('/events', EventsPage),
                                      ('/edit_event', EditEvent),
                                      ('/delete_event', DeleteEvent),
                                      ('/create', CreateEvent)],
                                     debug=True)


def main():
  run_wsgi_app(application)


if __name__ == "__main__":
  main()
