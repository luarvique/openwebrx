from owrx.form.input import DropdownInput, Option
from owrx.lookup import CCODE2COUNTRY
from owrx.form.input.converter import Converter

class CountryInput(DropdownInput):
    def __init__(self, id, label, infotext=None, converter: Converter = None):
        options = [Option(ccode, name)
            for ccode, name in CCODE2COUNTRY.items() if len(ccode) == 2
        ]
        options.sort(key=lambda x: x.text)
        options = [Option("", "None")] + options
        super().__init__(id, label, options, infotext=infotext, converter=converter)
