#
# This module is for reading and writing the simple BADC text file format.
# This file format is based on the comma seperated value (CSV) format 
# that is commonly produced by spreadsheet applications. It also checks 
# to see if certain metadata is available.
#
# SJP 2008-09-22
# BNL 2013-08 Some updates 
#   Issues raised:
#   Date Valid should really be the zero time for the file.

import sys, csv, string
import time, StringIO
import unittest
import os,os.path

# ======================================================================
# Provides the following exceptions
#

class BADCtfError(Exception): 
    pass
class BADCtfParseError(BADCtfError):
    ''' Failed basic conformance to format ''' 
    pass
class BADCtfDataError(BADCtfError):
    ''' Wrong shape data ''' 
    pass
class BADCtfMetadataInvalid(BADCtfError):
    ''' Invalid metadata arguments ''' 
    pass
class BADCtfMetadataIncomplete(BADCtfError): 
    ''' Missing mandatory fields '''
    pass 
class BADCtfMetadataNonstandard(BADCtfMetadataInvalid):
    ''' Metadata arguments not in standard controlled vocabularies '''
    pass

# ======================================================================
# Exploits the following basic checking functions
# each function takes a values tuple and checks it 

def checkAllTypes(values):
    ''' Calls the type checker for the type metadata check '''
    for v in values:
        if v not in ['char','int','float']:
            raise ValueError('Invalid data type')

def checkType(values,func):
    ''' Check that all values are of type func, 
         e.g. checkType([1,2,3],int) should be fine
         checkType([1,2.0],int) should raise an Error
         '''
    # Note that some things may be entered as strings and need conversion
    # and then checking     
    if func is str:
        for v in values:
            if not isinstance(v,str):
                raise ValueError('%s in %s is not %s'%(v,values,func))
    elif func in [int,float]:
            for v in values:
                if not isinstance(v,func):
                    try:
                        i=int(v)
                        f=float(v)
                        if float(i)!=f and func == int: 
                            raise ValueError('%s in %s is not %s'%(v,values,func))
                    except:
                        raise ValueError('%s in %s is not %s'%(v,values,func))
    else: raise ValueError (
		'Unknown type function %s for checkType'%func)
        
def checkLocation(values):
    ''' Check valid location for BADC Text File '''
    if len(values) in [2,4]:
        checkType(values,float)
    elif len(values) == 1:
        checkString(values[0])
    else: raise ValueError('Invalid Location Descriptor')

def checkInt(values):
    ''' Check valid integer '''
    checkType(values,int)

def checkFloat(values):
    ''' Check valid float '''
    checkType(values,float)
    
def checkString(values):
    ''' Check valid string '''
    checkType(values,str)
    
def checkDate(values):
    for v in values:
        time.strptime(v[0:10], "%Y-%m-%d") 

def checkStandardName(values):
    print '%%W: Checking for valid standard names not implemented (%s,%s)'%(values[0],values[1])

def checkHeight(values):
    checkfloat(values[0])

def checkFeatureType(values):
    for v in values:
        if v not in ['point series','trajectory','point collection']:
            raise ValueError('FeatureType [%s] not supported'%v)

def checkCoordinateVariables(values):
    ''' Check that a coordinate variable exists for at least one column '''
    # this is handled elsewhere
    raise NotImplementedError
    
def checkCellMethod(values):
    raise NotImplementedError

def checkConventions(values):
    if values[0] != "BADC-CSV":
        raise BADCtfMetadataInvalid(
			"Conventions must be BADC-CSV, not %s" % values[0])
    if values[1] != "1":
        raise BADCtfMetadataInvalid(
			"Conventions must be 'BADC-CSV, 1', not %s" % values[1])
        
def checkDataType(values):
    v = values[0]
    if v not in ('int', 'float', 'char'):
        raise BADCtfMetadataNonstandard(
			"Type not right must be int, float or char. not %s" % v)

