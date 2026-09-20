import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from analyze_single_response_str import analyze_user_input_from_text
from analyze_whole_conversation_llm import analyze_whole_conversation_llm
from choose_voice import choose_voice
from conversation_ws import register_conversation_ws
from generate_better_prompt import REQUIRED_FIELDS, generate_better_prompt
from use_chatgpt import load_env
from xai_text_to_speech import XaiTextToSpeech

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="")
CORS(app)
register_conversation_ws(app)


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


@app.route("/analyze_single_response", methods=["POST"])
def analyze_single_response():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "")

    suggestion = analyze_user_input_from_text(text)

    return jsonify({"suggestion": suggestion})


@app.route("/analyze_whole_conversation", methods=["POST"])
def analyze_whole_conversation():
    data = request.get_json(force=True, silent=True) or {}
    conversation_text = data.get("conversation", "")

    try:
        feedback = analyze_whole_conversation_llm(conversation_text)
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 502

    return jsonify({"feedback": feedback})


@app.route("/generate_voice", methods=["POST"])
def generate_voice():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "")
    voice_id = data.get("voice_id") or "eve"

    load_env()
    token = os.getenv("XAI_API_KEY")
    if not token:
        return jsonify({"error": "XAI_API_KEY is not set. Add it to your .env file."}), 502

    tts = XaiTextToSpeech(token=token, voice_id=voice_id)
    try:
        audio = tts.speak(text)
    except (ValueError, RuntimeError) as error:
        return jsonify({"error": str(error)}), 502

    return Response(audio, mimetype="audio/mpeg")


@app.route("/getbestvoice", methods=["POST"])
def getbestvoice():
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get("prompt", "")

    load_env()
    token = os.getenv("XAI_API_KEY")
    if not token:
        return jsonify({"error": "XAI_API_KEY is not set. Add it to your .env file."}), 502

    tts = XaiTextToSpeech(token=token)
    try:
        voice_id = choose_voice(tts, prompt)
    except (ValueError, RuntimeError) as error:
        return jsonify({"error": str(error)}), 502

    return jsonify({"voice_id": voice_id})


if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)
