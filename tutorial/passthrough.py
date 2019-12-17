import magma as m
import fault


class Passthrough(m.Circuit):
    IO = ["I", m.In(m.Bit), "O", m.Out(m.Bit)]

    @classmethod
    def definition(io):
        io.O <= io.I


passthrough_tester = fault.Tester(Passthrough)
passthrough_tester.circuit.I = 1
passthrough_tester.test()
passthrough_tester.circuit.O.expect(1)
passthrough_tester.compile_and_run("verilator")
