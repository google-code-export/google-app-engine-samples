<%@ include file="header.jsp" %>

<h3>Oops &ndash; a Google Data session token could not be found for your account.</h3>

<p>
  In order to see your data, you must first authorize access to your personal feeds. Start this process by choosing a service from the list below:
</p>

<ul>
  <li><a href="<c:out value="${model.request_url}"/>">Google Documents</a></li>
</ul>

<c:if test="${empty model.user}">
  <p><strong>Note:</strong> Because you are not signed in, you will have to repeat this process every time you access this page. If you <a href="<c:out value="${model.login_url}"/>">sign in</a> first, your session token will be persisted across requests.</p>
</c:if>

<%@ include file="footer.jsp" %>