import { Suspense } from "react";
import { connection } from "next/server";
import { session } from "@/lib/server/opsApi";
import OpsDashboard from "@/components/OpsDashboard";
import OpsLogin from "@/components/OpsLogin";
import "./ops.css";
export const metadata = {title:"咨询管理", robots:{index:false, follow:false}, referrer:"no-referrer"};
async function Operations() {
  // Runtime credentials arrive when the container starts, after the image is built.
  // Keep the request boundary outside try/catch so prerendering cannot freeze errors.
  await connection();
  let actor, unavailable = false;
  try {
    ({actor} = await session());
  } catch (error) {
    unavailable = error.message !== "OPS_UNAUTHORIZED";
  }
  return actor ? <OpsDashboard actor={actor} /> : <OpsLogin unavailable={unavailable} />;
}
export default function OpsPage() {
  return <main id="main" className="ops" lang="zh-CN"><Suspense fallback={<p role="status">正在检查登录状态…</p>}><Operations /></Suspense></main>;
}
