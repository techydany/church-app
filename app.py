from flask import Flask, render_template, request, redirect, session, send_file
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import io, csv, os, json
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "super-secret-key"

# ADMIN LOGIN
ADMIN_USERNAME = "dany"
ADMIN_PASSWORD = "5404"

# FIREBASE (SECURE VIA ENV VARIABLE)
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()


@app.route("/")
def login():
    return render_template("login.html")


@app.route("/admin-login", methods=["POST"])
def admin_login():
    if request.form["username"] == ADMIN_USERNAME and request.form["password"] == ADMIN_PASSWORD:
        session.clear()
        session["admin"] = True
        return redirect("/admin")
    return redirect("/")


@app.route("/user-login", methods=["POST"])
def user_login():
    username = request.form["username"]
    password = request.form["password"]

    for u in db.collection("users").where("username", "==", username).stream():
        if u.to_dict()["password"] == password:
            session.clear()
            session["user"] = username
            return redirect(f"/user/{username}")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/admin")
def admin():
    if not session.get("admin"):
        return "Forbidden", 403

    notices = [{"id": n.id, "text": n.to_dict()["text"]} for n in db.collection("notices").stream()]
    directory = [d.to_dict() for d in db.collection("directory").stream()]
    notifications = [{"id": n.id, **n.to_dict()} for n in db.collection("notifications").stream()]

    return render_template("admin.html",
                           notices=notices,
                           directory=directory,
                           notifications=notifications)


@app.route("/user/<username>")
def user(username):
    if session.get("user") != username:
        return "Forbidden", 403

    user = None
    for u in db.collection("users").where("username", "==", username).stream():
        user = u.to_dict()

    notices = [n.to_dict() for n in db.collection("notices").stream()]
    directory = [d.to_dict() for d in db.collection("directory").stream()]

    notifications = []
    for n in db.collection("notifications").stream():
        data = n.to_dict()
        if data["target"] == "all" or data["target"] == username:
            notifications.append(data)

    return render_template("user.html",
                           user=user,
                           notices=notices,
                           directory=directory,
                           notifications=notifications)


# ---------- NOTICES ----------
@app.route("/add-notice", methods=["POST"])
def add_notice():
    if not session.get("admin"):
        return "Forbidden", 403
    db.collection("notices").add({"text": request.form["text"]})
    return redirect("/admin")


@app.route("/edit-notice/<id>", methods=["POST"])
def edit_notice(id):
    if not session.get("admin"):
        return "Forbidden", 403
    db.collection("notices").document(id).update({"text": request.form["text"]})
    return redirect("/admin")


@app.route("/delete-notice/<id>")
def delete_notice(id):
    if not session.get("admin"):
        return "Forbidden", 403
    db.collection("notices").document(id).delete()
    return redirect("/admin")


# ---------- NOTIFICATIONS ----------
@app.route("/add-notification", methods=["POST"])
def add_notification():
    if not session.get("admin"):
        return "Forbidden", 403
    db.collection("notifications").add({
        "message": request.form["message"],
        "target": request.form["target"],
        "created_at": datetime.now()
    })
    return redirect("/admin")


@app.route("/delete-notification/<id>")
def delete_notification(id):
    if not session.get("admin"):
        return "Forbidden", 403
    db.collection("notifications").document(id).delete()
    return redirect("/admin")


# ---------- DIRECTORY ----------
@app.route("/add-directory", methods=["POST"])
def add_directory():
    if not session.get("admin"):
        return "Forbidden", 403
    db.collection("directory").add({
        "name": request.form["name"],
        "address": request.form["address"],
        "phone": request.form["phone"]
    })
    return redirect("/admin")


# ---------- USERS ----------
@app.route("/add-user", methods=["POST"])
def add_user():
    if not session.get("admin"):
        return "Forbidden", 403
    db.collection("users").add({
        "username": request.form["username"],
        "password": request.form["password"],
        "name": request.form["name"],
        "address": request.form["address"],
        "phone": request.form["phone"]
    })
    return redirect("/admin")


# ---------- EXPORT ----------
@app.route("/export/pdf")
def export_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for d in db.collection("directory").stream():
        p = d.to_dict()
        pdf.multi_cell(0, 10, f"{p['name']} | {p['address']} | {p['phone']}")

    return send_file(io.BytesIO(pdf.output(dest="S").encode("latin-1")),
                     download_name="directory.pdf",
                     as_attachment=True)


@app.route("/export/excel")
def export_excel():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Address", "Phone"])

    for d in db.collection("directory").stream():
        p = d.to_dict()
        writer.writerow([p["name"], p["address"], p["phone"]])

    return send_file(io.BytesIO(output.getvalue().encode()),
                     download_name="directory.csv",
                     as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
