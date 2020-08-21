"""
'lxe' position / pulse energy pseudopositioner support.

Notes
-----
OPA::

    An optical parametric amplifier, abbreviated OPA, is a laser light source
    that emits light of variable wavelengths by an optical parametric
    amplification process. It is essentially the same as an optical parametric
    oscillator, but without the optical cavity, that is, the light beams pass
    through the apparatus just once or twice, rather than many many times.

las_comp_wp::

    Laser compressor waveplate

las_pol_wp::

    Laser polarizer waveplate

LXE::

    Laser energy motor, I assume

LXT::

    Laser x-ray timing, probably
"""

import pathlib
import types
import typing

import numpy as np

from ophyd import Component as Cpt
from ophyd import EpicsSignal, PVPositioner

from .epics_motor import EpicsMotorInterface
from .interface import FltMvInterface
from .pseudopos import (LookupTablePositioner, PseudoSingleInterface,
                        pseudo_position_argument)
from .signal import UnitConversionDerivedSignal

if typing.TYPE_CHECKING:
    import matplotlib  # noqa


def load_calibration_file(
        filename: typing.Union[pathlib.Path, str]
        ) -> np.ndarray:
    """
    Load a calibration file.

    Data will be sorted by position and need not be pre-sorted.

    Two columns of data in a space-delimited text file.  No header:
        Column 1: waveplate position [mm?]
        Column 2: pulse energy [uJ]

    Parameters
    ----------
    filename : str
        The calibration data filename.

    Returns
    -------
    np.ndarray
        Of shape (num_data_rows, 2)
    """
    data = np.loadtxt(str(filename))
    sort_indices = data[:, 0].argsort()
    return np.column_stack([data[sort_indices, 0],
                            data[sort_indices, 1]
                            ])


class LaserEnergyPlotContext:
    table: np.ndarray
    figure: 'matplotlib.figure.Figure'
    pyplot: types.ModuleType  # matplotlib.pyplot
    column_names: typing.Tuple[str, ...]
    _subplot: 'matplotlib.axes._subplots.AxesSubplot'

    def __init__(self, *,
                 table: np.ndarray,
                 column_names: typing.Sequence[str]):
        self.table = table

        # Importing forces backend selection, so do inside method
        import matplotlib.pyplot as pyplot  # noqa
        self.pyplot = pyplot
        self.figure = None
        self._subplot = None
        self.column_names = tuple(column_names)

    def close(self):
        """No longer use the existing figure, but do not close it."""
        self.figure = None

    def plot(self, new_figure=True, show=True):
        """
        Plot calibration data.

        Parameters
        ----------
        new_figure : bool, optional
            Force creation of a new figure.

        show : bool, optional
            Show the plot.
        """
        plt = self.pyplot

        if self.figure is not None:
            # New figure if the last one was closed
            new_figure = not plt.fignum_exists(self.figure.number)

        self.figure = plt.figure() if new_figure else plt.gcf()

        self._subplot = self.figure.subplots()
        self._subplot.plot(
            self.table[:, self.column_names.index('motor')],
            self.table[:, self.column_names.index('energy')],
            "k-o"
        )
        if new_figure:
            self._subplot.set_xlabel("Motor position")
            self._subplot.set_ylabel(r"Pulse energy [$\mu$J]")

        if show:
            self.figure.show()

    def add_line(self, position: float, energy: float):
        """Add a new set of lines at (position, energy)."""
        if self.figure is None:
            self.plot(show=False)

        self._subplot.axvline(position)
        self._subplot.axhline(energy)
        self.figure.canvas.draw()


class LaserEnergyPositioner(LookupTablePositioner, FltMvInterface):
    """
    Uses the lookup-table positioner to convert energy <-> motor positions.

    Uses :func:`load_calibration_file` to load the data file.

    Parameters
    ----------
    calibration_file : pathlib.Path or str
        Path to the calibration file.

    column_names : list of str, optional
        The column names.  May be omitted, assumes the first column is the
        motor position and the second column is energy.

    enable_plotting : bool, optional
        Plot each move.
    """

    _plot_context: LaserEnergyPlotContext

    energy = Cpt(PseudoSingleInterface, egu='uJ')
    motor = Cpt(EpicsMotorInterface, '')

    def __init__(self, *args,
                 calibration_file: typing.Union[pathlib.Path, str],
                 column_names: typing.Sequence[str] = None,
                 enable_plotting: bool = False,
                 **kwargs):
        table = load_calibration_file(calibration_file)
        column_names = column_names or ['motor', 'energy']
        super().__init__(*args,
                         table=table,
                         column_names=column_names,
                         **kwargs)
        self._plot_context = None
        self.enable_plotting = enable_plotting

    @property
    def enable_plotting(self) -> bool:
        return self._plot_context is not None

    @enable_plotting.setter
    def enable_plotting(self, enable: bool):
        if enable == self.enable_plotting:
            return

        if enable:
            self._plot_context = LaserEnergyPlotContext(
                table=self.table,
                column_names=self.column_names,
            )
            self._plot_context.plot()
        else:
            self._plot_context.close()
            self._plot_context = None

    @pseudo_position_argument
    def move(self, position, wait=True, timeout=None, moved_cb=None):
        ret = super().move(position, wait=wait, timeout=timeout,
                           moved_cb=moved_cb)
        if self._plot_context is not None:
            real = self.forward(position)
            self._plot_context.add_line(position=real.motor,
                                        energy=position.energy)
        return ret

    def wm(self) -> float:
        # Remove the PseudoPosition tuple for FltMvInterface compatibility
        return super().wm[0]


class LaserTiming(PVPositioner, FltMvInterface):
    """
    "lxt" motor, which may also have been referred to as Vitara.

    Conversions for Vitara FS_TGT_TIME nanoseconds <-> seconds are done
    internally, such that the user may work in units of seconds.
    """

    _fs_tgt_time = Cpt(EpicsSignal, ':VIT:FS_TGT_TIME', auto_monitor=True)
    setpoint = Cpt(UnitConversionDerivedSignal,
                   derived_from='_fs_tgt_time',
                   derived_units='s',
                   original_units='ns',
                   )

    # A motor (record) will be moved after the above record is touched, so
    # use its done motion status:
    done = Cpt(EpicsSignal, ':MMS:PH.DMOV', auto_monitor=True)
    done_value = 1

    def __init__(self, prefix='', *, egu=None, **kwargs):
        if egu not in (None, 's'):
            raise ValueError(
                f'{self.__class__.__name__} is pre-configured to work in units'
                f' of seconds.'
            )
        super().__init__(prefix, egu='s', **kwargs)