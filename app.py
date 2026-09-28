import os
import math
import uuid
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
table = dynamodb.Table('Tournaments')

PLAYER_SERVICE_URL = os.getenv('PLAYER_SERVICE_URL', 'http://localhost:3001')

def get_players_from_service():
    try:
        res = requests.get(f"{PLAYER_SERVICE_URL}/players")
        if res.status_code == 200:
            # Filtriamo i giocatori ritirati
            return [p for p in res.json() if not p.get('ritirato')]
    except Exception as e:
        print("Errore connessione a Player Service:", e)
    return []

@app.route('/tournaments', methods=['POST'])
def create_tournament():
    data = request.json
    name = data.get('name', 'Nuovo Torneo')
    tournament_id = str(uuid.uuid4())[:8]
    
    players_data = get_players_from_service()
    if len(players_data) < 2:
        return jsonify({"error": "Servono almeno 2 giocatori per avviare un torneo"}), 400
        
    total_rounds = math.ceil(math.log2(len(players_data)))
    
    # Inizializza i giocatori per il torneo
    t_players = {}
    for p in players_data:
        t_players[str(p['id'])] = {
            "id": p['id'],
            "nome": p['nome'],
            "cognome": p['cognome'],
            "points": 0,
            "opponents": [],
            "lost_rounds": [],
            "ritirato": False,
            "matches_played": 0,
            "wins": 0
        }
        
    table.put_item(
        Item={
            'id': tournament_id,
            'name': name,
            'total_rounds': total_rounds,
            'current_round': 0,
            'players': t_players,
            'rounds': [],
            'status': 'ONGOING'
        }
    )
    return jsonify({"tournament_id": tournament_id, "total_rounds": total_rounds}), 201

@app.route('/tournaments/<t_id>/next-round', methods=['POST'])
def next_round(t_id):
    res = table.get_item(Key={'id': t_id})
    if 'Item' not in res:
        return jsonify({"error": "Torneo non trovato"}), 404
        
    t = res['Item']
    if t['current_round'] >= t['total_rounds']:
        return jsonify({"error": "Torneo già terminato"}), 400
        
    # Filtriamo i giocatori attivi
    active_players = [p for p in t['players'].values() if not p['ritirato']]
    # Ordiniamo per punti decrescenti
    active_players.sort(key=lambda x: x['points'], reverse=True)
    
    next_r_num = int(t['current_round']) + 1
    matches = []
    paired = set()
    
    # Abbinamento greedy
    for i, p1 in enumerate(active_players):
        if p1['id'] in paired: continue
        
        paired_opponent = None
        # Cerca il primo avversario valido (non affrontato)
        for j in range(i + 1, len(active_players)):
            p2 = active_players[j]
            if p2['id'] not in paired and p2['id'] not in p1['opponents']:
                paired_opponent = p2
                break
                
        if paired_opponent:
            matches.append({
                "round": next_r_num,
                "player1_id": p1['id'],
                "player2_id": paired_opponent['id'],
                "player1_name": f"{p1['cognome']} {p1['nome']}",
                "player2_name": f"{paired_opponent['cognome']} {paired_opponent['nome']}",
                "esito": None,
                "concluso": False
            })
            paired.add(p1['id'])
            paired.add(paired_opponent['id'])
        else:
            # Se rimane senza avversario (es. dispari o incroci esauriti), diamo il BYE (ID 0)
            matches.append({
                "round": next_r_num,
                "player1_id": p1['id'],
                "player2_id": 0,
                "player1_name": f"{p1['cognome']} {p1['nome']}",
                "player2_name": "BYE",
                "esito": "win_p1",
                "concluso": True
            })
            # Il BYE è vittoria automatica: 3 punti
            t['players'][str(p1['id'])]['points'] += 3
            t['players'][str(p1['id'])]['wins'] += 1
            t['players'][str(p1['id'])]['matches_played'] += 1
            paired.add(p1['id'])

    t['current_round'] = next_r_num
    t['rounds'].append(matches)
    
    table.put_item(Item=t)
    return jsonify({"matches": matches, "round": next_r_num})

@app.route('/tournaments/<t_id>/match-result', methods=['POST'])
def match_result(t_id):
    data = request.json
    r_num = int(data['round'])
    p1_id = str(data['player1_id'])
    p2_id = str(data['player2_id'])
    esito = data['esito']
    
    res = table.get_item(Key={'id': t_id})
    t = res['Item']
    
    p1 = t['players'][p1_id]
    p2 = t['players'][p2_id]
    
    p1['opponents'].append(int(p2_id))
    p2['opponents'].append(int(p1_id))
    p1['matches_played'] += 1
    p2['matches_played'] += 1
    
    if esito == 'win_p1':
        p1['points'] += 3
        p1['wins'] += 1
        p2['lost_rounds'].append(r_num)
    elif esito == 'win_p2':
        p2['points'] += 3
        p2['wins'] += 1
        p1['lost_rounds'].append(r_num)
    elif esito == 'double_loss':
        p1['lost_rounds'].append(r_num)
        p2['lost_rounds'].append(r_num)
    elif esito == 'drop_p1':
        p2['points'] += 3
        p2['wins'] += 1
        p1['ritirato'] = True
        p1['lost_rounds'].append(r_num)
    elif esito == 'drop_p2':
        p1['points'] += 3
        p1['wins'] += 1
        p2['ritirato'] = True
        p2['lost_rounds'].append(r_num)

    # Aggiorna il match nel round
    for m in t['rounds'][r_num - 1]:
        if str(m['player1_id']) == p1_id and str(m['player2_id']) == p2_id:
            m['esito'] = esito
            m['concluso'] = True
            break
            
    table.put_item(Item=t)
    return jsonify({"message": "Risultato salvato"})

@app.route('/tournaments/<t_id>/standings', methods=['GET'])
def get_standings(t_id):
    res = table.get_item(Key={'id': t_id})
    if 'Item' not in res:
        return jsonify({"error": "Torneo non trovato"}), 404
        
    t = res['Item']
    players = list(t['players'].values())
    
    # Funzione di supporto per calcolare Win % (minimo 33% da regole standard Svizzera, se richiesto, o puro)
    def calc_win_pct(p):
        if p['matches_played'] == 0: return 0.0
        return p['wins'] / p['matches_played']

    # 1. Calcolo OMW%
    for p in players:
        omw_sum = 0
        valid_opponents = 0
        for opp_id in p['opponents']:
            opp = t['players'].get(str(opp_id))
            if opp:
                omw_sum += calc_win_pct(opp)
                valid_opponents += 1
        p['omw'] = (omw_sum / valid_opponents) if valid_opponents > 0 else 0.0
        
    # 2. Calcolo O-OMW% e Somma Quadrati
    for p in players:
        oomw_sum = 0
        valid_opponents = 0
        for opp_id in p['opponents']:
            opp = t['players'].get(str(opp_id))
            if opp:
                oomw_sum += opp['omw']
                valid_opponents += 1
        p['oomw'] = (oomw_sum / valid_opponents) if valid_opponents > 0 else 0.0
        
        # Somma quadrata dei round persi
        p['lost_rounds_sq_sum'] = sum([r**2 for r in p['lost_rounds']])
        
    # Ordinamento: Punti, OMW%, O-OMW%, Somma quadrata (ascendente per penalità)
    players.sort(key=lambda x: (
        x['points'], 
        x['omw'], 
        x['oomw'], 
        -x['lost_rounds_sq_sum']
    ), reverse=True)
    
    return jsonify({"standings": players})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
