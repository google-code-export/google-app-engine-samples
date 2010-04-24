package com.google.appengine.demo.web;

import com.google.appengine.api.users.User;
import com.google.appengine.api.users.UserService;
import com.google.appengine.api.users.UserServiceFactory;
import com.google.appengine.demo.repo.TokenStore;
import com.google.gdata.client.GoogleService;
import com.google.gdata.client.Service;
import com.google.gdata.client.docs.DocsService;
import com.google.gdata.client.http.AuthSubUtil;
import com.google.gdata.util.AuthenticationException;
import com.google.gdata.util.ServiceException;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URL;
import java.security.GeneralSecurityException;
import java.util.HashMap;
import java.util.Map;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

public class FetcherServlet extends HttpServlet {

  private static UserService userService = UserServiceFactory.getUserService();

  @Override
  public void service(HttpServletRequest request, HttpServletResponse response)
      throws ServletException, IOException {
    String sessionToken = null;

    // Initialize a client to talk to Google Data API services.
    DocsService client = new DocsService("google-feedfetcher-v1");

    // If a user is currently signed in to the application, attempt to retrieve
    // a previously stored session token associated with that account from App
    // Engine's datastore.
    if (userService.isUserLoggedIn()) {
      User user = userService.getCurrentUser();
      sessionToken = TokenStore.getToken(user.getEmail());
    }

    // If sessionToken is null, check for a single-use token in the query
    // string; if found, exchange this token for a session token using the
    // client library.
    if (sessionToken == null) {
      try {
        // Find the AuthSub token and upgrade it to a session token.
        String authToken = AuthSubUtil.getTokenFromReply(
            request.getQueryString());

        // Upgrade the single-use token to a multi-use session token.
        sessionToken = AuthSubUtil.exchangeForSessionToken(authToken, null);
      } catch (AuthenticationException e) {
        //...
      } catch (GeneralSecurityException e) {
        //...
      } catch (NullPointerException e) {
        // Ignore
      }
    }

    if (sessionToken != null) {
      // If there is a current user, store the token in the datastore and
      // associate it with the current user's email address.
      if (userService.isUserLoggedIn()) {
        User user = userService.getCurrentUser();
        TokenStore.addToken(user.getEmail(), sessionToken);
      }

      // Set the session token as a field of the Service object. Since a new
      // Service object is created with each get call, we don't need to
      // worry about the anonymous token being used by other users.
      client.setAuthSubToken(sessionToken);

      // Fetch and write feed data to response
      String feedUrl = request.getParameter("feedUrl");
      if (feedUrl == null) {
        feedUrl = "https://docs.google.com/feeds/default/private/full";
      }

      // Attempt to fetch the feed; if successful, send the feed as text to
      // display to the user, otherwise send the error code/text.
      try {
        String feed = fetchFeed(client, feedUrl);
        writeAuthenticatedResponse(request, response, feedUrl, feed);
      } catch (ServiceException e) {
        String errorText = e.getCodeName();
        Integer errorCode = e.getHttpErrorCodeOverride();
        writeErrorResponse(request, response, errorCode, errorText);
      }
    } else {
      // If no session token is set, allow users to authorize this sample app
      // to fetch personal Google Data feeds by directing them to an
      // authorization page.

      // Generate AuthSub URL
      String nextUrl = request.getRequestURL().toString();
      String requestUrl = AuthSubUtil.getRequestUrl(nextUrl,
          "https://docs.google.com/feeds/", false, true);

      // Send the AuthSub URL to display to the user as a link.
      writeUnauthenticatedResponse(request, response, requestUrl);
    }
  }

  /**
   * Fetches and returns the specified feed from the specified service.
   *
   * @throws ServiceException if the passed client is not set up correctly or
   *                          an error is thrown by the Google Data service in
   *                          response to the fetch attempt
   * @throws IOException      if an I/O error prevents a connection from being
   *                          opened or otherwise causes request transmission
   *                          to fail
   */
  static String fetchFeed(GoogleService client, String feedUrl) throws
      ServiceException, IOException {
    if (feedUrl == null) {
      return null;
    }

    // Attempt to fetch the feed.
    Service.GDataRequest feedRequest = client.createFeedRequest(
        new URL(feedUrl));
    feedRequest.execute();

    return streamToString(feedRequest.getResponseStream());
  }

  /**
   * Reads the character data in the specified InputStream into a new String
   * which is returned once all the data is read.
   *
   * @throws IOException
   */
  static String streamToString(InputStream stream) throws IOException {
    if (stream == null) {
      return null;
    }

    StringBuilder builder = new StringBuilder();

    try {
      BufferedReader reader = new BufferedReader(
          new InputStreamReader(stream, "UTF-8"));

      String line;
      while ((line = reader.readLine()) != null) {
        builder.append(line).append("\n");
      }
    } finally {
      stream.close();
    }

    return builder.toString();
  }

  private void writeAuthenticatedResponse(HttpServletRequest request,
      HttpServletResponse response, String feedUrl, String feed) throws
      ServletException, IOException {
    Map<String, Object> model = new HashMap<String, Object>();
    model.put("feedUrl", feedUrl);
    model.put("feed", feed);

    String path = "/WEB-INF/jsp/authenticated.jsp";
    writeResponse(request, response, path, model);
  }

  private void writeUnauthenticatedResponse(HttpServletRequest request,
      HttpServletResponse response, String requestUrl) throws ServletException,
      IOException {
    Map<String, Object> model = new HashMap<String, Object>();
    model.put("request_url", requestUrl);

    String path = "/WEB-INF/jsp/unauthenticated.jsp";
    writeResponse(request, response, path, model);
  }

  private void writeErrorResponse(HttpServletRequest request,
      HttpServletResponse response, Integer errorCode, String errorText) throws
      ServletException, IOException {
    Map<String, Object> model = new HashMap<String, Object>();
    model.put("error_code", errorCode);
    model.put("error_text", errorText);

    String path = "/WEB-INF/jsp/error.jsp";
    writeResponse(request, response, path, model);
  }

  private void writeResponse(HttpServletRequest request,
      HttpServletResponse response, String path, Map<String, Object> model)
      throws ServletException, IOException{
    if (model == null) {
      model = new HashMap<String, Object>();
    }

    String nextUrl = request.getRequestURL().toString();
    model.put("logout_url", userService.createLogoutURL(nextUrl));
    model.put("login_url", userService.createLoginURL(nextUrl));
    model.put("user", userService.getCurrentUser());

    request.setAttribute("model", model);
    getServletContext().getRequestDispatcher(path).forward(request, response);
  }
}
