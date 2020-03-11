"""
Module for the `PIM` profile intensity monitor classes

This module contains all the classes relating to the profile intensity monitor
classes at the user level. A PIM always has a motor to control yag/diode
position, a zoom motor, and a camera to view the yag. Some PIMs have LEDs for
illumination and/or a focus motor. Each of these configurations is set up as
its own class.
"""
import logging

from ophyd.device import Device, Component as Cpt, FormattedComponent as FCpt
from ophyd.signal import EpicsSignal

from .epics_motor import IMS
from .areadetector.detectors import PCDSAreaDetector
from .epics_motor import BeckhoffAxis
from .inout import InOutRecordPositioner, TwinCATInOutPositioner
from .interface import BaseInterface
from .sensors import TwinCATThermocouple
from .signal import PytmcSignal
from .state import StatePositioner

logger = logging.getLogger(__name__)


class PIMY(InOutRecordPositioner, BaseInterface):
    """
    Standard profile monitor Y motor.

    This can move the stage to insert the yag
    or diode, or retract from the beam path.
    """
    states_list = ['DIODE', 'YAG', 'OUT']
    in_states = ['YAG', 'DIODE']

    _states_alias = {'YAG': 'IN'}
    # QIcon for UX
    _icon = 'fa.camera-retro'

    tab_whitelist = ['stage']

    def stage(self):
        """Save the original position to be restored on `unstage`."""
        self._original_vals[self.state] = self.state.value
        return super().stage()


class PIM(Device, BaseInterface):
    """
    Profile intensity monitor with y-motion motor, zoom motor, and a detector.

    Parameters
    ----------
    prefix : str
        The EPICS base of the PIM

    name : str
        A name to refer to the device

    prefix_det : str, optional
        The EPICS base PV of the detector. If None, it will be attempted to be
        inferred from `prefix`

    prefix_zoom : str, optional
        The EPICS base PV of the zoom motor. If None, it will be attempted to
        be inferred from `prefix`
    """

    _prefix_start = ''

    state = Cpt(PIMY, '', kind='omitted')
    zoom_motor = FCpt(IMS, '{self._prefix_zoom}', kind='normal')
    detector = FCpt(PCDSAreaDetector, '{self._prefix_det}', kind='normal')

    tab_whitelist = ['y_motor', 'remove', 'insert', 'removed', 'inserted']
    tab_component_names = True

    def infer_prefix(self, prefix):
        """Pulls out the first two segments of the prefix PV, if not already
           done"""
        if not self._prefix_start:
            self._prefix_start = '{0}:{1}:'.format(prefix.split(':')[0],
                                                   prefix.split(':')[1])

    @property
    def prefix_start(self):
        """Returns the first two segments of the prefix PV."""
        return str(self._prefix_start)

    @property
    def removed(self):
        """Returns ``True`` if the yag and diode are removed from the beam."""
        return self.state.removed

    @property
    def inserted(self):
        """Returns ``True`` if yag or diode are inserted."""
        return self.state.inserted

    def insert(self, moved_cb=None, timeout=None, wait=False):
        """Moves the YAG into the beam."""
        return self.state.insert(moved_cb=moved_cb, timeout=timeout,
                                 wait=wait)

    def remove(self, moved_cb=None, timeout=None, wait=False):
        """Moves the YAG and diode out of the beam."""
        return self.state.remove(moved_cb=moved_cb, timeout=timeout,
                                 wait=wait)

    def __init__(self, prefix, *, name, prefix_det=None, prefix_zoom=None,
                 **kwargs):
        self.infer_prefix(prefix)

        # Infer the detector PV from the base prefix
        if prefix_det:
            self._prefix_det = prefix_det
        else:
            self._prefix_det = self.prefix_start+'CVV:01'

        # Infer the zoom motor PV from the base prefix
        if prefix_zoom:
            self._prefix_zoom = prefix_zoom
        else:
            self._prefix_zoom = self.prefix_start+'CLZ:01'

        super().__init__(prefix, name=name, **kwargs)
        self.y_motor = self.state.motor


