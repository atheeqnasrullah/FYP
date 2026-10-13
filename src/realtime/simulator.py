import random, threading, time
from src.realtime.pipeline import command_bus

COMMANDS=["Rest","Hand_Open","Hand_Close","Wrist_Flexion","Wrist_Extension","Supination","Pronation","Left","Right"]

def start_simulator(interval=1.0):
    def run():
        while True:
            item={"command":random.choice(COMMANDS),"confidence":1.0,"source":"simulator","timestamp_ms":int(time.time()*1000)}
            try: command_bus.put(item,timeout=.2)
            except Exception: pass
            time.sleep(interval)
    threading.Thread(target=run,daemon=True).start()
