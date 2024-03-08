import json
import pprint
import websocket
from fake_useragent import UserAgent

ua = UserAgent()

IDENTIFY = {"op": "identify", "data": {"client": "InfCraftBrowser/1.0", "version": 1}}
SEARCH = {"op": "search",  "nonce":1,"data":{"offset":0,"sort":"time","order":"ascending"}}
ws = websocket.WebSocket()
headers = ["Pragma: no-cache","Cache-Control: no-cache","User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0","Accept-Encoding: gzip, deflate, br","Accept-Language: en-US,en;q=0.9","Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits"]
received = []

def stringify(inp):
    return str(inp).replace("'", '"')
ws.connect("wss://infinibrowser.zptr.cc/api/ws", header=headers)
ws.send(stringify(IDENTIFY))
print(ws.recv())
runs = 0
while True:
    print(f"Sending {SEARCH['data']['offset']}")
    ws.send(stringify(SEARCH))
    result = ws.recv()
    print(f"received! {result}")
    json_data = json.loads(result)["data"]["items"]
    if len(json_data) == 0:
        break
    received.extend(json_data)
    SEARCH["data"]["offset"] += len(json_data)
    runs += 1
    if runs % 10 == 0:
        ws.send(stringify({"op": "heartbeat"}))
        ws.recv()

ws.close()

pprint.pprint(received)