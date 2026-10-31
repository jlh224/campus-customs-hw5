export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

const ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
  "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"];
const TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];

function underThousand(n: number): string {
  const parts: string[] = [];
  if (n >= 100) {
    parts.push(`${ONES[Math.floor(n / 100)]} Hundred`);
    n %= 100;
  }
  if (n >= 20) {
    parts.push(TENS[Math.floor(n / 10)] + (n % 10 ? `-${ONES[n % 10]}` : ""));
  } else if (n > 0) {
    parts.push(ONES[n]);
  }
  return parts.join(" ");
}

/** 2400 -> "Two Thousand Four Hundred and 00/100" (the way a check spells it). */
export function amountInWords(amount: number): string {
  const dollars = Math.floor(amount);
  const cents = Math.round((amount - dollars) * 100);
  const thousands = Math.floor(dollars / 1000);
  const rest = dollars % 1000;
  const words = [thousands ? `${underThousand(thousands)} Thousand` : "", underThousand(rest)]
    .filter(Boolean)
    .join(" ") || "Zero";
  return `${words} and ${String(cents).padStart(2, "0")}/100`;
}

export function shopDate(iso: string | undefined): { month: string; day: string; year: string; weekday: string } {
  if (!iso) return { month: "—", day: "—", year: "", weekday: "" };
  const d = new Date(`${iso}T12:00:00`);
  return {
    month: d.toLocaleString("en-US", { month: "short" }).toUpperCase(),
    day: String(d.getDate()),
    year: String(d.getFullYear()),
    weekday: d.toLocaleString("en-US", { weekday: "long" }),
  };
}
