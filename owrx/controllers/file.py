from owrx.controllers.admin import Authentication
from owrx.controllers.template import WebpageController
from owrx.controllers.assets import AssetsController
from owrx.storage import Storage

import json
import re
import os
import logging

logger = logging.getLogger(__name__)


class FileController(AssetsController):
    def getFilePath(self, file):
        return Storage.getFilePath(file)


class FilesController(WebpageController):
    def __init__(self, handler, request, options):
        self.authentication = Authentication()
        self.user  = self.authentication.getUser(request)
        self.isimg = re.compile(r'.*\.(png|bmp|gif|jpg)$')
        self.issnd = re.compile(r'.*\.(mp3|wav)$')
        super().__init__(handler, request, options)

    def isAuthorized(self):
        return self.user is not None and self.user.is_enabled() and not self.user.must_change_password

    def template_variables(self):
        # We need to know if the user is authorized to delete files
        admin = self.isAuthorized()
        files = Storage.getSharedInstance().getStoredFiles()
        rows  = ""

        for i in range(len(files)):
            # Start a row
            if i % 3 == 0:
                rows += '<tr>\n'
            # Show images as they are, show document icon for the rest
            if self.isimg.match(files[i]):
                shot = "files/" + files[i]
                size = 0
            elif self.issnd.match(files[i]):
                shot = "static/gfx/audio-file.png"
                size = os.path.getsize(Storage.getFilePath(files[i]))
            else:
                shot = "static/gfx/text-file.png"
                size = os.path.getsize(Storage.getFilePath(files[i]))
            # Admin user gets to delete files
            if admin:
                buttons = ('<button type="button" ' +
                    'class="btn btn-sm btn-danger file-delete" ' +
                    'value="' + files[i] + '">delete</button>')
            else:
                buttons = ""
            # If there is file size...
            if size >= 1024 * 1024:
                size = ("%dMB" % round(size / 1024 / 1024))
            elif size >= 1024:
                size = ("%dkB" % round(size / 1024))
            elif size > 0:
                size = ("%d bytes" % size)
            else:
                size = ""
            # Print out individual tiles
            rows += ('<td class="file-tile">' +
                ('<a href="files/%s" download="%s">' % (files[i], files[i])) +
                ('<img src="%s" download="%s">' % (shot, files[i])) +
                ('<div class="file-size">%s</div>' % size) +
                ('<p class="file-title">%s</p>' % files[i]) +
                ('</a>%s</td>\n' % buttons))
            # Finish a row
            if i % 3 == 2:
                rows += '</tr>\n'

        # Finish final row
        if len(files) > 0 and len(files) % 3 != 0:
            rows += '</tr>\n'

        # Assign variables
        variables = super().template_variables()
        variables["rows"] = rows
        return variables

    def indexAction(self):
        self.serve_template("files.html", **self.template_variables())

    def delete(self):
        try:
            data = json.loads(self.get_body().decode("utf-8"))
            file = data["name"].strip() if "name" in data else ""
            # Only delete if we have a file name AND are authorized
            if self.isAuthorized() and len(file) > 0:
                Storage.getSharedInstance().deleteFile(file)
            self.send_response("{}", content_type="application/json", code=200)
        except Exception as e:
            logger.debug("delete(): " + str(e))
            self.send_response("{}", content_type="application/json", code=400)
