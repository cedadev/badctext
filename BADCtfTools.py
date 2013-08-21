from pupynere import netcdf_file

from BADCtf import BADCtf,makeBasicDummy

import unittest, uuid, os 

def btf2nc(ncfilename,source_filename=None,badctf=None):
    ''' Convert a badc text file object to a netcdf file object.
        Call by providing an output filename for the netcdf file,
        and one of a source filename or a badctf instance '''
    if source_filename is None and badctf is None:
        raise ValueError('Arguments must include on of a source file or BADCtf instance')
    elif source_filename is not None and badctf is not None:
        raise ValueError('Arguments must include only ONE of a source file or BADCtf instance')
        
    if source_filename is not None:
        tf=BADCtf('r',source_filename)
    else:
        tf=badctf
    
    ncf=netcdf_file(ncfilename,'w')
    
    # file global attributes
    for a in tf._metadata.globalRecords:
        if len(a)==2:
            try:
                t=getattr(ncf,a[0])
                t=';'.join([t,a[1][0]])
                setattr(ncf,a[0],t)
            except AttributeError:
                setattr(ncf,a[0],a[1][0])
        else: setattr(ncf,a[0],a[1:])
        
    fvars={}
    # first get attributes into useful dictionary
    for v in tf.colnames():
        attrs=tf._metadata[('*',v)]
        adict={}
        for a in tf._metadata[('*',v)]:
            adict[a[0]]=a[1]
        fvars[v]=adict
    # now load up the coordinate variables first
    index=-1
    dimensions=[]
    # we do this loop first for a future with multiple coordinate 
    # variables
    for v in tf.colnames():
        index+=1
        if 'coordinate_variable' in fvars[v]:
            data=tf[index]
            dlen=len(data)
            dim=ncf.createDimension(v,dlen)
            dimdata=ncf.createVariable(v,fvars[v]['type'][0],(v,))
            dimdata[:]=data
            dimensions.append(v)
    # now the assumption with a badc text file is that there is
    # only one coordinate variable.
    # not necessarily true for trajectory files, but one thing at a time ...
    assert len(dimensions) == 1, "Code doesn't support multiple coordinate variables"
    index=-1
    for v in tf.colnames():
        index+=1
        if 'coordinate_variable' not in fvars[v]:
            data=tf[index]
            fdata=ncf.createVariable(v,fvars[v]['type'][0],tuple(dimensions))
            fdata[:]=data
    return ncf

    

class test_btncf(unittest.TestCase):
    
    def setUp(self):
        self.data=makeBasicDummy()
        self.dummyfile=str(uuid.uuid4())+'.nc'
       
    def tearDown(self):
        if os.path.exists(self.dummyfile):
            os.remove(self.dummyfile)
        
    def test_readtf(self):
        ncf=btf2nc(self.dummyfile,badctf=self.data)
        x=[n for n in ncf.variables]
        ncf.close()  # will write a netcdf version out!
        n2=netcdf_file(self.dummyfile)
        y=[n for n in n2.variables]
        self.assertEqual(x,y)
        
if __name__=="__main__":
    unittest.main()
        
        