class PIMWithFocus(PIM):
    """
    Profile intensity monitor with y-motion motor, zoom motor, focus motor, and
    a detector.

    Parameters
    ----------
    prefix : str
        The EPICS base of the PIM

    name : str
        A name to refer to the device

    prefix_det : str, optional
        The EPICS base PV of the detector. If None, it will be attempted to be
        inferred from `prefix`

    prefix_zoom : str, optional
        The EPICS base PV of the zoom motor. If None, it will be attempted to
        be inferred from `prefix`

    prefix_focus : str, optional
        The EPICS base PV of the focus motor. If None, it will be attempted to
        be inferred from `prefix`
    """
    focus_motor = FCpt(IMS, '{self._prefix_focus}', kind='normal')

    def __init__(self, prefix, *, name, prefix_focus=None, **kwargs):
        self.infer_prefix(prefix)

        # Infer the focus motor PV from the base prefix
        if prefix_focus:
            self._prefix_focus = prefix_focus
        else:
            self._prefix_focus = self.prefix_start+'CLF:01'

        super().__init__(prefix, name=name, **kwargs)


class PIMWithLED(PIM):
    """
    Profile intensity monitor with y-motion motor, zoom motor, LED, and a
    detector.

    Parameters
    ----------
    prefix : str
        The EPICS base of the PIM

    name : str
        A name to refer to the device

    prefix_det : str, optional
        The EPICS base PV of the detector. If None, it will be attempted to be
        inferred from `prefix`

    prefix_zoom : str, optional
        The EPICS base PV of the zoom motor. If None, it will be attempted to
        be inferred from `prefix`

    prefix_led : str, optional
        The EPICS base PV of the LED. If None, it will be attempted to be
        inferred from `prefix`
    """
    led = FCpt(EpicsSignal, '{self._prefix_led}', kind='normal')

    def __init__(self, prefix, *, name, prefix_led=None, **kwargs):
        self.infer_prefix(prefix)

        # Infer the illuminator PV from the base prefix
        if prefix_led:
            self._prefix_led = prefix_led
        else:
            self._prefix_led = self.prefix_start+'CIL:01'

        super().__init__(prefix, name=name, **kwargs)


class PIMWithBoth(PIMWithFocus, PIMWithLED):
    """
    Profile intensity monitor with y-motion motor, zoom motor, focus motor,
    LED, and a detector.

    Parameters
    ----------
    prefix : str
        The EPICS base of the PIM

    name : str
        A name to refer to the device

    prefix_det : str, optional
        The EPICS base PV of the detector. If None, it will be attempted to be
        inferred from `prefix`

    prefix_zoom : str, optional
        The EPICS base PV of the zoom motor. If None, it will be attempted to
        be inferred from `prefix`

    prefix_focus : str, optional
        The EPICS base PV of the focus motor. If None, it will be attempted to
        be inferred from `prefix`

    prefix_led : str, optional
        The EPICS base PV of the LED. If None, it will be attempted to be
        inferred from `prefix`
    """
    pass


class LCLS2ImagerBase(Device, BaseInterface):
    """
    Shared PVs and components from the LCLS2 imagers

    All LCLS2 imagers are guaranteed to have the following components that
    behave essentially the same
    """
    tab_component_names = True

    y_states = Cpt(TwinCATInOutPositioner, ':MMS:STATE', kind='hinted')
    y_motor = Cpt(BeckhoffAxis, ':MMS', kind='normal')
    detector = Cpt(PCDSAreaDetector, ':CAM:', kind='normal')
    cam_power = Cpt(PytmcSignal, ':CAM:PWR', io='io', kind='config')


