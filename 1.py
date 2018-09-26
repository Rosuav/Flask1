from flask import Flask, render_template, g, Markup, request, redirect, url_for, Response
import psycopg2
import time
import json
import subprocess
import config # Local config variables and passwords, not in source control
app = Flask(__name__)
try: unicode
except NameError: unicode = str

# Enable Unicode return values for all database queries
# This would be the default in Python 3, but in Python 2, we
# need to enable these two extensions.
# http://initd.org/psycopg/docs/usage.html#unicode-handling
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

def get_db():
	if not hasattr(g, 'pgsql'):
		# Pull in the actual connection string from a non-git-managed file
		g.pgsql = psycopg2.connect(config.db_connection_string)
	return g.pgsql

@app.template_filter('preformat')
def preformat(s):
	"""Preformat a block of text, converting it into HTML.

	Translates newlines into line breaks or paragraphs, preserving
	indentation (by transforming leading spaces into &nbsp;) and other
	sequences of blank spaces. Does not translate tabs.

	Adds a space to the end of every logical line, to allow urlize to
	run to the end of a line rather than try to swallow a <br> or </p>.
	"""
	if not isinstance(s, unicode): s = s.decode("utf-8")
	s = Markup.escape(s)
	s = s.replace("\n ", Markup("\n&nbsp;")) # Spaces after newlines become non-breaking
	s = s.replace("  ", Markup(" &nbsp;")) # Repeated spaces alternate normal and non-breaking
	s = s.replace("\r\n\r\n", Markup(" </p>\n\n<p>")) # Double newlines become a paragraph
	s = s.replace("\r\n", Markup(" <br>\n")) # Single newlines become line breaks
	return s

@app.template_filter('trimspaces')
def trimspaces(s):
	"""After urlize, trim off the extra spaces from preformat()."""
	return s.replace(Markup(" </p>"),Markup("</p>")).replace(Markup(" <br>"),Markup("<br>"))

@app.route("/")
def view():
	if 'q' in request.args:
		if request.authorization and request.args['q']!='w':
			return redirect(url_for('view'))
		else:
			return Response(
				'<a href="'+url_for('view')+'">Invalid query, click here to retry</a>',
				401, {'WWW-Authenticate': 'Basic realm="1"'})
	auth = request.authorization
	auth = bool(auth and config.auth == "%s/%s"%(auth.username, auth.password))
	db = get_db()
	query = "select id,date,title,content,publish from one where publish"
	params = []
	if auth: query += ">= false"
	if 'id' in request.args:
		query += " and id=%s"
		params.append(request.args['id'])
	search = request.args.get('search', '') # Needed for the more link too
	if search:
		query += " and (date=%s or title ilike %s or content ilike %s)"
		params.extend((search, "%"+search+"%", "%"+search+"%"))
	more = 'more' in request.args # We don't care what its value is - it might even be blank
	if 'recent' in request.args: query += " order by id desc"
	else: query += " order by date desc, id desc"
	if not more: query += " limit 51"
	cur = db.cursor()
	cur.execute(query, params)
	rows = cur.fetchall()
	morelink = ""
	if not more and len(rows)>50:
		rows.pop() # Discard the last row. We only care that it's present (and therefore we need a "More" link)
		search = "" # ?search
		morelink = '<p><a href="?search='+search+'&amp;more=1">More...</a></p>'
	db.commit()
	return render_template("view.html", rows=rows, more=more, morelink=morelink, auth=auth)

# The previous version of this web site used actual PHP files. Provide redirects
# to catch any duff links (which shouldn't exist in the wild, as index will have
# been referenced as the directory name alone, and addent is private).
@app.route("/addent.php")
def addent_redirect():
	return redirect(url_for('addent'), 301)
@app.route("/index.php")
def view_redirect():
	return redirect(url_for('view'), 301)

@app.route("/addent", methods=["GET", "POST"])
def addent():
	auth = request.authorization
	if not auth or config.auth != "%s/%s"%(auth.username, auth.password):
		return redirect(url_for('view'))
	db = get_db()
	cur = db.cursor()
	row = None
	date, title, content, publish = time.strftime("%Y%m%d"), '', '', ''
	if 'id' in request.args:
		cur.execute("select date,title,content,publish from one where id=%s",(request.args["id"],))
		row = cur.fetchone()
		if row:
			date, title, content, publish = row
			publish = Markup(('Currently published.' if publish else 'Private entry.') +
				'<input type="hidden" name="id" value="' + request.args["id"] + '">')
	savenote = ""
	if request.method == "POST":
		rf = request.form # We're gonna do a lot with this
		if "id" in rf:
			cur.execute("update one set date=%s,title=%s,content=%s,publish=%s where id=%s",
				(rf["date"][:8], rf["title"], rf["content"], rf['action'] == 'Publish', rf["id"]))
			savenote = '<div class="status"><a href=".?id=' + rf['id'] + '">Updated.</a></div>'
		else:
			cur.execute("insert into one (date,title,content,publish) values (%s,%s,%s,%s) returning id",
				(rf["date"][:8], rf["title"], rf["content"], rf['action'] == 'Publish'))
			savenote = '<div class="status"><a href=".?id=%d">Inserted.</a></div>' % cur.fetchone()[0]
	db.commit()
	return render_template("addent.html", date=date, title=title,
		content=content, publish=publish, savenote=Markup(savenote))

@app.route("/postfix/")
def postfix():
	"""Provide read-only access to the processes used for mail transfer"""
	# Created per committee demand, 2018-09-26
	info = subprocess.check_output(["sudo", "/bin/systemctl", "status", "postfix", "--output", "json"])
	response = "Current processes used for mail transfer:<ul>"
	for line in info.decode().split("\n\n")[-1].split("\n"):
		if not line.startswith("{"): continue
		proc = json.loads(line)
		if "_PID" not in proc: continue
		if "_EXE" in proc:
			response += '<li><a href="%s">%s: %s</a></li>' % (
				proc["_PID"], proc["_PID"], proc["_EXE"])
		else:
			response += '<li>%s: nothing readable</li>' % proc["_PID"]
	return response + "</ul>"

@app.route("/postfix/<id>")
def postfix_proc(id):
	info = subprocess.check_output(["sudo", "/bin/systemctl", "status", "postfix", "--output", "json"])
	for line in info.decode().split("\n\n")[-1].split("\n"):
		if not line.startswith("{"): continue
		proc = json.loads(line)
		if proc.get("_PID") == id and "_EXE" in proc:
			return b"<pre>\r\n" + subprocess.check_output(["hd", proc["_EXE"]]) + b"</pre>"
	return "Unauthorized or too slow", 401

if __name__ == "__main__":
	import logging
	logging.basicConfig(level=logging.DEBUG)
	app.run(host='0.0.0.0')
