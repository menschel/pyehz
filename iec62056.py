# iec62056.py 
# (C) 2017 Patrick Menschel
import serial
import logging
import threading
import queue
import time
import datetime
from pprint import pprint

IEC_62056_STARTCHARACTER = b'/'
IEC_62056_TRANSMISSIONREQUESTCOMMAND = b'?'
IEC_62056_ENDCHARACTER = b'!'
IEC_62056_COMPLETIONCHARACTER = b'\r\n'

IEC_62056_STARTOFHEADERCHARACTER = b'\x01'
IEC_62056_SOH = IEC_62056_STARTOFHEADERCHARACTER 
IEC_62056_FRAMESTARTCHARACTER = b'\x02'
IEC_62056_STX = IEC_62056_FRAMESTARTCHARACTER
IEC_62056_BLOCKENDCHARACTER = b'\x03'
IEC_62056_ETX = IEC_62056_BLOCKENDCHARACTER

IEC_62056_PARTIALBLOCKENDCHARACTER = b'\x04'
IEC_62056_EOT = IEC_62056_PARTIALBLOCKENDCHARACTER

 
IEC_62056_ACKNOWLEDGECHARACTER = b'\x06'
IEC_62056_ACK = IEC_62056_ACKNOWLEDGECHARACTER
IEC_62056_REPEATREQUESTCHARACTER = b'\x15'#Negative Acknowledge Character
IEC_62056_NACK = IEC_62056_REPEATREQUESTCHARACTER


IEC_62056_COMMAND_MESSAGE_IDENTIFIERS = {'P':'Password Command',
                                         'W':'Write Command',
                                         'R':'Read Command',
                                         'E':'Execute Command',
                                         'B':'Exit Command (break)'}


IEC_62056_REGISTERS = {
                       'Voltage':{'address':0x0,
                                  'length':2,
                                  'unit':'V',
                                  'scale':'04.1f'},
                       'Current':{'address':0x1,
                                  'length':2,
                                  'unit':'A',
                                  'scale':'04.1f'},
                        'Frequency':{'address':0x2,
                                      'length':2,
                                      'unit':'Hz',
                                      'scale':'04.1f'},
                       'Active Power':{'address':0x3,
                                       'length':2,
                                       'unit':'kW',
                                       'scale':'04.2f'},    
                        'Reactive Power':{'address':0x4,
                                          'length':2,
                                          'unit':'VAr',
                                          'scale':'04.2f'},      
                        'Apparent Power':{'address':0x5,
                                          'length':2,
                                          'unit':'VA',
                                          'scale':'04.2f'},    
                         'Active Energy':{'address':0x10,
                                          'length':4,
                                          'unit':'Wh',
                                          'scale':'08f'},  
                        'Time':{'address':0x31, 
                                'length':2,
                                'unit':'',
                                'scale':''},                        
                        'Temperature':{'address':0x32,
                                       'length':2,
                                       'unit':'°C',
                                       'scale':''},      
                        'Serial Port':{'address':0x34,
                                       'length':6,
                                       'unit':'',
                                       'scale':''},
                        'Baudrate':{'address':0x35,
                                    'length':2,
                                    'unit':'',
                                    'scale':''},                       
                         'Meter ID':{'address':0x36,
                                     'length':6,
                                     'unit':'',
                                     'scale':''},
#                         'Password':{'address':0x37,
#                                     'length':4,
#                                     'unit':'',
#                                     'scale':''},                                                                                                                         
#                         'Clear_Energy':{'address':0x40,#write only
#                                         'length':6,
#                                         'unit':'',
#                                         'scale':''},                                                                                                                         
                                                                                                                        
                       }
                       

IEC_62056_MODE_A_BAUDRATE_IDENTIFIERS = {
                                         '1':1200,
                                         '2':2400,
                                         '3':4800,
                                         '4':9600,#DRS110M
                                         }

IEC_62056_MODE_B_BAUDRATE_IDENTIFIERS = {'A':300,
                                         'B':600,
                                         'C':1200,
                                         'D':2400,
                                         'E':4800,
                                         'F':9600,
                                         'G':19200,
                                         }

