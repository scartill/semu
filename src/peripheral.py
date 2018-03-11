import time
import logging 
import threading as th
import queue

class Peripheral(th.Thread):
    def __init__(self):
        super().__init__()
        self.in_queue = queue.Queue()
        self.out_queue = queue.Queue()      

    def send_stop(self):
        self.in_queue.put(('cmd', 'stop'))
        
    def send_word(self, word):
        self.in_queue.put(('word', word))
        
    def peek(self):
        try:
            if(not self.out_queue.empty()):
                return self.out_queue.get_nowait()
            else:
                return None
        except queue.Empty:
                return None         
        
    def run(self):
        while True:
            (type, message) = self.in_queue.get()
        
            if(type == 'cmd'):
                if(message == 'stop'):
                    self.on_stop()
                    logging.debug("Peripheral stop")
                    return
            
            if(type == 'word'):
                self.process(message)

    def process(self, word):
        pass
        
    def on_stop(self):
        pass
        
class SysTimer(Peripheral):
    def __init__(self):
        super().__init__()
        self.tick = 0
        self.restart_timer()
        self.gen_signal = 0      # Starts disactivated
        
    def restart_timer(self):
        self.timer = th.Timer(1.0, self.on_timer)
        self.timer.start()
        
    def on_timer(self):
        self.restart_timer()
        
        if(self.gen_signal != 0):            
            self.out_queue.put(self.tick)
            
        self.tick += 1
        self.tick &= 0xFFFFFFFF
    
    def process(self, word):
        self.gen_signal = word
    
    def on_stop(self):
        self.timer.cancel()     
    
class Serial(Peripheral):
    def process(self, word):
        print(chr(word))
        
    

        