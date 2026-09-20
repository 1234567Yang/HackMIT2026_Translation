"""DeepFace emotion recognition, wrapped in a class so the model is reused across calls."""

from deepface import DeepFace


class DeepFaceRecog:
    """Thin wrapper around DeepFace's emotion analysis."""

    def parseEmotion(self, img):
        """Analyze a face image and return its emotion breakdown.

        Args:
            img: image file path, or a numpy array / BGR image (anything
                DeepFace.analyze's img_path argument accepts).

        Returns:
            {"angry": float, "disgust": float, "fear": float, "happy": float,
            "sad": float, "surprise": float, "neutral": float} for the first
            detected face.
        """
        results = DeepFace.analyze(
            img_path=img,
            actions=["emotion"],
            enforce_detection=False,
        )

        # DeepFace.analyze returns a list, one entry per detected face.
        face = results[0]

        return {k: float(v) for k, v in face["emotion"].items()}