IEC_62056_MODE_C_BAUDRATE_IDENTIFIERS = {'0':300,
                                         '1':600,
                                         '2':1200,
                                         '3':2400,
                                         '4':4800,
                                         '5':9600,
                                         '6':19200,
                                         }



def iec_62056_calc_bcc(data):
    calc_bcc = 0
    for b in data[1:]:
        calc_bcc ^=b
    return calc_bcc

def iec_62056_check_bcc(data):
    ret = False
    calc_bcc = iec_62056_calc_bcc(data[:-1])
    data_bcc = data[-1]
    if calc_bcc == data_bcc:
        ret = True
    return ret
    

def iec_62056_generate_request_message(device_address=None):
    """
    Initial message - start of communication
    @param device_address: if given only the addressed device will answer, otherwise all devices will answer
    addressed is transmitted as ASCII
    @return: message as type bytes   
    """
    msg = bytearray()
    msg.extend(IEC_62056_STARTCHARACTER)
    msg.extend(IEC_62056_TRANSMISSIONREQUESTCOMMAND)
    if device_address:
        da = '{0:012}'.format(device_address)
        msg.extend(da.encode())
    msg.extend(IEC_62056_ENDCHARACTER)
    msg.extend(IEC_62056_COMPLETIONCHARACTER)
    return bytes(msg)
    
def iec_62056_generate_acknowledge_option_select_message(protocol=0,mode=0,baudrate=None):
    msg = bytearray()
    msg.extend(IEC_62056_ACK)
    msg.extend(str(protocol).encode())
    if baudrate:
        for b in IEC_62056_MODE_C_BAUDRATE_IDENTIFIERS:
            if IEC_62056_MODE_C_BAUDRATE_IDENTIFIERS[b] == baudrate:
                msg.extend(b.encode())
                break
    else:
        msg.extend(b':')#default for DRS110M whatever it means        
    msg.extend(str(mode).encode())
    msg.extend(IEC_62056_COMPLETIONCHARACTER)
    return bytes(msg)

def iec_62056_interpret_identification_message(msg):
    if msg[0:1] != IEC_62056_STARTCHARACTER:
        raise NotImplementedError('Frame is corrupt SOF')
    if msg[-2:] != IEC_62056_COMPLETIONCHARACTER:
        raise NotImplementedError('Frame is corrupt EOF')
    manufacturer = msg[1:4].decode()
    if manufacturer[2].isupper():
        reactiontime = 0.02 #20ms
    else:
        reactiontime = 0.2 #200ms
        
    baudrate_character = msg[4:5].decode()
    if baudrate_character.isdigit():
        protocol_mode = 'C'
        max_baudrate = IEC_62056_MODE_C_BAUDRATE_IDENTIFIERS[baudrate_character]
        baudrate_variable = True
    elif baudrate_character.isalpha():
        protocol_mode = 'B'
        max_baudrate = IEC_62056_MODE_B_BAUDRATE_IDENTIFIERS[baudrate_character]
        baudrate_variable = True
    else:
        #print('Unknown Baudrate Character {0}'.format(baudrate_character)) ':' on DRS110M
        protocol_mode = 'A'
        max_baudrate = None
        baudrate_variable = False
    identification = msg[5:-2].decode()
    return {'manufacturer':manufacturer,
            'reactiontime':reactiontime,
            'max_baudrate':max_baudrate,
            'identification':identification,
            'protocol_mode':protocol_mode,
            'baudrate_variable':baudrate_variable}
    
def print_iec_62056_identification(iec_62056_identification):
    print("""Manufacturer {manufacturer}
Identification {identification}
Protocol Mode {protocol_mode}    
Reaction Time {reactiontime}
Variable Baudrate {baudrate_variable}
Max Baudrate {reactiontime}""".format_map(iec_62056_identification))
    return

def iec_62056_interpret_data_message(msg):
    data = msg[1:-2].decode().rstrip(')')
    key,val = data.split('(')
    intkey = int(key,16)
    try:
        intval = int(val)
    except ValueError:
        intval = val
    return intkey,intval

