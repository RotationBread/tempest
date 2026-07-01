import requests, csv, io, math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ===================== HELPERS =====================
def safe_float(v, d=0.0):
    try: return d if v in [None,"","null","none"] else float(v)
    except: return d

def safe_int(v, d=0):
    try: return d if v in [None,"","null","none"] else int(float(v))
    except: return d

def r(v,d): return round(v,d) if v is not None else None
def ms_to_mph(ms): return ms*2.23694 if ms is not None else None
def c_to_f(c): return (c*9/5)+32 if c is not None else None
def mm_to_inches(mm): return mm/25.4 if mm is not None else None

def wet_bulb_temp(T,RH,P):
    if None in (T,RH,P): return None
    Pv=(RH/100)*6.112*math.exp((17.67*T)/(T+243.5)); Tw=T
    for _ in range(100):
        Pv_w=6.112*math.exp((17.67*Tw)/(Tw+243.5))
        diff=Pv-(Pv_w-P*(T-Tw)*0.00066*(1+0.00115*Tw))
        if abs(diff)<0.01: break
        Tw+=diff*0.1
    return Tw

# ===================== CONFIG =====================
DEVICE_ID=470036
API_KEY="4ca9b677-d072-439f-8920-22ea9c630dd8"
tz=ZoneInfo("America/New_York")

start_dt=datetime(2025,12,25,11,0,tzinfo=tz)
end_dt=datetime.now(tz)

TEMP_WINDOWS={"temp_delta_5min":5,"temp_delta_15min":15,"temp_delta_30min":30,"temp_delta_1hr":60,
              "temp_delta_3hr":180,"temp_delta_6hr":360,"temp_delta_12hr":720,
              "temp_delta_24hr":1440,"temp_delta_48hr":2880}

PRECIP_WINDOWS={"precip_1hr":60,"precip_3hr":180,"precip_6hr":360,
                "precip_12hr":720,"precip_24hr":1440}

# ===================== BUILD TIMELINE =====================
all_minutes={}
t=start_dt
while t<=end_dt:
    all_minutes[int(t.timestamp())]=None
    t+=timedelta(minutes=1)

# ===================== FETCH =====================
d=datetime(start_dt.year,start_dt.month,start_dt.day,tzinfo=tz)
days=[]
while d<=end_dt: days.append(d); d+=timedelta(days=1)

for i,day in enumerate(days):
    seg_start,max_end=max(day,start_dt),min(day+timedelta(days=1),end_dt)
    if seg_start>=max_end: continue

    url=f"https://swd.weatherflow.com/swd/rest/observations/device/{DEVICE_ID}" \
        f"?time_start={safe_int(seg_start.astimezone(timezone.utc).timestamp())}" \
        f"&time_end={safe_int(max_end.astimezone(timezone.utc).timestamp())}" \
        f"&format=csv&api_key={API_KEY}"

    for row in csv.DictReader(io.StringIO(requests.get(url).text)):
        ts=safe_int(row["timestamp"])
        if ts in all_minutes: row["timestamp"]=ts; all_minutes[ts]=row

    print(f"{i+1}/{len(days)} days fetched")

# ===================== FILL =====================
filled=[]; prev=None
for ts in sorted(all_minutes):
    obs=all_minutes[ts] or (prev.copy() if prev else {"timestamp":ts})
    obs["timestamp"]=ts
    for k in ["temperature","pressure","wind_avg","wind_dir","wind_gust","wind_lull",
              "humidity","solar_radiation","uv","lux","precip","strike_count"]:
        if obs.get(k) in [None,""]: obs[k]=prev.get(k,0) if prev else 0
    prev=obs; filled.append(obs)

# ===================== OUTPUT =====================
fields=[
"timestamp","air_temperature","barometric_pressure","station_pressure","pressure_trend",
"sea_level_pressure","relative_humidity","precip","precip_accum_local_day",
"precip_accum_local_day_final","precip_accum_local_yesterday_final",
"precip_minutes_local_day","precip_minutes_local_yesterday_final",
"wind_avg","wind_direction","wind_gust","wind_lull","solar_radiation","uv","brightness",
"lightning_strike_count","lightning_strike_count_last_1hr","lightning_strike_count_last_3hr",
"feels_like","heat_index","wind_chill","dew_point","wet_bulb_temperature",
"wet_bulb_globe_temperature","delta_t","air_density"] \
+ list(TEMP_WINDOWS)+list(PRECIP_WINDOWS)+["lightning_1day","precip_true","precip_true_24hr"]

