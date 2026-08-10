from owrx.form.input import DropdownEnum


class DabOutputRateValues(DropdownEnum):
    RATE_48000 = (48000, "48kHz")
    RATE_32000 = (32000, "32kHz")

    def __new__(cls, *args, **kwargs):
        value, description = args
        obj = object.__new__(cls)
        obj._value_ = value
        obj.description = description
        return obj

    def __str__(self):
        return self.description
