#!/usr/bin/python
import cgi
import sys
import datetime
from markdown import markdown as md
import re
import os
import glob
import urlparse

# @@ Todo
# * Prettier design
# * Presentation, print and mobile CSS?
# * Preview that includes diff
# * List of deleted pages and its revisions
# * If the login-email-address is not in the name-db, prompt user for name
# * Migrate old signup page and change password page
# * Check for valid email address in username
# * Prettier diff page
# * Write proper documentation/setup guide
# * iPhone app

config = {}

exists = os.path.exists
env = os.environ

if exists('.dienw/config.vars'):
    for line in open('.dienw/config.vars').readlines():
        if ': ' in line:
            line = line.strip()
            key, value = line.split(': ', 1)
            config[key] = value

if env.has_key('SCRIPT_NAME'):
    if not exists('.dienw/links'):
        os.mkdir('.dienw/links/')
    base = config.get('base', '/')
    title = config.get('title', 'Wiki')
    uri = env.get('REQUEST_URI')
    gform = urlparse.parse_qs(uri.partition('?')[2])
    pform = urlparse.parse_qs(sys.stdin.read())
    method = env.get('REQUEST_METHOD')

r_name = re.compile(r'^[A-Za-z0-9-=?&]+$')
dstr = '%Y-%m-%d %H:%M:%S'

class GitError(Exception):
    pass

def git(*args):
    import subprocess
    cmd = subprocess.Popen( ['git'] + list(args),
        stdin = subprocess.PIPE,
        stdout = subprocess.PIPE,
        stderr = sys.stderr )
    return cmd

def gitq(*args):
    cmd = git(*args)
    stdout, stderr = cmd.communicate()
    return cmd.returncode

def git_commit(msg, author):
    # See if we have something to commit; if not, just return
    gitq('update-index', '--refresh')
    r = gitq('diff-index', '--exit-code', '--quiet', 'HEAD')
    if r == 0:
        return
        
    r = gitq('commit', '-m', msg, '--author', author)
    
    if r != 0:
        raise GitError, r

def git_log(file = None, files = None):
    if not files:
        files = []
    if file:
        files.append(file)
    
    cmd = git("rev-list", "--all", "--pretty=raw",  "HEAD", "--", *files)
    cmd.stdin.close()
    
    content = cmd.stdout.read()
    cmd.wait()
    
    if cmd.returncode != 0:
        GitError, cmd.returncode
    
    content = content.replace("\n    ", "message ")
    content = content.split('\n\n')[:-1]
    commits = []
    for block in content:
        commit = {}
        lines = block.split("\n")
        for line in lines:
            key, value = line.split(' ', 1)
            commit[key] = value
        git_commit_fmt(commit)
        commits.append(commit)
    
    return commits
    
def git_add(*files):
    r = gitq('add', "--", *files)
    if r != 0:
        raise GitError, r

def git_remove(*files):
    r = gitq('rm', '-f', '--', *files)
    if r != 0:
        raise GitError, r

def git_show(file_cid):
    cmd = git("show", "--pretty=raw", file_cid)
    content = cmd.stdout.read()
    cmd.wait()
    return content

def git_commit_log(cid):
    cmd = git("rev-list", "-n1", "--pretty=raw", cid)
    out = cmd.stdout.read()
    cmd.wait()
    out = out.replace("\n    ", "message ")
    commit = {}
    for l in out.split('\n'):
        l = l.strip()
        if l:
            key, value = l.split(' ', 1)
            commit[key] = value
    git_commit_fmt(commit)
    return commit

def git_diff(name, cid1, cid2):
    cmd = git("diff", cid1 + ".." + cid2, name)
    out = cmd.stdout.read()
    cmd.wait()
    return out

def git_commit_fmt(commit):
    if 'author' in commit:
        author, epoch, tz = commit['author'].rsplit(' ', 2)
        epoch = float(epoch)
        author, email = author.rsplit(' <', 1)
        commit['author'] = author
        commit['aemail'] = email[:-1]
        commit['atime'] = datetime.datetime.fromtimestamp(epoch)
    
    if 'committer' in commit:
        committer, epoch, tz = commit['committer'].rsplit(' ', 2)
        epoch = float(epoch)
        committer, email = committer.rsplit(' <', 1)
        commit['committer'] = committer
        commit['cemail'] = email[:-1]
        commit['ctime'] = datetime.datetime.fromtimestamp(epoch)

