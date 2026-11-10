"""Focused desktop/package/host-native tests. Never starts Wine, Steam or Unity."""
import copy
import zlib
import struct
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

def png_chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
PNG=b'\x89PNG\r\n\x1a\n'+png_chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+png_chunk(b'IDAT',zlib.compress(b'\0\x80\xa0\xc0\xff'))+png_chunk(b'IEND',b'')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'loader'))
from moonloader import discovery,packages,launch
from moonloader.storage import load,write,contained,locked
from moonloader.service import Service


def descriptor(name='test-mod'):
    return {'schema':packages.SCHEMA,'id':name,'version':'1.0.0','name':'Test mod','summary':'A host fixture',
            'description':'Original synthetic host test only','author':'Tests','kind':'native','abi':'MoonLab_ModStart/v1',
            'entry':'mod.dll','icon':'icon.png','requires':[],'conflicts':[],'claims':[],
            'game':{'id':'moon-sweepers','appid':'5335510','hashes':{'GameAssembly.dll':'a'*64}},'files':{}}


def package(path,name='test-mod',extra=None):
    files={'mod.dll':b'MZ fixture','icon.png':PNG};files.update(extra or {})
    manifest=descriptor(name);manifest['files']={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('manifest.json',json.dumps(manifest))
        for name,data in files.items(): archive.writestr(name,data)
    return manifest


class LoaderChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_vdf_escaped_windows_and_nested(self):
        value=discovery.vdf(r'"libraryfolders" {"0" {"path" "D:\\Steam Library" "apps" {"5335510" "1"}}}')
        self.assertEqual(value['libraryfolders']['0']['path'],r'D:\Steam Library')
        with self.assertRaises(ValueError): discovery.vdf('"a" {')

    def test_secondary_library_discovered_not_other_app(self):
        steam=self.root/'Steam';library=self.root/'Other Library';(steam/'steamapps').mkdir(parents=True)
        (steam/'steamapps/libraryfolders.vdf').write_text('"libraryfolders" {"1" {"path" "'+str(library)+'"}}')
        (library/'steamapps/common/Moon Sweepers').mkdir(parents=True);(library/'steamapps/common/Moon Sweepers/MoonSweepers.exe').write_bytes(b'MZ')
        (library/'steamapps/appmanifest_5335510.acf').write_text('"AppState" {"appid" "5335510" "installdir" "Moon Sweepers"}')
        found,errors=discovery.discover([steam]);self.assertFalse(errors);self.assertEqual(len(found),1);self.assertEqual(found[0].steam_root,str(steam))
        self.assertEqual(discovery.discover([self.root/'Missing'])[0],[])

    def test_malformed_and_traversal_steam_manifest(self):
        steam=self.root/'Steam';(steam/'steamapps').mkdir(parents=True)
        (steam/'steamapps/appmanifest_5335510.acf').write_text('"AppState" {"appid" "5335510" "installdir" "../escape"}')
        found,errors=discovery.discover([steam]);self.assertFalse(found);self.assertTrue(errors)

    def test_manual_executable_and_wrong_game(self):
        game=self.root/'Manual';game.mkdir();(game/'MoonSweepers.exe').write_bytes(b'MZ')
        self.assertEqual(discovery.manual(game/'MoonSweepers.exe').path,str(game))
        with self.assertRaises(ValueError): discovery.manual(self.root)

    def test_mono_and_unknown_build_rejected(self):
        game=self.root/'game';game.mkdir();(game/'MoonSweepers.exe').write_bytes(b'MZ')
        self.assertFalse(discovery.inspect(discovery.Installation(str(game)))['compatible'])
        folder=game/'MoonSweepers_Data/Managed';folder.mkdir(parents=True);(folder/'Assembly-CSharp.dll').write_bytes(b'MZ')
        self.assertIn('Mono',discovery.inspect(discovery.Installation(str(game)))['reason'])

    def test_package_install_idempotence_and_changed_bytes(self):
        path=self.root/'mod.msmod';package(path)
        location,_=packages.install(path,self.root/'data');self.assertEqual(packages.install(path,self.root/'data')[0],location)
        installed=self.root/'data/library'/location;(installed/'mod.dll').write_bytes(b'changed')
        with self.assertRaises(ValueError): packages.installed(installed)

    def test_unlisted_checksum_symlink_and_duplicate_intake(self):
        path=self.root/'mod.msmod';package(path)
        with zipfile.ZipFile(path,'a') as archive: archive.writestr('extra.txt','bad')
        with self.assertRaises(ValueError): packages.examine(path)
        package(path)
        with zipfile.ZipFile(path,'a') as archive: archive.writestr('MOD.DLL','duplicate')
        with self.assertRaises(ValueError): packages.examine(path)
        package(path)
        with zipfile.ZipFile(path,'a') as archive:
            info=zipfile.ZipInfo('link');info.external_attr=(0o120777)<<16;archive.writestr(info,'target')
        with self.assertRaises(ValueError): packages.examine(path)

    def test_portable_path_rejections(self):
        from moonloader.storage import relative
        for name in ('../escape','/absolute','a//b','a/./b','CON.txt','a:stream','a\\b','x.','x ','LPT1','a?b'):
            with self.subTest(name=name),self.assertRaises(ValueError):relative(name)
        (self.root/'alias').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):contained(self.root,'alias/file')

    def test_dependencies_conflicts_claims_and_cycles(self):
        first=descriptor('first');second=descriptor('second');second['requires']=['first']
        mods={'first':first,'second':second};pins={'GameAssembly.dll':'a'*64}
        self.assertEqual(packages.resolve(mods,['second','first'],pins),['first','second'])
        with self.assertRaises(ValueError):packages.resolve(mods,['second'],pins)
        second['requires']=[];second['conflicts']=['first']
        with self.assertRaises(ValueError):packages.resolve(mods,['first','second'],pins)
        second['conflicts']=[];first['claims']=second['claims']=['MoonWalker.Update']
        with self.assertRaises(ValueError):packages.resolve(mods,['first','second'],pins)
        first['claims']=second['claims']=[];first['requires']=['second'];second['requires']=['first']
        with self.assertRaises(ValueError):packages.resolve(mods,['first','second'],pins)
        with self.assertRaises(ValueError):packages.resolve(mods,[],pins)

    def test_shared_update_and_legacy_exclusive_boundaries(self):
        first=descriptor('first');second=descriptor('second');pins=first['game']['hashes']
        for mod in (first,second):
            mod.update(abi='MoonLab_ModStart/v2',shared_claims=['MoonWalker.Update'],files={'mod.dll':'a'*64,'icon.png':'b'*64})
            packages.validate(mod)
        mods={'first':first,'second':second}
        self.assertEqual(packages.resolve(mods,['second','first'],pins),['first','second'])
        for legacy,shared in ((first,second),(second,first)):
            legacy.update(abi='MoonLab_ModStart/v1',claims=['MoonWalker.Update'],shared_claims=[])
            with self.assertRaises(ValueError):packages.resolve(mods,['first','second'],pins)
            legacy.update(abi='MoonLab_ModStart/v2',claims=[],shared_claims=['MoonWalker.Update'])
        first['claims']=second['claims']=['MoonPrototypeVehicle.FixedUpdate']
        with self.assertRaises(ValueError):packages.resolve(mods,['first','second'],pins)
        first['abi']='MoonLab_ModStart/v1'
        with self.assertRaises(ValueError):packages.validate(first)
        first.update(abi='MoonLab_ModStart/v2',shared_claims=['MoonPrototypeVehicle.FixedUpdate'])
        with self.assertRaises(ValueError):packages.validate(first)

    def test_late_update_roles_and_legacy_hooks(self):
        first=descriptor('first');second=descriptor('second');pins=first['game']['hashes']
        for mod,role in ((first,'observer'),(second,'override')):
            mod.update(abi='MoonLab_ModStart/v4',shared_claims=['MoonWalker.Update','MoonWalker.LateUpdate'],late_update_hook=role,files={'mod.dll':'a'*64,'icon.png':'b'*64})
            packages.validate(mod)
        mods={'first':first,'second':second}
        self.assertEqual(packages.resolve(mods,list(mods),pins),['first','second'])
        first['late_update_hook']='override'
        with self.assertRaisesRegex(ValueError,'Multiple LateUpdate'):packages.resolve(mods,list(mods),pins)
        first.update(late_update_hook='observer',abi='MoonLab_ModStart/v3')
        with self.assertRaisesRegex(ValueError,'Shared LateUpdate requires v4'):packages.validate(first)
        first.update(abi='MoonLab_ModStart/v4',claims=['MoonWalker.LateUpdate'],shared_claims=[])
        with self.assertRaises(ValueError):packages.resolve(mods,list(mods),pins)
        with self.assertRaises(ValueError):packages.resolve(mods,list(reversed(mods)),pins)

    def test_vehicle_roles_and_legacy_hooks(self):
        first=descriptor('first');second=descriptor('second');pins=first['game']['hashes']
        for mod,role in ((first,'input'),(second,'physics')):
            mod.update(abi='MoonLab_ModStart/v3',vehicle_hook=role,files={'mod.dll':'a'*64,'icon.png':'b'*64})
            packages.validate(mod)
        mods={'first':first,'second':second}
        self.assertEqual(packages.resolve(mods,['second','first'],pins),['first','second'])
        second['vehicle_hook']='input'
        with self.assertRaisesRegex(ValueError,'Multiple vehicle'):packages.resolve(mods,list(mods),pins)
        second['vehicle_hook']='physics'
        for legacy in (first,second):
            role=legacy.pop('vehicle_hook');legacy['claims']=['MoonPrototypeVehicle.FixedUpdate']
            with self.assertRaises(ValueError):packages.resolve(mods,list(mods),pins)
            legacy.update(claims=[],vehicle_hook=role)
        for invalid in ('both','',None):
            first['vehicle_hook']=invalid
            with self.assertRaises(ValueError):packages.validate(first)
        first.update(vehicle_hook='input',abi='MoonLab_ModStart/v2')
        with self.assertRaises(ValueError):packages.validate(first)

    def test_shared_dispatch_machine_contexts(self):
        output=self.root/'dispatch-checks'
        subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror',str(ROOT/'tests/native_dispatch_checks.c'),'-o',str(output)],check=True)
        subprocess.run([str(output)],check=True,capture_output=True)

    def test_state_and_selection_persist(self):
        path=self.root/'mod.msmod';package(path);data=self.root/'data'
        service=Service(data,self.root/'bundle');service.import_package(path,True)
        restored=Service(data,self.root/'bundle');self.assertEqual(restored.state['selected'],['test-mod']);self.assertIn('test-mod',restored.library()[0])
        restored.remove('test-mod');self.assertFalse(restored.state['selected']);self.assertTrue(list((data/'library').rglob('mod.dll')))

    def test_hook_framework_registry(self):
        output=self.root/'hook-framework-checks'
        subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror',str(ROOT/'tests/native_hook_framework_checks.c'),'-o',str(output)],check=True)
        subprocess.run([str(output)],check=True,capture_output=True)

    def test_hook_framework_manifest_contract(self):
        mod=descriptor();mod.update(abi='MoonLab_ModStart/v5',shared_claims=['MoonWalker.Update'],files={'mod.dll':'a'*64,'icon.png':'b'*64},hook_framework_abi=1)
        packages.validate(mod)
        for invalid in (True,False,0,2,'1',None):
            mod['hook_framework_abi']=invalid
            with self.assertRaisesRegex(ValueError,'Hook framework'):packages.validate(mod)
        mod.pop('hook_framework_abi')
        with self.assertRaisesRegex(ValueError,'Hook framework'):packages.validate(mod)
        mod.update(hook_framework_abi=1,abi='MoonLab_ModStart/v2')
        with self.assertRaisesRegex(ValueError,'Hook framework'):packages.validate(mod)
        mod.update(abi='MoonLab_ModStart/v5')
        mod.update(hook_framework_abi=1,shared_claims=[])
        with self.assertRaisesRegex(ValueError,'Hook framework'):packages.validate(mod)

    def test_hook_framework_requires_runtime_before_copy(self):
        service,installation=self.prepared_fixture()
        order,library=service.selected(installation)
        library['test-mod'][0].update(abi='MoonLab_ModStart/v5',shared_claims=['MoonWalker.Update'],hook_framework_abi=1)
        receipt=service.bundle/'runtime/receipt.json'
        runtime=load(receipt);runtime['shared_update_abi']=1;write(receipt,runtime)
        with patch.object(service,'selected',return_value=(order,library)):
            with self.assertRaisesRegex(ValueError,'hook framework ABI 1'):service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())
        runtime['hook_framework_abi']=1;write(receipt,runtime)
        with patch.object(service,'selected',return_value=(order,library)):
            root=service.prepare(installation)
        self.assertTrue((root/'game/MoonLab/mods/test-mod/mod.dll').is_file())

    def test_lock_prevents_simultaneous_writes(self):
        with locked(self.root/'data'):
            with self.assertRaises(ValueError):
                with locked(self.root/'data'):pass

    def test_plan_windows_is_explicit_no_spawn(self):
        service=Service(self.root/'data',self.root/'bundle');installation=discovery.Installation(str(self.root/'source'),'steam','C:/Steam')
        service.set_mode(installation, 'private')
        with patch.object(service,'selected',return_value=(['test-mod'],{'test-mod':(descriptor(),self.root/'fixture')})),patch('subprocess.Popen') as spawn:
            record=launch.plan(service,installation,platform='win32')
        spawn.assert_not_called();self.assertEqual(record['env']['SteamAppId'],'5335510')
        self.assertIn('profile',record['env']['MOONLAB_PROFILE_ROOT']);self.assertNotIn('MOONLAB_TEST_TOOLS',record['env'])
        self.assertTrue(record['command'][0].endswith('MoonSweepers.exe'))

    def test_nonsteam_linux_requires_separate_adapter(self):
        service=Service(self.root/'data',self.root/'bundle')
        service.state['default_mode'] = 'private'
        with patch.object(service,'selected',return_value=(['test-mod'],{'test-mod':(descriptor(),self.root/'fixture')})):
            with self.assertRaisesRegex(ValueError,'another storefront'):launch.plan(service,discovery.Installation(str(self.root/'source'),'epic'))

    def test_host_native_save_mapping_and_iat_guard(self):
        output=self.root/'native-checks'
        subprocess.run(['clang','-std=c11','-fshort-wchar','-Wall','-Wextra','-Werror',str(ROOT/'tests/native_loader_checks.c'),'-o',str(output)],check=True,capture_output=True)
        result=subprocess.run([str(output)],capture_output=True,text=True,check=True)
        self.assertIn('passed',result.stdout)


    def prepared_fixture(self):
        source=self.root/'source';source.mkdir()
        for name in discovery.PIN: (source/name).write_bytes(('original '+name).encode())
        pins={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in discovery.PIN}
        patched=patch.object(discovery,'PIN',pins);patched.start();self.addCleanup(patched.stop)
        bundle=self.root/'bundle';runtime=bundle/'runtime/windows-x64/version.dll';runtime.parent.mkdir(parents=True);runtime.write_bytes(b'new runtime')
        write(bundle/'runtime/receipt.json',{'sha256':hashlib.sha256(runtime.read_bytes()).hexdigest()})
        pkg=self.root/'mod.msmod';manifest=package(pkg);manifest['game']['hashes']=pins
        with zipfile.ZipFile(pkg,'w') as archive:
            archive.writestr('manifest.json',json.dumps(manifest));archive.writestr('mod.dll',b'MZ fixture');archive.writestr('icon.png',PNG)
        service=Service(self.root/'data',bundle);service.import_package(pkg,True)
        installation=discovery.Installation(str(source),'steam',str(self.root/'Steam'))
        service.set_mode(installation, 'private')
        return service,installation

    def test_shared_package_requires_updated_runtime_before_copy(self):
        service,installation=self.prepared_fixture()
        order,library=service.selected(installation)
        library['test-mod'][0].update(abi='MoonLab_ModStart/v2',shared_claims=['MoonWalker.Update'])
        with patch.object(service,'selected',return_value=(order,library)):
            with self.assertRaisesRegex(ValueError,'shared Update runtime'):service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())

    def test_vehicle_role_requires_runtime_before_copy(self):
        service,installation=self.prepared_fixture();order,library=service.selected(installation)
        library['test-mod'][0].update(abi='MoonLab_ModStart/v3',vehicle_hook='input')
        with patch.object(service,'selected',return_value=(order,library)):
            with self.assertRaisesRegex(ValueError,'vehicle adapter runtime'):service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())

    def test_late_update_requires_runtime_before_copy(self):
        service,installation=self.prepared_fixture();order,library=service.selected(installation)
        library['test-mod'][0].update(abi='MoonLab_ModStart/v4',late_update_hook='observer')
        with patch.object(service,'selected',return_value=(order,library)):
            with self.assertRaisesRegex(ValueError,'shared LateUpdate runtime'):service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())

    def test_prepare_is_private_repeatable_and_starts_no_process(self):
        service,installation=self.prepared_fixture()
        with patch('subprocess.Popen') as spawn:
            root=service.prepare(installation);service.prepare(installation)
        spawn.assert_not_called()
        self.assertTrue((root/'game/MoonLab/mods/test-mod/mod.dll').is_file())
        self.assertFalse((Path(installation.path)/'version.dll').exists())
        self.assertFalse((Path(installation.path)/'MoonLab').exists())
        self.assertTrue((root/'profile/AppData/LocalLow').is_dir())
        self.assertIn('Never seed',load(root/'save-origin.json')['policy'])
        (root/'game/GameAssembly.dll').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError,'original file changed'):service.prepare(installation)

    def test_partial_deployment_failure_restores_exact_prior_files(self):
        service,installation=self.prepared_fixture();root=service.prepare(installation)
        old=load(root/'deployment.json');old_version=(root/'game/version.dll').read_bytes()
        replace=os.replace;failed=False
        def interrupt(source,target):
            nonlocal failed
            if str(target).endswith('new-mod.dll') and not failed: failed=True;raise OSError('injected write failure')
            return replace(source,target)
        with patch('moonloader.service.os.replace',side_effect=interrupt):
            with self.assertRaises(OSError):service.deploy(root,{'version.dll':b'new version','new-mod.dll':b'new feature'},['new'])
        self.assertEqual((root/'game/version.dll').read_bytes(),old_version)
        self.assertEqual(load(root/'deployment.json'),old)
        self.assertFalse((root/'game/new-mod.dll').exists());self.assertFalse((root/'pending-deployment.json').exists())

    def test_interrupted_deployment_refuses_unknown_edits(self):
        service,installation=self.prepared_fixture();root=service.prepare(installation)
        before=load(root/'deployment.json');backup=root/'backups/fixture'
        for name in before['files']:
            path=backup/'old'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((root/'game'/name).read_bytes())
        after={'files':{'version.dll':hashlib.sha256(b'new').hexdigest()},'order':['new']}
        write(root/'pending-deployment.json',{'before':before,'after':after,'backup':'backups/fixture'})
        (root/'game/version.dll').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError,'Unknown edit'):service.recover(root)
        (root/'game/version.dll').write_bytes(b'new');service.recover(root)
        self.assertEqual(load(root/'deployment.json'),before)
        self.assertFalse((root/'pending-deployment.json').exists())

    def test_owned_edit_and_unowned_collision_are_preserved(self):
        service,installation=self.prepared_fixture();root=service.prepare(installation)
        feature=root/'game/MoonLab/mods/test-mod/mod.dll';feature.write_bytes(b'edited')
        with self.assertRaises(ValueError):service.prepare(installation)
        self.assertEqual(feature.read_bytes(),b'edited')
        feature.write_bytes(b'MZ fixture')
        (root/'game/unowned.dll').write_bytes(b'personal')
        with self.assertRaisesRegex(ValueError,'Unowned deployment'):service.deploy(root,{'unowned.dll':b'overwrite'},[])
        self.assertEqual((root/'game/unowned.dll').read_bytes(),b'personal')

    def test_live_process_marker_blocks_preparation_without_control(self):
        from moonloader.storage import process_birth,assert_inactive
        service,installation=self.prepared_fixture()
        write(service.root/'active.json',{'pid':os.getpid(),'birth':process_birth(os.getpid())})
        with self.assertRaisesRegex(ValueError,'still running'):service.prepare(installation)
        write(service.root/'active.json',{'pid':os.getpid(),'birth':'different-process'})
        assert_inactive(service.root)

    def test_windows_and_linux_discovery_roots_are_separate(self):
        roots=discovery.steam_roots(self.root,platform='win32',env={'PROGRAMFILES(X86)':'C:/Games'})
        self.assertEqual(str(roots[0]),'C:/Games/Steam')
        roots=discovery.steam_roots(self.root,platform='linux')
        self.assertTrue(any('.var/app/com.valvesoftware.Steam' in str(path) for path in roots))

    def test_gui_checkboxes_views_filter_and_no_launch(self):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from moonloader.ui import Window
        app=QApplication.instance() or QApplication([])
        service,installation=self.prepared_fixture()
        with patch.object(service,'installations',return_value=([installation],[])),patch('moonloader.launch.start') as start:
            window=Window(service,True);window.show();app.processEvents()
            self.assertEqual(window.list.count(),1);self.assertFalse(window.launch_button.isEnabled())
            for mode in ('grid','details','text'):
                window.set_view(mode);app.processEvents();window.list.setFocus()
                QTest.keyClick(window.list,Qt.Key.Key_Space);app.processEvents()
                self.assertFalse(service.state['selected'])
                QTest.keyClick(window.list,Qt.Key.Key_Space);app.processEvents()
                self.assertEqual(service.state['selected'],['test-mod'])
                point=window.list.itemDelegate().checkbox(window.list.visualItemRect(window.list.item(0))).center()
                QTest.mouseClick(window.list.viewport(),Qt.MouseButton.LeftButton,pos=point);app.processEvents()
                self.assertFalse(service.state['selected'])
                QTest.mouseClick(window.list.viewport(),Qt.MouseButton.LeftButton,pos=point);app.processEvents()
                self.assertEqual(service.state['selected'],['test-mod'])
            window.search.setText('missing');self.assertFalse(window.list.count());self.assertTrue(window.empty.isVisible())
            window.search.clear();window.resize(760,650);app.processEvents();self.assertFalse(window.details.isVisible())
            from test_runtime_contracts import managed_package
            source=self.root/'managed-ui.msmod'
            managed_package(source,service.library()[0]['test-mod'][0]['game']['hashes'])
            service.import_package(source,select=False);window.refresh_library();app.processEvents()
            managed_item=next(window.list.item(i) for i in range(window.list.count())
                              if window.list.item(i).data(Qt.ItemDataRole.UserRole)['kind']==packages.MANAGED_KIND)
            window.list.setCurrentItem(managed_item);window.list.setFocus()
            QTest.keyClick(window.list,Qt.Key.Key_Space);app.processEvents()
            self.assertIn('independent-managed',service.state['selected'])
            self.assertFalse(window.prepare_button.isEnabled())
            self.assertIn('Runtime is unavailable',window.message.text())
            window.close();start.assert_not_called()


    def test_grid_wheel_travel_ignores_global_lines_and_preserves_precise_input(self):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt, QPoint, QPointF
        from PySide6.QtGui import QWheelEvent
        from moonloader.ui import Window
        app=QApplication.instance() or QApplication([])
        service,installation=self.prepared_fixture()
        with patch.object(service,'installations',return_value=([installation],[])),patch('moonloader.launch.start') as start:
            window=Window(service,True);self.addCleanup(window.close)
            for _ in range(44):window.list.addItem(window.list.item(0).clone())
            window.set_view('grid');window.show();app.processEvents()
            bar=window.list.verticalScrollBar();selected=list(service.state['selected'])
            def wheel(angle=0,pixel=0):
                view=window.list.viewport();point=QPointF(view.rect().center())
                event=QWheelEvent(point,QPointF(view.mapToGlobal(point.toPoint())),QPoint(0,pixel),QPoint(0,angle),
                    Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
                app.sendEvent(view,event);app.processEvents()
            # The former fix depended on Qt multiplying a scrollbar step by
            # the desktop's wheel-line preference; wheel travel must not.
            bar.setSingleStep(1);bar.setValue(0);wheel(-120)
            self.assertEqual(bar.value(),384)
            bar.setValue(0)
            for _ in range(120):wheel(-1)
            self.assertEqual(bar.value(),384)
            wheel(120);self.assertEqual(bar.value(),0)
            wheel(120);self.assertEqual(bar.value(),0)
            wheel(pixel=-17);self.assertEqual(bar.value(),17)
            wheel(pixel=17);self.assertEqual(bar.value(),0)
            bar.setValue(bar.maximum());wheel(-120);self.assertEqual(bar.value(),bar.maximum())
            window.resize(1050,650);window.list.doItemsLayout();app.processEvents()
            bar.setValue(0);wheel(-120);self.assertEqual(bar.value(),min(384,window.list.viewport().height()))
            self.assertEqual(service.state['selected'],selected);start.assert_not_called()

    def test_launch_boundary_strips_test_tools_and_records_process_ownership(self):
        from types import SimpleNamespace
        service=Service(self.root/'data',self.root/'bundle');installation=discovery.Installation(str(self.root/'source'))
        record={'platform':'win32','command':['private-game.exe'],'env':{'MOONLAB_MODS':'test-mod'},'cwd':str(self.root),
                'run':str(service.root/'runs/fixture'),'runtime':'synthetic host boundary'}
        process=SimpleNamespace(pid=os.getpid())
        with patch('moonloader.launch.plan',return_value=record),patch.object(service,'prepare'),patch.dict(os.environ,{'MOONLAB_TEST_TOOLS':'1'}),patch('subprocess.Popen',return_value=process) as spawn:
            result,_=launch.start(service,installation)
        self.assertNotIn('MOONLAB_TEST_TOOLS',spawn.call_args.kwargs['env'])
        self.assertEqual(load(service.root/'active.json')['state'],'running')
        result._moon_lease.__exit__(None,None,None)

    @unittest.skipIf(os.name=='nt','Wine drive aliases belong to the Linux launcher')
    def test_short_private_profile_drive_is_owned_and_keeps_save_bytes_in_place(self):
        root=self.root/'installation';profile=root/'profile';profile.mkdir(parents=True)
        save=profile/'existing-save';save.write_bytes(b'private progress')
        record={'profile':str(profile),'private_proton':str(root/'proton/runtime')}
        launch.prepare_profile_drive(record);launch.prepare_profile_drive(record)
        alias=root/'proton/pfx/dosdevices/m:'
        self.assertEqual(os.readlink(alias),str(root))
        self.assertEqual((alias/'profile/existing-save').read_bytes(),b'private progress')
        self.assertEqual(save.read_bytes(),b'private progress')
        alias.unlink();alias.symlink_to(self.root)
        with self.assertRaisesRegex(ValueError,'drive changed'):launch.prepare_profile_drive(record)
        self.assertEqual(os.readlink(alias),str(self.root))

    @unittest.skipIf(os.name=='nt','Wine drive aliases belong to the Linux launcher')
    def test_short_profile_drive_refuses_an_unowned_alias(self):
        root=self.root/'installation';(root/'profile').mkdir(parents=True)
        devices=root/'proton/pfx/dosdevices';devices.mkdir(parents=True)
        alias=devices/'m:';alias.symlink_to(root)
        record={'profile':str(root/'profile'),'private_proton':str(root/'proton/runtime')}
        with self.assertRaisesRegex(ValueError,'unowned'):launch.prepare_profile_drive(record)
        self.assertFalse((root/'proton/profile-drive.json').exists())

    def test_exit_notice_uses_named_bootstrap_failure_and_tolerates_partial_logs(self):
        run=self.root/'failed-run';run.mkdir()
        record={'run':str(run),'order':['test-mod']}
        self.assertEqual(launch.failure_detail(record),'')
        (run/'loader.jsonl').write_text('{"case":"mod-started","success":true,"mod":"test-mod"}\n'
            '{"case":"mod-start-failed","success":false,"mod":"test-mod"}\n{"incomplete":')
        self.assertEqual(launch.failure_detail(record),'Mod startup failed: test-mod')
        (run/'loader.jsonl').write_text('x'*70000+'\n{"case":"mod-library-load-failed","success":false,"mod":"unselected"}\n')
        self.assertEqual(launch.failure_detail(record),'Could not load mod DLL')
        (run/'loader.jsonl').write_text('{"case":"load-complete","success":true}\n')
        self.assertEqual(launch.failure_detail(record),'')

    def test_post_spawn_log_failure_keeps_lease_and_starting_guard(self):
        from types import SimpleNamespace
        from moonloader.storage import assert_inactive
        service=Service(self.root/'data',self.root/'bundle');installation=discovery.Installation(str(self.root/'source'))
        record={'platform':'win32','command':['private-game.exe'],'env':{},'cwd':str(self.root),
                'run':str(service.root/'runs/fixture'),'runtime':'synthetic host boundary'}
        process=SimpleNamespace(pid=os.getpid());original_write=write
        def fail_log(path,value):
            if Path(path).name=='process.json':raise OSError('injected full disk')
            return original_write(path,value)
        with patch('moonloader.launch.plan',return_value=record),patch.object(service,'prepare'),patch('subprocess.Popen',return_value=process),patch('moonloader.launch.write',side_effect=fail_log):
            result,observed=launch.start(service,installation)
        self.assertIn('full disk',observed['diagnostic_error']);self.assertEqual(load(service.root/'active.json')['state'],'starting')
        result._moon_lease.__exit__(None,None,None)
        with self.assertRaisesRegex(ValueError,'interrupted launch'):assert_inactive(service.root)


    def test_package_icon_rejects_svg_disguised_as_png_and_giant_dimensions(self):
        path=self.root/'mod.msmod';package(path,extra={'icon.png':b'<svg xmlns="http://www.w3.org/2000/svg"/>'})
        with self.assertRaisesRegex(ValueError,'PNG data'):packages.examine(path)
        import struct
        giant=bytearray(PNG);struct.pack_into('>I',giant,16,100000)
        package(path,extra={'icon.png':bytes(giant)})
        with self.assertRaisesRegex(ValueError,'1024'):packages.examine(path)


    def test_portable_author_packager_is_repeatable_and_refuses_output_overwrite(self):
        from pack_mod import pack
        payload=self.root/'payload';payload.mkdir();(payload/'mod.dll').write_bytes(b'MZ fixture');(payload/'icon.png').write_bytes(PNG)
        manifest=self.root/'catalog.json';write(manifest,descriptor());output=self.root/'built.msmod'
        pack(manifest,payload,output);original=output.read_bytes();pack(manifest,payload,output)
        self.assertEqual(output.read_bytes(),original);self.assertEqual(packages.examine(output)['id'],'test-mod')
        (payload/'mod.dll').write_bytes(b'new build')
        with self.assertRaisesRegex(ValueError,'different package'):pack(manifest,payload,output)


if __name__=='__main__':unittest.main()
