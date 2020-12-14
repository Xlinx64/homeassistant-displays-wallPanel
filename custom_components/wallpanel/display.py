"""
Support for WallPanel
"""

from datetime import timedelta
import logging
import requests
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST, CONF_NAME, CONF_PORT,
    STATE_OFF, STATE_ON, STATE_UNKNOWN
)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

from ..display import (                                                     # pylint: disable=relative-beyond-top-level
    DisplayDevice,
    ATTR_BRIGHTNESS,
    SUPPORT_LOAD_URL, SUPPORT_SET_BRIGHTNESS#, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wallpanel'

ATTR_MESSAGE = 'message'
ATTR_URL = 'url'

DEFAULT_NAME = 'WallPanel'
DEFAULT_PORT = 2971

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

SERVICE_LOAD_START_URL = 'load_start_url'
SERVICE_SAY = 'say'
SERVICE_SOUND_START = 'sound_play'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port
})

SCHEMA_SERVICE_LOAD_START_URL = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})
SCHEMA_SERVICE_SOUND_START = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    vol.Required(ATTR_URL): cv.string
})
SCHEMA_SERVICE_SAY = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    vol.Required(ATTR_MESSAGE): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):                   # pylint: disable=unused-argument
    def service_handler(call):
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[DOMAIN]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DOMAIN]
        for device in devices:
            if call.service == SERVICE_LOAD_START_URL:
                device.load_start_url()
            elif call.service == SERVICE_SAY:
                device.tts(call.data[ATTR_MESSAGE])
            elif call.service == SERVICE_SOUND_START:
                device.sound_start(call.data[ATTR_URL])

    _LOGGER.info("Setting up WallPanelDevice for %s at %s:%s",
                 config.get(CONF_NAME, DEFAULT_NAME),
                 config.get(CONF_HOST), config.get(CONF_PORT, DEFAULT_PORT))

    if not DOMAIN in hass.data:
        hass.data[DOMAIN] = []

    device = WallPanelDevice(config.get(CONF_NAME, DEFAULT_NAME),
                              config.get(CONF_HOST),
                              config.get(CONF_PORT, DEFAULT_PORT))
    hass.data[DOMAIN].append(device)
    add_devices([device], True)

    hass.services.register(
        DOMAIN, SERVICE_SAY, service_handler,
        schema=SCHEMA_SERVICE_SAY)

    hass.services.register(
        DOMAIN, SERVICE_LOAD_START_URL, service_handler,
        schema=SCHEMA_SERVICE_LOAD_START_URL)

    hass.services.register(
        DOMAIN, SERVICE_SOUND_START, service_handler,
        schema=SCHEMA_SERVICE_SOUND_START)


class WallPanelDevice(DisplayDevice):
    def __init__(self, name, host, port):
        self.url = 'http://{}:{}/api/'.format(host, port)

        self._name = name
        self._attributes = {}
        self._state = STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        return self._attributes

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def supported_features(self):
        return SUPPORT_LOAD_URL | SUPPORT_SET_BRIGHTNESS# | SUPPORT_TURN_OFF | SUPPORT_TURN_ON

    def load_start_url(self):
        self._send_command(data={'relaunch': True})

    def load_url(self, url):
        self._send_command(data={'url': str(url)})

    def set_brightness(self, brightness):
        self._send_command(data={'brightness': str(brightness)})

    def sound_start(self, url):
        self._send_command(data={'audio': str(url)})

    # def turn_off(self):
    #     self._send_command(data={"brightness": "1"})
    #
    # def turn_on(self):
    #     self._send_command(data={"brightness": "255"})

    def tts(self, message):
        self._send_command(data={'speak': str(message)})

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        try:
            data = self._load_state()
        except OSError:
            return False

        if data['screenOn']:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

        self._attributes = {
            'currentUrl': data['currentUrl'],
            'screenOn': data['screenOn'],
            'brightness': data['brightness']
        }
        return True

    def _load_state(self,):
        url = self.url+"state"
        _LOGGER.debug("Loading state from %s", url)
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return {
            'status': 'Error',
            'statustext': 'Receieved HTTP {} from server'.format(response.status_code),
        }

    def _send_command(self, data):
        url = self.url+"command"
        _LOGGER.debug("Sending %s command to %s", command, url)
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json()
        return {
            'status': 'Error',
            'statustext': 'Receieved HTTP {} from server'.format(response.status_code),
        }