def urlencode(d):
    # In case anyone ever wonders. urllib.urlencode DOES NOT take the output
    # of urlparse.parse_qs. Ya, seriously. FU Python.
    from urllib import quote as q
    return '&'.join(['&'.join([k + '=' + q(v) for v in d[k]]) for k in d])

def menu():
    s = '<div id="menu">\n'
    s += markdown(open(".dienw/menu.txt").read())
    s += '\n</div>'
    return s

def html(ptitle, body):
   s = 'Content-Type: text/html; charset=utf-8\r\n\r\n'
   s += open(".dienw/template.html").read()
   s = s.replace("<!--title-->", title)
   s = s.replace("<!--ptitle-->", ptitle)
   s = s.replace("<!--menu-->", menu())
   s = s.replace("<!--body-->", body)
   s = s.replace("$base", base)
   return s

def content(ptitle, body, edit=None):
    c = '<h2 id="ptitle">%s</h2>\n' % ptitle
    if edit:
        c += '<ul id="pmenu">\n'
        c += '<li><a href="/@edit/%s">Edit</a></li>\n' % edit
        if not '?' in edit:
            c += '<li><a href="/@remove/%s">Remove</a></li>\n' % edit
        c += '<li><a href="/@info/%s">Info</a></li>\n' % edit
        c += '</ul>\n'
    c += '<div id="content">\n'
    c += body
    c += '\n</div>'
    return c

def notfound(name=None):
    t = 'Not found'
    s = 'Status: 404 Not Found\r\n'
    if name: name = "<em>%s</em>" % name
    else: name = 'you requested'
    c = '<p>Sorry, the page %s does not exist.</p>' % name
    s += html(t, content(t, c))
    return s

def redirect(l):
    t = 'Redirect'
    s = 'Status: 301 Found\r\n'
    s += 'Location: %s\r\n\r\n' % l
    c = '<p>You are being redirected. <a href="%s">Click here.</a></p>' % l
    s += html(t, content(t, c))
    return s

def markdown(s):
    return md(s.decode('utf-8'),
              ['headerid(level=2)', 'def_list']).encode('utf-8')

def diff(name):
    name = "%s.txt" % name
    
    commit = gform.get('commit', '')
    if not commit:
        return notfound()
    
    if len(commit) == 1:
        commit.append('HEAD')
    
    t = "Comparing commits %s and %s" % tuple(commit[:2])
    
    s = markdown('Back to latest version of [%s](/%s)' % (name[:-4], name[:-4]))
    s += '\n<pre class="diff">'
    for l in git_diff(name, *commit[:2]).split('\n'):
            l = l.rstrip()
            if l.startswith("+") and not l.startswith("+++"):
                    c = "add"
            elif l.startswith("-") and not l.startswith("---"):
                    c = "remove"
            elif l.startswith(" "):
                    c = "unchanged"
            elif l.startswith("@@"):
                    c = "position"
            elif l.startswith("diff"):
                    c = "header"
            else:
                    c = "other"
            s += '<span class="%s">' % c + cgi.escape(l) + '</span>\n'
    s += '</pre>'
    return html(t, content(t, s))
    
def get(name):
    
    commit = gform.get('commit', '')
    
    if not commit and not exists("%s.txt" % name):
        c = '<p>This page does not yet exist. '
        c += '<a href="/@edit/%s">Create it!</a></p>\n' % name
        s = 'Status: 404 Not Found\r\n'
        s += html(name, content(name, c))
        return s
    
    if commit:
        s = git_show("%s:%s.txt" % (commit[0], name))
        if s.startswith("# "):
            s = "# Previous version of " + s[2:]
            c = '**See the [current version](/%s).**' % name
            s = s.split('\n\n', 1)
            s = "%s\n\n%s\n\n%s" % (s[0], c, s[1])
    elif exists("%s.txt" % name):
        s = open("%s.txt" % name).read()
        
    t = pageTitle(s)
    if t:
        s = '\n\n'.join(s.split("\n\n")[1:])
    else:
        t = name
    c = markdown(s)
    if len(gform.keys()) > 0:
        name = "%s?%s" % (name, urlencode(gform))
    return html(t, content(t, c, name))

