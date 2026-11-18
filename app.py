import os, math, statistics, json, time, threading
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
# CORS is required because Netlify hosts the frontend on a different domain.
ALLOWED_ORIGINS = [x.strip() for x in os.getenv('CORS_ORIGINS', '*').split(',') if x.strip()]
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    if '*' in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = '*'
    elif origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/api/<path:_path>', methods=['OPTIONS'])
def api_options(_path):
    return ('', 204)

API_KEY = os.getenv('API_FOOTBALL_KEY', '').strip()
API_HOST = 'https://v3.football.api-sports.io'
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_DAILY_USAGE_DATE = datetime.now(timezone.utc).date()
_DAILY_API_CALLS = 0
_DAILY_API_SOFT_LIMIT = int(os.getenv('API_DAILY_SOFT_LIMIT', '90'))

def cache_ttl(path):
    # Cache successful responses to preserve the 100-request daily free quota.
    if path == '/teams': return 24 * 60 * 60
    if path == '/fixtures': return 60 * 60
    if path == '/fixtures/statistics': return 24 * 60 * 60
    if path == '/injuries': return 30 * 60
    return 10 * 60

def api_get(path, params=None):
    global _DAILY_USAGE_DATE, _DAILY_API_CALLS
    if not API_KEY:
        raise RuntimeError('API_FOOTBALL_KEY غير مضبوط. أضف مفتاح API في ملف .env.')
    params = params or {}
    cache_key = path + '?' + json.dumps(params, sort_keys=True, ensure_ascii=False)
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and now - cached['time'] < cache_ttl(path):
            return cached['data']
    # Keep a safety margin below the provider's 100-call free quota.
    with _CACHE_LOCK:
        today = datetime.now(timezone.utc).date()
        if today != _DAILY_USAGE_DATE:
            _DAILY_USAGE_DATE = today
            _DAILY_API_CALLS = 0
        if _DAILY_API_CALLS >= _DAILY_API_SOFT_LIMIT:
            raise RuntimeError(f'وصل الموقع إلى حد الحماية اليومي ({_DAILY_API_SOFT_LIMIT} طلباً). حاول بعد إعادة ضبط حصة API-Football.')
        _DAILY_API_CALLS += 1
    try:
        r = requests.get(API_HOST + path, headers={'x-apisports-key': API_KEY}, params=params, timeout=25)
        if r.status_code == 429:
            raise RuntimeError('تم بلوغ حد الطلبات أو يوجد تقييد مؤقت من API-Football. تحقق من الحصة ثم حاول لاحقاً.')
        r.raise_for_status()
        payload = r.json()
    except requests.RequestException as exc:
        raise RuntimeError('تعذر الاتصال بـ API-Football: ' + str(exc)) from exc
    if payload.get('errors'):
        raise RuntimeError(str(payload['errors']))
    data = payload.get('response', [])
    with _CACHE_LOCK:
        _CACHE[cache_key] = {'time': now, 'data': data}
    return data


def safe_mean(values):
    return round(sum(values)/len(values), 2) if values else None


def team_recent(team_id, last=10, season=None):
    params = {'team': team_id, 'last': last}
    if season:
        params['season'] = season
    return api_get('/fixtures', params)


def stats_for_fixtures(fixtures):
    out = []
    for fx in fixtures:
        f = fx.get('fixture', {})
        teams = fx.get('teams', {})
        goals = fx.get('goals', {})
        score = fx.get('score', {}).get('halftime', {})
        full = fx.get('score', {}).get('fulltime', {})
        out.append({
            'fixture_id': f.get('id'), 'date': f.get('date'), 'timestamp': f.get('timestamp'),
            'home_id': teams.get('home', {}).get('id'), 'away_id': teams.get('away', {}).get('id'),
            'home_name': teams.get('home', {}).get('name'), 'away_name': teams.get('away', {}).get('name'),
            'home_goals': goals.get('home'), 'away_goals': goals.get('away'),
            'ht_home': score.get('home'), 'ht_away': score.get('away'),
            'ft_home': full.get('home'), 'ft_away': full.get('away'),
            'status': f.get('status', {}).get('short')
        })
    return out


