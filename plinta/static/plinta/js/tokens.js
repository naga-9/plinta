// Generated from design/tokens.json by build_tokens. Do not edit.

export const CHART_PALETTE = [
  "--pl-chart-1",
  "--pl-chart-2",
  "--pl-chart-3",
  "--pl-chart-4",
  "--pl-chart-5",
  "--pl-chart-6",
  "--pl-chart-7",
  "--pl-chart-8"
];

/** The computed value of a CSS custom property, e.g. read('--pl-accent'). */
export function read(name, element) {
    const target = element || document.documentElement;
    return getComputedStyle(target).getPropertyValue(name).trim();
}

/** The chart palette as concrete colours, in the theme showing now. */
export function palette() {
    return CHART_PALETTE.map((name) => read(name));
}
