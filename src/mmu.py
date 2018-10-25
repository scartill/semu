# Emulated memory management unit

class MMU:
    def __init__(self, memory):
        self.memory = memory
        
    def read32(self, addr):
        return self.memory[addr:addr + 4]
    
    def write32(self, addr, buf):
        self.memory[addr:addr + 4] = buf
        