with open("combine2.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()

    timestamps,temps,precips,lightnings,pt_list=[],[],[],[],[]
    temp_ptrs={k:0 for k in TEMP_WINDOWS}
    precip_ptrs={k:0 for k in PRECIP_WINDOWS}
    l_ptr=pt_ptr=0

    current_day=None; precip_minutes=0; precip_accum=0; prev_pm=None

    for obs in filled:
        ts=obs["timestamp"]; dt=datetime.fromtimestamp(ts,tz); date=dt.date()
        if date!=current_day: current_day=date; precip_minutes=precip_accum=0

        T_c=safe_float(obs["temperature"]); T_f=c_to_f(T_c)
        RH=safe_float(obs["humidity"]); P=safe_float(obs["pressure"])
        wind=ms_to_mph(safe_float(obs["wind_avg"]))
        precip=mm_to_inches(safe_float(obs["precip"]))
        strike=safe_int(obs["strike_count"])
        lux=safe_int(obs["lux"]); uv=safe_float(obs["uv"])
        solar=obs["solar_radiation"]

        if precip>0: precip_minutes+=1; precip_accum+=precip
        solar=float((lux/125)*0.7+(uv*25)) if solar=="null" else float(solar)

        wind_chill=T_f if not (T_f<50 and wind>3) else 35.74+0.6215*T_f-35.75*(wind**0.16)+0.4275*T_f*(wind**0.16)
        heat_index=T_f if not (T_f>=80 and RH>=40) else -42.379+2.049*T_f+10.143*RH
        feels=wind_chill if T_f<50 else heat_index if T_f>=80 else T_f

        alpha=math.log(RH/100)+(17.625*T_c)/(243.04+T_c)
        dew=c_to_f(243.04*alpha/(17.625-alpha))

        wb_c=wet_bulb_temp(T_c,RH,P); wb_f=c_to_f(wb_c)
        delta_t=T_f-wb_f; density=(P*100)/(287.058*(T_c+273.15))

        rec=dict(zip(fields[:31],[
            ts,r(T_f,3),r(P,2),r(P,2),None,r(P,2),r(RH,2),r(precip,6),
            r(precip_accum,4),r(precip_accum,4),0,precip_minutes,0,
            r(wind,3),safe_int(obs["wind_dir"]),
            r(ms_to_mph(safe_float(obs["wind_gust"])),3),
            r(ms_to_mph(safe_float(obs["wind_lull"])),3),
            r(solar,1),r(uv,3),lux,strike,0,0,
            r(feels,3),r(heat_index,3),r(wind_chill,3),
            r(dew,3),r(wb_f,3),r(c_to_f(wb_c),3),
            r(delta_t,3),r(density,5)
        ]))

        timestamps.append(ts); temps.append(T_f); precips.append(precip); lightnings.append(strike)

        precip_true=False if prev_pm is None else precip_minutes>prev_pm
        prev_pm=precip_minutes; pt_list.append(precip_true)
        rec["precip_true"]=precip_true

        for k,m in TEMP_WINDOWS.items():
            cutoff=ts-m*60; p=temp_ptrs[k]
            while p<len(timestamps) and timestamps[p]<cutoff: p+=1
            temp_ptrs[k]=p; rec[k]=T_f-temps[p] if p<len(temps) else 0

        for k,m in PRECIP_WINDOWS.items():
            cutoff=ts-m*60; p=precip_ptrs[k]
            while p<len(timestamps) and timestamps[p]<cutoff: p+=1
            precip_ptrs[k]=p; rec[k]=sum(precips[p:])

        while l_ptr<len(timestamps) and timestamps[l_ptr]<ts-86400: l_ptr+=1
        rec["lightning_1day"]=sum(lightnings[l_ptr:])

        while pt_ptr<len(timestamps) and timestamps[pt_ptr]<ts-86400: pt_ptr+=1
        rec["precip_true_24hr"]=sum(pt_list[pt_ptr:])

        w.writerow(rec)

print("Done -> combine2.csv")