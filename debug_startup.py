from main import QuantScaleSystem
import time

print("Instantiating System...")
start = time.time()
try:
    s = QuantScaleSystem()
    print(f"Instantiation complete in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Instantiation failed: {e}")
