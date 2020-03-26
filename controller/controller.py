from datetime import datetime, timedelta, timezone
import json
import time
import urllib.request

import gevent

from .suntime import Sun

LAT = 51.0
LON = -1.6

SWITCH_OFF = 0
SWITCH_ON = 255

def time_delta(on, off):
    return ((off.hour * 3600 + off.minute * 60 + off.second) -
            (on.hour * 3600 + on.minute * 60 + on.second))

class SunEvent:
    # offset is datetime.timedelta object
    def __init__(self, sun, offset):
        self.sun = sun
        self.offset = offset

    def time(self):
        dt = self.suntime()
        dt.replace(tzinfo=timezone.utc)
        ts = dt.timestamp()

        return datetime.fromtimestamp(ts + self.offset).time()

class SunriseEvent(SunEvent):
    def suntime(self):
        return self.sun.get_sunrise_time()

    def asdict(self):
        return {'type': "sunrise",
                'offset': self.offset}

class SunsetEvent(SunEvent):
    def suntime(self):
        return self.sun.get_sunset_time()

    def asdict(self):
        return {'type': "sunset",
                'offset': self.offset}

class DailyEvent:
    # localtime is naive datetime.time object
    def __init__(self, localtime):
        self.localtime = localtime

    def time(self):
        return self.localtime

    def asdict(self):
        return {'type': "daily",
                'time': self.localtime.strftime("%H:%M:%S")}

class Timer:
    def __init__(self, on_event, off_event, minimum=None):
        self.on_event = on_event
        self.off_event = off_event
        self.minimum = minimum

    def is_on(self, dt):
        tim = dt.time()

        if self.minimum is not None:
            t = time_delta(self.on_event.time(), self.off_event.time())
            if t < self.minimum:
                return False

        return self.on_event.time() <= tim and self.off_event.time() > tim

    def asdict(self):
        val = {'on': self.on_event.asdict(), 'off': self.off_event.asdict()}
        if self.minimum is not None:
            val['minimum'] = self.minimum

class Controller:
    def __init__(self, resolution=60):
        self.resolution = resolution

        self.switches = {}
        self.sun = Sun(LAT, LON)

        self.secs = int(time.time())

    def load(self, settings):
        for name, switch in settings.items():
            self.switches[name] = {
                    'timers': [self.timer_factory(t) for t in switch['timers']],
                    'mode': switch['mode']}

    def dump(self):
        result = {}
        for name, switch in self.switches.items():
            result[name] = {'mode': switch['mode'],
                            'timers': [t.asdict() for t in switch['timers']]}
        return result

    def timer_factory(self, tim):
        on_event = self.event_factory(tim['on'])
        off_event = self.event_factory(tim['off'])
        minimum = tim.get('minimum')

        return Timer(on_event, off_event, minimum)

    def event_factory(self, evt):
        if evt['type'] == 'daily':
            localtime = datetime.strptime(evt['time'], "%H:%M:%S").time()
            event = DailyEvent(localtime)

        elif evt['type'] == 'sunrise':
            event = SunriseEvent(self.sun, evt['offset'])

        elif evt['type'] == 'sunset':
            event = SunsetEvent(self.sun, evt['offset'])

        return event

    def set_switch(self, switch, mode):
        self.switches[switch]['mode'] = mode
        if mode == 'manual':
            return
        elif mode == 'on':
            val = 'on'
        elif mode == 'auto':
            val = self._get_auto_setting(switch, self.secs)
        else:
            val = 'off'

        self._set_switch(switch, val)

    def start(self):
        self.secs = int(time.time()) + 1
        while 1:
            delta = self.secs - time.time()
            if delta > 0:
                gevent.sleep(delta)

            if (self.secs % self.resolution) == 0:
                self._update(datetime.fromtimestamp(self.secs))
            self.secs += 1

    # _update is called every self.resolution seconds
    def _update(self, dt):
        for s, switch in self.switches.items():
            if switch['mode'] == 'manual':
                continue
            elif switch['mode'] == 'on':
                setting = 'on'
            elif switch['mode'] == 'off':
                setting = 'off'
            else:
                setting = self._get_auto_setting(switch['timers'], dt)

            self._set_switch(s, setting)

    def _get_auto_setting(self, timers, dt):
        on = False
        for t in timers:
            on = on or t.is_on(dt)

        val = 'on' if on else 'off'
        return val

    def _set_switch(self, switch, setting):
        print(datetime.now(), switch, setting)
        url = "http://homeweb:5000/api/switch/%s" % switch
        data = json.dumps(SWITCH_ON if setting == 'on' else SWITCH_OFF).encode('utf-8')
        req = urllib.request.Request(url=url, data=data, method='PUT',
                headers={'Content-Type': "application/json"})

        try:
            urllib.request.urlopen(req)
        except urllib.error.URLError:
            print("Error openning " + url)