def team_metrics(team_id, fixtures):
    played = [x for x in fixtures if x['status'] in ('FT','AET','PEN') and x['home_goals'] is not None and x['away_goals'] is not None]
    gf=[]; ga=[]; outcomes=[]; btts=[]; o15=[]; o25=[]; o35=[]; clean=[]; fts=[]; ht_g=[]; ht_con=[]; st_g=[]; st_con=[]; comebacks=[]; late_data=[]
    home=[]; away=[]
    for x in played:
        is_home = x['home_id'] == int(team_id)
        scored = x['home_goals'] if is_home else x['away_goals']
        conceded = x['away_goals'] if is_home else x['home_goals']
        gf.append(scored); ga.append(conceded)
        outcomes.append('W' if scored>conceded else 'D' if scored==conceded else 'L')
        btts.append(int(scored>0 and conceded>0)); total=scored+conceded
        o15.append(int(total>=2)); o25.append(int(total>=3)); o35.append(int(total>=4))
        clean.append(int(conceded==0)); fts.append(int(scored==0))
        if x['ht_home'] is not None and x['ht_away'] is not None:
            hts = x['ht_home'] if is_home else x['ht_away']; htc = x['ht_away'] if is_home else x['ht_home']
            ht_g.append(hts); ht_con.append(htc)
            st_g.append(max(0,scored-hts)); st_con.append(max(0,conceded-htc))
            if hts < htc and scored > conceded: comebacks.append(1)
            else: comebacks.append(0)
        if is_home: home.append((scored,conceded))
        else: away.append((scored,conceded))
    wins=outcomes.count('W'); draws=outcomes.count('D'); losses=outcomes.count('L')
    return {
        'played':len(played),'form':outcomes,'wins':wins,'draws':draws,'losses':losses,
        'gf':gf,'ga':ga,'avg_gf':safe_mean(gf),'avg_ga':safe_mean(ga),
        'btts_pct':round(100*sum(btts)/len(btts),1) if btts else None,
        'over15_pct':round(100*sum(o15)/len(o15),1) if o15 else None,
        'over25_pct':round(100*sum(o25)/len(o25),1) if o25 else None,
        'over35_pct':round(100*sum(o35)/len(o35),1) if o35 else None,
        'clean_pct':round(100*sum(clean)/len(clean),1) if clean else None,
        'fts_pct':round(100*sum(fts)/len(fts),1) if fts else None,
        'ht_avg_gf':safe_mean(ht_g),'ht_avg_ga':safe_mean(ht_con),
        'st_avg_gf':safe_mean(st_g),'st_avg_ga':safe_mean(st_con),
        'comebacks':sum(comebacks) if comebacks else None,
        'home_avg_gf':safe_mean([a for a,b in home]),'home_avg_ga':safe_mean([b for a,b in home]),
        'away_avg_gf':safe_mean([a for a,b in away]),'away_avg_ga':safe_mean([b for a,b in away]),
        'last_fixtures':played[:10]
    }


def poisson(lam, k):
    return math.exp(-lam) * (lam**k) / math.factorial(k)



def team_extras(team_id, fixtures, season=None):
    """Fetch a small sample of fixture stats and injury list; unavailable fields stay None."""
    corner_values=[]; yellow_values=[]; red_values=[]; xg_values=[]
    notes=[]
    for fx in [x for x in fixtures if x.get('fixture_id') and x.get('status') in ('FT','AET','PEN')][:5]:
        try:
            payload=api_get('/fixtures/statistics', {'fixture': fx['fixture_id']})
            for team_block in payload:
                if team_block.get('team',{}).get('id') != int(team_id):
                    continue
                vals={str(v.get('type','')).lower():v.get('value') for v in team_block.get('statistics',[])}
                def numeric(*keys):
                    for k in keys:
                        v=vals.get(k)
                        if v is not None:
                            try: return float(str(v).replace('%',''))
                            except (ValueError,TypeError): pass
                    return None
                c=numeric('corner kicks','corners')
                y=numeric('yellow cards')
                r=numeric('red cards')
                x=numeric('expected_goals','expected goals','xg')
                if c is not None: corner_values.append(c)
                if y is not None: yellow_values.append(y)
                if r is not None: red_values.append(r)
                if x is not None: xg_values.append(x)
        except Exception as e:
            notes.append('تعذر جلب بعض إحصائيات المباراة: '+str(e)[:120])
    injuries=[]
    try:
        params={'team':team_id}
        if season: params['season']=season
        injury_payload=api_get('/injuries', params)
        for item in injury_payload:
            player=item.get('player',{}) or {}
            injury=player.get('reason') or player.get('type') or 'حالة مسجلة'
            injuries.append({'player':player.get('name'),'reason':injury,'date':(item.get('fixture') or {}).get('date')})
    except Exception as e:
        notes.append('قائمة الإصابات غير متاحة من المزود: '+str(e)[:120])
    return {
        'avg_corners':safe_mean(corner_values), 'avg_yellow':safe_mean(yellow_values),
        'avg_red':safe_mean(red_values), 'avg_xg':safe_mean(xg_values),
        'injuries':injuries, 'extras_notes':notes,
        'stats_sample':max(len(corner_values),len(yellow_values),len(red_values),len(xg_values))
    }

