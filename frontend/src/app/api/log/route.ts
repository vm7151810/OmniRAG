import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  if (process.env.DEBUG !== "true") {
    return NextResponse.json({ success: true, message: "Logging disabled" });
  }

  try {
    const body = await req.json();
    const { module, action, trace_id, data, timestamp } = body;

    const logEntry = {
      timestamp: timestamp || new Date().toISOString(),
      module: module || "unknown",
      action: action || "unknown",
      trace_id: trace_id || "unknown",
      data: data || {},
    };

    // Emit the single-line JSON log to the server console per Atomic Logging Standard
    console.log(JSON.stringify(logEntry));

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Log endpoint error:", error);
    return NextResponse.json(
      { success: false, error: "Failed to process log" },
      { status: 400 }
    );
  }
}