# ======================================================================
# The BADCtf class is the main class for manipulating data.
#
class BADCtf:
    '''
    
    
     MDinfo defines the valid use for the metadata items in the data
     files. The dictionary is keyed on the metadata label and has values
     that correspond to:
       A flag to say if the label can apply globally,
       A flag to say if the label can apply to a column,
       The minimum number of values assosiated with the label
       The maximum number of values assosiated with the label
       A flag to say if the label is manditory for 'basic' files
           (0=not manditory, 
            1=mandatory existence for at least one column, 
            2=must exist for all columns)
       A flag to say if the label is manditory for 'complete' files
           (0=not manditory, 
            1=mandatory existence for at least one column, 
            2=must exist for all columns)
    '''
    MDinfo = {"title":                  (1,0,1,1,0,0,checkString, 
					"A title for the data file"),
              "comments":               (1,1,1,1,0,0,checkString, 
					"Any text associated with data"),
              "location":               (1,1,1,4,0,1,checkLocation, 
					"Location for the data. Can be a name, bounding box, or lat and long values"),
                    #FIXME #ASKSAM Should this *and* observation station both by mandatory?
              "height":                 (1,1,2,2,0,0,checkHeight, 
					"Height valid for data"),
              "creator":                (1,1,1,2,0,1,checkString, 
					"The name of the person and/or institute that created the data"),
              "contributor":            (1,1,1,2,0,0,checkString, 
					"The name of the person and/or institute that contributed to the data"),
              "date_valid":             (1,1,1,2,0,1,checkDate, 
					"The date the data is valid for. Needs to be YYYY-MM-DD form"),
                    #FIXME #ASKSAM Note BNL expects this to be the zero time for time-since time variables.
                    # So, is this metadata name wrong?
              "last_revised_date":      (1,1,1,1,0,1,checkDate, 
					"The date the data was revised or worked up. Needs to be YYYY-MM-DD form"),
              "history":                (1,1,1,1,0,0,checkString, 
					"Text description of the file history"),
              "reference":              (1,1,1,1,0,0,checkString, 
					"Bibliographic reference"),
              "source":                 (1,1,1,1,0,1,checkString, 
					"The name of the tool used to produce the data. e.g. model name or instrument type"),
              "observation_station":    (1,1,1,1,0,1,checkString, 
					"The name of the observation station or instrument platform used"),
              "rights":                 (1,1,1,1,0,0,checkString, 
					"Conditions of use for the data"),
              "activity":               (1,1,1,1,0,1,checkString, 
					"The name of the activity sponsoring the collection of the data "),
              "add_offset":             (0,1,1,1,0,0,checkFloat, 
					"An offset value to add to the values recorded in the data"),
              "scale_factor":           (0,1,1,1,0,0,checkFloat, 
					"A scale factor to multiply the data values by"),
              "valid_min":              (1,1,1,1,0,0,checkFloat, 
					"Values below this value should be interpreted as missing"),
              "valid_max":              (1,1,1,1,0,0,checkFloat, 
					"Values above this value should be interpreted as missing"),
              "valid_range":            (1,1,2,2,0,0,checkFloat, 
					"Values outside this range should be interperated as missing"),
              "long_name":              (0,1,2,2,2,2,checkString, 
					"Description of variable and its unit"),
              "standard_name":          (0,1,3,3,0,0,checkStandardName, 
					"Name of variable from a standard list, with unit and the name of the list"),
              "feature_type":           (1,0,1,1,0,1,checkFeatureType, 
					"type of feature: point series, trajectory or point collection"),
              "coordinate_variable":    (0,1,0,2,1,1,checkInt, 
					"Flag to show which colume(s) are regarded as coordinate variables"),
              "Conventions":            (1,0,2,2,1,1,checkConventions, 
					"Metadata conventions used. Must be BADC-CSV, 1"),
              "type":                   (0,1,1,1,0,2,checkAllTypes, 
					"The type of the variables in a column. Should be char, int or float"),
              "cell_method":            (1,1,1,4,0,0,checkCellMethod, 
					"The cell method used in preparing the data")}

    def __init__(self, mode='w',filename='',):
        ''' Instantiate a BADCText file, default mode is to create
        a new instance ready for writing. (In which case don't provide
        a filename  - only provide a filename if reading an existing
        instance. '''
        
        if mode not in ['r','w']:
            raise BADCtfError('Cannot instantiate with mode %s'%mode)
        if mode=='w' and filename<>'':
            raise BADCtfError('Do not instantiate in write mode with a filename')
        
        self.mode=mode
        self._data = BADCtfData()
        self._metadata = BADCtfMetadata()
        
        if self.mode == 'r':
            self._parse(filename)
            self._check_valid()
        else:
            self.version='1'
            self.add_metadata('Conventions',('BADC-CSV', '1'),'G')
            
    def __eq__(self,other):
        return self._metadata==other._metadata
        
    def __ne__(self,other):
        return not self==other

    def _parse(self,filename):
        ''' Parse file filename to populate this instance. ''' 
        self.fh=open(filename,'r')
        reader = csv.reader(self.fh)
        section = 1
        for row in reader:
          try:
            # section 1 is the metadata section 
            if section == 1:
                while row[-1] == '': row=row[:-1] # remove blank cells
                if len(row) == 0: continue        # ignore blank lines
                elif len(row) == 1:
                    if row[0].lower() == 'data':
                        section = 2
                        continue
                else:
                    label, ref, values = row[0], row[1], row[2:]
                    values = tuple(values)
                    self.add_metadata(label,values,ref) 

            # section 2 the column names
            elif section == 2:
                while row[-1] == '': row=row[:-1] # remove blank cells
                for colname in row:
                    self.add_variable(colname)
                section = 3

            # section 3 is the data section 
            elif section == 3:
                while row[-1] == '': row=row[:-1] # remove blank cells
                if len(row) == 0: continue        # ignore blank lines
                elif len(row) == 1: 
                    if row[0].lower() == 'end data':
                        return
                else:
                    # data row
                    self.add_datarecord(row) 

          except BADCtfError:
              print row
              raise 

    def _check_valid(self):
        ''' Check content of this instance is valid '''
        for label in BADCtf.MDinfo:
            applyg, applyc, mino, maxo, mandb, mandc, check, meaning = BADCtf.MDinfo[label]

            # if label can't apply globally but is defined raise error 
            if not applyg and self[label] != []:
                raise BADCtfMetadataInvalid("Not allowed as global metadata parameter: %s, %s" %(label, self[label]))
            # if label can't apply to column but is defined raise error 
            if not applyc and self[label] == []:
                for colname in self.colnames():
                    if self[label,colname] != []: 
                        raise BADCtfMetadataInvalid("Given metadata not allowed for a column: %s, %s, %s" %(label, colname, self[label,colname]))
            # values have wong number of feilds 
            for values in self[label]:
                if len(values) > maxo:
                    raise BADCtfMetadataInvalid("Max number of metadata fields (%s) exceeded for %s: %s" % (maxo, label, values))
                if len(values) < mino:
                    raise BADCtfMetadataInvalid("Min number of metadata fields (%s) not given for %s: %s" % (mino, label, values,))
            for colname in self.colnames():
              for values in self[label,colname]:
                if len(values) > maxo:
                    raise BADCtfMetadataInvalid("Max number of metadata fields (%s) exceeded for %s: %s" % (maxo, label, values,))
                if len(values) < mino:
                    raise BADCtfMetadataInvalid("Min number of metadata fields (%s) not given for %s: %s" % (mino, label, values,))

            #see if values are OK
            for values in self[label]:
                try: 
                    check(values)
                except:
                    raise BADCtfMetadataInvalid("Metadata field values invalid %s: %s  [%s]" % (label, values,sys.exc_value))    
            for colname in self.colnames():
                for values in self[label,colname]:
                    check(values)

    def _check_complete(self, level='basic'):
        ''' Check content of this instance is complete '''
        self._check_valid()
        for label in BADCtf.MDinfo:
            applyg, applyc, mino, maxo, mandb, mandc, check, meaning = BADCtf.MDinfo[label]

            # find level for check
            if level=='basic': mand = mandb
            else: mand = mandc

            #if its not manditory skip
            if not mand:
                continue

            # if applies globally then there should be a global record or
            # one at least one variable
            if applyg:
              if self[label] != []:
                  #found global value. next label
                  continue
              for colname in self.colnames():
                  if self[label,colname] != []:
                      break
              else:
                  raise BADCtfMetadataIncomplete("Basic global metadata not there: %s" % label)
                  
            # if applies to column only then there should be a record for
            # each variable
            elif applyc and mand==2:
              for colname in self.colnames():
                  if self[label,colname] == []: 
                      raise BADCtfMetadataIncomplete(
                        'Basic column metadata not there: "%s" not there for %s' % (label, colname))

        # if one needs to exist in a column, check that at least one exists
        for label in ['coordinate_variable']:
            r=self._metadata[(label,'*')]
            if r==[]: raise BADCtfMetadataIncomplete(
                        'At least one column needs to have %s information'%label)

    def colnames(self):
        ''' Return names of data columns '''
        return tuple(self._data.colnames)

    def nvar(self):
        ''' return number of variables in file '''
        return self._data.nvar()

    def __len__(self):
        ''' Return length of data columns'''
        return len(self._data)

    def __getitem__(self, i):
        # -- ref change
        if type(i) == int:
            return self._data[i]
        else:
            return self._metadata[i]
        
    def add_variable(self,colname,data=()):
        # -- ref change
        self._data.add_variable(colname, data)

    def add_datarecord(self, datavalues):
        self._data.add_data_row(datavalues)

    def add_metadata(self, label, values, ref='G'):
        self._metadata.add_record(label, values, ref)
        
    def __repr__(self):
        return self._csv()

    def _csv(self):
        ''' Create comma separated value string view of content '''
        s = StringIO.StringIO()
        csvwriter = csv.writer(s, lineterminator='\n' )
        self._metadata.csv(csvwriter)
        self._data.csv(csvwriter)
        return s.getvalue() 

    def write(self,filename,fmt='csv'):
        ''' Write output to filename in format (fmt) cvs or cdl '''
        if fmt == 'csv':
            s=self._csv()
        elif fmt =='cdl':
            s=self._cdl()
        elif fmt=='na':
            s=self._NASA_Ames()
        else:  raise BADCTextError('Invalid format %s for writing'%sfmt)
        f=file(filename,'w')
        f.write(s)

    def _cdl(self):
        ''' Create a CDL file (possibly to make NetCDF) '''
        s = "// This CDL file was generated from a BADC text file file\n"
        s = s + "netcdf foo { \n"
     
        s = s + "dimensions:\n   point = %s;\n\n" % len(self) 
     
        s = s + "variables: \n"
        for colname in self.colnames():
            varname = "%s" % colname
            vartype = self['type', colname][0][0]
            s = s + "    %s %s(point);\n" % (vartype, varname)
        s = s + "\n"
            
        s = s + self._metadata.cdl()
        s = s + "\n"
        
        s = s + "data:\n\n"
        for i in range(self.nvar()):
            varname = "%s" % self._data.colnames[i]
            values = str(self[i])
            s =s + "%s = %s;\n" % (varname, values)
        s = s + "}\n"

        return s

    def _NASA_Ames(self):
        # create a NASA-Ames file 1001 FFI
        header = []

        # find creator and institute
        c = ''
        inst = ''
        for creator in self['creator']:
            c = c + creator[0] +  '; '
            # bnl doesn't like this assumption about creator structure
            if len(creator) == 2: 
                inst = inst +  creator[1] +  '; '
        if inst == '': inst = 'Unknown'
        header.append(c[:-2])
        header.append(inst[:-2])

        # find source (DPT)
        s = ''
        for source in self['source']:
            s = s + source[0] +  '; '
        header.append(s[:-2])
    
        # find activity
        a = ''
        for activity in self['activity']:
            a = a + activity[0] +  '; '
        header.append(a[:-2])
    
        # disk 1 of 1
        header.append("1 1")
    
        # dates 
        date_valid = self['date_valid']
        date_valid = min(date_valid)
        date_valid = date_valid[0]
        date_valid = date_valid.replace('-', ' ')
        last_revised_date = self['last_revised_date']
        last_revised_date = min(last_revised_date)
        last_revised_date = last_revised_date[0]
        last_revised_date = last_revised_date.replace('-', ' ')
        header.append("%s    %s" % (date_valid, last_revised_date))
    
        # ??
        header.append('0.0')
    
        # coord variable
        cvars=[]
        for v in self.colnames():
            r=self._metadata[('coordinate_variable',v)]
            if len(r)<>0: cvars.append(v)
        assert len(cvars)>0,'No coordinate variable, cannot convert to NA!'
        assert len(cvars)==1,'Cannot yet convert to NA (too many coordinate variables)'
       
        # FIXME: #ASKSAM What should this look like? 
        coord=self._metadata[('long_name',cvars[0])]
        header.append('%s (%s)' %coord[0])
        
        # number of variables not coord variable
        header.append("%s" % (self.nvar()-1)) 
    
        #scale factors
        sf_line = ''
        for i in range(1,self.nvar()):
            sf = self['scale_factor',i]
            if len(sf)==0: sf = "1.0"
            else: sf = sf[0][0]
            sf_line = sf_line + "%s " % sf
        header.append(sf_line)
    
        #scale factors
        max_line = ''
        for i in range(1,self.nvar()):
            vm = self['valid_max',i]
            if len(vm)==0: vm = "1.0e99"
            else: vm = vm[0][0]
            vr = self['valid_range',i]
            if len(vr)==0: vr = "1.0e99"
            else: vr = vr[0][1]
            vm = min(float(vm), float(vr))
            max_line = max_line + "%s " % vm
        header.append(max_line)
    
        # variable names
        long_names=self._metadata[('long_name','*')]
        for name in long_names:
            if name not in cvars:
                long_name = "%s (%s)" % name
                header.append(long_name)

        # normal comments
        header.append('1')
        header.append('File created from BADC text file')
    
        # special comments - all metadata to go in 
        s = StringIO.StringIO()
        cvswriter = csv.writer(s)
        self._metadata.csv(cvswriter)
        metadata = s.getvalue()
        nlines = metadata.count('\n')
        header.append("%s" % (nlines+2))
        header.append("BADC-CSV style metadata:")
        header.append(s.getvalue()) 
    
        # make header
        header="%s 1001\n%s" % (len(header)+nlines, string.join(header,'\n'))

        # data space separated
        data = ''
        for i in range(len(self)):
            data = data + ' '.join([str(i) for i in self._data.getrow(i)]) + '\n'
    
        return header+data
        
    
