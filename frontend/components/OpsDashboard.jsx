"use client";
import { useEffect, useRef, useState } from "react";
const statuses = {new:"待跟进",following_up:"跟进中",proposal_sent:"已发方案",closed:"已关闭",confirmed:"需求已确认（历史）"};
const notificationStates = {pending:"等待发送",sending:"发送中",sent:"已送达飞书",failed:"发送失败，请联系维护者"};
const date = value => value ? new Date(value).toLocaleString("zh-CN") : "—";
const display = value => Array.isArray(value) ? value.join("、") : (value ?? "未填写");
function amount(quote) {
  if (!quote) return "未向旅客展示报价";
  const sales = quote.sales_quote || quote;
  return sales.amount != null ? `${sales.currency || "CNY"} ${Number(sales.amount).toFixed(2)}（团体估算）` : "需人工确认";
}
function QuoteScope({quote}) {
  const sales = quote?.sales_quote || quote;
  if (!sales) return <p>旅客未生成销售估算。</p>;
  return <div><p>{amount(quote)}</p>{sales.notice && <p>{sales.notice}</p>}
    {sales.selected_routes?.length > 0 && <><h4>所选路线</h4><ul>{sales.selected_routes.map(item=><li key={item}>{item}</li>)}</ul></>}
    {sales.included?.length > 0 && <><h4>包含服务</h4><ul>{sales.included.map(item=><li key={item}>{item}</li>)}</ul></>}
    {sales.excluded?.length > 0 && <><h4>不包含服务</h4><ul>{sales.excluded.map(item=><li key={item}>{item}</li>)}</ul></>}
  </div>;
}
const reviewReasons = {CUSTOM_JOURNEY_REQUIRES_REVIEW:"独立需求需人工拟定方案",JOURNEY_REQUIRES_REVIEW:"行程需要人工核对",ROUTE_SCOPE_REQUIRES_REVIEW:"路线与服务范围需要确认",NO_PRICED_SERVICES:"尚无可计价服务",VEHICLE_CAPACITY_REQUIRES_REVIEW:"用车容量需要确认",COST_DATA_REQUIRES_REVIEW:"服务费用需要复核",CONTENT_COST_MAPPING_REQUIRES_REVIEW:"产品项目与费用对应需要复核",GUIDE_COST_REQUIRES_REVIEW:"导游费用需要确认",VEHICLE_COST_REQUIRES_REVIEW:"用车费用需要确认"};
async function request(path, options) {
  const response = await fetch(path,{cache:"no-store",...options});
  if (response.status===401) { window.location.reload(); throw new Error("登录已过期，请重新登录。"); }
  if (!response.ok) {
    throw new Error(response.status===409 ? "这条咨询已被其他页面更新，请重新打开详情再修改。" : response.status===404 ? "未找到这条咨询。" : "暂时无法完成操作，请稍后重试。");
  }
  return response.json();
}
function Fields({values}) {
  return <dl className="ops-fields">{values.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{display(value)}</dd></div>)}</dl>;
}
export default function OpsDashboard({actor}) {
  const detailRequest = useRef(0);
  const [filter,setFilter]=useState(""), [page,setPage]=useState(1), [list,setList]=useState(null);
  const [reference,setReference]=useState(""), [detail,setDetail]=useState(null), [status,setStatus]=useState("new");
  const [error,setError]=useState(""), [busy,setBusy]=useState(false), [refresh,setRefresh]=useState(0), [notice,setNotice]=useState("");
  useEffect(()=>{
    const controller = new AbortController();
    const params = new URLSearchParams({page:String(page)}); if (filter) params.set("status",filter);
    request(`/api/ops/enquiries?${params}`,{signal:controller.signal}).then(setList).catch(e=>{if (e.name!=="AbortError") setError(e.message);});
    return ()=>controller.abort();
  },[filter,page,refresh]);
  useEffect(()=>{
    const initial = new URLSearchParams(window.location.search).get("reference");
    if (initial && /^TC-[A-F0-9]{16}$/.test(initial)) {
      let active=true;
      const generation=++detailRequest.current;
      request(`/api/ops/enquiries/${initial}`).then(data=>{if(active && generation===detailRequest.current){setReference(initial);setDetail(data);setStatus(data.status);}}).catch(e=>{if(active && generation===detailRequest.current)setError(e.message);});
      return ()=>{active=false;};
    }
  },[]);
  async function open(ref) {
    const generation=++detailRequest.current;
    setBusy(true);setError("");setNotice("");setDetail(null);
    try {const data=await request(`/api/ops/enquiries/${ref}`);if(generation===detailRequest.current){setReference(ref);setDetail(data);setStatus(data.status);}}
    catch(e){setError(e.message);} finally{setBusy(false);}
  }
  async function save(event) {
    event.preventDefault();setBusy(true);setError("");setNotice("");
    try {
      await request(`/api/ops/enquiries/${reference}/status`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({status,expected_version:detail.status_version})});
      setDetail(await request(`/api/ops/enquiries/${reference}`));setRefresh(value=>value+1);setNotice("跟进状态已保存。");
    } catch(e){setError(e.message);} finally{setBusy(false);}
  }
  async function logout(){setBusy(true);try{await request("/api/ops/logout",{method:"POST"});window.location.reload();}catch(e){setError(e.message);setBusy(false);}}
  const pref=detail?.preferences || {}, trip=detail?.preview_snapshot?.request || {}, preview=detail?.preview_snapshot?.preview;
  return <>
    <header className="ops-heading"><div><p className="ops-eyebrow">TRAVEL COPILOT · OPERATIONS</p><h1>旅客咨询</h1><p>查看需求并记录跟进。咨询与销售估算均不代表预订确认。</p></div><div><span>{actor}</span><button onClick={logout} disabled={busy}>退出登录</button></div></header>
    <p role="alert" className="ops-error">{error}</p><p role="status">{notice}</p>
    <div className="ops-workspace"><section aria-label="咨询列表" className="ops-panel">
      <div className="ops-toolbar"><label>跟进状态<select value={filter} onChange={e=>{setFilter(e.target.value);setPage(1);setList(null);setError("");}}><option value="">全部</option>{Object.entries(statuses).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><button onClick={()=>{setError("");setList(null);setRefresh(v=>v+1);}} disabled={busy}>刷新列表</button></div>
      {!list ? <p role="status">正在读取咨询…</p> : <><p>共 {list.total} 条 · 第 {page} 页</p><div className="ops-list">{list.items.length===0 ? <p>暂无符合条件的咨询。</p> : list.items.map(item=><button disabled={busy} className={`ops-row ${reference===item.reference ? "is-selected" : ""}`} key={item.reference} onClick={()=>open(item.reference)}><strong>{item.name} · {statuses[item.status]}</strong><span>{item.reference}</span><span>{item.enquiry_kind==="custom" ? "独立需求" : item.product_id} · {date(item.created_at)}</span>{(item.quote_changed || item.review_reason) && <span className="ops-flag">需人工复核{item.quote_changed ? " · 报价发生变化" : ""}</span>}</button>)}</div><div className="ops-pagination"><button disabled={page<=1 || busy} onClick={()=>{setList(null);setPage(v=>v-1);}}>上一页</button><button disabled={page*list.limit>=list.total || busy} onClick={()=>{setList(null);setPage(v=>v+1);}}>下一页</button></div></>}
    </section><section className="ops-panel ops-detail" aria-label="咨询详情" aria-busy={busy}>
      {!detail ? <p>{busy ? "正在读取详情…" : "选择一条咨询查看详情。"}</p> : <><h2>{detail.reference}</h2><Fields values={[["姓名",detail.name],["邮箱",detail.email],["收到时间",date(detail.created_at)],["咨询类型",detail.enquiry_kind==="custom" ? "独立需求" : "产品咨询"],["产品",preview?.product?.name || detail.product_id || "未指定"]]}/>
      <h3>旅客需求</h3><Fields values={[["目的地",pref.destinations || trip.city],["日期",pref.travel_dates || pref.dates || trip.travel_date],["天数",pref.duration || trip.days],["人数",pref.travellers || (trip.adults == null ? null : `${trip.adults} 成人、${trip.children} 儿童、${trip.seniors} 长者`)],["兴趣",pref.interests],["包车",trip.need_private_car == null ? null : trip.need_private_car ? "需要" : "不需要"],["导游",trip.need_guide == null ? null : trip.need_guide ? "需要" : "不需要"]]}/>
      <p className="ops-prose">{detail.message || "未填写留言"}</p>
      {trip.notes && <><h4>行程补充说明</h4><p className="ops-prose">{trip.notes}</p></>}
      <Fields values={[["所选体验",preview?.selected_experiences?.map(item=>item.name).join("、") || preview?.selected_optional_choices?.map(item=>item.name).join("、") || "未选择"],["路线选择",trip.route_choices?.map(route=>`第 ${route.day} 天：${preview?.product?.quote_route_options?.find(option=>option.day===route.day && option.choice===route.choice)?.label || "需人工确认"}`).join("；") || "无单独路线分支"]]}/>
      <h3>报价依据</h3><Fields values={[["旅客当时看到",amount(detail.shown_quote)],["提交时服务端复核",amount(detail.verified_quote)],["报价是否变化",detail.quote_changed ? "是，请联系旅客说明差异" : "否"],["待复核原因",detail.review_reason ? (reviewReasons[detail.review_reason] || "相关服务或范围需人工复核") : "无额外标记"]]}/><p>估算不含住宿，最终安排与成交金额须人工确认。</p>
      <details><summary>旅客当时看到的服务范围</summary><QuoteScope quote={detail.shown_quote}/></details><details><summary>提交时复核的服务范围</summary><QuoteScope quote={detail.verified_quote}/></details>
      <h3>跟进状态</h3><form className="ops-status" onSubmit={save}><label>状态<select value={status} onChange={e=>setStatus(e.target.value)}>{Object.entries(statuses).map(([value,label])=><option key={value} value={value} disabled={value==="confirmed"}>{label}</option>)}</select></label><button disabled={busy || status==="confirmed" || status===detail.status}>保存状态</button><button type="button" disabled={busy} onClick={()=>open(reference)}>刷新详情</button></form>
      <h3>跟进记录</h3>{detail.events.length===0 ? <p>尚无状态变更记录。</p> : <ul>{detail.events.map(event=><li key={event.status_version}>{date(event.created_at)} · {event.actor}：{statuses[event.old_status]} → {statuses[event.new_status]}</li>)}</ul>}
      <h3>飞书提醒</h3>{detail.notifications.length===0 ? <p>历史咨询无提醒任务，不会自动补发。</p> : detail.notifications.map((job,i)=><p key={i}>{notificationStates[job.state]} · 已尝试 {job.attempts} 次{job.sent_at ? ` · ${date(job.sent_at)}` : ""}</p>)}
      </>}
    </section></div>
  </>;
}
