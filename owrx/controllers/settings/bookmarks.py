from owrx.controllers.template import WebpageController
from owrx.controllers.admin import AuthorizationMixin
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.bookmarks import Bookmark, Bookmarks
from owrx.modes import Modes, AnalogMode
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
import json
import math

import logging

logger = logging.getLogger(__name__)


class BookmarksController(AuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Bookmark editor", "settings/bookmarks"))

    def template_variables(self):
        variables = super().template_variables()
        variables["bookmarks"] = self.render_table()
        return variables

    def render_table(self):
        bookmarks = Bookmarks.getSharedInstance().getEditableBookmarks()
        emptyText = """
            <tr class="emptytext"><td colspan="7">
                No bookmarks in storage. You can add new bookmarks using the buttons below. 
            </td></tr>
        """

        return """
            <table class="table" data-modes='{modes}'>
                <tr>
                    <th>Name</th>
                    <th class="frequency">Frequency</th>
                    <th>Modulation</th>
                    <th>Underlying</th>
                    <th>Description</th>
                    <th>Scan</th>
                    <th>Actions</th>
                </tr>
                {bookmarks}
            </table>
        """.format(
            bookmarks="".join(self.render_bookmark(b) for b in bookmarks) if bookmarks else emptyText,
            modes=json.dumps({m.modulation: {
                "name"       : m.name,
                "analog"     : isinstance(m, AnalogMode),
                "underlying" : m.underlying if hasattr(m, "underlying") else []
            } for m in Modes.getAvailableClientModes() })
        )

    def render_bookmark(self, bookmark: Bookmark):
        def render_frequency(freq):
            suffixes = {
                0: "",
                3: "k",
                6: "M",
                9: "G",
                12: "T",
            }
            exp = 0
            if freq > 0:
                exp = int(math.log10(freq) / 3) * 3
            num = freq
            suffix = ""
            if exp in suffixes:
                num = freq / 10 ** exp
                suffix = suffixes[exp]
            return "{num:g} {suffix}Hz".format(num=num, suffix=suffix)

        scan  = bookmark.isScannable()
        name1 = bookmark.getModulation()
        name2 = bookmark.getUnderlying()
        mode1 = Modes.findByModulation(name1)
        mode2 = Modes.findByModulation(name2)

        return """
            <tr data-id="{id}">
                <td data-editor="name" data-value="{name}">{name}</td>
                <td data-editor="frequency" data-value="{frequency}" class="frequency">{rendered_frequency}</td>
                <td data-editor="modulation" data-value="{modulation}">{modulation_name}</td>
                <td data-editor="underlying" data-value="{underlying}">{underlying_name}</td>
                <td data-editor="description" data-value="{description}">{description}</td>
                <td data-editor="scannable" data-value="{scannable}">{scannable_check}</td>
                <td>
                    <button type="button" class="btn btn-sm btn-danger bookmark-delete">delete</button>
                </td>
            </tr>
        """.format(
            id=id(bookmark),
            name=bookmark.getName(),
            # TODO render frequency in si units
            frequency=bookmark.getFrequency(),
            rendered_frequency=render_frequency(bookmark.getFrequency()),
            modulation=name1 if mode1 is None else mode1.modulation,
            underlying=name2 if mode2 is None else mode2.modulation,
            modulation_name=name1 if mode1 is None else mode1.name,
            underlying_name="None" if not name2 else name2 if mode2 is None else mode2.name,
            description=bookmark.getDescription(),
            scannable="true" if scan else "false",
            scannable_check="&check;" if scan else "",
        )

    def _findBookmark(self, bookmark_id):
        bookmarks = Bookmarks.getSharedInstance()
        try:
            return next(b for b in bookmarks.getBookmarks() if id(b) == bookmark_id)
        except StopIteration:
            return None

    def _sanitizeBookmark(self, data):
        try:
            # Must have name, frequency, modulation
            if "name" not in data or "frequency" not in data or "modulation" not in data:
                return "Bookmark missing required fields"
            # Name must not be empty
            data["name"] = data["name"].strip()
            if len(data["name"]) == 0:
                return "Empty bookmark name"
            # Frequency must be integer
            if not isinstance(data["frequency"], int):
                data["frequency"] = int(data["frequency"])
            # Frequency must be >0
            if data["frequency"] <= 0:
                return "Frequency must be positive"
            # Get both modes
            mode1 = Modes.findByModulation(data["modulation"]) if "modulation" in data else None
            mode2 = Modes.findByModulation(data["underlying"]) if "underlying" in data else None
            # Unknown main mode
            if mode1 is None:
                return "Invalid modulation"
            # No underlying mode
            if mode2 is None:
                data["underlying"] = ""
            else:
                # Main mode has no underlying mode or underlying mode incorrect
                if not hasattr(mode1, "underlying") or mode2.modulation not in mode1.underlying:
                    return "Incorrect underlying modulation"
                # Underlying mode is at the default value
                #if mode2.modulation == mode1.underlying[0]:
                #    data["underlying"] = ""

        except Exception as e:
            # Something else went horribly wrong
            return str(e)

        # Everything ok
        return None

    def update(self):
        bookmark_id = int(self.request.matches.group(1))
        bookmark = self._findBookmark(bookmark_id)
        if bookmark is None:
            self.send_response("{}", content_type="application/json", code=404)
            return
        try:
            newd = {}
            data = json.loads(self.get_body().decode("utf-8"))
            for key in ["name", "frequency", "modulation", "underlying", "description", "scannable"]:
                if key in data:
                    newd[key] = data[key]
                elif hasattr(bookmark, key):
                    newd[key] = getattr(bookmark, key)
            # Make sure everything is correct
            error = self._sanitizeBookmark(newd)
            if error is not None:
                raise ValueError(error)
            # Update and store bookmark
            for key in newd:
                setattr(bookmark, key, newd[key])
            Bookmarks.getSharedInstance().store()
            # TODO this should not be called explicitly... bookmarks don't have any event capability right now, though
            Bookmarks.getSharedInstance().notifySubscriptions(bookmark)
            self.send_response("{}", content_type="application/json", code=200)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed updating bookmark: " + str(e))
            self.send_response("{}", content_type="application/json", code=400)

    def new(self):
        bookmarks = Bookmarks.getSharedInstance()

        def create(bookmark_data):
            # sanitize
            data = {}
            for key in ["name", "frequency", "modulation", "underlying", "description", "scannable"]:
                if key in bookmark_data:
                    data[key] = bookmark_data[key]
            error = self._sanitizeBookmark(data)
            if error is not None:
                raise ValueError(error)
            bookmark = Bookmark(data)
            bookmarks.addBookmark(bookmark)
            return {"bookmark_id": id(bookmark)}

        try:
            data = json.loads(self.get_body().decode("utf-8"))
            result = [create(b) for b in data]
            bookmarks.store()
            self.send_response(json.dumps(result), content_type="application/json", code=200)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed creating bookmark: " + str(e))
            self.send_response("{}", content_type="application/json", code=400)

    def delete(self):
        bookmark_id = int(self.request.matches.group(1))
        bookmark = self._findBookmark(bookmark_id)
        if bookmark is None:
            self.send_response("{}", content_type="application/json", code=404)
            return
        bookmarks = Bookmarks.getSharedInstance()
        bookmarks.removeBookmark(bookmark)
        bookmarks.store()
        self.send_response("{}", content_type="application/json", code=200)

    def indexAction(self):
        self.serve_template("settings/bookmarks.html", **self.template_variables())
