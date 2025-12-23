from owrx.form.input.validator import Validator
from owrx.form.error import ValidationError
import re

import logging

logger = logging.getLogger(__name__)


class WifiSsidValidator(Validator):
    def validate(self, key, value):
        # Allow for empty SSIDs which disable connection entry
        if len(value) > 0 and len(value) not in range(1, 33):
            raise ValidationError(key, "WiFi SSID must have length of 1..32 characters")
        # Do not allow any characters other than the ones below
        m = re.search(r"[^0-9A-Za-z_\-\.]", value)
        if m is not None:
            raise ValidationError(key, "WiFi SSID cannot contain '{0}' character".format(m.group(0)))
        pass

class WifiPassValidator(Validator):
    def validate(self, key, value):
        # Allow for empty password which disable connection entry
        if len(value) > 0 and len(value) not in range(8, 64):
            raise ValidationError(key, "WiFi password must have length of 8..63 characters")
        # Do not allow any characters other than the ones below
        m = re.search(r"[^\040-\176]", value)
        if m is not None:
            raise ValidationError(key, "WiFi password is limited to printable characters")
        pass
