import magma as m
from abc import abstractmethod
from ..wrapper import CircuitWrapper
from ..select_path import SelectPath
from ..wrapped_internal_port import WrappedVerilogInternalPort


class AbstractTester:
    def __init__(self, circuit: m.Circuit, clock: m.Clock = None,
                 reset: m.Reset = None, poke_delay_default=None,
                 expect_strict_default=True):
        """
        `circuit`: the device under test (a magma circuit)
        `clock`: optional, a port from `circuit` corresponding to the clock
        `reset`: optional, a port from `circuit` corresponding to the reset
        `expect_strict_default`: if True, use strict equality check if
        not specified by the user.
        """
        self._circuit = circuit
        self.poke_delay_default = poke_delay_default
        self.expect_strict_default = expect_strict_default
        self.actions = []
        if clock is not None and not isinstance(clock, m.Clock):
            raise TypeError(f"Expected clock port: {clock, type(clock)}")
        self.clock = clock
        # Make sure the user has initialized the clock before stepping it
        # While verilator initializes the clock value to 0, this assumption
        # does not hold for system verilog, so we log a warning (as to not
        # break existing TBs)
        self.clock_initialized = False
        # Only report once, in case the user calls step with an uninitialized
        # clock many times
        self.clock_init_warning_reported = False
        if reset is not None and not isinstance(reset, m.Reset):
            raise TypeError(f"Expected reset port: {reset, type(reset)}")
        self.reset_port = reset

    def get_port_type(self, port):
        if isinstance(port, SelectPath):
            port = port[-1]
        if isinstance(port, WrappedVerilogInternalPort):
            type_ = port.type_
        else:
            type_ = type(port)
        return type_

    @abstractmethod
    def poke(self, port, value, delay=None):
        """
        Set `port` to be `value`
        """
        raise NotImplementedError()

    @abstractmethod
    def peek(self, port):
        """
        Returns a handle to the current value of `port`
        """
        raise NotImplementedError()

    @abstractmethod
    def print(self, format_str, *args):
        """
        Prints out `format_str`

        `*args` should be a variable number of magma ports used to fill in the
        format string
        """
        raise NotImplementedError()

    @abstractmethod
    def assert_(self, expr):
        """
        Asserts `expr` is true
        """
        raise NotImplementedError()

    @abstractmethod
    def expect(self, port, value, strict=None, caller=None, **kwargs):
        """
        Expect the current value of `port` to be `value`
        """
        raise NotImplementedError()

    @abstractmethod
    def eval(self):
        """
        Evaluate the DUT given the current input port values
        """
        raise NotImplementedError()

    @abstractmethod
    def delay(self, time):
        """
        Wait the specified amount of time before proceeding
        """
        raise NotImplementedError()

    @abstractmethod
    def get_value(self, port):
        """
        Returns an object with a "value" property that will
        be filled after the simulation completes.
        """
        raise NotImplementedError()

    @abstractmethod
    def step(self, steps=1):
        """
        Step the clock `steps` times.
        """
        raise NotImplementedError()

    def zero_inputs(self):
        """
        Set all the input ports to 0, useful for intiializing everything to a
        known value
        """
        for name, port in self._circuit.IO.ports.items():
            if port.is_input():
                self.poke(self._circuit.interface.ports[name], 0)

    @property
    def circuit(self):
        return CircuitWrapper(self._circuit, self)

    @abstractmethod
    def loop(self, n_iter):
        raise NotImplementedError()

    @abstractmethod
    def file_open(self, file_name, mode="r", chunk_size=1, endianness="little"):
        """
        mode : "r" for read, "w" for write
        chunk_size : number of bytes per read/write
        """
        raise NotImplementedError()

    @abstractmethod
    def file_close(self, file):
        raise NotImplementedError()

    @abstractmethod
    def file_read(self, file):
        raise NotImplementedError()

    @abstractmethod
    def file_write(self, file, value):
        raise NotImplementedError()

    @abstractmethod
    def _while(self, cond):
        raise NotImplementedError()

    @abstractmethod
    def _if(self, cond):
        raise NotImplementedError()

    @abstractmethod
    def file_scanf(self, file, _format, *args):
        raise NotImplementedError()

    @abstractmethod
    def Var(self, name, _type):
        raise NotImplementedError()

    def wait_on(self, cond):
        loop = self._while(cond)
        loop.step()

    def wait_until_low(self, signal):
        self.wait_on(self.peek(signal))

    def wait_until_high(self, signal):
        self.wait_on(~self.peek(signal))

    def wait_until_negedge(self, signal):
        self.wait_until_high(signal)
        self.wait_until_low(signal)

    def wait_until_posedge(self, signal, steps_per_iter=1):
        self.wait_until_low(signal)
        self.wait_until_high(signal)

    def pulse_high(self, signal):
        # first make sure the signal is actually low to begin with
        self.expect(signal, 0)

        # first set the signal high, then bring it low again
        self.poke(signal, 1)
        self.poke(signal, 0)

    def pulse_low(self, signal):
        # first make sure the signal is actually high to begin with
        self.expect(signal, 1)

        # first set the signal low, then bring it high again
        self.poke(signal, 0)
        self.poke(signal, 1)

    def sync_reset(self, active_high=True, cycles=1):
        # assert reset and set clock to zero
        self.poke(self.reset_port, 1 if active_high else 0)
        self.poke(self.clock, 0)

        # wait the desired number of clock cycles
        self.step(2 * cycles)

        # de-assert reset
        self.poke(self.reset_port, 0 if active_high else 1)

    def internal(self, *args):
        # return a SelectPath containing the desired path
        return SelectPath([self.circuit] + list(args))

    def __call__(self, *args, **kwargs):
        """
        Poke the inputs of the circuit using *args (ordered, anonymous input
        reference, excluding clocks) and **kwargs.  **kwargs will overwrite any
        inputs written by *args.

        Evaluate the circuit

        Return the "peeked" output(s) of the circuit (tuple for multiple
        outputs)
        """
        for arg, port in zip(args, self._circuit.interface.outputs()):
            self.poke(port, arg)
        self.eval()
        result = tuple(self.peek(port) for port in
                       self._circuit.interface.inputs())
        if len(result) == 1:
            return result[0]
        return result