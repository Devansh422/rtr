import { useEffect, useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getLocales } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { Check, Languages } from "lucide-react";

/*
 * Language switcher.
 *
 * Lists the languages the platform PLANS to support as well as the ones it has,
 * greyed out. §8 sequences 22 scheduled languages over several phases, and "Tamil is
 * coming, help translate it" recruits translators where an absent entry recruits
 * nobody. The catalogue comes from the API so the frontend cannot claim a language
 * the backend does not actually serve content in.
 */
export default function LanguageSwitcher({ compact = false }) {
  const { locale, setLocale } = useLocale();
  const [catalogue, setCatalogue] = useState([]);

  useEffect(() => {
    getLocales().then((data) => setCatalogue(data?.locales ?? []));
  }, []);

  const current = catalogue.find((entry) => entry.code === locale);
  const available = catalogue.filter((entry) => entry.available);
  const planned = catalogue.filter((entry) => !entry.available);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-8 items-center gap-1.5 rounded border border-border px-2 text-[0.8rem] font-medium text-foreground/70 transition-colors hover:bg-muted"
          aria-label="Change language"
          data-testid="language-switcher"
        >
          <Languages className="h-4 w-4" aria-hidden="true" />
          {compact ? null : <span lang={locale}>{current?.nativeName ?? locale.toUpperCase()}</span>}
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>Available now</DropdownMenuLabel>
        {available.map((entry) => (
          <DropdownMenuItem
            key={entry.code}
            onSelect={() => setLocale(entry.code)}
            className="flex items-center justify-between"
            data-testid={`locale-${entry.code}`}
          >
            <span>
              <span lang={entry.code}>{entry.nativeName}</span>
              <span className="ml-2 text-meta text-muted-foreground">{entry.englishName}</span>
            </span>
            {entry.code === locale ? <Check className="h-4 w-4 text-primary" aria-hidden="true" /> : null}
          </DropdownMenuItem>
        ))}

        {planned.length ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="font-normal text-meta text-muted-foreground">
              Coming as volunteers translate them
            </DropdownMenuLabel>
            {planned.slice(0, 6).map((entry) => (
              <DropdownMenuItem key={entry.code} disabled className="opacity-50">
                <span lang={entry.code}>{entry.nativeName}</span>
                <span className="ml-2 text-meta">{entry.englishName}</span>
              </DropdownMenuItem>
            ))}
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
