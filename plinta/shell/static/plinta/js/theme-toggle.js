// Switching between light and dark, and remembering the choice.
//
// The stylesheet already follows the operating system; this exists so a
// viewer can disagree with it. A choice is stored as `light` or `dark` and
// stamped on the root element, where the last block of tokens.css wins.

const KEY = 'plinta-theme';
const ROOT = document.documentElement;

/** The stored choice, or null when the viewer has not made one. */
export function stored() {
    try {
        const value = localStorage.getItem(KEY);
        return value === 'light' || value === 'dark' ? value : null;
    } catch {
        // Private browsing, or site data blocked. No stored choice, so the
        // operating system decides — which is the default anyway.
        return null;
    }
}

/** Which theme is showing now, whether chosen or inherited. */
export function current() {
    return (
        ROOT.getAttribute('data-theme') ||
        (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    );
}

/** Show `theme`, and remember it. */
export function apply(theme) {
    ROOT.setAttribute('data-theme', theme);
    try {
        localStorage.setItem(KEY, theme);
    } catch {
        // The page still switches; only the memory of it is lost.
    }
    ROOT.dispatchEvent(new CustomEvent('plinta:theme', { detail: { theme } }));
}

/** Swap to the other one. */
export function toggle() {
    apply(current() === 'dark' ? 'light' : 'dark');
}

/** Re-apply a stored choice, and wire every [data-plinta-theme-toggle]. */
export function init() {
    const choice = stored();
    if (choice) {
        ROOT.setAttribute('data-theme', choice);
    }
    for (const el of document.querySelectorAll('[data-plinta-theme-toggle]')) {
        el.addEventListener('click', toggle);
    }
}

init();
