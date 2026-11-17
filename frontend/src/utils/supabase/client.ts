import { createBrowserClient } from "@supabase/ssr";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://jbhnfqyinngiiqbcpilt.supabase.co";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "sb_publishable_fdSRzsljqly4ZbCEVLqaNw_wPGIc2vK";

export const createClient = () =>
  createBrowserClient(
    supabaseUrl,
    supabaseKey
  );
