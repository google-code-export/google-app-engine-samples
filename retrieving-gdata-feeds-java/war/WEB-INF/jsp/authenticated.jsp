<%@ include file="header.jsp" %>

<h3>Congratulations &ndash; a Google Data session token was found for your account!</h3>

<p>
  A Google Data session token for your account is available, so this application can access your personal <a href="<c:out value="${model.feedUrl}"/>">feed</a>, displayed below:
</p>

<p style="font-family:Courier New, monospace; white-space:nowrap;">
  <c:out value="${model.feed}" escapeXml="true"/>
</p>

<%@ include file="footer.jsp" %>