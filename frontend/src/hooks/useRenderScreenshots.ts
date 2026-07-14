import { useMemo } from "react";
import type { PipelineRecord } from "../types/pipeline";

function extractScreenshotPath(output: string): string | null {
  if (!output) return null;
  try {
    const data = JSON.parse(output);
    if (data.success && data.screenshot_path) {
      return data.screenshot_path as string;
    }
  } catch {
    // Not JSON, try regex fallback
    const match = output.match(/"screenshot_path"\s*:\s*"([^"]+)"/);
    if (match) {
      return match[1];
    }
  }
  return null;
}

export function useRenderScreenshots(record: PipelineRecord | null): string[] {
  return useMemo(() => {
    const paths: string[] = [];
    if (!record) return paths;

    if (record.events) {
      for (const event of record.events) {
        if (event.type === "item.completed") {
          const item = (event.item as Record<string, unknown>) || {};
          if (
            item.type === "command_execution" &&
            typeof item.command === "string" &&
            item.command.includes("render_shader.py") &&
            typeof item.aggregated_output === "string"
          ) {
            const path = extractScreenshotPath(item.aggregated_output);
            if (path) {
              paths.push(path);
            }
          }
        }
      }
    }

    // Fallback / final render based on workdir convention.
    if (record.workdir) {
      const finalPath = `${record.workdir}/render_final.png`;
      if (!paths.includes(finalPath)) {
        paths.push(finalPath);
      }
    }

    return paths;
  }, [record]);
}

export default useRenderScreenshots;
