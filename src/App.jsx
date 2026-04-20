import { useState, useEffect } from "react";

const INTOWN_NEIGHBORHOODS = [
  "Vineville","Ingleside","College Hill","Beall's Hill",
  "Huguenin Heights","Shirley Hills","Cherokee Heights","Rogers Avenue",
  "Historic Macon","Downtown Macon","Midtown Macon"
];

const FALLBACK_DATA = [
  {
    id:"MCA-2026-0412", address:"1247 Vineville Ave", neighborhood:"Vineville", intown:true,
    type:"Residential Addition", status:"Under Review", submitted:"2026-03-15", hearing:"2026-04-28T18:00:00",
    description:"Proposed 380 sq ft rear addition including master bedroom and full bath.",
    applicant:"Hendricks & Sons Construction", distance:0.4, lat:32.851, lng:-83.647,
    reactions:{support:10,oppose:6,neutral:5}, comments:[]
  },
  {
    id:"MCA-2026-0398", address:"576 College St", neighborhood:"College Hill", intown:true,
    type:"Historic Preservation", status:"Approved", submitted:"2026-02-28", hearing:null,
    description:"Renovation of historic storefront: facade restoration, updated electrical and plumbing.",
    applicant:"College Hill Alliance Partners", distance:0.8, lat:32.839, lng:-83.638,
    reactions:{support:41,oppose:1,neutral:8}, comments:[]
  },
  {
    id:"MCA-2026-0371", address:"988 Ingleside Ave", neighborhood:"Ingleside", intown:true,
    type:"Conditional Use", status:"Pending Hearing", submitted:"2026-02-10", hearing:"2026-05-03T19:00:00",
    description:"18-unit multifamily residential building on vacant lot.",
    applicant:"Greenfield Partners LLC", distance:1.1, lat:32.856, lng:-83.654,
    reactions:{support:14,oppose:38,neutral:19}, comments:[]
  },
  {
    id:"MCA-2026-0318", address:"2140 Napier Ave", neighborhood:"Beall's Hill", intown:true,
    type:"Demolition Permit", status:"Under Review", submitted:"2026-03-20", hearing:"2026-04-30T18:00:00",
    description:"Demolition of c.1910 contributing structure in Beall's Hill historic district.",
    applicant:"Napier Holdings LLC", distance:0.9, lat:32.843, lng:-83.644,
    reactions:{support:2,oppose:67,neutral:7}, comments:[]
  },
];

const STATUS_CONFIG = {
  "Under Review":          {color:"#F59E0B", bg:"rgba(245,158,11,0.12)",  dot:"#F59E0B"},
  "Approved":              {color:"#10B981", bg:"rgba(16,185,129,0.12)",  dot:"#10B981"},
  "Pending Hearing":       {color:"#6366F1", bg:"rgba(99,102,241,0.12)",  dot:"#6366F1"},
  "Denied":                {color:"#EF4444", bg:"rgba(239,68,68,0.12)",   dot:"#EF4444"},
  "Decision Issued":       {color:"#10B981", bg:"rgba(16,185,129,0.12)",  dot:"#10B981"},
  "Withdrawn":             {color:"#6B7280", bg:"rgba(107,114,128,0.12)", dot:"#6B7280"},
  "Continued":             {color:"#F59E0B", bg:"rgba(245,158,11,0.12)",  dot:"#F59E0B"},
  "Violation / Revocation":{color:"#EF4444", bg:"rgba(239,68,68,0.12)",   dot:"#EF4444"},
};

const TYPE_ICONS = {
  "Historic Preservation":"🏛️","Conditional Use":"📋","Rezoning":"🔀",
  "Variance Request":"📐","Special Exception":"⚡","Violation / Revocation":"⚠️",
  "Subdivision":"📏","Annexation":"🗺️","Text Amendment":"📝",
  "Planned Development":"🏗️","Residential Addition":"🏠",
  "Commercial Renovation":"🏢","New Construction":"🏗️",
  "Demolition Permit":"⚠️","Other":"📄",
};

function formatDate(s){
  if(!s)return "—";
  return new Date(s).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});
}
function formatHearing(s){
  if(!s)return null;
  const d=new Date(s);
  return {
    date:d.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"}),
    time:d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"}),
  };
}
function getStatusConfig(status){
  return STATUS_CONFIG[status] || {color:"#9CA3AF",bg:"rgba(156,163,175,0.12)",dot:"#9CA3AF"};
}

