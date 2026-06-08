import { LangfuseWeb } from "langfuse";

let langfuseWeb: LangfuseWeb | null = null;

export function submitFeedback(traceId: string, value: number) {
  if (!process.env.NEXT_PUBLIC_LANGFUSE_PUBLIC_KEY || !process.env.NEXT_PUBLIC_LANGFUSE_HOST) {
    console.warn("Langfuse public key or host not set. Skipping feedback submission.");
    return;
  }

  if (!langfuseWeb) {
    langfuseWeb = new LangfuseWeb({
      publicKey: process.env.NEXT_PUBLIC_LANGFUSE_PUBLIC_KEY,
      baseUrl: process.env.NEXT_PUBLIC_LANGFUSE_HOST,
    });
  }

  langfuseWeb.score({
    traceId,
    name: "user-feedback",
    value,
  });
}