def post(name): 
    existed = True
    if not exists("%s.txt" % name):
        existed = False
    
    p = pform.get('preview', '')
    r = pform.get('remove', '')
    s = pform.get('text', '')
    if s: s = s[0].replace('\r\n', '\n').replace('\r', '\n')
    
    user = env.get('REMOTE_USER', '')
    
    if user:
        for l in open('.dienw/user.names').read().split('\n'):
            aemail, author = l.split(': ', 1)
            if aemail == user:
                user = '%s <%s>' % (author.strip(), aemail.strip())
                break
    else:
        user = 'Anonymous <anonymous@dienw.com>'
    
    if p and s:
        return edit(name, s).replace('<!--preview-->', markdown(s))
    elif s:
        open("%s.txt" % name, 'w').write(s)
        oldlinks = []
        if existed:
            oldlinks.extend(outboundLinks(name))
        newlinks = links(s)
        for link in oldlinks: 
            if link not in newlinks: 
                os.remove('.dienw/links/%s%%%s' % (name, link))
        for link in newlinks: 
            if link not in oldlinks: 
                open('.dienw/links/%s%%%s' % (name, link), 'w').write('')
        git_add("%s.txt" % name)
        git_commit('%s edited by %s' % (name, user.rsplit(' ', 1)[0]), user)
        # No redirect as we would redirect to ourselves, kind of pointless
        # main() checks for output of post(name) and falls back to get(name)
        # if there is none
    elif r:
        git_remove('%s.txt' % name)
        git_commit('%s removed by %s' % (name, user.rsplit(' ', 1)[0]), user)
        for fn in glob.glob('.dienw/links/%s%%*' % name):
            os.remove(fn)
        open('.dienw/removed', 'a').write('%s\n' % name)
        return redirect("/")
    elif existed:
        return redirect("/@remove/%s" % name)
    else:
        return redirect("/")


def edit(name, c=None):
    commit = gform.get('commit', '')
    if not c and not commit and exists("%s.txt" % name):
        c = open("%s.txt" % name).read()
    elif commit:
        c = git_show("%s:%s.txt" % (commit[0], name))
    elif not c:
        t = name
        c = ''
    
    if c:
        t = pageTitle(c)
        if not t: t = name
        c = cgi.escape(c)
        
    if commit:
        t = 'a previous version of %s' % t
    
    t = "Editing %s" % t
    s = '<!--preview-->\n'
    s += '<form action="/%s" method="POST">\n' % name
    s += '<div id="editing">\n'
    s += '<p><textarea name="text">%s</textarea></p>\n' % c
    s += '<p><input type="submit" name="save" value="Save" /> '
    s += '<input type="submit" name="preview" value="Preview" /></p>\n'
    s += '</form>\n'
    s += '</div>\n'
    return html(t, content(t, s))

def remove(name):
    if exists("%s.txt" % name):
        pt = pageTitle(name=name)
        t = 'Remove %s?' % pt
        c = 'Are you sure you want to remove the page *%s*?\n\n' % pt
        s = '<form action="/%s" method="POST">\n' % name
        s += '<div id="editing">\n'
        s += '<p><a href="/%s">Keep</a> ' % name
        s += '<input type="submit" name="remove" value="Remove" /></p>\n'
        s += '</form>\n'
        s += '</div>\n'
        return html(t, content(t, markdown(c) + s))
    else:
        return notfound(name)

def username(email):
    pass

