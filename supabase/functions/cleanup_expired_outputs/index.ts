// Supabase Edge Function: cleanup_expired_files

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const BUCKET = "project_resources";

serve(async () => {
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!; // Supabse 프로젝트 설정에 inject된 환경변수 읽음
  const supabase = createClient(supabaseUrl, serviceRoleKey);

  const now = new Date().toISOString();

  // 1. output_contents (audio + script) 삭제
  const { data: expiredOutputs, error: outputsErr } = await supabase
    .from("output_contents")
    .select("id, audio_path, script_path, expires_at")
    .lt("expires_at", now);

  if (outputsErr) {
    console.error("output_contents select error:", outputsErr);
  } else if (expiredOutputs && expiredOutputs.length > 0) {
    console.log(`Found ${expiredOutputs.length} expired output_contents rows`);

    for (const row of expiredOutputs) {
      if (row.audio_path) {
        const { error } = await supabase.storage
          .from(BUCKET)
          .remove([row.audio_path]);
        if (error) console.error("Audio delete error:", error);
        else console.log(`Deleted audio file: ${row.audio_path}`);
      }

      if (row.script_path) {
        const { error } = await supabase.storage
          .from(BUCKET)
          .remove([row.script_path]);
        if (error) console.error("Script delete error:", error);
        else console.log(`Deleted script file: ${row.script_path}`);
      }

      const { error: deleteErr } = await supabase
        .from("output_contents")
        .delete()
        .eq("id", row.id);

      if (deleteErr) console.error("Row delete error:", deleteErr);
      else console.log(`Deleted output_contents row id: ${row.id}`);
    }
  }

  // 2. output_images (img_path) 삭제
  const { data: expiredImages, error: imagesErr } = await supabase
    .from("output_images")
    .select("id, img_path, expires_at")
    .lt("expires_at", now);

  if (imagesErr) {
    console.error("output_images select error:", imagesErr);
  } else if (expiredImages && expiredImages.length > 0) {
    console.log(`Found ${expiredImages.length} expired output_images rows`);

    for (const row of expiredImages) {
      if (row.img_path) {
        const { error } = await supabase.storage
          .from(BUCKET)
          .remove([row.img_path]);
        if (error) console.error("Image delete error:", error);
        else console.log(`Deleted image file: ${row.img_path}`);
      }

      const { error: deleteErr } = await supabase
        .from("output_images")
        .delete()
        .eq("id", row.id);

      if (deleteErr) console.error("Image row delete error:", deleteErr);
      else console.log(`Deleted output_images row id: ${row.id}`);
    }
  }

  // 3. input_contents (last_used_at + 180일 < now) 삭제

  // 180일 전 시간 계산
  const days180Ago = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString();

  const { data: expiredInputs, error: inputsErr } = await supabase
    .from("input_contents")
    .select("id, storage_path, last_used_at")
    .lt("last_used_at", days180Ago);

  if (inputsErr) {
    console.error("input_contents select error:", inputsErr);
  } else if (expiredInputs && expiredInputs.length > 0) {
    console.log(`Found ${expiredInputs.length} expired input_contents rows`);

    for (const row of expiredInputs) {
      // 파일 삭제
      if (row.storage_path) {
        const { error } = await supabase.storage
          .from(BUCKET)
          .remove([row.storage_path]);
        if (error) console.error("Input file delete error:", error);
        else console.log(`Deleted input file: ${row.storage_path}`);
      }

      // DB row 삭제
      const { error: delErr } = await supabase
        .from("input_contents")
        .delete()
        .eq("id", row.id);

      if (delErr) console.error("input_contents row delete error:", delErr);
      else console.log(`Deleted input_contents row id: ${row.id}`);
    }
  }

  return new Response("Cleanup completed");
});