import os
import time
import warnings
import numpy as np
import pandas as pd
import requests
from ast import literal_eval
from requests.adapters import HTTPAdapter
import shutil

warnings.filterwarnings("ignore")

session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=0))

DATA_ROOT = "data/b117"
TOTAL_CAPITAL = 1_000_000
FEE = 0.003
ATR_K = 3.0


# =========================================================
# 1) 업비트 OHLCV 수집
# =========================================================

def prepare_directory():
    """매 실행 시 기존 데이터를 완전히 삭제하고 새로 생성"""
    if os.path.exists(DATA_ROOT):
        shutil.rmtree(DATA_ROOT)
    os.makedirs(DATA_ROOT, exist_ok=True)


def fetch_chunk(ticker, to_date, count):
    url = "https://api.upbit.com/v1/candles/days"
    params = {
        "market": ticker,
        "to": to_date.strftime("%Y-%m-%d %H:%M:%S"),
        "count": count,
    }
    for _ in range(5):
        try:
            r = session.get(url, params=params, timeout=3)
            if r.status_code == 200:
                data = r.json()
                return None if not data else pd.DataFrame(data)
            if r.status_code == 429:
                time.sleep(1.2)
            elif r.status_code in (400, 404):
                return None
            else:
                time.sleep(0.5)
        except:
            time.sleep(0.5)
    return None


