"""Flask web server for remote dashboard access."""

from __future__ import annotations

import logging
import socket
import threading
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template

from src.core.models import Brand
from src.db.repository import Repository

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
    app.config["JSON_SORT_KEYS"] = False

    # Repository for database access
    repo = Repository()

    @app.route("/")
    def index():
        """Main dashboard page."""
        return render_template("dashboard.html")

    @app.route("/api/summary")
    def api_summary():
        """Get summary statistics."""
        total_items = 0
        total_opportunities = 0
        total_restricted = 0
        all_scores: list[int] = []
        brand_stats = {}

        for brand in Brand:
            candidates = repo.get_candidates_by_brand(brand, active_only=True)
            items_count = len(candidates)
            opportunities = 0
            restricted = 0
            scores: list[int] = []
            total_profit = Decimal("0")

            for candidate in candidates:
                if candidate.id:
                    latest = repo.get_latest_score(candidate.id)
                    if latest:
                        scores.append(latest.score)
                        all_scores.append(latest.score)
                        if latest.score >= 60:
                            opportunities += 1
                        total_profit += latest.profit_net

                    spapi = repo.get_latest_spapi_snapshot(candidate.id)
                    if spapi and spapi.is_restricted:
                        restricted += 1

            avg_score = sum(scores) / len(scores) if scores else 0

            brand_stats[brand.value] = {
                "items": items_count,
                "opportunities": opportunities,
                "avg_score": round(avg_score, 1),
                "total_profit": float(total_profit),
                "restricted": restricted,
            }

            total_items += items_count
            total_opportunities += opportunities
            total_restricted += restricted

        overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0

        return jsonify({
            "total_items": total_items,
            "opportunities": total_opportunities,
            "avg_score": round(overall_avg, 1),
            "restricted": total_restricted,
            "brands": brand_stats,
            "updated_at": datetime.now().isoformat(),
        })

    @app.route("/api/scores/<brand>")
    def api_brand_scores(brand: str):
        """Get scores for a specific brand."""
        try:
            brand_enum = Brand(brand)
        except ValueError:
            return jsonify({"error": f"Unknown brand: {brand}"}), 404

        candidates = repo.get_candidates_by_brand(brand_enum, active_only=True)
        results = []

        for candidate in candidates:
            if candidate.id:
                latest = repo.get_latest_score(candidate.id)
                if latest:
                    results.append({
                        "part_number": candidate.part_number,
                        "asin": candidate.asin,
                        "title": candidate.title or "",
                        "score": latest.score,
                        "profit": float(latest.profit_net),
                        "margin": float(latest.margin_net),
                        "scenario": latest.winning_scenario,
                        "updated": latest.calculated_at.isoformat() if latest.calculated_at else None,
                    })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        return jsonify({
            "brand": brand,
            "count": len(results),
            "items": results,
        })

    @app.route("/api/top")
    def api_top_opportunities():
        """Get top opportunities across all brands."""
        all_results = []

        for brand in Brand:
            candidates = repo.get_candidates_by_brand(brand, active_only=True)

            for candidate in candidates:
                if candidate.id:
                    latest = repo.get_latest_score(candidate.id)
                    if latest and latest.score >= 60:
                        all_results.append({
                            "brand": brand.value,
                            "part_number": candidate.part_number,
                            "asin": candidate.asin,
                            "title": candidate.title or "",
                            "score": latest.score,
                            "profit": float(latest.profit_net),
                            "margin": float(latest.margin_net),
                        })

        # Sort by score descending, take top 20
        all_results.sort(key=lambda x: x["score"], reverse=True)

        return jsonify({
            "count": len(all_results[:20]),
            "items": all_results[:20],
        })

    @app.route("/api/score-distribution")
    def api_score_distribution():
        """Get score distribution for histogram."""
        buckets = [0] * 5  # 0-20, 20-40, 40-60, 60-80, 80-100

        for brand in Brand:
            candidates = repo.get_candidates_by_brand(brand, active_only=True)

            for candidate in candidates:
                if candidate.id:
                    latest = repo.get_latest_score(candidate.id)
                    if latest:
                        bucket = min(latest.score // 20, 4)
                        buckets[bucket] += 1

        return jsonify({
            "buckets": [
                {"range": "0-20", "count": buckets[0]},
                {"range": "20-40", "count": buckets[1]},
                {"range": "40-60", "count": buckets[2]},
                {"range": "60-80", "count": buckets[3]},
                {"range": "80-100", "count": buckets[4]},
            ],
            "total": sum(buckets),
        })

    return app


class WebServer:
    """Manages the Flask web server in a background thread."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5050) -> None:
        self.host = host
        self.port = port
        self._app: Flask | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def url(self) -> str:
        """Get the URL to access the dashboard."""
        # Get local IP for display
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "localhost"

        return f"http://{local_ip}:{self.port}"

    def start(self) -> str:
        """Start the web server. Returns the URL."""
        if self._running:
            return self.url

        self._app = create_app()
        self._running = True

        def run_server():
            # Suppress Flask's default logging
            import logging as flask_logging
            flask_logging.getLogger("werkzeug").setLevel(flask_logging.ERROR)

            try:
                self._app.run(
                    host=self.host,
                    port=self.port,
                    debug=False,
                    use_reloader=False,
                    threaded=True,
                )
            except Exception as e:
                logger.error(f"Web server error: {e}")
            finally:
                self._running = False

        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()

        logger.info(f"Web dashboard started at {self.url}")
        return self.url

    def stop(self) -> None:
        """Stop the web server."""
        self._running = False
        # Flask doesn't have a clean shutdown in threaded mode,
        # but since it's a daemon thread, it will stop when the app exits
        logger.info("Web dashboard stopped")
