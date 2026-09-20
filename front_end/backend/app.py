from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from llm import REQUIRED_FIELDS, generate_better_prompt

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="")
CORS(app)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    target = FRONTEND_DIST / path if path else None

    if target and target.is_file():
        return send_from_directory(FRONTEND_DIST, path)

    return send_from_directory(FRONTEND_DIST, "index.html")


@app.route("/api/review", methods=["POST"])
def review():
    data = request.get_json(force=True, silent=True) or {}

    missing = [field for field in REQUIRED_FIELDS if not data.get(field)]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        improved_prompt = generate_better_prompt(data)
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 502

    return jsonify({"improved_prompt": improved_prompt})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