def iec_62056_interpret_obis_msg(msg):
    obis_data = {}
    data = msg[msg.index(IEC_62056_STX)+1:msg.index(IEC_62056_ETX)]#STX to ETX
    datalines = [x.decode() for x in data.split(IEC_62056_COMPLETIONCHARACTER) if x]
    for l in datalines:
        line_elements = [x.rstrip(')') for x in l.split('(')]
        obis_code = line_elements[0]
        if len(line_elements) > 2:
            obis_vals = line_elements[1:]
            obis_data.update({obis_code:obis_vals})
        else:
            obis_val =  line_elements[1]
            obis_data.update({obis_code:obis_val})
    return obis_data
          
    


def iec_62056_is_identification_message(msg):
    ret = True
    conds = [msg[0:1] == IEC_62056_STARTCHARACTER,#SOF
             msg[-2:] == IEC_62056_COMPLETIONCHARACTER,#EOF                         
             ]
    for cond in conds:
        ret &= cond
    return ret

def iec_62056_is_acknowledge_message(msg):
    ret = True
    conds = [msg[0:1] == IEC_62056_ACK,                         
             ]
    for cond in conds:
        ret &= cond
    return ret    

def iec_62056_is_nack_message(msg):
    ret = True
    conds = [msg[0:1] == IEC_62056_NACK,                         
             ]
    for cond in conds:
        ret &= cond
    return ret 

def iec_62056_is_data_message(msg):
    ret = True
    conds = [msg[0:1] == IEC_62056_STX,
             msg[-2:-1] == IEC_62056_ETX,                         
             ]
    for cond in conds:
        ret &= cond
    return ret 

def iec_62056_is_programming_command_message(msg):
    ret = True
    conds = [msg[0:1] == IEC_62056_SOH,
             msg[3:4] == IEC_62056_STX,
             msg[-2:-1] == IEC_62056_ETX,                         
             ]
    for cond in conds:
        ret &= cond
    return ret 



def iec_62056_generate_programming_command_message(cmd='R',cmd_type=1,data=None):
    msg = bytearray()
    msg.extend(IEC_62056_SOH)
    msg.extend(cmd.encode())
    msg.extend(str(cmd_type).encode())
    if data != None:
        msg.extend(IEC_62056_STX)
        if isinstance(data,bytes):
            msg.extend(data)
        elif isinstance(data,str):
            msg.extend(data.encode())
        else:
            raise NotImplementedError('Data with Type {0} not handled'.format(type(data)))
    msg.extend(IEC_62056_ETX)
    msg.append(iec_62056_calc_bcc(msg))
    return bytes(msg)
    
def iec_62056_generate_r1_message(address):
    data = '{0:08x}()'.format(address)
    msg = iec_62056_generate_programming_command_message(cmd='R',cmd_type=1,data=data)
    return msg

def iec_62056_generate_p1_message(passwd):
    data = '({0:08})'.format(passwd)
    msg = iec_62056_generate_programming_command_message(cmd='P',cmd_type=1,data=data)
    return msg

def iec_62056_generate_b0_message():
    msg = iec_62056_generate_programming_command_message(cmd='B',cmd_type=0,data=None)
    return msg


def iec_62056_generate_w1_message(address,valuetowrite):
    data = '{0:08x}({1})'.format(address,valuetowrite)
    msg = iec_62056_generate_programming_command_message(cmd='W',cmd_type=1,data=data)
    return msg

def iec_62056_generate_r5_obis_message(obis_code):
    data = '{0}(;)'.format(obis_code)
    msg = iec_62056_generate_programming_command_message(cmd='R',cmd_type=5,data=data)
    return msg


def iec_62056_generate_r1_obis_message(obis_code):
    data = '{0}(;)'.format(obis_code)
    msg = iec_62056_generate_programming_command_message(cmd='R',cmd_type=1,data=data)
    return msg






