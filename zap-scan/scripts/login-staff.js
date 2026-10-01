// login-staff.js
// ZAP authentication script for FoodPilot staff accounts.
// Matches POST /api/auth/login with body {staff_code, pin}.
// "username" credential param holds the staff_code, "password" holds the PIN.

function authenticate(helper, paramsValues, credentials) {
    var msg = helper.prepareMessage();
    var uri = new org.apache.commons.httpclient.URI(
        paramsValues.get("Target URL") + "/api/auth/login", false);

    msg.getRequestHeader().setURI(uri);
    msg.getRequestHeader().setMethod("POST");
    msg.getRequestHeader().setHeader("Content-Type", "application/json");

    var body = JSON.stringify({
        staff_code: credentials.getParam("username"),
        pin: credentials.getParam("password")
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