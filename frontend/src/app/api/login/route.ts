import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const { password } = await request.json().catch(() => ({}));
  const expected = process.env.FRONTEND_PASSWORD ?? "admin";

  if (password === expected) {
    const response = NextResponse.json({ success: true });
    response.cookies.set("dus_session", "authenticated", {
      httpOnly: true,
      maxAge: 60 * 60 * 24 * 7,
      path: "/",
    });
    return response;
  }

  return NextResponse.json({ success: false }, { status: 401 });
}