class PPMPowerMeter(Device, BaseInterface):
    """
    Analog measurement tool for beam energy as part of the PPM assembly.

    When inserted into the beam, the ``raw_voltage`` signal value should
    increase proportional to the beam energy. The equivalent calibrated
    readings are ``dimensionless``, which is a unitless number that
    represents the relative calibration of every power meter, and
    ``calibrated_mj``, which is the real engineering unit of the beam
    power. These are calibrated using the other signals in the following way:

    ``dimensionless`` = (``raw_voltage`` + ``calib_offset``) * ``calib_ratio``
    ``calibrated_mj`` = ``dimensionless`` * ``calib_mj_ratio``
    """
    tab_component_names = True

    raw_voltage = Cpt(PytmcSignal, ':VOLT', io='i', kind='normal')
    dimensionless = Cpt(PytmcSignal, ':CALIB', io='i', kind='normal')
    calibrated_mj = Cpt(PytmcSignal, ':MJ', io='i', kind='normal')
    thermocouple = Cpt(TwinCATThermocouple, '', kind='normal')

    calib_offset = Cpt(PytmcSignal, ':CALIB:OFFSET', io='io', kind='config')
    calib_ratio = Cpt(PytmcSignal, ':CALIB:RATIO', io='io', kind='config')
    calib_mj_ratio = Cpt(PytmcSignal, ':CALIB:MJ_RATIO', io='io',
                         kind='config')

    raw_voltage_buffer = Cpt(PytmcSignal, ':VOLT_BUFFER', io='i',
                             kind='omitted')
    dimensionless_buffer = Cpt(PytmcSignal, ':CALIB_BUFFER', io='i',
                               kind='omitted')
    calibrated_mj_buffer = Cpt(PytmcSignal, ':MJ_BUFFER', io='i',
                               kind='omitted')


class PPM(LCLS2ImagerBase):
    """
    L2SI's Power and Profile Monitor design.

    Unlike the `XPIM`, this includes a power meter and two thermocouples, one
    on the power meter itself and one on the yag holder. The LED on this unit
    has been outfitted with a dimmable control in units of percentage.

    Parameters
    ----------
    prefix: ``str``
        The EPICS PV prefix for this imager, e.g. ``IM3L0:PPM``.

    name: ``str``, required keyword
        An identifying name for this motor, e.g. ``im3l0``
    """
    power_meter = Cpt(PPMPowerMeter, ':SPM', kind='normal')
    yag_thermocouple = Cpt(TwinCATThermocouple, ':YAG', kind='normal')

    led = Cpt(PytmcSignal, ':CAM:CIL:PCT', io='io', kind='config')


class XPIMFilterWheel(StatePositioner):
    """
    Controllable optical filters to prevent camera saturation.

    There are six filter slots, five with filters of varying optical densities
    and one that is empty. The enum strings here are T100, T50, etc. which
    represent the transmission percentage of the associated filter.
    """
    tab_component_names = True

    state = Cpt(EpicsSignal, ':GET_RBV', write_pv=':SET', kind='normal')

    reset_cmd = Cpt(PytmcSignal, ':ERR:RESET', io='i', kind='omitted')
    error_message = Cpt(PytmcSignal, ':ERR:MSG', io='i', kind='omitted')


class XPIM(LCLS2ImagerBase):
    """
    XTES's Imager design.

    Unlike the `PPM`, this includes a relative encoder zoom and focus dc motor
    stack and a controllable optical filter wheel. The LED on this unit has
    only been outfitted with binary control, on/off.

    Parameters
    ----------
    prefix: ``str``
        The EPICS PV prefix for this imager, e.g. ``IM3L0:PPM``.

    name: ``str``, required keyword
        An identifying name for this motor, e.g. ``im3l0``
    """
    zoom_motor = Cpt(BeckhoffAxis, ':CLZ', kind='normal')
    focus_motor = Cpt(BeckhoffAxis, ':CLF', kind='normal')

    led = Cpt(PytmcSignal, ':CAM:CIL:PWR', io='io', kind='config')
    filter_wheel = Cpt(XPIMFilterWheel, ':MFW', kind='config')