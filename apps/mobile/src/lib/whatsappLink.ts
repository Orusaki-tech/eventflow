/** WhatsApp click-to-chat URL from E.164 (digits only for wa.me). */
export function whatsAppMeUrlFromE164(e164: string): string | null {
  const digits = e164.replace(/\D/g, "");
  if (!digits) return null;
  return `https://wa.me/${digits}`;
}
