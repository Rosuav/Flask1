from flask import Flask, render_template, g, Markup, request
import psycopg2
app = Flask(__name__)

def get_db():
	if not hasattr(g, 'pgsql'):
		# Pull in the actual connection string from a non-git-managed file
		import config
		g.pgsql = psycopg2.connect(config.db_connection_string)
	return g.pgsql

@app.template_filter('preformat')
def preformat(s):
	"""Preformat a block of text, converting it into HTML.

	Translates newlines into line breaks or paragraphs, preserving
	indentation (by transforming leading spaces into &nbsp;) and other
	sequences of blank spaces. Does not translate tabs.
	"""
	s = Markup.escape(s.decode('utf-8'))
	s = s.replace("\n ",Markup("\n&nbsp;")) # Spaces after newlines become non-breaking
	s = s.replace("  ",Markup(" &nbsp;")) # Repeated spaces alternate normal and non-breaking
	s = s.replace("\r\n\r\n",Markup("</p>\n\n<p>")) # Double newlines become a paragraph
	s = s.replace("\r\n",Markup("<br>\n")) # Single newlines become line breaks
	return s

@app.route("/")
def view():
	db = get_db()
	query = "select id,date,title,content,publish from one where publish"
	params = []
	# TODO: Check query parameters and modify the SQL statement
	# if authenticated: query += ">= false"
	if 'id' in request.args:
		query += " and id=%s"
		params.append(request.args['id'])
	# if ?search: query += " and (date=%s or title ilike %s or content ilike %s)"; params.extend((?search, "%"+?search+"%", "%"+?search+"%"))
	more = False; # if ?more: more=True
	# if ?recent: query += " order by id desc"; else:
	query += " order by date desc, id desc"
	if not more: query += " limit 51"
	cur = db.cursor()
	cur.execute(query, params)
	rows = cur.fetchall()
	morelink = ""
	if not more and len(rows)>50:
		rows.pop() # Discard the last row. We only care that it's present (and therefore we need a "More" link)
		search = "" # ?search
		morelink = '<p><a href="?search='+search+'&amp;more=1">More...</a></p>'
	return render_template("view.html", rows=rows, morelink=morelink)

if __name__ == "__main__":
	import logging
	logging.basicConfig(level=logging.DEBUG)
	app.run(host='0.0.0.0')
