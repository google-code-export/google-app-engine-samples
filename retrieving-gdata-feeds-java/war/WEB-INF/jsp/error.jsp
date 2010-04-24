<%@ include file="header.jsp" %>

<h3>Oops &ndash; an error occurred while processing your request.</h3>

<p>
  Error code <c:out value="${model.error_code}"/>: <c:out value="${model.error_text}"/>
</p>

<%@ include file="footer.jsp" %>