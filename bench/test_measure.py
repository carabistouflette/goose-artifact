# SPDX-License-Identifier: Apache-2.0
"""Finite benchmark failure/retention controls; no download timings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import measure


class EvidenceTests(unittest.TestCase):
    def test_completed_samples_survive_failure_and_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as raw:
            output=Path(raw)/'run.json';evidence=measure.Evidence(output)
            evidence.record(0,'success',lambda:{'verified':True})
            def broken(): raise RuntimeError('injected failure')
            with self.assertRaises(RuntimeError):evidence.record(1,'success',broken)
            evidence.failure(RuntimeError('injected failure'))
            events=[json.loads(v) for v in evidence.events.read_text().splitlines()]
            self.assertTrue(events[2]['sample']['verified'])
            self.assertEqual(events[-1]['event'],'failed')
            before=evidence.events.read_bytes()
            with self.assertRaises(FileExistsError):measure.Evidence(output)
            self.assertEqual(evidence.events.read_bytes(),before)
            output.write_text('existing record')
            with self.assertRaises(SystemExit):measure.Evidence(output)
            self.assertEqual(output.read_text(),'existing record')

    def test_main_failure_retains_previous_sample(self):
        with tempfile.TemporaryDirectory() as raw:
            output=Path(raw)/'run.json'
            def failure(args,sizes,counts,evidence):
                evidence.record(0,'success',lambda:{'verified':True})
                raise RuntimeError('injected later failure')
            with patch.object(sys,'argv',['measure','--goose','/unused','--output',str(output)]),patch.object(measure,'execute',side_effect=failure):
                with self.assertRaisesRegex(RuntimeError,'later failure'):measure.main()
            events=[json.loads(line) for line in output.with_name(output.name+'.evidence').joinpath('events.jsonl').read_text().splitlines()]
            self.assertEqual(events[2]['event'],'sample-completed')
            self.assertEqual(events[-1]['event'],'failed')
            self.assertFalse(output.exists())

    def test_build_failure_retains_command_diagnostic_and_exit(self):
        with tempfile.TemporaryDirectory() as raw:
            folder=Path(raw)/'build'
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                measure.run([sys.executable,'-c','import sys;sys.stderr.write("build failure probe");sys.exit(7)'],output=folder)
            self.assertEqual(caught.exception.returncode,7)
            self.assertEqual((folder/'stderr').read_text(),'build failure probe')
            self.assertEqual(json.loads((folder/'process.json').read_text())['returncode'],7)

    def test_invalid_parameters_fail_before_build(self):
        options=[['--controls','-1'],['--startup-controls','-1'],['--controls','0'],
                 ['--sizes','999999999999','--samples','1'],['--sizes','1,1','--samples','1,1']]
        for option in options:
            with self.subTest(option=option),patch.object(sys,'argv',['measure','--goose','/absent',*option]),patch.object(measure,'build') as build,patch('sys.stderr'):
                with self.assertRaises(SystemExit):measure.main()
                build.assert_not_called()

    def test_hung_child_and_descendant_terminate_and_diagnostics_survive(self):
        with tempfile.TemporaryDirectory() as raw:
            folder=Path(raw)
            child_source=('import subprocess,sys,time;from pathlib import Path;'
                          'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
                          'Path(sys.argv[1]).write_text(str(p.pid));print("started",flush=True);time.sleep(30)')
            with self.assertRaises(subprocess.TimeoutExpired):
                measure.run_process([sys.executable,'-c',child_source,str(folder/'pid')],os.environ,folder,2)
            self.assertIn(b'started',(folder/'stdout').read_bytes())
            pid=int((folder/'pid').read_text())
            import time
            deadline=time.monotonic()+2
            terminated=False
            try:
                while True:
                    try:fields=Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()
                    except FileNotFoundError:
                        terminated=True
                        break
                    if fields and fields[0] in ('Z','X'):
                        terminated=True
                        break
                    if time.monotonic()>deadline:self.fail('live descendant after timeout')
                    time.sleep(.01)
            finally:
                if not terminated:
                    import signal
                    try:os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
            self.assertEqual(json.loads((folder/'process.json').read_text())['failure'],'TimeoutExpired')

    def test_success_requires_consistent_counters(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as raw:
            outcome={'stdout':b'artifact: stage=None publication=Applied received_bytes=3 written_bytes=4 residue_may_remain=false\n',
                     'stderr':b'', 'elapsed_ns':1, 'peak':0, 'returncode':0}
            with patch.object(measure,'run_process',return_value=outcome),self.assertRaisesRegex(RuntimeError,'counters'):
                measure.sample(SimpleNamespace(size=0,requests=[]),Path('/unused'),Path('/unused'),
                    SimpleNamespace(sign=lambda data:b'signature'),'key','https://localhost:1/payload',
                    Path(raw),4,4,'hash','success')

    def test_interruption_reaps_leader(self):
        with tempfile.TemporaryDirectory() as raw:
            folder=Path(raw)
            with patch.object(measure,'peak_rss_kib',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    measure.run_process([sys.executable,'-c','import time;time.sleep(30)'],os.environ,folder,2)
            state=json.loads((folder/'process.json').read_text())
            self.assertEqual(state['failure'],'KeyboardInterrupt')
            with self.assertRaises(ChildProcessError):os.waitpid(state['pid'],os.WNOHANG)

    def test_large_diagnostic_is_rejected_and_retained(self):
        with tempfile.TemporaryDirectory() as raw:
            folder=Path(raw)
            with self.assertRaisesRegex(RuntimeError,'diagnostic'):
                measure.run_process([sys.executable,'-c','print("x"*70000)'],os.environ,folder,2)
            self.assertGreater((folder/'stdout').stat().st_size,65536)


if __name__=='__main__':unittest.main()
