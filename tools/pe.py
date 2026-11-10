"""Bounded PE64 section/export/runtime-function reader (RVA remains explicit)."""
from pathlib import Path
import struct


class PE:
    def __init__(self,path):
        self.data=Path(path).read_bytes();data=self.data
        if data[:2]!=b'MZ':raise ValueError('Not a PE file')
        pe=struct.unpack_from('<I',data,0x3c)[0]
        if data[pe:pe+4]!=b'PE\0\0':raise ValueError('Bad PE signature')
        self.machine,sections=struct.unpack_from('<HH',data,pe+4)
        optional_size=struct.unpack_from('<H',data,pe+20)[0];optional=pe+24
        if struct.unpack_from('<H',data,optional)[0]!=0x20b:raise ValueError('PE32+ required')
        self.base=struct.unpack_from('<Q',data,optional+24)[0]
        self.directories=[struct.unpack_from('<II',data,optional+112+i*8) for i in range(16)]
        self.sections=[]
        for i in range(sections):
            off=optional+optional_size+i*40
            name=data[off:off+8].rstrip(b'\0').decode('ascii',errors='replace')
            size,rva,raw_size,raw=struct.unpack_from('<IIII',data,off+8)
            if raw+raw_size>len(data):raise ValueError('Section exceeds source')
            self.sections.append(dict(name=name,rva=rva,size=size,raw=raw,raw_size=raw_size))
    def offset(self,rva,size=1):
        for s in self.sections:
            delta=rva-s['rva']
            if 0<=delta and delta+size<=s['raw_size']:return s['raw']+delta
        raise ValueError('RVA has no complete raw span: '+hex(rva))
    def bytes(self,rva,size):
        off=self.offset(rva,size);return self.data[off:off+size]
    def string(self,rva):
        off=self.offset(rva);end=self.data.find(b'\0',off,min(len(self.data),off+8192))
        if end<0:raise ValueError('Unterminated PE string')
        return self.data[off:end].decode('utf-8',errors='replace')
    def exports(self):
        rva,size=self.directories[0]
        if not rva:return []
        raw=self.bytes(rva,40)
        base,count,names,functions,name_table,ordinals=struct.unpack_from('<IIIIII',raw,16)
        if count>1000000 or names>count:raise ValueError('Invalid export counts')
        result=[]
        for i in range(names):
            name_rva=struct.unpack('<I',self.bytes(name_table+i*4,4))[0]
            ordinal=struct.unpack('<H',self.bytes(ordinals+i*2,2))[0]
            if ordinal>=count:raise ValueError('Invalid export ordinal')
            target=struct.unpack('<I',self.bytes(functions+ordinal*4,4))[0]
            result.append(dict(name=self.string(name_rva),rva=target,ordinal=base+ordinal,
                               forwarder=self.string(target) if rva<=target<rva+size else None))
        return result
    def runtime_functions(self):
        rva,size=self.directories[3]
        if size%12:raise ValueError('Invalid x64 runtime-function directory')
        return [dict(zip(['begin','end','unwind'],struct.unpack('<III',self.bytes(rva+i,12)))) for i in range(0,size,12)]
