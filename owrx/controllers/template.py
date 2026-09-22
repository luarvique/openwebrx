from owrx.controllers import Controller
from owrx.adminaccess import is_admin_enabled
from owrx.details import ReceiverDetails
from owrx.config import Config
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
        document_root = self.get_document_root()
        variables = { "document_root": document_root, "map_type": "" }
        variables.update(ReceiverDetails().__dict__())
        variables["settings_button"] = self.render_settings_button(document_root)
        return variables

    def render_settings_button(self, document_root):
        if not is_admin_enabled():
            return ""
        return (
            '<a class="button" href="{root}settings" target="openwebrx-settings">'
            '<svg viewBox="0 -960 960 960"><use xlink:href="{root}static/gfx/svg-defs.svg#panel-settings">'
            "</use></svg><br/>Settings</a>"
        ).format(root=document_root)

    def template_variables(self):
        header = self.render_template("include/header.include.html", **self.header_variables())
        return {"header": header, "document_root": self.get_document_root()}


class IndexController(WebpageController):
    def indexAction(self):
        self.serve_template("index.html", **self.template_variables())


class MapController(WebpageController):
    def indexAction(self):
        # TODO check if we have a google maps api key first?
        self.serve_template("map-{}.html".format(self.map_type()), **self.template_variables())

    def header_variables(self):
        # Invert map type for the "map" toolbar icon
        variables = super().header_variables();
        type = self.map_type()
        if type == "google":
            variables.update({ "map_type" : "?type=leaflet" })
        elif type == "leaflet":
            variables.update({ "map_type" : "?type=google" })
        return variables

    def map_type(self):
        pm = Config.get()
        if "type" not in self.request.query:
            type = pm["map_type"]
        else:
            type = self.request.query["type"][0]
            if type not in ["google", "leaflet"]:
                type = pm["map_type"]
        return type


class PolicyController(WebpageController):
    def indexAction(self):
        self.serve_template("policy.html", **self.template_variables())