class BADCtfData:
    ''' Class to hold data in the files
        BADCtfData is an aggregation of variables
        '''
    def __init__(self): 
        self.variables = []
        self.colnames = []
        
    def add_variable(self, name, values):
        if len(self.variables) == 0 or len(values) == len(self.variables[0]):
            self.variables.append(BADCtfVariable(values))
            self.colnames.append(name)
        else:
            raise BADCtfError("Wrong length of data")

    def add_data_row(self, values):
        if self.nvar() == 0 and len(values) != 0:
            for v in values:
                self.variables.append(BADCtfVariable((v,)))
        elif self.nvar() == len(values):
            for i in range(len(values)):
                self.variables[i].append(values[i])
        else:
            raise BADCtfError("Wrong length of data")

    def __len__(self):
        # number of data rows
        if len(self.variables) == 0:
            return 0
        else:
            return len(self.variables[0])

    def nvar(self):
        # number of varibles
        return len(self.variables)

    def __getitem__(self, i):
        if type(i) == int:
            return self.variables[i].values
        else:
            col, row = i
            return self.variables[col][row]

    def getrow(self,i):
        row = []
        for j in range(self.nvar()):
            row.append(self.variables[j][i])
        return row
        
    def csv(self, csvwriter):
        csvwriter.writerow(('Data',))
        csvwriter.writerow(self.colnames)
        for i in range(len(self)):
            csvwriter.writerow(self.getrow(i))
        csvwriter.writerow(('End Data',))