def info(name):
    commit = gform.get('commit', '')

    if not commit and not exists("%s.txt" % name):
        return notfound(name)
    name = "%s.txt" % name
    if commit:
        s = git_show("%s:%s" % (commit[0], name))
        m = git_commit_log(commit[0])
        if s.startswith("# "):
            s = "# a previous version of " + s[2:]
    else:
        s = open(name).read()
        t = os.stat(name).st_mtime
        lastmod = datetime.datetime.fromtimestamp(t)
    chars = len(s)
    words = len(s.split(' '))
    if not commit:
        inbound = {}
        for link in inboundLinks(name[:-4]):
            if exists("%s.txt" % link):
                inbound[link] = pageTitle(name=link)
            else:
                inbound[link] = link
        outbound = {}
        for link in outboundLinks(name[:-4]):
            if exists("%s.txt" % link):
                outbound[link] = pageTitle(name=link)
            else:
                outbound[link] = link
    history = git_log(name)
    t = "Info on %s" % pageTitle(s)
    s = "## Statistics\n\n"
    if not commit:
        s += "Last edited by\n"
        s += ":    %s\n\n" % history[0]['author']
    else:
        s += "Edited by\n"
        s += ":    %s\n\n" % m['author']
    s += "Word count\n"
    s += ":    %s\n\n" % words
    s += "Character count\n"
    s += ":    %s\n\n" % chars
    if commit:
        s += "Modified on\n"
        s += ":    %s\n\n" % m['atime'].strftime(dstr)
    else:
        s += "Last modified on\n"
        s += ":    %s\n\n" % lastmod.strftime(dstr)
        s += "Linking here\n:"
        for key in inbound.keys():
            s += "    * [%s](/%s)\n" % (inbound[key], key)
        if len(inbound.keys()) == 0:
            s += "    * No pages link here.\n\n"
        s += "Linking to\n:"
        for key in outbound.keys():
            s += "    * [%s](/%s)\n" % (outbound[key], key)
        if len(outbound.keys()) == 0:
            s += "    * This page doesn't link anywhere.\n\n"
    s += "\n"
    s += "## History\n\n"
    if len(history) <= 1:
        s += "There is only one revision of this page.\n\n"
    cut = 1
    # Showing HEAD if we're looking at a different revision
    if commit:
        cut = 0
    for entry in history[cut:]:
        cc = commit and entry['commit'] == commit[0]
        s += "1. <dl><dt>Edited by</dt>\n"
        s += "   <dd>%s</dd>\n" % entry['author']
        s += "   <dt>Date</dt>\n"
        if cc: 
            ds = "   <dd>**[%s](/%s?commit=%s)**</dd>\n"
        else:
            ds = "   <dd>[%s](/%s?commit=%s)\n</dd>"
        s += ds % (entry['atime'].strftime(dstr), name[:-4], entry['commit'])
        s += "   <dt>Compare</dt>\n   <dd><ul>\n"
        if not cc and commit:
            s += "   <li>[current with this](%s)</li>\n" % \
                 "/@diff/%s?commit=%s&commit=%s" % \
                 (name[:-4], commit[0], entry['commit'])
        if not entry == history[0]:
            s += "   <li>[this with latest](%s)</li>\n" % \
                 "/@diff/%s?commit=%s" % (name[:-4], entry['commit'])
        s += "   </ul></dd></dl>\n"
    return html(t, content(t, markdown(s)))

