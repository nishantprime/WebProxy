from flask import Flask, request, Response
import requests
from bs4 import BeautifulSoup
import os

server_url = os.getenv('url')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

js_code = f"""
<script>
    document.addEventListener('DOMContentLoaded', () => {{
        document.body.addEventListener('click', e => {{
            const targetUrl = e.target.getAttribute('href');
            const isExternalLink = targetUrl && targetUrl.startsWith('http') && !targetUrl.startsWith('https://{server_url}');
            
            if (isExternalLink && !window.confirm('You are leaving the proxy site and going to ' + targetUrl + '. Continue?')) {{
                e.preventDefault();
            }}
        }});
    }});
</script>
"""

def modify_links(base_url, html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(['a'], href=True):
        old_url = tag['href']

        if '//' not in old_url:
            new_url = f'{base_url}/{old_url.lstrip("/")}'
            tag['href'] = new_url

    return str(soup)


app = Flask(__name__)

user_site = 'https://www.wiki.com'

# Create a session and set headers
session = requests.Session()
session.headers.update(headers)

@app.route('/clone', methods=['GET', 'POST'])
def clone_site():
    global user_site
    if request.method == 'POST':
        site = request.form.get('site', '')
        if site.startswith('www'):
            site = 'https://' + site
        user_site = site.rstrip('/')
        
        return f"User site set to: {user_site}<br><br><a href='/'>Return"

    return f"""
Currently cloning: {user_site}

<form method='post'>
    <label for='site'>Enter Website URL:</label>
    <input type='text' id='site' name='site' value='https://'>
    <input type='submit' value='Clone'>
</form>
"""

def fetch_and_modify_content(url):
    full_url = user_site + '/' + url
    user_sitename = user_site.replace('https://','')
    try:
        response = session.get(full_url)
        content_type = response.headers['Content-Type']

        if content_type.startswith(('text', 'application')):
            html_content = response.content.replace(user_sitename.encode('utf-8'), server_url.encode('utf-8'))
            html_content = html_content.replace(b'</head>', js_code.encode('utf-8') + b'</head>', 1)
            return html_content, content_type
            
        return response.content, content_type
    except Exception as e:
        return str(e), 'text/plain'

@app.route('/<path:url>')
def proxy(url):
    if 'http' not in url:
        modified_content, content_type = fetch_and_modify_content(url)
        return Response(modified_content, content_type=content_type)
    else:
        response = session.get(url)
        content_type = response.headers['Content-Type']
        modified_content = modify_links(url, response.content)
        return Response(modified_content, content_type=content_type)
            

@app.route('/')
def site():
    modified_content, content_type = fetch_and_modify_content('')
    return Response(modified_content, content_type=content_type)

if __name__ == '__main__':
    app.run(debug=True)