class BADCtfVariable:
    ''' class to hold 1D data '''
	    
    def __init__(self, values=[]):
        self.set_values(values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, i):
        return self.values[i]

    def append(self,v):
        self.values.append(v)

    def set_values(self, values):
        self.values = list(values)

        
class BADCtfMetadata:
    ''' Holds the text file metadata. '''
    
    def __init__(self):
        # records use label as key, with value as content
        self.globalRecords = []
        self.varRecords = []

    def __getitem__(self, i):
        # if the item is selected with a label and a column name then
        # use get the metadata record for the column. otherwise use expect the
        # metadata label for global
        val = []
        if type(i) == tuple:
            lab, col = i
            for label, value in self.globalRecords:
                if lab ==label:
                    val.append(value)

            for label, column, value in self.varRecords:
                if (lab == label) and (col==column or col=='*'):
                    val.append(value) 
                elif (lab =='*') and (col==column):
                    val.append((label,value))
        else:
            lab = i
            for label, value in self.globalRecords:
                if lab ==label:
                    val.append(value)
        return val

    def __eq__(self,other):
        ''' test metadata equivalence '''
        g=self.globalRecords==other.globalRecords
        c=self.varRecords==other.varRecords
        return g and c
        
    def __ne__(self,other):
        ''' test lack of metadata equivalence '''
        return not self==other

    def add_record(self, label, values, ref='G'):
        '''  Add records '''
        if type(values) != tuple: values = (values,)
        if type(ref)== str and ref=='G':
            self.globalRecords.append((label,values))
        elif type(ref) ==str:
            self.varRecords.append((label,ref,values))        
           
    def cdl(self):
        # return cdl representation of metadata
        s = "// variable attributes\n"
        # make sure labels are unique for netCDF. e.g. creator, creator1, creator2
        used_labels = {}
        for label, column, values in self.varRecords:
            if used_labels.has_key((label,column)):
                use_label = "%s%s" % (label, used_labels[label,column])
                used_labels[label, column] = used_labels[label, column]+1
            else:
                use_label = label
                used_labels[label, column] = 1
            value = string.join(values, ', ')
            s =s+'        %s:%s = "%s";\n' % (column, use_label, value)

        s=s+"\n// global attributes\n"
        used_labels = {}
        for label, values in self.globalRecords:
            if used_labels.has_key(label):
                use_label = "%s%s" % (label, used_labels[label])
                used_labels[label] = used_labels[label]+1
            else:
                use_label = label
                used_labels[label] = 1        
            value = string.join(values, ', ')
            s=s+'        :%s = "%s";\n' % (use_label, value)
        return s

    def csv(self, csvwriter):
        for label, values in self.globalRecords:
            csvwriter.writerow((label,'G') + values)
        for label, ref, values in self.varRecords:
            csvwriter.writerow((label,ref) + values)
            
    def __repr__(self):
        s = StringIO.StringIO()
        csvwriter = csv.writer(s, lineterminator='\n' )
        self.csv(csvwriter)
        return s.getvalue()
        

