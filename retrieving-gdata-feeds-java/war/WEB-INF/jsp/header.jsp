<%@ page isELIgnored="false" %>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %>

<html>
  <head>
    <title>Google Data Feed Fetcher: read Google Data API Atom feeds</title>
    <style type="text/css">
      strong {
        color: red;
      }
    </style>
  </head>
  <body>
    <c:choose>
      <c:when test="${empty model.user}">
        <a href="<c:out value="${model.login_url}"/>">Sign in</a>
      </c:when>
      <c:otherwise>
        <a href="<c:out value="${model.logout_url}"/>">Sign out</a>
      </c:otherwise>
    </c:choose>