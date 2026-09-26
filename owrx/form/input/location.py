from owrx.form.input import Input
from owrx.form.input.validator import Validator
from owrx.form.error import ValidationError
import html


class LocationValidator(Validator):
    def validate(self, key, value):
        if "lat" in value and not -90 < value["lat"] < 90:
            raise ValidationError(key, "Latitude out of range (-90 to 90)")
        if "lon" in value and not -180 < value["lon"] < 180:
            raise ValidationError(key, "Longitude out of range (-180 to 180)")


class LocationInput(Input):
    def __init__(self, id, label, validator: Validator = None):
        if validator is None:
            validator = LocationValidator()
        super().__init__(id, label, validator=validator)

    def render_input_group(self, value, errors):
        return """
            <div class="row {rowclass}">
                {inputs}
            </div>
            {errors}
            <div class="row">
                <div class="col map-input" for="{id}"></div>
            </div>
        """.format(
            id=html.escape(self.id, quote=True),
            rowclass="is-invalid" if errors else "",
            inputs=self.render_input(value, errors),
            errors=self.render_errors(errors),
        )

    def render_input(self, value, errors):
        return "".join(self.render_sub_input(value, id, errors) for id in ["lat", "lon"])

    def render_sub_input(self, value, id, errors):
        coordinate = "Latitude" if id == "lat" else "Longitude"
        return """
            <div class="col">
                <input type="number" class="{classes}" id="{id}" name="{id}" placeholder="{coordinate}"
                aria-label="{label}: {coordinate}" value="{value}" step="any" {disabled}>
            </div>
        """.format(
            id=html.escape("{0}-{1}".format(self.id, id), quote=True),
            label=html.escape(self.label, quote=True),
            coordinate=coordinate,
            classes=self.input_classes(errors),
            value=html.escape(str(value[id]), quote=True),
            disabled="disabled" if self.disabled else "",
        )

    def parse(self, data):
        value = {k: float(data["{0}-{1}".format(self.id, k)][0]) for k in ["lat", "lon"]}
        return {self.id: value}
