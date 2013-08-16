from pupynere import netcdf_file

from BADCtf import BADCtf,makeBasicDummy

import unittest, uuid, os 

class btncf(netcdf_file):
    ''' A netcdf object with badc text file read write methods as well as nc write'''
    def __init__(self,mode,filename):
        ''' Instantiate as r or w, with filename. If the filename extension is
        .nc, netcdf I/O will be used, if .csv, badc text file I/O will be used. 
        '''
        fext=os.path.splitext(filename)[-1]
        if fext not in ['.nc','.csv']:
            raise ValueError('Unknown filetype for btncf - %s'%fext)
        if fext == '.csv':
            # get a dummy netcdf filename
            cachefile=str(uuid.uuid4())+'.nc'
            netcdf_file.__init__(self,cachefile,'w')
            if mode=='r':
                self.badctf=BADCtf('r',filename)
                self.__unpacktf()
        elif fext == 'nc':
            netcdf_file.__init__(self,mode,filename)
            self.badctf=None
            
        self.filetype=fext
        self.mode=mode
            
    def __unpacktf(self):
        ''' Used to unpack a BADCtf into this netcdf_file instance '''
        assert self.badctf is not None
        # file global attributes
        for a in self.badctf._metadata.globalRecords:
            if len(a)==2:
                setattr(self,a[0],a[1])
            else: setattr(self,a[0],a[1:])
        fvars={}
        # first get attributes into useful dictionary
        for v in self.badctf.colnames():
            attrs=self.badctf._metadata[('*',v)]
            adict={}
            for a in self.badctf._metadata[('*',v)]:
                adict[a[0]]=a[1]
            fvars[v]=adict
        # now load up the coordinate variables first
        index=-1
        dimensions=[]
        # we do this loop first fora future with multiple coordinate 
        # variables
        for v in self.badctf.colnames():
            index+=1
            if 'coordinate_variable' in fvars[v]:
                data=self.badctf[index]
                dlen=len(data)
                dim=self.createDimension(v,dlen)
                dimdata=self.createVariable(v,fvars[v]['type'][0],(v,))
                dimdata[:]=data
                dimensions.append(v)
        # now the assumption with a badc text file is that there is
        # only one coordinate variable.
        assert len(dimensions) == 1, "Code doesn't support multiple coordinate variables"
        index=-1
        for v in self.badctf.colnames():
            index+=1
            if 'coordinate_variable' not in fvars[v]:
                data=self.badctf[index]
                fdata=self.createVariable(v,fvars[v]['type'][0],tuple(dimensions))
                fdata[:]=data
        
    def __packtf(self):
        ''' Used to pack a text file instance from the netcdf variables'''
        # Need to check it's the right kind of feature type ...
        raise NotImplementedError
    
    def close(self):
        ''' Close this instance, which if mode is 'w' means writing
        the data out to a file.'''
        # overridden here just in case we want to do something more.
        netcdf_file.close(self)

    def convert(self):
        ''' If data was read in .nc, write out in .csv and vice versa. 
        '''
        raise NotImplementedError

class test_btncf(unittest.TestCase):
    
    def setUp(self):
        self.data=makeBasicDummy()
        self.dummyfile=str(uuid.uuid4())+'.csv'
        self.data.write(self.dummyfile)
        
    def tearDown(self):
        os.remove(self.dummyfile)
        
    def test_readtf(self):
        ncf=btncf('r',self.dummyfile)
        print ncf.variables
        ncf.close()   # will write a netcdf version out!
        
if __name__=="__main__":
    unittest.main()
        
        
