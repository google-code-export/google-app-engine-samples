import java.io.IOException;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@SuppressWarnings("serial")
public class V1Servlet extends HttpServlet {
  @Override
  public void doGet(HttpServletRequest req, HttpServletResponse resp)
      throws IOException {
    resp.setContentType("text/plain");

    String action = req.getParameter("action");

    ShardedCounterV1 counter = new ShardedCounterV1();

    if ("increment".equals(action)) {
      counter.increment();
      resp.getWriter().println("Counter incremented.");
    } else {
      resp.getWriter().println("getCount() -> " + counter.getCount());
    }
  }
}