def meta(name):
    
    if name == 'about':
        t = "About This Site"
        c = "This is a [Dienw](http://dienw.com/wiki) based wiki. "
        c += "Dienw is based on [pwyky](http://infomesh.net/pwyky/), "
        c += "[wikiri](http://blitiri.com.ar/git/?p=wikiri) and "
        c += "[git](http://git-scm.com/). "
        c += "To find out more about it, please consult the "
        c += "[Documentation](http://dienw.com/wiki#documentation).\n\n"
        
        p = {
            'about': 'This page.', 
            'search': 'Search the text in the site.', 
            'names': 'Provide a list of all pages.', 
            'needed': 'List of pages that are linked to but not yet made.', 
            'unlinked': 'Pages that are not linked to elsewhere.', 
            'updates': 'Shows the most recent changes.'
        }.items()
        p.sort()
        c += '\n'.join(['* [%s](/@meta/%s) - %s' % (k, k, v) for k, v in p])
    
        return html(t, content(t, markdown(c)))
        
    elif name == 'names': 
       results = [fn[:-4] for fn in glob.glob('*.txt')]
       results.sort()
       results = ['* [%s](/%s)' % (pageTitle(name=fn), fn) for fn in results]
       t = 'All Pages'
       c = 'There are %s pages in this site:\n\n' % len(results)
       c += '\n'.join(results)
       return html(t, content(t, markdown(c)))
    
    elif name == 'updates':
        i = 100
        keys, result = updates(i)
        
        t = 'Updates: Recently Changed Pages'
        c = 'The %s most recent changes in this site are: \n\n' % len(keys)
        for n in keys:
            value = result[n]
            pdate, ptime = tuple(n.split(' '))
            ptime = ptime.rstrip('_')
            c += '* **%s**: ' % pdate
            c += '[%s](/%s) %s\n' % (pageTitle(name=value), value, ptime)
        return html(t, content(t, markdown(c)))
        
    elif name == 'needed': 
        t = 'Needed Pages'
        results = {}
        for fn in glob.glob('*.txt'):
            fn = fn[:-4]
            for needed in outboundLinks(fn):
                if not exists("%s.txt" % needed):
                    if results.has_key(needed):
                        results[needed].append(fn)
                    else:
                        results[needed] = [fn]
        keys = results.keys()
        keys.sort()
        c = 'A list of pages in this wiki that were linked but not '
        c += 'yet created.\n\n'
        for key in keys:
            fp = dict([(uniq, None) for uniq in results[key]]).keys()
            fp.sort()
            c += '* [%s](/%s) from: ' % (key, key)
            c += ', '.join(['[%s](/%s)\n' % (pageTitle(name=v), v) for v in fp])
        if len(keys) == 0:
            c += 'No such pages. All interlinked already exist!'
        return html(t, content(t, markdown(c)))
    
    elif name == 'unlinked':
        t = 'Unlinked Pages'
        c = "The following is a list of pages which aren't linked "
        c += 'to from any other page.\n\n'
        p = ''
        for fn in glob.glob('*.txt'): 
           fn = fn[:-4]
           inbound = inboundLinks(fn)
           if len(inbound) == 0:
              p += '* [%s](/%s) ([Info](/@info/%s))\n' % \
                   (pageTitle(name=fn), fn, fn)
        if not p:
            p += 'No such pages. All pages are interlinked!'
        c += p
        return html(t, content(t, markdown(c)))
    
    elif name == 'search':
        t = 'Search'
        s = '<form action="" method="GET">\n'
        s += 'Search: <input type="text" name="regexp" size="25" />\n'
        s += '<input type="submit" />\n'
        s += '</form>\n'
        regexp = gform.get('regexp', '')
        if regexp:
            r_regexp = re.compile(regexp[0])
            
            results = {}
            for fn in glob.glob('*.txt'): 
               for line in open(fn).read().splitlines(): 
                  find = r_regexp.findall(line)
                  if find: 
                     if results.has_key(fn): 
                        results[fn] += len(find)
                     else:
                         results[fn] = len(find)
            results = [(v, k) for k, v in results.items()]
            results.sort()
            results.reverse()
            results = [(k, v) for v, k in results][:20] # 20 results only!
            
            c = '## Search Result for %r\n\n' % regexp[0]
            for (fn, count) in results: 
                n = fn[:-4]
                c += '* [%s](/%s) - %s matches\n' % \
                     (pageTitle(name=n), n, count)
               
            s += markdown(c)
        return html(t, content(t, s))
    
    elif name == 'feed':
        keys, result = updates(20)
        s = 'Content-Type: application/xml; charset=utf-8\r\n\r\n'
        s += '<?xml version="1.0" encoding="utf-8"?>\n'
        s += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        s += '<title>%s</title>\n' % title
        s += '<link href="%s@meta/feed" rel="self" />\n' % base
        s += '<link href="%s" />\n' % base
        fbase = "tag%s" % base.replace('/', '').replace('http', '')
        pdate, ptime = tuple(keys[0].split(' '))
        ptime = ptime.rstrip('_')
        s += '<updated>%sT%sZ</updated>\n' % (pdate, ptime)
        s += '<id>%s,%s:%s</id>\n' % (fbase, pdate, ptime.replace(':', ''))
        s += '<author><name>Contributors of %s</name></author>\n' % title
        for n in keys:
            pdate, ptime = tuple(n.split(' '))
            ptime = ptime.rstrip('_')
            s += '<entry>\n'
            s += '<title>%s</title>\n' % pageTitle(name=result[n])
            s += '<link href="%s%s" />\n' % (base, result[n])
            s += '<id>%s,%s:/%s</id>\n' % (fbase, pdate, result[n])
            s += '<updated>%sT%sZ</updated>\n' % (pdate, ptime)
            name = "%s.txt" % result[n]
            commit = git_log(name)[0]['commit']
            diff = git_diff(name, "%s^" % commit, commit)
            if diff:
                s += '<content type="xhtml">\n'
                s += '<div xmlns="http://www.w3.org/1999/xhtml">'
                s += '<pre style="white-space: pre-wrap;">'
                s += cgi.escape(diff)
                s += '</pre></div>\n'
                s += '</content>\n'
            s += '</entry>\n'
        s += '</feed>\n'
        return s

