import os, signal, threading
threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
try:
    import app.main
    print("Success")
except KeyboardInterrupt:
    pass