class iec62056():
    def __init__(self,port,portsettings=None):
        """
        @param ser: Serial Connection, can be an serial.Serial object or a string to the port
        """
        self._init_logger()
        self._log_debug('Init with ser {0} ({1}), portsettings {2}'.format(port,type(port),portsettings))
        self.port = port
        if portsettings:
            self.portsettings = portsettings            
        else:
            self.portsettings = {}
        self.ser = None
        self.is_started = False
        if self.port and self.portsettings:
            self.configure_serial(port=self.port, portsettings=self.portsettings)
            
        
        self.device_address=None
        self.meter_objs = {}
        self.timeout = 2
        self.data_queue = queue.Queue()
        self.programm_queue = queue.Queue()
        self.acknowledge_queue = queue.Queue()
        self.identification_queue = queue.Queue()
        
        self.mutex = threading.Lock()
        self.device_lock = threading.Lock()
        self.txqueue = queue.Queue()
        self.txhandler = threading.Thread(target=self.handletx)
        self.txhandler.setDaemon(True)
        self.rxhandler = threading.Thread(target=self.handlerx)
        self.rxhandler.setDaemon(True)
        if self.ser:
            self.start_serial()
        self._log_info('Init Complete')
        
    def _init_logger(self):
        self._logger = logging.getLogger('iec62056')
        self._logger.setLevel(logging.DEBUG)
        self._fh = logging.FileHandler('iec62056.log')
        #self._fh.setLevel(logging.DEBUG)
        #self._fh.setLevel(logging.INFO)
        self._fh.setLevel(logging.ERROR)
        self._ch = logging.StreamHandler()
        self._ch.setLevel(logging.ERROR)
        self._formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self._fh.setFormatter(self._formatter)
        self._ch.setFormatter(self._formatter)
        self._logger.addHandler(self._fh)
        self._logger.addHandler(self._ch)
        self._log_info('Logger has been initialized')
        return
    
    def _log_info(self,msg):
        if self._logger:
            self._logger.info(msg)
        return
                
    def _log_error(self,msg):
        if self._logger:
            self._logger.error(msg)
        return
    
    def _log_debug(self,msg):
        if self._logger:
            self._logger.debug(msg)
        return     
    
    def handlerx(self):
        self._log_debug('handlerx started')
        rxbuff = bytearray()
        while self.ser.isOpen():
            msg = self.ser.read(64)
            if msg:
                self._log_debug('Serial Read {0}'.format(' '.join(['{0:02x}'.format(x) for x in msg])))
                rxbuff.extend(msg)
                if rxbuff[0] == IEC_62056_FRAMESTARTCHARACTER[0]:
                    if rxbuff[-2] == IEC_62056_BLOCKENDCHARACTER[0]:
                        self.on_iec62056_message(rxbuff)
                        rxbuff = bytearray()
                    else:
                        #incomplete message
                        pass
                else:                                
                    self.on_iec62056_message(rxbuff)
                    rxbuff = bytearray()
        return  
    
    
    def configure_serial(self,port=None,portsettings=None):
        self._log_debug('Configure Serial Port: {0} Settings:{1}'.format(port,portsettings))
        if not self.is_started:
            if port:
                self.port=port
            if portsettings:
                self.portsettings=portsettings
            if self.port and self.portsettings:
                if self.ser:
                    self.ser.close()
                    del self.ser
                try:
                    self.ser = serial.Serial(port=self.port,baudrate=self.portsettings['baudrate'],bytesize=self.portsettings['bytesize'],parity=self.portsettings['parity'],stopbits=self.portsettings['stopbits'],timeout=self.portsettings['timeout'])
                except serial.SerialException:
                    self._log_error('SerialException - Could not open Serial Port {0}'.format(port))
                    raise ValueError('Could not open Serial Port {0}'.format(port))            
        return
    

    def change_baudrate_serial(self,baudrate):
        self._log_debug('Set Serial Baudrate {0}'.format(baudrate))
        self.ser.setBaudrate(baudrate=baudrate)
        self._log_debug('Baudrate now is {0}'.format(self.ser.baudrate))
        return
    
    def start_serial(self):
        if self.ser:
            if not self.is_started:
                self.rxhandler.start()
                self.txhandler.start()
                self.is_started = True
        else:
            raise NotImplementedError('Tried to start unconfigured Serial')
        return
    
        
    
    def on_iec62056_message(self,msg):

        if iec_62056_is_identification_message(msg):
            self._log_debug('found identification message {0}'.format(msg))
            self.on_identification_message(msg)

        elif iec_62056_is_acknowledge_message(msg):
            self._log_debug('found ack message {0}'.format(msg))
            self.on_ack_message(msg)

        elif iec_62056_is_data_message(msg):
            self._log_debug('found data message {0}'.format(msg))
            self.on_data_message(msg)

        elif iec_62056_is_programming_command_message(msg):
            self._log_debug('found programming message {0}'.format(msg))
            self.on_programming_message(msg)
        else:
            print('No corresponding message {0}'.format(' '.join(['{0:02x}'.format(x) for x in msg])))    
        return
    
    def on_identification_message(self,msg):
        md = iec_62056_interpret_identification_message(msg)
        with self.mutex:
            mi = md.pop('identification')
            md.update({'status':'initialized'})
            self.meter_objs.update({mi:md})
            self.protocol_mode = md['protocol_mode'] 
        self.identification_queue.put(msg)
        return md
    
    def on_data_message(self,msg):
        if iec_62056_check_bcc(msg):
            self.data_queue.put(msg)
        return
    
    def on_programming_message(self,msg):
        if iec_62056_check_bcc(msg):
            self.programm_queue.put(msg)
        return
    
    def on_ack_message(self,msg):
        self.acknowledge_queue.put(msg)
        return        
    
    
    def handletx(self):
        self._log_debug('handletx started')
        while self.ser.isOpen():
            try:
                nexttxmessage = self.txqueue.get(1)
                self.ser.write(nexttxmessage)
                self._log_debug('Serial Write {0}'.format(' '.join(['{0:02x}'.format(x) for x in nexttxmessage])))
            except queue.Empty:
                pass
        return
    
    def transmit(self,msg):
        self.txqueue.put(msg)
        return
    
    def start_communication(self,device_address=None):
        self._log_info('start_communication to {0}'.format(device_address))
        self.ser.flushInput()#discard anything that is there
        if device_address == None:
            if self.device_address:
                device_address = self.device_address
        msg = iec_62056_generate_request_message(device_address)
        self.transmit(msg)
        resp = None
        while not resp:
            try:
                resp = self.identification_queue.get(timeout=self.timeout)
                self.device_address = device_address
            except queue.Empty:
                resp = None
                self._log_error('Timeout on Start Communication message - next try')
                self.transmit(msg)                          
        return
    
    def acknowledge_option_select(self,protocol=0,baudrate=None,mode=0):
        msg = iec_62056_generate_acknowledge_option_select_message(protocol=0, mode=mode,baudrate=baudrate)
        self._log_debug('sending ack_option_switch_message for protocol {0}, baudrate {1}, mode {2}'.format(protocol,baudrate,mode))
        self.transmit(msg)
        self._log_debug('ack_option_switch_message sent')
        return
    
    def start_programming_mode_with_password(self,password=0):
        self._log_info('start_programming_mode_with_password {0}'.format(password))
        msg = iec_62056_generate_acknowledge_option_select_message(protocol=0, mode=1)
        self.transmit(msg)
        self._log_debug('ack_option_switch_message sent')
        try:
            self.programm_queue.get(timeout=self.timeout)
            self._log_debug('password_request received')
            msg = iec_62056_generate_p1_message(0)
            self.transmit(msg)
            self._log_debug('password_message sent')
            self.acknowledge_queue.get(timeout=self.timeout)
            self._log_debug('password_response received')
        except queue.Empty:
            self._log_error('Timeout on P1 message')
        return
       
    def read_register(self,reg_address):
        msg = iec_62056_generate_r1_message(reg_address)
        self.transmit(msg)
        try:
            data = self.data_queue.get(timeout=self.timeout)
        except queue.Empty:
            data = None
            self._log_error('No Response from Register {0}'.format(reg_address))        
        return data
    
    def simple_read_register(self,reg_address):
        self.start_programming_mode_with_password()
        data = self.read_register(reg_address)
        return data
    
    def log_off(self):
        msg = iec_62056_generate_b0_message()
        self.transmit(msg)
        return 
    
    
    def get_value_r1(self,valname,reg_dict=IEC_62056_REGISTERS):
        reg = reg_dict[valname]
        reg.update({'raw_data':None,
                    'value':None,
                    })
        addr = reg['address']
        data = self.read_register(addr)
        if data:
            reg.update({'raw_data':data})
            key,val = iec_62056_interpret_data_message(data)
            if key != addr:
                print('Protocol Error - expected{0} but found {1}'.format(addr,key))
            signal_scaling = reg['scale']
            if '.' in signal_scaling:
                idx = signal_scaling.index('.')
                idx2 = signal_scaling.index('f')
                signal_exponent = int(signal_scaling[idx+1:idx2])
                signal_divisor = 1
                for i in range(signal_exponent):
                    signal_divisor *= 10
                val /= signal_divisor
            reg.update({'value':val})    
            reg.update({'time_stamp':datetime.datetime.now()})    
        return reg
    
    def print_value(self,valname):
        reg = self.get_value_r1(valname)
        if reg['raw_data']:
            val_as_str = '{value}{unit}'.format_map(reg)
            print('{0}:{1}'.format(valname, val_as_str))
        return
    
    def printstr_value(self,valname):
        reg = self.get_value_r1(valname)
        if reg['raw_data']:
            val_as_str = '{value}{unit}'.format_map(reg)
            ret = '{0}:{1}'.format(valname, val_as_str)
        else:
            ret = '{0}:{1}'.format(valname, "None")
        return ret
        
    
    def print_registers(self,reg_dict=IEC_62056_REGISTERS):
        self.start_programming_mode_with_password()
        for valname in reg_dict:
            self.print_value(valname)
        self.log_off()
        return        
    
    def prints_registers(self,reg_dict=IEC_62056_REGISTERS):
        self.start_programming_mode_with_password()
        ret = []
        for valname in reg_dict:
            ret.append(self.print_value(valname))
        self.log_off()
        return ret               
        
    def get_meter_information(self):
        with self.mutex:
            mi = self.meter_objs.copy()
        return mi    
    
    def clear_active_energy(self):
        self.start_programming_mode_with_password()
        msg = iec_62056_generate_w1_message(address=0x40,valuetowrite='00000000')
        self.transmit(msg)
        self._log_debug('clear active energy sent')
        self.acknowledge_queue.get(timeout=self.timeout)
        self._log_debug('acknowledge received')
        return
    
    def get_obis_data_frame(self):
        msg = self.data_queue.get(timeout=5)
        obis_data = iec_62056_interpret_obis_msg(msg=msg)
        return obis_data
    
    def request_r5_p01(self):
        msg = iec_62056_generate_r5_obis_message('P.1')
        self.transmit(msg)
        self._log_debug('requested R5 P.01')
        ret = self.data_queue.get(timeout=5)
        print(ret)
        return ret

    def request_r5_p98(self):
        msg = iec_62056_generate_r5_obis_message('P.98')
        self.transmit(msg)
        self._log_debug('requested R5 P.98')
        ret = self.data_queue.get(timeout=5)
        print(ret)
        return ret
    
    def request_r1_180(self):
        msg = iec_62056_generate_r1_obis_message('1.8.0')
        self.transmit(msg)
        self._log_debug('requested R1 1.8.0')
        ret = self.data_queue.get(timeout=5)
        print(ret)
        return ret
    

