from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import logging
from datetime import datetime
import random

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# --- Simulated test registry (replace with DB/real data source) ---
TEST_REGISTRY = [
    {"id": "TC001", "name": "Checkout Flow", "component": "payments", "last_run": "2024-06-01", "avg_duration_s": 45, "defect_history": 8, "business_criticality": 10},
    {"id": "TC002", "name": "User Login", "component": "auth", "last_run": "2024-06-02", "avg_duration_s": 12, "defect_history": 5, "business_criticality": 9},
    {"id": "TC003", "name": "Product Search", "component": "catalog", "last_run": "2024-06-01", "avg_duration_s": 20, "defect_history": 3, "business_criticality": 7},
    {"id": "TC004", "name": "Order History", "component": "orders", "last_run": "2024-05-28", "avg_duration_s": 30, "defect_history": 2, "business_criticality": 6},
    {"id": "TC005", "name": "Password Reset", "component": "auth", "last_run": "2024-05-20", "avg_duration_s": 18, "defect_history": 4, "business_criticality": 8},
    {"id": "TC006", "name": "Inventory Update", "component": "catalog", "last_run": "2024-06-03", "avg_duration_s": 60, "defect_history": 1, "business_criticality": 5},
    {"id": "TC007", "name": "Payment Refund", "component": "payments", "last_run": "2024-05-15", "avg_duration_s": 55, "defect_history": 7, "business_criticality": 10},
    {"id": "TC008", "name": "Email Notification", "component": "notifications", "last_run": "2024-06-02", "avg_duration_s": 10, "defect_history": 1, "business_criticality": 4},
    {"id": "TC009", "name": "Cart Management", "component": "payments", "last_run": "2024-06-01", "avg_duration_s": 35, "defect_history": 6, "business_criticality": 9},
    {"id": "TC010", "name": "Admin Dashboard", "component": "admin", "last_run": "2024-05-10", "avg_duration_s": 25, "defect_history": 2, "business_criticality": 3},
]

DEFAULT_WEIGHTS = {
    "business_criticality": 0.40,
    "defect_history": 0.30,
    "code_change_relevance": 0.20,
    "execution_time_penalty": 0.10,
}

COVERAGE_COMPONENTS = ["payments", "auth", "catalog", "orders", "notifications", "admin"]


def score_test(test: dict, changed_components: list, weights: dict) -> dict:
    w = weights
    bc = test["business_criticality"] / 10.0
    dh = min(test["defect_history"] / 10.0, 1.0)
    cc = 1.0 if test["component"] in changed_components else 0.2
    # Penalize long tests slightly (normalize to 0-1, invert)
    et_penalty = 1.0 - min(test["avg_duration_s"] / 120.0, 1.0)

    score = (
        w["business_criticality"] * bc +
        w["defect_history"] * dh +
        w["code_change_relevance"] * cc +
        w["execution_time_penalty"] * et_penalty
    )

    justification = (
        f"Business criticality {test['business_criticality']}/10"
        + (f"; component '{test['component']}' directly changed" if cc == 1.0 else f"; component '{test['component']}' not in change set")
        + f"; {test['defect_history']} historical defects"
        + f"; avg run time {test['avg_duration_s']}s"
    )

    return {**test, "score": round(score, 4), "justification": justification, "code_change_hit": cc == 1.0}


def compute_release_risk(prioritized: list, changed_components: list) -> dict:
    avg_score = sum(t["score"] for t in prioritized) / len(prioritized) if prioritized else 0
    high_risk_tests = [t for t in prioritized if t["score"] >= 0.7]
    risk_level = "HIGH" if avg_score >= 0.65 else "MEDIUM" if avg_score >= 0.45 else "LOW"
    return {
        "risk_level": risk_level,
        "avg_priority_score": round(avg_score, 3),
        "high_risk_test_count": len(high_risk_tests),
        "changed_components": changed_components,
        "recommendation": (
            "Block release — critical tests at risk." if risk_level == "HIGH"
            else "Proceed with caution — review flagged tests." if risk_level == "MEDIUM"
            else "Safe to release after test suite passes."
        )
    }


def find_coverage_gaps(prioritized: list, changed_components: list) -> list:
    covered = {t["component"] for t in prioritized}
    gaps = []
    for comp in COVERAGE_COMPONENTS:
        if comp in changed_components and comp not in covered:
            gaps.append({"component": comp, "gap": "Changed but no tests selected"})
        elif comp not in covered:
            gaps.append({"component": comp, "gap": "No tests in prioritized suite"})
    return gaps


@app.route("/")
def home():
    return render_template("index.html")


@app.post("/api/prioritize")
def prioritize():
    data = request.get_json() or {}
    changed_components = data.get("changed_components", [])
    weights = {**DEFAULT_WEIGHTS, **data.get("weights", {})}

    # Normalize weights to sum to 1
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    scored = [score_test(t, changed_components, weights) for t in TEST_REGISTRY]
    scored.sort(key=lambda x: x["score"], reverse=True)

    release_risk = compute_release_risk(scored, changed_components)
    coverage_gaps = find_coverage_gaps(scored, changed_components)

    return jsonify({
        "prioritized_tests": scored,
        "release_risk": release_risk,
        "coverage_gaps": coverage_gaps,
        "weights_used": weights,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    })


@app.get("/api/components")
def get_components():
    return jsonify({"components": COVERAGE_COMPONENTS})


if __name__ == "__main__":
    app.run(debug=True)
