from flask import Flask, render_template, request, redirect, session, url_for
from flask_socketio import SocketIO, join_room, send
from models import get_db, create_tables
import bcrypt

app = Flask(__name__)
app.secret_key = "secretkey"

socketio = SocketIO(app, manage_session=False)   # ✅ FIX 1 (important for session)

create_tables()

# ---------------- AUTH ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        # ✅ FIX 2 (handle password type safely)
        if user:
            stored_password = user["password"]

            # convert to bytes if needed
            if isinstance(stored_password, str):
                stored_password = stored_password.encode()

            if bcrypt.checkpw(password.encode(), stored_password):
                session["user"] = username
                return redirect(url_for("chat"))

        return "Invalid credentials"

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # ✅ FIX 3 (ensure password stored as bytes)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed)
            )
            db.commit()
            return redirect(url_for("login"))

        except Exception as e:   # ✅ FIX 4 (better error)
            print(e)
            return "User already exists"

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")


# ---------------- CHAT ---------------- #

@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect("/")
    return render_template("chat.html", username=session["user"])


# ---------------- SOCKET ---------------- #

def get_room(user1, user2):
    return "_".join(sorted([user1, user2]))


@socketio.on("join_private")
def join_private(data):
    user = session.get("user")

    # ✅ FIX 5 (prevent crash if not logged in)
    if not user:
        return

    other = data["other_user"]
    room = get_room(user, other)

    join_room(room)

    db = get_db()
    messages = db.execute(
        "SELECT sender, message FROM messages WHERE room=?",
        (room,)
    ).fetchall()

    for msg in messages:
        send(f"{msg['sender']}: {msg['message']}", room=request.sid)


@socketio.on("private_message")
def private_message(data):
    user = session.get("user")

    # ✅ FIX 6 (prevent crash)
    if not user:
        return

    other = data["other_user"]
    message = data["message"]

    room = get_room(user, other)

    db = get_db()
    db.execute(
        "INSERT INTO messages (sender, receiver, room, message) VALUES (?, ?, ?, ?)",
        (user, other, room, message)
    )
    db.commit()

    send(f"{user}: {message}", room=room)


if __name__ == "__main__":
    socketio.run(app, debug=True)