def get_ohlcv_long(ticker, to_date, total_count=700):
    dfs, remain, cur_to = [], total_count, to_date
    while remain > 0:
        cnt = min(remain, 200)
        df = fetch_chunk(ticker, cur_to, cnt)
        if df is None or df.empty:
            break
        df = df.rename(columns={
            "opening_price": "open",
            "high_price": "high",
            "low_price": "low",
            "trade_price": "close",
            "candle_acc_trade_price": "value",
            "candle_acc_trade_volume": "volume",
            "candle_date_time_kst": "date",
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        dfs.append(df)
        remain -= len(df)
        cur_to = df.index[0] - pd.Timedelta(days=1)
        time.sleep(0.05)
    if not dfs:
        return None
    full = pd.concat(dfs).sort_index()
    return full[~full.index.duplicated(keep="first")]


# =========================================================
# 2) 자동 화이트리스트 생성
# =========================================================

def build_auto_whitelist(target_count=50, min_days=200):
    print("📌 자동 화이트리스트 생성 시작...", end=" ")
    upbit = session.get("https://api.upbit.com/v1/market/all?isDetails=false").json()
    upbit_syms = {m["market"].replace("KRW-", "") for m in upbit if m["market"].startswith("KRW-")}

    tickers = session.get("https://api.binance.com/api/v3/ticker/24hr").json()
    usdt = sorted(
        [t for t in tickers if t["symbol"].endswith("USDT")],
        key=lambda x: float(x["quoteVolume"]),
        reverse=True
    )
    binance_syms = [t["symbol"].replace("USDT", "") for t in usdt]
    candidates = [s for s in binance_syms if s in upbit_syms]

    print(f"(교집합 {len(candidates)}개)")
    valid, bar_len = [], 10
    to_date = pd.Timestamp.today().replace(hour=9, minute=0, second=0)

    for i, sym in enumerate(candidates, start=1):
        df = get_ohlcv_long(f"KRW-{sym}", to_date, total_count=min_days)

        if df is not None and len(df) >= min_days:
            valid.append(sym)

        pct = i / len(candidates)
        bar = "#" * int(bar_len * pct) + "-" * (bar_len - int(bar_len * pct))
        print(f"\r📌 화이트리스트 검증 [{bar}] {pct*100:5.1f}% ({i}/{len(candidates)})", end="")

        if len(valid) >= target_count:
            full_bar = "#" * bar_len
            print(f"\r📌 화이트리스트 검증 [{full_bar}] 100.0% ({len(candidates)}/{len(candidates)}) → 완료: {len(valid)}개 확보")
            break

    print()
    return valid


# =========================================================
# 3) 데이터 수집
# =========================================================

def collect_b117_universe():
    os.makedirs(DATA_ROOT, exist_ok=True)

    markets = session.get("https://api.upbit.com/v1/market/all?isDetails=false").json()
    krw_markets = [m["market"] for m in markets if m["market"].startswith("KRW-")]

    wl = set(BINANCE_WHITELIST)

    targets = []
    for m in krw_markets:
        sym = m.replace("KRW-", "")
        if sym in wl or sym in ("BTC", "ETH"):
            targets.append((m, sym))

    print(f"📥 Step 1) 업비트 데이터 수집 ({len(targets)} symbols)")
    to_date = pd.Timestamp.today().replace(hour=9, minute=0, second=0)

    for i, (market, sym) in enumerate(targets, start=1):
        df = get_ohlcv_long(market, to_date, total_count=700)
        if df is not None and not df.empty:
            df.to_csv(os.path.join(DATA_ROOT, f"{sym}.csv"))

        pct = i / len(targets)
        bar = "#" * int(10 * pct) + "-" * (10 - int(10 * pct))
        print(f"\r📥 진행 [{bar}] {pct*100:5.1f}% ({i}/{len(targets)})  {sym:<12}", end="")

    print("\n→ 완료")


# =========================================================
# 4) RAW 로딩 + 기본 지표
# =========================================================

def load_raw_data():
    df_dict = {}
    for f in os.listdir(DATA_ROOT):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(DATA_ROOT, f), index_col=0, parse_dates=True).sort_index()
        df.columns = [c.lower() for c in df.columns]

        df["ma30"] = df["close"].rolling(30).mean()
        df["ma120"] = df["close"].rolling(120).mean()
        df["mom30"] = df["close"].pct_change(30)
        df["ma_short"] = df["close"].rolling(20).mean()
        df["ma_long"] = df["close"].rolling(120).mean()

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = (100 - (100 / (1 + rs))).fillna(50)

        high, low, close = df["high"], df["low"], df["close"]
        tr = np.maximum(
            high - low,
            np.maximum((high - close.shift()).abs(), (low - close.shift()).abs())
        )
        df["atr"] = tr.rolling(14).mean().bfill()

        df_dict[f.replace(".csv", "")] = df
    return df_dict


# =========================================================
# 5) ALT 스코어 (시장 국면별)
# =========================================================

def score_alt_by_regime(df, btc_df, regime):
    r90 = df["close"].pct_change(90).iloc[-1]
    if np.isnan(r90):
        r90 = -1

    ma10 = df["close"].rolling(10).mean().iloc[-1]
    ma30 = df["close"].rolling(30).mean().iloc[-1]
    if np.isnan(ma10) or np.isnan(ma30) or ma30 == 0:
        momentum = -1
    else:
        momentum = (ma10 / ma30) - 1

    vol_chg = df["volume"].pct_change(30).iloc[-1]
    if np.isnan(vol_chg):
        vol_chg = 0

    vol = df["close"].pct_change().rolling(30).std().iloc[-1]
    if np.isnan(vol) or vol == 0:
        vol_score = 0
    else:
        vol_score = 1 / vol

    corr = df["close"].pct_change().corr(btc_df["close"].pct_change())
    if np.isnan(corr):
        corr = 0

    if regime == "BULL":
        score = (
            0.45 * r90 +
            0.35 * momentum +
            0.15 * vol_chg +
            0.05 * corr
        )
    elif regime == "SIDE":
        score = (
            0.30 * r90 +
            0.30 * momentum +
            0.10 * vol_chg +
            0.30 * corr
        )
    else:
        return -999

    return float(score)


# =========================================================
# 6) ALT 바스켓 (시장 국면별)
# =========================================================

def build_alt_basket_auto_regime(df_dict, regime, top_n=7):
    btc = df_dict["BTC"]
    alts = [sym for sym in df_dict.keys() if sym not in ("BTC", "ETH")]

    if regime == "BEAR":
        return []

    scores = {}
    for sym in alts:
        df = df_dict[sym]
        if len(df) < 120:
            continue
        score = score_alt_by_regime(df, btc, regime)
        scores[sym] = score

    selected = sorted(scores, key=scores.get, reverse=True)[:top_n]
    return selected


def build_baskets(df_dict):
    btc_df = df_dict["BTC"]
    dates = btc_df.index
    rows = []

    for i, dt in enumerate(dates):
        btc_row = btc_df.loc[dt]
        regime = get_market_state(btc_row)

        if regime == "BEAR":
            sats = []
        else:
            sats = build_alt_basket_auto_regime(df_dict, regime, top_n=7)

        rows.append({
            "id": f"w{i+1:04d}",
            "start": dt,
            "sat": str(sats)
        })

    baskets = pd.DataFrame(rows)
    baskets["start"] = pd.to_datetime(baskets["start"])
    return baskets.sort_values("start").reset_index(drop=True)


# =========================================================
# 7) 인덱스 정렬
# =========================================================

def align_index(df_dict, start_dt=None, end_dt=None):
    idx = df_dict["BTC"].index
    if start_dt:
        idx = idx[idx >= pd.to_datetime(start_dt)]
    if end_dt:
        idx = idx[idx <= pd.to_datetime(end_dt)]
    return {k: v.reindex(idx).copy() for k, v in df_dict.items()}, idx


# =========================================================
# 8) 시장 국면 + 시뮬레이션 엔진
# =========================================================

def get_market_state(btc_row):
    price = btc_row["close"]
    ma_long = btc_row["ma_long"]
    rsi = btc_row["rsi"]

    if pd.isna(price) or pd.isna(ma_long) or pd.isna(rsi):
        return "NONE"

    if price < ma_long or rsi < 40:
        return "BEAR"
    if price > ma_long and rsi > 50:
        return "BULL"
    return "SIDE"


def get_dynamic_weights(state):
    if state == "BULL":
        return {"BTC": 0.4, "ETH": 0.5, "ALT": 0.1}
    if state == "SIDE":
        return {"BTC": 0.6, "ETH": 0.3, "ALT": 0.1}
    if state == "BEAR":
        return {"BTC": 0.0, "ETH": 0.0, "ALT": 0.0}
    return {"BTC": 0.0, "ETH": 0.0, "ALT": 0.0}


def run_simulation(df_dict, baskets, S, start_dt=None, end_dt=None, initial_weights=None):
    df_dict, idx = align_index(df_dict, start_dt, end_dt)
    if len(idx) < 2:
        return pd.DataFrame(), pd.DataFrame()

    tokens = list(df_dict.keys())
    btc_df = df_dict["BTC"]
    b_starts = pd.to_datetime(baskets["start"])

    rets_hist = pd.DataFrame(0.0, index=idx, columns=tokens)
    weights_hist = pd.DataFrame(0.0, index=idx, columns=tokens)

    prev_weights = {t: 0.0 for t in tokens} if initial_weights is None else initial_weights.copy()
    entry_price = {t: None for t in tokens}

    first_date = idx[0]
    weights_hist.loc[first_date] = prev_weights

    peak_value = 1.0

    THRESH = 0.05
    SLIPPAGE = {
        "BTC": 0.0003,
        "ETH": 0.0005,
    }
    DEFAULT_ALT_SLIPPAGE = 0.0015

    for i in range(1, len(idx)):
        date_prev = idx[i - 1]
        date_cur = idx[i]

        port_ret = 0.0
        for t in tokens:
            df = df_dict[t]
            if pd.isna(df.loc[date_prev, "close"]) or pd.isna(df.loc[date_cur, "close"]):
                continue
            r = (df.loc[date_cur, "close"] - df.loc[date_prev, "close"]) / df.loc[date_prev, "close"]
            port_ret += r * prev_weights[t]

        cur_value = (1 + port_ret)
        peak_value = max(peak_value, cur_value)
        dd = (cur_value - peak_value) / peak_value

        if dd < -0.10:
            prev_weights = {t: 0.0 for t in tokens}
            weights_hist.loc[date_cur] = prev_weights
            continue

        btc_row = btc_df.loc[date_cur]
        state = get_market_state(btc_row)
        base_w = get_dynamic_weights(state)

        if state == "BEAR":
            prev_weights = {t: 0.0 for t in tokens}
            weights_hist.loc[date_cur] = prev_weights
            continue

        b_idx = np.searchsorted(b_starts, date_cur, side="right") - 1
        sats = literal_eval(baskets.iloc[b_idx]["sat"]) if b_idx >= 0 else []

        target_weights = prev_weights.copy()

        for t in tokens:
            df = df_dict[t]
            row = df.loc[date_cur]

            if pd.isna(row["close"]) or pd.isna(row["ma_long"]) or pd.isna(row["ma_short"]) or pd.isna(row["rsi"]):
                continue

            price = float(row["close"])
            ma_long = float(row["ma_long"])
            ma_short = float(row["ma_short"])
            rsi = float(row["rsi"])
            atr = float(row["atr"])

            if t == "BTC":
                w = base_w["BTC"]
            elif t == "ETH":
                w = base_w["ETH"]
            else:
                w = base_w["ALT"] if t in sats else 0.0

            hist = df.loc[:date_cur].tail(30)["close"]
            bot = hist.min()
            rebound = (price - bot) / bot * 100 if bot > 0 else 0

            has_pos = prev_weights[t] > 0
            entry_cond = (price > ma_long and ma_short > ma_long and rsi >= S["RSI"] and rebound >= S["RB"])
            exit_A = price < ma_long * 0.99
            exit_C = rsi < 45
            exit_D = has_pos and entry_price[t] is not None and price < (entry_price[t] - ATR_K * atr)
            exit_cond = has_pos and (exit_A or exit_C or exit_D)

            if (not has_pos) and entry_cond and w > 0:
                target_weights[t] = w
                entry_price[t] = price
            elif has_pos and exit_cond:
                target_weights[t] = 0.0
                entry_price[t] = None
            else:
                if has_pos and w > 0:
                    target_weights[t] = w

        tw_sum = sum(target_weights.values())
        if tw_sum > 1.0:
            f = 1.0 / tw_sum
            for t in tokens:
                target_weights[t] *= f

        for t in tokens:
            old_w = prev_weights[t]
            new_w = target_weights[t]
            diff = abs(new_w - old_w)

            if diff < THRESH:
                target_weights[t] = old_w
                continue

            trade_size = diff

            if t in SLIPPAGE:
                slip_cost = SLIPPAGE[t]
            else:
                slip_cost = DEFAULT_ALT_SLIPPAGE

            total_cost = FEE + slip_cost
            rets_hist.loc[date_cur, t] -= trade_size * total_cost

        weights_hist.loc[date_cur] = target_weights
        prev_weights = target_weights.copy()

        for t in tokens:
            df = df_dict[t]
            if pd.isna(df.loc[date_prev, "close"]) or pd.isna(df.loc[date_cur, "close"]):
                continue
            r = (df.loc[date_cur, "close"] - df.loc[date_prev, "close"]) / df.loc[date_prev, "close"]
            rets_hist.loc[date_cur, t] += r * prev_weights[t]

    return rets_hist, weights_hist


# =========================================================
# 9) 파라미터 그리드
# =========================================================

PARAM_GRID = {
    "RB": [15, 18],
    "RSI": [55, 60],
    "W_ALT": [0.1],  # 의미상 유지 (현재 엔진에서는 동적 비중으로 처리)
}


def generate_param_space():
    params = []
    for rb in PARAM_GRID["RB"]:
        for rsi in PARAM_GRID["RSI"]:
            params.append({
                "RB": rb,
                "RSI": rsi,
            })
    return params


# =========================================================
# 10) 최적화 (WFA Train 구간)
# =========================================================

def print_opt_progress(i, total, best, start_time, bar_len=10):
    pct = i / total
    filled = int(bar_len * pct)
    bar = "#" * filled + "-" * (bar_len - filled)
    elapsed = time.time() - start_time
    eta = (elapsed / max(1, i)) * (total - i)
    print("\r" + " " * 120, end="")
    print(
        f"\r⚙️  Step 4-OPT [{bar}] {pct*100:5.1f}% ({i}/{total})  "
        f"ETA:{eta:6.1f}s  Best:{best:8.2f}",
        end=""
    )


def optimize_params(df_dict, baskets, train_start, train_end):
    best_score = -1e9
    best_S = None

    params_list = generate_param_space()
    total = len(params_list)
    start_time = time.time()

    for i, S_try in enumerate(params_list, start=1):
        print_opt_progress(i, total, best_score, start_time)

        rets, _ = run_simulation(df_dict, baskets, S_try, train_start, train_end)
        if rets.empty:
            continue

        total_ret = rets.sum(axis=1)
        eq = (1 + total_ret).cumprod()

        if len(eq) < 2:
            continue

        days = (eq.index[-1] - eq.index[0]).days
        if days <= 0:
            continue

        cagr = (eq.iloc[-1] ** (365.25 / days) - 1) * 100
        mdd = ((eq - eq.cummax()) / eq.cummax()).min() * 100

        score = cagr + mdd

        if score > best_score:
            best_score = score
            best_S = S_try

    print("\r" + " " * 120 + "\r", end="")
    print(f" score:{best_score:.1f} params:{best_S}")
    return best_S


# =========================================================
# 11) WFA 윈도우 생성
# =========================================================

def make_wfa_windows(idx, train_days=120, test_days=45, btc_df=None):
    idx = pd.to_datetime(idx)

    if btc_df is not None:
        valid = ~btc_df["ma_long"].isna()
        if valid.any():
            first_valid = btc_df.index[valid][0]
            idx = idx[idx >= first_valid]

    windows = []
    start = idx.min()
    end = idx.max()
    cur_train_start = start

    while True:
        train_end = cur_train_start + pd.Timedelta(days=train_days - 1)
        test_start = train_end + pd.Timedelta(days=1)
        test_end = test_start + pd.Timedelta(days=test_days - 1)

        if test_end > end:
            break

        windows.append((
            cur_train_start.strftime("%Y-%m-%d"),
            train_end.strftime("%Y-%m-%d"),
            test_start.strftime("%Y-%m-%d"),
            test_end.strftime("%Y-%m-%d"),
        ))

        cur_train_start += pd.Timedelta(days=test_days)

    return windows


# =========================================================
# 12) WFA 실행
# =========================================================

def walk_forward(df_dict, baskets, windows):
    oos_rets = []
    oos_weights = []
    prev_end_weights = None

    total_wfa = len(windows)

    for wi, (ts, te, vs, ve) in enumerate(windows, start=1):
        print(f"🚀 Step 4) WFA {wi}/{total_wfa} [TRN] {ts.replace('-', '.')}~{te.replace('-', '.')} [TST] {vs.replace('-', '.')}~{ve.replace('-', '.')}")
        best_S = optimize_params(df_dict, baskets, ts, te)

        r_df, w_df = run_simulation(
            df_dict,
            baskets,
            best_S,
            start_dt=vs,
            end_dt=ve,
            initial_weights=prev_end_weights,
        )

        if r_df.empty:
            continue

        prev_end_weights = w_df.iloc[-1].to_dict()
        oos_rets.append(r_df)
        oos_weights.append(w_df)

    if not oos_rets:
        return pd.DataFrame(), pd.DataFrame()

    return (
        pd.concat(oos_rets).sort_index(),
        pd.concat(oos_weights).sort_index()
    )


# =========================================================
# 13) 리포트
# =========================================================

def report(rets_df, weights_df):
    if rets_df.empty:
        print("No returns.")
        return

    total = rets_df.sum(axis=1)
    eq = TOTAL_CAPITAL * (1 + total).cumprod()

    days = (eq.index[-1] - eq.index[0]).days
    cagr = ((eq.iloc[-1] / TOTAL_CAPITAL) ** (365.25 / days) - 1) * 100
    mdd = ((eq - eq.cummax()) / eq.cummax()).min() * 100

    print("📊 Step 5) 최종 리포트")
    print(f"CAGR: {cagr:.2f}%   MDD: {mdd:.2f}%   Final: {int(eq.iloc[-1]):,}")

    y_ret = total.groupby(total.index.year).apply(lambda x: (1 + x).prod() - 1)
    print("연도별 수익률:")
    print((y_ret * 100).map(lambda x: f"{x:.2f}%"))


# =========================================================
# 15) 메인 실행
# =========================================================

if __name__ == "__main__":
    prepare_directory()

    BINANCE_WHITELIST = build_auto_whitelist()

    collect_b117_universe()

    print("📦 Step 2) RAW 데이터 로딩...", end="")
    dfs = load_raw_data()
    print(" 완료")

    print("🧺 Step 3) ALT 7 바스켓 생성...", end="")
    bks = build_baskets(dfs)
    print(" 완료")

    btc_idx = dfs["BTC"].index
    windows = make_wfa_windows(btc_idx, train_days=120, test_days=45, btc_df=dfs["BTC"])

    print("🚀 Step 4) WFA 시작")
    r_df, w_df = walk_forward(dfs, bks, windows)

    print("📊 Step 5) 전체 구간 리포트")
    report(r_df, w_df)
