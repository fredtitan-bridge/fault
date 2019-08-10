from pathlib import Path
import magma as m
import fault


def pytest_generate_tests(metafunc):
    fault.pytest_sim_params(metafunc, 'system-verilog', 'verilog-ams')


def test_mixed_sim(target, simulator, n_trials=100, vsup=1.5):
    # declare the circuit
    ports = []
    ports += ['in_', m.In(m.Bit)]
    ports += ['out', m.Out(m.Bit)]
    if target == 'verilog-ams':
        ports += ['vdd', m.In(m.Bit)]
        ports += ['vss', m.In(m.Bit)]
    dut = m.DeclareCircuit('myinv', *ports)

    # define the test content
    tester = fault.Tester(dut)
    if target == 'verilog-ams':
        tester.poke(dut.vdd, 1)
        tester.poke(dut.vss, 0)
    for _ in range(n_trials):
        # generate random bit
        in_ = fault.random_bit()
        # send stimulus and check output
        tester.poke(dut.in_, in_)
        tester.expect(dut.out, not in_, strict=True)

    # define run options
    kwargs = dict(
        target=target,
        simulator=simulator,
        ext_model_file=True,
        tmp_dir=True
    )
    if target == 'verilog-ams':
        kwargs['model_paths'] = [Path('tests/spice/myinv.sp').resolve()]
        kwargs['use_spice'] = ['myinv']
        kwargs['vsup'] = vsup
    elif target == 'system-verilog':
        kwargs['ext_libs'] = [Path('tests/verilog/myinv.v').resolve()]

    # compile and run
    tester.compile_and_run(**kwargs)