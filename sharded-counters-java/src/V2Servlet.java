import java.io.IOException;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@SuppressWarnings("serial")
public class V2Servlet extends HttpServlet {
  @Override
  public void doGet(HttpServletRequest req, HttpServletResponse resp)
      throws IOException {
    resp.setContentType("text/plain");

    String counterName = req.getParameter("name");
    String action = req.getParameter("action");
    String shards = req.getParameter("shards");

    ShardedCounterV2 counter = new ShardedCounterV2(counterName);

    if ("increment".equals(action)) {
      counter.increment();
      resp.getWriter().println("Counter incremented.");
    } else if ("increase_shards".equals(action)) {
      int inc = Integer.valueOf(shards);
      counter.addShards(inc);
      resp.getWriter().println("Shard count increased by " + inc + ".");
    } else {
      resp.getWriter().println("getCount() -> " + counter.getCount());
    }
  }
}