class drs110m():
    """Protocol A fixed baudrate of 9600 """
    def __init__(self,iec62056_dev,device_address,regs=None):
        self.portsettings = {'baudrate':9600,
                             'bytesize':serial.SEVENBITS,
                             'parity':serial.PARITY_EVEN,
                             'stopbits':serial.STOPBITS_ONE,
                             'timeout':0.1,
                             }
        self.iec62056_dev = iec62056_dev
        if not self.iec62056_dev.is_started:
            self.iec62056_dev.configure_serial(portsettings=self.portsettings)
            self.iec62056_dev.start_serial()        
        self.device_address = device_address
        if regs:
            self.reg_dict = {}
            for reg in regs:
                self.reg_dict.update({reg:IEC_62056_REGISTERS[reg]})
        else:
            self.reg_dict = IEC_62056_REGISTERS
        self.reg_values = dict.fromkeys(self.reg_dict.keys())
        
    def start_communication(self):
        self.iec62056_dev.start_communication(device_address=self.device_address)
        self.iec62056_dev.start_programming_mode_with_password()
        return
    
    def update_values(self):
        self.start_communication()
        for valname in self.reg_dict:
            reg = self.iec62056_dev.get_value_r1(valname)
            if reg['raw_data']:
                self.reg_values.update({valname:reg})
        self.log_off()
        return True
    
    def log_off(self):
        self.iec62056_dev.log_off()
        return
    
    def get_value(self,valname):
        return {valname:self.reg_values[valname]}
    
    def printstr_value(self,valname):
        val = self.get_value(valname)
        val_as_str = '{value}{unit}'.format_map(val[valname])
        ret = '{0}:{1}'.format(valname, val_as_str)
        return ret
            
    def print_all_values(self):
        for val in self.reg_values:
            if val:
                print(self.printstr_value(val))
                
                