// ── SVG Map ───────────────────────────────────────────────────────────────────
function MapView({apps,onSelect,selectedId,intownOnly}){
  const [tooltip,setTooltip]=useState(null);
  const W=860,H=500;
  const LAT_MIN=32.82,LAT_MAX=32.87,LNG_MIN=-83.71,LNG_MAX=-83.61;
  function proj(lat,lng){
    return {x:((lng-LNG_MIN)/(LNG_MAX-LNG_MIN))*W, y:H-((lat-LAT_MIN)/(LAT_MAX-LAT_MIN))*H};
  }
  const home=proj(32.851,-83.647);
  const roads=[
    {pts:[[32.82,-83.650],[32.87,-83.648]],w:2.8,c:"#252A42",lbl:"I-75"},
    {pts:[[32.83,-83.71],[32.835,-83.61]],w:2.5,c:"#252A42",lbl:"I-16"},
    {pts:[[32.82,-83.633],[32.87,-83.631]],w:1.8,c:"#1E2235",lbl:"Forsyth St / US-41"},
    {pts:[[32.835,-83.630],[32.858,-83.653]],w:1.5,c:"#1E2235",lbl:"Vineville Ave"},
    {pts:[[32.825,-83.700],[32.840,-83.680],[32.850,-83.660]],w:1.4,c:"#1E2235",lbl:"Riverside Dr"},
    {pts:[[32.840,-83.625],[32.845,-83.660]],w:1.2,c:"#1E2235",lbl:"Napier Ave"},
    {pts:[[32.850,-83.640],[32.858,-83.665]],w:1.2,c:"#1E2235",lbl:"Ingleside Ave"},
    {pts:[[32.833,-83.625],[32.842,-83.648]],w:1.2,c:"#1E2235",lbl:"College St"},
    {pts:[[32.833,-83.615],[32.833,-83.640]],w:1.4,c:"#1E2235",lbl:"Cherry St"},
  ];
  const ocmulgee=[[32.820,-83.710],[32.828,-83.700],[32.835,-83.692],[32.842,-83.681],[32.852,-83.668],[32.860,-83.660],[32.870,-83.655]];
  const intownPoly=[[32.862,-83.638],[32.862,-83.625],[32.833,-83.622],[32.831,-83.635],[32.833,-83.648],[32.840,-83.665],[32.852,-83.668],[32.862,-83.655],[32.862,-83.638]];
  const neighborhoods=[
    {n:"Vineville",lat:32.853,lng:-83.648,it:true},{n:"Ingleside",lat:32.857,lng:-83.656,it:true},
    {n:"College Hill",lat:32.840,lng:-83.638,it:true},{n:"Beall's Hill",lat:32.844,lng:-83.645,it:true},
    {n:"Huguenin Hts",lat:32.846,lng:-83.661,it:true},{n:"Shirley Hills",lat:32.832,lng:-83.689,it:false},
    {n:"Downtown",lat:32.835,lng:-83.627,it:false},{n:"Midtown",lat:32.848,lng:-83.633,it:false},
    {n:"Cherokee Hts",lat:32.860,lng:-83.644,it:true},
  ];
  function polyPts(pts){return pts.map(([la,ln])=>{const p=proj(la,ln);return `${p.x},${p.y}`;}).join(" ");}
  return(
    <div>
      <div style={{display:"flex",alignItems:"center",gap:14,marginBottom:12,flexWrap:"wrap"}}>
        {Object.entries(STATUS_CONFIG).slice(0,4).map(([st,cfg])=>(
          <div key={st} style={{display:"flex",alignItems:"center",gap:5,fontSize:11,color:"#9CA3AF"}}>
            <div style={{width:9,height:9,borderRadius:"50%",background:cfg.dot}}/>{st}
          </div>
        ))}
        <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:5,fontSize:11,color:"#6B7280"}}>
          <div style={{width:9,height:9,borderRadius:"50%",background:"#4F6BFF",border:"2px solid #7E9AFF"}}/>Your Location
        </div>
      </div>
      <div style={{borderRadius:12,overflow:"hidden",border:"1px solid #1E2235",background:"#0D1018"}}>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{display:"block"}}>
          <rect width={W} height={H} fill="#0D1018"/>
          {Array.from({length:14}).map((_,i)=><line key={`gx${i}`} x1={i*(W/14)} y1={0} x2={i*(W/14)} y2={H} stroke="#12151E" strokeWidth={1}/>)}
          {Array.from({length:10}).map((_,i)=><line key={`gy${i}`} x1={0} y1={i*(H/10)} x2={W} y2={i*(H/10)} stroke="#12151E" strokeWidth={1}/>)}
          <polyline points={polyPts(ocmulgee)} fill="none" stroke="#1A3A5C" strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" opacity={0.7}/>
          <polyline points={polyPts(ocmulgee)} fill="none" stroke="#1E4A74" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" opacity={0.5}/>
          {(()=>{const p=proj(32.838,-83.693);return <text x={p.x-10} y={p.y} fill="#1E4A74" fontSize={9} fontWeight={700} fontFamily="DM Sans,sans-serif" transform={`rotate(-30,${p.x-10},${p.y})`}>OCMULGEE RIVER</text>;})()} 
          <polygon points={polyPts(intownPoly)} fill={intownOnly?"rgba(79,107,255,0.07)":"rgba(79,107,255,0.03)"} stroke="#4F6BFF" strokeWidth={intownOnly?1.5:0.8} strokeDasharray={intownOnly?"7 4":"4 4"} opacity={intownOnly?1:0.5}/>
          {(()=>{const p=proj(32.831,-83.649);return <><circle cx={p.x} cy={p.y} r={28} fill="rgba(16,185,129,0.06)" stroke="rgba(16,185,129,0.2)" strokeWidth={0.8}/><text x={p.x} y={p.y+3} fill="#164030" fontSize={8} textAnchor="middle" fontFamily="DM Sans,sans-serif" fontWeight={700}>MERCER</text></>;})()} 
          {(()=>{const p=proj(32.862,-83.669);return <><circle cx={p.x} cy={p.y} r={18} fill="rgba(16,185,129,0.05)" stroke="rgba(16,185,129,0.15)" strokeWidth={0.8}/><text x={p.x} y={p.y+3} fill="#164030" fontSize={7.5} textAnchor="middle" fontFamily="DM Sans,sans-serif" fontWeight={700}>WESLEYAN</text></>;})()} 
          {roads.map((r,i)=>{const pts=r.pts.map(([la,ln])=>{const p=proj(la,ln);return `${p.x},${p.y}`;}).join(" ");return <polyline key={i} points={pts} fill="none" stroke={r.c} strokeWidth={r.w} strokeLinecap="round" strokeLinejoin="round"/>;})}
          {roads.filter(r=>r.lbl).map((r,i)=>{const mid=r.pts[Math.floor(r.pts.length/2)];const p=proj(mid[0],mid[1]);return <text key={i} x={p.x} y={p.y-5} fill="#2A3050" fontSize={8} textAnchor="middle" fontFamily="DM Sans,sans-serif" fontWeight={600}>{r.lbl}</text>;})}
          {neighborhoods.map(n=>{const p=proj(n.lat,n.lng);return <text key={n.n} x={p.x} y={p.y} fill={n.it?"#272F5A":"#1A1F30"} fontSize={9} textAnchor="middle" fontFamily="DM Sans,sans-serif" fontWeight={700} letterSpacing={0.4}>{n.n.toUpperCase()}</text>;})}
          <circle cx={home.x} cy={home.y} r={40} fill="none" stroke="rgba(79,107,255,0.13)" strokeWidth={1} strokeDasharray="3 3"/>
          <circle cx={home.x} cy={home.y} r={78} fill="none" stroke="rgba(79,107,255,0.07)" strokeWidth={1} strokeDasharray="3 3"/>
          {apps.map(app=>{
            if(!app.lat||!app.lng)return null;
            const p=proj(app.lat,app.lng);
            const sc=getStatusConfig(app.status);
            const isHov=tooltip?.app?.id===app.id;
            const isSel=selectedId===app.id;
            const sz=isSel?14:isHov?12:10;
            return(
              <g key={app.id} style={{cursor:"pointer"}}
                onMouseEnter={()=>setTooltip({app,x:p.x,y:p.y})}
                onMouseLeave={()=>setTooltip(null)}
                onClick={()=>onSelect(app)}>
                {(isSel||isHov)&&<circle cx={p.x} cy={p.y} r={sz+7} fill={sc.bg} stroke={sc.dot} strokeWidth={1} opacity={0.7}/>}
                <circle cx={p.x} cy={p.y} r={sz} fill={isSel?sc.dot:"#161921"} stroke={sc.dot} strokeWidth={isSel?0:2}/>
                <text x={p.x} y={p.y+4.5} textAnchor="middle" fontSize={isSel?11:9} style={{userSelect:"none"}}>{TYPE_ICONS[app.type]||"📄"}</text>
              </g>
            );
          })}
          <circle cx={home.x} cy={home.y} r={9} fill="#4F6BFF" stroke="#7E9AFF" strokeWidth={2}/>
          <text x={home.x} y={home.y+4} textAnchor="middle" fontSize={9}>🏠</text>
          {tooltip&&(()=>{
            const {app,x,y}=tooltip;const sc=getStatusConfig(app.status);
            const tx=Math.min(x+14,W-198);const ty=Math.max(y-72,10);
            return(
              <g>
                <rect x={tx} y={ty} width={192} height={70} rx={8} fill="#161921" stroke="#2A2E42" strokeWidth={1}/>
                <text x={tx+10} y={ty+18} fill="#E8EAF0" fontSize={12} fontWeight={700} fontFamily="DM Sans">{app.address}</text>
                <text x={tx+10} y={ty+33} fill="#6B7280" fontSize={10} fontFamily="DM Sans">{app.neighborhood} · {app.type}</text>
                <circle cx={tx+11} cy={ty+51} r={4} fill={sc.dot}/>
                <text x={tx+20} y={ty+55} fill={sc.color} fontSize={10} fontWeight={600} fontFamily="DM Sans">{app.status}</text>
              </g>
            );
          })()}
        </svg>
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App(){
  const [apps,setApps]=useState([]);
  const [loading,setLoading]=useState(true);
  const [lastUpdated,setLastUpdated]=useState(null);
  const [selected,setSelected]=useState(null);
  const [view,setView]=useState("list");
  const [statusFilter,setStatusFilter]=useState("All");
  const [intownOnly,setIntownOnly]=useState(false);
  const [alertEmail,setAlertEmail]=useState("");
  const [alertRadius,setAlertRadius]=useState("0.5");
  const [alertSaved,setAlertSaved]=useState(false);
  const [commentText,setCommentText]=useState("");
  const [commentSentiment,setCommentSentiment]=useState("neutral");
  const [exportMsg,setExportMsg]=useState("");
  const [calMonth,setCalMonth]=useState(new Date());
  const [newReaction,setNewReaction]=useState({});
  const [mapSelectedId,setMapSelectedId]=useState(null);

  // Load data from scraper JSON, fall back to mock data
  useEffect(()=>{
    fetch("/permitwatch_data.json")
      .then(r=>{
        if(!r.ok)throw new Error("No data file");
        return r.json();
      })
      .then(data=>{
        const items=(data.items||[]).map(item=>({
          ...item,
          reactions: item.reactions||{support:0,oppose:0,neutral:0},
          comments:  item.comments||[],
          distance:  item.distance||null,
        }));
        setApps(items);
        setLastUpdated(data.scraped_at||data.generated_at||null);
        setLoading(false);
      })
      .catch(()=>{
        // Fall back to mock data if JSON not yet generated
        setApps(FALLBACK_DATA);
        setLoading(false);
      });
  },[]);

  const filteredApps=apps.filter(a=>{
    if(intownOnly&&!a.intown)return false;
    if(statusFilter!=="All"&&a.status!==statusFilter)return false;
    return true;
  });

  function openDetail(app){setSelected(app);setView("detail");setCommentText("");}

  function addComment(appId){
    if(!commentText.trim())return;
    const nc={id:Date.now(),author:"You",time:"just now",text:commentText,sentiment:commentSentiment};
    setApps(prev=>prev.map(a=>a.id===appId?{...a,comments:[...a.comments,nc]}:a));
    setSelected(prev=>({...prev,comments:[...prev.comments,nc]}));
    setCommentText("");
  }

  function addReaction(appId,type){
    if(newReaction[appId]===type)return;
    const pt=newReaction[appId];
    const upd=prev=>{const r={...prev.reactions};if(pt)r[pt]=Math.max(0,r[pt]-1);r[type]=r[type]+1;return r;};
    setApps(prev=>prev.map(a=>a.id!==appId?a:{...a,reactions:upd(a)}));
    setSelected(prev=>!prev||prev.id!==appId?prev:{...prev,reactions:upd(prev)});
    setNewReaction(r=>({...r,[appId]:type}));
  }

  function exportApp(app){
    const txt=`PERMIT APPLICATION\n${"=".repeat(40)}\nID: ${app.id}\nAddress: ${app.address}\nNeighborhood: ${app.neighborhood}\nType: ${app.type}\nStatus: ${app.status}\nApplicant: ${app.applicant||"—"}\nZoning: ${app.zoning||"—"}\n\nDescription:\n${app.description||"—"}\n\nReactions: ✅ ${app.reactions.support}  ❌ ${app.reactions.oppose}  ➖ ${app.reactions.neutral}\n\nSource: ${app.source_url||"mbpz.org"}\nExported from PermitWatch Macon · ${new Date().toLocaleDateString()}`;
    navigator.clipboard.writeText(txt).then(()=>{setExportMsg(app.id);setTimeout(()=>setExportMsg(""),2200);});
  }

  const calYear=calMonth.getFullYear(),calMN=calMonth.getMonth();
  const firstDay=new Date(calYear,calMN,1).getDay();
  const daysInMonth=new Date(calYear,calMN+1,0).getDate();
  const calDays=Array.from({length:firstDay+daysInMonth},(_,i)=>i<firstDay?null:i-firstDay+1);
  const hearingDates=filteredApps.filter(a=>a.hearing).map(a=>({...a,hp:new Date(a.hearing)}));
  const hByDay={};
  hearingDates.forEach(a=>{if(a.hp.getFullYear()===calYear&&a.hp.getMonth()===calMN){const d=a.hp.getDate();if(!hByDay[d])hByDay[d]=[];hByDay[d].push(a);}});

  const statuses=["All","Under Review","Pending Hearing","Approved","Denied","Withdrawn","Continued"];

  const IntownToggle=()=>(
    <button onClick={()=>setIntownOnly(v=>!v)} style={{display:"flex",alignItems:"center",gap:7,padding:"6px 13px",border:`1px solid ${intownOnly?"#4F6BFF":"#2A2E42"}`,borderRadius:20,background:intownOnly?"#4F6BFF18":"transparent",color:intownOnly?"#7E9AFF":"#6B7280",cursor:"pointer",fontFamily:"inherit",fontSize:12,fontWeight:600,transition:"all .15s",flexShrink:0,whiteSpace:"nowrap"}}>
      🏘 Intown Only {intownOnly&&<span style={{background:"#4F6BFF",color:"white",borderRadius:10,padding:"1px 7px",fontSize:10}}>ON</span>}
    </button>
  );

  const StatusPills=()=>(
    <>{statuses.map(s=>(
      <button key={s} onClick={()=>setStatusFilter(s)} style={{background:statusFilter===s?"#4F6BFF22":"transparent",border:`1px solid ${statusFilter===s?"#4F6BFF":"#2A2E42"}`,borderRadius:20,cursor:"pointer",fontFamily:"inherit",fontSize:12,fontWeight:500,color:statusFilter===s?"#7E9AFF":"#6B7280",padding:"5px 12px",transition:"all .15s",flexShrink:0,whiteSpace:"nowrap"}}>{s}</button>
    ))}</>
  );

  if(loading){
    return(
      <div style={{fontFamily:"'DM Sans',sans-serif",minHeight:"100vh",background:"#0F1117",display:"flex",alignItems:"center",justifyContent:"center",flexDirection:"column",gap:16}}>
        <div style={{fontSize:32,animation:"spin 1.5s linear infinite"}}>📋</div>
        <div style={{color:"#6B7280",fontSize:14}}>Loading permit data…</div>
        <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
      </div>
    );
  }

  return(
    <div style={{fontFamily:"'DM Sans','Helvetica Neue',sans-serif",minHeight:"100vh",background:"#0F1117",color:"#E8EAF0"}}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
        *{box-sizing:border-box;margin:0;padding:0;}
        ::-webkit-scrollbar{width:5px;}::-webkit-scrollbar-track{background:#1A1D27;}::-webkit-scrollbar-thumb{background:#2E3348;border-radius:10px;}
        .card{background:#161921;border:1px solid #1E2235;border-radius:12px;transition:all .2s;}
        .card:hover{border-color:#2E3560;transform:translateY(-1px);}
        .btn{border:none;cursor:pointer;font-family:inherit;font-size:13px;font-weight:500;border-radius:8px;padding:8px 16px;transition:all .15s;}
        .btn-primary{background:#4F6BFF;color:white;}.btn-primary:hover{background:#3D5BEF;}
        .btn-ghost{background:transparent;color:#9CA3AF;border:1px solid #2A2E42;}.btn-ghost:hover{background:#1E2235;color:#E8EAF0;}
        .nav-tab{background:transparent;border:none;cursor:pointer;font-family:inherit;font-size:13px;font-weight:500;color:#6B7280;padding:8px 14px;border-radius:8px;transition:all .15s;}
        .nav-tab.active{background:#1E2235;color:#E8EAF0;}.nav-tab:hover:not(.active){color:#9CA3AF;}
        .input{background:#1A1D27;border:1px solid #2A2E42;border-radius:8px;color:#E8EAF0;font-family:inherit;font-size:13px;padding:9px 12px;width:100%;outline:none;transition:border-color .15s;}
        .input:focus{border-color:#4F6BFF;}
        textarea.input{resize:vertical;min-height:80px;}
        .reaction-btn{background:transparent;border:1px solid #2A2E42;border-radius:8px;cursor:pointer;font-family:inherit;font-size:13px;padding:6px 14px;transition:all .15s;display:flex;align-items:center;gap:6px;}
        .reaction-btn:hover{background:#1E2235;}
        .rs{background:rgba(16,185,129,.12);border-color:#10B981;color:#10B981;}
        .ro{background:rgba(239,68,68,.12);border-color:#EF4444;color:#EF4444;}
        .rn{background:rgba(156,163,175,.12);border-color:#9CA3AF;color:#9CA3AF;}
        .calendar-day{border-radius:8px;min-height:60px;padding:6px;font-size:12px;border:1px solid transparent;}
        .calendar-day.hh{background:#1A1D27;border-color:#2A2E42;}
        .hpill{background:#4F6BFF22;border-radius:4px;color:#7E9AFF;font-size:10px;padding:2px 5px;margin-top:3px;cursor:pointer;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;}
        .hpill:hover{background:#4F6BFF44;}
        .back-btn{background:transparent;border:none;color:#6B7280;cursor:pointer;font-family:inherit;font-size:13px;display:flex;align-items:center;gap:6px;padding:0;transition:color .15s;}
        .back-btn:hover{color:#E8EAF0;}
        .sb{background:transparent;border:1px solid #2A2E42;border-radius:8px;cursor:pointer;font-family:inherit;font-size:12px;padding:5px 12px;transition:all .15s;color:#6B7280;}
        .sb.act{border-color:#4F6BFF;color:#7E9AFF;background:#4F6BFF15;}
        .tag{display:inline-flex;align-items:center;gap:6px;border-radius:20px;font-size:11px;font-weight:600;padding:4px 10px;letter-spacing:.3px;}
        .mlc{background:#161921;border:1px solid #1E2235;border-radius:10px;padding:12px 14px;cursor:pointer;transition:all .15s;}
        .mlc:hover{border-color:#2E3560;background:#1A1D27;}
        .mlc.sel{border-color:#4F6BFF;background:#4F6BFF0A;}
        .toast{position:fixed;bottom:24px;right:24px;background:#10B981;color:white;padding:10px 18px;border-radius:10px;font-size:13px;font-weight:500;z-index:100;animation:su .3s ease;}
        @keyframes su{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
        .asaved{background:#10B98120;border:1px solid #10B981;border-radius:10px;padding:10px 16px;color:#10B981;font-size:13px;font-weight:500;margin-top:12px;display:flex;align-items:center;gap:8px;}
        a{color:#7E9AFF;text-decoration:none;}.a:hover{text-decoration:underline;}
        @media(max-width:768px){
          .nav-tab{font-size:11px;padding:6px 8px;}
          .hide-mobile{display:none!important;}
          .stack-mobile{flex-direction:column!important;align-items:flex-start!important;}
          .full-mobile{width:100%!important;}
          .grid-mobile{grid-template-columns:1fr!important;}
        }
        @media(max-width:768px){
          .nav-tab{font-size:11px;padding:6px 8px;}
          .hide-mobile{display:none!important;}
          .stack-mobile{flex-direction:column!important;align-items:flex-start!important;}
          .full-mobile{width:100%!important;}
          .grid-mobile{grid-template-columns:1fr!important;}
        }
        @media(max-width:768px){
          .nav-tab{font-size:11px;padding:6px 8px;}
          .hide-mobile{display:none!important;}
          .stack-mobile{flex-direction:column!important;align-items:flex-start!important;}
          .full-mobile{width:100%!important;}
          .grid-mobile{grid-template-columns:1fr!important;}
        }
        @media(max-width:768px){
          .nav-tab{font-size:11px;padding:6px 8px;}
          .hide-mobile{display:none!important;}
          .stack-mobile{flex-direction:column!important;align-items:flex-start!important;}
          .full-mobile{width:100%!important;}
          .grid-mobile{grid-template-columns:1fr!important;}
        }
        @media(max-width:768px){
          .nav-tab{font-size:11px;padding:6px 8px;}
          .hide-mobile{display:none!important;}
          .stack-mobile{flex-direction:column!important;align-items:flex-start!important;}
          .full-mobile{width:100%!important;}
          .grid-mobile{grid-template-columns:1fr!important;}
        }
        @media(max-width:768px){
          .nav-tab{font-size:11px;padding:6px 8px;}
          .hide-mobile{display:none!important;}
          .stack-mobile{flex-direction:column!important;align-items:flex-start!important;}
          .full-mobile{width:100%!important;}
          .grid-mobile{grid-template-columns:1fr!important;}
        }
      `}</style>

      {/* Header */}
      <div style={{borderBottom:"1px solid #1E2235",padding:"0 24px"}}>
        <div style={{maxWidth:1020,margin:"0 auto",display:"flex",alignItems:"center",justifyContent:"space-between",height:56,flexWrap:"wrap",gap:8}}>
          <div style={{display:"flex",alignItems:"center",gap:10}}>
            <div style={{background:"#4F6BFF",borderRadius:8,width:28,height:28,display:"flex",alignItems:"center",justifyContent:"center",fontSize:14}}>📋</div>
            <div>
              <span style={{fontWeight:700,fontSize:15,letterSpacing:"-.3px"}}>PermitWatch</span>
              <span style={{color:"#3A4060",margin:"0 6px"}}>·</span>
              <span style={{color:"#6B7280",fontSize:12}}>Intown Macon Neighborhood Association</span>
            </div>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:4}}>
            {lastUpdated&&(
              <span style={{color:"#3A4060",fontSize:11,marginRight:8}}>
                Updated {new Date(lastUpdated).toLocaleDateString("en-US",{month:"short",day:"numeric"})}
              </span>
            )}
            {[{id:"list",lbl:"📋 Applications"},{id:"map",lbl:"🗺 Map"},{id:"calendar",lbl:"🗓 Hearings"},{id:"alerts",lbl:"🔔 Alerts"}].map(t=>(
              <button key={t.id} className={`nav-tab ${view===t.id||(view==="detail"&&t.id==="list")?"active":""}`}
                onClick={()=>{setView(t.id);if(t.id!=="detail")setSelected(null);}}>
                {t.lbl}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{maxWidth:1020,margin:"0 auto",padding:"24px"}}>

        {/* LIST */}
        {view==="list"&&(
          <div>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20,flexWrap:"wrap",gap:10}}>
              <div>
                <h1 style={{fontSize:22,fontWeight:700,letterSpacing:"-.5px"}}>Permit Applications</h1>
                <p style={{color:"#6B7280",fontSize:13,marginTop:3}}>{filteredApps.length} permit{filteredApps.length!==1?"s":""} · Macon-Bibb County{intownOnly?" · Intown only":""}</p>
              </div>
              <div style={{display:"flex",alignItems:"center",gap:8,overflowX:"auto",paddingBottom:4,WebkitOverflowScrolling:"touch",scrollbarWidth:"none"}}>
                <IntownToggle/><div style={{width:1,height:18,flexShrink:0,background:"#2A2E42"}}/><StatusPills/>
              </div>
            </div>
            <div style={{display:"flex",flexDirection:"column",gap:12}}>
              {filteredApps.map(app=>{
                const sc=getStatusConfig(app.status);
                const hearing=formatHearing(app.hearing);
                const tot=app.reactions.support+app.reactions.oppose+app.reactions.neutral;
                const spct=tot?Math.round((app.reactions.support/tot)*100):0;
                return(
                  <div key={app.id} className="card" style={{padding:"18px 20px",cursor:"pointer"}} onClick={()=>openDetail(app)}>
                    <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",gap:12}}>
                      <div style={{display:"flex",gap:14,flex:1}}>
                        <div style={{fontSize:24,marginTop:2}}>{TYPE_ICONS[app.type]||"📄"}</div>
                        <div style={{flex:1}}>
                          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4,flexWrap:"wrap"}}>
                            <span style={{fontWeight:600,fontSize:15}}>{app.address}</span>
                            <span style={{background:sc.bg,color:sc.color,whiteSpace:"nowrap"}} className="tag">
                              <span style={{width:5,height:5,borderRadius:"50%",background:sc.dot,display:"inline-block"}}></span>{app.status}
                            </span>
                            {app.intown&&<span style={{background:"#4F6BFF18",color:"#7E9AFF",borderRadius:20,padding:"3px 8px",fontSize:10,fontWeight:700}}>INTOWN</span>}
                          </div>
                          <div style={{color:"#9CA3AF",fontSize:13,marginBottom:8}}>
                            {[app.neighborhood && app.neighborhood!=="Macon" ? app.neighborhood : null,app.type,app.zoning,formatDate(app.submitted)].filter(Boolean).join(" · ")}
                          </div>
                          {app.description&&<p style={{color:"#6B7280",fontSize:13,lineHeight:1.5,marginBottom:10}}>{app.description}</p>}
                          <div style={{display:"flex",alignItems:"center",gap:14,flexWrap:"wrap"}}>
                            <div style={{display:"flex",alignItems:"center",gap:8}}>
                              <div style={{display:"flex",height:5,width:80,borderRadius:3,overflow:"hidden",background:"#1E2235"}}>
                                <div style={{width:`${spct}%`,background:"#10B981",transition:"width .3s"}}/>
                                <div style={{width:`${tot?Math.round((app.reactions.oppose/tot)*100):0}%`,background:"#EF4444"}}/>
                              </div>
                              <span style={{color:"#6B7280",fontSize:12}}>{app.reactions.support}✅ {app.reactions.oppose}❌</span>
                            </div>
                            <span style={{color:"#3A4060"}}>·</span>
                            <span style={{color:"#6B7280",fontSize:12}}>{app.comments.length} comment{app.comments.length!==1?"s":""}</span>
                            {hearing&&<><span style={{color:"#3A4060"}}>·</span><span style={{color:"#7E9AFF",fontSize:12}}>🗓 {hearing.date}</span></>}
                          </div>
                        </div>
                      </div>
                      <div style={{color:"#3A4060",fontSize:10,fontFamily:"DM Mono,monospace",whiteSpace:"nowrap"}}>{app.id}</div>
                    </div>
                  </div>
                );
              })}
              {filteredApps.length===0&&(
                <div style={{textAlign:"center",padding:"48px 24px",color:"#4A5068"}}>
                  <div style={{fontSize:32,marginBottom:12}}>🔍</div>
                  <div style={{fontWeight:600,marginBottom:6}}>No applications match your filters</div>
                  <div style={{fontSize:13}}>Try adjusting the status filter or disabling Intown Only</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* MAP */}
        {view==="map"&&(
          <div>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20,flexWrap:"wrap",gap:10}}>
              <div>
                <h1 style={{fontSize:22,fontWeight:700,letterSpacing:"-.5px"}}>Map View</h1>
                <p style={{color:"#6B7280",fontSize:13,marginTop:3}}>{filteredApps.length} permit{filteredApps.length!==1?"s":""} · Macon, GA{intownOnly?" · Intown only":""}</p>
              </div>
              <div style={{display:"flex",alignItems:"center",gap:8,overflowX:"auto",paddingBottom:4,WebkitOverflowScrolling:"touch",scrollbarWidth:"none"}}>
                <IntownToggle/><div style={{width:1,height:18,flexShrink:0,background:"#2A2E42"}}/><StatusPills/>
              </div>
            </div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 270px",gap:16,alignItems:"start"}} className="grid-mobile">
              <div>
                <MapView apps={filteredApps} onSelect={app=>setMapSelectedId(app.id===mapSelectedId?null:app.id)} selectedId={mapSelectedId} intownOnly={intownOnly}/>
                {mapSelectedId&&(
                  <div style={{marginTop:10,display:"flex",justifyContent:"center",gap:10}}>
                    <button className="btn btn-ghost" onClick={()=>setMapSelectedId(null)}>Deselect</button>
                    <button className="btn btn-primary" onClick={()=>{const a=apps.find(x=>x.id===mapSelectedId);if(a)openDetail(a);}}>View Full Details →</button>
                  </div>
                )}
              </div>
              <div className="hide-mobile" style={{display:"flex",flexDirection:"column",gap:8,maxHeight:550,overflowY:"auto"}}>
                <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:4,paddingLeft:2}}>{filteredApps.length} Permits</div>
                {filteredApps.map(app=>{
                  const sc=getStatusConfig(app.status);const isSel=mapSelectedId===app.id;
                  return(
                    <div key={app.id} className={`mlc ${isSel?"sel":""}`} onClick={()=>setMapSelectedId(app.id===mapSelectedId?null:app.id)}>
                      <div style={{display:"flex",alignItems:"flex-start",gap:8,marginBottom:6}}>
                        <span style={{fontSize:16,marginTop:1}}>{TYPE_ICONS[app.type]||"📄"}</span>
                        <div style={{flex:1}}>
                          <div style={{fontSize:13,fontWeight:600,lineHeight:1.3}}>{app.address}</div>
                          <div style={{fontSize:11,color:"#6B7280",marginTop:2}}>{app.neighborhood}</div>
                        </div>
                      </div>
                      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                        <span style={{background:sc.bg,color:sc.color,borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:600,display:"flex",alignItems:"center",gap:4}}>
                          <span style={{width:4,height:4,borderRadius:"50%",background:sc.dot,display:"inline-block"}}></span>{app.status}
                        </span>
                        {app.intown&&<span style={{background:"#4F6BFF18",color:"#7E9AFF",borderRadius:20,padding:"2px 7px",fontSize:10,fontWeight:700}}>INTOWN</span>}
                      </div>
                    </div>
                  );
                })}
                {filteredApps.length===0&&<div style={{color:"#4A5068",fontSize:13,textAlign:"center",padding:"20px 10px"}}>No permits match filters</div>}
              </div>
            </div>
          </div>
        )}

        {/* DETAIL */}
        {view==="detail"&&selected&&(()=>{
          const sc=getStatusConfig(selected.status);
          const hearing=formatHearing(selected.hearing);
          const myR=newReaction[selected.id];
          return(
            <div>
              <button className="back-btn" style={{marginBottom:20}} onClick={()=>{setView("list");setSelected(null);}}>← Back to Applications</button>
              <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:20,flexWrap:"wrap",gap:12}}>
                <div>
                  <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:6,flexWrap:"wrap"}}>
                    <span style={{fontSize:26}}>{TYPE_ICONS[selected.type]||"📄"}</span>
                    <h1 style={{fontSize:22,fontWeight:700,letterSpacing:"-.5px"}}>{selected.address}</h1>
                    <span style={{background:sc.bg,color:sc.color,whiteSpace:"nowrap"}} className="tag"><span style={{width:5,height:5,borderRadius:"50%",background:sc.dot,display:"inline-block"}}></span>{selected.status}</span>
                    {selected.intown&&<span style={{background:"#4F6BFF18",color:"#7E9AFF",borderRadius:20,padding:"3px 8px",fontSize:10,fontWeight:700}}>INTOWN</span>}
                  </div>
                  <div style={{color:"#6B7280",fontSize:13}}>{selected.neighborhood} · Macon-Bibb County · {selected.id}</div>
                </div>
                <button className="btn btn-ghost" onClick={()=>exportApp(selected)} style={{display:"flex",alignItems:"center",gap:6}}>📋 {exportMsg===selected.id?"Copied!":"Copy & Share"}</button>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:16}} className="grid-mobile">
                {[
                  {l:"Applicant",v:selected.applicant||"—"},
                  {l:"Zoning District",v:selected.zoning||"—"},
                  {l:"Hearing Date",v:hearing?`${hearing.date} at ${hearing.time}`:"Not scheduled"},
                  {l:"Submitted",v:formatDate(selected.submitted)},
                ].map(({l,v})=>(
                  <div key={l} className="card" style={{padding:"14px 16px"}}>
                    <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:5}}>{l}</div>
                    <div style={{fontSize:14,fontWeight:500}}>{v}</div>
                  </div>
                ))}
              </div>
              {selected.description&&(
                <div className="card" style={{padding:"16px 20px",marginBottom:16}}>
                  <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:8}}>Description</div>
                  <p style={{fontSize:14,lineHeight:1.6,color:"#C4C9DC"}}>{selected.description}</p>
                </div>
              )}
              {selected.hearing_url&&(
                <div style={{marginBottom:16}}>
                  <a href={selected.hearing_url} target="_blank" rel="noopener noreferrer" style={{color:"#7E9AFF",fontSize:13,display:"flex",alignItems:"center",gap:6}}>
                    🔗 View original MBPZ filing
                  </a>
                </div>
              )}
              <div className="card" style={{padding:"16px 20px",marginBottom:16}}>
                <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:12}}>Community Reaction</div>
                <div style={{display:"flex",gap:10,marginBottom:14,flexWrap:"wrap"}}>
                  {[{k:"support",l:"Support",ic:"✅",cl:"rs"},{k:"oppose",l:"Oppose",ic:"❌",cl:"ro"},{k:"neutral",l:"Neutral",ic:"➖",cl:"rn"}].map(({k,l,ic,cl})=>(
                    <button key={k} className={`reaction-btn ${myR===k?cl:""}`} onClick={()=>addReaction(selected.id,k)}>
                      {ic} <span>{selected.reactions[k]}</span> <span style={{color:"#6B7280"}}>{l}</span>
                    </button>
                  ))}
                </div>
                <div style={{display:"flex",height:8,borderRadius:4,overflow:"hidden",background:"#1E2235"}}>
                  {(()=>{const t=selected.reactions.support+selected.reactions.oppose+selected.reactions.neutral;return t?(<><div style={{width:`${(selected.reactions.support/t)*100}%`,background:"#10B981",transition:"width .3s"}}/><div style={{width:`${(selected.reactions.oppose/t)*100}%`,background:"#EF4444",transition:"width .3s"}}/><div style={{flex:1,background:"#2E3348"}}/></>):null;})()}
                </div>
                <div style={{color:"#6B7280",fontSize:12,marginTop:6}}>{selected.reactions.support+selected.reactions.oppose+selected.reactions.neutral} total votes</div>
              </div>
              <div className="card" style={{padding:"16px 20px"}}>
                <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:14}}>Neighborhood Comments ({selected.comments.length})</div>
                {selected.comments.length===0&&<p style={{color:"#4A5068",fontSize:13,marginBottom:14}}>No comments yet. Be the first to weigh in.</p>}
                {selected.comments.map(c=>(
                  <div key={c.id} style={{borderBottom:"1px solid #1E2235",paddingBottom:12,marginBottom:12}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:5,flexWrap:"wrap"}}>
                      <div style={{width:26,height:26,borderRadius:"50%",background:"#2A2E42",display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:600,color:"#9CA3AF"}}>{c.author[0]}</div>
                      <span style={{fontSize:13,fontWeight:600}}>{c.author}</span>
                      <span style={{color:"#4A5068",fontSize:12}}>· {c.time}</span>
                      {c.sentiment!=="neutral"&&<span style={{fontSize:10,fontWeight:600,padding:"2px 8px",borderRadius:20,background:c.sentiment==="support"?"#10B98120":"#EF444420",color:c.sentiment==="support"?"#10B981":"#EF4444"}}>{c.sentiment==="support"?"SUPPORTS":"OPPOSES"}</span>}
                    </div>
                    <p style={{color:"#9CA3AF",fontSize:13,lineHeight:1.5,paddingLeft:34}}>{c.text}</p>
                  </div>
                ))}
                <div style={{paddingTop:4}}>
                  <div style={{marginBottom:8}}><textarea className="input" placeholder="Share your thoughts with the neighborhood..." value={commentText} onChange={e=>setCommentText(e.target.value)}/></div>
                  <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}>
                    <div style={{display:"flex",gap:6}}>
                      {["support","neutral","oppose"].map(s=>(
                        <button key={s} className={`sb ${commentSentiment===s?"act":""}`} onClick={()=>setCommentSentiment(s)}>
                          {s==="support"?"✅":s==="oppose"?"❌":"➖"} {s}
                        </button>
                      ))}
                    </div>
                    <button className="btn btn-primary" onClick={()=>addComment(selected.id)}>Post Comment</button>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* CALENDAR */}
        {view==="calendar"&&(
          <div>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20,flexWrap:"wrap",gap:10}}>
              <div>
                <h1 style={{fontSize:22,fontWeight:700,letterSpacing:"-.5px"}}>Hearing Calendar</h1>
                <p style={{color:"#6B7280",fontSize:13,marginTop:3}}>{hearingDates.length} upcoming{intownOnly?" · Intown only":""}</p>
              </div>
              <div style={{display:"flex",alignItems:"center",gap:10,flexWrap:"wrap"}}>
                <IntownToggle/>
                <button className="btn btn-ghost" style={{padding:"6px 12px"}} onClick={()=>setCalMonth(new Date(calYear,calMN-1,1))}>‹</button>
                <span style={{fontWeight:600,fontSize:15,minWidth:130,textAlign:"center"}}>{calMonth.toLocaleDateString("en-US",{month:"long",year:"numeric"})}</span>
                <button className="btn btn-ghost" style={{padding:"6px 12px"}} onClick={()=>setCalMonth(new Date(calYear,calMN+1,1))}>›</button>
              </div>
            </div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(7,1fr)",gap:1,marginBottom:4}}>
              {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(d=>(
                <div key={d} style={{color:"#4A5068",fontSize:11,fontWeight:600,textAlign:"center",padding:"8px 0",textTransform:"uppercase",letterSpacing:".5px"}}>{d}</div>
              ))}
            </div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(7,1fr)",gap:4}}>
              {calDays.map((day,i)=>{
                const hs=day?(hByDay[day]||[]):[];
                return(
                  <div key={i} className={`calendar-day ${hs.length?"hh":""}`} style={{background:day?"#161921":"transparent",border:day&&!hs.length?"1px solid #1E2235":""}}>
                    {day&&(<><div style={{color:hs.length?"#E8EAF0":"#4A5068",fontSize:12,fontWeight:hs.length?600:400,marginBottom:4}}>{day}</div>
                      {hs.map(a=><div key={a.id} className="hpill" onClick={()=>openDetail(a)} title={a.address}>{a.address.split(" ").slice(0,2).join(" ")}</div>)}
                    </>)}
                  </div>
                );
              })}
            </div>
            <div style={{marginTop:24}}>
              <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:12}}>Upcoming Hearings</div>
              {hearingDates.sort((a,b)=>a.hp-b.hp).map(a=>{
                const sc=getStatusConfig(a.status);const h=formatHearing(a.hearing);
                return(
                  <div key={a.id} className="card" style={{padding:"14px 18px",marginBottom:8,display:"flex",alignItems:"center",gap:16,cursor:"pointer"}} onClick={()=>openDetail(a)}>
                    <div style={{background:"#4F6BFF22",borderRadius:8,padding:"10px 12px",textAlign:"center",minWidth:52}}>
                      <div style={{color:"#7E9AFF",fontSize:10,fontWeight:700,textTransform:"uppercase"}}>{h.date.split(",")[0]}</div>
                      <div style={{color:"#4F6BFF",fontSize:18,fontWeight:700,lineHeight:1.2}}>{a.hp.getDate()}</div>
                    </div>
                    <div style={{flex:1}}>
                      <div style={{fontWeight:600,fontSize:14,marginBottom:2}}>{a.address}</div>
                      <div style={{color:"#6B7280",fontSize:12}}>{a.neighborhood} · {a.type} · {h.time}</div>
                    </div>
                    <div style={{display:"flex",alignItems:"center",gap:8}}>
                      {a.intown&&<span style={{background:"#4F6BFF18",color:"#7E9AFF",borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:700}}>INTOWN</span>}
                      <span style={{background:sc.bg,color:sc.color,whiteSpace:"nowrap"}} className="tag"><span style={{width:5,height:5,borderRadius:"50%",background:sc.dot,display:"inline-block"}}></span>{a.status}</span>
                    </div>
                  </div>
                );
              })}
              {hearingDates.length===0&&<div style={{color:"#4A5068",fontSize:13,textAlign:"center",padding:"32px"}}>No upcoming hearings match your filters</div>}
            </div>
          </div>
        )}

        {/* ALERTS */}
        {view==="alerts"&&(
          <div style={{maxWidth:560}}>
            <div style={{marginBottom:24}}>
              <h1 style={{fontSize:22,fontWeight:700,letterSpacing:"-.5px",marginBottom:6}}>Alert Preferences</h1>
              <p style={{color:"#6B7280",fontSize:13}}>Get notified when new permit applications are filed in Macon.</p>
            </div>
            <div className="card" style={{padding:"20px",marginBottom:16}}>
              <div style={{fontWeight:600,fontSize:14,marginBottom:14}}>📍 Your Address</div>
              <input className="input" placeholder="Enter your address in Macon, GA..." defaultValue="" style={{marginBottom:12}}/>
              <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:8}}>Alert Radius</div>
              <div style={{display:"flex",gap:8,marginBottom:14}}>
                {["0.25","0.5","1.0","2.0"].map(r=>(
                  <button key={r} onClick={()=>setAlertRadius(r)} style={{background:alertRadius===r?"#4F6BFF22":"transparent",border:`1px solid ${alertRadius===r?"#4F6BFF":"#2A2E42"}`,borderRadius:20,cursor:"pointer",fontFamily:"inherit",fontSize:12,fontWeight:500,color:alertRadius===r?"#7E9AFF":"#6B7280",padding:"5px 12px",transition:"all .15s"}}>{r} mi</button>
                ))}
              </div>
              <div style={{color:"#6B7280",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:".8px",marginBottom:8}}>Neighborhood Scope</div>
              <div style={{display:"flex",gap:8}}>
                {["All Macon","Intown Macon Only"].map(opt=>{
                  const active=(opt==="Intown Macon Only")===intownOnly;
                  return <button key={opt} onClick={()=>setIntownOnly(opt==="Intown Macon Only")} style={{background:active?"#4F6BFF22":"transparent",border:`1px solid ${active?"#4F6BFF":"#2A2E42"}`,borderRadius:20,cursor:"pointer",fontFamily:"inherit",fontSize:12,fontWeight:500,color:active?"#7E9AFF":"#6B7280",padding:"5px 14px",transition:"all .15s"}}>{opt}</button>;
                })}
              </div>
            </div>
            <div className="card" style={{padding:"20px",marginBottom:16}}>
              <div style={{fontWeight:600,fontSize:14,marginBottom:14}}>📧 Email Alerts</div>
              <input className="input" type="email" placeholder="your@email.com" value={alertEmail} onChange={e=>setAlertEmail(e.target.value)} style={{marginBottom:12}}/>
              {[
                {l:"New applications filed within my radius",c:true},
                {l:"Status changes on nearby permits",c:true},
                {l:"Upcoming hearing dates (48hr reminder)",c:true},
                {l:"Demolition permit applications (immediate)",c:true},
                {l:"New comments on applications I follow",c:false},
              ].map(({l,c})=>(
                <label key={l} style={{display:"flex",alignItems:"center",gap:10,cursor:"pointer",marginBottom:10}}>
                  <input type="checkbox" defaultChecked={c} style={{accentColor:"#4F6BFF",width:15,height:15}}/>
                  <span style={{fontSize:13,color:"#C4C9DC"}}>{l}</span>
                </label>
              ))}
            </div>
            <div className="card" style={{padding:"20px",marginBottom:16}}>
              <div style={{fontWeight:600,fontSize:14,marginBottom:14}}>📱 Text Alerts</div>
              <input className="input" type="tel" placeholder="+1 (478) 000-0000" style={{marginBottom:10}}/>
              <p style={{color:"#4A5068",fontSize:12}}>SMS for urgent filings: demolitions, new construction, and variances in Intown Macon.</p>
            </div>
            <button className="btn btn-primary" style={{width:"100%",padding:"11px",fontSize:14}} onClick={()=>{setAlertSaved(true);setTimeout(()=>setAlertSaved(false),3000);}}>
              Save Alert Preferences
            </button>
            {alertSaved&&<div className="asaved">✅ Alerts active for {intownOnly?"Intown Macon":"all of Macon"} within {alertRadius} miles</div>}
          </div>
        )}

      </div>
      {exportMsg&&<div className="toast">✅ Application details copied to clipboard</div>}
    </div>
  );
}
