from owrx.controllers import Controller
from owrx.details import ReceiverDetails
from owrx.config import Config
from owrx.mapconfig import public_settings, script_json, value
from string import Template
import importlib.resources


class TemplateController(Controller):
    def render_template(self, file, **vars):
        file_content = importlib.resources.files("htdocs").joinpath(file).read_text(encoding="utf-8")
        template = Template(file_content)

        return template.safe_substitute(**vars)

    def serve_template(self, file, **vars):
        self.send_response(self.render_template(file, **vars), content_type="text/html")

    def default_variables(self):
        return {}


class WebpageController(TemplateController):
    def get_document_root(self):
        path_parts = [part for part in self.request.path[1:].split("/")]
        levels = max(0, len(path_parts) - 1)
        return "../" * levels

    def header_variables(self):
        variables = { "document_root": self.get_document_root(), "map_type": "" }
        variables.update(ReceiverDetails().__dict__())
        return variables

    def template_variables(self):
        header = self.render_template("include/header.include.html", **self.header_variables())
        return {"header": header, "document_root": self.get_document_root()}


class IndexController(WebpageController):
    def indexAction(self):
        self.serve_template("index.html", **self.template_variables())


class MapController(WebpageController):
    def indexAction(self):
        if value(Config.get(), "map_enabled", True) is False:
            self.send_response("The web map client is disabled by the administrator.", code=403, content_type="text/plain")
            return
        self.serve_template("map-{}.html".format(self.map_type()), **self.template_variables())

    def template_variables(self):
        variables = super().template_variables()
        variables["map_config"] = script_json(public_settings(Config.get()))
        return variables

    def google_allowed(self):
        config = Config.get()
        key = value(config, "google_maps_api_key", "")
        return bool(key) and value(config, "map_allow_google", bool(key)) is True

    def header_variables(self):
        variables = super().header_variables()
        # Do not advertise an unusable/disabled Google client in the toolbar.
        if self.map_type() == "google":
            variables["map_type"] = "?type=leaflet"
        elif self.google_allowed():
            variables["map_type"] = "?type=google"
        return variables

    def map_type(self):
        config = Config.get()
        default = value(config, "map_type", "leaflet")
        requested = self.request.query.get("type", [default])
        requested = requested[0] if requested else default
        if requested not in ("google", "leaflet"):
            requested = default
        return "google" if requested == "google" and self.google_allowed() else "leaflet"


class PolicyController(WebpageController):
    def indexAction(self):
        self.serve_template("policy.html", **self.template_variables())

