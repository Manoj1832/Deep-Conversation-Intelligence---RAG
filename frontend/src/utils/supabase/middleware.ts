import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://jbhnfqyinngiiqbcpilt.supabase.co";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "sb_publishable_fdSRzsljqly4ZbCEVLqaNw_wPGIc2vK";

export const updateSession = async (request: NextRequest) => {
  let supabaseResponse = NextResponse.next({
    request: {
      headers: request.headers,
    },
  });

  const supabase = createServerClient(
    supabaseUrl,
    supabaseKey,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          supabaseResponse = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const { data: { user } } = await supabase.auth.getUser();

  // If unauthenticated and accessing dashboard, redirect to /login
  const isAuthRoute = request.nextUrl.pathname.startsWith("/login");
  const isDashboardRoute =
    request.nextUrl.pathname.startsWith("/chat") ||
    request.nextUrl.pathname.startsWith("/history") ||
    request.nextUrl.pathname.startsWith("/memories") ||
    request.nextUrl.pathname.startsWith("/personality") ||
    request.nextUrl.pathname.startsWith("/settings");

  // In development, if no active auth session is present, allow guest access or redirect
  // If user is logged in and visits /login, redirect to /chat
  if (user && isAuthRoute) {
    return NextResponse.redirect(new URL("/chat", request.url));
  }

  return supabaseResponse;
};
