"""Installed 32/64-bit Steam namespace selection; synthetic /proc only."""
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'loader'))
from moonloader.launch import host_pid


class SteamClientTests(unittest.TestCase):
    def test_current_nested_client_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as folder:
            proc=Path(folder);steam=proc/'Steam'
            def process(pid,parent,executable):
                path=proc/str(pid);path.mkdir(exist_ok=True)
                (path/'cmdline').write_bytes(str(executable).encode()+b'\0-silent\0')
                (path/'stat').write_text(f'{pid} (Steam (client)) S {parent} 0 0')
            with self.assertRaises(ValueError):host_pid(steam,proc_root=proc)
            process(10,1,steam/'ubuntu12_32/steam');self.assertEqual(host_pid(steam,proc_root=proc),10)
            (proc/'10/cmdline').write_bytes(b'')
            process(20,1,steam/'steamrt64/steam');process(30,20,'/runtime/launcher');process(40,30,steam/'steamrt64/steam')
            self.assertEqual(host_pid(steam,proc_root=proc),40)
            process(50,1,steam/'steamrt64/steam')
            with self.assertRaises(ValueError):host_pid(steam,proc_root=proc)
            (proc/'50/cmdline').write_bytes(b'/other/Steam/steamrt64/steam\0')
            self.assertEqual(host_pid(steam,proc_root=proc),40)
            # Pressure Vessel's client can be reparented outside the bootstrap
            # ancestry. Its namespace-relative pidfile remains authoritative.
            process(40,1,steam/'steamrt64/steam')
            for pid,inner in ((20,33),(40,139)):
                p=proc/str(pid);(p/'status').write_text(f'NSpid:\t{pid}\t{inner}\n')
                target=p/'root'/Path.home().relative_to('/')/'.steam/steam.pid'
                target.parent.mkdir(parents=True);target.write_text('139\n')
            self.assertEqual(host_pid(steam,proc_root=proc),40)
            (proc/'40/status').write_text('NSpid:\t40\t140\n')
            with self.assertRaises(ValueError):host_pid(steam,proc_root=proc)


if __name__=='__main__':unittest.main()
