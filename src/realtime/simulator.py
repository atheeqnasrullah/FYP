import random, threading, time
from src.realtime.pipeline import command_bus
from src.utils.config import runtime_labels

COMMANDS=runtime_labels()

def start_simulator(interval=1.0):
    def run():
        while True:
            item={"command":random.choice(COMMANDS),"confidence":1.0,"source":"simulator","timestamp_ms":int(time.time()*1000)}
            try: command_bus.put(item,timeout=.2)
            except Exception: pass
            time.sleep(interval)
    threading.Thread(target=run,daemon=True).start()
