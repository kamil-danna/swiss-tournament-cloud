import os
import math
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import requests

app = Flask(__name__)
CORS(app)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password123@localhost:27017/")
PLAYER_SERVICE_URL = os.getenv("PLAYER_SERVICE_URL", "http://localhost:3001")

client = MongoClient(MONGO_URI)
db = client["tournamentdb"]
tournaments_col = db["tournaments"]

BYE_ID = 0
BYE_NAME = "BYE"

def compute_standings(tournament):
    players = tournament.get("players", [])
    matches = tournament.get("matches", [])
    
    stats = {}
    for p in players:
        p_id = p["id"]
        stats[p_id] = {
            "id": p_id,
            "nome": p["nome"],
            "cognome": p["cognome"],
            "ritirato": p.get("ritirato", False),
            "points": 0,
            "matches_played": 0,
            "matches_won": 0,
            "opponents": [],
            "lost_rounds_sq_sum": 0
        }

    for m in matches:
        if not m.get("concluso", False):
            continue
        
        p1 = m["player1_id"]
        p2 = m["player2_id"]
        esito = m.get("esito")
        rnd = m["round"]

        if p2 == BYE_ID:
            if p1 in stats:
                stats[p1]["points"] += 3
                stats[p1]["matches_won"] += 1
                stats[p1]["matches_played"] += 1
            continue

        if p1 in stats and p2 in stats:
            stats[p1]["opponents"].append(p2)
            stats[p2]["opponents"].append(p1)
            stats[p1]["matches_played"] += 1
            stats[p2]["matches_played"] += 1

            if esito == "win_p1":
                stats[p1]["points"] += 3
                stats[p1]["matches_won"] += 1
                stats[p2]["lost_rounds_sq_sum"] += (rnd ** 2)
            elif esito == "win_p2":
                stats[p2]["points"] += 3
                stats[p2]["matches_won"] += 1
                stats[p1]["lost_rounds_sq_sum"] += (rnd ** 2)
            elif esito == "double_loss":
                stats[p1]["lost_rounds_sq_sum"] += (rnd ** 2)
                stats[p2]["lost_rounds_sq_sum"] += (rnd ** 2)
            elif esito == "drop_p1":
                stats[p2]["points"] += 3
                stats[p2]["matches_won"] += 1
                stats[p1]["lost_rounds_sq_sum"] += (rnd ** 2)
                stats[p1]["ritirato"] = True
            elif esito == "drop_p2":
                stats[p1]["points"] += 3
                stats[p1]["matches_won"] += 1
                stats[p2]["lost_rounds_sq_sum"] += (rnd ** 2)
                stats[p2]["ritirato"] = True

    mw = {}
    for pid, s in stats.items():
        if s["matches_played"] == 0:
            mw[pid] = 0.33
        else:
            mw[pid] = max(0.33, s["matches_won"] / s["matches_played"])

    for pid, s in stats.items():
        opps = s["opponents"]
        s["omw"] = sum(mw[op] for op in opps if op in mw) / len(opps) if opps else 0.33

    for pid, s in stats.items():
        opps = s["opponents"]
        s["oomw"] = sum(stats[op]["omw"] for op in opps if op in stats) / len(opps) if opps else 0.33

    standings = list(stats.values())
    standings.sort(
        key=lambda x: (
            x["points"],
            round(x["omw"], 4),
            round(x["oomw"], 4),
            -x["lost_rounds_sq_sum"]
        ),
        reverse=True
    )
    return standings

