import flask
app = flask.Flask(__name__)

@app.route("/")
def view():
	return render_template("view.html")

if __name__ == "__main__":
	app.run(host='0.0.0.0')
