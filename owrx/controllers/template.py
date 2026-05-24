from owrx.controllers import Controller
from owrx.details import ReceiverDetails
from owrx.config import Config
from string import Template
import pkg_resources


class TemplateController(Controller):
    def render_template(self, file, **vars):
        file_content = pkg_resources.resource_string("htdocs", file).decode("utf-8")
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

