// Shared storefront types and helpers. The product "photo" is a color swatch derived from the
// product's real color, so the store looks intentional without stock imagery.

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Product = {
  id: string;
  name: string;
  category: string;
  gender?: string;
  price: number | null;
  color: string | null;
  colors?: string[];
  weather?: string;
  sizes: string[];
  stock?: number;
};

export type ProductDetail = Product & { description: string; reviews: { text: string; rating: number | null }[] };

// What the shopper is currently viewing, so the assistant has page context.
export type PageContext =
  | { kind: "product"; id: string; name: string; category: string }
  | { kind: "category"; category: string; gender?: string }
  | { kind: "help"; topic: string }
  | null;

export async function fetchProduct(id: string): Promise<ProductDetail | null> {
  try {
    const res = await fetch(`${API_BASE}/api/product/${encodeURIComponent(id)}`);
    if (!res.ok) return null;
    return (await res.json()) as ProductDetail;
  } catch {
    return null;
  }
}

// English category → Chinese display label
const CATEGORY_LABELS: Record<string, string> = {
  shoes: "鞋履",
  tops: "上装",
  hoodies: "卫衣",
  leggings: "紧身裤",
  outerwear: "外套",
  jackets: "外套",
  bras: "运动内衣",
  bottoms: "下装",
  shorts: "短裤",
  bags: "包袋",
  accessories: "配饰",
  "sports bras": "运动内衣",
};

export function categoryLabel(category: string): string {
  if (!category) return "";
  return CATEGORY_LABELS[category.toLowerCase()] || category;
}

// Named colors from the catalog mapped to a base hex. Includes both English and Chinese color names.
const COLORS: Record<string, string> = {
  // English colors
  black: "#1d1d20",
  "storm blue": "#3d5a78",
  "heather grey": "#a1a5ac",
  "heather gray": "#a1a5ac",
  slate: "#5a6b7b",
  oatmeal: "#d7ccb8",
  charcoal: "#3a3f46",
  navy: "#2a3550",
  olive: "#5f6b4a",
  sand: "#cbb997",
  // Chinese colors
  "黑色": "#1d1d20",
  "白色": "#f0f0f0",
  "灰色": "#8b8f96",
  "粉色": "#e8a0b8",
  "深灰": "#3a3f46",
  "藏青": "#2a3550",
  "浅灰": "#a1a5ac",
  "黑红": "#8b1a1a",
  "黑白": "#2a2a2a",
  "小麦色": "#cbb997",
  "金色": "#c5a55a",
  "全黑": "#111111",
  "灰蓝": "#5a6b7b",
};

export function colorHex(color: string | null): string {
  if (!color) return "#8b8f96";
  const key = color.trim().toLowerCase();
  // Try lowercased match first (handles English); then try the original trimmed string (Chinese).
  return COLORS[key] || COLORS[color.trim()] || "#8b8f96";
}

// A soft top-lit gradient of the product color, so each tile reads as a premium swatch.
export function swatchStyle(color: string | null): React.CSSProperties {
  const base = colorHex(color);
  return { background: `radial-gradient(120% 120% at 30% 20%, ${base}dd, ${base})` };
}

export type Store = { brand: string; products: Product[] };

// The store names itself from the active domain pack, so nothing here hardcodes the brand.
export async function fetchStore(): Promise<Store> {
  try {
    const res = await fetch(`${API_BASE}/api/catalog`);
    if (!res.ok) return { brand: "", products: [] };
    const data = await res.json();
    return { brand: data.brand || "", products: (data.products || []) as Product[] };
  } catch {
    return { brand: "", products: [] };
  }
}
