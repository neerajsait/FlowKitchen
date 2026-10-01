// login-customer.js
// ZAP authentication script for FoodPilot customer accounts.
// Matches POST /api/auth/login with body {email, password}.

function authenticate(helper, paramsValues, credentials) {
    var msg = helper.prepareMessage();
    var uri = new org.apache.commons.httpclient.URI(
        paramsValues.get("Target URL") + "/api/auth/login", false);

    msg.getRequestHeader().setURI(uri);
    msg.getRequestHeader().setMethod("POST");
    msg.getRequestHeader().setHeader("Content-Type", "application/json");

    var body = JSON.stringify({
        email: credentials.getParam("username"),
        password: credentials.getParam("password")
    });
    msg.setRequestBody(body);
    msg.getRequestHeader().setContentLength(msg.getRequestBody().length());

    helper.sendAndReceive(msg, false);
    return msg;
}

function getRequiredParamsNames() {
    return [];
}

function getOptionalParamsNames() {
    return [];
}

function getCredentialsParamsNames() {
    return ["username", "password"];
}