from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import joblib

app = Flask(__name__)
CORS(app)

# Load trained Random Forest model
model = joblib.load("customer_model.pkl")

FEATURES = [
    "Fresh",
    "Milk",
    "Grocery",
    "Frozen",
    "Detergents_Paper",
    "Delicassen"
]

# Business meaning of the two learned clusters
SEGMENT_INFO = {
    0: {
        "name": "Moderate Spending Customer",
        "short": "Moderate Spending"
    },
    1: {
        "name": "High Spending Customer",
        "short": "High Spending"
    }
}


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "error": "Please send valid JSON data."
            }), 400

        values = {
            "fresh": data.get("fresh"),
            "milk": data.get("milk"),
            "grocery": data.get("grocery"),
            "frozen": data.get("frozen"),
            "detergents_paper": data.get("detergents_paper"),
            "delicassen": data.get("delicassen")
        }

        missing = [
            key for key, value in values.items()
            if value is None
        ]

        if missing:
            return jsonify({
                "success": False,
                "error": "All customer spending values are required.",
                "missing_features": missing
            }), 400

        # Convert inputs to numbers
        fresh = float(values["fresh"])
        milk = float(values["milk"])
        grocery = float(values["grocery"])
        frozen = float(values["frozen"])
        detergents_paper = float(values["detergents_paper"])
        delicassen = float(values["delicassen"])

        spending_values = {
            "Fresh": fresh,
            "Milk": milk,
            "Grocery": grocery,
            "Frozen": frozen,
            "Detergents & Paper": detergents_paper,
            "Delicassen": delicassen
        }

        if min(spending_values.values()) < 0:
            return jsonify({
                "success": False,
                "error": "Spending values cannot be negative."
            }), 400

        # Keep exact training feature names/order
        customer = pd.DataFrame([{
            "Fresh": fresh,
            "Milk": milk,
            "Grocery": grocery,
            "Frozen": frozen,
            "Detergents_Paper": detergents_paper,
            "Delicassen": delicassen
        }])

        # Predict learned DBSCAN-derived segment
        prediction = int(model.predict(customer)[0])
        probabilities = model.predict_proba(customer)[0]

        # Map model probabilities to meaningful labels
        probability_result = {}
        for cluster, probability in zip(model.classes_, probabilities):
            cluster_id = int(cluster)
            segment = SEGMENT_INFO.get(cluster_id, {"short": f"Cluster {cluster_id}"})
            probability_result[segment["short"]] = round(float(probability) * 100, 2)

        # Main confidence = probability of predicted class
        predicted_class_index = list(model.classes_).index(prediction)
        confidence = round(float(probabilities[predicted_class_index]) * 100, 2)

        # Explain the customer's own spending pattern
        total_spending = round(sum(spending_values.values()), 2)
        top_categories = sorted(
            spending_values.items(),
            key=lambda item: item[1],
            reverse=True
        )[:2]

        top_category_names = [item[0] for item in top_categories]
        top_category_text = " and ".join(top_category_names)

        segment = SEGMENT_INFO.get(
            prediction,
            {
                "name": f"Cluster {prediction}",
                "short": f"Cluster {prediction}"
            }
        )

        if prediction == 1:
            why = (
                f"The model matched this customer more strongly with the high-spending group. "
                f"Their total entered spending is {total_spending:,.0f}, with the largest amounts in "
                f"{top_category_text}. This overall spending pattern is closer to the learned High Spending segment."
            )
        else:
            why = (
                f"The model matched this customer more strongly with the moderate-spending group. "
                f"Their total entered spending is {total_spending:,.0f}, with the largest amounts in "
                f"{top_category_text}. This overall pattern is closer to the learned Moderate Spending segment "
                f"than to the smaller high-spending group."
            )

        return jsonify({
            "success": True,
            "customer": {
                "fresh": fresh,
                "milk": milk,
                "grocery": grocery,
                "frozen": frozen,
                "detergents_paper": detergents_paper,
                "delicassen": delicassen,
                "total_spending": total_spending,
                "top_categories": top_category_names
            },
            "prediction": {
                "cluster": prediction,
                "segment_name": segment["name"],
                "confidence": confidence,
                "why": why,
                "probabilities": probability_result
            }
        })

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Please enter valid numerical values."
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
