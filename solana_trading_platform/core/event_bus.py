# core/event_bus.py
class EventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type: str, callback):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def publish(self, event_type: str, data):
        for callback in self.subscribers.get(event_type, []):
            callback(data)

# Example usage:
if __name__ == "__main__":
    bus = EventBus()
    def on_balance_fetched(data):
        print(f"Event received: {data}")
    bus.subscribe("balance_fetched", on_balance_fetched)
    bus.publish("balance_fetched", {"balance": 10})