def updates(i):
    result = {}
    for name in glob.glob('*.txt'):
        if r_name.match(name[:-4]):
            t = os.stat(name).st_mtime
            lastmod = datetime.datetime.fromtimestamp(t)
            lastmod = lastmod.strftime(dstr)
            while result.has_key(lastmod):
                lastmod += '_'
            result[lastmod] = name[:-4]
    keys = result.keys()
    keys.sort()
    keys.reverse()
    return (keys[:i], result)

def inboundLinks(n):
    return [fn[13:-(len(n)+1)] for fn in glob.glob('.dienw/links/*%%%s' % n)]

def outboundLinks(n):
    return [fn[13+len(n)+1:] for fn in glob.glob('.dienw/links/%s%%*' % n)]

def pageTitle(s=None,name=None):
    if name and exists('%s.txt' % name):
        s = open("%s.txt" % name).read()
    if s:
        if s.startswith('# '):
            return s.split("\n\n")[0][2:].strip()
    return name

def links(s):
    # @@ replace with a regexp matching all markdown links
    s = "<xml>%s</xml>" % markdown(s)
    ls = []
    # cause we care so much about performance
    from xml.etree import ElementTree
    tree = ElementTree.fromstring(s)
    anchors = tree.findall(".//a")
    for anchor in anchors:
        if 'href' in anchor.keys():
            if r_name.match(anchor.get('href')):
                ls.append(anchor.get('href'))
    return ls

def main():
    if method not in ('GET', 'POST'):
        t = 'Method Not Allowed'
        s = 'Status: 405 Method Not Allowed\r\n'
        c = '<p>Sorry, the method <em>%s</em> is not supported.</p>' % method
        s += html(t, content(t, c))
        print s
        return
    
    if '?' in uri: path = uri.split('?', 1)[0]
    else: path = uri
    
    if path == '/':
        path = '/index'
   
    if not path.startswith('/@'):
        action = 'get'
        name = path[1:]
    else:
        i = path.find('/', 2)
        action = path[2:i]
        name = path[(i+1):]
    
    # This should never actually be executed as the regexp of the url-rewrite
    # on the HTTP server should not even pass the request to the script
    if (not r_name.match(name)) and (name != __file__):
        raise Exception, 'Invalid filename: %s' % name
   
    if action == 'get':
        if method == 'POST':
            # In case we preview instead of save
            response = post(name)
            if response:
                print response
                return
        print get(name)
    elif action == 'edit':
        print edit(name)
    elif action == 'remove':
        print remove(name)
    elif action == 'info':
        print info(name)
    elif action == 'meta':
        print meta(name)
    elif action == 'diff':
        print diff(name)
    else:
        print notfound(action)
    return

def handle_cmd():
    print "This is a CGI application. It only runs inside a web server."
    return

if __name__=='__main__': 
    if env.has_key('SCRIPT_NAME'): 
        try: main()
        except: cgi.print_exception()
    else:
        sys.exit(handle_cmd())
