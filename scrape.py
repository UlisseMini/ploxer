import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse


class Socks5Proxy(object):
    __slots__ = ["host", "port"]

    def __init__(self, host, port):
        parsed = urlparse(f'socks5://{host}:{port}')
        if parsed.netloc == '':
            raise ValueError(f'Invalid socks5 proxy: {host}:{port}')

        self.host = host
        self.port = port

    def to_uri(self):
        return f"socks5://{self.host}:{self.port}"

    def __repr__(self):
        return f"<Socks5Proxy host={self.host!r}, port={self.port!r}>"


def scrape(url):
    r = requests.get(url)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def must_find(e, *args, **kwargs):
    r = e.find(*args, **kwargs)
    if not r:
        raise ValueError("Element not found")
    return r


def parse_table(table):
    def decorator(func):
        tbody = must_find(table, "tbody")
        for r in tbody.find_all("tr"):
            func(r.find_all("td"))

        return (lambda *args, **kwargs: None)
    return decorator


def socks_proxy_net():
    bs = scrape("https://socks-proxy.net")

    table = must_find(bs, id="proxylisttable")

    res = []
    @parse_table(table)
    def parse_cols(cols):
        if len(cols) != 8:
            print(f"warn: skipping row with {len(cols)} columns, expected 8")
            return
        host = cols[0].get_text().strip()
        port = cols[1].get_text().strip()
        res.append(Socks5Proxy(host, port))

    return res


def spys_one():
    bs = scrape("http://spys.one/en/socks-proxy-list/")

    # parse their stupid script thing
    varscript = bs.find_all("script", attrs={"type": "text/javascript"})[0].get_text()
    svars = {}
    for s in varscript.split(";"):
        exec(s, svars, svars)

    res = []
    for r in bs.find_all(class_=["spy1x", "spy1xx"]):
        cols = r.find_all("td")
        #print("r:", r)
        if len(cols) != 10:
            print(f"warn: skipping row with {len(cols)} columns, expected 10")
            continue
        if cols[1].get_text().lower() != "socks5":
            print("non socks")
            continue

        script = cols[0].find("script")
        script.extract()
        m = re.match(r"document\.write\(\".*?\"\+(.+)\)", script.get_text())
        if m is None:
            print("regex didn't match")
            continue
        p = []
        for part in m.group(1).split("+"):
            exec("p="+part, svars, svars)
            p.append(str(svars["p"]))
        port = int(''.join(p))

        host = cols[0].get_text()

        res.append(Socks5Proxy(host, port))
    return res


def proxyserverlist24(url='http://www.proxyserverlist24.top'):
    proxies = []

    soup = scrape(url)

    results = soup.select('h3 a')
    for a in results:
        subtitle = a.parent.parent.select_one('div.post-body').text
        if 'http prox' in subtitle.lower(): continue

        resp = requests.get(a['href'])
        if not resp.ok or 'http prox' in resp.text.lower(): continue

        soup = BeautifulSoup(resp.text, features="lxml")
        pre = soup.select_one('pre')
        if pre is None: continue
        for proxy in pre.text.split('\n'):
            split = proxy.strip().partition(':')
            ip = split[0]
            port = split[2]

            try:
                proxies.append(Socks5Proxy(ip, int(port)))
            except ValueError:
                pass

    return proxies


def proxynova(url='https://www.proxynova.com/proxy-server-list/elite-proxies/'):
    soup = scrape(url)

    proxies = []

    for tr in soup.find_all('tr')[1:]:
        try:
            tds = tr.find_all('td')
            ip = tds[0].find('abbr')['title'].strip()
            port = tds[1].text.strip()

            proxies.append(Socks5Proxy(ip, port))
        except (ValueError, TypeError, IndexError) as e:
            pass

    return proxies

def main():
    funcs = [socks_proxy_net, spys_one, proxyserverlist24, proxynova]

    proxies = set()
    for f in funcs:
        for proxy in f():
            proxies.add(proxy)

    with open("proxies.txt", "w") as f:
        f.write('\n'.join([i.to_uri() for i in proxies]))

if __name__ == '__main__':
    main()
