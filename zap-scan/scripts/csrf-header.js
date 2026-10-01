function sendingRequest(msg, initiator, helper) {
  var cookies = msg.getRequestHeader().getHttpCookies();
  for (var i = 0; i < cookies.size(); i++) {
    var c = cookies.get(i);
    if (c.getName() == "csrf_access_token") {
      msg.getRequestHeader().setHeader("X-CSRF-TOKEN", c.getValue());
    }
  }
}
function responseReceived(msg, initiator, helper) {}