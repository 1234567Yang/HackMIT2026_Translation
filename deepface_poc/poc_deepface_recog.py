"""Minimal DeepFace emotion-recognition POC."""

import json
import os

from deepface import DeepFace


class DeepFaceRecog:
    """Thin wrapper around DeepFace's emotion analysis."""

    def recognize(self, img):
        """Analyze a face image and return its emotion breakdown.

        Args:
            img: image file path, or a numpy array / BGR image (anything
                DeepFace.analyze's img_path argument accepts).

        Returns:
            {'emotion': {...}, 'dominant_emotion': str} for the first
            detected face.
        """
        results = DeepFace.analyze(
            img_path=img,
            actions=["emotion"],
            enforce_detection=False,
        )

        # DeepFace.analyze returns a list, one entry per detected face.
        face = results[0]

        return {
            "emotion": {k: float(v) for k, v in face["emotion"].items()},
            "dominant_emotion": face["dominant_emotion"],
        }


if __name__ == "__main__":
    image_path = os.path.join(os.path.dirname(__file__), "test9.jpg")

    recognizer = DeepFaceRecog()
    result = recognizer.recognize(image_path)

    print(json.dumps(result, indent=2))
