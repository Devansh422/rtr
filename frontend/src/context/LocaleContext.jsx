import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { STRINGS, DEFAULT_LOCALE, LIVE_LOCALES } from "@/lib/strings";

/*
 * i18n scaffolding for EN/HI (§8 of IMPLEMENTATION_PLAN.md).
 *
 * Hand-rolled rather than i18next, deliberately, and it is worth being explicit
 * about why since the plan names i18next:
 *
 * - The plan pairs i18next with Next.js i18n ROUTING (`/hi/...`), which is what
 *   actually delivers the SEO benefit. This app is still CRA, so per-locale URLs
 *   are not available and i18next would add a dependency, a provider and a loader
 *   for something this 60-line context already does.
 * - What matters right now is the CONTRACT: components call `t("key")`, content
 *   comes back locale-aware from the API, and the language choice is persisted and
 *   applied to <html lang>. Swapping the implementation for i18next during the
 *   Next.js migration touches this file and not the components.
 *
 * Long-form content (constitution articles, courses, petitions) is NOT translated
 * here -- the API returns it per-locale with provenance, because §8's rule is that
 * a machine draft of constitutional text is never served as the text. This context
 * only handles interface strings.
 */

const LocaleContext = createContext(null);
const STORAGE_KEY = "rtr_locale";

export function LocaleProvider({ children }) {
  const [locale, setLocaleState] = useState(() => {
    const stored = typeof window !== "undefined" && localStorage.getItem(STORAGE_KEY);
    if (stored && LIVE_LOCALES.includes(stored)) return stored;
    // Respect the browser's preference on a first visit, but only for a language
    // the platform actually has strings for -- falling back to a half-translated
    // interface is worse than English.
    const browser = typeof navigator !== "undefined" ? navigator.language?.slice(0, 2) : null;
    return LIVE_LOCALES.includes(browser) ? browser : DEFAULT_LOCALE;
  });

  const setLocale = useCallback((next) => {
    if (!LIVE_LOCALES.includes(next)) return;
    setLocaleState(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, []);

  useEffect(() => {
    // Screen readers switch voice on this, and it drives CSS `:lang()` font
    // selection for Devanagari.
    document.documentElement.lang = locale;
  }, [locale]);

  /**
   * Look up an interface string.
   *
   * Falls back to English, then to the key itself. Returning the key rather than an
   * empty string is deliberate: a missing translation shows up as `forum.replyCta`
   * in the UI, which someone notices and fixes, where a blank space is invisible.
   */
  const t = useCallback(
    (key, vars) => {
      const template = STRINGS[locale]?.[key] ?? STRINGS[DEFAULT_LOCALE][key] ?? key;
      if (!vars) return template;
      return Object.entries(vars).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        template
      );
    },
    [locale]
  );

  const value = useMemo(() => ({ locale, setLocale, t, available: LIVE_LOCALES }), [locale, setLocale, t]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) {
    // A component rendering outside the provider would otherwise crash on
    // `context.t`, which is a confusing failure a long way from the cause.
    throw new Error("useLocale must be used inside a LocaleProvider");
  }
  return context;
}
