/**
 * White-label configuration. Changing the brand only requires environment
 * variables (and optionally replacing public/brand/logo.svg); no logic changes.
 */
export const brand = {
  name: process.env.NEXT_PUBLIC_BRAND_NAME ?? "Industrial Intelligence OS",
  shortName: process.env.NEXT_PUBLIC_BRAND_SHORT_NAME ?? "IIOS",
  tagline: process.env.NEXT_PUBLIC_BRAND_TAGLINE ?? "Inteligencia operativa para la industria",
  primaryColor: process.env.NEXT_PUBLIC_BRAND_PRIMARY_COLOR ?? "#0f766e",
};