def makeBadDummy():
    ''' Makes an incomplete invalid badc text file instance, for testing '''
    t = BADCtf()
    d1 = (301.2, 303.4, 305.6, 305.2)
    d2 = (1002.2, 1004.4, 1005.7, 1015.2)
    d3 = (6,12,18,24)
    
    t.add_variable("temp",d1)
    t.add_variable("press",d2)
    t.add_variable('time',d3)
    t.add_metadata('creator', 'Scrofulous Student')
    t.add_metadata('creator', ('Prof Bigshot, Hogwarts Uni'))
    return t
    
def makeBasicDummy():
    ''' Makes a complete, valid, basic badc text file instance for testing'''
    t=makeBadDummy()
    # following are mandatory basic column metadata
    t.add_metadata('long_name',('Temperature','K'),'temp')
    t.add_metadata('long_name',('Pressure','hPa'),'press')
    t.add_metadata('long_name',('Time since zero hours on valid date','hours'),'time')
    t.add_metadata('type','float','temp')
    t.add_metadata('type','float','press')
    t.add_metadata('type','int','time')
    t.add_metadata('coordinate_variable','1','time')
    # following are basic mandatory file metadata
    t.add_metadata('date_valid','2013-12-01')
    t.add_metadata('feature_type','point series')
    t.add_metadata('observation_station','My back yard')
    t.add_metadata('location','My back yard')
    t.add_metadata('activity','testing BADCtf')
    t.add_metadata('source','My Dummy data program')
    now = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    t.add_metadata('last_revised_date',now)
    return t 
            
        