class pafal():
    
    """Protocol C variable baudrate of 300-?? """
    def __init__(self,iec62056_dev,device_address=None,regs=None):
        self.portsettings = {'baudrate':300,
                             'bytesize':serial.SEVENBITS,
                             'parity':serial.PARITY_EVEN,
                             'stopbits':serial.STOPBITS_ONE,
                             'timeout':0.6,
                             }
        self.iec62056_dev = iec62056_dev
        self.iec62056_dev.configure_serial(portsettings=self.portsettings)
        self.iec62056_dev.start_serial()        
        self.device_address = device_address
        self.obis_data = {}
        
    
    def start_communication(self):
        self.iec62056_dev.change_baudrate_serial(300)
        self.iec62056_dev.start_communication(device_address=self.device_address)
        self.iec62056_dev.acknowledge_option_select(protocol=0,baudrate=9600,mode=0)
        time.sleep(0.2)
        self.iec62056_dev.change_baudrate_serial(9600)
        time.sleep(1.1)
        self.obis_data.update(self.iec62056_dev.get_obis_data_frame())
        return self.obis_data
    
    def request_r5_p01(self):
        return self.iec62056_dev.request_r5_p01()
    
    def request_r5_p98(self):
        return self.iec62056_dev.request_r5_p98()
    
    def request_r1_180(self):
        return self.iec62056_dev.request_r1_180()
    
    

        
                
    
