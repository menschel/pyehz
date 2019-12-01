# pyehz
Python 3 Interface to Smart Meters

The goal of this project is to provide a Python 3 Interface to Smart Meters, or 
"elektronischer Haushaltszähler" as its called in German.

Please refer to my post in FHEM forum for some detailed information.
https://forum.fhem.de/index.php/topic,105726.0.html

The basic functionality of a smart meter is defined in the IEC 62056, defining "registers" where to find
specific measurement values, e.g. Load, Voltage, Frequency.

There are multiple interface variants on multiple physical layers and they all speak dialects of this protocol.

The supported devices currently are Pafal 20ec3gr and DRS110M.

Pafal 20ec3gr is a common multi-phase smart meter that local electric power providers install in private homes.
It can be accessed via optical link on the front plate.
It is capable to work both ways, e.g. if a solar power installation is present it also counts the energy flowing back into the net.
In the standard configuration, it does not provide any interesting data except for its ID and the active energy.

DRS110M is a single phase smart meter for DIN rail that can handle up to 10A(100A) that was distributed by BGE Tech.
It can be accessed via RS485 and a serial protocol.
It provides excessive data about voltage, current, frequency, active/reactive/apparent power, active energy.
Unfortunately the chinese manufacturer YTL discontinued that product.



