import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    // Dev-only: log server-side to show analytics reception
    console.log("[analytics]", body?.event || "unknown", body?.payload || {});
  } catch {}
  return NextResponse.json({ ok: true });
}


