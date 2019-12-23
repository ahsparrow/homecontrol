from gevent import monkey; monkey.patch_all()
import gevent

import datetime

from controller.controller import Controller, DailyTimer, SunsetTimer

c = Controller([('socket1', 255), ('outside_light', 255)], resolution=300)

tim1 = SunsetTimer(-1800, 1)
c.add_timer(tim1, "outside_light")

tim2 = DailyTimer(datetime.time(21, 45, 0), -1)
c.add_timer(tim2, "outside_light")

g = gevent.spawn(Controller.start, c)

gevent.joinall([g])
