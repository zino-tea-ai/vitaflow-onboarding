# Test 3: Packet Loss Retry
import random, time
from dataclasses import dataclass

@dataclass
class Packet:
    seq_id: int
    data: str
    retries: int = 0

class PacketLossSimulator:
    def __init__(self, loss_rate=0.3, max_retries=3):
        self.loss_rate = loss_rate
        self.max_retries = max_retries
        self.received = []
        self.failed = []
        self.total_retries = 0

    def send(self, p): return random.random() > self.loss_rate

    def send_with_retry(self, p):
        for r in range(self.max_retries + 1):
            if self.send(p):
                p.retries = r
                self.received.append(p)
                self.total_retries += r
                return True, r
            time.sleep(0.01 * (2 ** r))
        p.retries = r
        self.failed.append(p)
        self.total_retries += r
        return False, r

    def run_test(self, n=15):
        print(f"Packet Loss Test - Loss: {self.loss_rate*100:.0f}%")
        print("="*50)
        for i in range(n):
            p = Packet(i+1, f"data_{i}")
            ok, retries = self.send_with_retry(p)
            s = "OK" if ok else "FAIL"
            r = f"(retry {retries}x)" if retries else ""
            print(f"  Packet #{i+1:03d}: {s} {r}")
        rate = len(self.received)/n*100
        print(f"Result: {len(self.received)}/{n} ({rate:.1f}%) avg_retry={self.total_retries/n:.2f}")
        print()

if __name__ == "__main__":
    for r in [0.1, 0.3, 0.5]:
        PacketLossSimulator(r).run_test()
    print("Test 3 completed!")
