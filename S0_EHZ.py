import logging,datetime,sys,time

class S0_EHZ():
    def __init__(self):
        self._initLogger()
        self.timestamp=None
        self.debouncetime=None
        self.pulsesPerKwh = 1000
        self.channel = 16 # 14 is GND Connect PhotoDiode in between, test with pushbutton
        try:
            import RPi.GPIO as GPIO
        except RuntimeError:
            self._logDebug('Error while importing RPi.GPIO')
            print("Error importing RPi.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")
        self._logDebug('Version Info Board Revision {0}, RPi GPIO Version {1}'.format(GPIO.RPI_REVISION,GPIO.VERSION))
        print('Version Info Board Revision {0}, RPi GPIO Version {1}'.format(GPIO.RPI_REVISION,GPIO.VERSION))
        
        try:
            GPIO.setmode(GPIO.BOARD)
            self._logDebug('Mode Set to Board Numbering')
            GPIO.setup(self.channel, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._logDebug('Using PIN {0} with PullUp'.format(self.channel))
            GPIO.add_event_detect(self.channel, GPIO.RISING, callback=self.HandleS0Event)  # add rising edge detection on a channel
            self._logDebug('Using PIN {0} with PullUp'.format(self.channel))
        except:
            print('Error')
            GPIO.cleanup()
            sys.exit(0)
            
     
    
    
    def _initLogger(self):
        self._logger = logging.getLogger('S0_EHZ')
        self._logger.setLevel(logging.DEBUG)
        self._fh = logging.FileHandler('S0_EHZ.log')
        self._fh.setLevel(logging.DEBUG)
#         self._fh.setLevel(logging.INFO)
        self._ch = logging.StreamHandler()
        self._ch.setLevel(logging.ERROR)
        self._formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self._fh.setFormatter(self._formatter)
        self._ch.setFormatter(self._formatter)
        self._logger.addHandler(self._fh)
        self._logger.addHandler(self._ch)
        self._logDebug('Logger has been initialized')
        return
    
    def _logInfo(self,msg):
        if self._logger:
            self._logger.info(msg)
        return
                
    def _logError(self,msg):
        if self._logger:
            self._logger.error(msg)
        return
    
    def _logDebug(self,msg):
        if self._logger:
            self._logger.debug(msg)
        return
    
    
    def HandleS0Event(self,channel):
        #print('got Interrupt on {0}'.format(channel))
        newtimestamp = time.time()
        if self.timestamp:            
            difftime =  newtimestamp-self.timestamp
            if self.debouncetime:
                if difftime < self.debouncetime:
                    return
            self.debouncetime = 0.5*difftime
            #250pulses for 1 kw/h
            # 1 Pulse Seconds = 3600/250* S  kw * 
            currentKw = 3600/(self.pulsesPerKwh * difftime)
            # self._logInfo('Power Consumption is {0:3.3}kw'.format(currentKw))
            #print('Power Consumption is {0:3.3}kw'.format(currentKw))
            print('{0},{1:6.3}'.format(datetime.datetime.now(),currentKw))
        self.timestamp = newtimestamp
        return
        
if __name__ == '__main__':
    myS0 = S0_EHZ()
    input('press enter to exit')
