from owrx.controllers.template import WebpageController
from owrx.config import Config
from urllib.parse import parse_qs, urlencode
from uuid import uuid4
from http.cookies import SimpleCookie
from owrx.users import UserList
from datetime import datetime, timedelta

import logging

logger = logging.getLogger(__name__)


class SessionStorage(object):
    sharedInstance = None
    sessionLifetime = timedelta(hours=6)

    @staticmethod
    def getSharedInstance():
        if SessionStorage.sharedInstance is None:
            SessionStorage.sharedInstance = SessionStorage()
        return SessionStorage.sharedInstance

    def __init__(self):
        self.sessions = {}

    def generateKey(self):
        return str(uuid4())

    def startSession(self, data):
        key = self.generateKey()
        self.updateSession(key, data)
        return key

    def getSession(self, key):
        if key not in self.sessions:
            return None
        expires, data = self.sessions[key]
        if expires < datetime.utcnow():
            del self.sessions[key]
            return None
        return data

    def updateSession(self, key, data):
        expires = datetime.utcnow() + SessionStorage.sessionLifetime
        self.sessions[key] = expires, data

    def prolongSession(self, key):
        data = self.getSession(key)
        if data is None:
            raise KeyError("Invalid session key")
        self.updateSession(key, data)

    def dropSession(self, key):
        if key in self.sessions:
            del self.sessions[key]


class SessionController(WebpageController):
    def loginAction(self):
        if self.request.local or Config.get()["allow_remote_config"]:
            self.serve_template("login.html", **self.template_variables())
        else:
            self.send_response("access forbidden", code=403)

    def processLoginAction(self):
        if not self.request.local and not Config.get()["allow_remote_config"]:
            self.send_response("access forbidden", code=403)
            return

        data = parse_qs(self.get_body().decode("utf-8"))
        data = {k: v[0] for k, v in data.items()}
        userlist = UserList.getSharedInstance()
        if "user" in data and "password" in data:
            if data["user"] in userlist:
                user = userlist[data["user"]]
                if user.is_enabled() and user.password.is_valid(data["password"]):
                    key = SessionStorage.getSharedInstance().startSession({"user": user.name})
                    cookie = SimpleCookie()
                    cookie["owrx-session"] = key
                    cookie["owrx-session"]["httponly"] = True
                    cookie["owrx-session"]["samesite"] = "Lax"
                    target = self.request.query["ref"][0] if "ref" in self.request.query else "/settings"
                    if user.must_change_password:
                        # force password change
                        target = "/pwchange?{0}".format(urlencode({"ref": target}))
                    elif not target.startswith("/"):
                        # prevent redirecting to external URL
                        target = "/settings"
                    self.set_response_cookies(cookie)
                    self.send_redirect(target)
                    return
        target = "{}login?{}".format(self.get_document_root(), urlencode({"ref": self.request.query["ref"][0]}))
        self.send_redirect(target)

    def logoutAction(self):
        if not self.request.local and not Config.get()["allow_remote_config"]:
            self.send_response("access forbidden", code=403)
            return
        # invalidate the session on the server side
        if "owrx-session" in self.request.cookies:
            key = self.request.cookies["owrx-session"].value
            SessionStorage.getSharedInstance().dropSession(key)
        # expire the session cookie in the browser
        cookie = SimpleCookie()
        cookie["owrx-session"] = ""
        cookie["owrx-session"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        cookie["owrx-session"]["max-age"] = 0
        self.set_response_cookies(cookie)
        # redirect back to login page
        self.send_redirect("/login")