def selftest(port,con_type,cmd,meterid):  
    iec62056_obj = iec62056(port=port)    
    if cmd == 'readout_drs110m':        
        drs110m_dev = drs110m(iec62056_dev=iec62056_obj,device_address=meterid,regs=['Time','Active Energy','Active Power'])
        drs110m_dev.update_values()      
        drs110m_dev.print_all_values()
        
    elif cmd == 'readout_pafal':
        pafal_dev = pafal(iec62056_dev=iec62056_obj)
        pafal_dev.start_communication()
        pprint(pafal_dev.obis_data)

    return        
    
if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-c", "--command", dest="command", default='readout_pafal',
                      help="COMMAND to execute", metavar="COMMAND")
    parser.add_option("-p", "--port", dest="port", default='/dev/ttyUSB0',
                      help="PORT device to use", metavar="PORT")
    parser.add_option("-t", "--type", dest="type", default='RS485',
                      help="TYPE of PORT, can be RS485 or IR", metavar="TYPE")    
    parser.add_option("-i", "--meterid", dest="meterid", type="int", default=1613300153,
                      help="METERID to start communication with", metavar="METERID")
    
    (options, args) = parser.parse_args()
 
    selftest(port=options.port,con_type=options.type,cmd=options.command,meterid=options.meterid)


    
