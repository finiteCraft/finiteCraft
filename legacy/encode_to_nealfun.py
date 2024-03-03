import json

tree = json.load(open('tree.json'))
emoji = json.load(open('emoji.json'))
thing = []

for i in tree.keys():
    if i in emoji.keys():
        thing.append({"text": i, "emoji": emoji[i]['emoji']})
    else:
        thing.append({"text": i, "emoji": ""})

stringify = str({"elements": thing}).replace("False", "false").replace("'", '"')
print(stringify)

