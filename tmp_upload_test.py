import requests
with open('test.png', 'wb') as f:
    f.write(b'test')
with open('test.png', 'rb') as f:
    r = requests.post('http://127.0.0.1:80/ui/upload', files={'file':('test.png', f, 'image/png')}, data={'chunked':'1', 'create_message':'1', 'client_msg_id':'abc123'})
print(r.status_code)
print(r.text)