class testBADCtf(unittest.TestCase):
    ''' Used to test BADC text files '''
    
    dummycsv='xxxx.csv'
    dummycdl='xxxx.cdl'
    dummyna='xxxx.na'
    sample="badc-csv-full-example2.csv"


    def _makeDummy(self):
        ''' Makes some dummy data '''
        t=makeBasicDummy()
        return t
        
    def setUp(self):
        self.t=self._makeDummy()
        
    def tearDown(self):
        for f in [self.dummycsv,self.dummycdl]:#,self.dummyna]:
            if os.path.exists(f): os.remove(f)
        
    def testMake(self):
        ''' Test making some dummy data without writing it'''
        self.assertEqual(self.t.nvar(),3)

    def testMakeAndWrite(self):
        ''' Tests simple making and writing '''
        self.t.write(self.dummycsv)
        self.assertEqual(True,os.path.exists(self.dummycsv))
        
    def testMakeAndCheckBasicFails(self):
        ''' Test basic valid checking '''
        self.t2=makeBadDummy()
        self.assertRaises(BADCtfMetadataIncomplete,self.t2._check_complete,('basic',))
        
    def testMakeAndCheckBasic(self):
        ''' Test basic valid checking '''
        self.t._check_complete('basic')
        
    def testMakeAndCheck(self):
        ''' Test basic valid checking '''
        self.t._check_complete(1)    
        
    def testMakeAndWriteCDL(self):
        ''' Test CDL writing '''
        self.t.write(self.dummycdl,fmt='cdl')
        print self.t._cdl()
        self.assertEqual(True,os.path.exists(self.dummycdl))
        
    def testMakeAndWriteAndRead(self):
        ''' test reading and comparison '''
        self.t.write(self.dummycsv)
        t2=BADCtf('r',self.dummycsv)
        self.assertEqual(self.t,t2)
        
    def testMakeAndWriteNA(self):
        ''' test producing a NASA ames file '''
        self.t.write(self.dummyna,fmt='na')
        self.assertEqual(True,os.path.exists(self.dummyna))
        
    def testMetaEquality(self):
        t1=self._makeDummy()
        t2=self._makeDummy()
        self.assertEqual(t1._metadata,t2._metadata)
        t2.add_metadata('creator','another author')
        self.assertNotEqual(t1._metadata,t2._metadata)
        
    def testReadingExample(self):
        print '\n%I: Some warnings expected wrt checking standard names'
        t=BADCtf('r',self.sample)
        self.assertEqual(t.nvar(),35)
       

if __name__ == "__main__":
    unittest.main()
