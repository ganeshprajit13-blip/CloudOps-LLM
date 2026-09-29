import { supportApi } from './supportApi';

export async function askGroqSupport(messagesHistory) {
  const lastUserMsg = messagesHistory.filter(m => m.role === 'user').slice(-1)[0]?.content || '';
  if (!lastUserMsg) return "Please enter a valid question.";

  try {
    const res = await supportApi.chat(lastUserMsg, messagesHistory);
    return res.reply || "An answer could not be generated.";
  } catch (err) {
    console.warn("Support API call failed, falling back to local guidance:", err);
    return "Service temporarily unavailable. Please try asking your question again on the main Support Agent page.";
  }
}
