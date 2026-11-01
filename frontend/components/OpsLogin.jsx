"use client";
import { useState } from "react";
export default function OpsLogin({unavailable}) {
  const [error,setError] = useState(""), [busy,setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/ops/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:form.get("username"),password:form.get("password")})});
      if (!response.ok) {
        setError(response.status===429 ? "尝试次数较多，请一分钟后重试。" : response.status===503 ? "运营登录尚未配置，请联系维护者。" : "账号或密码不正确，请重新输入。");
      } else { window.location.reload(); }
    } catch { setError("连接失败，请稍后重试。"); }
    finally { setBusy(false); }
  }
  return <section className="ops-login"><p className="ops-eyebrow">TRAVEL COPILOT · OPERATIONS</p><h1>咨询管理</h1><p>登录后查看旅客需求、报价依据和跟进记录。</p>
    {unavailable ? <p role="status">运营入口尚未配置。请按运营操作说明完成账号与服务端配置。</p> : <form onSubmit={submit}>
      <label>账号<input name="username" autoComplete="username" required maxLength={80}/></label>
      <label>密码<input name="password" type="password" autoComplete="current-password" required maxLength={256}/></label>
      <p role="alert">{error}</p><button disabled={busy}>{busy ? "正在登录…" : "登录"}</button>
    </form>}
  </section>;
}