def model_probs(a, b):
    if a['avg_gf'] is None or a['avg_ga'] is None or b['avg_gf'] is None or b['avg_ga'] is None or min(a['played'],b['played']) < 5:
        return None
    # Transparent simple goals-for/goals-against blend; not an xG model.
    home_lam = max(.15, (a['avg_gf'] + b['avg_ga'])/2 * 1.08)
    away_lam = max(.15, (b['avg_gf'] + a['avg_ga'])/2)
    ph=[poisson(home_lam,i) for i in range(9)]
    pa=[poisson(away_lam,i) for i in range(9)]
    win=draw=loss=over25=over35=btts=0
    for i,p1 in enumerate(ph):
        for j,p2 in enumerate(pa):
            p=p1*p2
            if i>j: win+=p
            elif i==j: draw+=p
            else: loss+=p
            if i+j>=3: over25+=p
            if i+j>=4: over35+=p
            if i>0 and j>0: btts+=p
    return {'home_lambda':round(home_lam,2),'away_lambda':round(away_lam,2),
            'home_win':round(win*100,1),'draw':round(draw*100,1),'away_win':round(loss*100,1),
            'over25':round(over25*100,1),'over35':round(over35*100,1),'btts':round(btts*100,1),
            'model':'Poisson مبسط من متوسط الأهداف المسجلة والمستقبلة؛ ليس xG ولا ضماناً.'}


@app.route('/')
def home():
    return render_template('index.html')

@app.get('/api/status')
def status():
    return jsonify({'api_configured': bool(API_KEY), 'provider':'API-Football / API-Sports', 'mode':'live' if API_KEY else 'manual', 'server_daily_calls': _DAILY_API_CALLS, 'server_daily_soft_limit': _DAILY_API_SOFT_LIMIT})

@app.get('/api/search-team')
def search_team():
    q=request.args.get('q','').strip()
    if len(q)<2: return jsonify({'results':[]})
    try:
        res=api_get('/teams', {'search':q})[:12]
        return jsonify({'results':[{'id':x['team']['id'],'name':x['team']['name'],'country':x.get('team',{}).get('country'),'logo':x.get('team',{}).get('logo')} for x in res]})
    except Exception as e:
        return jsonify({'error':str(e)}), 400

@app.get('/api/analyze')
def analyze():
    try:
        a_id=int(request.args['home_id']); b_id=int(request.args['away_id'])
        season=request.args.get('season')
        a_fx=stats_for_fixtures(team_recent(a_id,10,season))
        b_fx=stats_for_fixtures(team_recent(b_id,10,season))
        a=team_metrics(a_id,a_fx); b=team_metrics(b_id,b_fx)
        a.update(team_extras(a_id,a_fx,season)); b.update(team_extras(b_id,b_fx,season))
        model=model_probs(a,b)
        # Integrity: only flag missing/odd data quality; never accuse a club of match fixing.
        warnings=[]
        if min(a['played'],b['played'])<8: warnings.append('العينة أقل من 8 مباريات لأحد الفريقين؛ الثقة الإحصائية محدودة.')
        if not a['played'] or not b['played']: warnings.append('لا توجد نتائج مكتملة كافية.')
        return jsonify({'team_a':a,'team_b':b,'model':model,'warnings':warnings,
                        'data_note':'البيانات مصدرها API-Football عند تفعيل المفتاح. الإحصائيات غير المتاحة لا يتم تخمينها.',
                        'generated_at':datetime.now(timezone.utc).isoformat()})
    except KeyError:
        return jsonify({'error':'اختر الفريقين من نتائج البحث أولاً.'}),400
    except Exception as e:
        return jsonify({'error':str(e)}),400

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=False)