@app.route("/tournaments", methods=["POST"])
def create_tournament():
    try:
        res = requests.get(f"{PLAYER_SERVICE_URL}/players")
        if res.status_code != 200:
            return jsonify({"error": "Impossibile recuperare i giocatori"}), 500
        
        all_players = res.json()
        active_players = [p for p in all_players if not p.get("ritirato", False)]
        count = len(active_players)
        if count < 2:
            return jsonify({"error": "Servono almeno 2 giocatori attivi per avviare un torneo"}), 400

        total_rounds = math.ceil(math.log2(count))
        tournament = {
            "name": request.json.get("name", "Torneo Svizzera"),
            "total_rounds": total_rounds,
            "current_round": 0,
            "players": active_players,
            "matches": [],
            "status": "created"
        }
        inserted = tournaments_col.insert_one(tournament)
        return jsonify({"message": "Torneo creato", "tournament_id": str(inserted.inserted_id), "total_rounds": total_rounds}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/tournaments/<tournament_id>/next-round", methods=["POST"])
def next_round(tournament_id):
    from bson.objectid import ObjectId
    t = tournaments_col.find_one({"_id": ObjectId(tournament_id)})
    if not t:
        return jsonify({"error": "Torneo non trovato"}), 404

    curr_round = t.get("current_round", 0)
    for m in t.get("matches", []):
        if m["round"] == curr_round and not m.get("concluso", False):
            return jsonify({"error": f"Il round {curr_round} non è ancora terminato"}), 400

    if curr_round >= t["total_rounds"]:
        tournaments_col.update_one({"_id": ObjectId(tournament_id)}, {"$set": {"status": "finished"}})
        return jsonify({"message": "Torneo già completato", "status": "finished"}), 200

    next_r = curr_round + 1
    standings = compute_standings(t)
    available = [p for p in standings if not p.get("ritirato", False)]

    bye_match = None
    if len(available) % 2 != 0:
        bye_player = None
        for cand in reversed(available):
            had_bye = any(
                (m["player1_id"] == cand["id"] or m["player2_id"] == cand["id"]) and m["player2_id"] == BYE_ID
                for m in t.get("matches", [])
            )
            if not had_bye:
                bye_player = cand
                break
        
        if not bye_player:
            bye_player = available[-1]

        available.remove(bye_player)
        bye_match = {
            "round": next_r,
            "player1_id": bye_player["id"],
            "player1_name": f"{bye_player['cognome']} {bye_player['nome']}",
            "player2_id": BYE_ID,
            "player2_name": BYE_NAME,
            "esito": "win_p1",
            "concluso": True
        }

    past_pairs = set()
    for m in t.get("matches", []):
        past_pairs.add(tuple(sorted([m["player1_id"], m["player2_id"]])))

    def pair_players(pool):
        if not pool:
            return []
        p1 = pool[0]
        for i in range(1, len(pool)):
            p2 = pool[i]
            pair_key = tuple(sorted([p1["id"], p2["id"]]))
            if pair_key not in past_pairs:
                remainder = pool[1:i] + pool[i+1:]
                sub_pairs = pair_players(remainder)
                if sub_pairs is not None:
                    return [(p1, p2)] + sub_pairs
        return None

    paired = pair_players(available)
    if paired is None:
        paired = []
        for i in range(0, len(available), 2):
            paired.append((available[i], available[i+1]))

    new_matches = []
    for p1, p2 in paired:
        new_matches.append({
            "round": next_r,
            "player1_id": p1["id"],
            "player1_name": f"{p1['cognome']} {p1['nome']}",
            "player2_id": p2["id"],
            "player2_name": f"{p2['cognome']} {p2['nome']}",
            "esito": None,
            "concluso": False
        })

    if bye_match:
        new_matches.append(bye_match)

    tournaments_col.update_one(
        {"_id": ObjectId(tournament_id)},
        {
            "$set": {"current_round": next_r, "status": "in_progress"},
            "$push": {"matches": {"$each": new_matches}}
        }
    )

    return jsonify({"message": f"Round {next_r} generato", "matches": new_matches}), 200

@app.route("/tournaments/<tournament_id>/match-result", methods=["POST"])
def set_result(tournament_id):
    from bson.objectid import ObjectId
    data = request.json
    p1_id = data.get("player1_id")
    p2_id = data.get("player2_id")
    rnd = data.get("round")
    esito = data.get("esito")

    if esito not in ["win_p1", "win_p2", "double_loss", "drop_p1", "drop_p2"]:
        return jsonify({"error": "Esito non valido"}), 400

    res = tournaments_col.update_one(
        {
            "_id": ObjectId(tournament_id),
            "matches": {
                "$elemMatch": {
                    "round": rnd,
                    "player1_id": p1_id,
                    "player2_id": p2_id
                }
            }
        },
        {
            "$set": {
                "matches.$.esito": esito,
                "matches.$.concluso": True
            }
        }
    )

    if res.matched_count == 0:
        return jsonify({"error": "Match non trovato"}), 404

    if esito == "drop_p1":
        requests.put(f"{PLAYER_SERVICE_URL}/players/{p1_id}/drop")
    elif esito == "drop_p2":
        requests.put(f"{PLAYER_SERVICE_URL}/players/{p2_id}/drop")

    return jsonify({"message": "Risultato salvato con successo"}), 200

@app.route("/tournaments/<tournament_id>/standings", methods=["GET"])
def get_standings(tournament_id):
    from bson.objectid import ObjectId
    t = tournaments_col.find_one({"_id": ObjectId(tournament_id)})
    if not t:
        return jsonify({"error": "Torneo non trovato"}), 404

    standings = compute_standings(t)
    return jsonify({
        "tournament_name": t.get("name"),
        "current_round": t.get("current_round"),
        "total_rounds": t.get("total_rounds"),
        "status": t.get("status"),
        "standings": standings
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
